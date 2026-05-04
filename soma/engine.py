import random
import re
from typing import List

import jieba

from soma.abc import BaseFrameworkEngine
from soma.base import Focus
from soma.config import FrameworkConfig, WisdomLaw

# 中英文停用词
_STOP_WORDS = {
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一",
    "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着",
    "没有", "看", "好", "自己", "这", "他", "她", "它", "们", "那", "个",
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "shall", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "through", "during",
    "before", "after", "above", "below", "between", "under", "again",
    "further", "then", "once", "here", "there", "when", "where", "why",
    "how", "all", "both", "each", "few", "more", "most", "other", "some",
    "such", "no", "nor", "not", "only", "own", "same", "so", "than",
    "too", "very", "just", "because", "but", "and", "or", "if", "while",
    "although", "though", "even", "also", "it", "its", "that", "this",
    "these", "those", "what", "which", "who", "whom",
}

# 标点/空白模式 — 用于过滤纯标点 token
_PUNCT_PATTERN = re.compile(r"^[\s,\.!?;:：；，。！？、\-+()（）\[\]【】/\\\"'""''‘’]+$")


def _extract_keywords(text: str, max_keywords: int = 10) -> List[str]:
    """从文本中提取关键词 — jieba 分词 + 停用词过滤"""
    tokens = jieba.cut(text)
    keywords = []
    for token in tokens:
        token = token.strip().lower()
        if (
            token
            and token not in _STOP_WORDS
            and len(token) >= 2
            and not _PUNCT_PATTERN.match(token)
        ):
            keywords.append(token)
    # 去重保持顺序
    seen = set()
    unique = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            unique.append(kw)
    return unique[:max_keywords]


