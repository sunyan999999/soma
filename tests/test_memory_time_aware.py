"""记忆时间感知测试（v2.0.12）

背景：接入方反馈记忆串台 —— 记忆注入 LLM 时无时间信息，LLM 把远期旧状态
当当前状态回复。修复 = explain_activation 返回时间 + query_memory 支持
max_age_days 时间窗口硬截断。

覆盖：
- explain_activation() 返回 timestamp/age_days/memory_type
- query_memory() 暴露 max_age_days 透传
- 底层 max_age_days 硬截断远期记忆
- 端到端：query_memory(max_age_days) 不含远期记忆
"""
import time
from pathlib import Path

import pytest

from soma.agent import SOMA_Agent
from soma.base import ActivatedMemory, MemoryUnit
from soma.config import SOMAConfig, load_config


@pytest.fixture
def agent(tmp_path):
    framework = load_config(Path("wisdom_laws.yaml"))
    config = SOMAConfig(
        framework=framework,
        episodic_persist_dir=tmp_path / "chroma",
        default_top_k=5,
        recall_threshold=0.01,
        use_vector_search=False,
    )
    a = SOMA_Agent(config)
    yield a
    a.close()


def _backdate(agent, keyword, days: float):
    """把最近一条匹配记忆的时间改到 days 天前（模拟远期记忆）"""
    mems = agent.memory.episodic.query_by_keywords([keyword], top_k=10)
    if not mems:
        return
    old_ts = time.time() - days * 86400
    agent.memory.episodic._conn.execute(
        "UPDATE episodic_memories SET timestamp=? WHERE id=?",
        (old_ts, mems[0].id))
    agent.memory.episodic._conn.commit()


class TestExplainActivationTime:
    def test_includes_time_fields(self, agent):
        """explain_activation 返回 timestamp/age_days/memory_type"""
        agent.remember("用户最近睡眠不错", {"domain": "健康"})
        results = agent.query_memory("睡眠", top_k=5)
        assert results, "应召回记忆"
        for item in results:
            assert "timestamp" in item, "缺 timestamp"
            assert "age_days" in item, "缺 age_days"
            assert "memory_type" in item, "缺 memory_type"
            assert isinstance(item["age_days"], float)
            assert item["age_days"] >= 0
            assert item["memory_type"] == "episodic"

    def test_old_memory_age_days_large(self, agent):
        """远期记忆的 age_days 应正确反映年龄（无过滤时）"""
        agent.remember("用户睡眠不好经常失眠", {"domain": "健康"})
        _backdate(agent, "失眠", 40)
        # 直接查底层（绕过 ranker threshold），用高匹配关键词
        all_mem = agent.memory.episodic.query_by_keywords(
            ["失眠"], top_k=10, max_age_days=1000)
        assert all_mem
        ages = [(time.time() - m.timestamp) / 86400 for m in all_mem]
        assert any(a > 30 for a in ages), "应有 >30 天的远期记忆"


class TestMaxAgeDays:
    def test_passthrough_no_error(self, agent):
        """query_memory(max_age_days) 透传不抛错 + 时间字段保留"""
        agent.remember("用户最近睡眠不错", {"domain": "健康"})
        results = agent.query_memory("睡眠", top_k=5, max_age_days=30)
        assert results
        for item in results:
            assert "age_days" in item
            assert item["age_days"] <= 30

    def test_episodic_truncates_old(self, agent):
        """底层 max_age_days 硬截断远期记忆"""
        agent.remember("用户睡眠不好经常失眠", {"domain": "健康"})
        agent.remember("用户最近睡眠不错", {"domain": "健康"})
        _backdate(agent, "失眠", 40)
        all_mem = agent.memory.episodic.query_by_keywords(
            ["睡眠"], top_k=10, max_age_days=1000)
        recent = agent.memory.episodic.query_by_keywords(
            ["睡眠"], top_k=10, max_age_days=30)
        assert len(all_mem) == 2
        assert len(recent) == 1, "40 天记忆应被截断"
        assert all((time.time() - m.timestamp) / 86400 <= 30 for m in recent)

    def test_query_memory_end_to_end(self, agent):
        """端到端：query_memory(max_age_days=30) 不含远期记忆"""
        agent.remember("用户睡眠不好经常失眠", {"domain": "健康"})
        agent.remember("用户最近睡眠不错", {"domain": "健康"})
        _backdate(agent, "失眠", 40)
        results = agent.query_memory("睡眠", top_k=5, max_age_days=30)
        assert results
        for item in results:
            assert item["age_days"] <= 30, f"含远期记忆: {item['content_preview'][:20]}"


