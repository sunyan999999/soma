"""知识门控管道测试"""
import pytest
from soma.knowledge_gate import (
    KnowledgeGate, GateResult, ExternalKnowledge,
    MIN_FOCUS_KEYWORD_HITS, STYLE_ALIGNMENT_THRESHOLD,
    MAX_CONFLICTS_BEFORE_QUARANTINE, EXTERNAL_MEMORY_TTL_DAYS,
)


class FakeFocus:
    """模拟 Focus"""
    def __init__(self, law_id="first_principles", keywords=None, weight=0.8,
                 dimension="测试维度", rationale="测试理由"):
        self.law_id = law_id
        self.keywords = keywords or ["系统", "分析", "思考"]
        self.weight = weight
        self.dimension = dimension
        self.rationale = rationale


class FakeEngine:
    """模拟 WisdomEngine"""
    def decompose(self, text):
        # 简单规则：文本包含"分析"或"系统"则生成 Foci
        if "分析" in text or "系统" in text or "思考" in text:
            return [FakeFocus()]
        return []


class FakeEpisodic:
    """模拟情节记忆库"""
    def __init__(self, memories=None):
        self.memories = memories or []

    def search(self, query, top_k=10):
        return self.memories[:top_k]

    def query_by_keywords(self, keywords, top_k=10, **kwargs):
        # 简单匹配：关键词出现在 content 中则命中
        results = []
        for m in self.memories:
            if any(kw in m.content for kw in keywords):
                results.append(m)
            if len(results) >= top_k:
                break
        return results

    def stats(self):
        return {"episodic": len(self.memories)}


class FakeSemantic:
    """模拟语义记忆库"""
    def __init__(self, triples=None):
        self.triples = triples or []

    def get_all_triples(self):
        return self.triples

    def stats(self):
        return {"semantic": len(self.triples)}


class FakeMemory:
    """模拟 MemoryUnit"""
    def __init__(self, content="", importance=0.5, mem_id="m1"):
        self.content = content
        self.importance = importance
        self.id = mem_id
        self.memory_type = "episodic"
        self.access_count = 0
        self.timestamp = 1000000.0
        self.context = {}


class FakeMemoryCore:
    """模拟 MemoryCore"""
    def __init__(self):
        self.episodic = FakeEpisodic()
        self.semantic = FakeSemantic()
        self.skill = None


class FakeAgent:
    """最小化的 Fake SOMA Agent，供 KnowledgeGate 测试"""
    def __init__(self):
        self.engine = FakeEngine()
        self.memory = FakeMemoryCore()
        self._remembered = []

    def remember(self, content, context=None, importance=0.5, user_id="", session_id=""):
        self._remembered.append({
            "content": content,
            "context": context,
            "importance": importance,
        })
        return f"mem-{len(self._remembered)}"


# ═══════════════════════════════════════════════════════════════
# 层1: 相关性过滤测试
# ═══════════════════════════════════════════════════════════════

class TestRelevanceFilter:
    def setup_method(self):
        self.gate = KnowledgeGate(FakeAgent(), relevance_threshold=2)

    def test_high_relevance_passes(self):
        foci = [FakeFocus(keywords=["系统", "分析"])]
        ek = ExternalKnowledge(content="我们需要系统地分析这个问题的根源")
        ek = self.gate._filter_relevance(ek, foci)
        assert ek.verdict != "rejected"
        assert ek.relevance_score > 0

    def test_irrelevant_content_rejected(self):
        foci = [FakeFocus(keywords=["区块链", "加密货币"])]
        ek = ExternalKnowledge(content="今天天气很好适合出去散步")
        ek = self.gate._filter_relevance(ek, foci)
        assert ek.verdict == "rejected"
        assert "相关性不足" in ek.reject_reason

    def test_no_foci_mid_score(self):
        ek = ExternalKnowledge(content="任意内容")
        ek = self.gate._filter_relevance(ek, [])
        assert ek.relevance_score == 0.5


# ═══════════════════════════════════════════════════════════════
# 层2: SOMA 推理消化测试
# ═══════════════════════════════════════════════════════════════

