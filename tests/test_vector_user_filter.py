# -*- coding: utf-8 -*-
"""向量通道的隔离条件必须是**检索前**过滤（v2.0.18.2）

背景
----
``query_by_vector`` 原先走「先全局取候选、再按 user_id 剔除」的检索后过滤，
且用一个粗略的 ``fetch_k = top_k * 3`` 当补偿。多租户下单个用户的记忆占全库比例
很低时，这 3×top_k 条候选里往往**一条都不属于**该用户 —— 向量通道对该用户等于
失效。而它是 RRF 融合里的主通道（权重 2.0，关键词通道只有 1.0），关键词通道本来
就是 SQL 前置过滤，两条通道时机不一致正是这个 bug 的根源。

本文件用「头部用户占满候选池、长尾用户被挤出去」的确定性构造复现它，并守住修复：

  · 长尾用户必须能取回自己的 top_k 条（修复前是 0 条）
  · 长尾用户不得取到别人的记忆
  · agent/group 语义与关键词通道、与调用方的 post-filter 一致
  · max_age_days 时间窗在 SQL 侧生效
  · 子集接近全库时退回 faiss 路径 —— 单用户部署的行为与性能不变
  · 脏数据（维度不符 / 零向量）不能炸掉整次扫描

「回退即失败」验证见 tmp/verify_recall_fix_revert.py：把修复改回去，本文件必须
失败（exit=1），否则标明验证无效，不是测试结论。
"""
import hashlib
import sqlite3

import numpy as np
import pytest

faiss = pytest.importorskip("faiss")           # noqa: E402

from soma.vector_store import NumpyVectorIndex  # noqa: E402

DIM = 8
QUERY = np.zeros(DIM, dtype=np.float32)
QUERY[0] = 1.0


class DirEmbedder:
    """按文本前缀给出可控方向的确定性嵌入器。

    - ``big*``   与查询近乎同向（cos ≈ 0.999）→ 占满全局候选池
    - ``small*`` 与查询夹角较大但仍相关（cos ≈ 0.86）→ 正确实现必须召回

    两个方向都高于任何合理相关阈值；关键是长尾用户的条目在**全局**排序里排不进
    前 fetch_k，这正是检索后过滤会丢掉它们的原因，而不是「它们不相关」。
    """

    dimension = DIM

    def _vec(self, text: str) -> np.ndarray:
        spread = 0.04 if text.startswith("big") else 0.6
        h = int(hashlib.md5(text.encode("utf-8")).hexdigest()[:8], 16)
        rng = np.random.RandomState(h)
        v = np.zeros(DIM, dtype=np.float32)
        v[0] = 1.0
        v[1:] = rng.randn(DIM - 1).astype(np.float32) * spread
        return (v / np.linalg.norm(v)).astype(np.float32)

    def encode(self, text: str) -> np.ndarray:
        return self._vec(text)

    def encode_batch(self, texts):
        return np.vstack([self._vec(t) for t in texts])


def _settle(store):
    """把索引推到与 DB 一致的确定状态。

    写入超过 _INCREMENTAL_LIMIT 条会触发一次后台异步重建，重建期间新写入的向量
    不在索引快照里 —— 再搜一次由失步自愈补上。测试要断言的正是「一致状态下」的
    召回，所以先等后台收工、再触发一次同步自愈。
    """
    idx = store._vector_index
    idx.wait_idle()
    store.query_by_vector(QUERY, top_k=1)   # 无过滤 → 走全局路径，触发失步自愈
    assert idx._faiss_index.ntotal == idx.count_indexed(store._conn)


def _store(tmp_path, n_big=1200, n_small=6, small_user="tail", big_user="head"):
    """建一个「1 个头部用户占满、1 个长尾用户被挤出候选池」的记忆库。

    n_big=1200 让索引走 HNSW 分支（≥1000 条），也就是生产上真正出问题的那条。
    """
    from soma.memory.episodic import EpisodicStore

    store = EpisodicStore(
        tmp_path, embedder=DirEmbedder(), use_vector_search=True)
    for i in range(n_big):
        store.add(f"big{i}", {"t": "tt"}, user_id=big_user)
    for i in range(n_small):
        store.add(f"small{i}", {"t": "tt"}, user_id=small_user)
    _settle(store)
    return store


