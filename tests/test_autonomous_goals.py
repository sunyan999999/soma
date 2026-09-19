# -*- coding: utf-8 -*-
"""自主认知循环补全测试（v2.0.18）

覆盖三件事：
- 自主目标来源（GoalGenerator）：过期状态 / 跨会话遗留计划 / 被埋没记忆 / 冲突
- 循环环节质量：停滞判定三态、进化节拍与脏标记、防目标自我嵌套
- 后台常驻（BackgroundRunner）：默认关闭、并发上限 1、可停、失败被记录
- 跨会话整合（integrate_session）：会话边界持久化
"""
import time

import pytest

from soma import SOMA


@pytest.fixture
def soma(tmp_path):
    s = SOMA(persist_dir=str(tmp_path), llm="mock")
    yield s
    s.close()


def _backdate(s: SOMA, memory_id: str, days: float) -> None:
    """把记忆时间改到 days 天前（模拟远期记忆）"""
    conn = s._agent.memory.episodic._conn
    conn.execute(
        "UPDATE episodic_memories SET timestamp=? WHERE id=?",
        (time.time() - days * 86400, memory_id),
    )
    conn.commit()


def _bg_soma(tmp_path, **kw):
    """开启后台循环的实例（默认 interval 很长，测试里不靠它自动跑）"""
    return SOMA(persist_dir=str(tmp_path), llm="mock",
                autonomous_background_enabled=True, **kw)


class TestGoalSources:
    """3a 自主目标来源 —— 每个目标都要能追溯到具体记忆"""

    def test_empty_store_yields_nothing(self, soma):
        """空库不凭空造目标"""
        assert soma.generate_goals() == []

    def test_stale_state_source(self, soma):
        mid = soma.remember("用户长期失眠", {"domain": "健康"},
                            importance=0.9, nature="state")
        _backdate(soma, mid, 120)
        goals = soma.generate_goals(max_goals=10)
        assert any(g["source"] == "stale_state" for g in goals)

    def test_fresh_state_is_not_a_goal(self, soma):
        soma.remember("用户最近睡眠不错", {"domain": "健康"},
                      importance=0.9, nature="state")
        goals = soma.generate_goals(max_goals=10)
        assert not any(g["source"] == "stale_state" for g in goals)

    def test_pending_plan_source(self, soma):
        mid = soma.remember("执行计划: 优化检索 → 加缓存",
                            {"type": "execution_plan", "problem": "优化检索性能"},
                            importance=0.8)
        _backdate(soma, mid, 3)
        goals = soma.generate_goals(max_goals=10)
        assert any(g["source"] == "cross_session_plan" for g in goals)

    def test_autonomous_plan_is_not_recycled(self, soma):
        """自主循环自己写下的计划不得被回收成新目标（防无限自我嵌套）"""
        mid = soma.remember(
            "执行计划: 目标A → 行动B",
            {"type": "execution_plan", "problem": "目标A", "origin": "autonomous"},
            importance=0.8,
        )
        _backdate(soma, mid, 3)
        goals = soma.generate_goals(max_goals=10)
        assert not any(g["source"] == "cross_session_plan" for g in goals)

    def test_buried_memory_source(self, soma):
        mid = soma.remember("用户偏好简洁的代码风格", {"domain": "偏好"},
                            importance=0.85, nature="fact")
        _backdate(soma, mid, 20)
        goals = soma.generate_goals(max_goals=10)
        assert any(g["source"] == "buried_memory" for g in goals)

    def test_low_importance_not_buried_goal(self, soma):
        """重要性不够的记忆不算"被埋没" """
        mid = soma.remember("用户随口提过一句天气", {"domain": "闲聊"},
                            importance=0.2)
        _backdate(soma, mid, 60)
        goals = soma.generate_goals(max_goals=10)
        assert not any(g["source"] == "buried_memory" for g in goals)

    def test_autonomous_loop_log_not_buried(self, soma):
        """自主循环的自我对话日志不是"用户知识"，不参与回顾"""
        mid = soma.remember("自主推理: x → 结论: y",
                            {"type": "autonomous_loop"}, importance=0.9)
        _backdate(soma, mid, 30)
        goals = soma.generate_goals(max_goals=10)
        assert not any(g["source"] == "buried_memory" for g in goals)

    def test_sorted_by_priority_with_evidence(self, soma):
        s1 = soma.remember("用户长期失眠", {"domain": "健康"},
                           importance=0.9, nature="state")
        _backdate(soma, s1, 200)
        s2 = soma.remember("执行计划: 做A → 做B",
                           {"type": "execution_plan", "problem": "做A"},
                           importance=0.8)
        _backdate(soma, s2, 3)
        goals = soma.generate_goals(max_goals=10)
        assert len(goals) >= 2
        assert goals == sorted(goals, key=lambda g: g["priority"], reverse=True)
        assert all(g["evidence"] for g in goals), "每个目标都要带证据"

    def test_max_goals_limit(self, soma):
        s1 = soma.remember("用户长期失眠", {"domain": "健康"},
                           importance=0.9, nature="state")
        _backdate(soma, s1, 200)
        s2 = soma.remember("执行计划: 做A → 做B",
                           {"type": "execution_plan", "problem": "做A"},
                           importance=0.8)
        _backdate(soma, s2, 3)
        assert len(soma.generate_goals(max_goals=1)) == 1

    def test_advanced_goal_not_repeated(self, soma):
        """近期已推进的目标不再重复产出"""
        mid = soma.remember("用户长期失眠", {"domain": "健康"},
                            importance=0.9, nature="state")
        _backdate(soma, mid, 120)
        first = soma.generate_goals(max_goals=10)
        assert first
        soma._mark_goal_advanced(first[0]["key"])
        again = soma.generate_goals(max_goals=10)
        assert first[0]["key"] not in {g["key"] for g in again}

    def test_conflict_source(self, soma):
        """未澄清的记忆冲突会被列为目标（读 hub.last_conflicts）"""
        from soma.base import ActivatedMemory, MemoryUnit
        a = ActivatedMemory(
            memory=MemoryUnit(content="用户失眠", nature="state"),
            activation_score=0.8, source="episodic")
        b = ActivatedMemory(
            memory=MemoryUnit(content="用户睡眠很好", nature="state"),
            activation_score=0.8, source="episodic")
        soma._agent.hub.last_conflicts = [(a, b, 0.61)]
        try:
            goals = soma.generate_goals(max_goals=10)
            assert any(g["source"] == "conflict" for g in goals)
        finally:
            soma._agent.hub.last_conflicts = []


