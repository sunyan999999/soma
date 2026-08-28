from typing import List, Optional

from soma.base import ActivatedMemory, Focus


class MemoryRetriever:
    """多路召回器 — 封装 MemoryCore 跨三库查询"""

    def __init__(self, memory_core):
        self.memory = memory_core

    def retrieve(self, focus: Focus, top_k: int, user_id: str = "",
                 agent_id: str = "", group_id: str = "",
                 max_age_days: Optional[float] = None) -> List[ActivatedMemory]:
        """对单个 Focus 执行跨三库（情节/语义/技能）查询

        v2.0.12: max_age_days 时间窗口硬截断透传。
        """
        return self.memory.query(focus, top_k=top_k, user_id=user_id,
                                 agent_id=agent_id, group_id=group_id,
                                 max_age_days=max_age_days)