def _raw_insert(store, mid, vec, user_id):
    """绕过 add() 直接塞一条带向量的记忆 —— 用于造脏数据。"""
    store._conn.execute(
        "INSERT INTO episodic_memories (id, content, content_hash, timestamp, "
        "user_id, vector, nature) VALUES (?, ?, ?, 0.0, ?, ?, 'event')",
        (mid, mid, mid, user_id, vec.tobytes()))
    store._conn.commit()


def _ids_of(store, user_id):
    rows = store._conn.execute(
        "SELECT id FROM episodic_memories WHERE user_id = ?", (user_id,)
    ).fetchall()
    return {r["id"] for r in rows}


class TestSmallShareUserRecall:
    def test_index_uses_hnsw_branch(self, tmp_path):
        """前提校验：这个库确实大到走 HNSW —— 否则测的不是有缺陷的那条路径。"""
        store = _store(tmp_path)
        assert store._vector_index.count_indexed(store._conn) == 1206
        assert store._vector_index._faiss_index.ntotal == 1206
        assert "hnsw" in store._vector_index._index_type

    def test_small_user_gets_full_top_k(self, tmp_path):
        """核心缺陷：长尾用户此前一条都取不回来。"""
        store = _store(tmp_path)
        tail_ids = _ids_of(store, "tail")

        hits = store.query_by_vector(QUERY, top_k=5, user_id="tail")

        assert len(hits) == 5, (
            f"长尾用户应取回 5 条，实得 {len(hits)} —— "
            "取回 0/1 条说明又在做检索后过滤")
        assert {m.id for m in hits} <= tail_ids

    def test_top_k_larger_than_own_count_is_capped_not_empty(self, tmp_path):
        """该用户只有 6 条、要 50 条 → 应给满 6 条，而不是因为候选被挤掉给 0 条。"""
        store = _store(tmp_path)
        hits = store.query_by_vector(QUERY, top_k=50, user_id="tail")
        assert len(hits) == 6

    def test_head_user_also_correct(self, tmp_path):
        """头部用户占多数，两种实现都能召回 —— 修复不能把它弄坏。"""
        store = _store(tmp_path)
        hits = store.query_by_vector(QUERY, top_k=5, user_id="head")
        assert len(hits) == 5
        assert {m.id for m in hits} <= _ids_of(store, "head")

    def test_results_are_the_nearest_ones(self, tmp_path):
        """不只是「取回了几条」——要取回**最相近**的那几条。"""
        store = _store(tmp_path, n_small=10)
        tail = store._conn.execute(
            "SELECT id, vector FROM episodic_memories WHERE user_id = 'tail'"
        ).fetchall()
        mat = np.vstack(
            [np.frombuffer(r["vector"], dtype=np.float32) for r in tail])
        mat = mat / np.linalg.norm(mat, axis=1, keepdims=True)
        sims = mat @ QUERY
        want = {tail[i]["id"] for i in np.argsort(-sims)[:3]}

        hits = store.query_by_vector(QUERY, top_k=3, user_id="tail")
        assert {m.id for m in hits} == want