class TestGoalJudgement:
    """3c 停滞判定 —— 无 LLM 时只判停滞，不谎报完成"""

    def test_same_answer_is_stalled(self, soma):
        verdict, why = soma._judge_goal(
            "g", {"final_answer": "同样的答案"}, {}, prev_answer="同样的答案")
        assert verdict == "stalled"
        assert why

    def test_new_answer_continues(self, soma):
        verdict, _ = soma._judge_goal(
            "g", {"final_answer": "新答案"}, {}, prev_answer="旧答案",
            actions_text="做点什么")
        assert verdict == "continue"

    def test_no_action_is_stalled(self, soma):
        verdict, _ = soma._judge_goal("g", {"final_answer": "x"}, {},
                                      prev_answer="", actions_text="")
        assert verdict == "stalled"

    def test_feedback_fn_completes(self, soma):
        verdict, _ = soma._judge_goal("g", {}, {}, feedback_fn=lambda a, b: True)
        assert verdict == "complete"

    def test_feedback_fn_false_does_not_complete(self, soma):
        verdict, _ = soma._judge_goal(
            "g", {}, {}, feedback_fn=lambda a, b: False, actions_text="做点什么")
        assert verdict == "continue"

    def test_stalled_is_not_complete(self, soma):
        """停滞 ≠ 完成 —— bool 视图不得把停滞算成达成"""
        assert soma._check_goal_complete(
            "g", {"final_answer": "同样的答案"}, {}, None) is False

    def test_run_autonomous_reports_stop_reason(self, soma):
        """无目标时明确报 no_goal，而不是空转跑满轮数"""
        r = soma.run_autonomous(None, max_rounds=2)
        assert r["stop_reason"] == "no_goal"
        assert r["round_count"] == 0
        assert r["completed"] is False


