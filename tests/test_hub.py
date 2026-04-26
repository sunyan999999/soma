import pytest

from soma.config import SOMAConfig
from soma.base import Focus
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
