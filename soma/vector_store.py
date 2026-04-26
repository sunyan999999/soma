"""向量索引 — 基于 SQLite BLOB + faiss HNSW 近邻搜索"""

import struct
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np


class NumpyVectorIndex:
    """将嵌入向量存为 SQLite BLOB，提供 faiss 加速的余弦相似度搜索

    与 EpisodicStore 共用同一数据库和表，通过 BLOB 列存储向量。

    - <1000 条: IndexFlatIP（精确内积搜索，等价余弦相似度）
    - ≥1000 条: IndexHNSWFlat（近似搜索，M=32, efConstruction=200）
    """

    def __init__(self, db_path: Path, vector_dim: int):
        self._db_path = db_path
        self._vector_dim = vector_dim
        self._faiss_index = None
        self._faiss_id_to_mem = {}  # faiss内部ID → memory_id
        self._index_type = "none"
        self._cached_count = -1  # 用于索引缓存失效检测

    def ensure_table(self, conn):
        """向 episodic_memories 表添加 vector BLOB 列（幂等操作）"""
        try:
            conn.execute(
                f"ALTER TABLE episodic_memories ADD COLUMN vector BLOB"
            )
            conn.commit()
        except Exception:
            pass  # 列已存在

    def store_vector(self, conn, memory_id: str, vector: np.ndarray):
        """存储嵌入向量（numpy → bytes），使 faiss 缓存失效"""
        blob = vector.astype(np.float32).tobytes()
        conn.execute(
            "UPDATE episodic_memories SET vector = ? WHERE id = ?",
            (blob, memory_id),
        )
        conn.commit()
        self._cached_count = -1  # 使索引缓存失效

    def get_all_vectors(
        self, conn
    ) -> Tuple[List[str], np.ndarray]:
        """获取所有已索引的记忆 ID 和向量矩阵 (N, dim)"""
        rows = conn.execute(
            "SELECT id, vector FROM episodic_memories WHERE vector IS NOT NULL"
        ).fetchall()

        if not rows:
            return [], np.empty((0, self._vector_dim), dtype=np.float32)

        ids = []
        vecs = np.empty((len(rows), self._vector_dim), dtype=np.float32)
        for i, row in enumerate(rows):
            ids.append(row[0])
            vecs[i] = np.frombuffer(row[1], dtype=np.float32)
        return ids, vecs

    def _build_faiss_index(self, ids: List[str], vecs: np.ndarray):
        """(重)构建 faiss 索引"""
        import faiss

        n = len(ids)
        if n == 0:
            self._faiss_index = None
            self._faiss_id_to_mem = {}
            return

        if n < 1000:
            # 精确搜索：内积 = 余弦相似度（向量已 L2 归一化）
            index = faiss.IndexFlatIP(self._vector_dim)
            self._index_type = "flat"
        else:
            # 近似搜索：HNSW
            index = faiss.IndexHNSWFlat(self._vector_dim, 32)
            index.hnsw.efConstruction = 200
            self._index_type = f"hnsw(n={n})"

        index.add(vecs.astype(np.float32))
        self._faiss_index = index
        self._faiss_id_to_mem = {i: mid for i, mid in enumerate(ids)}

    def similarity_search(
        self, conn, query_vec: np.ndarray, top_k: int = 5
    ) -> List[Tuple[str, float]]:
        """余弦相似度搜索，返回 [(memory_id, score), ...] 按分数降序"""
        # 仅在向量数量变化时重建索引
        current_count = self.count_indexed(conn)
        if current_count != self._cached_count or self._faiss_index is None:
            ids, vecs = self.get_all_vectors(conn)
            if len(ids) == 0:
                return []
            self._build_faiss_index(ids, vecs)
            self._cached_count = current_count

        query_vec = query_vec.reshape(1, -1).astype(np.float32)
        k = min(top_k, len(self._faiss_id_to_mem))
        distances, indices = self._faiss_index.search(query_vec, k)

        results = []
        for i in range(k):
            faiss_id = int(indices[0][i])
            mem_id = self._faiss_id_to_mem.get(faiss_id)
            if mem_id is not None:
                score = float(distances[0][i])
                results.append((mem_id, score))

        return results

    def delete_vector(self, conn, memory_id: str):
        conn.execute(
            "UPDATE episodic_memories SET vector = NULL WHERE id = ?",
            (memory_id,),
        )
        conn.commit()
        self._cached_count = -1  # 使索引缓存失效

    def count_indexed(self, conn) -> int:
        row = conn.execute(
            "SELECT COUNT(*) FROM episodic_memories WHERE vector IS NOT NULL"
        ).fetchone()
        return row[0] if row else 0

    def clear_incompatible_vectors(self, conn) -> int:
        """清除维度不匹配的旧向量，返回清除数量。
        当嵌入模型变更导致向量维度变化时调用。"""
        rows = conn.execute(
            "SELECT id, vector FROM episodic_memories WHERE vector IS NOT NULL"
        ).fetchall()
        stale = 0
        for row in rows:
            vec = np.frombuffer(row[1], dtype=np.float32)
            if len(vec) != self._vector_dim:
                conn.execute(
                    "UPDATE episodic_memories SET vector = NULL WHERE id = ?",
                    (row[0],),
                )
                stale += 1
        if stale > 0:
            conn.commit()
            self._cached_count = -1
        return stale