class TestNature:
    """记忆业务性质字段（v2.0.14：state/fact/event）"""

    def test_remember_nature_roundtrip(self, agent):
        """remember(nature) 存入 → 查询返回同一 nature"""
        agent.remember("用户最近睡眠不错", {"domain": "健康"}, nature="state")
        r = agent.query_memory("睡眠", top_k=3)
        assert r
        assert all(x["nature"] == "state" for x in r), f"nature 应为 state: {r}"

    def test_default_nature_event(self, agent):
        """不带 nature 的记忆默认 event"""
        agent.remember("用户昨天开会", {"domain": "工作"})
        r = agent.query_memory("开会", top_k=3)
        assert r and r[0]["nature"] == "event"

    def test_nature_fact(self, agent):
        agent.remember("用户会写 Python", {"domain": "技能"}, nature="fact")
        r = agent.query_memory("Python", top_k=3)
        assert r and r[0]["nature"] == "fact"

    def test_explain_activation_has_nature_stale(self, agent):
        """explain_activation 返回 nature/is_stale 字段"""
        agent.remember("用户睡眠不好", {"domain": "健康"}, importance=0.9,
                       nature="state")
        r = agent.query_memory("睡眠", top_k=3)
        assert r
        for x in r:
            assert "nature" in x and "is_stale" in x

    def test_state_stale_logic(self):
        """is_state_stale：state 超窗口 True，未超/fact False"""
        from soma.base import MemoryUnit
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).timestamp()
        old_state = MemoryUnit(content="失眠", nature="state",
                               timestamp=now - 40 * 86400)
        new_state = MemoryUnit(content="失眠", nature="state",
                               timestamp=now - 86400)
        old_fact = MemoryUnit(content="会Python", nature="fact",
                              timestamp=now - 100 * 86400)
        old_event = MemoryUnit(content="开会", nature="event",
                               timestamp=now - 100 * 86400)
        assert old_state.is_state_stale() is True
        assert new_state.is_state_stale() is False
        assert old_fact.is_state_stale() is False
        assert old_event.is_state_stale() is False

    def test_old_high_importance_state_is_stale(self, agent):
        """40 天前 state 记忆召回时 is_stale=True（提示勿当当前状态）"""
        from datetime import datetime, timezone
        from soma.base import ActivatedMemory, MemoryUnit
        now = datetime.now(timezone.utc).timestamp()
        mem = MemoryUnit(content="用户睡眠不好长期失眠", nature="state",
                         timestamp=now - 40 * 86400, importance=0.95)
        am = ActivatedMemory(memory=mem, activation_score=0.8,
                             source="episodic", match_rationale="匹配")
        info = agent.hub.explain_activation(am)
        assert info["nature"] == "state"
        assert info["is_stale"] is True, "40 天前 state 记忆应 is_stale=True"
        assert info["age_days"] > 30