class TestEvolutionRhythm:
    """3c 进化节拍 —— 配置驱动 + 脏标记，取代硬编码 % 5 / % 10 / % 30"""

    def test_off_beat_does_not_evolve(self, soma):
        soma._session_count = 1
        assert soma._maybe_evolve() == []

    def test_dirty_mark_skips_unchanged_samples(self, soma):
        """同一个节拍上样本数没变时不重复进化（空转）"""
        soma._session_count = 5
        soma._maybe_evolve()
        assert soma._maybe_evolve() == []

    def test_deep_evolution_beat(self, soma):
        soma._session_count = 30
        assert soma._is_deep_evolution_due() is True
        soma._session_count = 5
        assert soma._is_deep_evolution_due() is False

    def test_deep_beat_follows_config(self, soma):
        """深度节拍 = interval × deep_multiple，由配置决定"""
        soma._config.evolution_interval = 2
        soma._config.evolution_deep_multiple = 3
        soma._session_count = 6
        assert soma._is_deep_evolution_due() is True
        soma._session_count = 4
        assert soma._is_deep_evolution_due() is False

    def test_interval_follows_config(self, soma):
        soma._config.evolution_interval = 3
        soma._session_count = 2
        assert soma._maybe_evolve() == []
        soma._session_count = 3
        # 到点会真的尝试进化；只要不抛错即可（样本为 0 时 evolve 内部自行跳过）
        soma._maybe_evolve()


class TestSessionIntegration:
    """3d 跨会话整合 —— 会话边界持久化，只收集待办不擅自推进"""

    def test_first_run_is_new_session(self, soma):
        r = soma.integrate_session()
        assert r["is_new_session"] is True
        assert r["gap_seconds"] is None
        assert "首次" in r["gap_human"]

    def test_immediate_second_call_is_same_session(self, soma):
        soma.integrate_session()
        r = soma.integrate_session()
        assert r["is_new_session"] is False
        assert r["gap_seconds"] is not None

    def test_long_gap_is_new_session(self, soma):
        soma._agent.memory.episodic.meta_set(
            "autonomous_last_session_end", time.time() - 86400)
        r = soma.integrate_session()
        assert r["is_new_session"] is True
        assert "天" in r["gap_human"]

    def test_boundary_survives_new_instance(self, tmp_path):
        """会话边界写在库里 —— 换一个实例仍读得到（跨进程语义）"""
        s1 = SOMA(persist_dir=str(tmp_path), llm="mock")
        s1.integrate_session()
        s1.close()
        s2 = SOMA(persist_dir=str(tmp_path), llm="mock")
        try:
            r = s2.integrate_session()
            assert r["is_new_session"] is False, "新实例应看到上次会话的结束时间"
        finally:
            s2.close()

    def test_collects_pending_without_advancing(self, soma):
        mid = soma.remember("用户长期失眠", {"domain": "健康"},
                            importance=0.9, nature="state")
        _backdate(soma, mid, 120)
        r = soma.integrate_session()
        assert r["pending_count"] >= 1
        # 只收集、不推进 —— 目标仍然可以被正常生成出来
        assert soma.generate_goals(max_goals=10)


