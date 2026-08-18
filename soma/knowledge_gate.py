"""知识门控管道 — 五层质量过滤，让外部知识安全进入 SOMA 记忆库

外部知识经过五层过滤后才存入记忆库：
  [1] 相关性过滤  — Foci 语义匹配，不相关→拒绝
  [2] SOMA推理消化 — 7 规律拆解外部内容，提取结构化观点
  [3] 风格对齐    — 与记忆库 Top-20 高重要性记忆对齐风格
  [4] 一致性校验  — 复用 MemoryManager 检测与已有知识的矛盾
  [5] 分级存储    — source=web/external, 临时记忆 7 天 TTL

设计原则：
  - 纯本地管道：所有过滤层均不调用 LLM，零额外成本
  - 可配置阈值：每层阈值可从构造函数注入
  - 复用现有模块：WisdomEngine / ActivationHub / MemoryManager / QualityEvaluator

用法::

    from soma.knowledge_gate import KnowledgeGate

    gate = KnowledgeGate(soma_agent)
    result = gate.ingest(["外部文本1", "外部文本2"], problem_context="当前分析主题")
    print(f"接受: {len(result.accepted)}, 隔离: {len(result.quarantined)}, 拒绝: {len(result.rejected)}")
"""

import math
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from soma.source_trust import SourceTrust, SourceTrustConfig


# ═══════════════════════════════════════════════════════════════
# 配置常量（可覆盖）
# ═══════════════════════════════════════════════════════════════

# 层1: 相关性 — 内容至少匹配几个 Foci 关键词才通过
MIN_FOCUS_KEYWORD_HITS = 2
# 层2: 消化 — 至少提取几个观点才视为有效消化
MIN_EXTRACTED_POINTS = 1
# 层3: 风格 — 对齐度低于此值标记为 quarantined
STYLE_ALIGNMENT_THRESHOLD = 0.3
# 层4: 一致性 — 冲突数超过此值标记为 quarantined
MAX_CONFLICTS_BEFORE_QUARANTINE = 2
# 层5: TTL — 临时外部记忆的生存时间（天）
EXTERNAL_MEMORY_TTL_DAYS = 7
# 外部记忆默认重要性
EXTERNAL_DEFAULT_IMPORTANCE = 0.35
# 高质量外部记忆（通过所有层）的重要性
EXTERNAL_HIGH_IMPORTANCE = 0.55


@dataclass
class ExternalKnowledge:
    """外部知识条目 — 经过五层管道后的完整追踪记录"""

    content: str
    source_url: str = ""
    source_name: str = "external"       # web / document / rag / manual
    trust_score: float = 0.0            # 层0: 来源可信度 0-1
    relevance_score: float = 0.0        # 层1: 相关性 0-1
    content_quality_score: float = 0.0  # 层2.5: 内容质量 0-1（v2.0.9）
    quality_score: float = 0.0          # 层2-4 综合质量: 0-1
    style_alignment: float = 0.0        # 层3: 风格对齐度 0-1
    conflicts: List[str] = field(default_factory=list)  # 层4: 矛盾描述
    corroboration_score: float = 0.0    # 层4.5: 事实印证度 0-1（v2.0.9）
    digested_content: str = ""          # 层2 消化后内容
    aligned_content: str = ""           # 层3 风格对齐后内容
    verdict: str = ""                   # accepted | quarantined | rejected
    reject_reason: str = ""             # 拒绝原因
    foci_matched: List[str] = field(default_factory=list)  # 匹配到的 Foci


@dataclass
class GateResult:
    """一次知识门控的完整结果"""

    accepted: List[ExternalKnowledge] = field(default_factory=list)
    quarantined: List[ExternalKnowledge] = field(default_factory=list)
    rejected: List[ExternalKnowledge] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0

    @property
    def total(self) -> int:
        return len(self.accepted) + len(self.quarantined) + len(self.rejected)

    @property
    def acceptance_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return len(self.accepted) / self.total


