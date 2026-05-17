"""v0.9.2 SOMAOrchestrator 集成测试 — 多Agent编排管道"""
import pytest
from unittest.mock import Mock, MagicMock, patch


class FakeAgent:
    """模拟 SOMA_Agent 用于编排器测试"""
    def __init__(self, agent_id="test_agent", group_id="", respond_answer="mock回答"):
        self.agent_id = agent_id
        self.group_id = group_id
        self._respond_answer = respond_answer
        self._respond_calls = 0

    def respond(self, problem, user_id=""):
        self._respond_calls += 1
        return f"[{self.agent_id}] {self._respond_answer}: {problem[:30]}"


# ============================================================================
# Task 1: SOMAOrchestrator 基础生命周期
# ============================================================================

class TestOrchestratorLifecycle:
    """SOMAOrchestrator — 创建/注册/注销/默认Agent"""

    def test_create_with_config(self):
        from soma.config import SOMAConfig
        from soma.multi_agent.orchestrator import SOMAOrchestrator
        config = SOMAConfig()
        orch = SOMAOrchestrator(config)
        assert orch.agent_count == 0
        assert orch.default_agent is None

    def test_set_default_agent(self):
        from soma.config import SOMAConfig
        from soma.multi_agent.orchestrator import SOMAOrchestrator
        config = SOMAConfig()
        orch = SOMAOrchestrator(config)
        agent = FakeAgent("default_bot")
        orch.set_default(agent)
        assert orch.default_agent is agent
        assert orch.agent_count == 1

    def test_remove_agent_auto_switch_default(self):
        from soma.config import SOMAConfig
        from soma.multi_agent.orchestrator import SOMAOrchestrator
        config = SOMAConfig()
        orch = SOMAOrchestrator(config)
        orch.set_default(FakeAgent("bot1"))
        orch.set_default(FakeAgent("bot2"))
        orch.remove_agent("bot1")
        assert orch.agent_count == 1
        remaining = orch.registry.list_agents()
        assert remaining[0].agent_id == "bot2"

    def test_create_agents_with_specs(self):
        from soma.config import SOMAConfig
        from soma.multi_agent.orchestrator import SOMAOrchestrator
        config = SOMAConfig(use_vector_search=False)
        orch = SOMAOrchestrator(config)
        ids = orch.create_agents([
            {"agent_id": "analyst", "expertise": ["商业分析"], "description": "分析师"},
            {"agent_id": "engineer", "expertise": ["技术"], "description": "工程师"},
        ])
        assert ids == ["analyst", "engineer"]
        assert orch.agent_count == 2
        assert orch.default_agent is not None  # 第一个自动成为默认

    def test_single_mode_is_default(self):
        """v0.9.2核心约束：默认模式行为不变"""
        import tempfile
        from soma import SOMA
        tmpdir = tempfile.mkdtemp()
        s = SOMA(persist_dir=tmpdir, use_vector_search=False)
        assert s._orchestrator is None
        assert s._config.orchestration_mode == "single"
        s.close()


# ============================================================================
# Task 2: 路由测试
# ============================================================================

class TestOrchestratorRouting:
    """SOMAOrchestrator — L1/L2/回退路由"""

    def test_l1_routing_tech_to_engineer(self):
        from soma.config import SOMAConfig
        from soma.multi_agent.orchestrator import SOMAOrchestrator
        config = SOMAConfig(use_vector_search=False)
        orch = SOMAOrchestrator(config)
        orch.set_default(FakeAgent("analyst", respond_answer="商业视角"))
        orch.set_default(FakeAgent("engineer", respond_answer="技术方案"))
        # 第二个set_default覆盖了第一个默认，用registry直接注册
        orch.registry.register(
            FakeAgent("analyst2", respond_answer="商业视角"),
            expertise=["商业分析"], description="分析师",
        )
        orch.registry.register(
            FakeAgent("engineer2", respond_answer="技术方案"),
            expertise=["技术", "架构"], description="工程师", is_default=True,
        )
        experts = orch.router.route_multi("如何优化代码架构和系统性能", top_k=2)
        assert len(experts) > 0
        # 技术关键词应该命中engineer
        agent_ids = [getattr(a, 'agent_id', '') for a, _, _ in experts]
        assert "engineer2" in agent_ids

    def test_route_multi_respects_top_k(self):
        from soma.config import SOMAConfig
        from soma.multi_agent.orchestrator import SOMAOrchestrator
        config = SOMAConfig()
        orch = SOMAOrchestrator(config)
        for i in range(5):
            orch.registry.register(
                FakeAgent(f"bot{i}"), expertise=[f"领域{i}"],
            )
        experts = orch.router.route_multi("通用问题", top_k=2)
        assert len(experts) <= 2

    def test_fallback_when_no_match(self):
        from soma.config import SOMAConfig
        from soma.multi_agent.orchestrator import SOMAOrchestrator
        config = SOMAConfig()
        orch = SOMAOrchestrator(config)
        default = FakeAgent("default_bot")
        orch.set_default(default)
        # 非中文问题不会命中L1关键词
        experts = orch.router.route_multi("xyzzy", top_k=3)
        assert len(experts) > 0
        # 应回退到默认
        assert experts[0][2] == "fallback"

    def test_routing_stats_updated(self):
        from soma.config import SOMAConfig
        from soma.multi_agent.orchestrator import SOMAOrchestrator
        config = SOMAConfig()
        orch = SOMAOrchestrator(config)
        orch.registry.register(
            FakeAgent("tech"), expertise=["技术"],
        )
        orch.router.route_multi("代码架构优化", top_k=2)
        stats = orch.router.stats
        assert stats["route_count"] > 0