class TestIsolation:
    def test_no_cross_user_leak(self, tmp_path):
        store = _store(tmp_path)
        for uid in ("tail", "head"):
            hits = store.query_by_vector(QUERY, top_k=20, user_id=uid)
            assert all(m.user_id == uid for m in hits), (
                f"{uid} 的查询捞到了别人的记忆")

    def test_empty_user_id_does_not_filter(self, tmp_path):
        """空 user_id = 单用户部署的常态，必须与修复前一样不过滤。"""
        store = _store(tmp_path)
        hits = store.query_by_vector(QUERY, top_k=5, user_id="")
        assert len(hits) == 5
        assert {m.user_id for m in hits} == {"head"}   # 头部占满全局前 5

    def test_unknown_user_returns_empty(self, tmp_path):
        store = _store(tmp_path)
        assert store.query_by_vector(QUERY, top_k=5, user_id="nobody") == []

    def test_agent_own_and_group_shared(self, tmp_path):
        """agent_id 语义：自己的 + 同组共享的，与关键词通道一致。"""
        store = _store(tmp_path, n_small=0)
        store.add("small-own", {"t": "tt"}, agent_id="a1")
        store.add("small-grp", {"t": "tt"}, agent_id="a2",
                  shared_group_id="g1")
        store.add("small-other", {"t": "tt"}, agent_id="a2",
                  shared_group_id="g2")
        _settle(store)

        hits = store.query_by_vector(QUERY, top_k=50, agent_id="a1",
                                     group_id="g1")
        contents = {m.content for m in hits}
        assert "small-own" in contents, "自己的记忆应可见"
        assert "small-grp" in contents, "同组共享的记忆应可见"
        assert "small-other" not in contents, "别组的记忆不该可见"

    def test_max_age_days_filters_in_sql(self, tmp_path):
        """时间窗在 SQL 侧生效：把窗口外的条目做成最相近的，它们仍不得出现。"""
        store = _store(tmp_path, n_small=0)
        old_id = store.add("small-old", {"t": "tt"}, user_id="tail")
        fresh_id = store.add("small-fresh", {"t": "tt"}, user_id="tail")
        store._conn.execute(
            "UPDATE episodic_memories SET timestamp = timestamp - 90 * 86400 "
            "WHERE id = ?", (old_id,))
        store._conn.commit()

        hits = store.query_by_vector(QUERY, top_k=10, user_id="tail",
                                     max_age_days=30)
        got = {m.id for m in hits}
        assert fresh_id in got
        assert old_id not in got


class TestTimeWindowRecall:
    """时间窗是同一类缺陷：窗口内的条目也可能被全局候选挤出去。"""

    def test_window_subset_is_searched_not_post_filtered(self, tmp_path):
        """窗口内只有 5 条，全库 1206 条 —— 必须取回窗口内那 5 条。"""
        store = _store(tmp_path, n_big=1200, n_small=0)
        for i in range(5):
            store.add(f"small-fresh{i}", {"t": "tt"}, user_id="tail")
        store._conn.execute(
            "UPDATE episodic_memories SET timestamp = timestamp - 90 * 86400 "
            "WHERE user_id != 'tail'")
        store._conn.commit()

        hits = store.query_by_vector(QUERY, top_k=5, max_age_days=30)
        assert len(hits) == 5, (
            f"窗口内 5 条应全部取回，实得 {len(hits)} —— 说明仍在检索后过滤")
        assert {m.user_id for m in hits} == {"tail"}

    def test_wide_window_matches_previous_behavior(self, tmp_path):
        """窗口覆盖全库时退回全局路径 —— 单租户 + 宽窗口的行为与 2.0.18.1 一致。"""
        store = _store(tmp_path)
        direct = store._vector_index.similarity_search(store._conn, QUERY, 5)
        got = store.query_by_vector(QUERY, top_k=5, max_age_days=3650)
        assert [m.id for m in got] == [mid for mid, _ in direct]