class KnowledgeGate:
    """五层知识门控管道

    参数:
        soma_agent: SOMA_Agent 实例（复用 engine/hub/memory_core）
        relevance_threshold: 层1 关键词命中阈值
        style_threshold: 层3 风格对齐阈值
        max_conflicts: 层4 最大允许冲突数
        external_ttl_days: 层5 临时记忆生存天数
    """

    def __init__(
        self,
        soma_agent,
        relevance_threshold: int = MIN_FOCUS_KEYWORD_HITS,
        style_threshold: float = STYLE_ALIGNMENT_THRESHOLD,
        max_conflicts: int = MAX_CONFLICTS_BEFORE_QUARANTINE,
        external_ttl_days: int = EXTERNAL_MEMORY_TTL_DAYS,
        strictness: str = "balanced",
        trust_config: SourceTrustConfig = None,
        min_quality: float = 0.40,
        min_corroboration: float = 0.0,
    ):
        self._agent = soma_agent
        self._relevance_threshold = relevance_threshold
        self._style_threshold = style_threshold
        self._max_conflicts = max_conflicts
        self._ttl_days = external_ttl_days
        self._strictness = strictness
        # v2.0.9: 来源可信度 + 内容质量 + 事实印证阈值
        self._trust = SourceTrust(trust_config)
        self._min_quality = min_quality
        self._min_corroboration = min_corroboration
        self._apply_strictness()

        # 延迟初始化复用组件
        self._memory_manager = None

    def _apply_strictness(self):
        """v2.0.9: 按严格度档位调整过滤阈值。

        - strict: 质量/印证要求更高，孤立事实降级
        - balanced: 使用传入值（默认）
        - permissive: 放宽质量要求，接受更多
        """
        s = (self._strictness or "balanced").lower()
        if s == "strict":
            self._min_quality = min(self._min_quality + 0.15, 0.7)
            self._min_corroboration = max(self._min_corroboration, 0.2)
        elif s == "permissive":
            self._min_quality = max(self._min_quality - 0.15, 0.1)
            self._min_corroboration = 0.0
        # balanced: 不变

    @property
    def memory_manager(self):
        if self._memory_manager is None:
            from soma.memory_manager import MemoryManager
            mc = self._agent.memory
            self._memory_manager = MemoryManager(
                episodic_store=getattr(mc, "episodic", None),
                semantic_store=getattr(mc, "semantic", None),
                skill_store=getattr(mc, "skill", None),
            )
        return self._memory_manager

    # ═══════════════════════════════════════════════════════════
    # 主入口
    # ═══════════════════════════════════════════════════════════

    def ingest(
        self,
        contents: List[str],
        problem_context: str = "",
        source_name: str = "external",
        source_url: str = "",
    ) -> GateResult:
        """外部内容 → 五层过滤 → 分级存储

        Args:
            contents: 外部文本列表
            problem_context: 当前分析主题，用于相关性判断
            source_name: 来源标识 (web/document/rag)
            source_url: 来源 URL（v2.0.9 可选，提供时先过层0来源可信度过滤）

        Returns:
            GateResult 含 accepted/quarantined/rejected
        """
        t0 = time.perf_counter()
        result = GateResult()

        if not contents:
            result.stats = {"reason": "empty_input"}
            return result

        # 对问题上下文做拆解，获得基准 Foci
        # v2.0.9: problem_context 拆出的 Foci 若与内容零相关（如 context 过短/
        # 无关键词，decompose 仅靠加权随机兜底），回退用内容本身拆解作基准，
        # 避免相关性过滤误拒所有内容
        context = problem_context or ""
        foci = self._agent.engine.decompose(context) if context else []
        if foci and contents:
            joined = " ".join(contents)
            total_hits = sum(
                1 for f in foci for kw in getattr(f, "keywords", [])
                if kw and kw.lower() in joined.lower()
            )
            if total_hits == 0:
                fallback = self._agent.engine.decompose(joined[:300])
                if fallback:
                    foci = fallback

        # 逐条处理
        for raw_text in contents:
            if not raw_text or len(raw_text.strip()) < 10:
                continue

            ek = ExternalKnowledge(
                content=raw_text.strip(),
                source_name=source_name,
                source_url=source_url,
            )

            # ── 层0: 来源可信度过滤（v2.0.9）──
            # 提供 source_url 时先查来源信誉，黑名单域名直接拒绝
            if source_url:
                ek.trust_score, verdict = self._trust.rate(source_url)
                if verdict == "rejected":
                    ek.verdict = "rejected"
                    ek.reject_reason = f"来源不可信: {source_url}"
                    result.rejected.append(ek)
                    continue

            # ── 层1: 相关性过滤 ──
            ek = self._filter_relevance(ek, foci)
            if ek.verdict == "rejected":
                result.rejected.append(ek)
                continue

            # ── 层2: SOMA 推理消化 ──
            ek = self._digest_with_laws(ek, foci)
            if ek.verdict == "rejected":
                result.rejected.append(ek)
                continue

            # ── 层2.5: 内容质量检测（v2.0.9）──
            ek = self._check_content_quality(ek)
            if ek.verdict == "rejected":
                result.rejected.append(ek)
                continue

            # ── 层3: 风格对齐 ──
            ek = self._align_style(ek)

            # ── 层4: 一致性校验 ──
            ek = self._check_consistency(ek)

            # ── 层4.5: 事实印证（v2.0.9）──
            ek = self._corroborate(ek)

            # ── 综合质量分 ──
            ek.quality_score = self._compute_quality(ek)

            # ── 判定 ──
            low_quality = ek.content_quality_score < self._min_quality
            low_corroboration = ek.corroboration_score < self._min_corroboration
            if ek.style_alignment < self._style_threshold and len(ek.conflicts) > self._max_conflicts:
                ek.verdict = "rejected"
                ek.reject_reason = f"风格对齐度{ek.style_alignment:.2f}低于阈值且冲突{len(ek.conflicts)}超限"
                result.rejected.append(ek)
            elif low_quality:
                ek.verdict = "rejected"
                ek.reject_reason = f"内容质量{ek.content_quality_score:.2f}低于阈值{self._min_quality}"
                result.rejected.append(ek)
            elif len(ek.conflicts) > self._max_conflicts:
                ek.verdict = "quarantined"
                ek.reject_reason = f"冲突{len(ek.conflicts)}项超限，需人工确认"
                result.quarantined.append(ek)
            elif ek.style_alignment < self._style_threshold:
                ek.verdict = "quarantined"
                ek.reject_reason = f"风格对齐度{ek.style_alignment:.2f}低于阈值"
                result.quarantined.append(ek)
            elif low_corroboration:
                # 孤立事实（无印证）降级为 quarantined，避免错误知识污染
                ek.verdict = "quarantined"
                ek.reject_reason = f"事实印证度{ek.corroboration_score:.2f}低于阈值，缺少已有记忆支撑"
                result.quarantined.append(ek)
            else:
                ek.verdict = "accepted"
                result.accepted.append(ek)

        # ── 层5: 分级存储 ──
        self._tiered_store(result)

        result.duration_ms = round((time.perf_counter() - t0) * 1000, 1)
        result.stats = {
            "total": result.total,
            "accepted": len(result.accepted),
            "quarantined": len(result.quarantined),
            "rejected": len(result.rejected),
            "acceptance_rate": round(result.acceptance_rate, 2),
            "duration_ms": result.duration_ms,
        }
        return result

    # ═══════════════════════════════════════════════════════════
    # 层1: 相关性过滤
    # ═══════════════════════════════════════════════════════════

    def _filter_relevance(
        self, ek: ExternalKnowledge, foci: list
    ) -> ExternalKnowledge:
        """基于 Foci 关键词判断内容相关性"""
        if not foci:
            ek.relevance_score = 0.5  # 无 Foci 时中庸
            return ek

        text_lower = ek.content.lower()
        total_hits = 0
        matched_laws = []

        for f in foci:
            law_id = getattr(f, "law_id", "")
            keywords = getattr(f, "keywords", [])
            hits = sum(1 for kw in keywords if kw.lower() in text_lower)
            if hits > 0:
                total_hits += hits
                if law_id:
                    matched_laws.append(law_id)

        ek.foci_matched = matched_laws
        # 归一化：命中的关键词数 / (foci数 * 平均关键词数)
        avg_kw = max(sum(len(getattr(f, "keywords", [])) for f in foci) / max(len(foci), 1), 1)
        ek.relevance_score = round(min(total_hits / max(avg_kw * len(foci), 1), 1.0), 3)

        if total_hits < self._relevance_threshold:
            ek.verdict = "rejected"
            ek.reject_reason = (
                f"相关性不足: 仅命中{total_hits}个关键词 "
                f"(阈值{self._relevance_threshold}), foci={matched_laws}"
            )

        return ek

    # ═══════════════════════════════════════════════════════════
    # 层2: SOMA 推理消化
    # ═══════════════════════════════════════════════════════════

    def _digest_with_laws(
        self, ek: ExternalKnowledge, foci: list
    ) -> ExternalKnowledge:
        """7 规律拆解外部内容，提取结构化观点"""
        try:
            content_foci = self._agent.engine.decompose(ek.content)
        except Exception:
            # 拆解失败不拒绝，保留原始内容
            ek.digested_content = ek.content[:500]
            return ek

        if not content_foci:
            ek.verdict = "rejected"
            ek.reject_reason = "SOMA无法拆解该内容，可能过于碎片化或语法不完整"
            return ek

        # 为每段 Foci 生成结构化观点
        points = []
        for f in content_foci[:5]:  # 最多取 5 个 Foci
            dim = getattr(f, "dimension", "")
            law = getattr(f, "law_id", "")
            rationale = getattr(f, "rationale", "")
            if dim:
                points.append(f"[{law}] {dim}: {rationale}")

        if not points:
            ek.digested_content = ek.content[:300]
        else:
            ek.digested_content = "\n".join(points)

        if len(points) < MIN_EXTRACTED_POINTS:
            ek.verdict = "rejected"
            ek.reject_reason = f"仅提取{len(points)}个观点，低于最低阈值{MIN_EXTRACTED_POINTS}"

        return ek

    # ═══════════════════════════════════════════════════════════
    # 层2.5: 内容质量检测（v2.0.9）
    # ═══════════════════════════════════════════════════════════

    def _check_content_quality(self, ek: ExternalKnowledge) -> ExternalKnowledge:
        """评估内容质量。有 LLM 时用 LLM 增强，否则纯本地启发式。"""
        from soma.content_quality import assess_content_quality

        use_llm = self._has_llm()
        result = assess_content_quality(
            ek.content, agent=self._agent if use_llm else None,
            use_llm=use_llm,
        )
        ek.content_quality_score = result["score"]
        if result["score"] < self._min_quality:
            ek.verdict = "rejected"
            ek.reject_reason = (
                f"内容质量{result['score']:.2f}低于阈值{self._min_quality}"
                + (f"（{result['llm_reason']}）" if result.get("llm_reason") else "")
            )
        return ek

    def _has_llm(self) -> bool:
        """当前 agent 是否配置了 LLM（有 key 或非 mock 模型）。"""
        cfg = getattr(self._agent, "config", None)
        if cfg is None:
            return False
        return bool(
            getattr(cfg, "llm_api_key", "")
            or getattr(cfg, "llm_model", "mock") != "mock"
        )

    # ═══════════════════════════════════════════════════════════
    # 层4.5: 事实印证（v2.0.9）
    # ═══════════════════════════════════════════════════════════

    def _corroborate(self, ek: ExternalKnowledge) -> ExternalKnowledge:
        """事实印证：用内容关键词检索已有记忆，计算印证度。

        印证度高 → 与既有知识一致（可信）；印证度为 0 → 孤立事实（降权）。
        """
        from soma.engine import _extract_keywords

        text = ek.content or ek.digested_content or ""
        keywords = _extract_keywords(text, max_keywords=8)
        if not keywords:
            ek.corroboration_score = 0.0
            return ek

        try:
            episodic = getattr(self._agent.memory, "episodic", None)
            if episodic is None or not hasattr(episodic, "query_by_keywords"):
                ek.corroboration_score = 0.0
                return ek
            results = episodic.query_by_keywords(keywords, top_k=10)
        except Exception:
            ek.corroboration_score = 0.0
            return ek

        if not results:
            ek.corroboration_score = 0.0
            return ek

        # 印证度 = 高重要性命中比例（已有高价值记忆支撑则更可信）
        matched = [m for m in results if getattr(m, "importance", 0) >= 0.5]
        ek.corroboration_score = round(len(matched) / len(results), 3)
        return ek

    # ═══════════════════════════════════════════════════════════
    # 层3: 风格对齐
    # ═══════════════════════════════════════════════════════════

    def _align_style(self, ek: ExternalKnowledge) -> ExternalKnowledge:
        """与记忆库 Top-20 高重要性记忆对齐风格。

        分析维度: 平均句长 / 术语密度 / 论证结构模式。
        返回在 digested_content 基础上调整后的文本和对齐度。
        """
        style_samples = self._get_style_samples(20)
        if not style_samples:
            # 记忆库为空，无法对齐，原始内容直接使用
            ek.aligned_content = ek.digested_content or ek.content[:500]
            ek.style_alignment = 0.5
            return ek

        # 计算目标风格特征
        target = self._extract_style_features(style_samples)
        # 计算外部内容风格特征
        source_text = ek.digested_content or ek.content
        source_features = self._extract_style_features([source_text])

        # 计算对齐度（特征向量的余弦相似度）
        alignment = self._style_similarity(source_features, target)
        ek.style_alignment = round(alignment, 3)

        # 轻量风格调整：调整句长使之接近目标
        ek.aligned_content = self._adjust_style(source_text, source_features, target)

        return ek

    def _get_style_samples(self, n: int = 20) -> List[str]:
        """从记忆库获取高重要性风格样本

        v2.0.9: 修复生产环境静默失效——之前调用不存在的 episodic.search()，
        真实 EpisodicStore 无此方法，样本永远为空。改用 get_style_samples()。
        """
        try:
            episodic = getattr(self._agent.memory, "episodic", None)
            if episodic is None:
                return []
            # 优先用真实接口；Fake/旧接口兜底
            if hasattr(episodic, "get_style_samples"):
                return episodic.get_style_samples(n)
            if hasattr(episodic, "search"):
                results = episodic.search("", top_k=n * 3)
                return [
                    getattr(m, "content", str(m))
                    for m in sorted(
                        results, key=lambda m: getattr(m, "importance", 0),
                        reverse=True,
                    )[:n]
                    if len(getattr(m, "content", str(m))) > 50
                ]
        except Exception:
            pass
        return []

    def _extract_style_features(self, texts: List[str]) -> Dict[str, float]:
        """提取文本集的风格特征向量"""
        if not texts:
            return {"avg_sent_len": 25.0, "term_density": 0.15, "structure_score": 0.5}

        all_sents = []
        total_chars = 0
        # 术语检测（大写缩写、专业名词模式）
        term_count = 0

        for t in texts:
            # 分句
            sents = re.split(r"[。！？\.!\?\n]+", t)
            sents = [s.strip() for s in sents if len(s.strip()) > 5]
            all_sents.extend(sents)
            total_chars += len(t)
            # 检测术语：2-4字连续大写英文或中英混合专业词
            terms = re.findall(r"\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b|[A-Z]{2,6}", t)
            term_count += len(terms)

        avg_sent_len = sum(len(s) for s in all_sents) / max(len(all_sents), 1)
        term_density = term_count / max(total_chars, 1)
        # 结构分：句子数>3 且平均句长>15 认为结构良好
        structure_score = min(len(all_sents) / 10, 1.0) * min(avg_sent_len / 30, 1.0)

        return {
            "avg_sent_len": round(avg_sent_len, 1),
            "term_density": round(term_density, 4),
            "structure_score": round(structure_score, 3),
        }

    def _style_similarity(
        self, source: Dict[str, float], target: Dict[str, float]
    ) -> float:
        """计算两组风格特征的相似度（0-1）"""
        keys = ["avg_sent_len", "term_density", "structure_score"]
        # 对 avg_sent_len 做归一化：差值越小越好
        sent_diff = abs(source.get("avg_sent_len", 25) - target.get("avg_sent_len", 25))
        sent_sim = max(0, 1.0 - sent_diff / 50.0)

        term_diff = abs(source.get("term_density", 0.1) - target.get("term_density", 0.1))
        term_sim = max(0, 1.0 - term_diff / 0.3)

        struct_diff = abs(
            source.get("structure_score", 0.5) - target.get("structure_score", 0.5)
        )
        struct_sim = max(0, 1.0 - struct_diff)

        # 加权平均
        return 0.4 * sent_sim + 0.3 * term_sim + 0.3 * struct_sim

    def _adjust_style(
        self,
        text: str,
        source_features: Dict[str, float],
        target_features: Dict[str, float],
    ) -> str:
        """轻量风格调整：不依赖 LLM 的文本风格微调。

        策略：根据句长差异做截断/合并，保持原意不变。
        当记忆库和目标风格差异过大时不强行调整。
        """
        sent_diff = abs(
            source_features.get("avg_sent_len", 25)
            - target_features.get("avg_sent_len", 25)
        )
        if sent_diff < 10:
            # 差异不大，原样返回
            return text

        # 句长差异较大时，轻量调整
        sents = re.split(r"(?<=[。！？\.!\?])\s*", text)
        sents = [s.strip() for s in sents if len(s.strip()) > 3]

        if not sents:
            return text

        target_len = target_features.get("avg_sent_len", 25)
        adjusted = []
        buffer = ""

        for s in sents:
            if len(buffer) + len(s) < target_len * 1.5:
                buffer += s
            else:
                if buffer:
                    adjusted.append(buffer)
                buffer = s

        if buffer:
            adjusted.append(buffer)

        return "。".join(adjusted) if adjusted else text

    # ═══════════════════════════════════════════════════════════
    # 层4: 一致性校验
    # ═══════════════════════════════════════════════════════════

    def _check_consistency(self, ek: ExternalKnowledge) -> ExternalKnowledge:
        """检测外部知识与已有语义三元组的矛盾"""
        try:
            conflicts = self.memory_manager.detect_conflicts()
        except Exception:
            ek.conflicts = []
            return ek

        text_to_check = ek.aligned_content or ek.digested_content or ek.content
        text_lower = text_to_check.lower()

        relevant_conflicts = []
        for c in conflicts:
            # 检查冲突是否与当前内容相关
            subj_in = c.subject.lower() in text_lower
            pred_in = c.predicate.lower() in text_lower
            obj_a_in = c.object_a.lower() in text_lower
            obj_b_in = c.object_b.lower() in text_lower

            if subj_in or pred_in or obj_a_in or obj_b_in:
                relevant_conflicts.append(c.description)

        ek.conflicts = relevant_conflicts[:5]  # 最多保留 5 条
        return ek

    # ═══════════════════════════════════════════════════════════
    # 层5: 分级存储
    # ═══════════════════════════════════════════════════════════

    def _tiered_store(self, result: GateResult):
        """分级存储过滤后的知识到记忆库。

        accepted → importance=0.55, source=external, 高质
        quarantined → importance=0.25, source=external:quarantined, 标记待确认
        rejected → 不存储
        """
        now = time.time()
        ttl_seconds = self._ttl_days * 86400

        for ek in result.accepted:
            self._store_knowledge(
                ek, importance=EXTERNAL_HIGH_IMPORTANCE,
                ttl=ttl_seconds, status="accepted",
            )

        for ek in result.quarantined:
            self._store_knowledge(
                ek, importance=0.25,
                ttl=ttl_seconds, status="quarantined",
            )

    def _store_knowledge(
        self, ek: ExternalKnowledge, importance: float,
        ttl: float, status: str,
    ):
        """将一条知识存入记忆库"""
        try:
            content = ek.aligned_content or ek.digested_content or ek.content
            ctx = {
                "source": f"external:{ek.source_name}",
                "source_url": ek.source_url,
                "status": status,
                "relevance_score": ek.relevance_score,
                "quality_score": ek.quality_score,
                "style_alignment": ek.style_alignment,
                "ttl_seconds": ttl,
                "expires_at": time.time() + ttl,
                "conflicts": ek.conflicts,
            }

            self._agent.remember(
                f"[外部知识-{status}] {content[:500]}",
                ctx,
                importance=importance,
            )
        except Exception:
            pass  # 存储失败不阻塞管道

    # ═══════════════════════════════════════════════════════════
    # 质量分计算
    # ═══════════════════════════════════════════════════════════

    def _compute_quality(self, ek: ExternalKnowledge) -> float:
        """综合质量分 = 相关性*0.3 + 风格对齐*0.35 + (1-冲突惩罚)*0.35"""
        conflict_penalty = min(len(ek.conflicts) * 0.15, 1.0)
        consistency = max(0, 1.0 - conflict_penalty)
        quality = (
            ek.relevance_score * 0.30
            + ek.style_alignment * 0.35
            + consistency * 0.35
        )
        return round(quality, 3)