class TestBackgroundRunner:
    """3b 后台常驻 —— 默认关闭、并发上限 1、随时可停"""

    def test_disabled_by_default(self, soma):
        st = soma.background_status()
        assert st["enabled"] is False
        assert st["running"] is False
        r = soma.start_background()
        assert r["started"] is False
        assert r["reason"] == "disabled"
        assert "显式" in r["message"]

    def test_enabled_start_and_stop(self, tmp_path):
        s = _bg_soma(tmp_path)
        try:
            r = s.start_background()
            assert r["started"] is True
            assert s.background_status()["running"] is True
            # 并发上限 1：重复启动被拒
            r2 = s.start_background()
            assert r2["started"] is False and r2["reason"] == "already_running"
            st = s.stop_background(timeout=15)
            assert st["stopped"] is True
            assert s.background_status()["running"] is False
        finally:
            s.close()

    def test_stop_without_start(self, soma):
        r = soma.stop_background()
        assert r["stopped"] is True and r["was_running"] is False

    def test_tick_advances_goal(self, tmp_path):
        s = _bg_soma(tmp_path)
        try:
            mid = s.remember("用户长期失眠", {"domain": "健康"},
                             importance=0.9, nature="state")
            _backdate(s, mid, 120)
            called = []
            s.run_autonomous = lambda goal, **kw: (
                called.append(goal) or
                {"completed": False, "stop_reason": "stalled", "round_count": 1}
            )
            tick = s.run_background_tick()
            assert tick["tick"] == 1
            assert len(tick["advanced"]) == 1
            assert called, "tick 应真的去推进目标"
        finally:
            s.close()

    def test_tick_skips_when_busy(self, soma):
        """并发上限 1：已有 tick 在跑时再进入直接被跳过"""
        runner = soma._background_runner()
        assert runner._gate.acquire(blocking=False) is True
        try:
            r = runner.run_once()
            assert r.get("skipped") is True
            assert r.get("reason") == "tick_in_progress"
        finally:
            runner._gate.release()

    def test_tick_records_error_without_raising(self, tmp_path):
        """目标推进失败被记进 errors，不让 tick 抛出去"""
        s = _bg_soma(tmp_path)
        try:
            mid = s.remember("用户长期失眠", {"domain": "健康"},
                             importance=0.9, nature="state")
            _backdate(s, mid, 120)

            def boom(goal, **kw):
                raise RuntimeError("模拟推进失败")

            s.run_autonomous = boom
            tick = s.run_background_tick()
            assert tick["advanced"] == []
            assert tick["errors"] and "模拟推进失败" in tick["errors"][0]["error"]
        finally:
            s.close()

    def test_tick_times_out_skips_remaining(self, tmp_path):
        """单次 tick 的墙钟上限生效：超时后放弃剩余目标"""
        s = _bg_soma(tmp_path, autonomous_background_max_runtime=0)
        try:
            mid = s.remember("用户长期失眠", {"domain": "健康"},
                             importance=0.9, nature="state")
            _backdate(s, mid, 120)
            other = s.remember("执行计划: 做A → 做B",
                               {"type": "execution_plan", "problem": "做A"},
                               importance=0.8)
            _backdate(s, other, 3)
            tick = s.run_background_tick()
            assert tick["timed_out"] is True, "墙钟上限为 0 时应立即判定超时"
            assert tick["advanced"] == []
        finally:
            s.close()

    def test_status_shape_without_start(self, soma):
        st = soma.background_status()
        for key in ("enabled", "running", "tick_in_progress", "ticks",
                    "failures", "consecutive_failures", "interval", "last_result"):
            assert key in st


class TestSelfDirectedRun:
    """自主取目标跑一轮 —— 结果里要说清"为什么选它" """

    def test_self_directed_reports_source(self, tmp_path):
        s = SOMA(persist_dir=str(tmp_path), llm="mock")
        try:
            mid = s.remember("用户长期失眠", {"domain": "健康"},
                             importance=0.9, nature="state")
            _backdate(s, mid, 120)
            s.run_autonomous = lambda goal, **kw: {
                "goal": goal, "completed": False, "stop_reason": "stalled",
                "rounds": [], "round_count": 0, "final_answer": "",
            }
            r = s.run_self_directed()
            assert r["goal_source"] == "stale_state"
            assert r["goal_evidence"]
            assert r["goal"]
        finally:
            s.close()

    def test_self_directed_no_goal(self, soma):
        r = soma.run_self_directed()
        assert r["stop_reason"] == "no_goal"
        assert r["goal_source"] == ""

    def test_self_directed_marks_advanced(self, tmp_path):
        """跑过的目标会被记下来，下次不再重复选它"""
        s = SOMA(persist_dir=str(tmp_path), llm="mock")
        try:
            mid = s.remember("用户长期失眠", {"domain": "健康"},
                             importance=0.9, nature="state")
            _backdate(s, mid, 120)
            s.run_autonomous = lambda goal, **kw: {
                "goal": goal, "completed": False, "stop_reason": "stalled",
                "rounds": [], "round_count": 0, "final_answer": "",
            }
            first = s.run_self_directed()
            assert first["goal_key"]
            again = s.generate_goals(max_goals=10)
            assert first["goal_key"] not in {g["key"] for g in again}
        finally:
            s.close()


