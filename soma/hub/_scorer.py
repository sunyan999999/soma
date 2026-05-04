from soma.base import ActivatedMemory, Focus


class RelevanceScorer:
    """相关性打分器 — 计算单次 (focus, memory) 对的激活分数"""

    def compute_score(self, focus: Focus, am: ActivatedMemory) -> float:
        """激活分数 = 规律权重 × 记忆关联潜力 × 可用性修正"""
        score = focus.weight * am.memory.relevance_potential()
        # 可用性启发式修正：高频访问但低重要度的记忆可能只是"容易想起"而非真正有价值
        if am.memory.access_count > 20 and am.memory.importance < 0.5:
            score *= 0.7
        return score