class WisdomEngine(BaseFrameworkEngine):
    """思维框架引擎 — 基于规律图谱拆解问题为分析焦点"""

    # 规律组合模板：(law_id_a, law_id_b) → (组合名, 组合描述)
    _COMBINATIONS: dict = {
        ("first_principles", "systems_thinking"): (
            "根因系统分析",
            "将第一性原理的底层回归与系统思维的全局关联结合，从最基本要素出发，"
            "追踪其在系统网络中的传导路径，定位深层杠杆点。",
        ),
        ("systems_thinking", "contradiction_analysis"): (
            "动态张力分析",
            "将系统思维的结构化视角与矛盾分析的对立统一结合，识别系统中"
            "相互制衡的力量，找到主要矛盾和系统演化的动力来源。",
        ),
        ("contradiction_analysis", "inversion"): (
            "辩证反思",
            "将矛盾分析的对立统一与逆向思考的反方向审视结合，从正反两面"
            "检验假设，避免单方面思维导致的盲区。",
        ),
        ("first_principles", "pareto_principle"): (
            "要素优先级排序",
            "将第一性原理的底层回归与二八法则的少数关键结合，从最基本的"
            "构成要素中识别出起决定性作用的20%，集中精力突破。",
        ),
        ("systems_thinking", "evolutionary_lens"): (
            "系统演进洞察",
            "将系统思维的结构分析与演进视角的时间维度结合，理解系统在不同"
            "阶段的动态变化规律，预判下一阶段的演化方向。",
        ),
        ("analogical_reasoning", "first_principles"): (
            "跨域本质映射",
            "将类比推理的跨领域迁移与第一性原理的底层回归结合，从其他领域"
            "的成功模式中提取基本原理，映射到当前问题。",
        ),
    }

    def __init__(self, framework: FrameworkConfig, embedder=None):
        self.laws: List[WisdomLaw] = framework.laws
        self.embedder = embedder
        # 按权重降序排列
        self.laws.sort(key=lambda law: law.weight, reverse=True)

    def decompose(self, problem: str) -> List[Focus]:
        """
        将问题按思维规律拆解为分析焦点。

        策略：关键词匹配 + 规律链传播。
        对每条规律检查其 triggers 是否出现在问题中，
        匹配则生成一个 Focus。
        无匹配时返回最高权重规律作为默认透镜。
        已触发的规律会通过 relations 激活关联规律（二级传播）。
        """
        foci: List[Focus] = []
        problem_lower = problem.lower()

        # ── 阶段1: 关键词直接匹配 ────────────────────────
        for law in self.laws:
            matched_triggers = [
                t for t in law.triggers if t.lower() in problem_lower
            ]
            if matched_triggers:
                dimension = f"从「{law.name}」出发：{law.description}。应用于问题：「{problem}」"
                keywords = list(set(law.triggers + _extract_keywords(problem)))
                focus = Focus(
                    law_id=law.id,
                    dimension=dimension,
                    keywords=keywords,
                    weight=law.weight,
                    rationale=f"问题中出现触发词：{', '.join(matched_triggers)}",
                )
                foci.append(focus)

        # ── 阶段2: 规律链传播 — relations 激活关联规律 ─────
        if foci:
            directly_triggered = {f.law_id for f in foci}
            propagated_ids: set = set()
            for focus in list(foci):
                law = next((l for l in self.laws if l.id == focus.law_id), None)
                if not law or not law.relations:
                    continue
                for related_id in law.relations:
                    if related_id in directly_triggered or related_id in propagated_ids:
                        continue
                    propagated_ids.add(related_id)
                    rlaw = next((l for l in self.laws if l.id == related_id), None)
                    if not rlaw:
                        continue
                    # 加成系数：部分命中时提高
                    partial = sum(1 for t in rlaw.triggers if t.lower() in problem_lower)
                    bonus = 0.50 if partial > 0 else 0.35
                    foci.append(Focus(
                        law_id=rlaw.id,
                        dimension=(
                            f"从「{rlaw.name}」出发（由「{law.name}」关联激活）："
                            f"{rlaw.description}。应用于问题：「{problem}」"
                        ),
                        keywords=list(set(rlaw.triggers + _extract_keywords(problem))),
                        weight=round(rlaw.weight * bonus, 4),
                        rationale=f"规律链推理：{law.name} → {rlaw.name}"
                        + (f"（{partial}个触发词部分命中）" if partial > 0 else ""),
                    ))

            # ── 阶段2.5: 规律组合模板 — 双规律同时触发则合成视角 ──
            for (a_id, b_id), (combo_name, combo_desc) in self._COMBINATIONS.items():
                if a_id in directly_triggered and b_id in directly_triggered:
                    law_a = next(l for l in self.laws if l.id == a_id)
                    law_b = next(l for l in self.laws if l.id == b_id)
                    combo_weight = round((law_a.weight + law_b.weight) / 2 * 1.1, 4)
                    combo_dimension = (
                        f"从「{combo_name}」出发（{law_a.name} × {law_b.name}）："
                        f"{combo_desc}。应用于问题：「{problem}」"
                    )
                    combo_keywords = list(set(
                        law_a.triggers + law_b.triggers + _extract_keywords(problem)
                    ))
                    foci.append(Focus(
                        law_id=f"combo_{a_id}_{b_id}",
                        dimension=combo_dimension,
                        keywords=combo_keywords,
                        weight=combo_weight,
                        rationale=f"规律组合：{law_a.name} + {law_b.name} → {combo_name}",
                    ))

        # ── 阶段3: 兜底 — 无匹配时加权随机选取 ─────────────
        if not foci:
            # 3a: 向量语义匹配兜底（如果 embedder 可用）
            semantic_matches = self._semantic_match(problem) if self.embedder else []
            if semantic_matches:
                foci.extend(semantic_matches)

            # 3b: 语义也匹配不到则加权随机选取
            if not foci:
                weights = [law.weight for law in self.laws]
                top_law = random.choices(self.laws, weights=weights, k=1)[0]
                dimension = f"从「{top_law.name}」视角审视：{top_law.description}。应用于问题：「{problem}」"
                keywords = _extract_keywords(problem) + top_law.triggers
                foci.append(
                    Focus(
                        law_id=top_law.id,
                        dimension=dimension,
                        keywords=keywords,
                        weight=top_law.weight,
                        rationale="无特定规律匹配，加权随机选取思维规律",
                    )
                )

        # 动态语境排序：weight × (1 + context_relevance) + 微小抖动
        def _context_score(focus: Focus) -> float:
            if not focus.keywords:
                return 0.0
            hits = sum(1 for kw in focus.keywords if kw.lower() in problem_lower)
            return (hits / len(focus.keywords)) * 0.3  # max 0.3 bonus

        foci.sort(
            key=lambda f: f.weight * (1.0 + _context_score(f))
            + random.uniform(-0.003, 0.003),
            reverse=True,
        )
        return foci

    def _semantic_match(self, problem: str) -> List[Focus]:
        """向量语义匹配兜底：当关键词无匹配时，用嵌入相似度寻找相关规律。

        将问题文本与每条规律的描述+触发词拼接做语义编码，
        余弦相似度 > 阈值则视为语义匹配成功。
        """
        import numpy as np

        if not self.embedder:
            return []

        problem_vec = np.array(self.embedder.encode(problem))
        problem_norm = np.linalg.norm(problem_vec)
        if problem_norm == 0:
            return []

        matches = []
        for law in self.laws:
            # 构造规律的语义签名：名称 + 描述 + 触发词
            sig_text = f"{law.name}：{law.description} {' '.join(law.triggers)}"
            sig_vec = np.array(self.embedder.encode(sig_text))
            sig_norm = np.linalg.norm(sig_vec)
            if sig_norm == 0:
                continue

            sim = float(np.dot(problem_vec, sig_vec) / (problem_norm * sig_norm))
            if sim > 0.35:  # 语义相似度阈值
                matches.append((law, sim))

        # 按相似度 × 权重排序，取前3个
        matches.sort(key=lambda x: x[1] * x[0].weight, reverse=True)

        foci = []
        for law, sim in matches[:3]:
            dimension = (
                f"从「{law.name}」视角审视（语义匹配）："
                f"{law.description}。应用于问题：「{problem}」"
            )
            keywords = _extract_keywords(problem) + law.triggers
            foci.append(Focus(
                law_id=law.id,
                dimension=dimension,
                keywords=keywords,
                weight=round(law.weight * sim, 4),
                rationale=f"向量语义匹配（相似度: {sim:.3f}）",
            ))
        return foci
