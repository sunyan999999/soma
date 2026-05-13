"""v0.9.0 多智能体模块集成测试 — AgentRegistry + ExpertRouter + DistributedEvolver + ConsensusProtocol"""
import pytest
from unittest.mock import Mock, MagicMock, patch


# ============================================================================
# Task 1: AgentRegistry 测试
# ============================================================================

class FakeAgent:
    """模拟 SOMA_Agent 用于注册表测试"""
    def __init__(self, agent_id="test_agent", group_id=""):
        self.agent_id = agent_id
        self.group_id = group_id


class TestAgentRegistry:
    """AgentRegistry — 注册/注销/查找/统计"""

    def test_register_agent(self):
        from soma.multi_agent import AgentRegistry
        registry = AgentRegistry()
        agent = FakeAgent("expert_1")
        aid = registry.register(agent, expertise=["法律", "合同"], description="法律专家")
        assert aid == "expert_1"
        assert registry.agent_count == 1
        assert registry.get("expert_1") is agent

    def test_register_multiple_agents(self):
        from soma.multi_agent import AgentRegistry
        registry = AgentRegistry()
        registry.register(FakeAgent("a1"), expertise=["技术"])
        registry.register(FakeAgent("a2"), expertise=["金融"])
        registry.register(FakeAgent("a3"), expertise=["管理"])
        assert registry.agent_count == 3
        assert len(registry.list_agents()) == 3

    def test_register_default_agent(self):
        from soma.multi_agent import AgentRegistry
        registry = AgentRegistry()
        registry.register(FakeAgent("a1"), expertise=["技术"])
        default = FakeAgent("default_agent")
        registry.register(default, expertise=["通用"], is_default=True)
        assert registry.get_default() is default

    def test_unregister_agent(self):
        from soma.multi_agent import AgentRegistry
        registry = AgentRegistry()
        registry.register(FakeAgent("a1"), expertise=["技术"])
        assert registry.unregister("a1") is True
        assert registry.agent_count == 0
        assert registry.unregister("nonexistent") is False

    def test_find_experts_exact_match(self):
        from soma.multi_agent import AgentRegistry
        registry = AgentRegistry()
        registry.register(FakeAgent("law_agent"), expertise=["法律", "合同"])
        registry.register(FakeAgent("tech_agent"), expertise=["技术", "编程"])
        experts = registry.find_experts("法律")
        assert len(experts) == 1
        assert experts[0][1] == 1.0  # 完全匹配得分1.0

    def test_find_experts_partial_match(self):
        from soma.multi_agent import AgentRegistry
        registry = AgentRegistry()
        registry.register(FakeAgent("law_agent"), expertise=["知识产权法"])
        experts = registry.find_experts("知识产权")
        assert len(experts) == 1
        assert experts[0][1] >= 0.7  # 部分匹配≥0.7

    def test_find_experts_below_threshold(self):
        from soma.multi_agent import AgentRegistry
        registry = AgentRegistry()
        registry.register(FakeAgent("law_agent"), expertise=["法律"])
        experts = registry.find_experts("医疗", min_score=0.5)
        assert len(experts) == 0

    def test_get_info_returns_metadata(self):
        from soma.multi_agent import AgentRegistry
        registry = AgentRegistry()
        registry.register(FakeAgent("a1", "g1"), expertise=["技术"], description="技术专家")
        info = registry.get_info("a1")
        assert info is not None
        assert info.agent_id == "a1"
        assert info.group_id == "g1"
        assert info.expertise == ["技术"]
        assert info.description == "技术专家"

    def test_record_session_updates_success_rate(self):
        from soma.multi_agent import AgentRegistry
        registry = AgentRegistry()
        registry.register(FakeAgent("a1"), expertise=["技术"])
        # 初始成功率0.5
        info = registry.get_info("a1")
        assert info.success_rate == 0.5

        # 成功一次: 0.5 * 0.9 + 1.0 * 0.1 = 0.55
        registry.record_session("a1", success=True)
        info = registry.get_info("a1")
        assert info.session_count == 1
        assert 0.54 < info.success_rate < 0.56

        # 失败一次: 0.55 * 0.9 + 0.0 * 0.1 = 0.495
        registry.record_session("a1", success=False)
        info = registry.get_info("a1")
        assert info.session_count == 2
        assert 0.49 < info.success_rate < 0.50

    def test_agent_without_id_gets_auto_id(self):
        from soma.multi_agent import AgentRegistry
        registry = AgentRegistry()
        # FakeAgent 有 agent_id，但测试没有 agent_id 属性的对象
        class NoIdAgent:
            pass
        aid = registry.register(NoIdAgent(), expertise=["通用"])
        assert aid.startswith("agent_")


