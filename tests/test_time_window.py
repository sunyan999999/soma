"""v0.4.0 时间窗口过滤测试 — 验证 max_age_days 正确排除远古记忆"""

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
    """注入一条指定天数的旧记忆（绕过去重）"""
    import json
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
    """情节记忆 30 天时间窗口测试"""

    def test_recent_memory_visible(self, ep_store):
        ep_store.add("今天的记忆")
        results = ep_store.query_by_keywords(["今天"])
        assert len(results) == 1

    def test_old_memory_excluded(self, ep_store):
        _inject_old_episodic(ep_store, "40天前的旧闻", 40)
        results = ep_store.query_by_keywords(["40天前", "旧闻"])
        assert len(results) == 0

    def test_custom_max_age_days(self, ep_store):
        _inject_old_episodic(ep_store, "60天前的记录", 60)
        # 默认30天：不返回
        r1 = ep_store.query_by_keywords(["60天前", "记录"])
        assert len(r1) == 0
        # 自定义90天：应返回
        r2 = ep_store.query_by_keywords(["60天前", "记录"], max_age_days=90)
        assert len(r2) == 1

    def test_like_fallback_time_window(self, ep_store):
        """短关键词 LIKE 兜底也受时间窗口限制"""
        _inject_old_episodic(ep_store, "上古记忆", 50)
        # "古" 单字 < 3字 → LIKE 兜底
        results = ep_store.query_by_keywords(["古"])
        assert len(results) == 0

    def test_boundary_just_within_window(self, ep_store):
        """刚好在窗口内的记忆应返回"""
        _inject_old_episodic(ep_store, "29天前的记忆", 29)
        results = ep_store.query_by_keywords(["29天前", "记忆"])
        assert len(results) == 1

    def test_user_isolation_still_works_with_window(self, ep_store):
        """时间窗口 + user_id 过滤器同时生效"""
        _inject_old_episodic(ep_store, "A的现代记忆", 5, user_id="user_a")
        _inject_old_episodic(ep_store, "B的现代记忆", 5, user_id="user_b")
        results = ep_store.query_by_keywords(["现代"], user_id="user_a")
        assert len(results) == 1
        assert "A的现代记忆" in results[0].content


class TestSemanticTimeWindow:
    """语义记忆 30 天时间窗口测试"""

    def _inject_old_triple(self, store, subj, pred, obj, days_ago, namespace=""):
        """注入一条指定天数的旧三元组"""
        ts = time.time() - days_ago * 86400.0
        store._conn.execute(
            "INSERT INTO semantic_triples (subject, predicate, object, confidence, created_at, namespace)"
            " VALUES (?, ?, ?, 1.0, ?, ?)",
            (subj, pred, obj, ts, namespace),
        )
        store._conn.commit()

    def test_old_triple_excluded(self, sem_store):
        self._inject_old_triple(sem_store, "古代", "包含", "旧知识", 40)
        results = sem_store.query_by_keywords(["古代"])
        assert len(results) == 0

    def test_recent_triple_visible(self, sem_store):
        sem_store.add_triple("现代", "包含", "新知识")
        results = sem_store.query_by_keywords(["现代"])
        assert len(results) == 1


class TestSkillTimeWindow:
    """技能记忆 90 天时间窗口测试（默认更长）"""

    def _inject_old_skill(self, store, name, pattern, days_ago, user_id=""):
        import json
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

    def test_60_day_skill_visible(self, sk_store):
        """技能默认窗口90天，60天内的技能应可见"""
        self._inject_old_skill(sk_store, "老技能", "pattern_60", 60)
        results = sk_store.query_by_keywords(["老技能"])
        assert len(results) == 1

    def test_100_day_skill_excluded(self, sk_store):
        """超过90天的技能应被排除"""
        self._inject_old_skill(sk_store, "远古技能", "pattern_100", 100)
        results = sk_store.query_by_keywords(["远古技能"])
        assert len(results) == 0

    def test_custom_max_age_skill(self, sk_store):
        self._inject_old_skill(sk_store, "120天技能", "pattern_120", 120)
        r1 = sk_store.query_by_keywords(["120天技能"])
        assert len(r1) == 0
        r2 = sk_store.query_by_keywords(["120天技能"], max_age_days=180)
        assert len(r2) == 1
