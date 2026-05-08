"""v0.8.0 反思质量自评 — 对每次回答进行三维质量评估。

全部本地计算，不调用 LLM：
- 一致性：回答与激活记忆的语义一致性（嵌入相似度）
- 连贯性：回答的结构完整性（段落、过渡词、逻辑标记）
- 可操作性：回答是否包含具体建议和行动指引
"""

import re
from typing import Dict, List, Optional, Tuple

import numpy as np


class QualityEvaluator:
    """三维质量评估器。

    在 respond() 返回后运行，评估回答质量并存入上下文。
    """

    # 连贯性信号词
    COHERENCE_MARKERS = [
        "首先", "其次", "然后", "最后", "综上", "总之",
        "第一", "第二", "第三", "第1", "第2", "第3",
        "1.", "2.", "3.", "①", "②", "③",
        "一方面", "另一方面", "不仅如此", "此外", "另外",
        "因为", "所以", "因此", "如果", "那么",
        "然而", "但是", "不过", "尽管", "虽然",
    ]

    # 可操作性信号词
    ACTION_MARKERS = [
        "建议", "推荐", "应该", "需要", "可以", "必须",
        "步骤", "方案", "方法", "策略", "措施", "行动",
        "具体", "明确", "量化", "指标", "数据", "衡量",
        "执行", "实施", "操作", "部署", "落地",
        "第一步", "第二步", "第三步", "首先做", "然后做",
    ]

    def __init__(self, embedder=None):
        self._embedder = embedder

    def _encode(self, text: str) -> np.ndarray:
        if self._embedder is None:
            return np.array([])
        try:
            return np.array(self._embedder.encode(text))
        except Exception:
            return np.array([])

    def _cosine_sim(self, a: np.ndarray, b: np.ndarray) -> float:
        if len(a) == 0 or len(b) == 0:
            return 0.0
        a_norm = a / (np.linalg.norm(a) + 1e-10)
        b_norm = b / (np.linalg.norm(b) + 1e-10)
        return float(np.dot(a_norm, b_norm))

    # ── 一致性评估 ──────────────────────────────────────

    def consistency_score(
        self, answer: str, memory_contents: List[str], conflict_count: int = 0,
    ) -> float:
        """评估回答与激活记忆的语义一致性。

        - 使用嵌入向量余弦相似度（如果有 embedder）
        - 无 embedder 时回退到关键词重叠
        - 存在冲突时适当降分
        """
        if not memory_contents:
            return 0.5  # 无记忆参考时中性分

        if self._embedder is not None:
            answer_vec = self._encode(answer)
            mem_vecs = [self._encode(m) for m in memory_contents]
            mem_vecs = [v for v in mem_vecs if len(v) > 0]
            if not mem_vecs:
                return 0.5
            sims = [self._cosine_sim(answer_vec, mv) for mv in mem_vecs]
            base = float(np.mean(sims))
        else:
            # 字符 bigram 重叠回退（对中文/英文都适用）
            answer_lower = answer.lower()
            overlaps = []
            for mem in memory_contents:
                mem_lower = mem.lower()
                if len(mem_lower) < 2:
                    continue
                mem_bigrams = {mem_lower[i:i+2] for i in range(len(mem_lower) - 1)}
                if not mem_bigrams:
                    continue
                hits = sum(1 for bg in mem_bigrams if bg in answer_lower)
                overlaps.append(hits / len(mem_bigrams))
            base = float(np.mean(overlaps)) if overlaps else 0.3

        # 冲突惩罚：每个冲突对降低 0.05
        penalty = min(conflict_count * 0.05, 0.3)
        return max(0.0, base - penalty)

    # ── 连贯性评估 ──────────────────────────────────────

    def coherence_score(self, answer: str) -> float:
        """评估回答的结构完整性。

        检查：段落结构、过渡词、逻辑标记、句子长度方差。
        """
        score = 0.0

        # 1. 段落结构 (0-0.25): 有多段且段长合理
        paragraphs = [p.strip() for p in answer.split("\n\n") if p.strip()]
        if len(paragraphs) >= 3:
            score += 0.25
        elif len(paragraphs) >= 2:
            score += 0.15
        elif len(paragraphs) == 1 and len(answer) > 100:
            score += 0.05

        # 2. 过渡词/逻辑标记 (0-0.35): 使用的标记词数量
        marker_count = sum(1 for m in self.COHERENCE_MARKERS if m in answer)
        if marker_count >= 5:
            score += 0.35
        elif marker_count >= 3:
            score += 0.25
        elif marker_count >= 1:
            score += 0.15

        # 3. 句子长度方差 (0-0.20): 长短句交替表明表达多样性
        sentences = [s.strip() for s in re.split(r"[。！？\.\!\?]", answer) if s.strip()]
        if len(sentences) >= 3:
            lengths = [len(s) for s in sentences]
            mean_len = np.mean(lengths)
            if mean_len > 0:
                cv = float(np.std(lengths) / mean_len)
                if cv > 0.5:
                    score += 0.20
                elif cv > 0.3:
                    score += 0.12
                else:
                    score += 0.05

        # 4. 总分上限 (0-0.20): 回答长度合理
        if 200 <= len(answer) <= 2000:
            score += 0.20
        elif len(answer) > 2000:
            score += 0.10
        elif len(answer) >= 50:
            score += 0.05

        return min(score, 1.0)

    # ── 可操作性评估 ─────────────────────────────────────

    def actionability_score(self, answer: str) -> float:
        """评估回答是否包含具体、可执行的建议。

        检查：行动词密度、具体性标记、结构化的行动步骤。
        """
        score = 0.0

        # 1. 行动词密度 (0-0.40)
        action_count = sum(1 for m in self.ACTION_MARKERS if m in answer)
        if action_count >= 5:
            score += 0.40
        elif action_count >= 3:
            score += 0.30
        elif action_count >= 1:
            score += 0.15

        # 2. 具体性标记 (0-0.30): 数字、百分比、时间范围
        has_numbers = bool(re.search(r"\d+", answer))
        has_percent = bool(re.search(r"\d+%|百分之", answer))
        has_time = bool(re.search(r"小时|天|周|月|年|分钟|立即|短期|长期", answer))
        if has_numbers:
            score += 0.10
        if has_percent:
            score += 0.10
        if has_time:
            score += 0.10

        # 3. 行动步骤结构 (0-0.30): 有序列表或步骤标记
        step_count = len(re.findall(
            r"第[一二三四五六七八九十\d]+[步阶段]|步骤\s*\d|Step\s*\d",
            answer,
        ))
        if step_count >= 3:
            score += 0.30
        elif step_count >= 1:
            score += 0.20
        # 检查是否有编号列表项（至少2项）
        elif len(re.findall(r"\d+\.\s+\S", answer)) >= 2:
            score += 0.15

        return min(score, 1.0)

    # ── 综合评估 ─────────────────────────────────────────

    def evaluate(
        self,
        answer: str,
        memory_contents: Optional[List[str]] = None,
        conflict_count: int = 0,
    ) -> Dict:
        """执行完整的三维质量评估。

        返回评估字典，包含分项分数、综合分数和质量等级。
        """
        memory_contents = memory_contents or []
        consistency = self.consistency_score(answer, memory_contents, conflict_count)
        coherence = self.coherence_score(answer)
        actionability = self.actionability_score(answer)

        # 综合分数：加权平均（一致性最重要）
        overall = consistency * 0.40 + coherence * 0.30 + actionability * 0.30

        # 质量等级
        if overall >= 0.70:
            grade = "excellent"
        elif overall >= 0.50:
            grade = "good"
        elif overall >= 0.30:
            grade = "fair"
        else:
            grade = "poor"

        return {
            "overall": round(overall, 3),
            "consistency": round(consistency, 3),
            "coherence": round(coherence, 3),
            "actionability": round(actionability, 3),
            "grade": grade,
            "needs_reflection": grade in ("poor", "fair"),
        }
