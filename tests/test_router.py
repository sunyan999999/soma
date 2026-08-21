# -*- coding: utf-8 -*-
"""专家路由器测试 — L1/L2/fallback 三层路由"""
from unittest.mock import MagicMock
import numpy as np

from soma.multi_agent.router import ExpertRouter, _extract_domain_keywords


class FakeAgent:
    def __init__(self, agent_id):
        self.agent_id = agent_id


class FakeInfo:
    def __init__(self, agent_id, expertise, description=""):
        self.agent_id = agent_id
        self.expertise = expertise
        self.description = description


class FakeRegistry:
    def __init__(self, agents=None, default=None):
        self._entries = agents or []  # [(agent, info)]
        self._default = default

    def find_experts(self, domain, min_score=0.0):
        results = []
        for agent, info in self._entries:
            if domain in info.expertise or any(domain in e for e in info.expertise):
                results.append((agent, 0.9))
        return results

    def get_default(self):
        return self._default

    def list_agents(self):
        return [info for _, info in self._entries]

    def get(self, agent_id):
        for agent, _ in self._entries:
            if agent.agent_id == agent_id:
                return agent
        return None


def _build_registry():
    tech = FakeAgent("tech")
    law = FakeAgent("law")
    default = FakeAgent("default_agent")
    return FakeRegistry(
        agents=[
            (tech, FakeInfo("tech", ["技术"], "技术专家")),
            (law, FakeInfo("law", ["法律"], "法律专家")),
        ],
        default=default,
    )


def test_extract_domain_keywords():
    scores = _extract_domain_keywords("这个 API 架构有性能问题需要重构代码")
    assert "技术" in scores
    assert scores["技术"] >= 3


def test_extract_domain_keywords_english():
    scores = _extract_domain_keywords("The database deploy failed with a bug in the algorithm")
    assert "技术" in scores


def test_route_l1_match():
    router = ExpertRouter(_build_registry())
    agent, confidence, strategy = router.route("帮我写一段 Python 代码处理数据库并发")
    assert agent.agent_id == "tech"
    assert strategy == "l1"
    assert confidence > 0
    assert router.l1_hits == 1
    assert router.route_count == 1


def test_route_l1_law_match():
    router = ExpertRouter(_build_registry())
    agent, _, strategy = router.route("这个合同条款涉及知识产权和专利纠纷")
    assert agent.agent_id == "law"
    assert strategy == "l1"


def test_route_fallback_when_no_domain():
    router = ExpertRouter(_build_registry())
    agent, confidence, strategy = router.route("今天天气不错，适合散步")
    assert agent.agent_id == "default_agent"
    assert strategy == "fallback"
    assert confidence == 0.1
    assert router.fallbacks == 1


def test_route_l2_with_embedder():
    """L1 无匹配时走 L2 语义路由"""
    embedder = MagicMock()
    # encode: 含"系统/设计"视为技术方向向量，否则其他方向
    def _encode(text):
        if any(w in text for w in ("系统", "设计", "技术")):
            return np.array([1.0, 0.0], dtype=np.float32)
        return np.array([0.0, 1.0], dtype=np.float32)
    embedder.encode.side_effect = _encode
    registry = _build_registry()
    # 问题不含任何领域关键词（避免 L1），但 embedder 让技术专家高分
    agent, confidence, strategy = ExpertRouter(registry, embedder=embedder).route(
        "一个需要深度设计的系统性问题"
    )
    assert agent is not None
    assert strategy == "l2"
    assert confidence > 0


def test_route_l1_low_confidence_fallback():
    """L1 弱命中（confidence 低于 min）→ 回退"""
    router = ExpertRouter(_build_registry())
    # "代码"只命中技术1个关键词 → confidence 1/3 < 0.9
    agent, _, strategy = router.route("帮我写代码", min_confidence=0.9)
    assert agent.agent_id == "default_agent"
    assert strategy == "fallback"


def test_route_l1_no_expert_for_domain():
    """领域命中但无对应专家 → 回退"""
    registry = FakeRegistry(agents=[(FakeAgent("law"), FakeInfo("law", ["法律"]))], default=FakeAgent("d"))
    router = ExpertRouter(registry)
    # "股票"命中金融领域，但无金融专家
    agent, _, strategy = router.route("股票投资策略")
    assert strategy == "fallback"
    assert agent.agent_id == "d"


def test_semantic_similarity():
    embedder = MagicMock()
    embedder.encode.side_effect = lambda t: np.array([1.0, 0.0], dtype=np.float32)
    router = ExpertRouter(FakeRegistry(), embedder=embedder)
    sim = router._semantic_similarity("a", "b")
    assert sim == 1.0  # 同向量余弦 = 1

    embedder.encode.side_effect = lambda t: np.array([0.0, 0.0], dtype=np.float32)
    assert router._semantic_similarity("a", "b") == 0.0  # 零向量


def test_route_no_fallback_raises():
    registry = FakeRegistry(agents=[(FakeAgent("tech"), FakeInfo("tech", ["技术"]))], default=None)
    router = ExpertRouter(registry)
    try:
        router.route("天气不错", allow_fallback=False)
        assert False, "应抛出 RuntimeError"
    except RuntimeError as e:
        assert "没有可用的 agent" in str(e)


def test_route_multi_returns_multiple():
    router = ExpertRouter(_build_registry())
    results = router.route_multi("代码架构和合同法律问题都需要分析", top_k=3)
    assert len(results) >= 1
    assert all(isinstance(r, tuple) and len(r) == 3 for r in results)


def test_route_multi_fallback():
    router = ExpertRouter(_build_registry())
    results = router.route_multi("毫无领域特征的问题描述", top_k=2)
    assert results  # fallback 到默认 agent
    assert results[0][2] in ("l1", "fallback")


def test_stats():
    router = ExpertRouter(_build_registry())
    router.route("帮我写代码")
    stats = router.stats
    assert stats["route_count"] == 1
    assert 0 <= stats["l1_hit_rate"] <= 1
    assert 0 <= stats["fallback_rate"] <= 1
