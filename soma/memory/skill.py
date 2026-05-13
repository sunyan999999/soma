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
                user_id TEXT NOT NULL DEFAULT '',
                agent_id TEXT NOT NULL DEFAULT '',
                shared_group_id TEXT NOT NULL DEFAULT ''
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_skill_created ON skills(created_at DESC)"
        )
        # 先迁移列，再创建索引（旧数据库可能无这些列）
        for col in ("user_id", "agent_id", "shared_group_id"):
            try:
                self._conn.execute(
                    f"ALTER TABLE skills ADD COLUMN {col} TEXT NOT NULL DEFAULT ''"
                )
            except sqlite3.OperationalError:
                pass
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_skill_user ON skills(user_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_skill_agent ON skills(agent_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_skill_group ON skills(shared_group_id)"
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
        agent_id: str = "",
        shared_group_id: str = "",
    ) -> str:
        # 去重检查：同用户 + 同agent + 同名称 + 同模式不重复插入
        existing = self._conn.execute(
            "SELECT id FROM skills WHERE user_id = ? AND agent_id = ? "
            "AND name = ? AND pattern = ? LIMIT 1",
            (user_id, agent_id, name, pattern),
        ).fetchone()
        if existing:
            return existing["id"]

        skill_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc).timestamp()
        context_json = json.dumps(context or {}, ensure_ascii=False)

        self._conn.execute(
            """
            INSERT INTO skills (id, name, pattern, context_json, created_at,
                user_id, agent_id, shared_group_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (skill_id, name, pattern, context_json, now, user_id, agent_id, shared_group_id),
        )
        self._conn.commit()
        return skill_id

    def _row_to_memory(self, row: sqlite3.Row) -> MemoryUnit:
        return MemoryUnit(
            id=row["id"],
            content=f"技能: {row['name']} — {row['pattern']}",
            timestamp=row["created_at"],
            context=json.loads(row["context_json"]),
            memory_type="skill",
            importance=0.8,
        )

    def query_by_keywords(
        self, keywords: List[str], top_k: int = 3,
        user_id: str = "",
        agent_id: str = "",
        group_id: str = "",
        max_age_days: Optional[float] = None,
    ) -> List[MemoryUnit]:
        """按关键词搜索技能。

        max_age_days 默认 None 表示不过滤时间（技能是永久积累的思维模式）。
        传入具体数值可启用时间窗口过滤。
        """
        if not keywords:
            return []

        from soma.memory.search_utils import fts5_keyword_search

        return fts5_keyword_search(
            self._conn,
            keywords,
            table_name="skills",
            fts_table="skills_fts",
            search_cols=["name", "pattern", "context_json"],
            id_col="id",
            time_col="created_at",
            importance_col=None,
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

    def count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) FROM skills").fetchone()
        return row[0] if row else 0

    def close(self):
        self._conn.close()