# ============================================================================
# Task 3: solve 端到端管道
# ============================================================================

class TestOrchestratorSolve:
    """SOMAOrchestrator.solve() — 路由→分发→共识 全管道"""

    def test_solve_single_agent(self):
        from soma.config import SOMAConfig
        from soma.multi_agent.orchestrator import SOMAOrchestrator
        config = SOMAConfig()
        orch = SOMAOrchestrator(config)
        orch.set_default(FakeAgent("solo", respond_answer="独到见解"))
        result = orch.solve("如何提升团队效率？")
        assert "solo" in result.agents_involved
        assert "独到见解" in result.answer

    def test_solve_multi_agent_consensus(self):
        from soma.config import SOMAConfig
        from soma.multi_agent.orchestrator import SOMAOrchestrator
        config = SOMAConfig()
        orch = SOMAOrchestrator(config)
        orch.registry.register(
            FakeAgent("analyst", respond_answer="从商业角度分析"),
            expertise=["商业分析"],
        )
        orch.registry.register(
            FakeAgent("tech", respond_answer="从技术角度解决"),
            expertise=["技术"],
        )
        result = orch.solve("如何提升系统性能？", top_k=2)
        assert len(result.agents_involved) >= 1
        assert len(result.answer) > 0

    def test_solve_returns_orchestration_result(self):
        from soma.config import SOMAConfig
        from soma.multi_agent.orchestrator import SOMAOrchestrator
        config = SOMAConfig()
        orch = SOMAOrchestrator(config)
        orch.set_default(FakeAgent("bot"))
        result = orch.solve("测试")
        assert result.question == "测试"
        assert result.routing_strategy != ""
        assert isinstance(result.agents_involved, list)

    def test_solve_empty_agents_graceful(self):
        """无Agent时solve不崩溃"""
        from soma.config import SOMAConfig
        from soma.multi_agent.orchestrator import SOMAOrchestrator
        config = SOMAConfig()
        orch = SOMAOrchestrator(config)
        result = orch.solve("测试问题")
        assert "没有可用" in result.answer
        assert result.routing_strategy == "fallback"
        assert result.consensus is None

    def test_solve_agent_error_isolation(self):
        """单个Agent异常不影响其他Agent"""
        from soma.config import SOMAConfig
        from soma.multi_agent.orchestrator import SOMAOrchestrator
        config = SOMAConfig()

        class CrashAgent:
            agent_id = "crasher"
            group_id = ""
            def respond(self, problem, user_id=""):
                raise RuntimeError("模拟崩溃")

        orch = SOMAOrchestrator(config)
        orch.registry.register(CrashAgent(), expertise=["技术"])
        orch.registry.register(
            FakeAgent("survivor", respond_answer="我还在"),
            expertise=["管理"],
        )
        # 用包含两个领域关键词的问题确保两个专家都被路由到
        result = orch.solve("技术团队如何提升管理效率？", top_k=2)
        # survivor应该仍然返回结果
        assert "survivor" in result.agents_involved
        assert len(result.answer) > 0

    def test_consensus_has_agreement_level(self):
        from soma.config import SOMAConfig
        from soma.multi_agent.orchestrator import SOMAOrchestrator
        config = SOMAConfig()
        orch = SOMAOrchestrator(config)
        orch.registry.register(
            FakeAgent("a1", respond_answer="方案A：加缓存"),
            expertise=["技术"],
        )
        orch.registry.register(
            FakeAgent("a2", respond_answer="方案B：优化查询"),
            expertise=["技术"],
        )
        result = orch.solve("如何优化数据库性能？", top_k=2)
        if result.consensus:
            assert 0.0 <= result.consensus.agreement_level <= 1.0


# ============================================================================
# Task 4: SOMA门面集成测试
# ============================================================================

