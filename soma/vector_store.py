"""向量索引 — 基于 SQLite BLOB + faiss HNSW 近邻搜索

v1.0.1: 支持持久化 FAISS 索引（磁盘读写），增量更新避免每次全量重建。
"""

import json
import logging
import struct
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

_log = logging.getLogger("soma.vector")


class NumpyVectorIndex:
    """将嵌入向量存为 SQLite BLOB，提供 faiss 加速的余弦相似度搜索

    与 EpisodicStore 共用同一数据库和表，通过 BLOB 列存储向量。

    索引策略:
    - <1000 条: IndexFlatIP（精确内积搜索）
    - >=1000 条: IndexHNSWFlat（近似搜索，M=32, efConstruction=200）

    v1.0.1 持久化:
    - FAISS 索引写入 {db_path}.faiss_index 文件
    - ID 映射写入 {db_path}.faiss_id_map.json
    - 重启后优先加载磁盘索引，避免全量重建
    - store_vector 时增量更新 FAISS 索引，积累超过 1000 次增量后全量重建
    """

    _INCREMENTAL_LIMIT = 1000

    def __init__(self, db_path: Path, vector_dim: int):
        self._db_path = db_path
        self._vector_dim = vector_dim
        self._faiss_index = None
        self._faiss_id_to_mem: dict = {}
        self._mem_to_faiss_id: dict = {}
        self._index_type = "none"
        self._cached_count = -1
        self._incremental_adds = 0
        self._faiss_index_path = db_path.parent / (db_path.stem + ".faiss_index")
        self._faiss_id_map_path = db_path.parent / (db_path.stem + ".faiss_id_map.json")

    def ensure_table(self, conn):
        """向 episodic_memories 表添加 vector BLOB 列（幂等操作）"""
        try:
            conn.execute(
                f"ALTER TABLE episodic_memories ADD COLUMN vector BLOB"
            )
            conn.commit()
        except Exception:
            pass

    # ── 磁盘持久化 ──────────────────────────────────────────────

    def _save_index_to_disk(self):
        """将 FAISS 索引和 ID 映射写入磁盘"""
        import faiss

        if self._faiss_index is None:
            return
        try:
            faiss.write_index(self._faiss_index, str(self._faiss_index_path))
            with open(self._faiss_id_map_path, "w", encoding="utf-8") as f:
                json.dump({
                    "faiss_to_mem": {str(k): v for k, v in self._faiss_id_to_mem.items()},
                    "mem_to_faiss": self._mem_to_faiss_id,
                    "cached_count": self._cached_count,
                    "incremental_adds": self._incremental_adds,
                }, f)
        except Exception as e:
            _log.warning("保存 FAISS 索引到磁盘失败: %s", e)

    def _load_index_from_disk(self) -> bool:
        """从磁盘加载 FAISS 索引和 ID 映射。成功返回 True。"""
        import faiss

        if not self._faiss_index_path.exists() or not self._faiss_id_map_path.exists():
            return False
        try:
            self._faiss_index = faiss.read_index(str(self._faiss_index_path))
            with open(self._faiss_id_map_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._faiss_id_to_mem = {int(k): v for k, v in data["faiss_to_mem"].items()}
            self._mem_to_faiss_id = data.get("mem_to_faiss", {})
            self._cached_count = data.get("cached_count", self._faiss_index.ntotal)
            self._incremental_adds = data.get("incremental_adds", 0)

            n = self._faiss_index.ntotal
            if n < 1000:
                self._index_type = "flat"
            else:
                self._index_type = f"hnsw(n={n})"
            return True
        except Exception as e:
            _log.warning("从磁盘加载 FAISS 索引失败: %s，将重建", e)
            self._faiss_index = None
            return False

    # ── 索引构建（持久化） ─────────────────────────────────────

    def _build_faiss_index(self, ids: List[str], vecs: np.ndarray):
        """(重)构建 faiss 索引并写入磁盘"""
        import faiss

        n = len(ids)
        if n == 0:
            self._faiss_index = None
            self._faiss_id_to_mem = {}
            self._mem_to_faiss_id = {}
            self._incremental_adds = 0
            # 清理磁盘文件
            if self._faiss_index_path.exists():
                self._faiss_index_path.unlink()
            if self._faiss_id_map_path.exists():
                self._faiss_id_map_path.unlink()
            return

        if n < 1000:
            index = faiss.IndexFlatIP(self._vector_dim)
            self._index_type = "flat"
        else:
            index = faiss.IndexHNSWFlat(self._vector_dim, 32)
            index.hnsw.efConstruction = 200
            index.hnsw.efSearch = 64        # v1.1.7-clean: recall提升0.7→0.9
            self._index_type = f"hnsw(n={n})"

        index.add(vecs.astype(np.float32))
        self._faiss_index = index
        self._faiss_id_to_mem = {i: mid for i, mid in enumerate(ids)}
        self._mem_to_faiss_id = {mid: i for i, mid in enumerate(ids)}
        self._incremental_adds = 0
        self._save_index_to_disk()

    # ── 增量更新 ────────────────────────────────────────────────

    def _incremental_add(self, memory_id: str, vector: np.ndarray):
        """向已有 FAISS 索引增量添加单个向量"""
        if self._faiss_index is None:
            return False

        vec = vector.reshape(1, -1).astype(np.float32)
        new_id = self._faiss_index.ntotal
        self._faiss_index.add(vec)
        self._faiss_id_to_mem[new_id] = memory_id
        self._mem_to_faiss_id[memory_id] = new_id
        self._cached_count += 1
        self._incremental_adds += 1
        return True

    def _maybe_rebuild(self, conn):
        """如果增量添加过多则触发全量重建"""
        if self._incremental_adds >= self._INCREMENTAL_LIMIT:
            _log.info("增量添加达 %d 次，触发全量索引重建", self._incremental_adds)
            ids, vecs = self.get_all_vectors(conn)
            if len(ids) > 0:
                self._build_faiss_index(ids, vecs)
            self._cached_count = len(ids)

    # ── 公共接口 ────────────────────────────────────────────────

    def store_vector(self, conn, memory_id: str, vector: np.ndarray):
        """存储嵌入向量并增量更新 FAISS 索引"""
        blob = vector.astype(np.float32).tobytes()
        conn.execute(
            "UPDATE episodic_memories SET vector = ? WHERE id = ?",
            (blob, memory_id),
        )
        conn.commit()

        # 增量添加到 FAISS 索引（如果已构建）
        if self._faiss_index is not None:
            faiss.normalize_L2(vector.reshape(1, -1))
            if self._incremental_add(memory_id, vector):
                self._save_index_to_disk()
                self._maybe_rebuild(conn)
                return
        # 索引未构建或增量添加失败 → 下次搜索时重建
        self._cached_count = -1

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

    def similarity_search(
        self, conn, query_vec: np.ndarray, top_k: int = 5
    ) -> List[Tuple[str, float]]:
        """余弦相似度搜索，返回 [(memory_id, score), ...] 按分数降序

        优先使用持久化 FAISS 索引（磁盘加载或增量更新），仅在计数变化且无
        可用缓存时触发全量重建。
        """
        import faiss

        current_count = self.count_indexed(conn)
        if current_count == 0:
            return []

        # 尝试从磁盘加载（首次调用或缓存失效后）
        if self._faiss_index is None:
            if not self._load_index_from_disk():
                ids, vecs = self.get_all_vectors(conn)
                self._build_faiss_index(ids, vecs)
                self._cached_count = current_count

        # 缓存失效（向量数变化但磁盘已有较新索引或需要重建）
        if current_count != self._cached_count and self._faiss_index is not None:
            if current_count == self._faiss_index.ntotal:
                # 仅计数未同步，更新即可
                self._cached_count = current_count
            elif current_count > self._faiss_index.ntotal:
                # 有增量未更新到 FAISS → 全量重建（增量已在 store_vector 中处理）
                ids, vecs = self.get_all_vectors(conn)
                if len(ids) > 0:
                    self._build_faiss_index(ids, vecs)
                self._cached_count = len(ids)

        if self._faiss_index is None or self._faiss_index.ntotal == 0:
            return []

        query_vec = query_vec.reshape(1, -1).astype(np.float32)
        k = min(top_k, self._faiss_index.ntotal)
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
        """删除向量（令索引缓存失效，下次搜索时重建）"""
        conn.execute(
            "UPDATE episodic_memories SET vector = NULL WHERE id = ?",
            (memory_id,),
        )
        conn.commit()
        # 删除后无法从 HNSW 索引中精确移除，标记为过期
        if memory_id in self._mem_to_faiss_id:
            del self._mem_to_faiss_id[memory_id]
        self._cached_count = -1

    def count_indexed(self, conn) -> int:
        row = conn.execute(
            "SELECT COUNT(*) FROM episodic_memories WHERE vector IS NOT NULL"
        ).fetchone()
        return row[0] if row else 0

    def clear_incompatible_vectors(self, conn) -> int:
        """清除维度不匹配的旧向量，返回清除数量"""
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
