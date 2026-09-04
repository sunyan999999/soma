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
