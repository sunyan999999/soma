"""自主认知循环的补全（v2.0.18）—— 自主目标来源 + 后台常驻运行。

v2.0.0 起 SOMA 就有了完整的五阶段认知闭环（perceive→reason→act→feedback→evolve），
但一直差两件事：目标必须由外部传入，以及循环不会自己跑。本模块补的正是这两块：

- ``GoalGenerator``：从记忆与状态里自己找出「值得做的事情」——跨会话遗留的执行计划、
  过期的状态类记忆、尚未澄清的记忆冲突、被埋没的重要记忆。每个目标都带 ``source``
  与 ``evidence``，可追溯到具体记忆，不凭空造目标。
- ``BackgroundRunner``：在显式开启配置后，用一条 daemon 线程周期性取目标并推进。

硬性约束（后台循环）：

- **默认关闭**。配置 ``autonomous_background_enabled`` 为 False 时 ``start()``
  直接拒绝启动，不做静默兜底。
- **并发上限 1**。单个后台线程顺序执行，tick 内部再用一把非阻塞锁兜底，
  任何时刻最多一个 tick 在跑。
- **单次 tick 有墙钟上限**（``autonomous_background_max_runtime``），超出即放弃
  本轮剩余目标 —— 不为了跑完而无限占用。
- **连续失败自动停驻**（``autonomous_background_max_failures``），失败按指数退避
  重试，达上限后停驻而不是无限重试。
- **随时可停**。``stop()`` 置位事件后等待在跑的 tick 自然结束；不强行杀线程
  （Python 无法安全终止线程），若超时未结束会如实报告而不是假装已停。
"""
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

from soma.base import STATE_TTL_DAYS

_log = logging.getLogger("soma.autonomous")

# 已推进目标在多少小时内不重复推进
RECENT_GOAL_WINDOW_HOURS = 24.0
# 元信息键
META_LAST_SESSION_END = "autonomous_last_session_end"
META_RECENT_GOALS = "autonomous_recent_goals"

# 自主循环单轮失败的重试策略（v2.0.18）—— 瞬时故障（写锁竞争、LLM 抖动）
# 不该直接终止整个目标，但也不能无限重试，故设次数上限 + 指数退避。
AUTONOMOUS_MAX_CONSECUTIVE_ERRORS = 3
AUTONOMOUS_RETRY_BASE_SECONDS = 1.0
AUTONOMOUS_RETRY_MAX_SECONDS = 8.0

# 跨会话边界判定：两次活动间隔超过此时长即视为"新会话"（v2.0.18）
SESSION_GAP_SECONDS = 300.0


def human_gap(seconds: Optional[float]) -> str:
    """把秒差转成人类可读的间隔描述（跨会话整合用）。"""
    if seconds is None:
        return "首次运行（无上次会话记录）"
    if seconds < 60:
        return f"{int(seconds)} 秒"
    if seconds < 3600:
        return f"约 {int(seconds // 60)} 分钟"
    if seconds < 86400:
        return f"约 {seconds / 3600:.1f} 小时"
    return f"约 {seconds / 86400:.1f} 天"


@dataclass
class AutonomousGoal:
    """一个自主生成的目标。

    key 是稳定标识（同一条记忆/同一对冲突每次生成都相同），用于跨会话去重
    —— 避免每次启动都把同一件事重新推一遍。
    """

    key: str
    goal: str
    source: str          # stale_state | conflict | cross_session_plan | buried_memory
    priority: float
    evidence: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "goal": self.goal,
            "source": self.source,
            "priority": round(self.priority, 3),
            "evidence": list(self.evidence),
        }


