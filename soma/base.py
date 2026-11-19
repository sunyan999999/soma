import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# 近因衰减半衰期（天）：7天后权重衰减至 50%，14天后 25%，30天后 <5%
# 与记忆查询的默认30天时间窗口配合 —— 半衰期针对"短期相关性"，时间窗口负责硬截断
RECENCY_HALF_LIFE_DAYS = 7.0

#: importance 超过这个值，记忆开始获得"遗忘保护"（半衰期变长）。
#: 取 0.6 是为了**只保护真正重要的**：普通记忆（≤0.5）行为完全不变，
#: 不改变既有检索质量，只是让重要的记忆活得更久。
IMPORTANCE_PROTECT_FLOOR = 0.6
#: 保护上限倍率：importance=1.0 时半衰期是基准的几倍（7 → 28 天）。
IMPORTANCE_PROTECT_MAX = 4.0
#: 按业务性质调整半衰期（v2.0.14 引入的 nature 字段）。
#:   fact  —— 事实/技能，**长期有效**（"用户叫孙岩"不该过期）
#:   state —— 状态，**时效强**（"最近失眠"过一周就该弱化）
#:   event —— 一般事件，基准
NATURE_HALF_LIFE_FACTOR = {"fact": 3.0, "state": 0.5, "event": 1.0}
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

    def effective_half_life(self) -> float:
        """这条记忆的**半衰期**（天）—— 重要的事忘得慢。

        ## 为什么不能一刀切 7 天

        实测：`exp(-30/7) = 1.4%`。也就是说**任何**记忆，30 天后权重都不足
        今天的 1.4% —— 哪怕它是"用户叫孙岩"这种一辈子有效的事实。
        用户感受到的就是**「越用越不懂」**：聊了三个月，它不记得你是谁。

        ## 三个因子

        1. **importance**：≥ `IMPORTANCE_PROTECT_FLOOR` 开始获得保护，
           到 1.0 时半衰期 ×`IMPORTANCE_PROTECT_MAX`（7 → 28 天）。
        2. **nature**：`fact`（事实/技能，长期有效）×`NATURE_HALF_LIFE_FACTOR`
           （默认 3）；`state`（失眠/情绪，时效强）×0.5，**更快失效**。
        3. **access_count**：被反复回忆的事忘得慢（艾宾浩斯的"重复"效应），
           每次 +10%，封顶 +100%。

        ## 三个典型值

        | 记忆 | 参数 | 半衰期 |
        |---|---|---|
        | 「今天天气不错」 | imp .30, event, 0 次 | **7 天**（不变） |
        | 「这个项目用 Python」 | imp .80, fact, 3 次 | **54 天** |
        | 「用户叫孙岩」 | imp .95, fact, 8 次 | **114 天** |
        | 「用户最近失眠」 | imp .70, state, 1 次 | **4.6 天**（更快过期） |
        """
        base = RECENCY_HALF_LIFE_DAYS

        # ① importance 保护：只保护**真正重要**的，普通记忆行为不变
        imp = max(0.0, min(1.0, float(self.importance or 0.0)))
        if imp > IMPORTANCE_PROTECT_FLOOR:
            t = (imp - IMPORTANCE_PROTECT_FLOOR) / (1.0 - IMPORTANCE_PROTECT_FLOOR)
            base *= 1.0 + (IMPORTANCE_PROTECT_MAX - 1.0) * t

        # ② nature：事实长期有效，状态快速过期
        base *= NATURE_HALF_LIFE_FACTOR.get(self.nature or "event", 1.0)

        # ③ 被回忆过
        base *= 1.0 + min(int(self.access_count or 0), 10) * 0.1

        return base

    def relevance_potential(self) -> float:
        """关联潜力 = 指数近因衰减 × 重要性 × 使用频次因子

        **衰减用的半衰期不是常量** —— 见 `effective_half_life()`：
        重要的、事实类的、被反复回忆的记忆，半衰期更长。

        （2026-10-20 之前这里是写死的 `exp(-days/7)`，不区分记忆重要性 ——
          30 天后所有记忆都不足 1.4%，"越用越懂"从机制上就不成立。）
        """
        # ★ 2026-11-19（下游验证）：语义知识不参与近因衰减。
        #
        # 三元组是「事实」，不是「事件」—— 它没有过期语义。更实际的是：
        # 语义 MemoryUnit 的 timestamp 是**查询时刻**构造的（每次查都取 now），
        # 于是 days 是微秒级的浮点数，recency 每次相差 1e-10 —— 同一题在不同
        # 时刻激活就会得到略有不同的分数，在 top_k 的并列边界上直接翻转结果。
        #
        # 实测：同一题间隔数十次查询重复激活，分数从 0.763874999685 漂到
        # 0.763874999810，激活集合随之二选一。这与「排序缺次键」是两个独立
        # 来源，两处都修才能真正稳定。
        if self.memory_type == "semantic":
            return self.importance * (1.0 + 0.1 * self.access_count)

        now = datetime.now(timezone.utc).timestamp()
        days = max(now - self.timestamp, 0) / 86400.0
        recency = math.exp(-days / self.effective_half_life())
        return recency * self.importance * (1.0 + 0.1 * self.access_count)

    def is_state_stale(self, ttl_days: float = STATE_TTL_DAYS) -> bool:
        """状态类记忆（nature=state）是否已超时效窗口。

        失眠/情绪/健康等状态是暂时的——超过 ttl_days 未更新即视为可能已过时，
        注入 LLM 时应提示不得直接当作当前状态回复。非状态类（fact/event）恒返回 False。
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

    def age_label(self) -> str:
        """人类可读的记忆年龄标注（v2.0.18），供注入 LLM 的 prompt 使用。

        数据源与 explain_activation() 的 age_days 同源 —— 本方法只是把同一口径
        转成中文表述，不另造名词。注入层带上它能避免 LLM 把远期旧状态当作当前
        状态（2026-08「失眠串台」事故的根因）。

        分档：今天 / 昨天 / N 天前 / 约 N 周前 / 约 N 个月前 / 约 N 年前
        """
        d = self.age_days()
        if d < 1:
            return "今天"
        if d < 2:
            return "昨天"
        if d < 7:
            return f"{int(d)} 天前"
        if d < 30:
            return f"约 {int(d // 7)} 周前"
        if d < 365:
            return f"约 {int(d // 30)} 个月前"
        return f"约 {d / 365:.1f} 年前"

    def staleness_note(self) -> str:
        """状态类记忆超时效窗口时的注入提示（v2.0.18），非状态类返回空串。

        与 is_state_stale() 同一判据（nature=state 且超过 STATE_TTL_DAYS），
        供注入层在记忆条目下方附加「不得直接当作当前状态回复」的提醒。

        v2.0.18.1 措辞由接入方在生产验证中定稿：上游原先的「勿当作当前状态，
        必要时先向用户确认」比他们线上跑的强约束软一档；他们选了折中版 ——
        既堵死 2026-08「失眠串台」那类直接误用，又保留追问余地。
        """
        if not self.is_state_stale():
            return ""
        return (
            f"⚠ 该状态记录于{self.age_label()}，可能已变化，"
            "不得直接当作当前状态回复；确需使用须先向用户确认"
        )


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
