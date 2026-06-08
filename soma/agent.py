import hashlib
import logging
import time
from functools import lru_cache
from typing import Any, Dict, List, Optional

from litellm import completion

from soma.base import ActivatedMemory, Focus
from soma.config import SOMAConfig, load_config
from soma.embedder import SOMAEmbedder
from soma.engine import WisdomEngine
from soma.evolve import MetaEvolver
from soma.hub import ActivationHub
from soma.memory.core import MemoryCore
from soma.quality import QualityEvaluator
from soma.retry import llm_retry
from soma.zhongdao import ZhongdaoEngine

_log = logging.getLogger(__name__)


class SOMA_Agent:
    """顶层统一对话接口 — 编排完整智者思维管道"""

    # ── v0.6.0 推理模板：每条规律对应一个结构化推理框架 ─────
    _REASONING_TEMPLATES: Dict[str, str] = {
        "first_principles": (
            "**第一性原理推理**\n"
            "1. 基本要素识别：此问题最基础、不可再分的构成要素有哪些？\n"
            "2. 假设检验：当前分析中有哪些未经验证的隐含假设？如果这些假设不成立会怎样？\n"
            "3. 重构推导：抛开现有方案，从基本要素重新构建，会得到什么不同的解法？"
        ),
        "systems_thinking": (
            "**系统思维推理**\n"
            "1. 系统边界与结构：系统的边界、输入、输出是什么？关键组件及其连接关系？\n"
            "2. 反馈回路：增强回路（正反馈）在哪里？平衡回路（负反馈）在哪里？\n"
            "3. 杠杆点：系统中哪个节点的最小改变能产生最大的系统性影响？"
        ),
        "contradiction_analysis": (
            "**矛盾分析推理**\n"
            "1. 对立面识别：此问题中存在哪些对立统一的力量或利益？\n"
            "2. 主要矛盾判定：哪一对矛盾是当前阶段的主要矛盾？为什么？\n"
            "3. 矛盾转化：在什么条件下主要矛盾会发生转化？转化后的新主要矛盾可能是什么？"
        ),
        "pareto_principle": (
            "**二八法则推理**\n"
            "1. 关键少数识别：哪些 20% 的因素导致了 80% 的结果？判断依据是什么？\n"
            "2. 非关键因素排除：哪些因素是「有用的多数」但不应分散精力？\n"
            "3. 资源聚焦：将有限资源集中投放在哪几个关键点上收益最大？"
        ),
        "inversion": (
            "**逆向思考推理**\n"
            "1. 失败模式枚举：如果要让这件事彻底失败，有哪些最有效的路径？\n"
            "2. 脆弱点暴露：逆向推演暴露了当前方案中的哪些脆弱点或盲区？\n"
            "3. 防御策略：针对暴露的脆弱点，应该采取哪些预防或缓解措施？"
        ),
        "analogical_reasoning": (
            "**类比推理**\n"
            "1. 同构领域识别：哪些领域或场景在结构上与当前问题同构？相似点在哪里？\n"
            "2. 可迁移模式提取：从类比领域中可提取哪些已验证的有效模式或方法？\n"
            "3. 适应性改造：这些模式如何适配当前问题的特殊约束和条件？"
        ),
        "evolutionary_lens": (
            "**演进视角推理**\n"
            "1. 阶段定位：当前问题处于其生命周期的哪个阶段（萌芽/成长/成熟/衰退）？判断依据？\n"
            "2. 演进驱动力：推动问题向下一个阶段演进的核心驱动力是什么？\n"
            "3. 趋势预判：基于当前演进轨迹，6-12 个月后此问题最可能呈现什么状态？"
        ),
    }

    # ── v0.6.0 假设模板：每条规律对应一个可检验假设 ─────────
    _HYPOTHESIS_TEMPLATES: Dict[str, str] = {
        "first_principles": (
            "当前对「{problem}」的基本认知中，最核心的未验证假设是___，"
            "如果这个假设被推翻，结论会如何改变？"
        ),
        "systems_thinking": (
            "「{problem}」的系统杠杆点可能在___，在此处施加干预的预期连锁反应是___"
        ),
        "contradiction_analysis": (
            "「{problem}」的主要矛盾是___与___的对立，矛盾的主要方面是___"
        ),
        "pareto_principle": (
            "在「{problem}」中，真正决定 80% 结果的那 20% 关键因素是___"
        ),
        "inversion": (
            "导致「{problem}」恶化的最有效途径是___，这暴露了当前方案的___漏洞"
        ),
        "analogical_reasoning": (
            "与「{problem}」最相似的已知成功/失败场景是___，从该场景可借鉴的核心经验是___"
        ),
        "evolutionary_lens": (
            "「{problem}」当前处于___阶段，下一个阶段是___，过渡的标志性信号是___"
        ),
    }

    # ── v0.6.0 组合模板的推理框架 ───────────────────────────
    _COMBO_REASONING: Dict[str, str] = {
        "combo_first_principles_systems_thinking": (
            "**根因系统分析推理**\n"
            "1. 从基本要素出发，追踪其在系统网络中的传导路径\n"
            "2. 识别哪个基本要素的变化会引发系统级连锁反应\n"
            "3. 定位深层杠杆点：既能触及根本、又能影响全局的干预位置"
        ),
        "combo_systems_thinking_contradiction_analysis": (
            "**动态张力分析推理**\n"
            "1. 识别系统中相互制衡的力量对\n"
            "2. 判断哪对张力是当前系统演化的主要驱动力\n"
            "3. 分析如果其中一方被削弱或加强，系统的新的平衡点在哪里"
        ),
        "combo_contradiction_analysis_inversion": (
            "**辩证反思推理**\n"
            "1. 从正面论证当前方案的正确性\n"
            "2. 从反面论证当前方案可能出错的所有路径\n"
            "3. 正反综合：在哪些条件下正面成立、在哪些条件下反面成立"
        ),
        "combo_first_principles_pareto_principle": (
            "**要素优先级排序推理**\n"
            "1. 列出所有基本构成要素\n"
            "2. 按影响力对每个要素排序，识别前 20%\n"
            "3. 验证：忽略后 80% 要素，仅用前 20% 要素能否解释 80% 的结果"
        ),
        "combo_systems_thinking_evolutionary_lens": (
            "**系统演进洞察推理**\n"
            "1. 绘制系统当前状态的结构图\n"
            "2. 回溯系统从上一阶段到当前的演变路径\n"
            "3. 基于当前结构中的张力，预判系统的下一阶段形态"
        ),
        "combo_analogical_reasoning_first_principles": (
            "**跨域本质映射推理**\n"
            "1. 从类比领域提取其成功的底层基本原理\n"
            "2. 剥离类比领域的特殊约束，保留可迁移的本质\n"
            "3. 将本质原理映射到当前问题的具体约束中"
        ),
    }

    def __init__(self, config: SOMAConfig, agent_id: str = "", group_id: str = ""):
        self.config = config
        self.agent_id = agent_id
        self.group_id = group_id

        # 嵌入器（需在引擎之前创建，供语义匹配兜底使用）
        self.embedder = None
        if config.use_vector_search:
            self.embedder = SOMAEmbedder(config)
            # v1.1.1: 预热嵌入模型（后台下载，不阻塞）
            import threading
            threading.Thread(
                target=self.embedder.warmup, daemon=True,
                name="soma-embedder-warmup",
            ).start()

        # 加载思维框架
        framework = config.framework or load_config(config.framework_path)
        self.engine = WisdomEngine(framework, embedder=self.embedder)

        # 记忆核心
        self.memory = MemoryCore(config, embedder=self.embedder)

        # 自适应参数：根据当前记忆总量调整 top_k / threshold
        if config.adaptive_params:
            from soma.config import adaptive_top_k, adaptive_recall_threshold
            data_count = self.memory.stats().get("episodic", 0)
            top_k = adaptive_top_k(data_count)
            threshold = adaptive_recall_threshold(data_count)
        else:
            top_k = config.default_top_k
            threshold = config.recall_threshold

        # 双向激活调度器
        self.hub = ActivationHub(
            self.memory,
            top_k=top_k,
            threshold=threshold,
        )

        # 元认知进化器（持久化到 dashboard_data）
        self.evolver = MetaEvolver(self.engine, memory_core=self.memory,
                                   persist_dir=config.episodic_persist_dir)

        # v0.8.0: 反思质量评估器
        self.quality_evaluator = QualityEvaluator(embedder=self.embedder)

        # LLM 短时缓存（避免相同 prompt 重复调用）
        self._llm_cache: Dict[str, tuple] = {}

        # 保存最近一次构建的 prompt（供仪表盘可视化）
        self._last_prompt: str = ""
        # 保存最近一次反视角搜索结果（供 _build_prompt 使用）
        self._last_anti_memories: List[ActivatedMemory] = []
        # 保存最近一次推理框架（v0.6.0 推理引擎）
        self._last_reasoning: List[Dict] = []

        # v1.1.1: 当前问题复杂度（供 _build_prompt 自适应）
        self._current_complexity: int = 1

        # v0.9.1: 框架锚定检测 — 跟踪最近用户输入
        self._recent_user_turns: List[str] = []
        self._last_frame_anchoring: Optional[dict] = None

        # v1.1.2: 中道引擎 — 会话内实时偏差检测与自校正
        # v1.1.5: 支持 "auto" 模式 — L2+ 问题自动激活，L1 跳过
        self.zhongdao: Optional[ZhongdaoEngine] = None
        self._zhongdao_mode: str = "off"
        if config.enable_zhongdao is True or config.enable_zhongdao == "auto":
            self.zhongdao = ZhongdaoEngine(config)
            self._zhongdao_mode = "auto" if config.enable_zhongdao == "auto" else "on"

    def respond(self, problem: str, user_id: str = "") -> str:
        """完整管道：拆解 → 双向激活 → 合成 → 应答"""
        import time

        # Step 0: 评估问题复杂度
        complexity = self._assess_complexity(problem)
        self._current_complexity = complexity

        # v0.9.1: 记录用户输入用于框架锚定检测
        if self.config.enable_frame_detection:
            self._recent_user_turns.append(problem)
            max_window = self.config.frame_detection_window * 2
            if len(self._recent_user_turns) > max_window:
                self._recent_user_turns = self._recent_user_turns[-max_window:]
            self._last_frame_anchoring = self.hub.detect_frame_anchoring(
                self._recent_user_turns
            )
        else:
            self._last_frame_anchoring = None

        # Step 1: 问题拆解
        foci = self.engine.decompose(problem)
        # L3复杂问题多取foci，L1简单问题精简
        if complexity == 3:
            pass  # 保留全部
        elif complexity == 1 and len(foci) > 2:
            foci = foci[:2]

        # Step 2: 双向激活记忆（复杂度自适应 top_k）
        original_top_k = self.hub.top_k
        if complexity == 3:
            self.hub.top_k = min(original_top_k * 2, 15)
        elif complexity == 1:
            self.hub.top_k = max(original_top_k // 2, 2)
        try:
            activated = self.hub.activate(
                foci, user_id=user_id, laws=self.engine.laws,
                agent_id=self.agent_id, group_id=self.group_id,
            )
        finally:
            self.hub.top_k = original_top_k

        # Step 2.5: 确认偏误检测 — L2/L3 问题检索反视角证据
        if complexity >= 2:
            self._last_anti_memories = self.hub.anti_confirmation_search(
                foci, user_id=user_id, agent_id=self.agent_id, group_id=self.group_id,
            )
        else:
            self._last_anti_memories = []

        # Step 2.6: v0.8.0 收集记忆建议的焦点，合并进推理框架
        suggested_foci = []
        for am in activated:
            if am.suggested_focus and am.suggested_focus.weight >= 0.1:
                suggested_foci.append(am.suggested_focus)
        if suggested_foci:
            foci = foci + suggested_foci

        # v1.1.2: 中道引擎 — 会话内实时偏差检测与校正
        # v1.1.5: auto 模式下，L1 简单问题跳过中道（节省开销）
        _use_zhongdao = self.zhongdao is not None
        if _use_zhongdao and self._zhongdao_mode == "auto" and complexity <= 1:
            _use_zhongdao = False
        if _use_zhongdao:
            self.zhongdao.track(foci)
            usage_snapshot = dict(self.zhongdao._session_usage)
            foci, zhongdao_corrections = self.zhongdao.detect_and_correct(
                foci, self.engine.laws,
            )
            if zhongdao_corrections:
                total = sum(usage_snapshot.values())
                overuse_info = ", ".join(
                    f"{lid}={c}/{total}({c/total:.0%})"
                    for lid, c in usage_snapshot.items()
                )
                _log.info(
                    "中道校正触发: 总采样=%d, 使用分布=[%s], 校正项=%d",
                    total, overuse_info, len(zhongdao_corrections),
                )
                for c in zhongdao_corrections:
                    if c["type"] == "overuse_penalty":
                        _log.info(
                            "  └ 降权: %s(%s) %.4f→%.4f (使用率%.0%%)",
                            c["law_name"], c["law_id"],
                            c["old_weight"], c["new_weight"],
                            c["usage_ratio"] * 100,
                        )
                    elif c["type"] == "neglect_boost":
                        _log.info(
                            "  └ 提权注入: %s(%s) 权重=%.4f",
                            c["law_name"], c["law_id"], c["weight"],
                        )

        # Step 2.7: 构建结构化推理框架（v0.6.0 推理引擎）
        # v1.1.1: L1简单问题跳过推理框架，避免回复膨胀
        if complexity >= 2:
            self._last_reasoning = self._execute_reasoning(
                problem, foci, activated, self._last_anti_memories,
            )
        else:
            self._last_reasoning = []

        # Step 3: 合成 Prompt
        prompt = self._build_prompt(problem, foci, activated)

        # Step 4: 调用 LLM
        answer = self._call_llm(prompt, user_id)

        # Step 4.5: v0.8.0 反思质量自评
        quality = self.quality_evaluator.evaluate(
            answer=answer,
            memory_contents=[am.memory.content for am in activated],
            conflict_count=len(getattr(self.hub, 'last_conflicts', [])),
        )
        if quality["needs_reflection"]:
            self._last_quality_note = (
                f"[质量反馈] 综合分 {quality['overall']:.2f} ({quality['grade']}) — "
                f"一致性 {quality['consistency']:.2f} "
                f"连贯性 {quality['coherence']:.2f} "
                f"可操作性 {quality['actionability']:.2f}"
            )
        else:
            self._last_quality_note = ""

        # Step 4.6: 因果抽取（v0.6.0，仅复杂度达标且开关开启时执行）
        if complexity >= self.config.causal_extraction_complexity:
            self._extract_causal_relations(problem, answer)

        # Step 5: 更新访问计数（Python 对象 + 数据库持久化）
        for am in activated:
            am.memory.access_count += 1
            if am.source == "episodic":
                self.memory.episodic.increment_access(am.memory.id)

        # Step 6: 写入进化器上下文（含问题文本，供触发词追踪）
        self.evolver.set_current_context(foci, activated, problem)

        # Step 7: 录制 session（供仪表盘消费）
        self.record_session(problem, answer, foci, activated)

        return answer

    @staticmethod
    def _assess_complexity(problem: str) -> int:
        """评估问题复杂度：1=简单 2=中等 3=复杂"""
        score = 1
        # 长度因子
        if len(problem) > 100:
            score += 1
        # 深度词因子
        depth_words = [
            "为什么", "如何", "深层", "根本", "系统", "矛盾",
            "机制", "权衡", "复杂", "瓶颈", "困境", "根源",
        ]
        if any(w in problem for w in depth_words):
            score += 1
        return min(score, 3)

    # ── v0.6.0 推理引擎方法 ──────────────────────────────

    def _match_template(self, law_id: str, templates: Dict[str, str]) -> str:
        """按 law_id 匹配模板，支持组合模板前缀匹配"""
        if law_id in templates:
            return templates[law_id]
        for key in templates:
            if key in law_id or law_id in key:
                return templates[key]
        return ""

    def _execute_reasoning(
        self,
        problem: str,
        foci: List[Focus],
        activated: List[ActivatedMemory],
        anti_memories: List[ActivatedMemory],
    ) -> List[Dict]:
        """构建结构化推理框架 — 为每个 Focus 匹配推理模板、假设和证据。

        不调用 LLM，纯模板组织。结果注入 Prompt 引导 LLM 按框架思考。
        """
        blocks = []
        # L3复杂度上限：最多7个foci，避免Prompt过长
        if len(foci) > 7:
            foci = sorted(foci, key=lambda f: f.weight, reverse=True)[:7]
        for i, focus in enumerate(foci):
            # 匹配推理模板 — 组合模板优先
            template = ""
            if focus.law_id.startswith("combo_"):
                template = self._match_template(focus.law_id, self._COMBO_REASONING)
            if not template:
                template = self._match_template(focus.law_id, self._REASONING_TEMPLATES)
            if not template:
                template = (
                    f"从「{focus.dimension[:60]}」的角度分析：\n"
                    "请列出 3 个关键洞察，每个洞察附对应的证据或推理依据。"
                )

            # 匹配假设模板
            hypo_tmpl = self._match_template(focus.law_id, self._HYPOTHESIS_TEMPLATES)
            hypothesis = ""
            if hypo_tmpl:
                hypothesis = hypo_tmpl.replace("{problem}", problem)

            # 收集与此 Focus 相关的证据片段
            evidence_parts = []
            focus_kw = set(focus.keywords[:5]) if focus.keywords else set()
            for am in activated:
                content = am.memory.content
                hits = sum(1 for kw in focus_kw if kw.lower() in content.lower())
                if hits > 0:
                    evidence_parts.append(
                        f"[关联度 {am.activation_score:.2f}] {content[:200]}"
                    )
            # 反视角证据
            anti_parts = []
            for am in anti_memories:
                content = am.memory.content
                hits = sum(1 for kw in focus_kw if kw.lower() in content.lower())
                if hits > 0:
                    anti_parts.append(
                        f"[反对视角] {content[:200]}"
                    )

            blocks.append({
                "index": i + 1,
                "dimension": focus.dimension,
                "weight": focus.weight,
                "template": template,
                "hypothesis": hypothesis,
                "evidence": evidence_parts[:3],
                "counter_evidence": anti_parts[:2],
            })

        return blocks

    def record_session(
        self, problem: str, answer: str,
        foci: List[Focus], activated: List[ActivatedMemory],
    ) -> None:
        """录制一次对话会话到 AnalyticsStore。

        供所有调用路径（respond / chat / 外部流式）统一使用。
        接入方在流式收集完 answer 后调用此方法即可。
        """
        import sys, time
        try:
            from soma.analytics import AnalyticsStore
            store = AnalyticsStore(self.config.episodic_persist_dir)
            sid = f"session_{int(time.time())}"
            store.record_session({
                "id": sid,
                "problem": problem,
                "mock_mode": False,
                "provider_used": self.config.llm_model or "unknown",
                "response_time_ms": 0,
                "foci": [{"law_id": f.law_id, "dimension": f.dimension,
                          "keywords": f.keywords[:8], "weight": f.weight,
                          "rationale": f.rationale} for f in foci],
                "activated_memories": [self.hub.explain_activation(am) for am in activated],
                "answer": answer,
                "prompt": getattr(self, '_last_prompt', ''),
                "memory_stats": self.memory.stats(),
                "weights": self.evolver.get_weights(),
            })

            # v1.1.3: 中道校正持久化日志
            if self.zhongdao is not None and self.zhongdao.enabled:
                corrections = self.zhongdao.last_corrections
                if corrections:
                    agent_id = getattr(self, 'agent_id', '')
                    for c in corrections:
                        store.record_zhongdao_correction(
                            c, session_id=sid, agent_id=agent_id,
                        )
        except Exception as e:
            print(f"[soma] 录制会话失败 (dir={self.config.episodic_persist_dir}): {e}",
                  file=sys.stderr)

    def _build_prompt(
        self,
        problem: str,
        foci: List[Focus],
        memories: List[ActivatedMemory],
    ) -> str:
        """构建 LLM Prompt：L1轻量直答 / L2+完整推理框架（v1.1.1 复杂度自适应）"""
        complexity = getattr(self, '_current_complexity', 2)

        # ── L1 轻量模式：简单问答，遵守用户长度约束 ────────
        if complexity == 1:
            # 提取用户长度约束（"50字以内"、"三个要点"等）
            import re
            constraint_hints = []
            word_limit = re.search(r'(\d+)\s*字[以之]?[内下]', problem)
            if word_limit:
                constraint_hints.append(f"请严格控制在{word_limit.group(1)}字以内")
            point_limit = re.search(r'(\d+)\s*[个条点项]\s*(要点|建议|原因|步骤|方面)', problem)
            if point_limit:
                constraint_hints.append(f"请只给出{point_limit.group(1)}个{point_limit.group(2)}")
            constraint_text = "。".join(constraint_hints) if constraint_hints else "请简洁回答，不要展开"

            memory_text = ""
            if memories:
                parts = []
                for i, am in enumerate(memories[:3]):
                    parts.append(f"[参考{i+1}] {am.memory.content[:200]}")
                memory_text = "## 参考信息\n" + "\n".join(parts)

            prompt = f"""你是一位智者，善于简洁有力地回答问题。

{memory_text}

## 当前问题
{problem}

---
要求：
- {constraint_text}
- 用自然交谈的语气回答，不要使用模板化的分析结构
- 不要提及任何规律、理论或框架的名称
- 不要使用"### 维度分析"、"基本要素识别"等学术结构"""
            self._last_prompt = prompt
            return prompt

        # ── L2/L3 完整推理框架模式 ─────────────────────────
        reasoning_blocks = getattr(self, '_last_reasoning', [])
        if not reasoning_blocks:
            reasoning_blocks = self._execute_reasoning(
                problem, foci, memories,
                getattr(self, '_last_anti_memories', []),
            )

        framework_parts = []
        for rb in reasoning_blocks:
            part = f"""### 维度 {rb['index']}（权重 {rb['weight']:.2f}）

{ rb['template'] }"""

            if rb.get('hypothesis'):
                part += f"""

**可检验假设**：
{ rb['hypothesis'] }"""

            if rb.get('evidence'):
                ev = "\n".join(rb['evidence'])
                part += f"""

**支持证据**：
{ev}"""
            if rb.get('counter_evidence'):
                ce = "\n".join(rb['counter_evidence'])
                part += f"""

**反对证据**：
{ce}"""

            framework_parts.append(part)

        reasoning_framework = "\n\n".join(framework_parts)

        # ── 记忆参考 ─────────────────────────────────────────
        if memories:
            memory_text = "\n\n".join(
                f"**[参考 {i+1}]** (来源: {am.source}, 关联度: {am.activation_score:.3f})\n"
                f"{am.memory.content}"
                for i, am in enumerate(memories)
            )
        else:
            memory_text = "（暂无直接相关的参考信息）"

        # ── 反面视角 ─────────────────────────────────────────
        anti_text = ""
        anti_memories = getattr(self, '_last_anti_memories', [])
        if anti_memories:
            anti_parts = []
            for i, am in enumerate(anti_memories):
                anti_parts.append(
                    f"**[反面参考 {i+1}]** (关联度: {am.activation_score:.3f})\n"
                    f"{am.memory.content}"
                )
            anti_text = (
                "\n## 反面视角与潜在矛盾\n"
                "以下是一些可能与你当前思考方向相反或存在矛盾的信息，请审慎对待：\n\n"
                + "\n\n".join(anti_parts)
            )

        # ── v0.8.0 冲突检测警告 ─────────────────────────────
        conflict_text = ""
        if getattr(self.hub, 'last_conflicts', []):
            conflict_parts = []
            for i, (am_a, am_b, score) in enumerate(self.hub.last_conflicts):
                conflict_parts.append(
                    f"**矛盾 {i+1}** (冲突度: {score:.2f})\n"
                    f"- 记忆A [{am_a.source}, 关联度 {am_a.activation_score:.3f}]: "
                    f"{am_a.memory.content[:200]}\n"
                    f"- 记忆B [{am_b.source}, 关联度 {am_b.activation_score:.3f}]: "
                    f"{am_b.memory.content[:200]}"
                )
            conflict_text = (
                "\n## 潜在记忆矛盾\n"
                "以下记忆片段存在潜在逻辑矛盾，请结合上下文判断各自的适用条件：\n\n"
                + "\n\n".join(conflict_parts)
            )

        # ── v0.9.1 框架锚定觉察提示（脚注形式，低干扰） ────
        anchoring_text = ""
        if self.config.enable_frame_detection and self._last_frame_anchoring:
            anchoring_text = (
                "\n> " + self._last_frame_anchoring.get("reflection", "")
            )

        prompt = f"""你是一位**智者**，善于运用多种思维框架深入分析问题。

## 结构化推理框架
请按以下框架逐维度完成推理分析。对每个维度：
1. 按模板中的指引完成分析和填空
2. 检验提出的假设，结合支持/反对证据给出判断
3. 给出该维度的核心结论（2-3 句话）

{reasoning_framework}

## 相关记忆与经验
以下是过往积累的相关记忆片段：

{memory_text}
{anti_text}
{conflict_text}
## 当前问题
{problem}

---
**请按以下步骤作答**：
1. 逐维度完成上述推理框架中的分析（用自然语言，不要提及框架/规律名称）
2. 综合所有维度的分析结果，给出有深度的最终回答

重要：
- **不要在回答中提及任何规律、理论或框架的名称**，将思考方式自然融入分析
- 用日常交流的语言表达，像一位智者在自然交谈
- 当支持证据和反对证据都存在时，权衡两者而非选择性使用{anchoring_text}"""

        self._last_prompt = prompt
        return prompt

    def _call_llm(self, prompt: str, user_id: str = "") -> str:
        """通过 LiteLLM 统一接口调用大模型，带指数退避重试 + 短时缓存"""
        # 短时缓存：同用户 + 同 prompt 可配置 TTL 内不重复调用
        ttl = self.config.llm_cache_ttl
        cache_key = hashlib.sha256((user_id + "::" + prompt).encode()).hexdigest()
        cached = self._llm_cache.get(cache_key)
        if cached:
            ts, answer = cached
            if time.time() - ts < ttl:
                return answer

        answer = self._do_llm_call(prompt)

        # 缓存结果
        self._llm_cache[cache_key] = (time.time(), answer)
        max_cache = self.config.llm_cache_max_size
        if len(self._llm_cache) > max_cache:
            oldest = min(self._llm_cache, key=lambda k: self._llm_cache[k][0])
            del self._llm_cache[oldest]
        return answer

    @llm_retry
    def _do_llm_call(self, prompt: str) -> str:
        """实际 LLM 调用，由 @llm_retry 装饰器自动重试"""
        kwargs = {
            "model": self.config.llm_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "timeout": 60,
        }
        if self.config.llm_api_key:
            kwargs["api_key"] = self.config.llm_api_key
        if self.config.llm_base_url:
            kwargs["api_base"] = self.config.llm_base_url
        response = completion(**kwargs)
        return response.choices[0].message.content

    # ── v0.6.0 因果抽取 ─────────────────────────────────

    @llm_retry
    def _do_causal_extraction(self, extract_prompt: str) -> str:
        """因果关系抽取 LLM 调用，由 @llm_retry 装饰器自动重试"""
        kwargs = {
            "model": self.config.llm_model,
            "messages": [{"role": "user", "content": extract_prompt}],
            "temperature": 0.1,
            "timeout": 15,
        }
        if self.config.llm_api_key:
            kwargs["api_key"] = self.config.llm_api_key
        if self.config.llm_base_url:
            kwargs["api_base"] = self.config.llm_base_url
        response = completion(**kwargs)
        return response.choices[0].message.content

    def _extract_causal_relations(self, problem: str, answer: str) -> None:
        """从回答中自动抽取因果关系，存入语义记忆库。

        仅在 config.causal_extraction=True 且复杂度达标时调用。
        使用轻量 prompt（约 50 tokens）降低成本。
        """
        if not self.config.causal_extraction:
            return

        extract_prompt = (
            f"从以下回答中提取因果关系三元组（主语, 谓语, 宾语），"
            f"每行一个，格式：主语 | 谓语 | 宾语\n"
            f"只提取明确的、有依据的因果关系，不要推测。\n\n"
            f"问题：{problem[:200]}\n回答：{answer[:800]}\n\n"
            "因果关系："
        )

        try:
            raw = self._do_causal_extraction(extract_prompt)
        except Exception:
            return  # 因果抽取失败不影响主流程

        # 解析三元组："主语 | 谓语 | 宾语"
        for line in raw.strip().split("\n"):
            line = line.strip()
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 3:
                subject, predicate, object_ = parts[0], parts[1], parts[2]
                if subject and predicate and object_:
                    try:
                        self.remember_semantic(subject, predicate, object_, confidence=0.4)
                    except Exception:
                        logging.debug(
                            f"语义三元组保存失败: ({subject}, {predicate}, {object_})",
                            exc_info=True,
                        )

    def remember(
        self,
        content: str,
        context: Optional[Dict[str, Any]] = None,
        importance: float = 0.5,
        user_id: str = "",
        session_id: str = "",
        share_to_group: bool = False,
    ) -> str:
        """存储情节记忆。share_to_group=True 时写入公共记忆区。"""
        if share_to_group and self.group_id:
            return self.memory.share_to_group(
                content, context, importance,
                user_id=user_id, group_id=self.group_id, session_id=session_id,
            )
        return self.memory.remember(
            content, context, importance,
            user_id=user_id, session_id=session_id,
            agent_id=self.agent_id, shared_group_id="",
        )

    def share_to_group(
        self,
        content: str,
        context: Optional[Dict[str, Any]] = None,
        importance: float = 0.5,
        user_id: str = "",
        session_id: str = "",
    ) -> str:
        """显式将记忆共享到本agent所在组的公共记忆区"""
        return self.memory.share_to_group(
            content, context, importance,
            user_id=user_id, group_id=self.group_id, session_id=session_id,
        )

    def remember_semantic(
        self,
        subject: str,
        predicate: str,
        object_: str,
        confidence: float = 1.0,
        namespace: str = "",
    ) -> None:
        """存储语义三元组"""
        self.memory.remember_semantic(subject, predicate, object_, confidence,
                                      namespace=namespace)

    def query_memory(self, query: str, top_k: int = 5, user_id: str = "") -> List[Dict]:
        """直接查询记忆（绕过框架拆解）"""
        from soma.engine import _extract_keywords

        keywords = _extract_keywords(query, max_keywords=10)
        focus = Focus(
            law_id="direct_query",
            dimension=f"直接查询: {query}",
            keywords=keywords,
            weight=1.0,
            rationale="用户直接查询",
        )
        original_top_k = self.hub.top_k
        self.hub.top_k = top_k
        try:
            activated = self.hub.activate(
                [focus], user_id=user_id,
                agent_id=self.agent_id, group_id=self.group_id,
            )
        finally:
            self.hub.top_k = original_top_k
        return [self.hub.explain_activation(am) for am in activated]

    def decompose(self, problem: str) -> List[Focus]:
        """暴露思维拆解结果（供可视化和调试）"""
        return self.engine.decompose(problem)

    def close(self) -> None:
        """关闭所有子组件连接（memory + evolver + zhongdao）"""
        if self.zhongdao is not None:
            self.zhongdao.reset()
        self.memory.close()
        self.evolver.close()

    def __enter__(self) -> "SOMA_Agent":
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def reflect(self, task_id: str, outcome: str) -> None:
        """元认知反思"""
        self.evolver.reflect(task_id, outcome)