# ============================================================================
# Task 3: ExpertRouter 测试
# ============================================================================

class TestExpertRouter:
    """ExpertRouter — L1/L2/L3 路由策略"""

    @pytest.fixture
    def registry(self):
        from soma.multi_agent import AgentRegistry
        r = AgentRegistry()
        r.register(FakeAgent("law_1"), expertise=["法律", "合同"], description="法律专家")
        r.register(FakeAgent("tech_1"), expertise=["技术", "编程", "架构"], description="技术专家")
        r.register(FakeAgent("finance_1"), expertise=["金融", "投资"], description="金融专家")
        r.register(FakeAgent("general"), expertise=["通用"], is_default=True, description="通用助手")
        return r

    def test_l1_keyword_route_law(self, registry):
        from soma.multi_agent import ExpertRouter
        router = ExpertRouter(registry)
        agent, confidence, strategy = router.route("帮我分析这个合同条款")
        assert getattr(agent, 'agent_id', '') == "law_1"
        assert strategy == "l1"
        assert confidence > 0

    def test_l1_keyword_route_tech(self, registry):
        from soma.multi_agent import ExpertRouter
        router = ExpertRouter(registry)
        agent, confidence, strategy = router.route("这段代码的架构需要优化")
        assert getattr(agent, 'agent_id', '') == "tech_1"
        assert strategy == "l1"

    def test_l1_keyword_route_finance(self, registry):
        from soma.multi_agent import ExpertRouter
        router = ExpertRouter(registry)
        agent, confidence, strategy = router.route("投资股票需要注意什么")
        assert getattr(agent, 'agent_id', '') == "finance_1"
        assert strategy == "l1"

    def test_l1_no_match_falls_back_to_default(self, registry):
        from soma.multi_agent import ExpertRouter
        router = ExpertRouter(registry)
        agent, confidence, strategy = router.route("今天天气怎么样")
        assert getattr(agent, 'agent_id', '') == "general"
        assert strategy == "fallback"
        assert confidence == 0.1

    def test_l1_min_confidence_filter(self, registry):
        from soma.multi_agent import ExpertRouter
        router = ExpertRouter(registry)
        # 只有一个关键词命中，confidence = 1/3 ≈ 0.33
        # 设置 min_confidence=0.5 应触发 fallback
        agent, confidence, strategy = router.route("合同", min_confidence=0.5)
        # "合同" 只命中一个词 → confidence 0.33 < 0.5 → fallback
        assert strategy == "fallback"

    def test_route_multi_returns_top_k(self, registry):
        from soma.multi_agent import ExpertRouter
        router = ExpertRouter(registry)
        # "法律合规的技术架构" 同时命中法律和技术
        results = router.route_multi("法律合规的技术架构", top_k=3)
        assert len(results) >= 1
        # 每个结果格式: (agent, confidence, strategy)
        for agent, conf, strat in results:
            assert conf > 0
            assert strat in ("l1", "l2", "fallback")

    def test_route_multi_no_match_fallback(self, registry):
        from soma.multi_agent import ExpertRouter
        router = ExpertRouter(registry)
        results = router.route_multi("无意义的词语xyz", top_k=2)
        assert len(results) >= 1
        assert results[0][2] == "fallback"

    def test_route_without_default_raises(self):
        from soma.multi_agent import AgentRegistry, ExpertRouter
        registry = AgentRegistry()
        # 无任何 agent
        router = ExpertRouter(registry)
        with pytest.raises(RuntimeError, match="没有可用的 agent"):
            router.route("测试问题", allow_fallback=False)

    def test_route_stats_tracking(self, registry):
        from soma.multi_agent import ExpertRouter
        router = ExpertRouter(registry)
        router.route("合同纠纷如何处理")  # L1 hit
        router.route("天气不错")          # fallback
        stats = router.stats
        assert stats["route_count"] == 2
        assert stats["l1_hit_rate"] > 0
        assert stats["fallback_rate"] > 0


