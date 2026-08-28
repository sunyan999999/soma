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
