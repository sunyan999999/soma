"""边界测试 — 冷启动、空记忆、持久化连接管理"""
from pathlib import Path

import pytest

from soma.config import SOMAConfig, load_config
from soma.agent import SOMA_Agent
from soma.memory.episodic import EpisodicStore
from soma.memory.skill import SkillStore


class TestColdStart:
    """空记忆冷启动场景"""

    @pytest.fixture
    def empty_agent(self, tmp_path):
        framework = load_config(Path("wisdom_laws.yaml"))
        config = SOMAConfig(
            framework=framework,
            episodic_persist_dir=tmp_path / "empty",
            default_top_k=5,
            recall_threshold=0.01,
            use_vector_search=False,
        )
        return SOMA_Agent(config)

    def test_respond_with_no_memories(self, empty_agent):
        from unittest.mock import patch

        with patch("soma.agent.completion") as mock:
            mock.return_value.choices = [
                type("C", (), {"message": type("M", (), {"content": "分析完成"})()})()
            ]

            answer = empty_agent.respond("为什么增长停滞？")
            assert len(answer) > 0

    def test_decompose_with_no_memories(self, empty_agent):
        foci = empty_agent.decompose("为什么增长停滞？")
        assert len(foci) >= 1

    def test_query_memory_empty(self, empty_agent):
        results = empty_agent.query_memory("增长")
        assert len(results) == 0

    def test_stats_all_zero(self, empty_agent):
        stats = empty_agent.memory.stats()
        assert stats["episodic"] == 0
        assert stats["semantic"] == 0
        assert stats["skill"] == 0

    def test_reflect_no_context(self, empty_agent):
        empty_agent.reflect("cold_start", "success")
        assert len(empty_agent.evolver.get_log()) == 1

    def test_evolve_no_data(self, empty_agent):
        changes = empty_agent.evolver.evolve()
        assert len(changes) == 0


class TestStoreClose:
    """存储连接管理"""

    def test_episodic_close(self, tmp_path):
        store = EpisodicStore(tmp_path, use_vector_search=False)
        store.add("测试记忆")
        assert store.count() == 1
        store.close()
        # 关闭后不应报错

    def test_skill_close(self, tmp_path):
        store = SkillStore(persist_dir=tmp_path)
        store.add_skill("测试技能", "测试模式")
        assert store.count() == 1
        store.close()

    def test_episodic_persistence_across_instances(self, tmp_path):
        """两个实例指向同一 DB 应能看到相同数据"""
        store1 = EpisodicStore(tmp_path, use_vector_search=False)
        mid = store1.add("持久化测试记忆")
        store1.close()

        store2 = EpisodicStore(tmp_path, use_vector_search=False)
        mem = store2.get(mid)
        assert mem is not None
        assert "持久化测试" in mem.content
        store2.close()
