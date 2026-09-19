import json
import sqlite3
import threading
from pathlib import Path

import numpy as np
import pytest

from soma.vector_store import NumpyVectorIndex


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test.db"


@pytest.fixture
def conn(db_path):
    c = sqlite3.connect(str(db_path))
    # 创建简化版测试表
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS episodic_memories (
            id TEXT PRIMARY KEY,
            content TEXT NOT NULL,
            timestamp REAL NOT NULL,
            importance REAL DEFAULT 0.5,
            access_count INTEGER DEFAULT 0,
            context_json TEXT DEFAULT '{}',
            memory_type TEXT DEFAULT 'episodic'
        )
        """
    )
    c.commit()
    yield c
    c.close()


@pytest.fixture
def index(db_path):
    return NumpyVectorIndex(db_path, vector_dim=4)  # 小维度便于测试


class TestNumpyVectorIndex:
    def test_ensure_table_idempotent(self, index, conn):
        index.ensure_table(conn)
        # 检查列已存在
        cols = conn.execute("PRAGMA table_info(episodic_memories)").fetchall()
        col_names = [c[1] for c in cols]
        assert "vector" in col_names

        # 再次调用不应报错
        index.ensure_table(conn)

    def test_store_and_retrieve(self, index, conn):
        index.ensure_table(conn)

        # 插入测试行
        conn.execute(
            "INSERT INTO episodic_memories (id, content, timestamp) VALUES (?, ?, ?)",
            ("test_1", "测试内容", 1234567890.0),
        )
        conn.commit()

        vec = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32)
        index.store_vector(conn, "test_1", vec)

        # 验证存储
        row = conn.execute(
            "SELECT vector FROM episodic_memories WHERE id = ?", ("test_1",)
        ).fetchone()
        assert row[0] is not None
        restored = np.frombuffer(row[0], dtype=np.float32)
        np.testing.assert_array_almost_equal(restored, vec)

    def test_similarity_search(self, index, conn):
        index.ensure_table(conn)

        # 插入三条记忆（L2归一化，确保内积 = 余弦相似度）
        a_vec = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        b_vec = np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float32)
        c_vec = np.array([0.7, 0.7, 0.0, 0.0], dtype=np.float32)
        c_vec = c_vec / np.linalg.norm(c_vec)  # ≈ [0.707, 0.707, 0, 0]
        vecs = [
            ("a", a_vec),
            ("b", b_vec),
            ("c", c_vec.astype(np.float32)),
        ]
        for mid, vec in vecs:
            conn.execute(
                "INSERT INTO episodic_memories (id, content, timestamp) VALUES (?, ?, ?)",
                (mid, f"记忆{mid}", 1234567890.0),
            )
            conn.commit()
            index.store_vector(conn, mid, vec)

        # 查询向量接近 [1,0,0,0] → a 和 c 应排在前面
        query = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        results = index.similarity_search(conn, query, top_k=2)

        assert len(results) == 2
        assert results[0][0] == "a"  # 最相似
        assert results[0][1] > 0.9  # 接近 1.0

    def test_empty_store(self, index, conn):
        index.ensure_table(conn)
        query = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        results = index.similarity_search(conn, query)
        assert len(results) == 0

    def test_delete_vector(self, index, conn):
        index.ensure_table(conn)
        conn.execute(
            "INSERT INTO episodic_memories (id, content, timestamp) VALUES (?, ?, ?)",
            ("del_1", "待删除", 1234567890.0),
        )
        conn.commit()
        index.store_vector(conn, "del_1", np.ones(4, dtype=np.float32))

        index.delete_vector(conn, "del_1")
        assert index.count_indexed(conn) == 0

    def test_count_indexed(self, index, conn):
        index.ensure_table(conn)
        assert index.count_indexed(conn) == 0

        for i in range(5):
            conn.execute(
                "INSERT INTO episodic_memories (id, content, timestamp) VALUES (?, ?, ?)",
                (f"c_{i}", f"记忆{i}", 1234567890.0),
            )
            conn.commit()
            index.store_vector(conn, f"c_{i}", np.ones(4, dtype=np.float32))

        assert index.count_indexed(conn) == 5

    # ── 回归：索引构建后的一致性（修复 faiss NameError + delete 残留）──

    def test_store_vector_after_index_build_no_desync(self, index, conn):
        """索引构建后再插入记忆，DB 与 faiss 保持一致。

        回归: store_vector 内 faiss.normalize_L2 未 import faiss → NameError，
        索引构建后每次插入记忆 faiss 索引不更新，新记忆语义召回不到。
        """
        index.ensure_table(conn)
        rng = np.random.default_rng(0)
        for i in range(3):
            mid = f"m{i}"
            conn.execute(
                "INSERT INTO episodic_memories (id, content, timestamp) VALUES (?, ?, ?)",
                (mid, f"记忆{i}", 1234567890.0),
            )
            conn.commit()
            index.store_vector(conn, mid, rng.normal(size=4).astype(np.float32))
        # 触发索引构建
        index.similarity_search(conn, rng.normal(size=4).astype(np.float32), 3)
        assert index._faiss_index is not None
        # 索引构建后再插入 → 修复前抛 NameError 导致 DB 与 faiss 失步
        mid = "after_build"
        conn.execute(
            "INSERT INTO episodic_memories (id, content, timestamp) VALUES (?, ?, ?)",
            (mid, "构建后插入", 1234567890.0),
        )
        conn.commit()
        index.store_vector(conn, mid, rng.normal(size=4).astype(np.float32))
        # DB 向量数 == faiss ntotal，无失步
        assert index.count_indexed(conn) == index._faiss_index.ntotal == 4
        # 查询能搜到新记忆
        res = [r[0] for r in index.similarity_search(
            conn, rng.normal(size=4).astype(np.float32), 4)]
        assert mid in res

    def test_delete_leaves_no_stale_in_search(self, index, conn):
        """删除记忆后 query 不返回已删向量（回归: faiss 残留占用 top-k 名额）。"""
        index.ensure_table(conn)
        rng = np.random.default_rng(1)
        for i in range(4):
            mid = f"m{i}"
            conn.execute(
                "INSERT INTO episodic_memories (id, content, timestamp) VALUES (?, ?, ?)",
                (mid, f"记忆{i}", 1234567890.0),
            )
            conn.commit()
            index.store_vector(conn, mid, rng.normal(size=4).astype(np.float32))
        index.similarity_search(conn, rng.normal(size=4).astype(np.float32), 4)  # 构建索引
        # 删除 m0, m1
        for mid in ("m0", "m1"):
            conn.execute("UPDATE episodic_memories SET vector=NULL WHERE id=?", (mid,))
            conn.commit()
            index.delete_vector(conn, mid)
        # 查询不应包含已删向量（重建清除残留）
        res = [r[0] for r in index.similarity_search(
            conn, rng.normal(size=4).astype(np.float32), 4)]
        assert not any(r in ("m0", "m1") for r in res)
        assert set(res) <= {"m2", "m3"}
        assert len(res) == 2

    def test_similarity_search_self_heals_desync(self, index, conn):
        """DB 与 faiss 失步（新增向量未入索引）时，下次查询自动重建修复。"""
        index.ensure_table(conn)
        rng = np.random.default_rng(2)
        for i in range(2):
            mid = f"m{i}"
            conn.execute(
                "INSERT INTO episodic_memories (id, content, timestamp) VALUES (?, ?, ?)",
                (mid, f"记忆{i}", 1234567890.0),
            )
            conn.commit()
            index.store_vector(conn, mid, rng.normal(size=4).astype(np.float32))
        index.similarity_search(conn, rng.normal(size=4).astype(np.float32), 2)  # 构建
        # 模拟增量添加失败：DB 有向量但 faiss 索引未更新
        mid = "orphan"
        conn.execute(
            "INSERT INTO episodic_memories (id, content, timestamp) VALUES (?, ?, ?)",
            (mid, "失步记忆", 1234567890.0),
        )
        conn.commit()
        conn.execute(
            "UPDATE episodic_memories SET vector=? WHERE id=?",
            (np.ones(4, dtype=np.float32).tobytes(), mid),
        )
        conn.commit()
        index._cached_count = -1  # 模拟缓存失效
        # 查询应自动重建并纳入 orphan
        res = [r[0] for r in index.similarity_search(
            conn, rng.normal(size=4).astype(np.float32), 5)]
        assert mid in res
        assert index.count_indexed(conn) == index._faiss_index.ntotal == 3


class TestIndexFileIntegrity:
    """索引文件的持久化完整性（v2.0.18.1）

    背景：接入方生产日志出现
        `从磁盘加载 FAISS 索引失败: ... read error: 43126570 != 55224480 ... 将重建`
    —— 磁盘上的 .faiss_index 与索引自身声明的大小不符（被截断），于是每个新进程
    启动都要白付一次全量 HNSW 重建。根因是保存时直接往目标文件写，既非原子，
    又可能与后台剪枝线程的写盘并发。本类把这几种情形都钉死。
    """

    @staticmethod
    def _build(tmp_path, n=30):
        db = tmp_path / "ep.db"
        c = sqlite3.connect(str(db), check_same_thread=False)
        c.row_factory = sqlite3.Row
        c.execute("CREATE TABLE episodic_memories (id TEXT PRIMARY KEY, vector BLOB)")
        idx = NumpyVectorIndex(db, 4)
        idx.ensure_table(c)

        import faiss
        vecs = np.random.RandomState(7).randn(n, 4).astype(np.float32)
        faiss.normalize_L2(vecs)
        ids = [f"m{i:03d}" for i in range(n)]
        for i, mid in enumerate(ids):
            c.execute("INSERT INTO episodic_memories (id, vector) VALUES (?, ?)",
                      (mid, vecs[i].tobytes()))
        c.commit()
        idx._build_faiss_index(ids, vecs)      # 内部会写盘
        return c, idx, ids

    def test_saved_index_reloads_in_fresh_instance(self, tmp_path):
        """写盘后新建实例（模拟新进程）应直接加载成功，无需重建。"""
        c, _idx, ids = self._build(tmp_path)
        fresh = NumpyVectorIndex(tmp_path / "ep.db", 4)
        assert fresh._load_index_from_disk() is True
        assert fresh._faiss_index.ntotal == len(ids)
        c.close()

    def test_save_leaves_no_tmp_files(self, tmp_path):
        """原子写走临时文件，正常路径不得留下残留。"""
        c, _idx, _ids = self._build(tmp_path)
        assert list(tmp_path.glob("*.tmp")) == []
        c.close()

    def test_truncated_index_rejected_then_rebuilds_once(self, tmp_path):
        """截断的索引文件 → 拒绝加载 → 重建一次后，后续进程都能正常加载。

        「每次启动都重建」的根因就是写盘留下半成品文件；重建写出的文件完整，
        所以正常只会重建这一次。
        """
        c, _idx, ids = self._build(tmp_path)
        p = tmp_path / "ep.faiss_index"
        raw = p.read_bytes()
        p.write_bytes(raw[: len(raw) // 2])    # 模拟写一半被打断

        fresh = NumpyVectorIndex(tmp_path / "ep.db", 4)
        assert fresh._load_index_from_disk() is False, "截断文件必须被拒绝"

        got_ids, vecs = fresh.get_all_vectors(c)
        fresh._build_faiss_index(got_ids, vecs)    # 重建 → 原子写回

        later = NumpyVectorIndex(tmp_path / "ep.db", 4)
        assert later._load_index_from_disk() is True, (
            "重建后的文件应当完整，新进程不该再重建一次"
        )
        assert later._faiss_index.ntotal == len(ids)
        c.close()

    def test_id_map_mismatch_is_rejected(self, tmp_path):
        """索引与 ID 映射条数不一致时必须拒绝加载。

        否则命中会因在映射里查不到 mem_id 被静默丢弃（召回莫名变少），
        同时两侧计数对不上还会被搜索路径当成「有待剪枝」而反复全表 COUNT。
        """
        c, _idx, _ids = self._build(tmp_path)
        mp = tmp_path / "ep.faiss_id_map.json"
        data = json.loads(mp.read_text(encoding="utf-8"))
        del data["faiss_to_mem"]["0"]          # 映射少一条
        mp.write_text(json.dumps(data), encoding="utf-8")

        fresh = NumpyVectorIndex(tmp_path / "ep.db", 4)
        assert fresh._load_index_from_disk() is False
        c.close()

    def test_failed_save_does_not_damage_existing_file(self, tmp_path,
                                                       monkeypatch):
        """写盘失败（磁盘满 / 文件被占用）时，磁盘上原有的完整索引必须不被破坏。"""
        import faiss

        c, idx, ids = self._build(tmp_path)
        good = (tmp_path / "ep.faiss_index").read_bytes()

        def boom(_index, path):
            # 必须真的往目标文件写一截再失败 —— 否则异常发生在打开文件之前，
            # 旧的非原子实现也能「侥幸」不破坏文件，这个测试就守不住任何东西。
            with open(str(path), "wb") as f:
                f.write(b"partial")
            raise OSError("no space left on device")

        monkeypatch.setattr(faiss, "write_index", boom)
        idx._save_index_to_disk()              # 异常被内部吞掉，只记 warning

        assert (tmp_path / "ep.faiss_index").read_bytes() == good, (
            "写盘失败不该动到已有的索引文件"
        )
        fresh = NumpyVectorIndex(tmp_path / "ep.db", 4)
        assert fresh._load_index_from_disk() is True, "原有索引仍应完好可加载"
        assert fresh._faiss_index.ntotal == len(ids)
        assert list(tmp_path.glob("*.tmp")) == [], "失败后须清掉自己的临时文件"
        c.close()

    def test_target_file_stays_intact_while_writing(self, tmp_path, monkeypatch):
        """写盘进行中的任意时刻，目标文件都必须是「完整的旧文件」。

        这是非原子写的要害：直接往目标文件写，写到一半就被读方看到 —— 生产上
        `read error: 43126570 != 55224480` 正是这么来的。本测试用「写完后、替换
        目标前」这个时间点做探针，确定性地判定目标文件有没有被写成中间态。
        """
        import faiss

        c, idx, _ids = self._build(tmp_path)
        p = tmp_path / "ep.faiss_index"
        good = p.read_bytes()
        # 先改索引内容，确保新写出的字节与磁盘上的旧文件必然不同 ——
        # 否则「旧代码下探针也没看出差别」，测试就白写了。
        idx._incremental_add("extra", np.ones(4, dtype=np.float32))

        real = faiss.write_index
        probed = []

        def peek(index_obj, path):
            real(index_obj, path)
            # 此刻「写」已完成、尚未替换目标文件：读方看到的内容必须还等于旧文件
            probed.append(p.read_bytes() == good)

        monkeypatch.setattr(faiss, "write_index", peek)
        idx._save_index_to_disk()

        assert probed == [True], (
            "写盘中途目标文件被改写成了中间态（非原子写）"
        )
        c.close()

    def test_concurrent_saves_leave_loadable_file(self, tmp_path):
        """多线程同时调用写盘（主线程同步重建 vs 后台剪枝线程）不抛错，且最终
        留下一个可加载的文件。

        注意：本测试只固化「并发调用是安全的」，不足以证明写入过程不可被读方
        看见中间态 —— 那个由 test_target_file_stays_intact_while_writing 负责。
        """
        c, idx, ids = self._build(tmp_path)
        errs = []

        def worker():
            try:
                for _ in range(5):
                    idx._save_index_to_disk()
            except Exception as e:            # pragma: no cover - 失败即测试失败
                errs.append(repr(e))

        ts = [threading.Thread(target=worker) for _ in range(3)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()

        assert not errs, f"并发写盘抛错: {errs}"
        fresh = NumpyVectorIndex(tmp_path / "ep.db", 4)
        assert fresh._load_index_from_disk() is True, "并发写后文件必须仍可加载"
        assert fresh._faiss_index.ntotal == len(ids)
        assert list(tmp_path.glob("*.tmp")) == []
        c.close()