class TestAutonomousUserIsolation:
    """3e 自主目标的用户隔离（v2.0.18.2）

    四个自主目标来源里原本有三个不做用户过滤，而 goal 文本**直接内嵌记忆
    原文**（``mem.content[:40]`` / evidence ``[:60]``），随后被
    ``BackgroundRunner.run_once()`` 拿去 ``run_autonomous()`` 执行 —— 多租户
    部署下等于把**别人的**记忆端到自主循环面前。与 2.0.18.1 修的过期状态块
    跨用户泄漏同类，由接入方 DSH 在复验信里指出。
    """

    @staticmethod
    def _seed_two_users(s):
        """两个用户各留一类会被自主来源捡走的记忆。

        - alice：120 天前的 state  → 命中 stale_state
        - bob  ：20 天前高重要性   → 命中 buried_memory
        """
        a = s.remember("alice 长期失眠睡不好", {"domain": "健康"},
                       importance=0.9, user_id="alice", nature="state")
        b = s.remember("bob 的私人日记正在考虑换城市生活", {"domain": "私人"},
                       importance=0.95, user_id="bob", nature="event")
        _backdate(s, a, 120)
        _backdate(s, b, 20)
        return a, b

    @staticmethod
    def _text(goals):
        return " ".join(g["goal"] + " " + " ".join(g.get("evidence", []))
                        for g in goals)

    # ── 来源层：user_id 有没有真的传到 store ──────────────

    def test_all_store_sources_pass_user_id(self):
        """三个查库的来源都必须把 user_id 透传下去 —— 少一个就漏一个用户面。

        用 AST 的关键字参数判定，不做子串匹配：``user_id`` 在 docstring 里
        被提到（解释修复动机）是正常的，纯子串匹配会被文档误伤 —— 与
        ``assert "JOIN" not in sql`` 撞上自己 SQL 注释是同一个坑。
        """
        import ast
        import inspect
        import textwrap

        from soma.autonomous import GoalGenerator

        for name in ("_from_stale_states", "_from_pending_plans",
                     "_from_buried_memories"):
            src = textwrap.dedent(inspect.getsource(getattr(GoalGenerator, name)))
            kw = set()
            for node in ast.walk(ast.parse(src)):
                if isinstance(node, ast.Call):
                    kw |= {k.arg for k in node.keywords}
            assert "user_id" in kw, f"{name} 未把 user_id 传给 store"

    def test_conflict_source_filters_both_sides(self):
        """冲突对必须**两侧**都属于该用户 —— 只比一侧等于没比。

        ``hub.last_conflicts`` 是进程内观测值，来自「最近一次激活」；多租户下
        那次激活可能是别人的，所以只能按两侧各自的 ``memory.user_id`` 判定。
        """
        import ast
        import inspect
        import textwrap

        from soma.autonomous import GoalGenerator

        src = textwrap.dedent(inspect.getsource(GoalGenerator._from_conflicts))
        tree = ast.parse(src)

        # 数「按名字读 user_id」的次数，两种写法都算：
        #   a.user_id               → Attribute(attr="user_id")
        #   getattr(a, "user_id")   → getattr 调用的第二个位置参数是常量
        # （现用后者 —— 记忆对象不保证有 user_id 属性，直接取会 AttributeError）
        reads = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr == "user_id":
                reads += 1
            elif (isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Name)
                  and node.func.id == "getattr"
                  and len(node.args) >= 2
                  and isinstance(node.args[1], ast.Constant)
                  and node.args[1].value == "user_id"):
                reads += 1

        assert reads >= 2, (
            f"冲突对只比了 {reads} 侧的 user_id，应当两侧都比")

    # ── 行为层：按用户生成时是否真的不混 ──────────────────

    def test_goals_split_by_user(self, tmp_path):
        """传了 user_id 后，目标文本里不出现别人的记忆原文"""
        s = SOMA(persist_dir=str(tmp_path), llm="mock")
        try:
            self._seed_two_users(s)
            alice = self._text(s.generate_goals(max_goals=10, user_id="alice"))
            bob = self._text(s.generate_goals(max_goals=10, user_id="bob"))
            assert "换城市" not in alice, "alice 的目标里出现了 bob 的记忆原文"
            assert "失眠" not in bob, "bob 的目标里出现了 alice 的记忆原文"
            assert "失眠" in alice, "alice 自己的条目应当照常生成"
            assert "换城市" in bob, "bob 自己的条目应当照常生成"
        finally:
            s.close()

    def test_unscoped_call_keeps_single_tenant_semantics(self, tmp_path):
        """不传 user_id 仍是「系统级」旧语义 —— 这是**有意保留**的单租户契约。

        多租户的安全性不靠改这个默认值，而靠 ``_target_users()`` 的 fail-safe
        （见 ``test_multi_tenant_without_config_is_refused``）：库里有多个用户
        却不配置用户列表时，后台循环直接不产出目标。
        """
        s = SOMA(persist_dir=str(tmp_path), llm="mock")
        try:
            self._seed_two_users(s)
            text = self._text(s.generate_goals(max_goals=10))
            assert "失眠" in text and "换城市" in text
        finally:
            s.close()

    # ── 用户列表解析 ────────────────────────────────────

    def test_target_users_config_forms(self, tmp_path):
        """三种配置形态：逗号列表 / 通配 / 未配置"""
        s = SOMA(persist_dir=str(tmp_path), llm="mock")
        try:
            self._seed_two_users(s)
            s.remember("carol 的一句话", {"domain": "x"},
                       importance=0.5, user_id="carol")
            r = s._background_runner()

            s._config.autonomous_background_user_ids = "bob,alice"
            assert r._target_users() == ["bob", "alice"]
            assert r._skip_reason == ""

            s._config.autonomous_background_user_ids = "  alice , , bob  "
            assert r._target_users() == ["alice", "bob"], "空白项要被丢掉"

            s._config.autonomous_background_user_ids = "*"
            assert set(r._target_users()) == {"alice", "bob", "carol"}
        finally:
            s.close()

    def test_wildcard_rotates_across_ticks(self, tmp_path):
        """通配模式下每 tick 只覆盖上限内的用户，并按游标轮转 —— 条数降序
        排列时若不轮转，永远只服务头部那几个用户。"""
        s = SOMA(persist_dir=str(tmp_path), llm="mock")
        try:
            self._seed_two_users(s)
            s.remember("carol 的一句话", {"domain": "x"},
                       importance=0.5, user_id="carol")
            s._config.autonomous_background_user_ids = "*"
            s._config.autonomous_background_max_users_per_tick = 2
            r = s._background_runner()
            first = r._target_users()
            second = r._target_users()
            assert len(first) == 2 and len(second) == 2
            assert set(first) != set(second), "游标没有前进，永远只服务同一批"
        finally:
            s.close()

    # ── fail-safe：多租户未配置时拒绝混合 ────────────────

    def test_multi_tenant_without_config_is_refused(self, tmp_path):
        """多用户库 + 未配置用户列表 → 不产出目标，而不是静默混合。

        「未配置」和「真的是单租户」是两回事：前者在单租户库上是合理的旧
        语义，在多租户库上就是跨用户泄漏。只能靠库里的用户数区分。
        """
        s = SOMA(persist_dir=str(tmp_path), llm="mock")
        try:
            self._seed_two_users(s)
            s._config.autonomous_background_user_ids = ""
            ran = []
            s.run_autonomous = lambda goal, **kw: ran.append(goal)
            tick = s.run_background_tick()

            assert tick["users"] == []
            assert tick["advanced"] == []
            assert not ran, "fail-safe 生效时不得推进任何目标"
            assert "未配置" in tick["skip_reason"]

            st = s.background_status()
            assert st["multi_tenant_ready"] is False
            assert st["last_skip_reason"], "拒绝原因要能从状态里读到"
        finally:
            s.close()

    def test_single_tenant_not_affected_by_guard(self, tmp_path):
        """单租户库（只有一个用户）不受 fail-safe 影响，仍是旧语义"""
        s = SOMA(persist_dir=str(tmp_path), llm="mock")
        try:
            mid = s.remember("用户长期失眠", {"domain": "健康"},
                             importance=0.9, user_id="alice", nature="state")
            _backdate(s, mid, 120)
            s._config.autonomous_background_user_ids = ""
            r = s._background_runner()
            assert r._target_users() == [""]
            assert r._skip_reason == ""
        finally:
            s.close()

    def test_empty_store_is_not_treated_as_multi_tenant(self, tmp_path):
        """空库不触发 fail-safe —— 否则新库永远开不了后台循环"""
        s = SOMA(persist_dir=str(tmp_path), llm="mock")
        try:
            s._config.autonomous_background_user_ids = ""
            r = s._background_runner()
            assert r._target_users() == [""]
            assert r._skip_reason == ""
        finally:
            s.close()

    # ── 端到端：每个用户各跑一轮 ────────────────────────

    def test_tick_runs_each_user_separately(self, tmp_path):
        """配好用户列表后，每个用户各生成一轮，且目标只含自己的记忆"""
        s = _bg_soma(tmp_path, autonomous_background_user_ids="alice,bob")
        try:
            self._seed_two_users(s)
            seen = []
            s.run_autonomous = lambda goal, **kw: (
                seen.append(goal) or
                {"completed": False, "stop_reason": "stalled", "round_count": 1}
            )
            tick = s.run_background_tick()

            assert tick["users"] == ["alice", "bob"]
            assert tick["skip_reason"] == ""
            assert {i["user_id"] for i in tick["advanced"]} == {"alice", "bob"}
            for item in tick["advanced"]:
                if item["user_id"] == "alice":
                    assert "换城市" not in item["goal"]
                else:
                    assert "失眠" not in item["goal"]
        finally:
            s.close()

    # ── 去重键也要按用户分开 ────────────────────────────

    def test_goal_key_is_user_scoped(self, tmp_path):
        """两个用户写下**同样文字**的计划时，key 不能撞成同一个。

        ``plan:{problem[:60]}`` 用的是计划文本而不是记忆 id —— 不加用户前缀
        的话，A 推进过的目标会把 B 的同名目标错误地去重掉（跨用户串扰，方向
        是漏报而非泄漏，但同属「user 维度缺失」）。
        """
        s = SOMA(persist_dir=str(tmp_path), llm="mock")
        try:
            plan = {"type": "execution_plan", "problem": "优化检索性能"}
            s.remember("执行计划: 优化检索性能", plan,
                       importance=0.8, user_id="alice")
            s.remember("执行计划: 优化检索性能", plan,
                       importance=0.8, user_id="bob")

            a = s.generate_goals(max_goals=10, user_id="alice")
            b = s.generate_goals(max_goals=10, user_id="bob")
            assert a and b, "两个用户各自的计划都应能产出目标"
            assert a[0]["key"] != b[0]["key"], "同名计划必须有不同的 key"

            # A 推进过之后，B 的目标不该被连坐去重
            s._mark_goal_advanced(a[0]["key"])
            again = s.generate_goals(max_goals=10, user_id="bob")
            assert again, "bob 的目标被 alice 的推进记录去重掉了"
            assert not s.generate_goals(max_goals=10, user_id="alice"), \
                "alice 自己推进过的目标仍应被去重"
        finally:
            s.close()

    def test_single_tenant_key_has_no_prefix(self, tmp_path):
        """留空 user_id 时不加前缀 —— 单租户行为零变化，旧记录照常命中"""
        s = SOMA(persist_dir=str(tmp_path), llm="mock")
        try:
            mid = s.remember("用户长期失眠", {"domain": "健康"},
                             importance=0.9, nature="state")
            _backdate(s, mid, 120)
            goals = s.generate_goals(max_goals=10)
            assert goals
            assert goals[0]["key"].startswith("stale_state:"), \
                f"单租户下 key 不应带用户前缀，实际是 {goals[0]['key']!r}"
        finally:
            s.close()

    # ── 用户枚举本身 ────────────────────────────────────

    def test_distinct_user_ids_excludes_blank_bucket(self, tmp_path):
        """空串桶代表「未指定用户」这个命名空间本身，不该被当成一个用户枚举出来
        —— 否则通配模式会为它单独跑一轮系统级混合。"""
        s = SOMA(persist_dir=str(tmp_path), llm="mock")
        try:
            s.remember("没有用户归属的记忆", {"domain": "x"}, importance=0.5)
            s.remember("alice 的第一条", {"domain": "x"},
                       importance=0.5, user_id="alice")
            s.remember("alice 的第二条", {"domain": "x"},
                       importance=0.5, user_id="alice")
            s.remember("bob 的一条", {"domain": "x"},
                       importance=0.5, user_id="bob")

            ids = s._agent.memory.episodic.distinct_user_ids()
            assert "" not in ids
            assert ids[0] == "alice", "应按记忆条数降序"
            assert "bob" in ids
        finally:
            s.close()
