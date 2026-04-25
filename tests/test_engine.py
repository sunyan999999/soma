import pytest

from soma.config import WisdomLaw, FrameworkConfig, load_config
from soma.engine import WisdomEngine, _extract_keywords


def make_law(id_, name, description, weight, triggers, relations=None):
    return WisdomLaw(
        id=id_, name=name, description=description,
        weight=weight, triggers=triggers, relations=relations or [],
    )


@pytest.fixture
def sample_framework():
    return FrameworkConfig(
        name="测试框架",
        version="0.1.0",
        laws=[
            make_law("first_principles", "第一性原理", "回归底层逻辑", 0.9, ["为什么", "本质", "根源"]),
            make_law("systems_thinking", "系统思维", "整体关联分析", 0.85, ["系统", "关联", "整体"]),
            make_law("contradiction", "矛盾分析", "对立统一", 0.8, ["矛盾", "冲突", "对立"]),
            make_law("pareto", "二八法则", "聚焦关键少数", 0.75, ["重点", "核心", "关键"]),
            make_law("inversion", "逆向思考", "反方向思考", 0.7, ["反过来", "逆向", "反面"]),
        ],
    )


@pytest.fixture
def engine(sample_framework):
    return WisdomEngine(sample_framework)


class TestExtractKeywords:
    def test_chinese(self):
        # 中文无空格分词在 MVP 中返回整体作为单个 token
        # 这是已知限制，Alpha 阶段替换为更精确的分词
        kws = _extract_keywords("新产品 增长 停滞 怎么办")
        assert "新产品" in kws or "增长" in kws or "停滞" in kws

    def test_mixed(self):
        # 混合文本按空格和标点分词
        kws = _extract_keywords("AI 模型 优化 策略 有哪些")
        assert len(kws) >= 2

    def test_chinese_no_spaces(self):
        """中文无空格的连续文本，MVP 返回整体作为一个关键词 token"""
        kws = _extract_keywords("新产品增长停滞怎么办")
        # 整体作为一个 token 保留（已知限制，Alpha 阶段升级）
        assert len(kws) >= 1

    def test_stop_words_filtered(self):
        kws = _extract_keywords("我的系统有问题了")
        assert "我" not in kws
        assert "的" not in kws
        assert "了" not in kws
        assert "有" not in kws

    def test_max_keywords(self):
        kws = _extract_keywords("人工智能赋能企业数字化转型的战略路径研究与实践方法论探讨", max_keywords=5)
        assert len(kws) <= 5

    def test_deduplication(self):
        text = "增长 增长 增长"
        kws = _extract_keywords(text)
        assert len(kws) == 1
        assert kws[0] == "增长"


class TestWisdomEngine:
    def test_decompose_single_match(self, engine):
        foci = engine.decompose("为什么新产品增长停滞？")
        assert len(foci) >= 1
        assert foci[0].law_id == "first_principles"  # "为什么" 触发
        assert "为什么" in foci[0].rationale

    def test_decompose_multiple_matches(self, engine):
        foci = engine.decompose("系统架构的主要矛盾是什么？")
        law_ids = {f.law_id for f in foci}
        assert "contradiction" in law_ids  # "矛盾"
        assert "systems_thinking" in law_ids  # "系统"

    def test_decompose_sorted_by_weight(self, engine):
        foci = engine.decompose("系统的核心矛盾是什么？")
        # 匹配三条："系统" → systems_thinking(0.85), "核心" → pareto(0.75), "矛盾" → contradiction(0.8)
        # 排序后: systems_thinking(0.85) > contradiction(0.8) > pareto(0.75)
        assert foci[0].weight >= foci[1].weight >= foci[2].weight

    def test_decompose_fallback(self, engine):
        """无关键词匹配时返回最高权重规律"""
        foci = engine.decompose("今天天气很好")
        assert len(foci) == 1
        assert foci[0].law_id == "first_principles"  # 最高权重
        assert "无特定规律匹配" in foci[0].rationale

    def test_decompose_keywords(self, engine):
        foci = engine.decompose("为什么增长停滞")
        assert len(foci) >= 1
        focus = foci[0]
        assert len(focus.keywords) > 0
        # 应包含触发词和提取的关键词
        has_trigger = any(t in focus.keywords for t in ["为什么", "本质", "根源"])
        assert has_trigger

    def test_decompose_dimension(self, engine):
        foci = engine.decompose("系统矛盾如何解决")
        # 应有两个 Focus
        for f in foci:
            assert f.dimension  # 维度描述不为空
            assert f.law_id in {"systems_thinking", "contradiction"}

    def test_english_problem_fallback(self, engine):
        """英文问题（中文触发词不匹配时应使用兜底策略）"""
        foci = engine.decompose("Why is the system broken?")
        # 无中文触发词匹配，应兜底
        assert len(foci) == 1
        assert foci[0].law_id == "first_principles"