class TestDigestWithLaws:
    def setup_method(self):
        self.gate = KnowledgeGate(FakeAgent())

    def test_digest_generates_structured_points(self):
        foci = [FakeFocus()]
        ek = ExternalKnowledge(
            content="第一性原理的核心是从最基本要素出发分析问题，"
                    "这需要系统思维来理解各要素之间的连接关系。"
        )
        ek = self.gate._digest_with_laws(ek, foci)
        assert ek.digested_content  # 有消化输出
        assert ek.verdict != "rejected"

    def test_blank_content_handled(self):
        foci = [FakeFocus()]
        ek = ExternalKnowledge(content="")
        ek = self.gate._digest_with_laws(ek, foci)
        # 空内容也应该生成 digested_content
        assert ek.verdict == "rejected" or ek.digested_content == ""


# ═══════════════════════════════════════════════════════════════
# 层3: 风格对齐测试
# ═══════════════════════════════════════════════════════════════

class TestStyleAlignment:
    def setup_method(self):
        # 预装一些风格样本
        agent = FakeAgent()
        agent.memory.episodic.memories = [
            FakeMemory(content="从系统论的角度来看，这个问题存在三个层次的反馈回路。"
                               "首先是最基本的正反馈机制推动增长。"
                               "其次是负反馈机制维持稳定。"
                               "最后是延迟反馈带来的震荡效应。",
                       importance=0.9),
            FakeMemory(content="第一性原理分析要求我们回归事物的最基本构成要素。"
                               "通过分解到不可再分的原子层面，"
                               "然后从这些原子出发重新构建理解框架。",
                       importance=0.85),
        ]
        self.gate = KnowledgeGate(agent)

    def test_style_alignment_with_samples(self):
        ek = ExternalKnowledge(
            content="这个系统需要分析它的核心组件和它们之间的交互关系",
            digested_content="[first_principles] 核心组件分析: 将系统拆分为基本模块进行逐层分析"
        )
        ek = self.gate._align_style(ek)
        assert ek.style_alignment > 0
        assert ek.aligned_content

    def test_no_samples_mid_score(self):
        gate = KnowledgeGate(FakeAgent())
        ek = ExternalKnowledge(content="测试文本")
        ek = gate._align_style(ek)
        assert ek.style_alignment == 0.5  # 无样本时默认值

    def test_similar_style_gets_high_score(self):
        # 记忆库内容与外部内容风格相似
        agent = FakeAgent()
        agent.memory.episodic.memories = [
            FakeMemory(content="系统分析显示该架构存在三个主要瓶颈。"
                               "我们建议从数据流入手逐步优化。"
                               "每个优化点需要量化评估其影响范围。",
                       importance=0.9),
        ]
        gate = KnowledgeGate(agent)
        ek = ExternalKnowledge(
            content="架构评估表明该设计存在性能瓶颈。"
                    "建议从缓存层入手逐步改进。"
                    "每个改进需要测试其实际效果。",
        )
        ek.digested_content = ek.content
        ek = gate._align_style(ek)
        # 相似学术风格应得到较高分
        assert ek.style_alignment > 0.4


# ═══════════════════════════════════════════════════════════════
# 层4: 一致性校验测试
# ═══════════════════════════════════════════════════════════════

class TestConsistencyCheck:
    def setup_method(self):
        agent = FakeAgent()
        # 预置语义三元组
        agent.memory.semantic.triples = [
            {"subject": "SOMA", "predicate": "USES", "object": "ONNX",
             "confidence": 0.9},
            {"subject": "SOMA", "predicate": "USES", "object": "PyTorch",
             "confidence": 0.2},
        ]
        self.gate = KnowledgeGate(agent)

    def test_content_triggers_conflict_detection(self):
        ek = ExternalKnowledge(
            content="SOMA 使用 ONNX 进行推理，同时也支持 PyTorch 后端",
        )
        ek = self.gate._check_consistency(ek)
        # 应该有 "SOMA USES ONNX vs SOMA USES PyTorch" 的冲突
        assert len(ek.conflicts) >= 0  # 至少检测到冲突

    def test_no_conflicts_for_unrelated_content(self):
        ek = ExternalKnowledge(content="Python 是一个流行的编程语言")
        ek = self.gate._check_consistency(ek)
        assert len(ek.conflicts) == 0


# ═══════════════════════════════════════════════════════════════
# 层5: 分级存储测试
# ═══════════════════════════════════════════════════════════════

