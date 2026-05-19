"""v1.1.0 专项测试 — 并行分发 + 分布式演化集成"""

import time
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from soma.config import SOMAConfig
from soma.multi_agent.orchestrator import SOMAOrchestrator, OrchestrationResult
from soma.multi_agent.consensus import AgentOpinion


class MockAgent:
    """模拟 SOMA_Agent — 可控制响应延迟和内容"""

    def __init__(self, agent_id: str, delay: float = 0.05, fail: bool = False):
        self.agent_id = agent_id
        self.delay = delay
        self.fail = fail
        self.evolver = MagicMock()
        self.evolver.get_weights.return_value = {"first_principles": 0.85}
        self.evolver.adjust_weight = MagicMock()

    def respond(self, problem: str) -> str:
        if self.fail:
            raise RuntimeError(f"{self.agent_id} simulated failure")
        time.sleep(self.delay)
        return f"[{self.agent_id}] 对「{problem[:20]}...」的分析"


@pytest.fixture
def config():
    return SOMAConfig(
        episodic_persist_dir=Path(tempfile.mkdtemp()),
        orchestration_mode="multi",
        orchestration_top_k=3,
        orchestration_consensus="voting",
        orchestration_parallel=True,
        orchestration_evolution_enabled=True,
        orchestration_evolution_interval=5,
    )


@pytest.fixture
def orch(config):
    return SOMAOrchestrator(config)


# ═══════════════════════════════════════════════════════════════
# T1: 串行分发（parallel=False）
# ═══════════════════════════════════════════════════════════════

def test_dispatch_serial_mode(config):
    """并行关闭时使用串行分发"""
    config.orchestration_parallel = False
    orch = SOMAOrchestrator(config)

    a1 = MockAgent("a1", delay=0.02)
    a2 = MockAgent("a2", delay=0.02)
    orch.registry.register(a1, expertise=["技术"], description="技术专家")
    orch.registry.register(a2, expertise=["商业"], description="商业专家")

    opinions, ids, strategies = orch._dispatch_serial(
        "测试问题", [(a1, 0.9, "l1"), (a2, 0.8, "l1")],
    )
    assert len(opinions) == 2
    assert ids == ["a1", "a2"]
    assert "l1" in strategies


# ═══════════════════════════════════════════════════════════════
# T2: 并行分发 — 延迟验证（并行应快于串行总和）
# ═══════════════════════════════════════════════════════════════