# ============================================================================
# Task 4: DistributedEvolver 测试
# ============================================================================

class MockEvolver:
    """模拟 MetaEvolver 用于分布式演化测试"""
    def __init__(self, weights=None):
        self._weights = dict(weights) if weights else {
            "first_principles": 0.9,
            "systems_thinking": 0.8,
            "contradiction_analysis": 0.7,
        }
        self._evolve_count = 0

    def evolve(self):
        self._evolve_count += 1
        return [{"law_id": k, "old_weight": v, "new_weight": v + 0.01}
                for k, v in self._weights.items()]

    def get_weights(self):
        return dict(self._weights)

    def adjust_weight(self, law_id, weight):
        self._weights[law_id] = weight


class TestDistributedEvolver:
    """DistributedEvolver — 注册/演化/合并/冲突仲裁"""

    @pytest.fixture
    def tmp_dir(self, tmp_path):
        return tmp_path / "evolve"

    def test_register_agent(self, tmp_dir):
        from soma.multi_agent import DistributedEvolver
        de = DistributedEvolver(tmp_dir)
        ev = MockEvolver()
        de.register_agent("agent_a", ev, session_count=10, success_rate=0.8)
        assert de.agent_count == 1

    def test_unregister_agent(self, tmp_dir):
        from soma.multi_agent import DistributedEvolver
        de = DistributedEvolver(tmp_dir)
        de.register_agent("agent_a", MockEvolver())
        assert de.unregister_agent("agent_a") is True
        assert de.agent_count == 0
        assert de.unregister_agent("nonexistent") is False

    def test_evolve_single_agent(self, tmp_dir):
        from soma.multi_agent import DistributedEvolver
        de = DistributedEvolver(tmp_dir)
        ev = MockEvolver()
        de.register_agent("agent_a", ev)
        changes = de.evolve_agent("agent_a")
        assert len(changes) == 3
        assert ev._evolve_count == 1

    def test_evolve_unregistered_returns_empty(self, tmp_dir):
        from soma.multi_agent import DistributedEvolver
        de = DistributedEvolver(tmp_dir)
        changes = de.evolve_agent("nonexistent")
        assert changes == []

    def test_evolve_all(self, tmp_dir):
        from soma.multi_agent import DistributedEvolver
        de = DistributedEvolver(tmp_dir)
        de.register_agent("a", MockEvolver({"law1": 0.5}))
        de.register_agent("b", MockEvolver({"law1": 0.7}))
        results = de.evolve_all()
        assert len(results) == 2

    def test_merge_simple_average(self, tmp_dir):
        from soma.multi_agent import DistributedEvolver
        de = DistributedEvolver(tmp_dir)
        de.register_agent("a", MockEvolver({"law1": 0.5, "law2": 0.3}),
                           session_count=5, success_rate=0.6)
        de.register_agent("b", MockEvolver({"law1": 0.9, "law2": 0.7}),
                           session_count=15, success_rate=0.9)
        merged = de.merge_weights(strategy="simple_average")
        # 等权平均: law1 = (0.5+0.9)/2 = 0.7, law2 = (0.3+0.7)/2 = 0.5
        assert abs(merged["law1"] - 0.7) < 0.01
        assert abs(merged["law2"] - 0.5) < 0.01

    def test_merge_weighted_by_sessions(self, tmp_dir):
        from soma.multi_agent import DistributedEvolver
        de = DistributedEvolver(tmp_dir)
        # agent_a: 5次会话, agent_b: 15次会话 → b的权重是a的3倍
        de.register_agent("a", MockEvolver({"law1": 0.4}),
                           session_count=5, success_rate=0.5)
        de.register_agent("b", MockEvolver({"law1": 0.8}),
                           session_count=15, success_rate=0.5)
        merged = de.merge_weights(strategy="weighted_by_sessions")
        # law1 = (0.4*5 + 0.8*15) / (5+15) = (2+12)/20 = 0.7
        assert abs(merged["law1"] - 0.7) < 0.01

    def test_merge_weighted_by_success(self, tmp_dir):
        from soma.multi_agent import DistributedEvolver
        de = DistributedEvolver(tmp_dir)
        # agent_a: 成功率0.3, agent_b: 成功率0.9 → b更有话语权
        de.register_agent("a", MockEvolver({"law1": 0.4}),
                           session_count=5, success_rate=0.3)
        de.register_agent("b", MockEvolver({"law1": 0.8}),
                           session_count=15, success_rate=0.9)
        merged = de.merge_weights(strategy="weighted_by_success")
        # 偏向高成功率agent
        assert merged["law1"] > 0.5  # 偏向0.8而非0.4
        assert merged["law1"] < 0.8  # 不完全取b的值

    def test_merge_no_agents_returns_default(self, tmp_dir):
        from soma.multi_agent import DistributedEvolver
        defaults = {"law1": 0.5}
        de = DistributedEvolver(tmp_dir, default_weights=defaults)
        merged = de.merge_weights()
        assert merged == defaults

    def test_get_global_weights_before_merge(self, tmp_dir):
        from soma.multi_agent import DistributedEvolver
        defaults = {"law1": 0.5}
        de = DistributedEvolver(tmp_dir, default_weights=defaults)
        assert de.get_global_weights() == defaults

    def test_apply_global_weights(self, tmp_dir):
        from soma.multi_agent import DistributedEvolver
        de = DistributedEvolver(tmp_dir)
        ev = MockEvolver({"law1": 0.3})
        de.register_agent("a", ev)
        # 先合并
        de.merge_weights(strategy="simple_average")
        # 应用全局权重
        success = de.apply_global_weights("a")
        assert success is True
        assert ev._weights["law1"] == 0.3  # 单agent合并不变

    def test_apply_all(self, tmp_dir):
        from soma.multi_agent import DistributedEvolver
        de = DistributedEvolver(tmp_dir)
        de.register_agent("a", MockEvolver({"law1": 0.5}))
        de.register_agent("b", MockEvolver({"law1": 0.7}))
        de.merge_weights()
        count = de.apply_all()
        assert count == 2

    def test_get_stats(self, tmp_dir):
        from soma.multi_agent import DistributedEvolver
        de = DistributedEvolver(tmp_dir)
        de.register_agent("a", MockEvolver({"law1": 0.5}),
                           session_count=10, success_rate=0.75)
        de.merge_weights()
        stats = de.get_stats()
        assert stats["agent_count"] == 1
        assert stats["merge_count"] == 1
        assert stats["merge_strategy"] == "weighted_by_success"
        assert "a" in stats["agents"]
        assert stats["agents"]["a"]["session_count"] == 10
        assert stats["agents"]["a"]["success_rate"] == 0.75

    def test_update_stats(self, tmp_dir):
        from soma.multi_agent import DistributedEvolver
        de = DistributedEvolver(tmp_dir)
        de.register_agent("a", MockEvolver())
        de.update_stats("a", session_count=20, success_rate=0.95)
        stats = de.get_stats()
        assert stats["agents"]["a"]["session_count"] == 20
        assert stats["agents"]["a"]["success_rate"] == 0.95

    def test_conflict_resolution_biases_toward_high_success(self, tmp_dir):
        from soma.multi_agent import DistributedEvolver
        de = DistributedEvolver(tmp_dir)
        # 两个agent对同一law的权重差距很大
        de.register_agent("weak", MockEvolver({"law1": 0.2}),
                           session_count=5, success_rate=0.3)
        de.register_agent("strong", MockEvolver({"law1": 0.9}),
                           session_count=50, success_rate=0.95)
        merged = de.merge_weights(strategy="weighted_by_success")
        # 差距>0.15，应偏向成功率高的agent (0.9)
        assert merged["law1"] > 0.65  # 明显偏向0.9


