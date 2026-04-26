import json
import sqlite3
import time as time_mod
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional


class MetaEvolver:
    """元认知进化器 — 反思追踪、自动调权、技能固化（SQLite 持久化）"""

    def __init__(self, engine, memory_core=None, persist_dir: Optional[Path] = None):
        self.engine = engine
        self.memory_core = memory_core
        self._current_foci: List[Any] = []
        self._current_activated: List[Any] = []

        if persist_dir is None:
            persist_dir = Path("dashboard_data")
        persist_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = persist_dir / "evolver.db"
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._create_tables()
        self._load_state()

    def _create_tables(self):
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reflection_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                outcome TEXT NOT NULL,
                timestamp REAL NOT NULL
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_reflection_time ON reflection_log(timestamp DESC)"
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS law_stats (
                law_id TEXT PRIMARY KEY,
                successes INTEGER DEFAULT 0,
                failures INTEGER DEFAULT 0
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS skill_tracker (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                law_id TEXT NOT NULL,
                domain TEXT NOT NULL,
                source TEXT NOT NULL,
                timestamp REAL NOT NULL
            )
            """
        )
        self._conn.commit()

    def _load_state(self):
        """启动时从 SQLite 恢复内存状态"""
        # 加载 law_stats
        rows = self._conn.execute("SELECT law_id, successes, failures FROM law_stats").fetchall()
        self._law_stats: Dict[str, Dict[str, int]] = {}
        for r in rows:
            self._law_stats[r["law_id"]] = {
                "successes": r["successes"],
                "failures": r["failures"],
            }

        # 加载 skill_tracker
        rows = self._conn.execute(
            "SELECT law_id, domain, source, timestamp FROM skill_tracker"
        ).fetchall()
        self._skill_tracker: List[Dict[str, Any]] = []
        for r in rows:
            self._skill_tracker.append({
                "law_id": r["law_id"],
                "domain": r["domain"],
                "source": r["source"],
                "timestamp": r["timestamp"],
            })

    # ── 上下文捕获 ──────────────────────────────────────────

    def set_current_context(self, foci, activated):
        self._current_foci = list(foci)
        self._current_activated = list(activated)

    # ── 反思与追踪 ──────────────────────────────────────────

    def reflect(self, task_id: str, outcome: str) -> None:
        """记录反思并持久化"""
        ts = time_mod.time()
        self._conn.execute(
            "INSERT INTO reflection_log (task_id, outcome, timestamp) VALUES (?, ?, ?)",
            (task_id, outcome, ts),
        )
        self._conn.commit()

        is_success = outcome.lower() in ("success", "成功")
        is_failure = outcome.lower() in ("failure", "失败")

        if not (is_success or is_failure):
            return

        for focus in self._current_foci:
            lid = focus.law_id
            existing = self._conn.execute(
                "SELECT law_id FROM law_stats WHERE law_id = ?", (lid,)
            ).fetchone()
            if existing is None:
                self._conn.execute(
                    "INSERT INTO law_stats (law_id, successes, failures) VALUES (?, 0, 0)",
                    (lid,),
                )
            col = "successes" if is_success else "failures"
            self._conn.execute(
                f"UPDATE law_stats SET {col} = {col} + 1 WHERE law_id = ?", (lid,)
            )
            self._conn.commit()

        # 重新加载内存中的 stats
        self._load_state()

        if is_success and self._current_activated:
            for focus in self._current_foci:
                for am in self._current_activated:
                    domain = am.memory.context.get("domain", "unknown")
                    self._conn.execute(
                        "INSERT INTO skill_tracker (law_id, domain, source, timestamp) VALUES (?, ?, ?, ?)",
                        (focus.law_id, domain, am.source, ts),
                    )
            self._conn.commit()
            self._load_state()

    # ── 手动调权 ────────────────────────────────────────────

    def adjust_weight(self, law_id: str, new_weight: float) -> bool:
        clamped = max(0.0, min(1.0, new_weight))
        for law in self.engine.laws:
            if law.id == law_id:
                law.weight = clamped
                self.engine.laws.sort(key=lambda law: law.weight, reverse=True)
                return True
        return False

    # ── 自动进化 ────────────────────────────────────────────

    def evolve(self) -> List[Dict[str, Any]]:
        changes = []

        for law_id, stats in list(self._law_stats.items()):
            total = stats["successes"] + stats["failures"]
            if total < 3:
                continue

            rate = stats["successes"] / total

            for law in self.engine.laws:
                if law.id == law_id:
                    old = law.weight
                    if rate > 0.7:
                        law.weight = min(1.0, old + 0.02)
                    elif rate < 0.3:
                        law.weight = max(0.0, old - 0.02)

                    if law.weight != old:
                        changes.append({
                            "law_id": law_id,
                            "old_weight": round(old, 4),
                            "new_weight": round(law.weight, 4),
                            "success_rate": round(rate, 3),
                            "total_samples": total,
                        })

                    # 重置统计
                    self._conn.execute(
                        "UPDATE law_stats SET successes = 0, failures = 0 WHERE law_id = ?",
                        (law_id,),
                    )
                    self._conn.commit()
                    break

        # 重新加载内存中的 stats（DB 已更新）
        if changes:
            self._load_state()
            self.engine.laws.sort(key=lambda law: law.weight, reverse=True)

        the_changes: List[Dict[str, Any]] = changes
        solidified = self._solidify_skills()
        return the_changes + solidified

    def discover_laws(self, embedder=None, llm_model: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """尝试从高关联记忆中发现新规律。

        需要提供 embedder 和 memory_core（构造时传入）。
        返回候选规律 dict（供人工审核），或 None 表示无条件。
        建议在 evolve() 后每隔 N 次会话调用一次（如每 50 次）。
        """
        if not self.memory_core or not embedder:
            return None

        from soma.law_discovery import LawDiscovery

        discovery = LawDiscovery(self.memory_core, embedder, llm_model=llm_model)
        return discovery.discover(current_law_count=len(self.engine.laws))

    def approve_law(self, candidate: Dict[str, Any], embedder=None) -> bool:
        """审批通过一条候选规律，加入框架。"""
        if not self.memory_core or not embedder:
            return False

        from soma.law_discovery import LawDiscovery

        discovery = LawDiscovery(self.memory_core, embedder)
        return discovery.approve(candidate, self.engine)

    def _solidify_skills(self) -> List[Dict[str, Any]]:
        if not self.memory_core:
            return []

        counter: Counter = Counter()
        for entry in self._skill_tracker:
            key = (entry["law_id"], entry["domain"])
            counter[key] += 1

        result = []
        for (law_id, domain), count in counter.items():
            if count >= 3:
                law_name = law_id
                for law in self.engine.laws:
                    if law.id == law_id:
                        law_name = law.name
                        break
                skill_name = f"{law_name} × {domain}"
                skill_pattern = (
                    f"在面对 {domain} 领域的问题时，优先从 {law_name} 的角度切入分析，"
                    f"该方法已在 {count} 次实践中被验证有效。"
                )
                self.memory_core.skill.add_skill(
                    skill_name, skill_pattern,
                    context={"law_id": law_id, "domain": domain},
                )
                result.append({
                    "type": "skill_solidified",
                    "skill_name": skill_name,
                    "law_id": law_id,
                    "domain": domain,
                    "occurrences": count,
                })

        # 清除已固化的追踪记录
        self._conn.execute("DELETE FROM skill_tracker")
        self._conn.commit()
        self._skill_tracker.clear()
        return result

    # ── 查询接口 ────────────────────────────────────────────

    def get_log(self) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT task_id, outcome, timestamp FROM reflection_log ORDER BY timestamp DESC LIMIT 200"
        ).fetchall()
        return [
            {"task_id": r["task_id"], "outcome": r["outcome"], "timestamp": r["timestamp"]}
            for r in rows
        ]

    def clear_log(self) -> None:
        self._conn.execute("DELETE FROM reflection_log")
        self._conn.execute("DELETE FROM law_stats")
        self._conn.execute("DELETE FROM skill_tracker")
        self._conn.commit()
        self._load_state()

    def get_weights(self) -> Dict[str, float]:
        return {law.id: law.weight for law in self.engine.laws}

    def get_stats(self) -> Dict[str, Any]:
        result = {}
        for law_id, stats in self._law_stats.items():
            total = stats["successes"] + stats["failures"]
            rate = stats["successes"] / total if total > 0 else 0.0
            result[law_id] = {
                "successes": stats["successes"],
                "failures": stats["failures"],
                "total": total,
                "success_rate": round(rate, 3),
            }
        return result

    def close(self):
        self._conn.close()
