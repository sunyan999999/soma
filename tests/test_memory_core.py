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
        use_vector_search=False,
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

    def test_graph_expanded_retrieval(self, memory):
        """图谱扩展检索：当语义图谱中有 (A, 关联, B) 时，
        搜索 A 应能找到关于 B 的情节记忆。"""
        # 建立语义图谱：增长 → 第一性原理
        memory.remember_semantic("增长", "依赖", "第一性原理")

        # 存储关于 B 的情节记忆（不含 A 关键词）
        memory.remember(
            "第一性原理的核心：将问题分解到不可再分的基本元素",
            {"domain": "方法论"},
        )

        # 用 A 关键词搜索 — 应通过图扩展找到关于 B 的记忆
        focus = Focus(
            law_id="first_principles",
            dimension="如何分析增长问题",
            keywords=["增长"],
            weight=0.9,
            rationale="",
        )

        results = memory.query(focus, top_k=5)
        assert len(results) >= 1
        contents = [r.memory.content.lower() for r in results]
        assert any("第一性原理" in c for c in contents), \
            f"图谱扩展未生效，检索结果: {contents}"

    def test_graph_expansion_no_match(self, memory):
        """图谱中无匹配节点时，扩展不应影响检索"""
        memory.remember("普通的业务分析笔记", {"domain": "分析"})

        focus = Focus(
            law_id="pareto_principle",
            dimension="测试",
            keywords=["普通"],
            weight=0.8,
            rationale="",
        )

        results = memory.query(focus, top_k=5)
        assert len(results) >= 1
        # 无图谱匹配时行为正常

    def test_expand_via_semantic_graph_empty(self, memory):
        """空图谱时扩展返回空列表"""
        terms = memory._expand_via_semantic_graph(["测试"])
        assert terms == []

    def test_expand_via_semantic_graph_with_data(self, memory):
        """有匹配节点时返回扩展词"""
        memory.remember_semantic("增长", "依赖", "第一性原理")
        memory.remember_semantic("第一性原理", "应用于", "工程设计")
        terms = memory._expand_via_semantic_graph(["增长"])
        assert "第一性原理" in terms