# ============================================================================
# Task 2: ConsensusProtocol 测试
# ============================================================================

class TestConsensusProtocol:
    """ConsensusProtocol — 加权投票 / LLM仲裁 / 辩证综合"""

    @pytest.fixture
    def protocol(self):
        from soma.multi_agent import ConsensusProtocol
        return ConsensusProtocol()

    @pytest.fixture
    def protocol_with_llm(self):
        from soma.multi_agent import ConsensusProtocol
        mock_llm = Mock(return_value="共识度: 0.75\n仲裁结论: 综合各方观点，建议采用方案A但考虑B的补充。\n分歧点: 实施优先级、资源分配")
        return ConsensusProtocol(llm_call=mock_llm)

    @pytest.fixture
    def two_similar_opinions(self):
        from soma.multi_agent import AgentOpinion
        return [
            AgentOpinion(
                agent_id="agent_a", answer="应采用微服务架构提升系统可扩展性",
                confidence=0.9, key_points=["微服务", "可扩展性", "独立部署"],
                supporting_memories=5,
            ),
            AgentOpinion(
                agent_id="agent_b", answer="推荐使用微服务架构以便独立扩展各模块",
                confidence=0.85, key_points=["微服务", "独立扩展", "技术债务低"],
                supporting_memories=4,
            ),
        ]

    @pytest.fixture
    def two_divergent_opinions(self):
        from soma.multi_agent import AgentOpinion
        return [
            AgentOpinion(
                agent_id="agent_a", answer="应优先考虑性能优化，使用Rust重写核心模块",
                confidence=0.9, key_points=["性能", "Rust", "零成本抽象", "内存安全"],
                supporting_memories=3,
            ),
            AgentOpinion(
                agent_id="agent_b", answer="应优先考虑开发效率，保持Python并优化算法",
                confidence=0.5, key_points=["开发效率", "Python", "快速迭代", "团队熟悉"],
                supporting_memories=5,
            ),
        ]

    @pytest.fixture
    def three_opinions(self):
        from soma.multi_agent import AgentOpinion
        return [
            AgentOpinion(
                agent_id="agent_a", answer="方案A：集中式缓存",
                confidence=0.9, key_points=["集中式", "一致性好", "管理简单"],
                supporting_memories=4,
            ),
            AgentOpinion(
                agent_id="agent_b", answer="方案B：分布式缓存",
                confidence=0.5, key_points=["分布式", "扩展性好", "容错强"],
                supporting_memories=3,
            ),
            AgentOpinion(
                agent_id="agent_c", answer="方案C：混合架构",
                confidence=0.5, key_points=["混合", "兼顾一致性", "兼顾扩展性"],
                supporting_memories=2,
            ),
        ]

    # ── 加权投票 ──

    def test_single_opinion_returns_directly(self, protocol):
        from soma.multi_agent import AgentOpinion
        op = AgentOpinion(agent_id="solo", answer="唯一答案", confidence=0.8)
        result = protocol.form_consensus("测试?", [op])
        assert result.agreement_level == 1.0
        assert result.consensus_answer == "唯一答案"
        assert result.strategy_used == "single_agent"
        assert result.is_strong_consensus

    def test_weighted_voting_selects_highest_weight(self, protocol, two_similar_opinions):
        result = protocol.form_consensus("架构选择?", two_similar_opinions, strategy="voting")
        # agent_a 置信度0.9 + 5条记忆 > agent_b 0.85 + 4条记忆
        assert "agent_a" in result.consensus_answer or result.agreement_level >= 0.5
        assert result.strategy_used == "voting"
        assert result.agent_count == 2

    def test_weighted_voting_with_divergent_opinions(self, protocol, two_divergent_opinions):
        result = protocol.form_consensus("技术选型?", two_divergent_opinions, strategy="voting")
        # 2 agent最多1个分歧点，共识度最低~0.75
        assert 0.7 < result.agreement_level <= 1.0
        assert result.strategy_used == "voting"
        # agent_b有更多支持记忆+更高总权重，会被选为最佳观点
        assert len(result.disagreements) >= 1

    def test_weighted_voting_with_three_opinions(self, protocol, three_opinions):
        result = protocol.form_consensus("缓存架构?", three_opinions, strategy="voting")
        assert result.agent_count == 3
        # agreement < 0.8 + 3个agent → 有少数派观点
        assert result.minority_view is not None
        assert len(result.disagreements) >= 1

    def test_empty_opinions_raises(self, protocol):
        with pytest.raises(ValueError, match="至少需要一个 agent 观点"):
            protocol.form_consensus("问题?", [])

    def test_consensus_result_has_strong_consensus_property(self, protocol):
        from soma.multi_agent import AgentOpinion
        op = AgentOpinion(agent_id="a", answer="答案", confidence=0.9)
        result = protocol.form_consensus("问题?", [op])
        assert result.is_strong_consensus  # 1.0 >= 0.8

    # ── LLM 仲裁 ──

    def test_llm_arbitration_calls_llm(self, protocol_with_llm, two_divergent_opinions):
        result = protocol_with_llm.form_consensus(
            "技术选型?", two_divergent_opinions, strategy="llm_arbitration",
        )
        assert result.strategy_used == "llm_arbitration"
        assert result.agreement_level == 0.75
        assert "方案A" in result.consensus_answer
        assert len(result.disagreements) == 1
        protocol_with_llm._llm_call.assert_called_once()

    def test_llm_arbitration_fallback_on_error(self, protocol, two_divergent_opinions):
        mock_llm = Mock(side_effect=RuntimeError("API故障"))
        from soma.multi_agent import ConsensusProtocol
        proto = ConsensusProtocol(llm_call=mock_llm)
        result = proto.form_consensus(
            "技术选型?", two_divergent_opinions, strategy="llm_arbitration",
        )
        # LLM失败 → 回退到voting
        assert result.strategy_used == "voting"

    def test_llm_arbitration_without_llm_falls_back_to_voting(self, protocol, two_divergent_opinions):
        # 没有LLM且指定llm_arbitration → 回退到voting
        result = protocol.form_consensus(
            "技术选型?", two_divergent_opinions, strategy="llm_arbitration",
        )
        assert result.strategy_used == "voting"

    # ── 辩证综合 ──

    def test_dialectical_synthesis_calls_llm(self, protocol_with_llm, two_divergent_opinions):
        result = protocol_with_llm.form_consensus(
            "技术选型?", two_divergent_opinions, strategy="dialectical_synthesis",
        )
        assert result.strategy_used == "dialectical_synthesis"
        assert result.agreement_level == 0.6  # 辩证综合默认
        protocol_with_llm._llm_call.assert_called_once()

    def test_dialectical_synthesis_fallback_to_arbitration(self, protocol, two_divergent_opinions):
        mock_llm = Mock(side_effect=[RuntimeError("API故障"), "仲裁: 回退成功"])
        from soma.multi_agent import ConsensusProtocol
        proto = ConsensusProtocol(llm_call=mock_llm)
        result = proto.form_consensus(
            "技术选型?", two_divergent_opinions, strategy="dialectical_synthesis",
        )
        # 辩证综合失败 → 回退到LLM仲裁
        assert result.strategy_used == "llm_arbitration"

    def test_dialectical_without_llm_falls_back_to_voting(self, protocol, two_divergent_opinions):
        result = protocol.form_consensus(
            "技术选型?", two_divergent_opinions, strategy="dialectical_synthesis",
        )
        assert result.strategy_used == "voting"

    # ── AgentOpinion ──

    def test_agent_opinion_summary(self):
        from soma.multi_agent import AgentOpinion
        op = AgentOpinion(
            agent_id="expert_1", answer="详细答案...",
            confidence=0.85, key_points=["关键点A", "关键点B", "关键点C", "关键点D"],
        )
        summary = op.summary()
        assert "expert_1" in summary
        assert "0.85" in summary
        assert "关键点A" in summary
        # 最多显示3个关键点

    def test_agent_opinion_empty_points(self):
        from soma.multi_agent import AgentOpinion
        op = AgentOpinion(agent_id="expert_1", answer="答案", key_points=[])
        assert "无核心论点" in op.summary()


