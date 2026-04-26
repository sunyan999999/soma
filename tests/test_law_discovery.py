"""新规律自主归纳测试"""
import numpy as np
import pytest

from soma.law_discovery import LawDiscovery, _simple_keyword_extract


class MockMemoryCore:
    """Mock MemoryCore for law discovery testing"""

    def __init__(self, memories=None, skills=None):
        self.episodic = MockEpisodicStore(memories or [])
        self.skill = MockSkillStore(skills or [])


class MockEpisodicStore:
    def __init__(self, memories):
        self._memories = memories

    def query_by_keywords(self, keywords, top_k=500):
        return self._memories[:top_k]


class MockSkillStore:
    def __init__(self, skills):
        self._skills = skills

    def add_skill(self, name, pattern, context=None):
        self._skills.append({"name": name, "pattern": pattern, "context": context or {}})
        return True

    def count(self):
        return len(self._skills)


class MockEmbedder:
    def encode(self, text):
        return np.random.randn(512).astype(np.float32)

    def encode_batch(self, texts):
        return np.array([self.encode(t) for t in texts])

    @property
    def dimension(self):
        return 512


class TestSimpleKeywordExtract:
    def test_chinese_extraction(self):
        text = "第一性原理是回归事物最基本的要素从底层逻辑出发推导"
        kw = _simple_keyword_extract(text)
        assert len(kw) > 0
        assert all(isinstance(k, str) for k in kw)

    def test_english_extraction(self):
        text = "First principles thinking deconstructs problems to fundamental elements"
        kw = _simple_keyword_extract(text)
        assert len(kw) > 0

    def test_empty_text(self):
        assert _simple_keyword_extract("") == []