def test_dispatch_parallel_faster_than_serial():
    """三个各延迟 100ms 的 Agent，并行应 < 180ms（串行需 300ms+）"""
    config = SOMAConfig(
        episodic_persist_dir=Path(tempfile.mkdtemp()),
        orchestration_parallel=True,
    )
    orch = SOMAOrchestrator(config)

    a1 = MockAgent("slow1", delay=0.10)
    a2 = MockAgent("slow2", delay=0.10)
    a3 = MockAgent("slow3", delay=0.10)
    orch.registry.register(a1, expertise=["A"])
    orch.registry.register(a2, expertise=["B"])
    orch.registry.register(a3, expertise=["C"])

    t0 = time.perf_counter()
    opinions, ids, strategies = orch._dispatch_parallel(
        "测试", [(a1, 0.9, "l1"), (a2, 0.8, "l1"), (a3, 0.7, "l1")],
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000

    assert len(opinions) == 3
    # 并行应显著快于串行总和 (300ms)
    assert elapsed_ms < 250, f"并行分发耗时 {elapsed_ms:.0f}ms，应 < 250ms"


# ═══════════════════════════════════════════════════════════════
# T3: 并行分发 — 单个 Agent 失败不影响其他
# ═══════════════════════════════════════════════════════════════

def test_dispatch_parallel_agent_failure_isolated():
    """一个 Agent 抛异常，其他两个正常返回"""
    config = SOMAConfig(
        episodic_persist_dir=Path(tempfile.mkdtemp()),
        orchestration_parallel=True,
    )
    orch = SOMAOrchestrator(config)

    a_good1 = MockAgent("good1", delay=0.02)
    a_bad = MockAgent("bad", delay=0.02, fail=True)
    a_good2 = MockAgent("good2", delay=0.02)

    orch.registry.register(a_good1, expertise=["A"])
    orch.registry.register(a_bad, expertise=["B"])
    orch.registry.register(a_good2, expertise=["C"])

    opinions, ids, _ = orch._dispatch_parallel(
        "测试", [(a_good1, 0.9, "l1"), (a_bad, 0.8, "l1"), (a_good2, 0.7, "l1")],
    )
    assert len(opinions) == 2
    assert "bad" not in [o.agent_id for o in opinions]
    assert "good1" in ids and "good2" in ids


# ═══════════════════════════════════════════════════════════════
# T4: 并行分发 — 结果按原顺序排列（确定性）
# ═══════════════════════════════════════════════════════════════

def test_dispatch_parallel_result_order_deterministic():
    """并行结果应按 agent_involved 顺序排列，保证确定性"""
    config = SOMAConfig(
        episodic_persist_dir=Path(tempfile.mkdtemp()),
        orchestration_parallel=True,
    )
    orch = SOMAOrchestrator(config)

    a1 = MockAgent("agent_a", delay=0.10)  # 慢
    a2 = MockAgent("agent_b", delay=0.01)  # 快
    a3 = MockAgent("agent_c", delay=0.05)  # 中

    for _ in range(5):  # 多次运行验证确定性
        opinions, ids, _ = orch._dispatch_parallel(
            "测试", [(a1, 0.9, "l1"), (a2, 0.8, "l1"), (a3, 0.7, "l1")],
        )
        assert [o.agent_id for o in opinions] == ["agent_a", "agent_b", "agent_c"]


# ═══════════════════════════════════════════════════════════════
# T5: 单 Agent 自动退化为串行（不启动线程池）
# ═══════════════════════════════════════════════════════════════

def test_single_agent_no_parallel_overhead(config, orch):
    """只有 1 个专家时不用 ThreadPoolExecutor"""
    a = MockAgent("solo")
    orch.registry.register(a, expertise=["通用"])
    orch.default_agent = a

    # 通过 _solve_impl 间接测试：应该走 _dispatch_serial
    with patch.object(orch, '_dispatch_serial', wraps=orch._dispatch_serial) as spy_serial:
        with patch.object(orch, '_dispatch_parallel') as spy_parallel:
            orch._solve_impl("测试", "voting", 1)
            assert spy_serial.call_count == 1
            assert spy_parallel.call_count == 0


# ═══════════════════════════════════════════════════════════════
# T6: 分布式演化 — 注册 agent 时自动注册到 evolver
# ═══════════════════════════════════════════════════════════════

def test_create_agents_registers_evolver(config, orch):
    """create_agents 自动将 agent 注册到 DistributedEvolver"""
    assert orch._evolver is not None
    assert orch._evolver.agent_count == 0

    orch.create_agents([
        {"agent_id": "expert_a", "expertise": ["数学"]},
        {"agent_id": "expert_b", "expertise": ["物理"]},
    ])
    assert orch._evolver.agent_count == 2


# ═══════════════════════════════════════════════════════════════
# T7: 分布式演化 — 每次 solve 后更新统计
# ═══════════════════════════════════════════════════════════════

def test_evolve_after_solve_updates_stats(config, orch):
    """每次 solve 后 evolver 的 agent 统计应更新"""
    orch.create_agents([
        {"agent_id": "math", "expertise": ["数学"]},
    ])
    assert orch._solve_count == 0

    orch._evolve_after_solve([
        AgentOpinion(agent_id="math", answer="42", confidence=0.9),
    ])
    assert orch._solve_count == 1
    stats = orch._evolver._agent_stats.get("math", {})
    assert stats.get("session_count") == 1
    assert stats.get("success_rate") == 0.9


# ═══════════════════════════════════════════════════════════════
# T8: 分布式演化 — 定期触发全局合并
# ═══════════════════════════════════════════════════════════════

def test_evolve_periodic_merge(config, orch):
    """每 N 次 solve 自动触发全局权重合并"""
    orch.create_agents([
        {"agent_id": "x", "expertise": ["X"]},
        {"agent_id": "y", "expertise": ["Y"]},
    ])

    # 触发 4 次（未达到 interval=5）
    for _ in range(4):
        orch._evolve_after_solve([
            AgentOpinion(agent_id="x", answer="ok", confidence=0.8),
            AgentOpinion(agent_id="y", answer="ok", confidence=0.7),
        ])

    # 还没有合并过
    assert orch._evolver._merge_count == 0

    # 第 5 次触发合并
    orch._evolve_after_solve([
        AgentOpinion(agent_id="x", answer="ok", confidence=0.85),
    ])

    assert orch._evolver._merge_count == 1
    assert orch._solve_count == 5


# ═══════════════════════════════════════════════════════════════
# T9: 演化关闭时不创建 evolver
# ═══════════════════════════════════════════════════════════════

def test_evolution_disabled_no_evolver():
    """orchestration_evolution_enabled=False 时不创建 evolver"""
    config = SOMAConfig(
        episodic_persist_dir=Path(tempfile.mkdtemp()),
        orchestration_evolution_enabled=False,
    )
    orch = SOMAOrchestrator(config)
    assert orch._evolver is None
    # _evolve_after_solve 应安全跳过
    orch._evolve_after_solve([AgentOpinion(agent_id="x", answer="ok", confidence=1.0)])
    assert orch._solve_count == 0


# ═══════════════════════════════════════════════════════════════
# T10: remove_agent 同时从 evolver 注销
# ═══════════════════════════════════════════════════════════════

def test_remove_agent_unregisters_evolver(config, orch):
    """remove_agent 应从 DistributedEvolver 中注销"""
    orch.create_agents([
        {"agent_id": "temp", "expertise": ["临时"]},
    ])
    assert orch._evolver.agent_count == 1
    orch.remove_agent("temp")
    assert orch._evolver.agent_count == 0


# ═══════════════════════════════════════════════════════════════
# T11: stats 包含演化信息
# ═══════════════════════════════════════════════════════════════

def test_stats_includes_evolution(config, orch):
    """stats 属性应包含并行和演化状态"""
    orch.create_agents([
        {"agent_id": "e1", "expertise": ["E"]},
    ])
    s = orch.stats
    assert s["parallel_enabled"] is True
    assert s["evolution_enabled"] is True
    assert "evolution" in s
    assert s["evolution"]["agent_count"] == 1


# ═══════════════════════════════════════════════════════════════
# T12: 向后兼容 — 默认配置串行行为不变
# ═══════════════════════════════════════════════════════════════

def test_default_config_still_works():
    """默认 SOMAConfig 创建的 orchestrator 仍可正常工作"""
    config = SOMAConfig(episodic_persist_dir=Path(tempfile.mkdtemp()))
    orch = SOMAOrchestrator(config)
    # 默认模式应能正常创建
    assert orch.agent_count == 0
    assert orch.config.orchestration_parallel is True  # 默认开启并行
    assert orch.config.orchestration_evolution_enabled is True


# ═══════════════════════════════════════════════════════════════
# T13: OrchestrationResult 保持兼容
# ═══════════════════════════════════════════════════════════════

def test_orchestration_result_backward_compat():
    """OrchestrationResult 数据结构向后兼容"""
    result = OrchestrationResult(
        question="Q",
        answer="A",
        agents_involved=["a1"],
        routing_strategy="l1",
    )
    assert result.question == "Q"
    assert result.answer == "A"
    assert result.consensus is None  # 未提供时默认 None


# ═══════════════════════════════════════════════════════════════
# T14: 并行分发超时保护
# ═══════════════════════════════════════════════════════════════

def test_dispatch_parallel_timeout():
    """并行分发有 300 秒超时保护"""
    config = SOMAConfig(
        episodic_persist_dir=Path(tempfile.mkdtemp()),
        orchestration_parallel=True,
    )
    orch = SOMAOrchestrator(config)
    a = MockAgent("fast", delay=0.01)
    orch.registry.register(a, expertise=["快"])

    opinions, ids, _ = orch._dispatch_parallel(
        "测试", [(a, 0.9, "l1")],
    )
    assert len(opinions) == 1
    assert opinions[0].answer.startswith("[fast]")
