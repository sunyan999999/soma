"""
L3 用户画像存储 — SQLite 持久化 + Markdown 白盒输出。

Profile（用户画像）是从多个场景块中提取的稳定用户特征。
采用双层存储：SQLite（结构化） + Markdown（可读文档）。

每条 Profile 条目表示一个用户特征：
- trait_type: "preference" | "skill" | "habit" | "knowledge_gap" | "goal"
- trait_key: 特征名，如 "preferred_language"
- trait_value: 特征值，如 "Python"
- confidence: 置信度 [0, 1]，同 key 多次出现时累积递增
"""

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from soma.abc import BaseMemoryStore

_log = logging.getLogger("soma.memory.profile")


class ProfileStore(BaseMemoryStore):
    """L3 用户画像存储 — 跨场景提取稳定用户特征"""

    # 允许的特征类型
    VALID_TRAIT_TYPES = {"preference", "skill", "habit", "knowledge_gap", "goal"}

    def __init__(self, persist_dir: Path, collection_name: str = "profiles"):
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
            CREATE TABLE IF NOT EXISTS profile_entries (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL DEFAULT '',
                trait_type TEXT NOT NULL,
                trait_key TEXT NOT NULL,
                trait_value TEXT NOT NULL,
                confidence REAL DEFAULT 0.5,
                evidence_ids TEXT NOT NULL DEFAULT '[]',
                source_scene_ids TEXT NOT NULL DEFAULT '[]',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                md_path TEXT NOT NULL DEFAULT ''
            )
            """
        )
        for idx_spec in [
            "CREATE INDEX IF NOT EXISTS idx_profile_user ON profile_entries(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_profile_type ON profile_entries(trait_type)",
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_profile_user_type_key "
                "ON profile_entries(user_id, trait_type, trait_key)",
        ]:
            self._conn.execute(idx_spec)
        self._conn.commit()

    # ── 公共 API ──

    def upsert_entry(
        self,
        trait_type: str,
        trait_key: str,
        trait_value: str,
        confidence: float = 0.5,
        evidence_ids: Optional[List[str]] = None,
        source_scene_ids: Optional[List[str]] = None,
        user_id: str = "",
    ) -> str:
        """插入或更新画像条目。同用户+同类型+同key时，confidence 取最高值+0.05奖励。"""
        if trait_type not in self.VALID_TRAIT_TYPES:
            raise ValueError(
                f"无效 trait_type: {trait_type}，有效值: {self.VALID_TRAIT_TYPES}"
            )

        now = datetime.now(timezone.utc).timestamp()
        evidence_json = json.dumps(evidence_ids or [], ensure_ascii=False)
        scene_json = json.dumps(source_scene_ids or [], ensure_ascii=False)

        existing = self._conn.execute(
            "SELECT id, confidence, evidence_ids, source_scene_ids "
            "FROM profile_entries WHERE user_id = ? AND trait_type = ? AND trait_key = ?",
            (user_id, trait_type, trait_key),
        ).fetchone()

        if existing:
            # 合并：confidence 取最高值 + 0.05 奖励
            new_conf = min(1.0, max(existing["confidence"], confidence) + 0.05)
            merged_evidence = list(set(
                json.loads(existing["evidence_ids"]) + (evidence_ids or [])
            ))
            merged_scenes = list(set(
                json.loads(existing["source_scene_ids"]) + (source_scene_ids or [])
            ))
            entry_id = existing["id"]
            self._conn.execute(
                """UPDATE profile_entries SET trait_value = ?, confidence = ?,
                   evidence_ids = ?, source_scene_ids = ?, updated_at = ?
                   WHERE id = ?""",
                (trait_value, new_conf,
                 json.dumps(merged_evidence, ensure_ascii=False),
                 json.dumps(merged_scenes, ensure_ascii=False),
                 now, entry_id),
            )
            self._conn.commit()
            _log.debug(
                "Profile entry updated: %s/%s/%s → confidence %.2f",
                user_id, trait_type, trait_key, new_conf,
            )
        else:
            entry_id = uuid.uuid4().hex
            md_path = str(self._md_dir / f"profile_{user_id or 'default'}.md")
            self._conn.execute(
                """INSERT INTO profile_entries (id, user_id, trait_type, trait_key,
                   trait_value, confidence, evidence_ids, source_scene_ids,
                   created_at, updated_at, md_path)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (entry_id, user_id, trait_type, trait_key, trait_value,
                 confidence, evidence_json, scene_json, now, now, md_path),
            )
            self._conn.commit()
            _log.debug(
                "Profile entry created: %s/%s/%s", user_id, trait_type, trait_key,
            )

        self._write_markdown(user_id)
        return entry_id

    def get_entries(
        self,
        user_id: str = "",
        trait_type: str = "",
        min_confidence: float = 0.0,
    ) -> List[Dict]:
        """获取画像条目列表，按置信度降序"""
        query = "SELECT * FROM profile_entries WHERE user_id = ? AND confidence >= ?"
        params: List = [user_id, min_confidence]
        if trait_type:
            query += " AND trait_type = ?"
            params.append(trait_type)
        query += " ORDER BY confidence DESC, updated_at DESC"

        rows = self._conn.execute(query, params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_entry(self, entry_id: str) -> Optional[Dict]:
        """按 ID 获取条目"""
        row = self._conn.execute(
            "SELECT * FROM profile_entries WHERE id = ?", (entry_id,)
        ).fetchone()
        return self._row_to_dict(row) if row else None

    def delete_entry(self, entry_id: str) -> bool:
        """删除条目"""
        row = self._conn.execute(
            "SELECT id FROM profile_entries WHERE id = ?", (entry_id,)
        ).fetchone()
        if not row:
            return False
        self._conn.execute(
            "DELETE FROM profile_entries WHERE id = ?", (entry_id,)
        )
        self._conn.commit()
        return True

    def count(self, user_id: str = "") -> int:
        """返回画像条目数"""
        if user_id:
            return self._conn.execute(
                "SELECT COUNT(*) FROM profile_entries WHERE user_id = ?", (user_id,)
            ).fetchone()[0]
        return self._conn.execute(
            "SELECT COUNT(*) FROM profile_entries"
        ).fetchone()[0]

    def generate_markdown(self, user_id: str = "") -> str:
        """生成用户画像的完整 Markdown 文档"""
        entries = self.get_entries(user_id=user_id)
        if not entries:
            return f"# User Profile: {user_id or '(default)'}\n\n(无画像条目)\n"

        lines = [
            f"# User Profile: {user_id or '(default)'}",
            f"_Last updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}_",
            "",
        ]
        for trait_type in ["preference", "skill", "habit", "knowledge_gap", "goal"]:
            typed = [e for e in entries if e["trait_type"] == trait_type]
            if not typed:
                continue
            type_names = {
                "preference": "偏好",
                "skill": "技能",
                "habit": "习惯",
                "knowledge_gap": "知识缺口",
                "goal": "目标",
            }
            lines.append(f"## {type_names.get(trait_type, trait_type)}")
            lines.append("")
            for e in typed:
                lines.append(
                    f"- **{e['trait_key']}**: {e['trait_value']} "
                    f"(置信度: {e['confidence']:.2f}, "
                    f"证据: {len(e.get('evidence_ids', []))} 条记忆, "
                    f"来源: {len(e.get('source_scene_ids', []))} 个场景)"
                )
            lines.append("")
        return "\n".join(lines)

    def close(self):
        """关闭数据库连接"""
        self._conn.close()

    # ── 基类兼容接口 ──

    def store(self, content: str, context: Optional[dict] = None,
              importance: float = 0.5) -> str:
        ctx = context or {}
        return self.upsert_entry(
            trait_type=ctx.get("trait_type", "preference"),
            trait_key=ctx.get("trait_key", content[:40]),
            trait_value=content,
            confidence=importance,
            evidence_ids=ctx.get("evidence_ids"),
            source_scene_ids=ctx.get("source_scene_ids"),
            user_id=ctx.get("user_id", ""),
        )

    def query(self, query_text: str, top_k: int = 10) -> List[Dict]:
        rows = self._conn.execute(
            "SELECT * FROM profile_entries WHERE trait_key LIKE ? OR trait_value LIKE ? "
            "ORDER BY confidence DESC LIMIT ?",
            (f"%{query_text}%", f"%{query_text}%", top_k),
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def delete(self, memory_id: str) -> bool:
        return self.delete_entry(memory_id)

    # ── 内部辅助 ──

    def _row_to_dict(self, row: sqlite3.Row) -> Dict:
        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "trait_type": row["trait_type"],
            "trait_key": row["trait_key"],
            "trait_value": row["trait_value"],
            "confidence": row["confidence"],
            "evidence_ids": json.loads(row["evidence_ids"]),
            "source_scene_ids": json.loads(row["source_scene_ids"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "md_path": row["md_path"],
        }

    def _write_markdown(self, user_id: str = ""):
        md = self.generate_markdown(user_id)
        md_path = self._md_dir / f"profile_{user_id or 'default'}.md"
        try:
            md_path.write_text(md, encoding="utf-8")
        except OSError as exc:
            _log.warning("Profile Markdown 写入失败: %s", exc)