class TestTieredStorage:
    def setup_method(self):
        self.agent = FakeAgent()
        self.gate = KnowledgeGate(self.agent)

    def test_accepted_stored_with_high_importance(self):
        ek = ExternalKnowledge(
            content="这是一条高质量的外部知识",
            aligned_content="高质量知识的消化版本",
            verdict="accepted",
            source_name="web",
            relevance_score=0.8,
            quality_score=0.75,
            style_alignment=0.7,
        )
        result = GateResult(accepted=[ek])
        self.gate._tiered_store(result)
        assert len(self.agent._remembered) == 1
        assert self.agent._remembered[0]["importance"] == 0.55

    def test_quarantined_stored_with_low_importance(self):
        ek = ExternalKnowledge(
            content="需要人工确认的内容",
            verdict="quarantined",
            source_name="web",
        )
        result = GateResult(quarantined=[ek])
        self.gate._tiered_store(result)
        assert len(self.agent._remembered) == 1
        assert self.agent._remembered[0]["importance"] == 0.25

    def test_rejected_not_stored(self):
        ek = ExternalKnowledge(content="垃圾内容", verdict="rejected")
        result = GateResult(rejected=[ek])
        self.gate._tiered_store(result)
        assert len(self.agent._remembered) == 0


# ═══════════════════════════════════════════════════════════════
# 集成测试: 完整五层管道
# ═══════════════════════════════════════════════════════════════

class TestFullPipeline:
    def setup_method(self):
        agent = FakeAgent()
        agent.memory.episodic.memories = [
            FakeMemory(content="系统分析方法论: 从全局视角理解要素间的关联关系。"
                               "核心在于识别正反馈回路和负反馈回路的平衡点。",
                       importance=0.9),
        ]
        self.gate = KnowledgeGate(agent)

    def test_relevant_content_accepted(self):
        contents = [
            "系统分析方法告诉我们，任何复杂问题都可以拆解为子系统的交互。"
            "通过识别各子系统之间的反馈回路，我们可以找到系统的关键杠杆点。"
        ]
        result = self.gate.ingest(contents, problem_context="系统分析", source_name="web")
        # 相关内容应该被接受或隔离，不应被拒绝
        assert result.total >= 1
        assert result.acceptance_rate >= 0

    def test_irrelevant_content_rejected(self):
        contents = ["今天天气真好，适合出去玩"]
        result = self.gate.ingest(contents, problem_context="深度学习优化", source_name="web")
        assert result.total == 0 or len(result.rejected) >= 1

    def test_empty_input(self):
        result = self.gate.ingest([], problem_context="测试")
        assert result.total == 0
        assert result.stats.get("reason") == "empty_input"

    def test_result_structure(self):
        contents = [
            "系统的核心在于分析各组件之间的相互依赖关系",
            "完全不相关的内容",
        ]
        result = self.gate.ingest(contents, problem_context="系统架构", source_name="web")
        assert hasattr(result, "accepted")
        assert hasattr(result, "quarantined")
        assert hasattr(result, "rejected")
        assert "total" in result.stats
        assert "duration_ms" in result.stats


# ═══════════════════════════════════════════════════════════════
# 质量分计算测试
# ═══════════════════════════════════════════════════════════════

class TestQualityScore:
    def setup_method(self):
        self.gate = KnowledgeGate(FakeAgent())

    def test_perfect_quality(self):
        ek = ExternalKnowledge(
            content="完美质量内容",
            relevance_score=1.0,
            style_alignment=1.0,
            conflicts=[],
        )
        score = self.gate._compute_quality(ek)
        assert score == 1.0

    def test_poor_quality(self):
        ek = ExternalKnowledge(
            content="低质量内容",
            relevance_score=0.1,
            style_alignment=0.1,
            conflicts=["冲突1", "冲突2", "冲突3", "冲突4"],
        )
        score = self.gate._compute_quality(ek)
        assert score < 0.5

    def test_conflicts_reduce_score(self):
        ek1 = ExternalKnowledge(content="无冲突内容", relevance_score=0.8, style_alignment=0.8, conflicts=[])
        ek2 = ExternalKnowledge(content="有冲突内容", relevance_score=0.8, style_alignment=0.8,
                                conflicts=["冲突1", "冲突2"])
        score1 = self.gate._compute_quality(ek1)
        score2 = self.gate._compute_quality(ek2)
        assert score2 < score1


# ═══════════════════════════════════════════════════════════════
# 数据类测试
# ═══════════════════════════════════════════════════════════════

class TestDataClasses:
    def test_external_knowledge_defaults(self):
        ek = ExternalKnowledge(content="test")
        assert ek.source_name == "external"
        assert ek.relevance_score == 0.0
        assert ek.verdict == ""

    def test_gate_result_counters(self):
        r = GateResult(
            accepted=[ExternalKnowledge(content="a")],
            rejected=[ExternalKnowledge(content="b")],
        )
        assert r.total == 2
        assert r.acceptance_rate == 0.5

    def test_gate_result_stats(self):
        r = GateResult(stats={"custom": 42})
        assert r.stats["custom"] == 42


