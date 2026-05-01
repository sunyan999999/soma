"""v0.4.0 时间窗口测试 — 验证 max_age_days opt-in 过滤行为

SOMA 设计原则：记忆永久保存，时间窗口是可选过滤器而非默认行为。
近因衰减由指数公式 exp(-days/7) 自然实现，无需硬截断。
"""

import time

import pytest

from soma.memory.episodic import EpisodicStore
from soma.memory.semantic import SemanticStore
from soma.memory.skill import SkillStore


@pytest.fixture
def ep_store(tmp_path):
    s = EpisodicStore(tmp_path)
    yield s
    s.close()


@pytest.fixture
def sem_store(tmp_path):
    s = SemanticStore(tmp_path)
    yield s
    s.close()


@pytest.fixture
def sk_store(tmp_path):
    s = SkillStore(tmp_path)
    yield s
    s.close()


def _inject_old_episodic(store, content, days_ago, user_id=""):
    import uuid
    from datetime import datetime, timezone

    mid = uuid.uuid4().hex
    ts = datetime.now(timezone.utc).timestamp() - days_ago * 86400.0
    store._conn.execute(
        "INSERT INTO episodic_memories (id, content, content_hash, timestamp, importance, context_json, user_id)"
        " VALUES (?, ?, ?, ?, 0.5, '{}', ?)",
        (mid, content, f"hash_{mid}", ts, user_id),
    )
    store._conn.commit()
    return mid


class TestEpisodicTimeWindow:
    """情节记忆时间窗口测试 — opt-in 模式"""

    def test_recent_memory_always_visible(self, ep_store):
        ep_store.add("今天的记忆")
        results = ep_store.query_by_keywords(["今天"])
        assert len(results) == 1

    def test_old_memory_visible_by_default(self, ep_store):
        """默认不限时：远古记忆也应可召回"""
        _inject_old_episodic(ep_store, "40天前的旧闻", 40)
        results = ep_store.query_by_keywords(["40天前", "旧闻"])
        assert len(results) == 1  # 不限时，应该能找到

    def test_max_age_days_excludes_old(self, ep_store):
        """显式传入 max_age_days 时排除过期记忆"""
        _inject_old_episodic(ep_store, "40天前的旧闻", 40)
        results = ep_store.query_by_keywords(["40天前", "旧闻"], max_age_days=30)
        assert len(results) == 0  # 40天 > 30天窗口

    def test_custom_max_age_days(self, ep_store):
        _inject_old_episodic(ep_store, "60天前的记录", 60)
        # 默认不限时：能找到
        r1 = ep_store.query_by_keywords(["60天前", "记录"])
        assert len(r1) == 1
        # 30天窗口：找不到
        r2 = ep_store.query_by_keywords(["60天前", "记录"], max_age_days=30)
        assert len(r2) == 0
        # 90天窗口：能找到
        r3 = ep_store.query_by_keywords(["60天前", "记录"], max_age_days=90)
        assert len(r3) == 1

    def test_like_fallback_respects_time_window(self, ep_store):
        """短关键词 LIKE 兜底在传入 max_age_days 时过滤"""
        _inject_old_episodic(ep_store, "上古记忆", 50)
        # "古" 单字 < 3字 → LIKE 兜底，默认不限时
        r1 = ep_store.query_by_keywords(["古"])
        assert len(r1) == 1
        # 传入 max_age_days=30 应排除
        r2 = ep_store.query_by_keywords(["古"], max_age_days=30)
        assert len(r2) == 0

    def test_boundary_just_within_window(self, ep_store):
        """传入窗口时，刚好在窗口内应返回"""
        _inject_old_episodic(ep_store, "29天前的记忆", 29)
        results = ep_store.query_by_keywords(["29天前", "记忆"], max_age_days=30)
        assert len(results) == 1

    def test_user_isolation_with_window(self, ep_store):
        """时间窗口 + user_id 同时生效"""
        _inject_old_episodic(ep_store, "A的记忆", 5, user_id="user_a")
        _inject_old_episodic(ep_store, "B的记忆", 5, user_id="user_b")
        results = ep_store.query_by_keywords(["记忆"], user_id="user_a", max_age_days=30)
        assert len(results) == 1
        assert "A的记忆" in results[0].content


class TestSemanticTimeWindow:
    """语义记忆时间窗口测试 — opt-in 模式"""

    def _inject_old_triple(self, store, subj, pred, obj, days_ago, namespace=""):
        ts = time.time() - days_ago * 86400.0
        store._conn.execute(
            "INSERT INTO semantic_triples (subject, predicate, object, confidence, created_at, namespace)"
            " VALUES (?, ?, ?, 1.0, ?, ?)",
            (subj, pred, obj, ts, namespace),
        )
        store._conn.commit()

    def test_old_triple_visible_by_default(self, sem_store):
        """默认不限时，远古三元组也可召回"""
        self._inject_old_triple(sem_store, "古代", "包含", "旧知识", 40)
        results = sem_store.query_by_keywords(["古代"])
        assert len(results) == 1

    def test_old_triple_excluded_with_window(self, sem_store):
        """传入 max_age_days 时排除过期三元组"""
        self._inject_old_triple(sem_store, "古代", "包含", "旧知识", 40)
        results = sem_store.query_by_keywords(["古代"], max_age_days=30)
        assert len(results) == 0

    def test_recent_triple_visible(self, sem_store):
        sem_store.add_triple("现代", "包含", "新知识")
        results = sem_store.query_by_keywords(["现代"])
        assert len(results) == 1


class TestSkillTimeWindow:
    """技能记忆时间窗口测试 — 默认永久，opt-in 过滤"""

    def _inject_old_skill(self, store, name, pattern, days_ago, user_id=""):
        import uuid
        from datetime import datetime, timezone

        sid = uuid.uuid4().hex
        ts = datetime.now(timezone.utc).timestamp() - days_ago * 86400.0
        store._conn.execute(
            "INSERT INTO skills (id, name, pattern, context_json, created_at, user_id)"
            " VALUES (?, ?, ?, '{}', ?, ?)",
            (sid, name, pattern, ts, user_id),
        )
        store._conn.commit()

    def test_skill_permanent_by_default(self, sk_store):
        """技能默认永不过期（SOMA 设计初衷：技能是永久积累的思维模式）"""
        self._inject_old_skill(sk_store, "古老技能", "pattern_200", 200)
        results = sk_store.query_by_keywords(["古老技能"])
        assert len(results) == 1

    def test_skill_time_window_opt_in(self, sk_store):
        """传入 max_age_days 时启用时间窗口过滤"""
        self._inject_old_skill(sk_store, "过期技能", "pattern_100", 100)
        results = sk_store.query_by_keywords(["过期技能"], max_age_days=90)
        assert len(results) == 0

    def test_custom_max_age_skill(self, sk_store):
        self._inject_old_skill(sk_store, "120天技能", "pattern_120", 120)
        # 默认不限时
        r1 = sk_store.query_by_keywords(["120天技能"])
        assert len(r1) == 1
        # 90天窗口：排除
        r2 = sk_store.query_by_keywords(["120天技能"], max_age_days=90)
        assert len(r2) == 0
        # 180天窗口：包含
        r3 = sk_store.query_by_keywords(["120天技能"], max_age_days=180)
        assert len(r3) == 1