class TestInjectionTimeAnnotation:
    """注入层时间标注（v2.0.18）

    2.0.13 只修了「返回给调用方」的 explain_activation，SOMA **自身注入 LLM 的
    prompt**（_build_prompt 的四条路径）当时仍无时间信息 —— 本类覆盖补齐的另一半。
    """

    @staticmethod
    def _am(content, days, nature="state", score=0.8, source="episodic"):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).timestamp()
        mem = MemoryUnit(content=content, nature=nature,
                         timestamp=now - days * 86400)
        return ActivatedMemory(memory=mem, activation_score=score, source=source)

    def test_age_label_buckets(self):
        """age_label 分档：今天 / 昨天 / N 天前 / 约 N 周前 / 约 N 个月前"""
        assert self._am("x", 0.1).memory.age_label() == "今天"
        assert self._am("x", 1.5).memory.age_label() == "昨天"
        assert self._am("x", 5).memory.age_label() == "5 天前"
        assert "周前" in self._am("x", 12).memory.age_label()
        assert "个月前" in self._am("x", 90).memory.age_label()

    def test_staleness_note_only_for_stale_state(self):
        """过期提示只对 nature=state 且超 30 天出现（fact/event 恒不提示）"""
        assert self._am("失眠", 90, nature="state").memory.staleness_note() != ""
        assert self._am("失眠", 3, nature="state").memory.staleness_note() == ""
        assert self._am("会Python", 200, nature="fact").memory.staleness_note() == ""
        assert self._am("开会", 200, nature="event").memory.staleness_note() == ""

    def test_l1_injection_has_time(self, agent):
        """L1 轻量模式注入带时间标注 + 过期提示"""
        agent._current_complexity = 1
        old = self._am("用户长期失眠", 90)
        prompt = agent._build_prompt("我睡不好", [], [old])
        assert "约 3 个月前" in prompt, f"L1 注入缺时间标注:\n{prompt}"
        assert "不得直接当作当前状态回复" in prompt, "L1 注入缺过期提示"

    def test_l2_injection_has_time(self, agent):
        """L2/L3 推理模式注入带时间标注 + 过期提示"""
        agent._current_complexity = 2
        agent._last_reasoning = [{"index": 1, "weight": 1.0, "template": "测试维度"}]
        old = self._am("用户长期失眠", 90)
        prompt = agent._build_prompt("我睡不好", [], [old])
        assert "约 3 个月前" in prompt, f"L2 注入缺时间标注:\n{prompt}"
        assert "不得直接当作当前状态回复" in prompt

    def test_same_content_distinguishable(self, agent):
        """核心验收：同样内容的记忆，新旧在注入文本中可区分"""
        agent._current_complexity = 1
        old = self._am("用户失眠，连续三晚睡不好", 90)
        new = self._am("用户失眠，连续三晚睡不好", 0.1)
        p_old = agent._build_prompt("睡眠", [], [old])
        p_new = agent._build_prompt("睡眠", [], [new])
        assert "约 3 个月前" in p_old and "约 3 个月前" not in p_new
        assert "今天" in p_new
        assert p_old != p_new, "新旧记忆的注入文本应可区分"

    def test_anti_view_path_has_time(self, agent):
        """反面视角注入路径带时间标注"""
        agent._current_complexity = 2
        agent._last_reasoning = [{"index": 1, "weight": 1.0, "template": "测试"}]
        agent._last_anti_memories = [self._am("用户去年失眠", 300)]
        prompt = agent._build_prompt("睡眠", [], [self._am("参考", 1)])
        assert "个月前" in prompt, f"反面视角缺时间标注:\n{prompt}"

    def test_conflict_path_has_time(self, agent):
        """矛盾记忆注入路径带时间标注"""
        agent._current_complexity = 2
        agent._last_reasoning = [{"index": 1, "weight": 1.0, "template": "测试"}]
        a = self._am("用户失眠", 120)
        b = self._am("用户睡眠很好", 2)
        agent.hub.last_conflicts = [(a, b, 0.55)]
        try:
            prompt = agent._build_prompt("睡眠", [], [])
            assert "约 4 个月前" in prompt, f"矛盾路径缺 A 时间:\n{prompt}"
            assert "2 天前" in prompt, f"矛盾路径缺 B 时间:\n{prompt}"
        finally:
            agent.hub.last_conflicts = []

    def test_formatting_failure_is_safe(self):
        """格式化异常不得中断注入 —— 退回空串而非抛错"""
        from soma.agent import _memory_time_note, _staleness_block

        class Broken:
            class memory:
                pass

        assert _memory_time_note(Broken()) == ""
        assert _staleness_block(Broken()) == ""


