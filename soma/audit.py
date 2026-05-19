"""审计日志 — 企业级操作追踪（v1.0.1）

零外部依赖，SQLite 持久化。记录所有记忆 CRUD 操作，支持按时间/用户/操作类型检索。

用法::

    from soma.audit import AuditLogger

    audit = AuditLogger(persist_dir="soma_data")
    audit.log("memory_create", user_id="alice", details={"memory_id": "abc123"})
    records = audit.query(user_id="alice", limit=50)
"""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class AuditLogger:
    """审计日志记录器 — 基于 SQLite 的不可变事件存储"""

    def __init__(self, persist_dir: Path, db_name: str = "audit.db"):
        persist_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = persist_dir / db_name
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._create_table()

    def _create_table(self):
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                user_id TEXT NOT NULL DEFAULT '',
                session_id TEXT DEFAULT '',
                details TEXT DEFAULT '{}',
                ip_address TEXT DEFAULT '',
                created_at REAL NOT NULL
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id, created_at)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_type ON audit_log(event_type, created_at)"
        )
        self._conn.commit()

    # ── 写入 ────────────────────────────────────────────────────

    def log(
        self,
        event_type: str,
        user_id: str = "",
        session_id: str = "",
        details: Optional[Dict[str, Any]] = None,
        ip_address: str = "",
    ) -> str:
        """记录一条审计事件。返回事件 ID。

        event_type 建议取值:
        - memory_create / memory_read / memory_update / memory_delete
        - semantic_create / semantic_delete
        - scene_extract / profile_update
        - agent_register / agent_deregister
        - config_change / evolution_trigger
        """
        event_id = uuid.uuid4().hex
        now_ts = datetime.now(timezone.utc).timestamp()
        self._conn.execute(
            "INSERT INTO audit_log (id, event_type, user_id, session_id, details, ip_address, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (event_id, event_type, user_id, session_id,
             json.dumps(details or {}, ensure_ascii=False),
             ip_address, now_ts),
        )
        self._conn.commit()
        return event_id

    # ── 查询 ────────────────────────────────────────────────────

    def query(
        self,
        user_id: str = "",
        event_type: str = "",
        since: Optional[float] = None,
        until: Optional[float] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """按条件检索审计事件。返回按时间倒序排列。"""
        conditions = []
        params: list = []

        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)
        if event_type:
            conditions.append("event_type = ?")
            params.append(event_type)
        if since is not None:
            conditions.append("created_at >= ?")
            params.append(since)
        if until is not None:
            conditions.append("created_at <= ?")
            params.append(until)

        where = " AND ".join(conditions) if conditions else "1=1"
        params.extend([limit, offset])

        rows = self._conn.execute(
            f"SELECT * FROM audit_log WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()

        return [{
            "id": r["id"],
            "event_type": r["event_type"],
            "user_id": r["user_id"],
            "session_id": r["session_id"],
            "details": json.loads(r["details"]),
            "ip_address": r["ip_address"],
            "created_at": r["created_at"],
        } for r in rows]

    def count(
        self,
        user_id: str = "",
        event_type: str = "",
        since: Optional[float] = None,
    ) -> int:
        """统计审计事件数量"""
        conditions = []
        params: list = []

        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)
        if event_type:
            conditions.append("event_type = ?")
            params.append(event_type)
        if since is not None:
            conditions.append("created_at >= ?")
            params.append(since)

        where = " AND ".join(conditions) if conditions else "1=1"
        row = self._conn.execute(
            f"SELECT COUNT(*) as cnt FROM audit_log WHERE {where}", params
        ).fetchone()
        return row["cnt"] if row else 0

    def stats(self) -> Dict[str, Any]:
        """审计摘要统计"""
        total = self._conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
        by_type = {}
        for row in self._conn.execute(
            "SELECT event_type, COUNT(*) as cnt FROM audit_log GROUP BY event_type"
        ).fetchall():
            by_type[row["event_type"]] = row["cnt"]
        by_user = {}
        for row in self._conn.execute(
            "SELECT user_id, COUNT(*) as cnt FROM audit_log WHERE user_id != '' GROUP BY user_id"
        ).fetchall():
            by_user[row["user_id"]] = row["cnt"]
        return {
            "total_events": total,
            "by_type": by_type,
            "by_user": by_user,
        }

    def close(self):
        self._conn.close()
