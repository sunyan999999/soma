import time
from datetime import datetime, timezone

from soma.base import MemoryUnit, Focus, ActivatedMemory


class TestMemoryUnit:
    def test_default_values(self):
        mu = MemoryUnit(content="测试记忆")
        assert mu.content == "测试记忆"
        assert mu.memory_type == "episodic"
        assert mu.importance == 0.5
        assert mu.access_count == 0
        assert len(mu.id) == 32  # uuid hex

    def test_custom_values(self):
        ts = datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp()
        mu = MemoryUnit(
            content="自定义",
            timestamp=ts,
            importance=0.9,
            access_count=5,
            context={"domain": "测试"},
            memory_type="semantic",
        )
        assert mu.timestamp == ts
        assert mu.importance == 0.9
        assert mu.access_count == 5
        assert mu.context == {"domain": "测试"}
        assert mu.memory_type == "semantic"

    def test_unique_ids(self):
        mu1 = MemoryUnit(content="a")
        mu2 = MemoryUnit(content="b")
        assert mu1.id != mu2.id

    def test_relevance_potential_fresh(self):
        """新鲜记忆关联潜力应较高"""
        mu = MemoryUnit(content="新鲜", importance=1.0)
        score = mu.relevance_potential()
        # 刚创建的，days ≈ 0，recency ≈ 1.0
        assert 0.9 < score <= 1.1

    def test_relevance_potential_decay(self):
        """老旧记忆关联潜力应衰减"""
        # 100 天前的记忆
        old_ts = datetime.now(timezone.utc).timestamp() - 100 * 86400
        mu = MemoryUnit(content="旧记忆", timestamp=old_ts, importance=1.0)
        score = mu.relevance_potential()
        # recency = 1/(1+100) ≈ 0.0099
        assert score < 0.02

    def test_access_count_boost(self):
        """高访问次数应有加成"""
        mu = MemoryUnit(content="热记忆", importance=1.0, access_count=100)
        base_mu = MemoryUnit(content="冷记忆", importance=1.0, access_count=0)
        assert mu.relevance_potential() > base_mu.relevance_potential()

    def test_importance_scaling(self):
        """importance 应线性影响得分"""
        mu_high = MemoryUnit(content="重要", importance=1.0)
        mu_low = MemoryUnit(content="不重要", importance=0.1)
        assert mu_high.relevance_potential() > mu_low.relevance_potential()


class TestFocus:
    def test_create_focus(self):
        f = Focus(
            law_id="first_principles",
            dimension="从第一性原理分析增长停滞",
            keywords=["本质", "增长", "停滞"],
            weight=0.9,
            rationale="问题中包含'为什么'触发词",
        )
        assert f.law_id == "first_principles"
        assert f.weight == 0.9
        assert len(f.keywords) == 3


class TestActivatedMemory:
    def test_create_activated(self):
        mu = MemoryUnit(content="激活的记忆")
        am = ActivatedMemory(
            memory=mu,
            activation_score=0.85,
            source="episodic",
            match_rationale="关键词匹配'增长'",
        )
        assert am.activation_score == 0.85
        assert am.source == "episodic"
        assert am.memory.content == "激活的记忆"
