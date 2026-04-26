import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from soma.abc import BaseMemoryStore
from soma.base import MemoryUnit


class SkillStore(BaseMemoryStore):
    """技能模式存储 — SQLite 持久化"""

    def __init__(self, persist_dir: Optional[Path] = None):
        if persist_dir is None:
            persist_dir = Path("skill_data")
        persist_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = persist_dir / "skills.db"
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._create_table()

    def _create_table(self):
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS skills (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                pattern TEXT NOT NULL,
                context_json TEXT DEFAULT '{}',
                created_at REAL NOT NULL
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_skill_created ON skills(created_at DESC)"
        )
        self._conn.commit()

    def add_skill(
        self,
        name: str,
        pattern: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        skill_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc).timestamp()
        context_json = json.dumps(context or {}, ensure_ascii=False)

        self._conn.execute(
            """
            INSERT INTO skills (id, name, pattern, context_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (skill_id, name, pattern, context_json, now),
        )
        self._conn.commit()
        return skill_id

    def query_by_keywords(
        self, keywords: List[str], top_k: int = 3
    ) -> List[MemoryUnit]:
        if not keywords:
            return []

        conditions = []
        params = []
        for kw in keywords:
            pattern = f"%{kw}%"
            conditions.append("(name LIKE ? OR pattern LIKE ? OR context_json LIKE ?)")
            params.extend([pattern, pattern, pattern])

        where_clause = " OR ".join(conditions)
        sql = f"""
            SELECT * FROM skills
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT ?
        """
        params.append(top_k)

        rows = self._conn.execute(sql, params).fetchall()
        results = []
        for row in rows:
            results.append(
                MemoryUnit(
                    id=row["id"],
                    content=f"技能: {row['name']} — {row['pattern']}",
                    timestamp=row["created_at"],
                    context=json.loads(row["context_json"]),
                    memory_type="skill",
                    importance=0.8,
                )
            )
        return results

    def count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) FROM skills").fetchone()
        return row[0] if row else 0

    def close(self):
        self._conn.close()