class GoalGenerator:
    """从记忆与当前状态里生成自主目标。

    只读：本类不写任何记忆，也不改变 SOMA 状态（唯一例外是读 ``hub.last_conflicts``
    这个已存在的属性）。任一来源抛错都只影响该来源，其余来源照常产出。
    """

    def __init__(self, soma):
        self._soma = soma

    # ── 访问辅助 ────────────────────────────────────────

    def _cfg(self):
        return getattr(self._soma, "_config", None)

    def _episodic(self):
        agent = getattr(self._soma, "_agent", None)
        core = getattr(agent, "memory", None)
        return getattr(core, "episodic", None)

    # ── 主入口 ──────────────────────────────────────────

    def generate(
        self, max_goals: int = 3, recent_keys: Optional[Set[str]] = None,
        user_id: str = "",
    ) -> List[AutonomousGoal]:
        """按优先级返回最多 max_goals 个目标。

        recent_keys: 近期已推进过的目标 key，命中的目标不重复产出。

        user_id (v2.0.18.2): 只从该用户的记忆里生成目标。**多租户部署必须传**
        —— 留空是「系统级、不按用户过滤」的旧语义，会把不同用户的记忆混进
        同一个目标集（goal 文本里直接内嵌记忆原文），只适用于单租户部署。
        """
        recent_keys = recent_keys or set()
        collected: List[AutonomousGoal] = []
        sources: List[Callable[..., List[AutonomousGoal]]] = [
            self._from_stale_states,
            self._from_conflicts,
            self._from_pending_plans,
            self._from_buried_memories,
        ]
        for fn in sources:
            try:
                collected.extend(fn(user_id=user_id))
            except Exception:
                _log.debug("自主目标来源 %s 失败，跳过", fn.__name__, exc_info=True)

        # v2.0.18.2: key 带上用户前缀。三个来源的 key 天然全局唯一
        # （stale_state/conflict 用的是记忆 id），但 plan:{problem[:60]} 用的是
        # **计划文本前 60 字** —— 两个用户写下同样的计划文字就会撞成同一个 key，
        # 于是 A 推进过的目标会把 B 的同名目标错误地去重掉（跨用户串扰，方向是
        # 漏报而非泄漏，但同属「user 维度缺失」）。加前缀后去重天然按用户分开。
        # 留空不加前缀：单租户行为零变化，已存的旧记录也照常命中。
        if user_id:
            for g in collected:
                g.key = f"{user_id}|{g.key}"

        # 同 key 去重，保留优先级最高的那条
        best: Dict[str, AutonomousGoal] = {}
        for g in collected:
            if g.key in recent_keys:
                continue
            prev = best.get(g.key)
            if prev is None or g.priority > prev.priority:
                best[g.key] = g

        goals = sorted(best.values(), key=lambda g: g.priority, reverse=True)
        return goals[:max(0, int(max_goals))]

    # ── 来源 1：过期的状态类记忆 ────────────────────────

    def _from_stale_states(self, user_id: str = "") -> List[AutonomousGoal]:
        """nature=state 且超时效窗口的记忆 —— 最贴合「失眠串台」的场景：
        系统自己发现「这条状态很久没更新了」，而不是等调用方来问。

        v2.0.18.1: 候选池按 ``older_than_days=STATE_TTL_DAYS`` 直取过期子集。
        原先取的是「最近 50 条 state」再逐条判 is_state_stale() —— 两个条件方向
        相反，数据量大时几乎必然取空（接入方 26,977 条库上该来源形同死的）。
        这与 ``SOMA_Agent._stale_state_memories()`` 是同一处修正。

        v2.0.18.2: 本来源原先**不按用户过滤**，与刚修的 P0（过期状态块跨用户
        泄漏）同类 —— 多租户下某用户的 state 会被写进系统级 goal 文本并拿去
        run_autonomous() 执行。现按 user_id 过滤；留空则保持单租户语义。
        """
        store = self._episodic()
        cfg = self._cfg()
        if store is None:
            return []
        base = float(getattr(cfg, "autonomous_stale_state_priority", 0.5))
        out: List[AutonomousGoal] = []
        for mem in store.query_by_filters(
            nature="state", older_than_days=STATE_TTL_DAYS, limit=50,
            user_id=user_id,
        ):
            if not mem.is_state_stale():
                continue
            age = mem.age_days()
            label = mem.age_label()
            out.append(AutonomousGoal(
                key=f"stale_state:{mem.id}",
                goal=(
                    f"复核状态「{mem.content[:40]}」—— 该状态记录于{label}，"
                    f"可能已不反映当前情况，需要更新或确认"
                ),
                source="stale_state",
                priority=min(0.95, base + age / 365.0),
                evidence=[f"{label} · 重要性 {mem.importance:.2f} · {mem.content[:60]}"],
            ))
        return out

    # ── 来源 2：尚未澄清的记忆冲突 ──────────────────────

    def _from_conflicts(self, user_id: str = "") -> List[AutonomousGoal]:
        """读 hub.last_conflicts（最近一次激活时检测到的矛盾对）。

        这是进程内观测值：跨会话刚启动、还没有任何激活时为空 —— 此时不产目标，
        属于「没有观测到冲突」而非「没有冲突」，故不做任何猜测性补全。

        v2.0.18.2: user_id 给定时只保留**两侧都属于该用户**的冲突对。
        ``last_conflicts`` 来自「最近一次激活」，多租户下那次激活可能是别的
        用户 —— 而 goal 文本直接内嵌两侧记忆原文，不过滤同样是跨用户泄漏。
        """
        cfg = self._cfg()
        hub = getattr(getattr(self._soma, "_agent", None), "hub", None)
        conflicts = list(getattr(hub, "last_conflicts", None) or [])
        priority = float(getattr(cfg, "autonomous_conflict_priority", 0.7))
        out: List[AutonomousGoal] = []
        for item in conflicts[:5]:
            try:
                am_a, am_b, score = item
                a, b = am_a.memory, am_b.memory
            except Exception:
                continue
            if user_id and (
                str(getattr(a, "user_id", "") or "") != user_id
                or str(getattr(b, "user_id", "") or "") != user_id
            ):
                continue
            pair = "|".join(sorted([getattr(a, "id", ""), getattr(b, "id", "")]))
            out.append(AutonomousGoal(
                key=f"conflict:{pair}",
                goal=(
                    f"澄清两条相互矛盾的记忆："
                    f"「{a.content[:40]}」 ↔ 「{b.content[:40]}」"
                ),
                source="conflict",
                priority=priority,
                evidence=[
                    f"A [{a.age_label()}]: {a.content[:60]}",
                    f"B [{b.age_label()}]: {b.content[:60]}",
                    f"冲突度 {float(score):.2f}",
                ],
            ))
        return out

    # ── 来源 3：跨会话遗留的执行计划 ────────────────────

    def _from_pending_plans(self, user_id: str = "") -> List[AutonomousGoal]:
        """execute() 落到记忆里的执行计划 —— 那些「记了要做、但没做」的事。

        跳过 origin="autonomous" 的条目：那是自主循环自己执行时写下的计划，
        收回来会形成「目标→执行→新计划→新目标」的无限嵌套（冒烟实测到过）。
        只认人/外部调用方记下的计划。

        v2.0.18.2: 按 user_id 过滤（此前漏了 —— 这是四个来源里第三个没有用户
        维度的，goal 文本内嵌 problem[:80]）。
        """
        store = self._episodic()
        cfg = self._cfg()
        if store is None:
            return []
        priority = float(getattr(cfg, "autonomous_plan_priority", 0.6))
        out: List[AutonomousGoal] = []
        for mem in store.query_by_context_type(
            "execution_plan", days=30, limit=50, user_id=user_id,
        ):
            ctx = mem.context if isinstance(mem.context, dict) else {}
            if ctx.get("origin") == "autonomous":
                continue
            problem = str(ctx.get("problem") or mem.content[:60]).strip()
            if not problem:
                continue
            label = mem.age_label()
            out.append(AutonomousGoal(
                key=f"plan:{problem[:60]}",
                goal=f"推进此前记录但未完成的计划（{label}记下）：{problem[:80]}",
                source="cross_session_plan",
                priority=priority,
                evidence=[f"{label} · {mem.content[:80]}"],
            ))
        return out

    # ── 来源 4：被埋没的重要记忆 ────────────────────────

    def _from_buried_memories(self, user_id: str = "") -> List[AutonomousGoal]:
        """重要性高、却从未被检索过的旧记忆 —— 遗忘曲线下容易静默沉底的那批。

        v2.0.18.2: 本来源原先**不按用户过滤**，与 ``_from_stale_states`` 同属
        跨用户混合（goal 文本内嵌记忆原文）。现按 user_id 过滤；留空则保持
        单租户语义。
        """
        store = self._episodic()
        cfg = self._cfg()
        if store is None:
            return []
        min_imp = float(getattr(cfg, "autonomous_buried_importance", 0.7))
        min_age = float(getattr(cfg, "autonomous_buried_age_days", 14.0))
        out: List[AutonomousGoal] = []
        for mem in store.query_by_filters(
            min_importance=min_imp, max_access_count=0, limit=50,
            user_id=user_id,
        ):
            if mem.age_days() < min_age:
                continue
            ctx = mem.context if isinstance(mem.context, dict) else {}
            # 系统自身的操作日志（自主循环记录、执行计划）不是"用户知识"，
            # 回顾它们没有价值；执行计划另有 _from_pending_plans 专门处理。
            if ctx.get("type") in ("autonomous_loop", "execution_plan"):
                continue
            out.append(AutonomousGoal(
                key=f"buried:{mem.id}",
                goal=(
                    f"回顾一条重要但长期未被用到的记忆"
                    f"（{mem.age_label()}，重要性 {mem.importance:.2f}）：{mem.content[:60]}"
                ),
                source="buried_memory",
                priority=min(0.65, 0.4 + mem.importance * 0.2),
                evidence=[f"{mem.age_label()} · 0 次访问 · {mem.content[:60]}"],
            ))
        return out


