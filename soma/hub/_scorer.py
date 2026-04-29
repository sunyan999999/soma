from soma.base import ActivatedMemory, Focus


class RelevanceScorer:
    """相关性打分器 — 计算单次 (focus, memory) 对的激活分数"""

    def compute_score(self, focus: Focus, am: ActivatedMemory) -> float:
        """激活分数 = 规律权重 × 记忆关联潜力"""
        return focus.weight * am.memory.relevance_potential()
