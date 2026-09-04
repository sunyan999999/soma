"""faiss 后台异步重建测试（v2.0.14）

背景：增量插入 1000 条触发 faiss 全量重建 ~5s 阻塞插入。
修复：重建放后台线程，插入线程只做轻量快照读取后立即返回。

覆盖：
- 触发后台重建不阻塞主线程
- 后台重建完成后索引可用（ntotal 正确）
- 重建期间的增量由一致性检查自愈补入（不丢）
"""
import sqlite3
import time
from pathlib import Path

import numpy as np
import pytest

from soma.vector_store import NumpyVectorIndex


def _mk_store(tmp_path, n=5):
    db = tmp_path / "test.db"
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE episodic_memories (id TEXT PRIMARY KEY, vector BLOB)")
    store = NumpyVectorIndex(db, 8)
    ids, vecs = [], []
    for i in range(n):
        mid = f"m{i}"
        ids.append(mid)
        v = np.random.rand(8).astype(np.float32)
        conn.execute(
            "INSERT INTO episodic_memories (id, vector) VALUES (?,?)",
            (mid, v.tobytes()))
        vecs.append(v)
    conn.commit()
    store._build_faiss_index(ids, np.vstack(vecs))
    return store, conn


def test_rebuild_non_blocking(tmp_path):
    """触发后台重建，插入线程不阻塞（<1s）"""
    store, conn = _mk_store(tmp_path)
    store._incremental_adds = store._INCREMENTAL_LIMIT + 1
    t0 = time.time()
    store._maybe_rebuild(conn)
    elapsed = time.time() - t0
    assert elapsed < 1.0, f"后台重建不应阻塞主线程 ({elapsed:.1f}s)"
    # 后台线程应已在跑或完成
    assert store._rebuild_busy or store._faiss_index is not None


def test_rebuild_completes_background(tmp_path):
    """后台重建完成后索引可用且 busy 复位"""
    store, conn = _mk_store(tmp_path)
    store._incremental_adds = store._INCREMENTAL_LIMIT + 1
    store._maybe_rebuild(conn)
    # 等后台完成（最多 5s）
    for _ in range(50):
        if not store._rebuild_busy:
            break
        time.sleep(0.1)
    assert store._rebuild_busy is False, "后台重建应完成"
    assert store._faiss_index is not None, "重建后索引应可用"
    assert store._faiss_index.ntotal >= 5, "索引应含全部向量"
    # 重建后索引仍能搜索
    q = np.random.rand(8).astype(np.float32)
    store.similarity_search(conn, q, top_k=3)


def test_incremental_after_rebuild_selfheals(tmp_path):
    """重建期间的增量不丢——一致性检查自愈补入"""
    store, conn = _mk_store(tmp_path)
    store._incremental_adds = store._INCREMENTAL_LIMIT + 1
    store._maybe_rebuild(conn)
    # 重建期间再插入 2 条（增量 add 到旧索引 / 写入 DB）
    for i in range(5, 7):
        mid = f"m{i}"
        v = np.random.rand(8).astype(np.float32)
        conn.execute(
            "INSERT INTO episodic_memories (id, vector) VALUES (?,?)",
            (mid, v.tobytes()))
        conn.commit()
        blob = v.astype(np.float32).tobytes()
        conn.execute(
            "UPDATE episodic_memories SET vector=? WHERE id=?", (blob, mid))
        conn.commit()
    # 等后台完成
    for _ in range(50):
        if not store._rebuild_busy:
            break
        time.sleep(0.1)
    assert not store._rebuild_busy
    # 一致性检查应把 DB 里新增的向量补入（自愈）
    store.similarity_search(conn, np.random.rand(8).astype(np.float32), top_k=3)
    assert store._faiss_index.ntotal >= 7, \
        f"重建期间的增量应被补入 (ntotal={store._faiss_index.ntotal})"
