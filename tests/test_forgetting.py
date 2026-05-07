"""主动遗忘引擎测试"""
import time
import pytest
from soma.memory.forgetting import (
    ForgettingEngine,
    DECAY_RATES,
    DECAY_IMPORTANCE_BONUS,
)


class TestDecayRates:
    """验证各类别衰减率配置合理性"""

    def test_strategy_lowest_decay(self):
        """策略类衰减率最低——保留最久"""
        assert DECAY_RATES["strategy"] < DECAY_RATES["fact"]
        assert DECAY_RATES["strategy"] < DECAY_RATES["insight"]
        assert DECAY_RATES["strategy"] < DECAY_RATES["external"]

    def test_external_highest_decay(self):
        """外部知识衰减率最高——较快遗忘"""
        assert DECAY_RATES["external"] > DECAY_RATES["strategy"]
        assert DECAY_RATES["external"] > DECAY_RATES["fact"]

    def test_all_positive(self):
        for k, v in DECAY_RATES.items():
            assert v > 0, f"{k} 衰减率应为正数"


class TestComputeMemoryStrength:
    @pytest.fixture
    def engine(self, tmp_path):
        import sqlite3
        db = tmp_path / "test.db"
        conn = sqlite3.connect(str(db))
        e = ForgettingEngine(conn)
        yield e
        conn.close()

    def test_fresh_memory_near_importance(self, engine):
        """刚创建的记忆强度接近importance"""
        now = time.time()
        strength = engine.compute_memory_strength(
            importance=0.8, timestamp=now, access_count=0,
        )
        assert strength == pytest.approx(0.8, rel=0.1)

    def test_old_memory_decayed(self, engine):
        """90天前的记忆明显衰减"""
        ninety_days_ago = time.time() - 90 * 86400
        strength = engine.compute_memory_strength(
            importance=0.8, timestamp=ninety_days_ago, access_count=0,
        )
        assert strength < 0.3

    def test_access_count_boosts_strength(self, engine):
        """高访问次数提升记忆强度"""
        ninety_days_ago = time.time() - 90 * 86400
        low_access = engine.compute_memory_strength(
            importance=0.8, timestamp=ninety_days_ago, access_count=0,
        )
        high_access = engine.compute_memory_strength(
            importance=0.8, timestamp=ninety_days_ago, access_count=10,
        )
        assert high_access > low_access

    def test_strategy_decays_slower_than_default(self, engine):
        """策略类记忆衰减慢于默认"""
        ninety_days_ago = time.time() - 90 * 86400
        strategy_strength = engine.compute_memory_strength(
            importance=0.8, timestamp=ninety_days_ago, access_count=0,
            memory_type="strategy",
        )
        default_strength = engine.compute_memory_strength(
            importance=0.8, timestamp=ninety_days_ago, access_count=0,
            memory_type="default",
        )
        assert strategy_strength > default_strength

    def test_negative_importance_returns_negative(self, engine):
        """负importance直接返回负值（标记为废弃）"""
        strength = engine.compute_memory_strength(
            importance=-0.1, timestamp=time.time(), access_count=0,
        )
        assert strength < 0

    def test_zero_importance_decays_to_zero(self, engine):
        """importance=0 的记忆强度为 0"""
        strength = engine.compute_memory_strength(
            importance=0.0, timestamp=time.time(), access_count=0,
        )
        assert strength == pytest.approx(0.0)

    def test_importance_bonus_applied(self, engine):
        """类别重要性加成被应用"""
        now = time.time()
        base = engine.compute_memory_strength(
            importance=0.5, timestamp=now, access_count=0, memory_type="default",
        )
        boosted = engine.compute_memory_strength(
            importance=0.5, timestamp=now, access_count=0, memory_type="strategy",
        )
        # strategy有+0.10加成，effective importance更高
        assert boosted > base

    def test_importance_capped_at_one(self, engine):
        """importance加成后不超过1.0"""
        now = time.time()
        strength = engine.compute_memory_strength(
            importance=1.0, timestamp=now, access_count=0, memory_type="strategy",
        )
        assert strength <= 1.0


