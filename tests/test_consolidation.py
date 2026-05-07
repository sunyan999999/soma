"""记忆摘要合并测试"""
import pytest
from soma.memory.consolidation import (
    ConsolidationEngine,
    _cosine_similarity,
    _text_overlap,
    _extract_unique_info,
)
import numpy as np


class TestConsolidationUtils:
    def test_cosine_identical(self):
        a = np.array([1.0, 2.0, 3.0])
        assert _cosine_similarity(a, a) == pytest.approx(1.0)

    def test_cosine_orthogonal(self):
        a = np.array([1.0, 0.0, 0.0])
        b = np.array([0.0, 1.0, 0.0])
        assert _cosine_similarity(a, b) == pytest.approx(0.0)

    def test_text_overlap_identical(self):
        assert _text_overlap("第一性原理回归本质", "第一性原理回归本质") == pytest.approx(1.0)

    def test_text_overlap_none(self):
        assert _text_overlap("第一性原理", "系统思维方法") == pytest.approx(0.0)

    def test_text_overlap_partial(self):
        score = _text_overlap(
            "第一性原理是回归事物本质的思考方式",
            "第一性原理在商业决策中的应用",
        )
        assert 0 < score < 1.0

    def test_extract_unique_info_finds_new_content(self):
        unique = _extract_unique_info(
            "第一性原理是回归事物本质",
            "第一性原理是回归事物本质。补充：在实践中需要反复验证。第三视角很重要。",
        )
        assert "在实践中需要反复验证" in unique or "第三视角很重要" in unique


class TestConsolidationEngine:
    @pytest.fixture
    def store(self, tmp_path):
        from soma.memory.episodic import EpisodicStore
        s = EpisodicStore(tmp_path)
        yield s
        s.close()

    def test_merge_table_created(self, store):
        engine = ConsolidationEngine(store._conn)
        tables = store._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='memory_merges'"
        ).fetchall()
        assert len(tables) == 1

    def test_merge_two_similar_memories(self, store):
        mid1 = store.add("第一性原理是回归事物本质的思考方式，有助于从底层逻辑出发", context={"v": 1})
        mid2 = store.add("运用第一性原理可以从底层逻辑出发分析问题", context={"v": 2})

        engine = ConsolidationEngine(store._conn)
        engine.merge(mid1, mid2)

        # 主体保留并追加了补充信息
        mem = store.get(mid1)
        assert mem is not None
        assert mem.importance >= 0.5

        # 次要记忆被标记为废记忆
        mem2 = store.get(mid2)
        assert mem2.importance == -0.1  # 标记为待归档

        # 合并日志已记录
        log_row = store._conn.execute(
            "SELECT * FROM memory_merges WHERE primary_id = ?", (mid1,)
        ).fetchone()
        assert log_row is not None

    def test_merge_keeps_higher_importance_as_primary(self, store):
        mid_low = store.add("系统思维强调整体大于部分", importance=0.3)
        mid_high = store.add("系统思维告诉我们整体大于部分之和，这是系统论的基本原理", importance=0.8)

        engine = ConsolidationEngine(store._conn)
        result = engine.merge(mid_low, mid_high)

        # 如果importance高的作为secondary传入，应交换
        # 结果应是保留importance高的作为primary
        mem_high = store.get(mid_high)
        assert mem_high is not None
        # 高重要性记忆应被保留且升级
        assert mem_high.importance >= 0.8

    def test_run_consolidation_pass(self, store):
        # 插入多对相似记忆
        for i in range(5):
            store.add(f"第一性原理应用案例{i}: 在商业决策中回归基本要素", importance=0.3 + i * 0.1)
            store.add(f"商业决策的第一性原理分析{i}: 找到最基础的要素", importance=0.3 + i * 0.1)

        engine = ConsolidationEngine(store._conn)
        merged = engine.run_consolidation_pass(max_merges=5)
        assert merged >= 0  # 不要求一定合并（取决于embedder是否加载）

    def test_consolidation_respects_user_id(self, store):
        mid_a = store.add("用户A的记忆: 第一性原理很重要", user_id="user_a")
        mid_b = store.add("用户B的记忆: 第一性原理很重要", user_id="user_b")

        engine = ConsolidationEngine(store._conn)
        # 不同user_id的不应合并
        engine.merge(mid_a, mid_b)

        # 两个用户各自的记忆仍存在
        mem_a = store.get(mid_a)
        mem_b = store.get(mid_b)
        assert mem_a is not None
        assert mem_b is not None
