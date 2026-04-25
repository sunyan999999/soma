import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from soma.base import MemoryUnit


class EpisodicStore:
    """情节记忆存储 — MVP 使用 SQLite + 关键词匹配"""

    def __init__(self, persist_dir: Path, collection_name: str = "episodic"):
        persist_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = persist_dir / f"{collection_name}.db"
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._create_table()

    def _create_table(self):
        self._conn.execute(
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
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_timestamp ON episodic_memories(timestamp DESC)"
        )
        self._conn.commit()

    def add(
        self, content: str, context: Optional[Dict[str, Any]] = None, importance: float = 0.5
    ) -> str:
        memory_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc).timestamp()
        context_json = json.dumps(context or {}, ensure_ascii=False)

        self._conn.execute(
            """
            INSERT INTO episodic_memories (id, content, timestamp, importance, context_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (memory_id, content, now, importance, context_json),
        )
        self._conn.commit()
        return memory_id

    def query_by_keywords(self, keywords: List[str], top_k: int = 5) -> List[MemoryUnit]:
        if not keywords:
            return []

        # Build LIKE clauses for each keyword on content + context_json
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

    def _row_to_memory(self, row: sqlite3.Row) -> MemoryUnit:
        # sqlite3.Row 不支持 .get()，需要用索引或 keys() 检查
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

    def close(self):
        self._conn.close()
