import time
from typing import Any, Dict, List


class MetaEvolver:
    """元认知进化器 — MVP 存根，Alpha 阶段实现完整进化闭环"""

    def __init__(self, engine):
        self.engine = engine
        self._reflection_log: List[Dict[str, Any]] = []

    def reflect(self, task_id: str, outcome: str) -> None:
        """记录反思日志。MVP 不更新权重。"""
        self._reflection_log.append({
            "task_id": task_id,
            "outcome": outcome,
            "timestamp": time.time(),
        })

    def get_log(self) -> List[Dict[str, Any]]:
        """返回反思日志"""
        return self._reflection_log

    def clear_log(self) -> None:
        """清空日志"""
        self._reflection_log.clear()
