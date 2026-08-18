# -*- coding: utf-8 -*-
"""内容质量检测测试 — v2.0.9"""
from soma.content_quality import (
    assess_content_quality,
    _info_density,
    _marketing_density,
    _repetition_ratio,
    _fluff_ratio,
)

GOOD_TEXT = (
    "第一性原理认为应当回归事物的基本构成要素，从底层逻辑出发推导结论，"
    "避免被表象和既有假设所误导，这有助于在复杂问题中找到真正的因果链。"
)
MARKETING_TEXT = "限时抢购！全场五折！立即点击购买！错过今天再等一年！免费领取红包！"
FLUFF_TEXT = "我觉得吧这个东西呢怎么说呢反正就是很好的很棒的非常不错的大家都应该知道的这样一个东西。"
REPETITIVE_TEXT = "重复重复重复重复重复重复重复重复的重复内容重复重复。"
SHORT_TEXT = "短"


def test_good_text_high_quality():
    result = assess_content_quality(GOOD_TEXT)
    assert result["score"] >= 0.8, f"正常知识应高分, got {result['score']}"


def test_marketing_text_low_quality():
    result = assess_content_quality(MARKETING_TEXT)
    # 营销密度高 → 分数显著低
    assert result["metrics"]["marketing_density"] >= 0.6
    assert result["score"] < 0.6, f"营销内容应低分, got {result['score']}"


def test_fluff_text_detected():
    result = assess_content_quality(FLUFF_TEXT)
    assert result["metrics"]["fluff_ratio"] >= 0.3
    assert result["score"] < 0.9, f"空话应低于正常知识, got {result['score']}"


def test_short_text_zero():
    result = assess_content_quality(SHORT_TEXT)
    assert result["score"] == 0.0


def test_llm_failure_falls_back_to_local():
    """无 agent 时纯本地兜底"""
    result = assess_content_quality(GOOD_TEXT, agent=None, use_llm=True)
    assert result["llm_used"] is False
    assert result["score"] > 0  # 本地分兜底


def test_llm_used_when_available():
    """有 agent 且 use_llm 时调用 LLM"""
    from unittest.mock import MagicMock
    agent = MagicMock()
    agent._call_llm.return_value = '{"quality": 0.9, "is_factual": true, "reason": "内容合理"}'
    result = assess_content_quality(GOOD_TEXT, agent=agent, use_llm=True)
    assert result["llm_used"] is True


def test_info_density():
    assert _info_density(GOOD_TEXT) > 0.5
    assert _info_density("的 的 的 的 的 的 的 的") < 0.3


def test_marketing_density_detects():
    assert _marketing_density(MARKETING_TEXT) > 0.5
    assert _marketing_density(GOOD_TEXT) < 0.5


def test_repetition_ratio_detects():
    assert _repetition_ratio(REPETITIVE_TEXT) > 0.5
    assert _repetition_ratio(GOOD_TEXT) < 0.3


def test_fluff_ratio_detects():
    assert _fluff_ratio(FLUFF_TEXT) > 0.3
    assert _fluff_ratio(GOOD_TEXT) == 0.0
