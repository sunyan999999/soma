from typing import Dict, List

from soma.base import ActivatedMemory, Focus, MemoryUnit
from soma.memory.core import MemoryCore


class ActivationHub:
    """双向激活调度器 — 计算关联潜力并返回 Top-K 相关记忆"""

    def __init__(
        self,
        memory_core: MemoryCore,
        top_k: int = 5,
        threshold: float = 0.3,
    ):
        self.memory = memory_core
        self.top_k = top_k
        self.threshold = threshold

    def activate(self, foci: List[Focus]) -> List[ActivatedMemory]:
        """
        双向激活：对每个 Focus 查询 MemoryCore，全局合并排序。

        1. 每个 Focus 过取 top_k * 2 条结果
        2. 计算 activation_score = focus.weight × memory.relevance_potential()
        3. 多 Focus 命中的记忆获得 0.5× 叠加加成
        4. 按分数降序排列，阈值过滤，返回 Top-K
        """
        # id → [ActivatedMemory, focus_count]
        candidates: Dict[str, list] = {}

        for focus in foci:
            results = self.memory.query(focus, top_k=self.top_k * 2)

            for am in results:
                mid = am.memory.id
                if mid not in candidates:
                    am.activation_score = focus.weight * am.memory.relevance_potential()
                    candidates[mid] = [am, 1]
                else:
                    prev_am, count = candidates[mid]
                    # 叠加加成
                    prev_am.activation_score += (
                        focus.weight * am.memory.relevance_potential() * 0.5
                    )
                    candidates[mid] = [prev_am, count + 1]

        # 收集、排序、过滤
        all_activated = [entry[0] for entry in candidates.values()]
        all_activated.sort(key=lambda am: am.activation_score, reverse=True)

        filtered = [am for am in all_activated if am.activation_score >= self.threshold]
        return filtered[: self.top_k]

    def explain_activation(
        self, activated: ActivatedMemory
    ) -> Dict:
        """返回激活记忆的详细解释信息"""
        mem = activated.memory
        return {
            "memory_id": mem.id,
            "content_preview": mem.content[:200],
            "activation_score": activated.activation_score,
            "source": activated.source,
            "match_rationale": activated.match_rationale,
            "relevance_potential": mem.relevance_potential(),
            "importance": mem.importance,
            "access_count": mem.access_count,
        }
