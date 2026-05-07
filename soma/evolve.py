import json
import os
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
        self._candidate_triggers: Dict[str, Dict[str, Any]] = {}
        self._last_problem: str = ""

        if persist_dir is None:
            persist_dir = Path(os.environ.get("SOMA_DATA_DIR", "soma_data"))
        persist_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = persist_dir / "evolver.db"
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._create_tables()
        self._load_state()

    def _create_tables(self):
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS weights (
                law_id TEXT PRIMARY KEY,
                weight REAL NOT NULL
            )
            """
        )
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
        # v0.6.0: 候选触发词追踪
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS candidate_triggers (
                law_id TEXT NOT NULL,
                word TEXT NOT NULL,
                session_count INTEGER DEFAULT 1,
                first_seen REAL NOT NULL,
                last_seen REAL NOT NULL,
                PRIMARY KEY (law_id, word)
            )
            """
        )
        # v0.6.0: 思维模板追踪
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS focus_patterns (
                domain_key TEXT NOT NULL,
                law_ids TEXT NOT NULL,
                count INTEGER DEFAULT 1,
                first_seen REAL NOT NULL,
                last_seen REAL NOT NULL,
                PRIMARY KEY (domain_key, law_ids)
            )
            """
        )
        self._conn.commit()

    def _load_state(self):
        """启动时从 SQLite 恢复内存状态"""
        # 恢复权重（覆盖 YAML 默认值）
        rows = self._conn.execute("SELECT law_id, weight FROM weights").fetchall()
        if rows:
            weight_map = {r["law_id"]: r["weight"] for r in rows}
            for law in self.engine.laws:
                if law.id in weight_map:
                    law.weight = weight_map[law.id]
            self.engine.laws.sort(key=lambda law: law.weight, reverse=True)

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

        # v0.6.0: 加载候选触发词
        rows = self._conn.execute(
            "SELECT law_id, word, session_count, first_seen, last_seen FROM candidate_triggers"
        ).fetchall()
        self._candidate_triggers: Dict[str, Dict[str, Any]] = {}
        for r in rows:
            key = f"{r['law_id']}::{r['word']}"
            self._candidate_triggers[key] = {
                "law_id": r["law_id"],
                "word": r["word"],
                "session_count": r["session_count"],
                "first_seen": r["first_seen"],
                "last_seen": r["last_seen"],
            }

    def _save_weights(self):
        """将当前权重写入 SQLite"""
        for law in self.engine.laws:
            self._conn.execute(
                "INSERT INTO weights (law_id, weight) VALUES (?, ?) "
                "ON CONFLICT(law_id) DO UPDATE SET weight = excluded.weight",
                (law.id, law.weight),
            )
        self._conn.commit()

    # ── 上下文捕获 ──────────────────────────────────────────

    def set_current_context(self, foci, activated, problem: str = ""):
        self._current_foci = list(foci)
        self._current_activated = list(activated)
        self._last_problem = problem

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

        # v0.6.0: 追踪触发词共现 + 思维模板模式（仅成功时）
        if self._last_problem and is_success:
            self.track_triggers(self._last_problem, self._current_foci, outcome)
            self.track_focus_pattern(self._last_problem, self._current_foci)

    # ── v0.6.0 触发词自动扩展 ─────────────────────────────

    def track_triggers(self, problem: str, foci, outcome: str) -> None:
        """追踪问题关键词与成功规律的共现关系。

        成功会话中，将问题的关键词记录为该规律的候选触发词。
        当某候选词在 >=5 次不同会话中出现时，自动提升为正式触发词。
        """
        if outcome.lower() not in ("success", "成功"):
            return

        from soma.engine import _extract_keywords
        problem_words = _extract_keywords(problem, max_keywords=15)
        if not problem_words:
            return

        ts = time_mod.time()
        for focus in foci:
            law_id = focus.law_id
            # 跳过组合规律和反视角规律
            if law_id.startswith("combo_") or law_id.endswith("_anti"):
                continue
            for word in problem_words:
                key = f"{law_id}::{word}"
                if key in self._candidate_triggers:
                    entry = self._candidate_triggers[key]
                    entry["session_count"] += 1
                    entry["last_seen"] = ts
                    self._conn.execute(
                        "UPDATE candidate_triggers SET session_count=?, last_seen=? "
                        "WHERE law_id=? AND word=?",
                        (entry["session_count"], ts, law_id, word),
                    )
                else:
                    self._candidate_triggers[key] = {
                        "law_id": law_id,
                        "word": word,
                        "session_count": 1,
                        "first_seen": ts,
                        "last_seen": ts,
                    }
                    self._conn.execute(
                        "INSERT INTO candidate_triggers (law_id, word, session_count, first_seen, last_seen) "
                        "VALUES (?, ?, 1, ?, ?)",
                        (law_id, word, ts, ts),
                    )
        self._conn.commit()

    def track_focus_pattern(self, problem: str, foci) -> None:
        """追踪问题领域与其触发的规律组合之间的关联模式。

        用问题前几个关键词作为 domain_key，记录该领域下成功的 foci 组合。
        当同一组合出现 >=5 次时，固化为可复用的思维模板。
        """
        from soma.engine import _extract_keywords
        domain_words = _extract_keywords(problem, max_keywords=3)
        if not domain_words:
            return
        domain_key = "_".join(domain_words)

        # 提取规律ID列表（排序以保证一致性，跳过组合/反视角）
        law_ids = sorted(
            f.law_id for f in foci
            if not f.law_id.startswith("combo_") and not f.law_id.endswith("_anti")
        )
        if not law_ids:
            return
        law_ids_str = ",".join(law_ids)

        ts = time_mod.time()
        existing = self._conn.execute(
            "SELECT count FROM focus_patterns WHERE domain_key=? AND law_ids=?",
            (domain_key, law_ids_str),
        ).fetchone()

        if existing:
            new_count = existing["count"] + 1
            self._conn.execute(
                "UPDATE focus_patterns SET count=?, last_seen=? WHERE domain_key=? AND law_ids=?",
                (new_count, ts, domain_key, law_ids_str),
            )
        else:
            self._conn.execute(
                "INSERT INTO focus_patterns (domain_key, law_ids, count, first_seen, last_seen) "
                "VALUES (?, ?, 1, ?, ?)",
                (domain_key, law_ids_str, ts, ts),
            )
        self._conn.commit()

    def _mine_thought_templates(self, threshold: int = 3) -> List[Dict[str, Any]]:
        """挖掘可复用的思维模板。

        从 focus_patterns 中找出出现 >= threshold 次的 (domain, law_ids) 组合，
        固化为思维模板。返回新固化的模板列表。
        """
        templates = []
        rows = self._conn.execute(
            "SELECT domain_key, law_ids, count FROM focus_patterns WHERE count >= ?",
            (threshold,),
        ).fetchall()

        for row in rows:
            # 将 law_ids 转为可读的规律名称列表
            law_id_list = row["law_ids"].split(",")
            law_names = []
            for lid in law_id_list:
                for law in self.engine.laws:
                    if law.id == lid:
                        law_names.append(law.name)
                        break

            templates.append({
                "type": "thought_template",
                "domain_key": row["domain_key"],
                "law_ids": law_id_list,
                "law_names": law_names,
                "occurrences": row["count"],
            })

        if templates:
            self._conn.commit()
        return templates

    def get_thought_templates(self) -> List[Dict[str, Any]]:
        """获取所有已固化的思维模板（含未达阈值的高频模式）"""
        rows = self._conn.execute(
            "SELECT domain_key, law_ids, count FROM focus_patterns ORDER BY count DESC LIMIT 20"
        ).fetchall()
        result = []
        for row in rows:
            law_id_list = row["law_ids"].split(",")
            law_names = []
            for lid in law_id_list:
                for law in self.engine.laws:
                    if law.id == lid:
                        law_names.append(law.name)
                        break
            result.append({
                "domain_key": row["domain_key"],
                "law_ids": law_id_list,
                "law_names": law_names,
                "count": row["count"],
            })
        return result

    def _promote_triggers(self, threshold: int = 3) -> List[Dict[str, Any]]:
        """将候选触发词提升为正式触发词。

        条件：session_count >= threshold 且该词不在当前触发词列表中。
        返回被提升的触发词列表。
        """
        promoted = []
        # 构建当前触发词集合（按 law_id 分组）
        current_triggers: Dict[str, set] = {}
        for law in self.engine.laws:
            current_triggers[law.id] = {t.lower() for t in law.triggers}

        for key, entry in list(self._candidate_triggers.items()):
            if entry["session_count"] < threshold:
                continue
            law_id = entry["law_id"]
            word = entry["word"]
            # 检查是否已是正式触发词
            if law_id in current_triggers and word.lower() in current_triggers[law_id]:
                continue
            # 找到对应规律并添加触发词
            law_found = False
            for law in self.engine.laws:
                if law.id == law_id:
                    law_found = True
                    triggers = getattr(law, 'triggers', [])
                    if word not in triggers:
                        triggers.append(word)
                        promoted.append({
                            "type": "trigger_promoted",
                            "law_id": law_id,
                            "word": word,
                            "session_count": entry["session_count"],
                        })
                    break
            # 仅当找到对应规律时才清除候选词
            if law_found:
                self._conn.execute(
                    "DELETE FROM candidate_triggers WHERE law_id=? AND word=?",
                    (law_id, word),
                )

        if promoted:
            self._conn.commit()
            # 重新加载候选词
            self._load_state()
        return promoted

    # ── 手动调权 ────────────────────────────────────────────

    def adjust_weight(self, law_id: str, new_weight: float) -> bool:
        clamped = max(0.0, min(1.0, new_weight))
        for law in self.engine.laws:
            if law.id == law_id:
                law.weight = clamped
                self.engine.laws.sort(key=lambda law: law.weight, reverse=True)
                self._save_weights()
                return True
        return False

    # ── 自动进化 ────────────────────────────────────────────

    def evolve(self) -> List[Dict[str, Any]]:
        changes: List[Dict[str, Any]] = []

        # ── 阶段0: 偏差检测与纠正 ─────────────────────────────
        total_uses = sum(
            (s["successes"] + s["failures"]) for s in self._law_stats.values()
        )
        if total_uses >= 20:
            for law_id, stats in self._law_stats.items():
                usage = stats["successes"] + stats["failures"]
                usage_rate = usage / total_uses if total_uses > 0 else 0

                for law in self.engine.laws:
                    if law.id != law_id:
                        continue
                    old = law.weight

                    if usage_rate > 0.40 and old > 0.20:
                        # 过度使用 → 降权
                        law.weight = round(max(0.1, old - 0.05), 4)
                        changes.append({
                            "law_id": law_id,
                            "old_weight": round(old, 4),
                            "new_weight": round(law.weight, 4),
                            "reason": "偏差纠正：使用频率过高",
                            "usage_rate": round(usage_rate, 3),
                        })
                    elif usage_rate < 0.03:
                        total = stats["successes"] + stats["failures"]
                        if total < 3:
                            break
                        rate = stats["successes"] / total if total > 0 else 0
                        if rate > 0.6 and old < 0.90:
                            # 很少使用但效果好的规律 → 提权
                            law.weight = round(min(0.95, old + 0.03), 4)
                            changes.append({
                                "law_id": law_id,
                                "old_weight": round(old, 4),
                                "new_weight": round(law.weight, 4),
                                "reason": "偏差纠正：优质规律使用不足",
                                "usage_rate": round(usage_rate, 3),
                            })
                    break

        # ── 阶段1: 成功率驱动的自动调权 ──────────────────────
        for law_id, stats in list(self._law_stats.items()):
            total = stats["successes"] + stats["failures"]
            if total < 3:
                continue

            rate = stats["successes"] / total

            for law in self.engine.laws:
                if law.id == law_id:
                    old = law.weight
                    step = self._calc_step(total)
                    if rate > 0.7:
                        law.weight = min(1.0, old + step)
                    elif rate < 0.3:
                        law.weight = max(0.0, old - step)

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
            self._save_weights()

        solidified = self._solidify_skills()

        # v0.6.0: 触发词自动提升 + 思维模板挖掘
        promoted_triggers = self._promote_triggers()
        new_templates = self._mine_thought_templates()

        return changes + solidified + promoted_triggers + new_templates

    def _calc_step(self, total_samples: int) -> float:
        """基于样本量动态计算权重调整步长"""
        if total_samples >= 15:
            return 0.03
        elif total_samples >= 5:
            return 0.02
        return 0.01

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
        ok = discovery.approve(candidate, self.engine)
        if ok:
            self._save_weights()
        return ok

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
        self._conn.execute("DELETE FROM candidate_triggers")
        self._conn.execute("DELETE FROM focus_patterns")
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
