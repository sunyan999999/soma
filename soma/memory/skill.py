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
        self._conn.execute("PRAGMA journal_mode=WAL")
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
        self._create_fts5()
        self._conn.commit()

    def _create_fts5(self):
        """创建 FTS5 trigram 全文索引"""
        self._conn.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS skills_fts USING fts5(
                name,
                pattern,
                context_json,
                content='skills',
                content_rowid='rowid',
                tokenize='trigram'
            )
            """
        )
        self._conn.executescript("""
            CREATE TRIGGER IF NOT EXISTS skills_fts_ai AFTER INSERT ON skills BEGIN
                INSERT INTO skills_fts(rowid, name, pattern, context_json)
                VALUES (new.rowid, new.name, new.pattern, new.context_json);
            END;
            CREATE TRIGGER IF NOT EXISTS skills_fts_ad AFTER DELETE ON skills BEGIN
                INSERT INTO skills_fts(skills_fts, rowid, name, pattern, context_json)
                VALUES ('delete', old.rowid, old.name, old.pattern, old.context_json);
            END;
            CREATE TRIGGER IF NOT EXISTS skills_fts_au AFTER UPDATE ON skills BEGIN
                INSERT INTO skills_fts(skills_fts, rowid, name, pattern, context_json)
                VALUES ('delete', old.rowid, old.name, old.pattern, old.context_json);
                INSERT INTO skills_fts(rowid, name, pattern, context_json)
                VALUES (new.rowid, new.name, new.pattern, new.context_json);
            END;
        """)
        populated = self._conn.execute(
            "SELECT COUNT(*) FROM skills_fts"
        ).fetchone()[0]
        if populated == 0:
            self._conn.execute(
                "INSERT INTO skills_fts(rowid, name, pattern, context_json) "
                "SELECT rowid, name, pattern, context_json FROM skills"
            )

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

        # FTS5 trigram 全文搜索（3字及以上）+ LIKE 兜底
        fts_keywords = [kw for kw in keywords if len(kw) >= 3]
        memories: List[MemoryUnit] = []
        seen_ids: set = set()

        if fts_keywords:
            fts_query = " OR ".join(f'"{kw}"' for kw in fts_keywords)
            try:
                sql = """
                    SELECT s.* FROM skills s
                    INNER JOIN skills_fts fts ON s.rowid = fts.rowid
                    WHERE skills_fts MATCH ?
                    ORDER BY s.created_at DESC
                    LIMIT ?
                """
                rows = self._conn.execute(sql, (fts_query, top_k)).fetchall()
                for row in rows:
                    mid = row["id"]
                    if mid not in seen_ids:
                        seen_ids.add(mid)
                        memories.append(
                            MemoryUnit(
                                id=mid,
                                content=f"技能: {row['name']} — {row['pattern']}",
                                timestamp=row["created_at"],
                                context=json.loads(row["context_json"]),
                                memory_type="skill",
                                importance=0.8,
                            )
                        )
            except sqlite3.OperationalError:
                pass

        # LIKE 兜底（短关键词 1-2 字）
        remaining = top_k - len(memories)
        like_keywords = [kw for kw in keywords if len(kw) < 3]
        if like_keywords and remaining > 0:
            conditions = []
            params = []
            if seen_ids:
                placeholders = ",".join("?" * len(seen_ids))
                conditions.append(f"id NOT IN ({placeholders})")
                params.extend(seen_ids)
            kw_conds = []
            for kw in like_keywords:
                pattern = f"%{kw}%"
                kw_conds.append("(name LIKE ? OR pattern LIKE ? OR context_json LIKE ?)")
                params.extend([pattern, pattern, pattern])
            conditions.append("(" + " OR ".join(kw_conds) + ")")
            sql = f"""
                SELECT * FROM skills
                WHERE {' AND '.join(conditions)}
                ORDER BY created_at DESC
                LIMIT ?
            """
            params.append(remaining)
            rows = self._conn.execute(sql, params).fetchall()
            for row in rows:
                mid = row["id"]
                if mid not in seen_ids:
                    memories.append(
                        MemoryUnit(
                            id=mid,
                            content=f"技能: {row['name']} — {row['pattern']}",
                            timestamp=row["created_at"],
                            context=json.loads(row["context_json"]),
                            memory_type="skill",
                            importance=0.8,
                        )
                    )

        return memories

    def count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) FROM skills").fetchone()
        return row[0] if row else 0

    def close(self):
        self._conn.close()
