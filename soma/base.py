import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# 近因衰减半衰期（天）：7天后权重衰减至 50%，14天后 25%，30天后 <5%
# 与记忆查询的默认30天时间窗口配合 —— 半衰期针对"短期相关性"，时间窗口负责硬截断
RECENCY_HALF_LIFE_DAYS = 7.0
# 状态类记忆（nature=state）时效窗口（天）：超过视为可能已过时，注入层应提示
STATE_TTL_DAYS = 30.0


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
    agent_id: str = ""
    shared_group_id: str = ""
    # v2.0.5: 多模态记忆支持（纯增量，不影响现有功能）
    content_type: str = "text"         # text/table/chart
    structured_data: Optional[dict] = None  # JSON 结构化数据
    # v2.0.14: 业务性质 — 区分时效强弱（state/fact/event）
    nature: str = "event"   # state 状态类(失眠/情绪/健康,时效强) / fact 事实技能类(长期有效) / event 一般事件(默认)

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
        recency = math.exp(-days / RECENCY_HALF_LIFE_DAYS)
        return recency * self.importance * (1.0 + 0.1 * self.access_count)

    def is_state_stale(self, ttl_days: float = STATE_TTL_DAYS) -> bool:
        """状态类记忆（nature=state）是否已超时效窗口。

        失眠/情绪/健康等状态是暂时的——超过 ttl_days 未更新即视为可能已过时，
        注入 LLM 时应提示勿当作当前状态。非状态类（fact/event）恒返回 False。
        """
        if self.nature != "state":
            return False
        now = datetime.now(timezone.utc).timestamp()
        age_days = max(now - self.timestamp, 0) / 86400.0
        return age_days > ttl_days

    def age_days(self) -> float:
        """记忆年龄（天），供注入层时间标注"""
        now = datetime.now(timezone.utc).timestamp()
        return round(max(now - self.timestamp, 0) / 86400.0, 1)


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
    suggested_focus: Optional[Focus] = None  # v0.8.0: 记忆反向建议的思维焦点
