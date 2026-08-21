# -*- coding: utf-8 -*-
"""全自主认知循环测试 — v2.0.10 run_autonomous"""
import pytest

from soma import SOMA


@pytest.fixture
def soma(tmp_path):
    s = SOMA(persist_dir=str(tmp_path), llm="mock")
    yield s
    s.close()


def test_run_autonomous_basic(soma):
    """无 LLM 时跑满轮数，不提前误停"""
    r = soma.run_autonomous("简单分析目标", max_rounds=2)
    assert r["round_count"] == 2
    assert r["completed"] is False
    assert "final_answer" in r
    assert len(r["rounds"]) == 2


def test_run_autonomous_feedback_fn_completes(soma):
    """外部反馈函数在第一轮判定完成"""
    calls = [0]

    def fb(round_result, execution):
        calls[0] += 1
        return calls[0] >= 1

    r = soma.run_autonomous("测试目标", max_rounds=3, feedback_fn=fb)
    assert r["completed"] is True
    assert r["round_count"] == 1


def test_run_autonomous_feedback_fn_never_completes(soma):
    """外部反馈函数始终不完成 → 跑满"""
    r = soma.run_autonomous(
        "测试目标", max_rounds=2,
        feedback_fn=lambda a, b: False,
    )
    assert r["round_count"] == 2


def test_check_goal_complete_feedback_fn(soma):
    assert soma._check_goal_complete("目标", {}, {}, feedback_fn=lambda a, b: True) is True
    assert soma._check_goal_complete("目标", {}, {}, feedback_fn=lambda a, b: False) is False


def test_check_goal_complete_llm_true(soma):
    soma._config.llm_api_key = "fake-key"
    soma._agent._call_llm = lambda prompt, uid: "true"
    assert soma._check_goal_complete("目标", {"final_answer": "x"}, {"executed": ["y"]}) is True


def test_check_goal_complete_llm_false(soma):
    soma._config.llm_api_key = "fake-key"
    soma._agent._call_llm = lambda prompt, uid: "false"
    assert soma._check_goal_complete("目标", {"final_answer": "x"}, {"executed": ["y"]}) is False


def test_has_llm():
    soma = SOMA(persist_dir="soma_data", llm="mock")
    assert soma._has_llm() is False
    soma._config.llm_api_key = "k"
    assert soma._has_llm() is True
    soma.close()
