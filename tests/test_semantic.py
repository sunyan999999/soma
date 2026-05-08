import pytest
from pathlib import Path
from soma.memory.semantic import SemanticStore


@pytest.fixture
def store(tmp_path: Path):
    s = SemanticStore(tmp_path)
    s.add_triple("快速决策", "依赖", "第一性原理")
    s.add_triple("系统思维", "关联", "矛盾分析")
    s.add_triple("逆向思考", "突破", "认知盲区")
    return s


class TestSemanticStore:
    def test_add_triple(self, store):
        assert store.count_triples() == 3
        assert "快速决策" in store.list_nodes()
        assert "第一性原理" in store.list_nodes()

    def test_query_by_keywords_node(self, store):
        results = store.query_by_keywords(["第一性原理"])
        assert len(results) >= 1
        assert any("第一性原理" in r.content for r in results)

    def test_query_by_keywords_predicate(self, store):
        results = store.query_by_keywords(["依赖"])
        assert len(results) >= 1
        assert any("依赖" in r.content for r in results)

    def test_query_empty(self, store):
        results = store.query_by_keywords(["不存在"])
        assert len(results) == 0

    def test_get_neighbors(self, store):
        info = store.get_neighbors("快速决策")
        assert info["node"] == "快速决策"
        assert "第一性原理" in info["neighbors"]

    def test_get_neighbors_unknown_node(self, store):
        info = store.get_neighbors("不存在的概念")
        assert info["node"] == "不存在的概念"
        assert info["neighbors"] == []

    def test_list_nodes(self, store):
        nodes = store.list_nodes()
        assert "快速决策" in nodes
        assert "认知盲区" in nodes

    def test_count_triples(self, store):
        assert store.count_triples() == 3

    def test_semantic_memory_type(self, store):
        results = store.query_by_keywords(["第一性原理"])
        assert all(r.memory_type == "semantic" for r in results)

    def test_top_k_limit(self, store):
        # Add more triples
        for i in range(10):
            store.add_triple(f"概念{i}", "关联", f"概念{i+1}")
        results = store.query_by_keywords(["概念"], top_k=3)
        assert len(results) <= 3

    def test_expand_query_terms_depth_one(self, store):
        terms = store.expand_query_terms(["快速决策"], depth=1)
        assert "第一性原理" in terms
        assert len(terms) >= 1

    def test_expand_query_terms_depth_two(self, store):
        store.add_triple("第一性原理", "应用于", "工程设计")
        terms = store.expand_query_terms(["快速决策"], depth=2)
        assert "第一性原理" in terms
        assert "工程设计" in terms

    def test_expand_query_terms_unknown_node(self, store):
        terms = store.expand_query_terms(["不存在的概念"], depth=2)
        assert terms == []

    def test_expand_query_terms_empty_input(self, store):
        terms = store.expand_query_terms([], depth=2)
        assert terms == []

    def test_expand_query_terms_max_terms_cap(self, store):
        for i in range(20):
            store.add_triple(f"概念{i}", "关联", f"概念{i+1}")
        terms = store.expand_query_terms(["概念0"], depth=1, max_terms=5)
        assert len(terms) <= 5

    def test_expand_query_terms_dedup(self, store):
        store.add_triple("快速决策", "也关联", "系统思维")
        terms = store.expand_query_terms(["快速决策", "系统思维"], depth=1)
        assert len(terms) == len(set(terms))  # no duplicates

    def test_expand_query_terms_excludes_input_nodes(self, store):
        terms = store.expand_query_terms(["快速决策"], depth=2)
        assert "快速决策" not in terms  # input nodes excluded from expansion
