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
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA cache_size=-2000")       # 2MB 缓存（技能数据量最小）
        self._conn.execute("PRAGMA busy_timeout=15000")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS skills (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                pattern TEXT NOT NULL,
                context_json TEXT DEFAULT '{}',
                created_at REAL NOT NULL,
                user_id TEXT NOT NULL DEFAULT ''
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_skill_created ON skills(created_at DESC)"
        )
        # 先迁移列，再创建索引（旧数据库可能无 user_id 列）
        try:
            self._conn.execute(
                "ALTER TABLE skills ADD COLUMN user_id TEXT NOT NULL DEFAULT ''"
            )
        except sqlite3.OperationalError:
            pass
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_skill_user ON skills(user_id)"
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
        user_id: str = "",
    ) -> str:
        # 去重检查：同用户 + 同名称 + 同模式不重复插入
        existing = self._conn.execute(
            "SELECT id FROM skills WHERE user_id = ? AND name = ? AND pattern = ? LIMIT 1",
            (user_id, name, pattern),
        ).fetchone()
        if existing:
            return existing["id"]

        skill_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc).timestamp()
        context_json = json.dumps(context or {}, ensure_ascii=False)

        self._conn.execute(
            """
            INSERT INTO skills (id, name, pattern, context_json, created_at, user_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (skill_id, name, pattern, context_json, now, user_id),
        )
        self._conn.commit()
        return skill_id

    @staticmethod
    def _escape_fts5(kw: str) -> str:
        """转义 FTS5 双引号，防止语法损坏"""
        return kw.replace('"', '""')

    def query_by_keywords(
        self, keywords: List[str], top_k: int = 3,
        user_id: str = "",
        max_age_days: Optional[float] = None,
    ) -> List[MemoryUnit]:
        """按关键词搜索技能。

        max_age_days 默认 None 表示不过滤时间（技能是永久积累的思维模式）。
        传入具体数值可启用时间窗口过滤。
        """
        if not keywords:
            return []

        time_clause = ""
        time_params = []
        if max_age_days is not None:
            import math
            min_ts = datetime.now(timezone.utc).timestamp() - max_age_days * 86400.0
            time_clause = "AND s.created_at >= ?"
            time_params = [min_ts]

        # FTS5 trigram 全文搜索（3字及以上）+ LIKE 兜底
        fts_keywords = [kw for kw in keywords if len(kw) >= 3]
        memories: List[MemoryUnit] = []
        seen_ids: set = set()
        user_clause = "AND s.user_id = ?" if user_id else ""

        if fts_keywords:
            fts_query = " OR ".join(
                f'"{self._escape_fts5(kw)}"' for kw in fts_keywords
            )
            try:
                params = [fts_query] + time_params
                sql = f"""
                    SELECT s.* FROM skills s
                    INNER JOIN skills_fts fts ON s.rowid = fts.rowid
                    WHERE skills_fts MATCH ?
                    {time_clause}
                    {user_clause}
                    ORDER BY s.created_at DESC
                    LIMIT ?
                """
                if user_id:
                    params.append(user_id)
                params.append(top_k)
                rows = self._conn.execute(sql, params).fetchall()
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
            conditions = [] if max_age_days is None else ["created_at >= ?"]
            params = [] if max_age_days is None else time_params.copy()
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
