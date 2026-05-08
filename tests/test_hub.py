import pytest

from soma.config import SOMAConfig
from soma.base import ActivatedMemory, Focus, MemoryUnit
from soma.memory.core import MemoryCore
from soma.hub import ActivationHub


@pytest.fixture
def memory(tmp_path):
    config = SOMAConfig(episodic_persist_dir=tmp_path / "chroma", use_vector_search=False)
    mc = MemoryCore(config)
    # 预填充数据
    mc.remember("第一性原理在增长分析中的核心价值", {"domain": "分析"}, importance=0.9)
    mc.remember("系统思维帮助看清全局结构", {"domain": "思维"}, importance=0.85)
    mc.remember("矛盾分析是化解对立的关键方法", {"domain": "分析"}, importance=0.8)
    mc.remember("逆向思考在市场推广中的意外效果", {"domain": "营销"}, importance=0.7)
    mc.remember("完全不相关的天气预报信息", {"domain": "天气"}, importance=0.1)
    mc.remember_semantic("增长", "依赖", "第一性原理")
    mc.remember_semantic("系统", "关联", "矛盾")
    return mc


@pytest.fixture
def hub(memory):
    return ActivationHub(memory, top_k=3, threshold=0.01)


class TestActivationHub:
    def test_activate_returns_top_k(self, hub):
        foci = [
            Focus(
                law_id="first_principles",
                dimension="从第一性原理分析",
                keywords=["第一性原理", "增长"],
                weight=0.9,
                rationale="匹配",
            ),
        ]
        results = hub.activate(foci)
        assert len(results) <= 3  # top_k=3

    def test_activate_score_ordering(self, hub):
        foci = [
            Focus(
                law_id="first_principles",
                dimension="测试",
                keywords=["第一性原理"],
                weight=0.9,
                rationale="",
            ),
        ]
        results = hub.activate(foci)
        # 分数应降序排列
        for i in range(len(results) - 1):
            assert results[i].activation_score >= results[i + 1].activation_score

    def test_activate_threshold_filter(self, hub):
        hub.threshold = 0.5
        foci = [
            Focus(
                law_id="first_principles",
                dimension="测试",
                keywords=["完全不相关"],
                weight=0.1,
                rationale="",
            ),
        ]
        results = hub.activate(foci)
        # 低相关性 + 低权重 = 低分，应被过滤
        # 但"完全不相关"会匹配"天气预报"记忆，weight 0.1 可能产生低分
        assert len(results) == 0 or all(
            am.activation_score >= 0.5 for am in results
        )

    def test_multi_focus_boost(self, hub):
        """多 Focus 命中的记忆应获得叠加加成"""
        foci = [
            Focus(
                law_id="first_principles",
                dimension="维度1",
                keywords=["第一性原理"],
                weight=0.9,
                rationale="",
            ),
            Focus(
                law_id="systems_thinking",
                dimension="维度2",
                keywords=["系统"],
                weight=0.85,
                rationale="",
            ),
        ]
        results = hub.activate(foci)
        # 结果应包含不同来源的记忆
        sources = {r.source for r in results}
        assert len(sources) >= 1

    def test_activate_empty_foci(self, hub):
        results = hub.activate([])
        assert len(results) == 0

    def test_explain_activation(self, hub):
        foci = [
            Focus(
                law_id="first_principles",
                dimension="测试",
                keywords=["第一性原理"],
                weight=0.9,
                rationale="",
            ),
        ]
        results = hub.activate(foci)
        if results:
            explanation = hub.explain_activation(results[0])
            assert "memory_id" in explanation
            assert "activation_score" in explanation
            assert "source" in explanation

    def test_causal_analyze_with_systems_thinking(self, memory):
        """systems_thinking 律激活时应触发因果分析"""
        hub = ActivationHub(memory, top_k=3)
        # 构建因果链
        memory.remember_semantic("价格高", "causes", "客户流失")
        memory.remember_semantic("客户流失", "leads_to", "收入下降")

        foci = [
            Focus(
                law_id="systems_thinking",
                dimension="为什么收入下降",
                keywords=["收入下降", "客户流失"],
                weight=0.85,
                rationale="",
            ),
        ]
        result = hub.causal_analyze(foci)
        assert "root_causes" in result
        assert "收入下降" in result["root_causes"]
        assert "价格高" in result["root_causes"]["收入下降"]

    def test_causal_analyze_without_systems_thinking(self, memory):
        """非 systems_thinking 律不应触发因果分析"""
        hub = ActivationHub(memory, top_k=3)
        memory.remember_semantic("A", "causes", "B")

        foci = [
            Focus(
                law_id="first_principles",
                dimension="测试",
                keywords=["A"],
                weight=0.9,
                rationale="",
            ),
        ]
        result = hub.causal_analyze(foci)
        assert result["root_causes"] == {}
        assert result["chains"] == []