class TestForgettingEngine:
    @pytest.fixture
    def store(self, tmp_path):
        from soma.memory.episodic import EpisodicStore
        s = EpisodicStore(tmp_path)
        yield s
        s.close()

    def test_archive_table_created(self, store):
        engine = ForgettingEngine(store._conn)
        tables = store._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='episodic_archived'"
        ).fetchall()
        assert len(tables) == 1

    def test_decay_forgetting(self, store):
        """衰减记忆被归档"""
        # 插入很旧且低importance的记忆
        old_ts = time.time() - 120 * 86400  # 120天前
        store._conn.execute(
            """INSERT INTO episodic_memories (id, content, content_hash, timestamp, importance, user_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ("test_old_1", "古老的低价值记忆", "hash1", old_ts, 0.2, ""),
        )
        store._conn.commit()

        engine = ForgettingEngine(store._conn)
        result = engine.run_forgetting_pass(max_archive=50)

        assert result["decayed"] >= 1

        # 检查已归档
        archived = store._conn.execute(
            "SELECT * FROM episodic_archived WHERE id = 'test_old_1'"
        ).fetchone()
        assert archived is not None
        assert archived["archive_reason"] == "decay"

    def test_cold_memory_forgetting(self, store):
        """冷记忆（30天未访问 + 低importance）被归档"""
        cold_ts = time.time() - 35 * 86400
        store._conn.execute(
            """INSERT INTO episodic_memories (id, content, content_hash, timestamp, importance, access_count, user_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("test_cold_1", "从未被访问的冷记忆", "hash_cold", cold_ts, 0.3, 0, ""),
        )
        store._conn.commit()

        engine = ForgettingEngine(store._conn)
        result = engine.run_forgetting_pass(max_archive=50)

        assert result["cold"] >= 1

        archived = store._conn.execute(
            "SELECT * FROM episodic_archived WHERE id = 'test_cold_1'"
        ).fetchone()
        assert archived is not None
        assert archived["archive_reason"] == "cold"

    def test_redundancy_cleanup(self, store):
        """合并废记忆（importance=-0.1且超过14天）被永久删除"""
        old_ts = time.time() - 20 * 86400
        store._conn.execute(
            """INSERT INTO episodic_memories (id, content, content_hash, timestamp, importance, user_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ("test_waste_1", "合并后的废记忆", "hash_waste", old_ts, -0.1, ""),
        )
        store._conn.commit()

        engine = ForgettingEngine(store._conn)
        result = engine.run_forgetting_pass(max_archive=50)

        assert result["cleaned"] >= 1

        # 确认已从主表删除
        row = store._conn.execute(
            "SELECT * FROM episodic_memories WHERE id = 'test_waste_1'"
        ).fetchone()
        assert row is None

    def test_high_importance_not_forgotten(self, store):
        """高importance记忆不被遗忘"""
        old_ts = time.time() - 120 * 86400
        store._conn.execute(
            """INSERT INTO episodic_memories (id, content, content_hash, timestamp, importance, user_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ("test_keep_1", "重要的古老记忆", "hash_keep", old_ts, 0.9, ""),
        )
        store._conn.commit()

        engine = ForgettingEngine(store._conn)
        result = engine.run_forgetting_pass(max_archive=50)

        # 高importance记忆不应被归档
        archived = store._conn.execute(
            "SELECT * FROM episodic_archived WHERE id = 'test_keep_1'"
        ).fetchone()
        assert archived is None

    def test_archive_respects_user_id(self, store):
        """归档仅作用于指定user_id"""
        old_ts = time.time() - 120 * 86400
        store._conn.executemany(
            """INSERT INTO episodic_memories (id, content, content_hash, timestamp, importance, user_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                ("test_ua_1", "用户A的旧记忆", "hash_ua", old_ts, 0.2, "user_a"),
                ("test_ub_1", "用户B的旧记忆", "hash_ub", old_ts, 0.2, "user_b"),
            ],
        )
        store._conn.commit()

        engine = ForgettingEngine(store._conn)
        # 只对user_a执行遗忘
        result = engine.run_forgetting_pass(user_id="user_a", max_archive=50)

        # user_a的记忆被归档
        archived_a = store._conn.execute(
            "SELECT * FROM episodic_archived WHERE id = 'test_ua_1'"
        ).fetchone()
        assert archived_a is not None

        # user_b的记忆仍在主表
        active_b = store._conn.execute(
            "SELECT * FROM episodic_memories WHERE id = 'test_ub_1'"
        ).fetchone()
        assert active_b is not None

    def test_recall_archived(self, store):
        """浏览和搜索归档记忆"""
        engine = ForgettingEngine(store._conn)  # 先创建引擎以建表
        now = time.time()
        store._conn.execute(
            """INSERT INTO episodic_archived
               (id, content, content_hash, timestamp, importance, user_id, archived_at, archive_reason)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("test_arch_1", "关于第一性原理的归档记忆", "hash_ar", now - 86400, 0.5, "", now, "decay"),
        )
        store._conn.commit()

        # 按关键词搜索
        results = engine.recall_archived(query="第一性原理")
        assert len(results) >= 1
        assert results[0]["id"] == "test_arch_1"

        # 无关键词浏览最近
        results_all = engine.recall_archived(top_k=5)
        assert len(results_all) >= 1

    def test_restore_from_archive(self, store):
        """从归档恢复记忆"""
        engine = ForgettingEngine(store._conn)  # 先创建引擎以建表
        now = time.time()
        store._conn.execute(
            """INSERT INTO episodic_archived
               (id, content, content_hash, timestamp, importance, access_count,
                context_json, memory_type, user_id, session_id, archived_at, archive_reason)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("test_rest_1", "可恢复的记忆", "hash_res", now - 86400, 0.6, 3,
             '{"key":"val"}', "episodic", "", "", now, "decay"),
        )
        store._conn.commit()

        restored = engine.restore("test_rest_1")
        assert restored is True

        # 确认已回到主表
        mem = store._conn.execute(
            "SELECT * FROM episodic_memories WHERE id = 'test_rest_1'"
        ).fetchone()
        assert mem is not None
        assert mem["importance"] == 0.6
        assert mem["access_count"] == 3

        # 确认已从归档表移除
        arch = store._conn.execute(
            "SELECT * FROM episodic_archived WHERE id = 'test_rest_1'"
        ).fetchone()
        assert arch is None

    def test_restore_nonexistent(self, store):
        """恢复不存在的记忆返回False"""
        engine = ForgettingEngine(store._conn)
        assert engine.restore("nonexistent_id") is False

    def test_stats(self, store):
        """遗忘统计"""
        engine = ForgettingEngine(store._conn)  # 先创建引擎以建表
        now = time.time()
        store._conn.executemany(
            """INSERT INTO episodic_archived
               (id, content, content_hash, timestamp, importance, user_id, archived_at, archive_reason)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                ("st_a", "归档A", "ha", now, 0.3, "user_x", now, "decay"),
                ("st_b", "归档B", "hb", now, 0.4, "user_x", now, "cold"),
                ("st_c", "归档C", "hc", now, 0.2, "user_y", now, "decay"),
            ],
        )
        store._conn.commit()

        all_stats = engine.stats()
        assert all_stats["archived_count"] == 3

        user_stats = engine.stats(user_id="user_x")
        assert user_stats["archived_count"] == 2

    def test_archive_limit_respected(self, store):
        """归档上限被遵守：实际归档条目不超过max_archive"""
        old_ts = time.time() - 120 * 86400
        for i in range(20):
            store._conn.execute(
                """INSERT INTO episodic_memories (id, content, content_hash, timestamp, importance, user_id)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (f"low_{i}", f"低价值记忆{i}", f"hash{i}", old_ts, 0.1, ""),
            )
        store._conn.commit()

        engine = ForgettingEngine(store._conn)
        engine.run_forgetting_pass(max_archive=5)

        # 实际归档的数量不超过上限
        archived_count = store._conn.execute(
            "SELECT COUNT(*) FROM episodic_archived"
        ).fetchone()[0]
        assert archived_count <= 5
        assert archived_count > 0  # 至少有1条被归档

    def test_episodic_store_forget_integration(self, store):
        """EpisodicStore.forget() 集成调用"""
        old_ts = time.time() - 120 * 86400
        store.add("一条将被遗忘的旧记忆", importance=0.15)
        # 手动改时间戳以触发遗忘
        store._conn.execute(
            "UPDATE episodic_memories SET timestamp = ? WHERE importance = 0.15",
            (old_ts,),
        )
        store._conn.commit()

        result = store.forget(max_archive=50)
        assert isinstance(result, dict)
        assert "decayed" in result
        assert "cold" in result
        assert "cleaned" in result

    def test_recall_archived_store_method(self, store):
        """EpisodicStore.recall_archived() 集成调用"""
        ForgettingEngine(store._conn)  # 先建表
        now = time.time()
        store._conn.execute(
            """INSERT INTO episodic_archived
               (id, content, content_hash, timestamp, importance, user_id, archived_at, archive_reason)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("recall_test", "系统思维的归档记录", "hr", now, 0.5, "", now, "decay"),
        )
        store._conn.commit()

        results = store.recall_archived(query="系统思维")
        assert len(results) >= 1

    def test_restore_archived_store_method(self, store):
        """EpisodicStore.restore_archived() 集成调用"""
        ForgettingEngine(store._conn)  # 先建表
        now = time.time()
        store._conn.execute(
            """INSERT INTO episodic_archived
               (id, content, content_hash, timestamp, importance, user_id, archived_at, archive_reason)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("restore_store", "待恢复记忆", "hrs", now, 0.5, "", now, "decay"),
        )
        store._conn.commit()

        assert store.restore_archived("restore_store") is True
        assert store.get("restore_store") is not None
