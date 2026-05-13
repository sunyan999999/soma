import hashlib
import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from soma.abc import BaseMemoryStore
from soma.base import MemoryUnit

_log = logging.getLogger("soma.memory.episodic")


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

            dim = embedder.dimension if embedder else 512
            self._vector_index = NumpyVectorIndex(self._db_path, dim)
            self._vector_index.ensure_table(self._conn)
            # 维度迁移：清除嵌入模型变更导致的不兼容旧向量
            stale = self._vector_index.clear_incompatible_vectors(self._conn)
            if stale > 0:
                rebuilt = self.rebuild_vectors()
                if rebuilt > 0:
                    _log.info("向量维度迁移: 清除 %d 条旧向量, 重建 %d 条", stale, rebuilt)

            # v0.9.0: 向量健康检查 — 历史记忆可能缺少向量（向量搜索后启用场景）
            total = self.count()
            indexed = self._vector_index.count_indexed(self._conn)
            if total > 10 and indexed < total * 0.5:
                _log.info("向量健康检查: %d/%d 条记忆缺少向量，开始重建...", total - indexed, total)
                rebuilt = self.rebuild_vectors()
                if rebuilt > 0:
                    _log.info("向量健康检查完成: 已重建 %d 条向量", rebuilt)

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
                session_id TEXT NOT NULL DEFAULT '',
                agent_id TEXT NOT NULL DEFAULT '',
                shared_group_id TEXT NOT NULL DEFAULT ''
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
            ("agent_id", "TEXT NOT NULL DEFAULT ''"),
            ("shared_group_id", "TEXT NOT NULL DEFAULT ''"),
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
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_episodic_agent ON episodic_memories(agent_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_episodic_group ON episodic_memories(shared_group_id)"
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
        agent_id: str = "",
        shared_group_id: str = "",
    ) -> str:
        content_hash = self._compute_hash(content)

        # 去重检查：同用户 + 同agent + 同内容不重复插入
        existing = self._conn.execute(
            "SELECT id FROM episodic_memories WHERE user_id = ? AND agent_id = ? "
            "AND content_hash = ? LIMIT 1",
            (user_id, agent_id, content_hash),
        ).fetchone()
        if existing:
            return existing["id"]

        memory_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc).timestamp()
        context_json = json.dumps(context or {}, ensure_ascii=False)

        self._conn.execute(
            """
            INSERT INTO episodic_memories (id, content, content_hash, timestamp, importance,
                context_json, user_id, session_id, agent_id, shared_group_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (memory_id, content, content_hash, now, importance, context_json,
             user_id, session_id, agent_id, shared_group_id),
        )
        self._conn.commit()

        # 自动生成嵌入向量
        if self._use_vector and self._embedder is not None:
            try:
                vec = self._embedder.encode(content)
                self._vector_index.store_vector(self._conn, memory_id, vec)
            except Exception:
                _log.warning("嵌入向量生成失败，memory_id=%s，记忆已存储但无法语义搜索", memory_id)

        return memory_id

    def query_by_keywords(
        self, keywords: List[str], top_k: int = 5,
        user_id: str = "",
        agent_id: str = "",
        group_id: str = "",
        max_age_days: Optional[float] = None,
    ) -> List[MemoryUnit]:
        if not keywords:
            return []

        from soma.memory.search_utils import fts5_keyword_search

        return fts5_keyword_search(
            self._conn,
            keywords,
            table_name="episodic_memories",
            fts_table="episodic_fts",
            search_cols=["content", "context_json"],
            id_col="id",
            time_col="timestamp",
            importance_col="importance",
            user_col="user_id",
            row_converter=self._row_to_memory,
            top_k=top_k,
            user_id=user_id,
            max_age_days=max_age_days,
            agent_col="agent_id" if agent_id else "",
            agent_id=agent_id,
            group_col="shared_group_id" if group_id else "",
            group_id=group_id,
        )

    def query_by_vector(
        self, query_vec, top_k: int = 5, user_id: str = "",
        agent_id: str = "",
        group_id: str = "",
        max_age_days: Optional[float] = None,
    ) -> List[MemoryUnit]:
        """向量语义搜索（支持 user_id + agent/group 隔离 + 时间窗口过滤）"""
        if self._vector_index is None:
            return []

        filter_count = sum(1 for x in (user_id, agent_id) if x)
        fetch_k = top_k * (3 if filter_count else 1)
        results = self._vector_index.similarity_search(
            self._conn, query_vec, fetch_k
        )
        memories = []
        min_ts = None
        if max_age_days is not None:
            min_ts = datetime.now(timezone.utc).timestamp() - max_age_days * 86400.0
        for mid, score in results:
            mem = self.get(mid)
            if mem is None:
                continue
            # user_id 过滤（空user_id的记忆在指定user_id时被过滤）
            if user_id and mem.user_id != user_id:
                continue
            # agent/group 过滤：agent自己的 + 组共享的（空agent_id的记忆在指定agent_id时被过滤）
            if agent_id and mem.agent_id != agent_id:
                if not (group_id and mem.shared_group_id == group_id):
                    continue
            # 时间窗口过滤
            if min_ts is not None and mem.timestamp < min_ts:
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
            agent_id=row["agent_id"] if "agent_id" in row.keys() else "",
            shared_group_id=row["shared_group_id"] if "shared_group_id" in row.keys() else "",
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

    # ── v0.7.0 记忆智能 ─────────────────────────────────

    def consolidate(self, user_id: str = "", max_merges: int = 10) -> int:
        """执行一次记忆合并扫描（摘要合并）"""
        from soma.memory.consolidation import ConsolidationEngine
        engine = ConsolidationEngine(self._conn, self._embedder)
        return engine.run_consolidation_pass(user_id=user_id, max_merges=max_merges)

    def forget(self, user_id: str = "", max_archive: int = 50) -> dict:
        """执行一次遗忘扫描（三层遗忘策略）"""
        from soma.memory.forgetting import ForgettingEngine
        engine = ForgettingEngine(self._conn)
        return engine.run_forgetting_pass(user_id=user_id, max_archive=max_archive)

    def recall_archived(self, query: str = "", user_id: str = "", top_k: int = 20):
        """从归档中浏览/恢复记忆"""
        from soma.memory.forgetting import ForgettingEngine
        engine = ForgettingEngine(self._conn)
        return engine.recall_archived(query=query, user_id=user_id, top_k=top_k)

    def restore_archived(self, memory_id: str) -> bool:
        """恢复一条归档记忆"""
        from soma.memory.forgetting import ForgettingEngine
        engine = ForgettingEngine(self._conn)
        return engine.restore(memory_id)

    def import_knowledge(
        self, source_path: str, user_id: str = "", session_id: str = ""
    ) -> list:
        """从文件导入外部知识"""
        from soma.memory.external import FileSource, ExternalKnowledgeImporter
        source = FileSource(source_path)
        importer = ExternalKnowledgeImporter(self)
        return importer.import_source(source, user_id=user_id, session_id=session_id)

    def close(self):
        self._conn.close()