class BackgroundRunner:
    """后台常驻自主循环（默认关闭，需显式开启）。

    单条 daemon 线程 + 一把非阻塞锁，保证任何时刻最多一个 tick 在跑。
    """

    def __init__(self, soma, config=None):
        self._soma = soma
        self._cfg = config if config is not None else getattr(soma, "_config", None)
        self._thread: Optional[threading.Thread] = None
        self._stop_evt = threading.Event()
        self._gate = threading.Lock()          # 非阻塞获取 = tick 互斥
        self._start_lock = threading.Lock()    # 只保护 start() 的线程创建
        self._ticks = 0
        self._failures = 0
        self._consecutive_failures = 0
        self._last_result: Optional[Dict[str, Any]] = None
        self._started_at: Optional[float] = None
        self._stopped_reason: str = ""
        self._user_cursor = 0                   # 按用户轮转的游标（v2.0.18.2）
        self._skip_reason: str = ""             # 本轮为何没产出目标（多租户未配置）

    # ── 配置读取（每次读，便于运行期改配置） ────────────

    def _opt(self, name: str, default):
        return getattr(self._cfg, name, default)

    @property
    def enabled(self) -> bool:
        return bool(self._opt("autonomous_background_enabled", False))

    # ── 生命周期 ────────────────────────────────────────

    def start(self) -> Dict[str, Any]:
        """启动后台线程。未显式开启配置时拒绝启动（不静默兜底）。"""
        if not self.enabled:
            return {
                "started": False,
                "reason": "disabled",
                "message": (
                    "后台自主循环未开启。需要显式设置 "
                    "autonomous_background_enabled=True 才允许启动 —— "
                    "该循环会持续读写真库，不默认打开。"
                ),
            }
        with self._start_lock:
            if self._thread is not None and self._thread.is_alive():
                return {
                    "started": False,
                    "reason": "already_running",
                    "message": "后台自主循环已在运行",
                }
            self._stop_evt.clear()
            self._stopped_reason = ""
            self._started_at = time.time()
            self._thread = threading.Thread(
                target=self._loop, name="soma-autonomous", daemon=True,
            )
            self._thread.start()
        return {
            "started": True,
            "interval": int(self._opt("autonomous_background_interval", 3600)),
            "max_goals_per_tick": int(self._opt("autonomous_background_max_goals", 1)),
            "max_runtime": int(self._opt("autonomous_background_max_runtime", 120)),
        }

    def stop(self, timeout: float = 10.0) -> Dict[str, Any]:
        """请求停止并等待当前 tick 结束。不强行杀线程 —— 超时会如实报告。"""
        self._stop_evt.set()
        th = self._thread
        if th is None:
            return {"stopped": True, "was_running": False, "message": ""}
        th.join(timeout)
        if th.is_alive():
            return {
                "stopped": False,
                "was_running": True,
                "message": (
                    f"已置停止信号，但当前 tick 在 {timeout:.0f}s 内未结束；"
                    f"线程仍存活（不会强行终止，等它自然收尾）"
                ),
            }
        self._thread = None
        return {"stopped": True, "was_running": True, "message": ""}

    def status(self) -> Dict[str, Any]:
        th = self._thread
        raw_users = str(self._opt("autonomous_background_user_ids", "") or "").strip()
        return {
            "enabled": self.enabled,
            "running": bool(th is not None and th.is_alive()),
            "tick_in_progress": self._gate.locked(),
            "ticks": self._ticks,
            "failures": self._failures,
            "consecutive_failures": self._consecutive_failures,
            "interval": int(self._opt("autonomous_background_interval", 3600)),
            "started_at": self._started_at,
            "stopped_reason": self._stopped_reason,
            "last_result": self._last_result,
            # v2.0.18.2：目标按用户切分。留空 = 单租户语义（不按用户过滤）——
            # 多租户部署下不同用户的记忆会混进同一个目标集，用这两个字段让
            # 接入方能自检，而不是靠读文档发现。
            "user_ids_config": raw_users or "(未配置 = 单租户语义)",
            "multi_tenant_ready": bool(raw_users),
            # 未配置用户列表、但库里确实有多个用户时，本循环会拒绝产出目标
            # （fail-safe），原因记在这里，避免接入方只看到「一直没动静」。
            "last_skip_reason": self._skip_reason,
        }

    # ── tick ────────────────────────────────────────────

    def _loop(self) -> None:
        interval = max(1, int(self._opt("autonomous_background_interval", 3600)))
        max_failures = max(1, int(self._opt("autonomous_background_max_failures", 5)))
        backoff_base = float(self._opt("autonomous_background_backoff_base", 30.0))

        # 先等一个完整间隔再跑首次 tick —— 启动瞬间不产生意外负载，
        # 也让"刚开启就关闭"能干净收尾（不必等一次 tick 跑完）。
        wait_for = float(interval)
        while not self._stop_evt.is_set():
            if self._stop_evt.wait(wait_for):
                break

            result = None
            try:
                result = self.run_once()
            except Exception:
                # run_once 内部已兜住绝大部分异常，这里只兜罕见的意外
                _log.warning("后台自主 tick 异常", exc_info=True)
                self._failures += 1
                self._consecutive_failures += 1

            if self._consecutive_failures >= max_failures:
                self._stopped_reason = (
                    f"连续 {self._consecutive_failures} 次失败，已自动停驻"
                )
                _log.error("后台自主循环停驻：%s", self._stopped_reason)
                break

            if result is not None and result.get("errors"):
                # 本轮有目标推进失败：指数退避，别立刻再撞同一个问题
                wait_for = min(
                    backoff_base * (2 ** max(0, self._consecutive_failures - 1)),
                    float(interval),
                )
            else:
                wait_for = float(interval)

    def run_once(self) -> Dict[str, Any]:
        """同步执行一个 tick（后台线程与测试共用同一入口）。

        v2.0.18.2: 目标**按用户切分** —— 为本轮 ``_target_users()`` 里的每个用户
        各生成一轮目标（总时长仍受 max_runtime 约束）。用户列表为空时该轮不产出
        任何目标，而不是退回「系统级混合所有用户」的旧行为。
        """
        if not self._gate.acquire(blocking=False):
            return {"skipped": True, "reason": "tick_in_progress"}

        t0 = time.monotonic()
        max_runtime = float(self._opt("autonomous_background_max_runtime", 120))
        max_goals = max(1, int(self._opt("autonomous_background_max_goals", 1)))
        advanced: List[Dict[str, Any]] = []
        errors: List[Dict[str, str]] = []
        timed_out = False
        users = self._target_users()

        try:
            for uid in users:
                if time.monotonic() - t0 > max_runtime:
                    timed_out = True
                    break
                goals = self._soma.generate_goals(max_goals=max_goals, user_id=uid)
                for g in goals:
                    if time.monotonic() - t0 > max_runtime:
                        timed_out = True
                        break
                    goal_text = g.get("goal", "") if isinstance(g, dict) else str(g)
                    key = g.get("key", "") if isinstance(g, dict) else ""
                    try:
                        res = self._soma.run_autonomous(goal_text, max_rounds=2)
                        advanced.append({
                            "key": key,
                            "goal": goal_text[:120],
                            "user_id": uid,
                            "completed": bool(res.get("completed")),
                            "stop_reason": res.get("stop_reason", ""),
                            "rounds": int(res.get("round_count", 0)),
                        })
                        self._remember_advanced(key)
                    except Exception as exc:
                        errors.append({"key": key,
                                       "error": f"{type(exc).__name__}: {exc}"})
        finally:
            self._gate.release()

        self._ticks += 1
        if errors:
            self._consecutive_failures += 1
        else:
            self._consecutive_failures = 0

        result = {
            "tick": self._ticks,
            "goals_considered": max_goals,
            "users": users,
            "skip_reason": self._skip_reason,
            "advanced": advanced,
            "errors": errors,
            "timed_out": timed_out,
            "elapsed_ms": round((time.monotonic() - t0) * 1000, 1),
        }
        self._last_result = result
        return result

    # ── 本轮覆盖哪些用户（v2.0.18.2）────────────────────

    def _all_user_ids(self) -> List[str]:
        try:
            return list(self._soma._agent.memory.episodic.distinct_user_ids())
        except Exception:
            _log.debug("枚举用户失败，本轮跳过（不退回系统级混合）", exc_info=True)
            return []

    def _target_users(self) -> List[str]:
        """本轮要为其生成目标的用户列表。

        ``autonomous_background_user_ids``：
          · 未配置（默认）→ 单租户语义：不按用户过滤，返回 ``[""]``。但若库里
            **确实有多个用户**，则返回 ``[]``（本轮不产出目标）并记 ``_skip_reason``
            —— 见下方 fail-safe。
          · ``"*"``      → 自动枚举库里出现过的非空 user_id，按每 tick 上限轮转。
          · 其它         → 逗号分隔的用户 id 列表。

        自动枚举时游标按 ``max_users_per_tick`` 前进，避免每 tick 都只服务
        同一批头部用户（条数降序，不轮转会永远先跑最大的那几个）。
        """
        self._skip_reason = ""
        raw = str(self._opt("autonomous_background_user_ids", "") or "").strip()
        if not raw:
            # 未配置 = 单租户语义。但「未配置」和「真的是单租户」是两回事：
            # 多租户部署若忘了配这一项，旧行为会把不同用户的记忆混进同一个
            # 目标集（goal 文本直接内嵌记忆原文），属于跨用户隔离问题。
            # 这种「漏配」只能靠库里的用户数识别 —— 宁可这一轮不产出目标
            # （有明确日志与状态字段），也不静默混合。
            ids = self._all_user_ids()
            if len(ids) > 1:
                self._skip_reason = (
                    f"检测到 {len(ids)} 个用户，但 autonomous_background_user_ids "
                    f"未配置 —— 拒绝按「系统级混合」生成目标。请配置该用户列表"
                    f"（逗号分隔），或用 '*' 自动枚举轮转。"
                )
                _log.warning("后台自主循环本轮不产出目标：%s", self._skip_reason)
                return []
            return [""]
        if raw != "*":
            return [u.strip() for u in raw.split(",") if u.strip()]

        ids = self._all_user_ids()
        if not ids:
            return []
        per = max(1, int(self._opt(
            "autonomous_background_max_users_per_tick", 5)))
        if len(ids) <= per:
            return ids
        start = self._user_cursor % len(ids)
        picked = [ids[(start + i) % len(ids)] for i in range(per)]
        self._user_cursor = (start + per) % len(ids)
        return picked

    # ── 已推进目标的持久化（跨会话不重复推同一件事） ────
    # 读写都委托给门面，保持"哪些目标最近推进过"只有一处实现。

    def _remember_advanced(self, key: str) -> None:
        if not key:
            return
        try:
            self._soma._mark_goal_advanced(key)
        except Exception:
            _log.debug("记录已推进目标失败（不影响本轮）", exc_info=True)

    def recent_keys(self) -> Set[str]:
        try:
            return set(self._soma._recent_goal_keys())
        except Exception:
            return set()
