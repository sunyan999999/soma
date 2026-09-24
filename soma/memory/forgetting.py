"""主动遗忘引擎 — 三层遗忘策略，Ebbinghaus 指数衰减

设计参考：
- FSFM (arXiv:2604.20300): 四类遗忘机制分类
- FadeMem (arXiv:2601.18642): 差异化衰减率
- SleepGate (arXiv:2603.14517): O(log n) 干扰范围
- Ebbinghaus 公式: strength = importance × e^(-λ × days) × (1 + recall_count × 0.2)

SOMA 方案：三层遗忘（时间衰减/访问频率/冗余清理），归档而非真删除。
"""
import logging
import sqlite3
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

_log = logging.getLogger("soma.memory.forgetting")

# 类别差异化衰减率（λ值越低保留越久）
DECAY_RATES = {
    "strategy": 0.07,    # 成功的策略模式 — 保留最久
    "fact": 0.10,        # 用户事实/偏好
    "insight": 0.12,     # 洞察/经验
    "decision": 0.15,    # 设计决策
    "external": 0.20,    # 外部知识 — 较快遗忘
    "default": 0.14,     # 默认
}

# 类别对应的初始 importance 加成
DECAY_IMPORTANCE_BONUS = {
    "strategy": 0.10,
    "fact": 0.05,
    "insight": 0.03,
    "default": 0.0,
}


