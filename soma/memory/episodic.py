import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from soma.abc import BaseMemoryStore
from soma.base import MemoryUnit


class EpisodicStore(BaseMemoryStore):
    """情节记忆存储 — SQLite 持久化 + 可选向量语义搜索"""

    def __init__(
        self,
        persist_dir: Path,
        collection_name: str = "episodic",
        embedder=None,
        use_vector_search: bool = False,
    ):
        persist_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = persist_dir / f"{collection_name}.db"
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._embedder = embedder
        self._use_vector = use_vector_search and embedder is not None

        self._create_table()
        self._vector_index = None

        if self._use_vector:
            from soma.vector_store import NumpyVectorIndex

            dim = embedder.dimension if embedder else 384
            self._vector_index = NumpyVectorIndex(self._db_path, dim)
            self._vector_index.ensure_table(self._conn)
            # 维度迁移：清除嵌入模型变更导致的不兼容旧向量
            stale = self._vector_index.clear_incompatible_vectors(self._conn)
            if stale > 0:
                # 重新生成所有缺失的向量
                rebuilt = self.rebuild_vectors()
                if rebuilt > 0:
                    import logging
                    logging.getLogger("soma").info(
                        f"向量维度迁移: 清除 {stale} 条旧向量, 重建 {rebuilt} 条"
                    )

    def _create_table(self):
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS episodic_memories (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                content_hash TEXT NOT NULL DEFAULT '',
                timestamp REAL NOT NULL,
                importance REAL DEFAULT 0.5,
                access_count INTEGER DEFAULT 0,
                context_json TEXT DEFAULT '{}',
                memory_type TEXT DEFAULT 'episodic'
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_timestamp ON episodic_memories(timestamp DESC)"
        )
        # 为旧数据库补齐 content_hash 列（必须在 CREATE INDEX 之前）
        try:
            self._conn.execute(
                "ALTER TABLE episodic_memories ADD COLUMN content_hash TEXT NOT NULL DEFAULT ''"
            )
        except sqlite3.OperationalError:
            pass  # 列已存在
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_content_hash ON episodic_memories(content_hash)"
        )
        self._conn.commit()

    def _compute_hash(self, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def add(
        self,
        content: str,
        context: Optional[Dict[str, Any]] = None,
        importance: float = 0.5,
    ) -> str:
        content_hash = self._compute_hash(content)

        # 去重检查：完全相同的内容不重复插入
        existing = self._conn.execute(
            "SELECT id FROM episodic_memories WHERE content_hash = ? LIMIT 1",
            (content_hash,),
        ).fetchone()
        if existing:
            return existing["id"]

        memory_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc).timestamp()
        context_json = json.dumps(context or {}, ensure_ascii=False)

        self._conn.execute(
            """
            INSERT INTO episodic_memories (id, content, content_hash, timestamp, importance, context_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (memory_id, content, content_hash, now, importance, context_json),
        )
        self._conn.commit()

        # 自动生成嵌入向量
        if self._use_vector and self._embedder is not None:
            try:
                vec = self._embedder.encode(content)
                self._vector_index.store_vector(self._conn, memory_id, vec)
            except Exception:
                pass  # 嵌入失败不阻塞记忆存储

        return memory_id

    def query_by_keywords(self, keywords: List[str], top_k: int = 5) -> List[MemoryUnit]:
        if not keywords:
            return []

        conditions = []
        params = []
        for kw in keywords:
            pattern = f"%{kw}%"
            conditions.append("(content LIKE ? OR context_json LIKE ?)")
            params.extend([pattern, pattern])

        where_clause = " OR ".join(conditions)
        sql = f"""
            SELECT * FROM episodic_memories
            WHERE {where_clause}
            ORDER BY timestamp DESC, importance DESC
            LIMIT ?
        """
        params.append(top_k)

        rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_memory(r) for r in rows]

    def query_by_vector(
        self, query_vec, top_k: int = 5
    ) -> List[MemoryUnit]:
        """向量语义搜索"""
        if self._vector_index is None:
            return self.query_by_keywords([], top_k)  # 返回空

        results = self._vector_index.similarity_search(
            self._conn, query_vec, top_k
        )
        memories = []
        for mid, score in results:
            mem = self.get(mid)
            if mem is not None:
                mem.context["_vector_score"] = score
                memories.append(mem)
        return memories

    def rebuild_vectors(self, batch_size: int = 100) -> int:
        """为缺失向量的记忆批量生成嵌入"""
        if self._embedder is None or self._vector_index is None:
            return 0

        rows = self._conn.execute(
            "SELECT id, content FROM episodic_memories WHERE vector IS NULL"
        ).fetchall()

        count = 0
        for i in range(0, len(rows), batch_size):
            batch = rows[i : i + batch_size]
            ids = [r[0] for r in batch]
            texts = [r[1] for r in batch]
            vecs = self._embedder.encode_batch(texts)
            for j, mid in enumerate(ids):
                self._vector_index.store_vector(self._conn, mid, vecs[j])
                count += 1

        return count

    def get(self, memory_id: str) -> Optional[MemoryUnit]:
        row = self._conn.execute(
            "SELECT * FROM episodic_memories WHERE id = ?", (memory_id,)
        ).fetchone()
        return self._row_to_memory(row) if row else None

    def delete(self, memory_id: str) -> bool:
        cursor = self._conn.execute(
            "DELETE FROM episodic_memories WHERE id = ?", (memory_id,)
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) FROM episodic_memories").fetchone()
        return row[0] if row else 0

    def count_indexed(self) -> int:
        if self._vector_index is None:
            return 0
        return self._vector_index.count_indexed(self._conn)

    def _row_to_memory(self, row: sqlite3.Row) -> MemoryUnit:
        mem_type = row["memory_type"] if "memory_type" in row.keys() else "episodic"
        return MemoryUnit(
            id=row["id"],
            content=row["content"],
            timestamp=row["timestamp"],
            importance=row["importance"],
            access_count=row["access_count"],
            context=json.loads(row["context_json"]),
            memory_type=mem_type,
        )

    @property
    def use_vector(self) -> bool:
        return self._use_vector

    def increment_access(self, memory_id: str) -> bool:
        """递增记忆的访问计数并持久化"""
        self._conn.execute(
            "UPDATE episodic_memories SET access_count = access_count + 1 WHERE id = ?",
            (memory_id,),
        )
        self._conn.commit()
        return self._conn.total_changes > 0

    def close(self):
        self._conn.close()