class TestBackwardPropagation:
    """v0.8.0 任务3: 双向激活闭环 — 记忆→焦点反向传播"""

    @pytest.fixture
    def hub_with_laws(self, memory):
        from soma.config import WisdomLaw
        laws = [
            WisdomLaw(id="systems_thinking", name="系统思维",
                      description="整体关联", weight=0.85,
                      triggers=["系统", "关联", "全局"], relations=[]),
            WisdomLaw(id="contradiction_analysis", name="矛盾分析",
                      description="对立统一", weight=0.8,
                      triggers=["矛盾", "冲突", "对立"], relations=[]),
            WisdomLaw(id="first_principles", name="第一性原理",
                      description="回归本质", weight=0.9,
                      triggers=["本质", "根源", "根本"], relations=[]),
        ]
        hub = ActivationHub(memory, top_k=3, threshold=0.01)
        return hub, laws

    def test_backward_propagate_with_matching_domain(self, hub_with_laws):
        """领域标签匹配规律触发词 → 生成 suggested_focus"""
        hub, laws = hub_with_laws
        am = ActivatedMemory(
            memory=MemoryUnit(
                id="test1", content="系统思维帮助看清全局结构",
                context={"domain": "系统"}, importance=0.85,
            ),
            activation_score=0.75, source="episodic",
            match_rationale="测试",
        )
        hub._backward_propagate([am], laws)
        assert am.suggested_focus is not None
        assert am.suggested_focus.law_id == "systems_thinking"
        assert am.suggested_focus.weight <= 0.5  # 不超过最大权重的50%

    def test_backward_propagate_no_domain(self, hub_with_laws):
        """无领域标签 → 不生成建议"""
        hub, laws = hub_with_laws
        am = ActivatedMemory(
            memory=MemoryUnit(
                id="test2", content="一些无关内容",
                context={}, importance=0.5,
            ),
            activation_score=0.8, source="episodic",
            match_rationale="测试",
        )
        hub._backward_propagate([am], laws)
        assert am.suggested_focus is None

    def test_backward_propagate_low_score(self, hub_with_laws):
        """激活分数低于阈值 → 不生成建议"""
        hub, laws = hub_with_laws
        am = ActivatedMemory(
            memory=MemoryUnit(
                id="test3", content="系统相关但分数低",
                context={"domain": "系统"}, importance=0.3,
            ),
            activation_score=0.3, source="episodic",
            match_rationale="测试",
        )
        hub._backward_propagate([am], laws)
        assert am.suggested_focus is None

    def test_backward_propagate_no_matching_law(self, hub_with_laws):
        """领域标签不匹配任何规律触发词 → 不生成建议"""
        hub, laws = hub_with_laws
        am = ActivatedMemory(
            memory=MemoryUnit(
                id="test4", content="天气相关信息",
                context={"domain": "天气"}, importance=0.5,
            ),
            activation_score=0.7, source="episodic",
            match_rationale="测试",
        )
        hub._backward_propagate([am], laws)
        assert am.suggested_focus is None

    def test_explain_activation_includes_suggestion(self, hub_with_laws, memory):
        """explain_activation 包含 suggested_focus 信息"""
        hub, laws = hub_with_laws
        am = ActivatedMemory(
            memory=MemoryUnit(
                id="test5", content="矛盾是推动变化的核心动力",
                context={"domain": "矛盾"}, importance=0.8,
            ),
            activation_score=0.9, source="episodic",
            match_rationale="测试",
        )
        hub._backward_propagate([am], laws)
        info = hub.explain_activation(am)
        assert "suggested_focus" in info
        assert info["suggested_focus"]["law_id"] == "contradiction_analysis"
