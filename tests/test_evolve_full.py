from pathlib import Path
from unittest.mock import MagicMock

import pytest

from soma.evolve import MetaEvolver
from soma.base import Focus, ActivatedMemory, MemoryUnit


class FakeLaw:
    def __init__(self, id_, name, weight):
        self.id = id_
        self.name = name
        self.weight = weight


class FakeEngine:
    """简易 Engine 替身，持有 laws 列表"""
    def __init__(self, laws=None):
        self.laws = laws or [
            FakeLaw("first_principles", "第一性原理", 0.9),
            FakeLaw("systems_thinking", "系统思维", 0.85),
            FakeLaw("contradiction", "矛盾分析", 0.8),
            FakeLaw("pareto", "二八法则", 0.75),
        ]
        self.laws.sort(key=lambda law: law.weight, reverse=True)


def make_focus(law_id, weight=0.9):
    return Focus(
        law_id=law_id,
        dimension=f"测试维度:{law_id}",
        keywords=["测试"],
        weight=weight,
        rationale="测试",
    )


def make_activated(memory_id="m1", source="episodic", domain="分析"):
    mem = MemoryUnit(
        id=memory_id, content="测试记忆",
        context={"domain": domain, "type": "案例"},
    )
    return ActivatedMemory(
        memory=mem,
        activation_score=0.8,
        source=source,
        match_rationale="匹配",
    )


@pytest.fixture
def evolver(tmp_path: Path):
    return MetaEvolver(FakeEngine(), persist_dir=tmp_path)


@pytest.fixture
def mock_memory():
    """带 mock SkillStore 的 MemoryCore"""
    mm = MagicMock()
    mm.skill.add_skill.return_value = "skill_id_123"
    return mm


@pytest.fixture
def evolver_with_memory(mock_memory, tmp_path: Path):
    return MetaEvolver(FakeEngine(), memory_core=mock_memory, persist_dir=tmp_path)


class TestAdjustWeight:
    def test_adjust_valid_law(self, evolver):
        assert evolver.adjust_weight("first_principles", 0.5)
        assert evolver.get_weights()["first_principles"] == 0.5

    def test_adjust_clamps_to_bounds(self, evolver):
        assert evolver.adjust_weight("first_principles", 1.5)
        assert evolver.get_weights()["first_principles"] == 1.0

        assert evolver.adjust_weight("first_principles", -0.3)
        assert evolver.get_weights()["first_principles"] == 0.0

    def test_adjust_nonexistent_law(self, evolver):
        assert not evolver.adjust_weight("nonexistent", 0.5)

    def test_adjust_reorders_laws(self, evolver):
        # 把最高权重的 law 降到最低
        evolver.adjust_weight("first_principles", 0.1)
        assert evolver.engine.laws[-1].id == "first_principles"


class TestEvolve:
    def test_evolve_boost_high_success_rate(self, evolver):
        """成功率 > 0.7 应 +0.02"""
        evolver.set_current_context([make_focus("first_principles")], [])
        for _ in range(5):
            evolver.reflect("t1", "success")

        changes = evolver.evolve()
        assert len(changes) >= 1
        change = changes[0]
        assert change["old_weight"] == 0.9
        assert change["new_weight"] == 0.92
        assert change["success_rate"] == 1.0

    def test_evolve_penalize_low_success_rate(self, evolver):
        """成功率 < 0.3 应 -0.02"""
        # 先手动降低权重以便观察变化
        evolver.adjust_weight("systems_thinking", 0.5)

        evolver.set_current_context([make_focus("systems_thinking")], [])
        for _ in range(2):
            evolver.reflect("t1", "success")
        for _ in range(6):
            evolver.reflect("t2", "failure")

        changes = evolver.evolve()
        assert len(changes) >= 1
        change = changes[0]
        assert change["success_rate"] < 0.3
        assert change["new_weight"] < change["old_weight"]

    def test_evolve_not_enough_data(self, evolver):
        """不足 3 个样本不触发进化"""
        evolver.set_current_context([make_focus("first_principles")], [])
        evolver.reflect("t1", "success")
        evolver.reflect("t2", "success")

        changes = evolver.evolve()
        assert len(changes) == 0

    def test_evolve_clamps_at_one(self, evolver):
        """权重已接近 1.0 时不溢出"""
        evolver.adjust_weight("first_principles", 0.99)
        evolver.set_current_context([make_focus("first_principles")], [])
        for _ in range(5):
            evolver.reflect("t1", "success")

        changes = evolver.evolve()
        assert changes[0]["new_weight"] == 1.0

    def test_evolve_resets_stats_after(self, evolver):
        """进化后统计计数器归零"""
        evolver.set_current_context([make_focus("first_principles")], [])
        for _ in range(5):
            evolver.reflect("t1", "success")
        evolver.evolve()

        stats = evolver.get_stats()
        assert stats.get("first_principles", {}).get("total", 1) == 0


