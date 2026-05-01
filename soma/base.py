import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# 近因衰减半衰期（天）：7天后权重衰减至 50%，14天后 25%，30天后 <5%
_RECENCY_HALF_LIFE_DAYS = 7.0


@dataclass
class MemoryUnit:
    """记忆单元 — 所有记忆类型的基类"""

    content: str
    timestamp: float = field(default_factory=lambda: datetime.now(timezone.utc).timestamp())
    importance: float = 0.5
    access_count: int = 0
    context: Dict[str, Any] = field(default_factory=dict)
    memory_type: str = "episodic"
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    user_id: str = ""
    session_id: str = ""

    def relevance_potential(self) -> float:
        """关联潜力 = 指数近因衰减 × 重要性 × 使用频次因子

        衰减曲线: exp(-days/7)，半衰期 7 天。
        - 当天 (0d): 1.00
        - 3天后: 0.65
        - 7天后: 0.37
        - 14天后: 0.14
        - 30天后: 0.014 (<2% — 基本被抑制)
        """
        now = datetime.now(timezone.utc).timestamp()
        days = max(now - self.timestamp, 0) / 86400.0
        recency = math.exp(-days / _RECENCY_HALF_LIFE_DAYS)
        return recency * self.importance * (1.0 + 0.1 * self.access_count)


@dataclass
class Focus:
    """分析焦点 — WisdomEngine 的输出，ActivationHub 的输入"""

    law_id: str
    dimension: str  # 人类可读的分析维度描述
    keywords: List[str]  # 用于记忆库查询的关键词
    weight: float  # 触发该焦点的规律权重
    rationale: str  # 为什么该规律被触发


@dataclass
class ActivatedMemory:
    """被激活的记忆 — ActivationHub 的输出"""

    memory: MemoryUnit
    activation_score: float  # 由 ActivationHub 计算
    source: str  # "episodic" | "semantic" | "skill"
    match_rationale: str = ""  # 为什么该记忆被激活
