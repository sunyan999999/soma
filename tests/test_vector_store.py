import sqlite3
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
