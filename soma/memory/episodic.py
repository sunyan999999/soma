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
        # WAL 模式 + 性能 PRAGMA
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")       # WAL 下 NORMAL 足够安全
        self._conn.execute("PRAGMA cache_size=-8000")          # 8MB 缓存
        self._conn.execute("PRAGMA mmap_size=268435456")       # 256MB 内存映射
        self._conn.execute("PRAGMA temp_store=MEMORY")         # 临时表存内存
        self._conn.execute("PRAGMA busy_timeout=15000")        # 15秒忙等待（Windows并发场景）
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
                memory_type TEXT DEFAULT 'episodic',
                user_id TEXT NOT NULL DEFAULT '',
                session_id TEXT NOT NULL DEFAULT ''
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_timestamp ON episodic_memories(timestamp DESC)"
        )
        # 向后兼容迁移：补齐可能缺失的列
        for col, col_def in [
            ("content_hash", "TEXT NOT NULL DEFAULT ''"),
            ("user_id", "TEXT NOT NULL DEFAULT ''"),
            ("session_id", "TEXT NOT NULL DEFAULT ''"),
        ]:
            try:
                self._conn.execute(
                    f"ALTER TABLE episodic_memories ADD COLUMN {col} {col_def}"
                )
            except sqlite3.OperationalError:
                pass  # 列已存在
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_content_hash ON episodic_memories(content_hash)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_episodic_user ON episodic_memories(user_id)"
        )
        self._create_fts5()
        self._conn.commit()

    def _create_fts5(self):
        """创建 FTS5 trigram 全文索引表，用于加速中文关键词搜索"""
        self._conn.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS episodic_fts USING fts5(
                content,
                context_json,
                content='episodic_memories',
                content_rowid='rowid',
                tokenize='trigram'
            )
            """
        )
        # 触发器: INSERT → 同步到 FTS
        self._conn.executescript("""
            CREATE TRIGGER IF NOT EXISTS episodic_fts_ai AFTER INSERT ON episodic_memories BEGIN
                INSERT INTO episodic_fts(rowid, content, context_json)
                VALUES (new.rowid, new.content, new.context_json);
            END;
            CREATE TRIGGER IF NOT EXISTS episodic_fts_ad AFTER DELETE ON episodic_memories BEGIN
                INSERT INTO episodic_fts(episodic_fts, rowid, content, context_json)
                VALUES ('delete', old.rowid, old.content, old.context_json);
            END;
            CREATE TRIGGER IF NOT EXISTS episodic_fts_au AFTER UPDATE ON episodic_memories BEGIN
                INSERT INTO episodic_fts(episodic_fts, rowid, content, context_json)
                VALUES ('delete', old.rowid, old.content, old.context_json);
                INSERT INTO episodic_fts(rowid, content, context_json)
                VALUES (new.rowid, new.content, new.context_json);
            END;
        """)
        # 迁移已有数据到 FTS（幂等：如果 FTS 刚创建且为空）
        populated = self._conn.execute(
            "SELECT COUNT(*) FROM episodic_fts"
        ).fetchone()[0]
        if populated == 0:
            self._conn.execute(
                "INSERT INTO episodic_fts(rowid, content, context_json) "
                "SELECT rowid, content, context_json FROM episodic_memories"
            )

    def _compute_hash(self, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def add(
        self,
        content: str,
        context: Optional[Dict[str, Any]] = None,
        importance: float = 0.5,
        user_id: str = "",
        session_id: str = "",
    ) -> str:
        content_hash = self._compute_hash(content)

        # 去重检查：同用户 + 同内容不重复插入
        existing = self._conn.execute(
            "SELECT id FROM episodic_memories WHERE user_id = ? AND content_hash = ? LIMIT 1",
            (user_id, content_hash),
        ).fetchone()
        if existing:
            return existing["id"]

        memory_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc).timestamp()
        context_json = json.dumps(context or {}, ensure_ascii=False)

        self._conn.execute(
            """
            INSERT INTO episodic_memories (id, content, content_hash, timestamp, importance, context_json, user_id, session_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (memory_id, content, content_hash, now, importance, context_json, user_id, session_id),
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

    def query_by_keywords(
        self, keywords: List[str], top_k: int = 5,
        user_id: str = "",
        max_age_days: float = 30.0,
    ) -> List[MemoryUnit]:
        if not keywords:
            return []

        # 分离长关键词(FTS5 trigram)和短关键词(LIKE兜底)
        fts_keywords = [kw for kw in keywords if len(kw) >= 3]
        like_keywords = [kw for kw in keywords if len(kw) < 3]

        seen_ids = set()
        memories = []

        # 用户过滤子句
        user_clause = "AND em.user_id = ?" if user_id else ""
        # 时间窗口：30天内记忆（防止远古记忆污染回复）
        import math
        min_ts = datetime.now(timezone.utc).timestamp() - max_age_days * 86400.0

        # 路径1: FTS5 trigram 全文搜索（3字及以上，毫秒级）
        if fts_keywords:
            fts_query = " OR ".join(f'"{kw}"' for kw in fts_keywords)
            try:
                params = [fts_query]
                sql = f"""
                    SELECT em.* FROM episodic_memories em
                    INNER JOIN episodic_fts fts ON em.rowid = fts.rowid
                    WHERE episodic_fts MATCH ?
                    AND em.timestamp >= ? {user_clause}
                    ORDER BY em.timestamp DESC, em.importance DESC
                    LIMIT ?
                """
                params.extend([min_ts])
                if user_id:
                    params.append(user_id)
                params.append(top_k)
                rows = self._conn.execute(sql, params).fetchall()
                for r in rows:
                    mem = self._row_to_memory(r)
                    if mem.id not in seen_ids:
                        seen_ids.add(mem.id)
                        memories.append(mem)
            except sqlite3.OperationalError:
                pass  # FTS 语法错误时退回到 LIKE

        # 路径2: LIKE 兜底（短关键词 1-2 字）
        remaining = top_k - len(memories)
        if like_keywords and remaining > 0:
            conditions = ["timestamp >= ?"]
            params = [min_ts]
            if user_id:
                conditions.append("user_id = ?")
                params.append(user_id)
            if seen_ids:
                placeholders = ",".join("?" * len(seen_ids))
                conditions.append(f"id NOT IN ({placeholders})")
                params.extend(seen_ids)
            kw_conds = []
            for kw in like_keywords:
                pattern = f"%{kw}%"
                kw_conds.append("(content LIKE ? OR context_json LIKE ?)")
                params.extend([pattern, pattern])
            conditions.append("(" + " OR ".join(kw_conds) + ")")
            where_clause = " AND ".join(conditions)
            sql = f"""
                SELECT * FROM episodic_memories
                WHERE {where_clause}
                ORDER BY timestamp DESC, importance DESC
                LIMIT ?
            """
            params.append(remaining)
            rows = self._conn.execute(sql, params).fetchall()
            for r in rows:
                mem = self._row_to_memory(r)
                if mem.id not in seen_ids:
                    seen_ids.add(mem.id)
                    memories.append(mem)

        # 路径3: 纯 LIKE 兜底（FTS 失败时的完整回退）
        if not memories and not fts_keywords:
            return self._like_fallback(keywords, top_k, user_id=user_id, max_age_days=max_age_days)

        return memories

    def _like_fallback(
        self, keywords: List[str], top_k: int = 5,
        user_id: str = "",
        max_age_days: float = 30.0,
    ) -> List[MemoryUnit]:
        """纯 LIKE 搜索兜底"""
        conditions = ["timestamp >= ?"]
        min_ts = datetime.now(timezone.utc).timestamp() - max_age_days * 86400.0
        params = [min_ts]
        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)
        for kw in keywords:
            pattern = f"%{kw}%"
            conditions.append("(content LIKE ? OR context_json LIKE ?)")
            params.extend([pattern, pattern])
        sql = f"""
            SELECT * FROM episodic_memories
            WHERE {' OR '.join(conditions)}
            ORDER BY timestamp DESC, importance DESC
            LIMIT ?
        """
        params.append(top_k)
        rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_memory(r) for r in rows]

    def query_by_vector(
        self, query_vec, top_k: int = 5, user_id: str = "",
    ) -> List[MemoryUnit]:
        """向量语义搜索（可选用 user_id 隔离 + 时间窗口过滤）"""
        if self._vector_index is None:
            return []

        # 过取候选，后续在后处理中过滤
        fetch_k = top_k * 3 if user_id else top_k
        results = self._vector_index.similarity_search(
            self._conn, query_vec, fetch_k
        )
        memories = []
        min_ts = datetime.now(timezone.utc).timestamp() - 30.0 * 86400.0
        for mid, score in results:
            mem = self.get(mid)
            if mem is None:
                continue
            # user_id 过滤
            if user_id and mem.user_id and mem.user_id != user_id:
                continue
            # 时间窗口过滤：排除30天外的远古记忆
            if mem.timestamp < min_ts:
                continue
            mem.context["_vector_score"] = score
            memories.append(mem)
            if len(memories) >= top_k:
                break
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
            user_id=row["user_id"] if "user_id" in row.keys() else "",
            session_id=row["session_id"] if "session_id" in row.keys() else "",
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