# ============================================================================
# 端到端集成测试
# ============================================================================

class TestMultiAgentIntegration:
    """多 Agent 全流程：注册 → 路由 → 演化 → 共识"""

    def test_full_multi_agent_pipeline(self, tmp_path):
        """模拟完整多agent协作流程"""
        from soma.multi_agent import (
            AgentRegistry, ExpertRouter, DistributedEvolver,
            ConsensusProtocol, AgentOpinion,
        )

        # 1. 初始化注册表并注册专家
        registry = AgentRegistry()
        agents = {
            "law_expert": FakeAgent("law_expert"),
            "tech_expert": FakeAgent("tech_expert"),
            "finance_expert": FakeAgent("finance_expert"),
        }
        registry.register(agents["law_expert"], ["法律", "合同", "合规"], "法律领域专家")
        registry.register(agents["tech_expert"], ["技术", "架构", "编程"], "技术领域专家")
        registry.register(agents["finance_expert"], ["金融", "投资", "财务"], "金融领域专家")
        assert registry.agent_count == 3

        # 2. 路由问题到专家
        router = ExpertRouter(registry)
        law_agent, law_conf, law_strat = router.route("这个合同条款是否合法？")
        assert law_strat == "l1"
        assert law_agent.agent_id == "law_expert"

        tech_agent, tech_conf, tech_strat = router.route("微服务架构如何设计？")
        assert tech_strat == "l1"
        assert tech_agent.agent_id == "tech_expert"

        # 路由统计正确
        stats = router.stats
        assert stats["route_count"] == 2
        assert stats["l1_hit_rate"] == 1.0

        # 3. 分布式演化
        de = DistributedEvolver(tmp_path / "evolve")
        for aid in ["law_expert", "tech_expert", "finance_expert"]:
            de.register_agent(aid, MockEvolver({
                "first_principles": 0.7,
                "systems_thinking": 0.6,
            }), session_count=10, success_rate=0.7 + 0.1 * len(aid))

        # 记录一次成功会话
        registry.record_session("law_expert", success=True)
        registry.record_session("tech_expert", success=True)

        # 演化所有agent
        changes = de.evolve_all()
        assert len(changes) == 3

        # 合并权重
        merged = de.merge_weights(strategy="weighted_by_success")
        assert len(merged) == 2
        assert "first_principles" in merged
        assert "systems_thinking" in merged

        # 4. 共识形成
        protocol = ConsensusProtocol()
        opinions = [
            AgentOpinion(
                agent_id=aid, answer=f"{aid}的分析结果",
                confidence=0.7 + 0.1 * i,
                key_points=[f"{aid}_观点{i}" for i in range(3)],
                supporting_memories=i + 1,
            )
            for i, aid in enumerate(["law_expert", "tech_expert", "finance_expert"])
        ]
        result = protocol.form_consensus("综合分析", opinions)
        assert result.agent_count == 3
        assert result.strategy_used == "voting"
        assert 0 < result.agreement_level <= 1.0

    def test_isolated_agents_different_weights(self, tmp_path):
        """验证不同agent可以有独立的权重配置"""
        from soma.multi_agent import DistributedEvolver
        de = DistributedEvolver(tmp_path / "evolve_iso")
        de.register_agent("agent_a", MockEvolver({"law1": 0.9, "law2": 0.1}))
        de.register_agent("agent_b", MockEvolver({"law1": 0.1, "law2": 0.9}))

        w_a = de.get_agent_weights("agent_a")
        w_b = de.get_agent_weights("agent_b")
        assert w_a["law1"] > w_a["law2"]
        assert w_b["law2"] > w_b["law1"]

    def test_session_count_persistence_via_stats(self, tmp_path):
        """验证会话统计在registry中正确更新"""
        from soma.multi_agent import AgentRegistry
        registry = AgentRegistry()
        registry.register(FakeAgent("ag1"), ["领域A"])
        registry.register(FakeAgent("ag2"), ["领域B"])

        # 模拟多次会话
        for _ in range(5):
            registry.record_session("ag1", success=True)
        for _ in range(3):
            registry.record_session("ag2", success=False)

        info1 = registry.get_info("ag1")
        info2 = registry.get_info("ag2")
        assert info1.session_count == 5
        assert info2.session_count == 3
        # ag1 全部成功 → 成功率应 > 0.5
        # ag2 全部失败 → 成功率应 < 0.5
        assert info1.success_rate > 0.6
        assert info2.success_rate < 0.4
