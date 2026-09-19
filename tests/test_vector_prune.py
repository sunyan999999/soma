# -*- coding: utf-8 -*-
"""过期向量清理测试（v2.0.18）

背景：记忆被删除时（forgetting 直接 DELETE 行，不经过索引），faiss 索引里会留下
再也对不上任何记忆的残留向量。它们占住 top_k 名额，并让删除后的下一次搜索触发
同步全量重建。本文件验证「只清理这部分、不重新编码」的行为。

直接测 NumpyVectorIndex，不经 embedder（手动构造向量）。
"""
import sqlite3
import time

import numpy as np
import pytest

faiss = pytest.importorskip("faiss")

from soma.vector_store import NumpyVectorIndex       # noqa: E402

DIM = 8


def _build(tmp_path, n=10):
    """建一个最小记忆库：sqlite 表 + faiss 索引，返回 (conn, index, ids, vecs)"""
    db = tmp_path / "episodic.db"
    conn = sqlite3.connect(str(db), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE episodic_memories (id TEXT PRIMARY KEY, vector BLOB)")
    idx = NumpyVectorIndex(db, DIM)
    idx.ensure_table(conn)

    vecs = np.random.RandomState(42).randn(n, DIM).astype(np.float32)
    faiss.normalize_L2(vecs)
    ids = [f"m{i:03d}" for i in range(n)]
    for i, mid in enumerate(ids):
        conn.execute(
            "INSERT INTO episodic_memories (id, vector) VALUES (?, ?)",
            (mid, vecs[i].tobytes()),
        )
    conn.commit()
    idx._build_faiss_index(ids, vecs)
    return conn, idx, ids, vecs


def _delete_rows(conn, ids):
    """模拟 forgetting：直接删行，不通知向量索引"""
    for mid in ids:
        conn.execute("DELETE FROM episodic_memories WHERE id = ?", (mid,))
    conn.commit()


def _vec_of(conn, mid):
    blob = conn.execute(
        "SELECT vector FROM episodic_memories WHERE id = ?", (mid,)
    ).fetchone()[0]
    return np.frombuffer(blob, dtype=np.float32).copy()


class TestStaleDetection:
    def test_consistent_index_has_no_stale(self, tmp_path):
        conn, idx, ids, _ = _build(tmp_path, n=10)
        assert idx.stale_count(conn) == 0
        assert idx._should_prune(conn) is False

    def test_deleted_rows_become_stale(self, tmp_path):
        conn, idx, ids, _ = _build(tmp_path, n=10)
        _delete_rows(conn, ids[:3])
        assert idx.stale_count(conn) == 3, "删掉的行应被识别为过期向量"

    def test_stale_zero_when_index_missing(self, tmp_path):
        conn, idx, _ids, _ = _build(tmp_path, n=4)
        idx._faiss_index = None
        assert idx.stale_count(conn) == 0


class TestPrune:
    def test_prune_removes_only_stale(self, tmp_path):
        conn, idx, ids, _ = _build(tmp_path, n=10)
        _delete_rows(conn, ids[:3])
        r = idx.prune_stale(conn, background=False)

        assert r["pruned"] == 3
        assert r["remaining"] == 7
        assert r["rebuilt"] is True
        assert idx._faiss_index.ntotal == 7
        assert idx.stale_count(conn) == 0, "清理后不该再有残留"
        # 映射也要跟着收敛
        assert len(idx._faiss_id_to_mem) == 7
        assert len(idx._mem_to_faiss_id) == 7
        assert all(i in idx._faiss_id_to_mem for i in range(7))

    def test_no_stale_is_a_noop(self, tmp_path):
        conn, idx, _ids, _ = _build(tmp_path, n=6)
        before = idx._faiss_index.ntotal
        r = idx.prune_stale(conn, background=False)
        assert r["pruned"] == 0 and r["rebuilt"] is False
        assert idx._faiss_index.ntotal == before

    def test_prune_everything_drops_index(self, tmp_path):
        conn, idx, ids, _ = _build(tmp_path, n=5)
        _delete_rows(conn, ids)
        r = idx.prune_stale(conn, background=False)
        assert r["pruned"] == 5 and r["remaining"] == 0
        assert idx._faiss_index is None
        assert idx.stale_count(conn) == 0

    def test_kept_vectors_stay_searchable(self, tmp_path):
        """清理不能动到仍然有效的向量 —— 用保留条目的向量应能查到它自己。"""
        conn, idx, ids, _ = _build(tmp_path, n=10)
        _delete_rows(conn, ids[:4])
        idx.prune_stale(conn, background=False)

        q = _vec_of(conn, ids[7])
        hits = idx.similarity_search(conn, q, top_k=3)
        assert hits, "清理后仍应能搜到有效记忆"
        assert hits[0][0] == ids[7]

    def test_prune_survives_reload(self, tmp_path):
        """清理结果要落盘：新建索引对象重载后不残留过期条目。"""
        conn, idx, ids, _ = _build(tmp_path, n=10)
        _delete_rows(conn, ids[:3])
        idx.prune_stale(conn, background=False)

        fresh = NumpyVectorIndex(idx._db_path, DIM)
        assert fresh._load_index_from_disk() is True
        assert fresh._faiss_index.ntotal == 7
        assert fresh.stale_count(conn) == 0


class TestPruneScheduling:
    def test_background_prune_completes(self, tmp_path):
        conn, idx, ids, _ = _build(tmp_path, n=60)
        _delete_rows(conn, ids[:40])
        r = idx.prune_stale(conn, background=True)
        assert r["scheduled"] is True

        for _ in range(200):
            if not idx._rebuild_busy:
                break
            time.sleep(0.02)
        assert idx._rebuild_busy is False, "后台清理应在合理时间内结束"
        assert idx._faiss_index.ntotal == 20
        assert idx.stale_count(conn) == 0

    def test_busy_index_is_not_pruned_concurrently(self, tmp_path):
        conn, idx, ids, _ = _build(tmp_path, n=10)
        _delete_rows(conn, ids[:3])
        idx._rebuild_busy = True
        try:
            r = idx.prune_stale(conn, background=True)
            assert r["busy"] is True
            assert r["scheduled"] is False
        finally:
            idx._rebuild_busy = False

    def test_threshold_gate_min_count(self, tmp_path):
        """少量残留（< 32 且 < 5%）不值得重建。"""
        conn, idx, ids, _ = _build(tmp_path, n=1000)
        _delete_rows(conn, ids[:1])
        assert idx._should_prune(conn) is False

    def test_threshold_gate_ratio(self, tmp_path):
        """残留占比超 5% 时即使不足 32 条也触发。"""
        conn, idx, ids, _ = _build(tmp_path, n=200)
        _delete_rows(conn, ids[:12])          # 12 >= 200*0.05 = 10
        assert idx._should_prune(conn) is True

    def test_threshold_gate_min_count_reached(self, tmp_path):
        conn, idx, ids, _ = _build(tmp_path, n=1000)
        _delete_rows(conn, ids[:40])          # 40 >= 32
        assert idx._should_prune(conn) is True


class TestSearchCompensation:
    def test_stale_entries_do_not_crowd_out_results(self, tmp_path, monkeypatch):
        """残留向量会占住 top_k 名额（它们要么取不到 mem_id，要么由调用方查库
        过滤）—— k 不补偿的话有效结果会被挤没。这里让清理不触发，专门看补偿。"""
        conn, idx, ids, _ = _build(tmp_path, n=20)
        monkeypatch.setattr(idx, "_should_prune", lambda _conn, stale=None: False)
        _delete_rows(conn, ids[:10])          # 一半是残留

        q = _vec_of(conn, ids[15])
        hits = idx.similarity_search(conn, q, top_k=3)

        assert hits[0][0] == ids[15]
        alive = set(ids[10:])
        assert len([m for m, _ in hits if m in alive]) >= 3, (
            "有效结果应能取满 top_k，而不是被残留条目挤掉"
        )

    def test_search_does_not_rebuild_synchronously_on_delete(self, tmp_path,
                                                             monkeypatch):
        """删除造成的失步不该再触发同步全量重建（v2.0.18 起交给后台清理）。"""
        conn, idx, ids, _ = _build(tmp_path, n=40)
        original_ntotal = idx._faiss_index.ntotal
        _delete_rows(conn, ids[:20])

        scheduled = []
        monkeypatch.setattr(idx, "_schedule_prune",
                            lambda c, stale=None: scheduled.append(c) or True)

        hits = idx.similarity_search(conn, _vec_of(conn, ids[30]), top_k=3)

        assert scheduled, "应把清理交给后台通道"
        assert idx._faiss_index.ntotal == original_ntotal, (
            "删除后的搜索不该同步重建整个索引"
        )
        assert hits and hits[0][0] == ids[30], "本次搜索仍应正常返回"
        assert idx._cached_count == idx.count_indexed(conn)

    def test_search_counts_index_once(self, tmp_path, monkeypatch):
        """P2 回归：单次搜索只允许跑一次全表 COUNT。

        原先的调用链是 similarity_search 算完 current_count 后，又经
        _schedule_prune → _should_prune → stale_count → count_indexed
        把同一个 COUNT 再跑一遍。全表 COUNT 随记忆条数线性增长，而搜索是
        热路径，这第二次纯属重复计算。
        """
        conn, idx, ids, _ = _build(tmp_path, n=200)
        _delete_rows(conn, ids[:12])          # 12 >= 200*0.05 → 会触发剪枝判定
        calls = []
        real = NumpyVectorIndex.count_indexed

        def counting(self, c):
            calls.append(1)
            return real(self, c)

        monkeypatch.setattr(NumpyVectorIndex, "count_indexed", counting)
        try:
            idx.similarity_search(conn, _vec_of(conn, ids[30]), top_k=3)
            assert len(calls) == 1, (
                f"单次搜索跑了 {len(calls)} 次全表 COUNT（应为 1）"
            )
        finally:
            idx.wait_idle()   # 等后台清理让位，避免线程泄漏到后续测试

    def test_prune_decision_unchanged_when_stale_is_passed_in(self, tmp_path):
        """复用调用方算好的 stale 时，判定结果必须与自算时完全一致。"""
        conn, idx, ids, _ = _build(tmp_path, n=200)
        _delete_rows(conn, ids[:12])

        real_stale = idx.stale_count(conn)
        assert real_stale == 12
        assert idx._should_prune(conn) == idx._should_prune(conn, stale=real_stale)

        # 边界：差值传错时不该悄悄放过（0 与负数一律不清理）
        assert idx._should_prune(conn, stale=0) is False
        assert idx._should_prune(conn, stale=-5) is False


class TestMapIntegrity:
    def test_delete_vector_clears_both_directions(self, tmp_path):
        """delete_vector 必须同时清理正反两个映射（原先漏了反向映射）。"""
        conn, idx, ids, _ = _build(tmp_path, n=10)
        target = ids[0]
        faiss_id = idx._mem_to_faiss_id[target]

        idx.delete_vector(conn, target)

        assert target not in idx._mem_to_faiss_id
        assert faiss_id not in idx._faiss_id_to_mem, "反向映射必须一起清掉"
        row = conn.execute(
            "SELECT vector FROM episodic_memories WHERE id = ?", (target,)
        ).fetchone()
        assert row[0] is None, "DB 里的向量应被置空"

    def test_deleted_vector_no_longer_returned(self, tmp_path):
        """删掉向量后，用它的向量去查不该再命中它。"""
        conn, idx, ids, _ = _build(tmp_path, n=10)
        q = _vec_of(conn, ids[3])
        idx.delete_vector(conn, ids[3])

        hits = idx.similarity_search(conn, q, top_k=5)
        assert ids[3] not in [m for m, _ in hits]