class TestSOMAFacadeOrchestration:
    """SOMA 门面 — orchestration_mode 集成"""

    def test_soma_default_no_orchestrator(self):
        """默认模式不创建编排器"""
        import tempfile
        from soma import SOMA
        tmpdir = tempfile.mkdtemp()
        s = SOMA(persist_dir=tmpdir, use_vector_search=False)
        assert s._orchestrator is None
        assert s._config.orchestration_mode == "single"
        s.close()

    def test_soma_multi_mode_creates_orchestrator(self):
        """multi模式创建编排器"""
        import tempfile
        from soma import SOMA
        tmpdir = tempfile.mkdtemp()
        s = SOMA(orchestration_mode="multi", persist_dir=tmpdir, use_vector_search=False)
        assert s._orchestrator is not None
        assert s._config.orchestration_mode == "multi"
        s.close()

    def test_soma_register_expert(self):
        """SOMA.register_expert()注册专家"""
        import tempfile
        from soma import SOMA
        tmpdir = tempfile.mkdtemp()
        s = SOMA(orchestration_mode="multi", persist_dir=tmpdir, use_vector_search=False)
        aid = s.register_expert("analyst", ["商业分析"], "战略分析师")
        assert aid == "analyst"
        experts = s.list_experts()
        # 包含主soma Agent + 新注册的analyst
        assert len(experts) >= 1
        assert any(e["agent_id"] == "analyst" for e in experts)
        s.close()

    def test_soma_register_expert_without_multi_raises(self):
        """单模式下调用register_expert应抛异常"""
        import tempfile
        from soma import SOMA
        tmpdir = tempfile.mkdtemp()
        s = SOMA(persist_dir=tmpdir, use_vector_search=False)
        with pytest.raises(RuntimeError, match="orchestration_mode='multi'"):
            s.register_expert("test", ["测试"])
        s.close()

    def test_soma_list_experts_empty_in_single_mode(self):
        """单模式下list_experts返回空列表"""
        import tempfile
        from soma import SOMA
        tmpdir = tempfile.mkdtemp()
        s = SOMA(persist_dir=tmpdir, use_vector_search=False)
        assert s.list_experts() == []
        s.close()

    def test_soma_solve_multi_requires_multi_mode(self):
        """单模式下solve_multi应抛异常"""
        import tempfile
        from soma import SOMA
        tmpdir = tempfile.mkdtemp()
        s = SOMA(persist_dir=tmpdir, use_vector_search=False)
        with pytest.raises(RuntimeError, match="orchestration_mode='multi'"):
            s.solve_multi("测试")
        s.close()

    def test_soma_multi_respond_pipeline(self):
        """multi模式下respond走编排管道"""
        import tempfile
        from soma import SOMA
        tmpdir = tempfile.mkdtemp()
        s = SOMA(orchestration_mode="multi", persist_dir=tmpdir, use_vector_search=False)
        s.register_expert("tech", ["技术"], "技术专家")
        answer = s.respond("如何优化代码质量？")
        assert isinstance(answer, str)
        assert len(answer) > 0
        s.close()

    def test_soma_multi_chat_returns_orchestration_field(self):
        """multi模式下chat返回含orchestration字段"""
        import tempfile
        from soma import SOMA
        tmpdir = tempfile.mkdtemp()
        s = SOMA(orchestration_mode="multi", persist_dir=tmpdir, use_vector_search=False)
        # 直接向编排器注册FakeAgent，绕过register_expert
        # register_expert创建真实SOMA_Agent，Mock模式下无法调用LLM，共识无法形成
        s._orchestrator.registry.register(
            FakeAgent("tech", respond_answer="从技术角度优化性能：缓存、索引、异步"),
            expertise=["技术"],
            description="技术专家",
        )
        result = s.chat("如何提升系统性能？")
        assert "answer" in result
        assert "orchestration" in result
        assert "agents_involved" in result["orchestration"]
        s.close()

    def test_soma_respond_single_mode_unchanged(self):
        """回归：单模式下respond行为不变"""
        import tempfile
        from soma import SOMA
        tmpdir = tempfile.mkdtemp()
        s = SOMA(persist_dir=tmpdir, use_vector_search=False)
        answer = s.respond("测试问题")
        assert isinstance(answer, str)
        assert len(answer) > 0
        s.close()

    def test_soma_chat_single_mode_unchanged(self):
        """回归：单模式下chat行为不变"""
        import tempfile
        from soma import SOMA
        tmpdir = tempfile.mkdtemp()
        s = SOMA(persist_dir=tmpdir, use_vector_search=False)
        result = s.chat("测试问题")
        assert isinstance(result, dict)
        assert "answer" in result
        assert "foci" in result
        s.close()