class TestStaleStateInjection:
    """过期状态的独立注入通道（v2.0.18）

    仅给注入层加时间标注并不够：主激活路径按「规律权重 × 近因衰减」打分，7 天
    半衰期下 score 掉得极快，ranker 的 threshold 闸门会把远期记忆全部挡在门外，
    而 is_state_stale() 判的是 30 天以上 —— 两个条件互斥，过期状态永远到不了
    注入层。更关键的是「我最近睡眠怎么样」这类口语问题被判为 L1，连反视角检索
    都不跑。本类覆盖为此单开的 _stale_state_memories()。
    """

    def _stale_state(self, agent, content, days=120, importance=0.9):
        mid = agent.remember(content, {"domain": "健康"},
                             importance=importance, nature="state")
        agent.memory.episodic._conn.execute(
            "UPDATE episodic_memories SET timestamp=? WHERE id=?",
            (time.time() - days * 86400, mid))
        agent.memory.episodic._conn.commit()
        return mid

    def test_decay_would_have_blocked_it(self, agent):
        """记录本通道存在的理由：该记忆的关联潜力远低于激活阈值"""
        self._stale_state(agent, "用户长期失眠，连续三晚睡不好")
        mem = agent.memory.episodic.query_by_filters(nature="state", limit=5)[0]
        assert mem.relevance_potential() < agent.hub.threshold, (
            "前提变化：过期状态的关联潜力已不低于激活阈值，可重新评估是否需要本通道"
        )

    def test_stale_state_surfaces_for_l1(self, agent):
        """L1 口语问题也能带出过期状态，并给出「不得直接当作当前状态回复」"""
        mid = self._stale_state(agent, "用户长期失眠，连续三晚睡不好，白天精力下降")
        picked = agent._stale_state_memories("我最近睡眠怎么样，需要调整吗")
        assert [am.memory.id for am in picked] == [mid]

        agent._current_complexity = 1
        prompt = agent._build_prompt("我最近睡眠怎么样，需要调整吗", [], [], picked)
        assert "可能已过期的状态记录" in prompt, f"缺过期状态块:\n{prompt}"
        assert "约 4 个月前" in prompt
        assert "不得直接当作当前状态回复" in prompt
        assert "白天精力下降" in prompt

    def test_stale_state_surfaces_for_l2(self, agent):
        """L2 完整框架模式同样带出该块"""
        self._stale_state(agent, "用户长期失眠，白天精力下降")
        picked = agent._stale_state_memories("深入分析我的睡眠和精力问题")
        assert picked, "应命中该过期状态"
        agent._current_complexity = 2
        agent._last_reasoning = [{"index": 1, "weight": 1.0, "template": "测试"}]
        prompt = agent._build_prompt("深入分析我的睡眠和精力问题", [], [], picked)
        assert "可能已过期的状态记录" in prompt
        assert "不得直接当作当前状态回复" in prompt

    def test_irrelevant_state_not_injected(self, agent):
        """与问题没有共同汉字的状态不进块 —— 不能把无关旧状态塞进每次对话"""
        self._stale_state(agent, "用户三年前在杭州住过")
        assert agent._stale_state_memories("帮我看看这段排序算法怎么写") == []

    def test_fresh_state_not_injected(self, agent):
        """未超时效窗口的状态不进块（那是普通记忆参考的职责）"""
        self._stale_state(agent, "用户最近开始晨跑", days=3)
        assert agent._stale_state_memories("我最近晨跑怎么样") == []

    def test_fact_never_in_block(self, agent):
        """fact/event 再老也不进块 —— 判据是 is_state_stale()"""
        mid = agent.remember("用户偏好简洁的代码风格", {"domain": "偏好"},
                             importance=0.9, nature="fact")
        agent.memory.episodic._conn.execute(
            "UPDATE episodic_memories SET timestamp=? WHERE id=?",
            (time.time() - 400 * 86400, mid))
        agent.memory.episodic._conn.commit()
        assert agent._stale_state_memories("用户代码风格偏好是什么") == []

    def test_capped_at_two(self, agent):
        """最多 2 条 —— 注入块不能挤占正文"""
        for i in range(5):
            self._stale_state(agent, f"用户长期肩颈酸痛记录第 {i} 次",
                              days=60 + i, importance=0.7 + i * 0.02)
        picked = agent._stale_state_memories("用户肩颈酸痛怎么样")
        assert len(picked) == 2

    def test_empty_problem_is_safe(self, agent):
        self._stale_state(agent, "用户长期失眠")
        assert agent._stale_state_memories("") == []

    def test_no_stale_states_no_block(self, agent):
        """库里没有过期状态时，prompt 里不该出现这个块"""
        agent._current_complexity = 1
        assert "可能已过期的状态记录" not in agent._build_prompt("随便问问", [], [])
        assert agent._stale_state_memories("随便问问") == []

    def test_store_failure_is_safe(self, agent):
        """取状态失败不得中断对话 —— 退回空列表"""
        class Boom:
            def query_by_filters(self, **kw):
                raise RuntimeError("boom")

        original = agent.memory.episodic
        try:
            agent.memory.episodic = Boom()
            assert agent._stale_state_memories("睡眠") == []
        finally:
            agent.memory.episodic = original

    # ── v2.0.18.1：接入方生产验证发现的两处缺陷 ──────────────

    def test_stale_state_respects_user_id(self, agent):
        """P0 回归：A 的过期状态不得注入 B 的 prompt（跨用户泄漏）。

        接入方在多租户生产环境复现的原始场景：用户 A 写一条 nature=state 并置为
        60 天前，用户 B 无任何记忆却问到同一件事 —— 该块按「共同汉字 ≥2」命中了
        A 的记忆并注入 B 的 prompt。根因是 query_by_filters 的语义是「传了
        user_id 才过滤」，而这条通道当初没传，等于对所有用户开放。
        """
        mid = agent.remember(
            "我最近失眠很严重，每天晚上只能睡三小时",
            {"domain": "健康"}, importance=0.9, user_id="111", nature="state")
        agent.memory.episodic._conn.execute(
            "UPDATE episodic_memories SET timestamp=? WHERE id=?",
            (time.time() - 60 * 86400, mid))
        agent.memory.episodic._conn.commit()

        problem = "我最近失眠很严重，晚上翻来覆去睡不着"
        # 用户 B 取不到 A 的过期状态 —— 这是本用例的核心断言
        assert agent._stale_state_memories(problem, user_id="222") == [], (
            "跨用户泄漏：B 的提问捞到了 A 的过期状态"
        )
        # 用户 A 自己能取到（确认上面不是「功能整体失效」造成的假通过）
        assert [am.memory.id for am in agent._stale_state_memories(problem, user_id="111")] == [mid]
        # user_id="" 表示不过滤，保持单用户部署的既有行为
        assert len(agent._stale_state_memories(problem)) == 1

    def test_candidate_pool_reaches_old_state_beyond_recent_50(self, agent):
        """候选池回归：过期状态不再被「最近 50 条 state」挤出窗口。

        原先按 timestamp DESC 取最近 50 条 state 再逐条判 is_state_stale() ——
        两个条件方向相反。接入方在 26,977 条的生产库上造了 60/95 天前的 state
        记忆，该块仍不触发：那两条排不进「最近 50 条」，功能等于死的。
        这里用 60 条新鲜的 state 记忆把过期那条挤到窗口外。
        """
        for i in range(60):
            agent.remember(f"用户今天状态记录第 {i} 条，睡眠正常",
                           {"domain": "健康"}, nature="state")
        mid = self._stale_state(agent, "用户长期失眠，白天精力下降", days=90)

        picked = agent._stale_state_memories("用户失眠和精力怎么样")
        assert [am.memory.id for am in picked] == [mid], (
            f"候选池未按 older_than_days 收窄：取到 {len(picked)} 条"
        )