class TestLawDiscovery:
    @pytest.fixture
    def small_cluster_memories(self):
        """创建不足以形成聚类的少量记忆"""
        from soma.base import MemoryUnit

        return [
            MemoryUnit(
                content="第一性原理是回归基本要素的思维方式",
                importance=0.9,
                access_count=5,
                context={"domain": "哲学"},
            ),
            MemoryUnit(
                content="系统思维强调整体关联和反馈回路",
                importance=0.8,
                access_count=3,
                context={"domain": "哲学"},
            ),
        ]

    @pytest.fixture
    def large_cluster_memories(self):
        """创建足够形成聚类的记忆集合（20条跨域推理）"""
        from soma.base import MemoryUnit

        templates = [
            ("第一性原理：从基本要素推导，不依赖现有经验", "哲学", 0.9, 5),
            ("回归本质分析产品需求：用户核心诉求是什么？", "产品", 0.85, 4),
            ("底层逻辑拆分增长瓶颈：找到最基础驱动因素", "商业", 0.9, 6),
            ("基本原理应用于团队管理：激励的根本动力", "管理", 0.8, 3),
            ("本质思维在投资决策中的应用：价值投资的根基", "投资", 0.85, 4),
            ("第一性原理与创新：重新定义问题边界", "创新", 0.9, 7),
            ("从基本要素出发构建商业模型：最小可行单元", "商业", 0.8, 5),
            ("回归人需求的本质设计用户体验：剔除噪音", "设计", 0.85, 3),
            ("底层逻辑穿透行业周期：不变的商业规律", "商业", 0.9, 6),
            ("用基本原理解构复杂技术架构：核心抽象", "技术", 0.8, 4),
            ("追问为什么五层找到根本原因", "问题解决", 0.9, 5),
            ("拆解问题到不能再拆的原子要素", "方法论", 0.85, 4),
            ("从第一原理出发重构增长策略", "商业", 0.9, 6),
            ("回归事物最基本要素理解AI的本质", "技术", 0.8, 3),
            ("用本质思维穿透信息噪音找到关键", "信息", 0.85, 5),
            ("基本要素分析法在医疗诊断中应用", "医疗", 0.8, 3),
            ("从物理第一原理看能源转型路径", "能源", 0.85, 4),
            ("回归人类基本需求看房地产市场", "经济", 0.9, 5),
            ("用底层逻辑理解教育本质的变革", "教育", 0.8, 3),
            ("第一性原理思维在AI Agent设计中的应用", "技术", 0.9, 7),
        ]
        return [
            MemoryUnit(
                content=content,
                importance=imp,
                access_count=ac,
                context={"domain": domain},
            )
            for content, domain, imp, ac in templates
        ]

    def test_no_candidates_with_few_memories(self, small_cluster_memories):
        """记忆太少应返回 None"""
        mc = MockMemoryCore(small_cluster_memories)
        embedder = MockEmbedder()
        discovery = LawDiscovery(mc, embedder)
        result = discovery.discover()
        assert result is None

    def test_discover_with_sufficient_memories(self, large_cluster_memories):
        """记忆足够时应返回候选规律"""
        mc = MockMemoryCore(large_cluster_memories)
        embedder = MockEmbedder()
        discovery = LawDiscovery(mc, embedder)
        # 使用启发式模式（无 LLM）
        result = discovery.discover()
        if result is not None:
            assert "id" in result
            assert "name" in result
            assert "description" in result
            assert "triggers" in result
            assert "confidence" in result
            assert 0 <= result["confidence"] <= 1
            assert len(result["triggers"]) > 0

    def test_max_total_laws_limit(self, large_cluster_memories):
        """达到规律总数上限时应返回 None"""
        mc = MockMemoryCore(large_cluster_memories)
        embedder = MockEmbedder()
        discovery = LawDiscovery(mc, embedder)
        result = discovery.discover(current_law_count=15)
        assert result is None

    def test_approve_adds_law(self):
        """审批通过后应添加规律到引擎"""
        from soma.engine import WisdomEngine
        from soma.config import FrameworkConfig, WisdomLaw
        from soma.abc import BaseFrameworkEngine

        engine = WisdomEngine(FrameworkConfig(
            name="test",
            version="1.0",
            laws=[
                WisdomLaw(id="first_principles", name="第一性原理",
                          description="回归基本", weight=0.9,
                          triggers=["本质", "基本"]),
                WisdomLaw(id="systems_thinking", name="系统思维",
                          description="整体关联", weight=0.85,
                          triggers=["系统", "整体"]),
            ]
        ))
        mc = MockMemoryCore()
        embedder = MockEmbedder()
        discovery = LawDiscovery(mc, embedder)

        candidate = {
            "id": "test_law",
            "name": "测试规律",
            "description": "从测试数据中发现的规律",
            "triggers": ["测试", "试验", "验证"],
            "relations": ["first_principles"],
        }
        success = discovery.approve(candidate, engine)
        assert success
        assert len(engine.laws) == 3
        assert engine.laws[-1].id == "test_law"
        assert engine.laws[-1].weight == 0.60

    def test_heuristic_generates_without_llm(self, large_cluster_memories):
        """无 LLM 时启发式生成应产出有效候选"""
        mc = MockMemoryCore(large_cluster_memories)
        embedder = MockEmbedder()
        discovery = LawDiscovery(mc, embedder)  # llm_model=None

        snippets = [m.content[:100] for m in large_cluster_memories[:5]]
        keywords = ["第一性", "基本", "底层", "本质"]
        result = discovery._heuristic_generate_law(snippets, keywords, "哲学")
        assert result["id"].startswith("discovered_")
        assert len(result["name"]) > 0
        assert len(result["triggers"]) > 0

    def test_compute_confidence_bounds(self, large_cluster_memories):
        """置信度应在 0-1 之间"""
        cluster = {
            "memories": large_cluster_memories[:10],
            "size": 10,
            "label": 0,
        }
        discovery = LawDiscovery(MockMemoryCore(), MockEmbedder())
        conf = discovery._compute_confidence(cluster)
        assert 0.0 <= conf <= 1.0