class TestSkillSolidification:
    def test_solidifies_after_three_successes(self, evolver_with_memory, mock_memory):
        """同一 (law_id, domain) 成功 3 次后固化为技能"""
        evo = evolver_with_memory
        am = make_activated(domain="分析")

        for i in range(3):
            evo.set_current_context([make_focus("first_principles")], [am])
            evo.reflect(f"task_{i}", "success")

        changes = evo.evolve()
        skill_changes = [c for c in changes if c.get("type") == "skill_solidified"]
        assert len(skill_changes) == 1
        assert skill_changes[0]["law_id"] == "first_principles"
        assert skill_changes[0]["domain"] == "分析"
        assert skill_changes[0]["occurrences"] == 3
        mock_memory.skill.add_skill.assert_called_once()

    def test_no_solidify_without_memory_core(self, evolver):
        """无 memory_core 时不固化技能"""
        am = make_activated(domain="分析")
        for i in range(3):
            evolver.set_current_context([make_focus("first_principles")], [am])
            evolver.reflect(f"task_{i}", "success")

        changes = evolver.evolve()
        skill_changes = [c for c in changes if c.get("type") == "skill_solidified"]
        assert len(skill_changes) == 0

    def test_no_solidify_below_threshold(self, evolver_with_memory):
        """不足 3 次不固化"""
        am = make_activated(domain="分析")
        for i in range(2):
            evolver_with_memory.set_current_context([make_focus("first_principles")], [am])
            evolver_with_memory.reflect(f"task_{i}", "success")

        changes = evolver_with_memory.evolve()
        skill_changes = [c for c in changes if c.get("type") == "skill_solidified"]
        assert len(skill_changes) == 0


class TestReflectTracking:
    def test_freeform_outcome_not_tracked(self, evolver):
        """自由文本 outcome 不参与统计"""
        evolver.set_current_context([make_focus("first_principles")], [])
        evolver.reflect("t1", "这是一般反馈")
        evolver.reflect("t2", "还可以")

        stats = evolver.get_stats()
        assert stats == {}

    def test_success_and_failure_tracked(self, evolver):
        evolver.set_current_context([make_focus("first_principles")], [])
        evolver.reflect("t1", "success")
        evolver.reflect("t2", "success")
        evolver.reflect("t3", "failure")

        stats = evolver.get_stats()
        assert stats["first_principles"]["successes"] == 2
        assert stats["first_principles"]["failures"] == 1
        assert stats["first_principles"]["total"] == 3
        assert stats["first_principles"]["success_rate"] == pytest.approx(0.667, abs=0.01)

    def test_chinese_outcome_tracked(self, evolver):
        """中文 '成功'/'失败' 同样追踪"""
        evolver.set_current_context([make_focus("pareto")], [])
        evolver.reflect("t1", "成功")
        evolver.reflect("t2", "失败")

        stats = evolver.get_stats()
        assert stats["pareto"]["successes"] == 1
        assert stats["pareto"]["failures"] == 1

    def test_multi_focus_tracking(self, evolver):
        """多个 Focus 时每个 law 独立计数"""
        foci = [make_focus("first_principles"), make_focus("systems_thinking")]
        evolver.set_current_context(foci, [])
        evolver.reflect("t1", "success")

        stats = evolver.get_stats()
        assert stats["first_principles"]["successes"] == 1
        assert stats["systems_thinking"]["successes"] == 1

    def test_no_context_no_tracking(self, evolver):
        """未设置上下文时不追踪（不崩溃）"""
        evolver.reflect("t1", "success")
        stats = evolver.get_stats()
        assert stats == {}


class TestGetWeights:
    def test_returns_all_law_weights(self, evolver):
        w = evolver.get_weights()
        assert w["first_principles"] == 0.9
        assert w["systems_thinking"] == 0.85
        assert len(w) == 4

    def test_reflects_manual_changes(self, evolver):
        evolver.adjust_weight("pareto", 0.33)
        w = evolver.get_weights()
        assert w["pareto"] == 0.33


class TestClearLog:
    def test_clear_resets_all_state(self, evolver):
        evolver.set_current_context([make_focus("first_principles")], [])
        evolver.reflect("t1", "success")
        evolver.reflect("t2", "success")
        evolver.reflect("t3", "success")
        am = make_activated()
        evolver.set_current_context([make_focus("first_principles")], [am])
        evolver.reflect("t4", "success")

        evolver.clear_log()

        assert len(evolver.get_log()) == 0
        assert evolver.get_stats() == {}
        # evolve after clear should produce no changes
        changes = evolver.evolve()
        assert len(changes) == 0
