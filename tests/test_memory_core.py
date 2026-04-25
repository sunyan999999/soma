from pathlib import Path

import pytest

from soma.config import SOMAConfig
from soma.base import Focus
from soma.memory.core import MemoryCore


@pytest.fixture
def config(tmp_path):
    return SOMAConfig(
        episodic_persist_dir=tmp_path / "chroma",
        default_top_k=5,
    )


@pytest.fixture
def memory(config):
    return MemoryCore(config)


class TestMemoryCore:
    def test_remember_episodic(self, memory):
        mid = memory.remember("第一性原理应用案例", {"domain": "案例"}, importance=0.9)
        assert len(mid) == 32  # uuid hex

    def test_remember_semantic(self, memory):
        memory.remember_semantic("增长", "依赖", "创新")
        assert memory.semantic.count_triples() == 1

    def test_query_across_stores(self, memory):
        # 填充各库
        memory.remember("第一性原理在增长分析中的应用", {"domain": "分析"})
        memory.remember_semantic("增长", "依赖", "第一性原理")
        memory.skill.add_skill("归因分析", "按要素-连接-目的拆解问题")

        focus = Focus(
            law_id="first_principles",
            dimension="从第一性原理分析增长问题",
            keywords=["第一性原理", "增长"],
            weight=0.9,
            rationale="测试",
        )

        results = memory.query(focus, top_k=5)
        assert len(results) >= 1
        # 应有 episodic 和 semantic 的混合结果
        sources = {r.source for r in results}
        assert "episodic" in sources
        assert "semantic" in sources

    def test_stats(self, memory):
        memory.remember("记忆1")
        memory.remember("记忆2")
        memory.remember_semantic("A", "关联", "B")

        stats = memory.stats()
        assert stats["episodic"] == 2
        assert stats["semantic"] == 1
        assert stats["skill"] == 0

    def test_query_empty_memory(self, memory):
        focus = Focus(
            law_id="first_principles",
            dimension="测试",
            keywords=["不存在"],
            weight=0.9,
            rationale="",
        )
        results = memory.query(focus)
        assert len(results) == 0