class ForgettingEngine:
    """主动遗忘引擎 — 定期扫描并归档低价值记忆"""

    def __init__(self, conn):
        self._conn = conn
        self._ensure_tables()

    def _ensure_tables(self):
        """创建归档表（结构与主表一致，额外增加归档时间和原因）"""
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS episodic_archived (
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
                shared_group_id TEXT NOT NULL DEFAULT '',
                nature TEXT NOT NULL DEFAULT 'event',
                archived_at REAL NOT NULL,
                archive_reason TEXT NOT NULL DEFAULT 'decay'
            )
        """)
        # v2.0.19: 早期归档表没有这三列 —— 缺列会让「恢复」丢掉业务性质
        # （state 记忆恢复后变成 event，时效窗口就此失效）。幂等补列。
        for col, col_def in [
            ("agent_id", "TEXT NOT NULL DEFAULT ''"),
            ("shared_group_id", "TEXT NOT NULL DEFAULT ''"),
            ("nature", "TEXT NOT NULL DEFAULT 'event'"),
        ]:
            try:
                self._conn.execute(
                    "ALTER TABLE episodic_archived ADD COLUMN %s %s" % (col, col_def))
            except sqlite3.OperationalError:
                pass  # 列已存在
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_archived_at ON episodic_archived(archived_at DESC)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_archived_user ON episodic_archived(user_id)"
        )
        self._conn.commit()

    def compute_memory_strength(
        self, importance: float, timestamp: float, access_count: int,
        memory_type: str = "default",
    ) -> float:
        """Ebbinghaus 遗忘曲线: strength = importance × e^(-λ × days) × (1 + recall_count × 0.2)

        重要性为负值（已标记合并）的记忆返回负数强度。
        """
        if importance < 0:
            return importance  # 已被标记为废弃

        days = max(0, (datetime.now(timezone.utc).timestamp() - timestamp) / 86400.0)
        decay_rate = DECAY_RATES.get(memory_type, DECAY_RATES["default"])
        bonus = DECAY_IMPORTANCE_BONUS.get(memory_type, 0)
        effective_importance = min(importance + bonus, 1.0)

        raw_strength = effective_importance * (2.71828 ** (-decay_rate * days))
        recall_boost = 1.0 + access_count * 0.2
        return raw_strength * recall_boost

    def run_forgetting_pass(
        self, user_id: str = "",
        decay_threshold: float = 0.05,
        cold_threshold_days: int = 30,
        max_archive: int = 50,
    ) -> Dict:
        """执行一次遗忘扫描（由 evolve() 触发）。

        三层策略：
        1. 时间衰减遗忘 — strength < 0.05 归档
        2. 访问频率遗忘 — access_count=0 且 30天未访问 且 importance<0.5 → 归档
        3. 冗余清理 — 14天前标记为 importance=-0.1 的合并废记忆 → 永久删除

        Returns:
            {"decayed": N, "cold": N, "cleaned": N}
        """
        now = datetime.now(timezone.utc).timestamp()
        results = {"decayed": 0, "cold": 0, "cleaned": 0}

        # Layer 3: 冗余清理 — 合并后14天宽限期已过的废记忆
        cleanup_cutoff = now - 14 * 86400
        rows = self._conn.execute(
            """SELECT id FROM episodic_memories
               WHERE importance < 0 AND timestamp < ? AND user_id = ?""",
            (cleanup_cutoff, user_id),
        ).fetchall()
        for row in rows:
            self._conn.execute("DELETE FROM episodic_memories WHERE id = ?", (row["id"],))
            results["cleaned"] += 1
        if results["cleaned"]:
            self._conn.commit()
            _log.info("遗忘清理: 删除 %d 条合并废记忆", results["cleaned"])

        # Layer 1 & 2: 计算所有记忆强度，找候选
        rows = self._conn.execute(
            """SELECT * FROM episodic_memories
               WHERE importance > 0 AND user_id = ?
               ORDER BY importance ASC LIMIT 500""",
            (user_id,),
        ).fetchall()

        archive_candidates = []
        for row in rows:
            strength = self.compute_memory_strength(
                row["importance"], row["timestamp"],
                row["access_count"], row["memory_type"],
            )

            # Layer 1: 时间衰减
            if strength < decay_threshold and row["importance"] < 0.3:
                archive_candidates.append((row["id"], row, "decay"))
                results["decayed"] += 1
                continue

            # Layer 2: 访问频率
            days_since_access = max(0, (now - row["timestamp"]) / 86400.0)
            if (row["access_count"] == 0
                    and days_since_access > cold_threshold_days
                    and row["importance"] < 0.5):
                archive_candidates.append((row["id"], row, "cold"))
                results["cold"] += 1
                continue

        # 执行归档（上限防止单次清理过多）
        for mem_id, row, reason in archive_candidates[:max_archive]:
            self._conn.execute(
                """INSERT OR IGNORE INTO episodic_archived
                   (id, content, content_hash, timestamp, importance,
                    access_count, context_json, memory_type, user_id,
                    session_id, agent_id, shared_group_id, nature,
                    archived_at, archive_reason)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (row["id"], row["content"],
                 row["content_hash"] if "content_hash" in row.keys() else "",
                 row["timestamp"], row["importance"], row["access_count"],
                 row["context_json"] if "context_json" in row.keys() else "{}",
                 row["memory_type"] if "memory_type" in row.keys() else "episodic",
                 row["user_id"] if "user_id" in row.keys() else user_id,
                 row["session_id"] if "session_id" in row.keys() else "",
                 row["agent_id"] if "agent_id" in row.keys() else "",
                 row["shared_group_id"] if "shared_group_id" in row.keys() else "",
                 row["nature"] if "nature" in row.keys() else "event",
                 now, reason),
            )
            # 从主表移除
            self._conn.execute("DELETE FROM episodic_memories WHERE id = ?", (mem_id,))

        if archive_candidates:
            self._conn.commit()
            _log.info(
                "遗忘归档: %d 条 (衰减=%d, 冷记忆=%d)",
                len(archive_candidates), results["decayed"], results["cold"],
            )

        return results

    def archive_row(self, row, reason: str = "user_delete") -> bool:
        """归档并删除一条已取出的记忆（v2.0.19，供用户侧删除复用）。

        与 run_forgetting_pass 的自动归档走同一张表，用 archive_reason 区分
        来源（user_delete / decay / cold）。归档失败就不删 —— 宁可删不掉，
        也不能让一条记忆既不在主表、又没进归档。
        """
        keys = row.keys()
        try:
            self._conn.execute(
                """INSERT OR REPLACE INTO episodic_archived
                   (id, content, content_hash, timestamp, importance,
                    access_count, context_json, memory_type, user_id,
                    session_id, agent_id, shared_group_id, nature,
                    archived_at, archive_reason)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (row["id"], row["content"],
                 row["content_hash"] if "content_hash" in keys else "",
                 row["timestamp"], row["importance"], row["access_count"],
                 row["context_json"] if "context_json" in keys else "{}",
                 row["memory_type"] if "memory_type" in keys else "episodic",
                 row["user_id"] if "user_id" in keys else "",
                 row["session_id"] if "session_id" in keys else "",
                 row["agent_id"] if "agent_id" in keys else "",
                 row["shared_group_id"] if "shared_group_id" in keys else "",
                 row["nature"] if "nature" in keys else "event",
                 time.time(), reason),
            )
            self._conn.execute(
                "DELETE FROM episodic_memories WHERE id = ?", (row["id"],))
            self._conn.commit()
        except sqlite3.Error:
            _log.warning("归档失败, memory_id=%s", str(row["id"])[:8], exc_info=True)
            return False

        _log.info("记忆归档: %s (%s)", str(row["id"])[:8], reason)
        return True

    def recall_archived(
        self, query: str = "", user_id: str = "", top_k: int = 20
    ) -> List[Dict]:
        """从归档中恢复/浏览记忆"""
        if query:
            rows = self._conn.execute(
                """SELECT * FROM episodic_archived
                   WHERE user_id = ? AND (content LIKE ? OR context_json LIKE ?)
                   ORDER BY importance DESC LIMIT ?""",
                (user_id, f"%{query}%", f"%{query}%", top_k),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """SELECT * FROM episodic_archived
                   WHERE user_id = ?
                   ORDER BY archived_at DESC LIMIT ?""",
                (user_id, top_k),
            ).fetchall()
        return [dict(r) for r in rows]

    def restore(self, memory_id: str) -> bool:
        """从归档恢复一条记忆"""
        row = self._conn.execute(
            "SELECT * FROM episodic_archived WHERE id = ?", (memory_id,)
        ).fetchone()
        if not row:
            return False

        self._conn.execute(
            """INSERT OR IGNORE INTO episodic_memories
               (id, content, content_hash, timestamp, importance,
                access_count, context_json, memory_type, user_id, session_id,
                agent_id, shared_group_id, nature)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (row["id"], row["content"], row["content_hash"], row["timestamp"],
             row["importance"], row["access_count"],
             row["context_json"] if "context_json" in row.keys() else "{}",
             row["memory_type"], row["user_id"], row["session_id"],
             row["agent_id"] if "agent_id" in row.keys() else "",
             row["shared_group_id"] if "shared_group_id" in row.keys() else "",
             row["nature"] if "nature" in row.keys() else "event"),
        )
        self._conn.execute("DELETE FROM episodic_archived WHERE id = ?", (memory_id,))
        self._conn.commit()
        _log.info("记忆恢复: %s", memory_id[:8])
        return True

    def stats(self, user_id: str = "") -> Dict:
        """遗忘统计"""
        if user_id:
            archived = self._conn.execute(
                "SELECT COUNT(*) FROM episodic_archived WHERE user_id = ?", (user_id,)
            ).fetchone()
        else:
            archived = self._conn.execute(
                "SELECT COUNT(*) FROM episodic_archived"
            ).fetchone()
        return {"archived_count": archived[0] if archived else 0}
