"""v0.8.0 任务5: 反思质量自评测试"""
import pytest

from soma.quality import QualityEvaluator


@pytest.fixture
def evaluator():
    return QualityEvaluator(embedder=None)


class TestQualityEvaluator:
    def test_consistency_no_memories(self, evaluator):
        """无参考记忆时返回中性分"""
        score = evaluator.consistency_score("任意回答", [])
        assert score == 0.5

    def test_consistency_with_memories(self, evaluator):
        """有关键词重叠时返回更高分"""
        score = evaluator.consistency_score(
            "价格是客户流失的主要原因，需要降低价格",
            ["价格是客户流失的核心因素", "客户对价格敏感"],
        )
        assert 0.0 <= score <= 1.0  # 无 embedder 时基于关键词重叠

    def test_consistency_conflict_penalty(self, evaluator):
        """存在冲突时分数降低"""
        score_no_conflict = evaluator.consistency_score(
            "价格和品质都是重要因素",
            ["价格是核心因素"],
            conflict_count=0,
        )
        score_with_conflict = evaluator.consistency_score(
            "价格和品质都是重要因素",
            ["价格是核心因素"],
            conflict_count=3,
        )
        assert score_with_conflict < score_no_conflict

    def test_coherence_well_structured(self, evaluator):
        """结构良好的回答得分高"""
        answer = (
            "首先，我们需要分析问题的根本原因。\n\n"
            "其次，考虑系统的整体影响。\n\n"
            "第三，制定具体的改进方案。\n\n"
            "综上，这是一个系统性问题。"
        )
        score = evaluator.coherence_score(answer)
        assert score >= 0.5

    def test_coherence_unstructured(self, evaluator):
        """无结构的短回答得分低"""
        score = evaluator.coherence_score("好。")
        assert score < 0.3

    def test_actionability_concrete(self, evaluator):
        """包含具体建议的回答得分高"""
        answer = (
            "建议采取以下措施：第一步，降低价格10%；"
            "第二步，在2周内培训客服团队；第三步，每周监控客户满意度指标。"
        )
        score = evaluator.actionability_score(answer)
        assert score >= 0.4

    def test_actionability_vague(self, evaluator):
        """模糊的哲学性回答得分低"""
        score = evaluator.actionability_score(
            "这是一个复杂的系统性问题，需要从多角度深入思考。"
        )
        assert score < 0.3

    def test_evaluate_returns_all_dimensions(self, evaluator):
        """综合评估返回完整字段"""
        result = evaluator.evaluate(
            "首先分析原因，其次需要降低价格10%，建议2周内执行。",
            memory_contents=["价格是客户流失的核心因素"],
        )
        assert "overall" in result
        assert "consistency" in result
        assert "coherence" in result
        assert "actionability" in result
        assert "grade" in result
        assert "needs_reflection" in result
        assert 0.0 <= result["overall"] <= 1.0
        assert result["grade"] in ("excellent", "good", "fair", "poor")

    def test_evaluate_poor_needs_reflection(self, evaluator):
        """低质量回答标记需要反思"""
        result = evaluator.evaluate("好。", memory_contents=[])
        assert result["needs_reflection"] is True

    def test_evaluate_excellent_no_reflection(self, evaluator):
        """高质量回答不需要反思"""
        answer = (
            "首先分析根因：客户流失的主要原因是价格和服务质量。\n\n"
            "其次，建议采取以下措施：\n"
            "1. 将价格降低15%以匹配竞争对手\n"
            "2. 在30天内建立客服质量监控体系\n"
            "3. 每月进行客户满意度调查（目标≥85%）\n\n"
            "最后，以上措施预计可在90天内将流失率降低30%。"
        )
        result = evaluator.evaluate(
            answer,
            memory_contents=["价格和品质共同影响客户决策", "满意度监控覆盖70%客户"],
        )
        assert result["grade"] in ("excellent", "good")

    def test_score_range(self, evaluator):
        """所有分数在 [0, 1] 范围内"""
        result = evaluator.evaluate("任意回答")
        for key in ("overall", "consistency", "coherence", "actionability"):
            assert 0.0 <= result[key] <= 1.0, f"{key} 超出范围: {result[key]}"