class TestFallbackAndRobustness:
    def test_single_user_library_uses_faiss_path(self, tmp_path):
        """整库都属于一个 user 时不做前置过滤 —— 单用户部署行为不变。

        这也是 _MAX_FILTER_SHARE 的存在理由：子集≈全库时全局候选里天然有足够多
        该用户的记忆，逐条读向量的精确扫描只会在无收益的情况下更慢。
        """
        store = _store(tmp_path, n_small=0)
        idx = store._vector_index
        direct = idx.similarity_search(store._conn, QUERY, 5, user_id="head")

        calls = []
        orig = idx._exact_filtered_search

        def spy(*a, **kw):
            r = orig(*a, **kw)
            calls.append(r)
            return r

        idx._exact_filtered_search = spy
        try:
            got = store.query_by_vector(QUERY, top_k=5, user_id="head")
        finally:
            idx._exact_filtered_search = orig

        assert calls and calls[0][0] is None, "整库单用户时应退回全局检索"
        assert calls[0][1] == 1, "占比高时不该放大候选 —— 那会让单用户部署白算"
        assert [m.id for m in got] == [mid for mid, _ in direct]

    def test_no_filter_does_not_enter_filtered_path(self, tmp_path):
        """不传隔离条件时走原 FAISS 路径，结果与直接调 similarity_search 一致。"""
        store = _store(tmp_path)
        direct = store._vector_index.similarity_search(store._conn, QUERY, 5)
        got = store.query_by_vector(QUERY, top_k=5, user_id="")
        assert [m.id for m in got] == [mid for mid, _ in direct]

    def test_dirty_dim_vectors_are_skipped(self, tmp_path):
        """一条维度不符的历史脏数据不能让整次扫描抛异常（否则该用户直接查不到）。"""
        store = _store(tmp_path, n_small=4)
        _raw_insert(store, "dirty", np.zeros(3, dtype=np.float32), "tail")

        hits = store.query_by_vector(QUERY, top_k=10, user_id="tail")
        assert len(hits) == 4
        assert "dirty" not in {m.id for m in hits}

    def test_zero_vector_does_not_break_scan(self, tmp_path):
        """零向量在归一化时会除零 —— 必须挡住，且不影响其他条目。"""
        store = _store(tmp_path, n_small=4)
        _raw_insert(store, "zero", np.zeros(DIM, dtype=np.float32), "tail")

        hits = store.query_by_vector(QUERY, top_k=10, user_id="tail")
        # 4 条正常 + 零向量（余弦 0，仍属于该用户，排最后）
        assert [m.id for m in hits][:4] != ["zero"]
        assert len(hits) == 5 and hits[-1].id == "zero"

    def test_scores_are_cosine_like_faiss_index(self, tmp_path):
        """分数口径必须与全局路径一致（余弦），否则 RRF 融合会被污染。"""
        store = _store(tmp_path, n_big=0, n_small=6)
        hits = store.query_by_vector(QUERY, top_k=6, user_id="tail")
        rows = store._conn.execute(
            "SELECT id, vector FROM episodic_memories WHERE user_id = 'tail'"
        ).fetchall()
        by_id = {r["id"]: np.frombuffer(r["vector"], dtype=np.float32)
                 for r in rows}
        assert len(hits) == 6
        for m in hits:
            v = by_id[m.id]
            want = float(v / np.linalg.norm(v) @ QUERY)
            assert m.context["_vector_score"] == pytest.approx(want, abs=1e-5)

    def test_exact_path_works_before_faiss_index_exists(self, tmp_path):
        """过滤路径不依赖 faiss 索引 —— 索引未加载时也应正确召回。"""
        store = _store(tmp_path)
        store._vector_index._faiss_index = None
        store._vector_index._cached_count = -1
        hits = store.query_by_vector(QUERY, top_k=5, user_id="tail")
        assert len(hits) == 5


class TestFilterClause:
    """_build_filter_clause 的口径 —— 必须与 fts5_keyword_search 的 WHERE 一致。"""

    @pytest.fixture
    def idx(self, tmp_path):
        return NumpyVectorIndex(tmp_path / "x.db", DIM)

    def test_user_only(self, idx):
        clause, params = idx._build_filter_clause("u1", "", "", None)
        assert clause == " AND user_id = ?"
        assert params == ["u1"]

    def test_user_agent_group_and_time(self, idx):
        clause, params = idx._build_filter_clause("u1", "a1", "g1", 7)
        assert clause == (
            " AND user_id = ? AND (agent_id = ? OR shared_group_id = ?)"
            " AND timestamp >= ?")
        assert params[:3] == ["u1", "a1", "g1"]
        assert len(params) == 4

    def test_agent_without_group_is_exact_match(self, idx):
        clause, params = idx._build_filter_clause("", "a1", "", None)
        assert clause == " AND agent_id = ?"
        assert params == ["a1"]

    def test_no_conditions_returns_empty_clause(self, idx):
        clause, params = idx._build_filter_clause("", "", "", None)
        assert clause == "" and params == []

    def test_top_k_zero_is_safe(self, idx, tmp_path):
        conn = sqlite3.connect(str(tmp_path / "raw.db"))
        conn.row_factory = sqlite3.Row
        conn.execute(
            "CREATE TABLE episodic_memories (id TEXT PRIMARY KEY, vector BLOB, "
            "user_id TEXT, agent_id TEXT, shared_group_id TEXT, timestamp REAL)")
        conn.commit()
        assert idx._exact_filtered_search(
            conn, QUERY, 0, "u", "", "", None) == ([], 1)
        conn.close()
