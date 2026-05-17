"""
L2 场景块存储 — SQLite 持久化 + Markdown 白盒输出。

Scene（场景块）是对多条情节记忆的主题聚合。SceneStore 采用双层存储：
- SQLite 数据库：结构化元数据，高效检索和关联追溯
- Markdown 文件：人类可读的完整内容，用于调试和审查
"""

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from soma.abc import BaseMemoryStore

_log = logging.getLogger("soma.memory.scene")

SCHEMA_VERSION = 1


class SceneStore(BaseMemoryStore):
    """L2 场景块存储 — 将多条相关情节记忆聚合为主题场景"""

    def __init__(self, persist_dir: Path, collection_name: str = "scenes"):
        persist_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = persist_dir / f"{collection_name}.db"
        self._md_dir = persist_dir / collection_name
        self._md_dir.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._create_table()

    def _create_table(self):
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA cache_size=-8000")
        self._conn.execute("PRAGMA busy_timeout=15000")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS scenes (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL,
                summary TEXT NOT NULL,
                tags TEXT DEFAULT '[]',
                evidence_ids TEXT NOT NULL DEFAULT '[]',
                importance REAL DEFAULT 0.5,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                md_path TEXT NOT NULL DEFAULT '',
                schema_version INTEGER DEFAULT 1
            )
            """
        )
        for col_def, col_name in [
            ("INTEGER DEFAULT 1", "schema_version"),
        ]:
            try:
                self._conn.execute(
                    f"ALTER TABLE scenes ADD COLUMN {col_name} {col_def}"
                )
            except sqlite3.OperationalError:
                pass
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_scenes_user ON scenes(user_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_scenes_created ON scenes(created_at DESC)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_scenes_importance ON scenes(importance DESC)"
        )
        self._conn.commit()

    # ── 公共 API ──

    def add_scene(
        self,
        title: str,
        summary: str,
        tags: Optional[List[str]] = None,
        evidence_ids: Optional[List[str]] = None,
        importance: float = 0.5,
        user_id: str = "",
    ) -> str:
        """添加场景块，返回 scene_id。同用户+同标题自动去重。"""
        existing = self._conn.execute(
            "SELECT id FROM scenes WHERE user_id = ? AND title = ? LIMIT 1",
            (user_id, title),
        ).fetchone()
        if existing:
            return existing["id"]

        scene_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc).timestamp()
        tags_json = json.dumps(tags or [], ensure_ascii=False)
        evidence_json = json.dumps(evidence_ids or [], ensure_ascii=False)
        md_path = str(self._md_dir / f"scene_{scene_id[:12]}.md")

        self._conn.execute(
            """INSERT INTO scenes (id, user_id, title, summary, tags, evidence_ids,
               importance, created_at, updated_at, md_path)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (scene_id, user_id, title, summary, tags_json, evidence_json,
             importance, now, now, md_path),
        )
        self._conn.commit()
        self._write_markdown(scene_id)
        _log.debug("Scene added: %s (user=%s)", title, user_id)
        return scene_id

    def get_scene(self, scene_id: str) -> Optional[Dict]:
        """按 ID 获取单个场景"""
        row = self._conn.execute(
            "SELECT * FROM scenes WHERE id = ?", (scene_id,)
        ).fetchone()
        if not row:
            return None
        return self._row_to_dict(row)

    def get_scenes(
        self,
        user_id: str = "",
        top_k: int = 10,
        min_importance: float = 0.0,
    ) -> List[Dict]:
        """获取场景列表，按重要性降序"""
        rows = self._conn.execute(
            "SELECT * FROM scenes WHERE user_id = ? AND importance >= ? "
            "ORDER BY importance DESC, created_at DESC LIMIT ?",
            (user_id, min_importance, top_k),
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def delete_scene(self, scene_id: str) -> bool:
        """删除场景及其 Markdown 文件"""
        row = self._conn.execute(
            "SELECT md_path FROM scenes WHERE id = ?", (scene_id,)
        ).fetchone()
        if not row:
            return False
        self._conn.execute("DELETE FROM scenes WHERE id = ?", (scene_id,))
        self._conn.commit()
        if row["md_path"]:
            try:
                Path(row["md_path"]).unlink(missing_ok=True)
            except OSError:
                pass
        return True

    def count(self, user_id: str = "") -> int:
        """返回场景总数"""
        if user_id:
            return self._conn.execute(
                "SELECT COUNT(*) FROM scenes WHERE user_id = ?", (user_id,)
            ).fetchone()[0]
        return self._conn.execute(
            "SELECT COUNT(*) FROM scenes"
        ).fetchone()[0]

    def generate_markdown(self, scene_id: str) -> str:
        """生成指定场景的 Markdown 文档"""
        scene = self.get_scene(scene_id)
        if not scene:
            return ""
        return self._format_scene_md(scene)

    def close(self):
        """关闭数据库连接"""
        self._conn.close()

    # ── 基类兼容接口 ──

    def store(self, content: str, context: Optional[dict] = None,
              importance: float = 0.5) -> str:
        ctx = context or {}
        return self.add_scene(
            title=ctx.get("title", content[:60]),
            summary=content,
            tags=ctx.get("tags"),
            evidence_ids=ctx.get("evidence_ids"),
            importance=importance,
            user_id=ctx.get("user_id", ""),
        )

    def query(self, query_text: str, top_k: int = 10) -> List[Dict]:
        rows = self._conn.execute(
            "SELECT * FROM scenes WHERE title LIKE ? OR summary LIKE ? "
            "ORDER BY importance DESC LIMIT ?",
            (f"%{query_text}%", f"%{query_text}%", top_k),
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def delete(self, memory_id: str) -> bool:
        return self.delete_scene(memory_id)

    # ── 内部辅助 ──

    def _row_to_dict(self, row: sqlite3.Row) -> Dict:
        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "title": row["title"],
            "summary": row["summary"],
            "tags": json.loads(row["tags"]),
            "evidence_ids": json.loads(row["evidence_ids"]),
            "importance": row["importance"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "md_path": row["md_path"],
        }

    def _format_scene_md(self, scene: Dict) -> str:
        tags = scene.get("tags", [])
        evidence = scene.get("evidence_ids", [])
        created = datetime.fromtimestamp(
            scene["created_at"], tz=timezone.utc
        ).strftime("%Y-%m-%d %H:%M:%S UTC")

        lines = [
            f"# Scene: {scene['title']}",
            f"- **ID**: `{scene['id']}`",
            f"- **User**: {scene['user_id'] or '(default)'}",
            f"- **Time**: {created}",
            f"- **Importance**: {scene['importance']:.2f}",
            "",
            "## Summary",
            scene["summary"],
            "",
        ]
        if tags:
            lines.append("## Tags")
            lines.extend(f"- {t}" for t in tags)
            lines.append("")
        if evidence:
            lines.append("## Evidence (Linked Episodic Memories)")
            lines.extend(f"- `[{eid[:12]}...]` — see episodic store" for eid in evidence[:20])
            lines.append("")
        return "\n".join(lines)

    def _write_markdown(self, scene_id: str):
        md = self.generate_markdown(scene_id)
        if not md:
            return
        scene = self.get_scene(scene_id)
        if scene and scene.get("md_path"):
            try:
                Path(scene["md_path"]).write_text(md, encoding="utf-8")
            except OSError as exc:
                _log.warning("Markdown 写入失败: %s", exc)