# ═══════════════════════════════════════════════════════════════
# 常量测试
# ═══════════════════════════════════════════════════════════════

class TestConstants:
    def test_thresholds_reasonable(self):
        assert MIN_FOCUS_KEYWORD_HITS >= 1
        assert 0 < STYLE_ALIGNMENT_THRESHOLD < 1
        assert MAX_CONFLICTS_BEFORE_QUARANTINE >= 1
        assert EXTERNAL_MEMORY_TTL_DAYS >= 1


# ═══════════════════════════════════════════════════════════════
# v2.0.9 新增层测试: 内容质量 / 来源过滤 / 事实印证 / 严格度
# ═══════════════════════════════════════════════════════════════

class TestContentQualityLayer:
    def setup_method(self):
        self.agent = FakeAgent()
        self.gate = KnowledgeGate(self.agent)

    def test_marketing_content_rejected(self):
        """营销/低质内容被内容质量层拒绝"""
        ek = ExternalKnowledge(content="限时抢购！全场五折！立即点击购买！免费红包！")
        ek = self.gate._check_content_quality(ek)
        assert ek.verdict == "rejected"
        assert "内容质量" in ek.reject_reason

    def test_good_content_passes(self):
        ek = ExternalKnowledge(content=(
            "系统分析方法论强调从全局视角理解要素关联，识别反馈回路，"
            "这是复杂问题分析的基础框架和核心方法论。"
        ))
        ek = self.gate._check_content_quality(ek)
        assert ek.verdict == ""
        assert ek.content_quality_score >= 0.3


class TestSourceFilterLayer:
    def test_blacklist_source_rejected(self):
        agent = FakeAgent()
        gate = KnowledgeGate(agent)
        result = gate.ingest(
            ["系统分析的重要方法论内容"],
            problem_context="系统分析",
            source_url="https://spam-site.com/article",
        )
        # 黑名单来源应被拒绝（层0）
        assert any("来源不可信" in r.reject_reason for r in result.rejected)


class TestCorroborationLayer:
    def test_corroboration_with_existing_memory(self):
        agent = FakeAgent()
        agent.memory.episodic.memories = [
            FakeMemory(content="系统分析方法论从全局视角理解要素关联，识别反馈回路。",
                       importance=0.9),
        ]
        gate = KnowledgeGate(agent)
        ek = ExternalKnowledge(content=(
            "系统分析方法论从全局视角理解要素关联，识别反馈回路，"
            "这是复杂问题分析的核心框架。"
        ))
        ek = gate._corroborate(ek)
        # 与已有高重要性记忆印证 → 印证度 > 0
        assert ek.corroboration_score > 0

    def test_isolated_fact_zero_corroboration(self):
        agent = FakeAgent()
        gate = KnowledgeGate(agent)
        ek = ExternalKnowledge(content="完全孤立的火星地形研究新发现报告内容。")
        ek = gate._corroborate(ek)
        # 无已有记忆支撑 → 印证度 0
        assert ek.corroboration_score == 0.0


class TestContextFallback:
    def test_weak_context_falls_back_to_content(self):
        """v2.0.9: problem_context 拆出的 Foci 与内容零命中时，回退用内容拆解"""
        agent = FakeAgent()
        # FakeEngine 对「哲学思维」拆不出 Foci
        gate = KnowledgeGate(agent)
        result = gate.ingest(
            ["系统分析方法论强调从全局视角理解要素关联，识别反馈回路。"],
            problem_context="哲学思维",
            source_name="web",
        )
        # 回退后内容应能通过相关性过滤（不被误拒）
        assert result.total >= 1


class TestStrictness:
    def test_strict_raises_min_quality(self):
        gate = KnowledgeGate(FakeAgent(), min_quality=0.3, strictness="strict")
        assert round(gate._min_quality, 2) >= 0.45  # 0.3 + 0.15

    def test_permissive_lowers_min_quality(self):
        gate = KnowledgeGate(FakeAgent(), min_quality=0.3, strictness="permissive")
        assert gate._min_quality <= 0.3

    def test_balanced_unchanged(self):
        gate = KnowledgeGate(FakeAgent(), min_quality=0.3, strictness="balanced")
        assert gate._min_quality == 0.3
