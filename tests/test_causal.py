"""v0.8.0 任务1: 因果推理链测试"""
import pytest
from pathlib import Path
from soma.memory.semantic import SemanticStore
from soma.memory.causal import CausalGraph


@pytest.fixture
def store(tmp_path: Path):
    s = SemanticStore(tmp_path)
    # 构建因果链: 价格高 → 客户流失 → 收入下降 → 裁员
    s.add_triple("价格高", "causes", "客户流失")
    s.add_triple("客户流失", "leads_to", "收入下降")
    s.add_triple("收入下降", "causes", "裁员")
    # 分叉因果: 服务质量差 + 价格高 → 客户流失
    s.add_triple("服务质量差", "causes", "客户流失")
    # 抑制关系
    s.add_triple("优质服务", "prevents", "客户流失")
    # 非因果边（不应出现在因果图中）
    s.add_triple("客户流失", "关联", "用户满意度")
    return s


@pytest.fixture
def causal(store):
    return CausalGraph(store)


class TestCausalGraph:
    def test_is_causal_predicate(self, causal):
        assert causal.is_causal_predicate("causes") is True
        assert causal.is_causal_predicate("leads_to") is True
        assert causal.is_causal_predicate("prevents") is True
        assert causal.is_causal_predicate("increases") is True
        assert causal.is_causal_predicate("decreases") is True
        assert causal.is_causal_predicate("关联") is False
        assert causal.is_causal_predicate("depends_on") is False

    def test_find_root_causes_simple(self, causal):
        roots = causal.find_root_causes("裁员")
        assert "价格高" in roots
        assert "服务质量差" in roots

    def test_find_root_causes_leaf(self, causal):
        roots = causal.find_root_causes("价格高")
        assert roots == ["价格高"]  # 无因果前驱，自己就是根因

    def test_find_effects_chain(self, causal):
        effects = causal.find_effects("价格高", depth=3)
        assert "客户流失" in effects
        assert "收入下降" in effects
        assert "裁员" in effects

    def test_find_effects_limit_depth(self, causal):
        effects = causal.find_effects("价格高", depth=1)
        assert "客户流失" in effects
        assert "收入下降" not in effects  # 2跳，被深度限制

    def test_causal_chain_path(self, causal):
        chain = causal.get_causal_chain("价格高", "裁员")
        assert chain is not None
        assert len(chain) >= 4
        assert chain[0] == "价格高"
        assert chain[-1] == "裁员"

    def test_causal_chain_no_path(self, causal):
        chain = causal.get_causal_chain("服务质量差", "优质服务")
        assert chain is None

    def test_detect_cycle(self, causal):
        # 添加环路: 裁员 → 服务质量差(因为人手不足)
        causal.store.add_triple("裁员", "causes", "服务质量差")
        cycles = causal.detect_cycles()
        assert len(cycles) >= 1
        # 环路: 服务质量差→客户流失→收入下降→裁员→服务质量差
        found = any("服务质量差" in c and "裁员" in c for c in cycles)
        assert found

    def test_empty_graph(self, tmp_path):
        empty_store = SemanticStore(tmp_path / "empty")
        cg = CausalGraph(empty_store)
        assert cg.find_root_causes("anything") == []
        assert cg.find_effects("anything") == []
        assert cg.detect_cycles() == []

    def test_filter_causal_edges(self, causal):
        edges = causal.get_causal_edges()
        # 应包含所有因果边（5条），不包含非因果的"关联"边
        assert len(edges) >= 5
        predicates = {e["predicate"] for e in edges}
        assert "causes" in predicates or "leads_to" in predicates or "prevents" in predicates
        assert "关联" not in predicates

    def test_prevention_path(self, causal):
        """prevents 边在因果分析中被视为负向因果"""
        effects = causal.find_effects("优质服务", depth=2)
        assert "客户流失" in effects
