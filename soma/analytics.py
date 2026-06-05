"""SOMA 自我监控与分析存储 — 记录每次对话会话的完整上下文"""
import json
import os
import sqlite3
import time
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional


class AnalyticsStore:
    """会话分析存储 — SQLite 持久化，追踪每次 chat 的完整数据"""

    def __init__(self, persist_dir: Optional[Path] = None):
        if persist_dir is None:
            persist_dir = Path(os.environ.get("SOMA_DATA_DIR", "soma_data"))
        elif isinstance(persist_dir, str):
            persist_dir = Path(persist_dir)
        persist_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = persist_dir / "analytics.db"
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                problem TEXT NOT NULL,
                problem_preview TEXT NOT NULL,
                created_at REAL NOT NULL,
                provider TEXT NOT NULL,
                mock_mode INTEGER DEFAULT 0,
                response_time_ms REAL DEFAULT 0,
                foci_count INTEGER DEFAULT 0,
                foci_json TEXT DEFAULT '[]',
                activated_count INTEGER DEFAULT 0,
                activated_sources_json TEXT DEFAULT '[]',
                activated_scores_json TEXT DEFAULT '[]',
                answer_preview TEXT DEFAULT '',
                answer_length INTEGER DEFAULT 0,
                weights_json TEXT DEFAULT '{}',
                memory_stats_json TEXT DEFAULT '{}',
                raw_response_json TEXT DEFAULT '{}'
            );

            CREATE INDEX IF NOT EXISTS idx_sessions_time ON sessions(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_sessions_provider ON sessions(provider);
            CREATE INDEX IF NOT EXISTS idx_sessions_mock ON sessions(mock_mode);
            """
        )
        self._conn.commit()

    def record_session(self, session_data: Dict[str, Any]) -> str:
        """记录一次对话会话，返回 session_id"""
        sid = session_data.get("id", uuid.uuid4().hex)
        now = time.time()
        problem = session_data.get("problem", "")[:2000]
        problem_preview = problem[:100]

        foci = session_data.get("foci", [])
        foci_summary = [
            {"law_id": f.get("law_id", ""), "weight": f.get("weight", 0)}
            for f in foci
        ]

        activated = session_data.get("activated_memories", [])
        sources = [am.get("source", "") for am in activated]
        scores = [am.get("activation_score", 0) for am in activated]

        weights = session_data.get("weights", {})
        memory_stats = session_data.get("memory_stats", {})

        answer = session_data.get("answer", "")
        answer_preview = answer[:200]
        answer_length = len(answer)

        self._conn.execute(
            """
            INSERT OR REPLACE INTO sessions
            (id, problem, problem_preview, created_at, provider, mock_mode,
             response_time_ms, foci_count, foci_json, activated_count,
             activated_sources_json, activated_scores_json,
             answer_preview, answer_length, weights_json, memory_stats_json, raw_response_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sid, problem, problem_preview, now,
                session_data.get("provider_used", "unknown"),
                1 if session_data.get("mock_mode") else 0,
                session_data.get("response_time_ms", 0),
                len(foci), json.dumps(foci_summary, ensure_ascii=False),
                len(activated),
                json.dumps(sources, ensure_ascii=False),
                json.dumps(scores, ensure_ascii=False),
                answer_preview, answer_length,
                json.dumps(weights, ensure_ascii=False),
                json.dumps(memory_stats, ensure_ascii=False),
                json.dumps(session_data, ensure_ascii=False, default=str),
            ),
        )
        self._conn.commit()
        return sid

    def get_sessions(
        self,
        limit: int = 50,
        offset: int = 0,
        provider: Optional[str] = None,
        mock_only: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """分页查询会话列表"""
        conditions = []
        params: List[Any] = []
        if provider:
            conditions.append("provider = ?")
            params.append(provider)
        if mock_only is not None:
            conditions.append("mock_mode = ?")
            params.append(1 if mock_only else 0)

        where = ""
        if conditions:
            where = "WHERE " + " AND ".join(conditions)

        sql = f"""
            SELECT id, problem_preview, created_at, provider, mock_mode,
                   response_time_ms, foci_count, activated_count,
                   answer_preview, answer_length, weights_json, memory_stats_json,
                   foci_json, activated_sources_json, activated_scores_json
            FROM sessions
            {where}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])
        rows = self._conn.execute(sql, params).fetchall()

        results = []
        for r in rows:
            results.append({
                "id": r["id"],
                "problem_preview": r["problem_preview"],
                "created_at": r["created_at"],
                "provider": r["provider"],
                "mock_mode": bool(r["mock_mode"]),
                "response_time_ms": r["response_time_ms"],
                "foci_count": r["foci_count"],
                "activated_count": r["activated_count"],
                "answer_preview": r["answer_preview"],
                "answer_length": r["answer_length"],
                "weights": json.loads(r["weights_json"]),
                "memory_stats": json.loads(r["memory_stats_json"]),
                "foci": json.loads(r["foci_json"]),
                "activated_sources": json.loads(r["activated_sources_json"]),
                "activated_scores": json.loads(r["activated_scores_json"]),
            })
        return results

    def get_summary(self) -> Dict[str, Any]:
        """返回汇总统计"""
        total = self._conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]

        provider_counts = {}
        rows = self._conn.execute(
            "SELECT provider, COUNT(*) as cnt FROM sessions GROUP BY provider"
        ).fetchall()
        for r in rows:
            provider_counts[r["provider"]] = r["cnt"]

        mock_vs_real = {
            "mock": self._conn.execute(
                "SELECT COUNT(*) FROM sessions WHERE mock_mode = 1"
            ).fetchone()[0],
            "real": self._conn.execute(
                "SELECT COUNT(*) FROM sessions WHERE mock_mode = 0"
            ).fetchone()[0],
        }

        avg_row = self._conn.execute(
            "SELECT AVG(response_time_ms) as avg_time, AVG(foci_count) as avg_foci,"
            " AVG(activated_count) as avg_activated, AVG(answer_length) as avg_answer_len"
            " FROM sessions"
        ).fetchone()

        # 权重随时间变化 — 跳过消融/benchmark 的占位 weights
        recent_weights = {}
        rows = self._conn.execute(
            "SELECT weights_json FROM sessions"
            " WHERE id NOT LIKE 'ablate_%' AND id NOT LIKE 'bench_%'"
            " ORDER BY created_at DESC LIMIT 10"
        ).fetchall()
        for r in rows:
            w = json.loads(r["weights_json"])
            # 确保至少有一个值是数字（真正的权重），而非纯字符串占位
            if w and any(isinstance(v, (int, float)) for v in w.values()):
                recent_weights = w
                break

        return {
            "total_sessions": total,
            "provider_counts": provider_counts,
            "mock_vs_real": mock_vs_real,
            "avg_response_time_ms": round(avg_row["avg_time"] or 0, 1),
            "avg_foci_count": round(avg_row["avg_foci"] or 0, 1),
            "avg_activated_count": round(avg_row["avg_activated"] or 0, 1),
            "avg_answer_length": round(avg_row["avg_answer_len"] or 0, 0),
            "current_weights": recent_weights,
        }

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取单次会话的完整数据"""
        row = self._conn.execute(
            "SELECT raw_response_json FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if row is None:
            return None
        return json.loads(row["raw_response_json"])

    def get_weight_timeline(self, limit: int = 20) -> List[Dict]:
        """返回权重随时间变化的序列（用于图表）"""
        rows = self._conn.execute(
            "SELECT created_at, weights_json, provider FROM sessions"
            " ORDER BY created_at ASC LIMIT ?",
            (limit * 2,),
        ).fetchall()

        timeline = []
        for r in rows:
            timeline.append({
                "timestamp": r["created_at"],
                "weights": json.loads(r["weights_json"]),
                "provider": r["provider"],
            })
        return timeline

    def get_comparison_data(self) -> Dict[str, Any]:
        """返回用于对比分析的数据"""
        # 按 provider 分组统计
        provider_stats = {}
        rows = self._conn.execute(
            "SELECT provider, COUNT(*) as cnt, AVG(foci_count) as avg_foci,"
            " AVG(activated_count) as avg_activated, AVG(answer_length) as avg_len,"
            " AVG(response_time_ms) as avg_time"
            " FROM sessions GROUP BY provider"
        ).fetchall()
        for r in rows:
            provider_stats[r["provider"]] = {
                "count": r["cnt"],
                "avg_foci": round(r["avg_foci"] or 0, 1),
                "avg_activated": round(r["avg_activated"] or 0, 1),
                "avg_answer_length": round(r["avg_len"] or 0, 0),
                "avg_response_time_ms": round(r["avg_time"] or 0, 1),
            }

        # 按 mock/real 分组
        mode_stats = {}
        for mode_val, label in [(0, "real"), (1, "mock")]:
            r = self._conn.execute(
                "SELECT COUNT(*) as cnt, AVG(foci_count) as avg_foci,"
                " AVG(activated_count) as avg_activated, AVG(answer_length) as avg_len"
                " FROM sessions WHERE mock_mode = ?", (mode_val,)
            ).fetchone()
            if r:
                mode_stats[label] = {
                    "count": r["cnt"],
                    "avg_foci": round(r["avg_foci"] or 0, 1),
                    "avg_activated": round(r["avg_activated"] or 0, 1),
                    "avg_answer_length": round(r["avg_len"] or 0, 0),
                }

        return {
            "provider_stats": provider_stats,
            "mode_stats": mode_stats,
            "weight_timeline": self.get_weight_timeline(),
        }

    def delete_old_sessions(self, keep: int = 200) -> int:
        """清理旧会话，保留最近 N 条"""
        count_row = self._conn.execute("SELECT COUNT(*) FROM sessions").fetchone()
        total = count_row[0]
        if total <= keep:
            return 0
        # 找到第 N 条的时间戳
        row = self._conn.execute(
            "SELECT created_at FROM sessions ORDER BY created_at DESC LIMIT 1 OFFSET ?",
            (keep - 1,),
        ).fetchone()
        if row:
            self._conn.execute(
                "DELETE FROM sessions WHERE created_at < ?", (row["created_at"],)
            )
            self._conn.commit()
        return max(0, total - keep)

    def count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) FROM sessions").fetchone()
        return row[0] if row else 0

    # ── 基准测试存储 (v0.3.0b1) ────────────────────────────────

    def _create_benchmark_tables(self):
        """创建基准测试专用表"""
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS benchmark_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version TEXT NOT NULL,
                timestamp REAL NOT NULL,
                score_memory REAL DEFAULT 0,
                score_wisdom REAL DEFAULT 0,
                score_evolution REAL DEFAULT 0,
                score_overall REAL DEFAULT 0,
                memory_json TEXT DEFAULT '{}',
                wisdom_json TEXT DEFAULT '{}',
                evolution_json TEXT DEFAULT '{}',
                full_json TEXT DEFAULT '{}'
            );

            CREATE INDEX IF NOT EXISTS idx_bench_time ON benchmark_runs(timestamp DESC);
            """
        )
        # v0.6.1 迁移：新增多轮基准测试列
        for col, defn in [
            ("runs_count", "INTEGER DEFAULT 1"),
            ("multi_run_stats_json", "TEXT DEFAULT '{}'"),
        ]:
            try:
                self._conn.execute(f"ALTER TABLE benchmark_runs ADD COLUMN {col} {defn}")
            except Exception:
                pass  # 列已存在

        # v0.3.1b1 迁移：新增长缩性维度列
        for col, defn in [
            ("score_scalability", "REAL DEFAULT 0"),
            ("scalability_json", "TEXT DEFAULT '{}'"),
        ]:
            try:
                self._conn.execute(f"ALTER TABLE benchmark_runs ADD COLUMN {col} {defn}")
            except Exception:
                pass  # 列已存在
        self._conn.commit()

    def record_benchmark(self, run) -> int:
        """存储一次基准测试运行，返回 run_id"""
        self._create_benchmark_tables()
        ts = run.timestamp if run.timestamp else time.time()
        scal = run.scores.get("scalability", 0)
        scal_json = json.dumps(
            asdict(run.scalability) if hasattr(run, 'scalability') and hasattr(run.scalability, '__dataclass_fields__') else {},
            ensure_ascii=False, default=str,
        )
        self._conn.execute(
            """
            INSERT INTO benchmark_runs
            (version, timestamp, score_memory, score_wisdom, score_evolution, score_overall,
             score_scalability, memory_json, wisdom_json, evolution_json, scalability_json, full_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run.version, ts,
                run.scores.get("memory", 0),
                run.scores.get("wisdom", 0),
                run.scores.get("evolution", 0),
                run.scores.get("overall", 0),
                scal,
                json.dumps(asdict(run.memory) if hasattr(run.memory, '__dataclass_fields__') else run.memory, ensure_ascii=False, default=str),
                json.dumps(asdict(run.wisdom) if hasattr(run.wisdom, '__dataclass_fields__') else run.wisdom, ensure_ascii=False, default=str),
                json.dumps(asdict(run.evolution) if hasattr(run.evolution, '__dataclass_fields__') else run.evolution, ensure_ascii=False, default=str),
                scal_json,
                json.dumps(asdict(run) if hasattr(run, '__dataclass_fields__') else run, ensure_ascii=False, default=str),
            ),
        )
        self._conn.commit()
        return self._conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def get_latest_benchmark(self) -> Optional[Dict]:
        """获取最近一次基准测试结果"""
        self._create_benchmark_tables()
        row = self._conn.execute(
            "SELECT * FROM benchmark_runs ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        scores = {
            "memory": row["score_memory"],
            "wisdom": row["score_wisdom"],
            "evolution": row["score_evolution"],
            "overall": row["score_overall"],
        }
        # 伸缩性分数（v0.3.1b1 新增列，旧数据可能为 NULL）
        try:
            scores["scalability"] = row["score_scalability"] or 0
        except Exception:
            scores["scalability"] = 0

        result = {
            "id": row["id"],
            "version": row["version"],
            "timestamp": row["timestamp"],
            "scores": scores,
            "memory": json.loads(row["memory_json"]),
            "wisdom": json.loads(row["wisdom_json"]),
            "evolution": json.loads(row["evolution_json"]),
        }
        # 伸缩性维度数据（v0.3.1b1 新增列）
        try:
            result["scalability"] = json.loads(row["scalability_json"] or "{}")
        except Exception:
            result["scalability"] = {}
        return result

    def get_benchmark_history(self, limit: int = 20) -> List[Dict]:
        """获取基准测试历史记录"""
        self._create_benchmark_tables()
        rows = self._conn.execute(
            "SELECT id, version, timestamp, score_memory, score_wisdom,"
            " score_evolution, score_overall, score_scalability"
            " FROM benchmark_runs ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            {
                "id": r["id"],
                "version": r["version"],
                "timestamp": r["timestamp"],
                "scores": {
                    "memory": r["score_memory"],
                    "wisdom": r["score_wisdom"],
                    "evolution": r["score_evolution"],
                    "overall": r["score_overall"],
                    "scalability": r["score_scalability"] or 0,
                },
            }
            for r in rows
        ]

    def get_benchmark_compare(self) -> Dict:
        """返回 SOMA + 竞品对比数据（供前端雷达图）"""
        latest = self.get_latest_benchmark()
        from soma.benchmarks import COMPETITOR_DATA

        result = {
            "soma": latest["scores"] if latest else {},
            "soma_memory": latest["memory"] if latest else {},
            "soma_wisdom": latest["wisdom"] if latest else {},
            "soma_evolution": latest["evolution"] if latest else {},
            "competitors": COMPETITOR_DATA,
            "last_updated": latest["timestamp"] if latest else None,
        }
        return result

    # ── 多轮基准测试存储 (v0.6.1+) ───────────────────────────

    def record_multi_benchmark(self, multi_result) -> int:
        """存储多轮基准测试结果，返回 run_id

        将 MultiRunResult 的统计摘要存入 benchmark_runs 表。
        单轮分数取均值，统计指标和原始值存入 multi_run_stats_json。
        """
        self._create_benchmark_tables()
        ts = multi_result.timestamp if multi_result.timestamp else time.time()

        scores_dict = {}
        for key in ["overall", "memory", "wisdom", "evolution", "scalability"]:
            if key in multi_result.scores:
                scores_dict[key] = multi_result.scores[key].mean

        multi_json = json.dumps(
            {
                "runs": multi_result.runs,
                "total_duration_s": multi_result.total_duration_s,
                "data_scale": multi_result.data_scale,
                "scores": {
                    k: {
                        "mean": s.mean, "std": s.std,
                        "ci95": [s.ci95_low, s.ci95_high],
                        "cv_pct": s.cv_pct, "stability": s.stability,
                        "values": s.values,
                    }
                    for k, s in multi_result.scores.items()
                },
            },
            ensure_ascii=False,
        )

        self._conn.execute(
            """
            INSERT INTO benchmark_runs
            (version, timestamp, score_memory, score_wisdom, score_evolution, score_overall,
             score_scalability, runs_count, multi_run_stats_json,
             memory_json, wisdom_json, evolution_json, scalability_json, full_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '{}', '{}', '{}', '{}', '{}')
            """,
            (
                multi_result.version, ts,
                scores_dict.get("memory", 0),
                scores_dict.get("wisdom", 0),
                scores_dict.get("evolution", 0),
                scores_dict.get("overall", 0),
                scores_dict.get("scalability", 0),
                multi_result.runs,
                multi_json,
            ),
        )
        self._conn.commit()
        return self._conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def get_latest_multi_benchmark(self) -> Optional[Dict]:
        """获取最近一次多轮基准测试的统计结果"""
        self._create_benchmark_tables()
        row = self._conn.execute(
            "SELECT * FROM benchmark_runs WHERE runs_count > 1 OR multi_run_stats_json != '{}' ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "version": row["version"],
            "runs": row["runs_count"],
            "timestamp": row["timestamp"],
            "scores": {
                "memory": row["score_memory"],
                "wisdom": row["score_wisdom"],
                "evolution": row["score_evolution"],
                "scalability": row["score_scalability"],
                "overall": row["score_overall"],
            },
            "multi_run_stats": json.loads(row["multi_run_stats_json"] or "{}"),
        }

    # ── 中道引擎校正日志 (v1.1.3) ──────────────────────────

    def _create_zhongdao_tables(self):
        """创建中道校正日志表"""
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS zhongdao_corrections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                session_id TEXT NOT NULL DEFAULT '',
                agent_id TEXT NOT NULL DEFAULT '',
                type TEXT NOT NULL,
                law_id TEXT NOT NULL,
                law_name TEXT NOT NULL DEFAULT '',
                usage_ratio REAL DEFAULT 0,
                old_weight REAL DEFAULT 0,
                new_weight REAL DEFAULT 0,
                details_json TEXT DEFAULT '{}'
            );

            CREATE INDEX IF NOT EXISTS idx_zhongdao_time
                ON zhongdao_corrections(timestamp DESC);
            CREATE INDEX IF NOT EXISTS idx_zhongdao_type
                ON zhongdao_corrections(type);
            CREATE INDEX IF NOT EXISTS idx_zhongdao_law
                ON zhongdao_corrections(law_id);
            """
        )
        self._conn.commit()

    def record_zhongdao_correction(
        self,
        correction: Dict[str, Any],
        session_id: str = "",
        agent_id: str = "",
    ) -> int:
        """记录一次中道校正事件，返回行ID"""
        self._create_zhongdao_tables()
        self._conn.execute(
            """
            INSERT INTO zhongdao_corrections
            (timestamp, session_id, agent_id, type, law_id, law_name,
             usage_ratio, old_weight, new_weight, details_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                time.time(),
                session_id,
                agent_id,
                correction.get("type", ""),
                correction.get("law_id", ""),
                correction.get("law_name", ""),
                correction.get("usage_ratio", 0),
                correction.get("old_weight", 0),
                correction.get("new_weight", correction.get("weight", 0)),
                json.dumps(correction, ensure_ascii=False),
            ),
        )
        self._conn.commit()
        return self._conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def get_zhongdao_history(
        self,
        limit: int = 50,
        law_id: Optional[str] = None,
        correction_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """查询中道校正历史"""
        self._create_zhongdao_tables()
        conditions = []
        params: List[Any] = []
        if law_id:
            conditions.append("law_id = ?")
            params.append(law_id)
        if correction_type:
            conditions.append("type = ?")
            params.append(correction_type)

        where = ""
        if conditions:
            where = "WHERE " + " AND ".join(conditions)

        sql = f"""
            SELECT * FROM zhongdao_corrections
            {where}
            ORDER BY timestamp DESC
            LIMIT ?
        """
        params.append(limit)
        rows = self._conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def get_zhongdao_summary(self) -> Dict[str, Any]:
        """中道校正汇总统计"""
        self._create_zhongdao_tables()
        total = self._conn.execute(
            "SELECT COUNT(*) FROM zhongdao_corrections"
        ).fetchone()[0]

        by_type = {}
        rows = self._conn.execute(
            "SELECT type, COUNT(*) as cnt FROM zhongdao_corrections GROUP BY type"
        ).fetchall()
        for r in rows:
            by_type[r["type"]] = r["cnt"]

        by_law = {}
        rows = self._conn.execute(
            "SELECT law_id, law_name, COUNT(*) as cnt FROM zhongdao_corrections GROUP BY law_id ORDER BY cnt DESC LIMIT 10"
        ).fetchall()
        for r in rows:
            by_law[r["law_id"]] = {
                "name": r["law_name"],
                "count": r["cnt"],
            }

        return {
            "total_corrections": total,
            "by_type": by_type,
            "by_law": by_law,
        }

    # ── v1.1.4: 校正效果追踪 + 自动调参 + 归档 ──────────────

    def get_correction_effectiveness(self, days: int = 30) -> Dict[str, Any]:
        """B1: 分析中道校正前后效果对比

        返回每日校正次数、各规律被校正频率、平均权重变化幅度。
        """
        self._create_zhongdao_tables()
        cutoff = time.time() - days * 86400

        # 每日校正次数趋势
        daily = self._conn.execute(
            """
            SELECT date(timestamp, 'unixepoch', 'localtime') as day,
                   COUNT(*) as cnt
            FROM zhongdao_corrections
            WHERE timestamp > ?
            GROUP BY day ORDER BY day
            """,
            (cutoff,),
        ).fetchall()
        daily_trend = [{"day": r["day"], "count": r["cnt"]} for r in daily]

        # 各规律被校正频率
        law_freq = self._conn.execute(
            """
            SELECT law_id, law_name, type, COUNT(*) as cnt,
                   AVG(ABS(new_weight - old_weight)) as avg_delta
            FROM zhongdao_corrections
            WHERE timestamp > ?
            GROUP BY law_id, type
            ORDER BY cnt DESC
            """,
            (cutoff,),
        ).fetchall()
        law_stats = {}
        for r in law_freq:
            lid = r["law_id"]
            if lid not in law_stats:
                law_stats[lid] = {
                    "law_name": r["law_name"],
                    "overuse_penalty": 0,
                    "neglect_boost": 0,
                    "avg_weight_delta": 0,
                }
            law_stats[lid][r["type"]] = r["cnt"]
            law_stats[lid]["avg_weight_delta"] = round(r["avg_delta"], 4)

        # 汇总
        total = self._conn.execute(
            "SELECT COUNT(*) FROM zhongdao_corrections WHERE timestamp > ?",
            (cutoff,),
        ).fetchone()[0]

        avg_ratio = self._conn.execute(
            "SELECT AVG(usage_ratio) FROM zhongdao_corrections WHERE timestamp > ? AND type='overuse_penalty'",
            (cutoff,),
        ).fetchone()[0] or 0

        return {
            "period_days": days,
            "total_corrections": total,
            "avg_overuse_ratio": round(avg_ratio, 4),
            "daily_trend": daily_trend,
            "law_stats": law_stats,
        }

    def suggest_optimal_params(self, days: int = 30) -> Dict[str, Any]:
        """B2: 基于历史校正数据推荐最优中道参数

        分析思路：如果某规律被频繁过度使用（阈值太高错过校正），
        建议降低 threshold_ratio；如果校正后权重变化过大导致思维震荡，
        建议减小 penalty/boost。
        """
        self._create_zhongdao_tables()
        cutoff = time.time() - days * 86400

        # 当前阈值下被校正的频率
        total = self._conn.execute(
            "SELECT COUNT(*) FROM zhongdao_corrections WHERE timestamp > ?",
            (cutoff,),
        ).fetchone()[0]

        # 各类型校正占比
        overuse = self._conn.execute(
            "SELECT COUNT(*) FROM zhongdao_corrections WHERE timestamp > ? AND type='overuse_penalty'",
            (cutoff,),
        ).fetchone()[0]

        # 平均权重变化
        avg_delta = self._conn.execute(
            "SELECT AVG(ABS(new_weight - old_weight)) FROM zhongdao_corrections WHERE timestamp > ?",
            (cutoff,),
        ).fetchone()[0] or 0.1

        # 建议逻辑
        suggestions = []
        ratio = overuse / max(total, 1)

        if ratio > 0.7:
            suggestions.append("过载校正占比>70%，建议降低 threshold_ratio 从 0.40 → 0.35")
            rec_ratio = 0.35
        elif ratio < 0.2 and total > 10:
            suggestions.append("校正触发较少，建议提高 threshold_ratio 从 0.40 → 0.45")
            rec_ratio = 0.45
        else:
            rec_ratio = 0.40

        if avg_delta > 0.1:
            suggestions.append(f"权重变化幅度较大({avg_delta:.3f})，建议减小 penalty_factor 从 0.20 → 0.15")
            rec_penalty = 0.15
        else:
            rec_penalty = 0.20

        if total < 5 and days > 7:
            suggestions.append("校正数据量较少，建议减小 min_samples 从 5 → 3 以提高灵敏度")
            rec_samples = 3
        else:
            rec_samples = 5

        rec_boost = 0.15  # boost 因子通常保持稳定

        return {
            "based_on_days": days,
            "total_corrections": total,
            "current_params": {
                "threshold_ratio": 0.40,
                "penalty_factor": 0.20,
                "boost_factor": 0.15,
                "min_samples": 5,
            },
            "recommended_params": {
                "threshold_ratio": rec_ratio,
                "penalty_factor": rec_penalty,
                "boost_factor": rec_boost,
                "min_samples": rec_samples,
            },
            "suggestions": suggestions,
        }

    def archive_old_corrections(self, days: int = 90) -> int:
        """B4: 归档旧校正记录，返回归档数量"""
        self._create_zhongdao_tables()
        cutoff = time.time() - days * 86400

        # 创建归档表
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS zhongdao_corrections_archive (
                id INTEGER PRIMARY KEY,
                timestamp REAL NOT NULL,
                session_id TEXT NOT NULL DEFAULT '',
                agent_id TEXT NOT NULL DEFAULT '',
                type TEXT NOT NULL,
                law_id TEXT NOT NULL,
                law_name TEXT NOT NULL DEFAULT '',
                usage_ratio REAL DEFAULT 0,
                old_weight REAL DEFAULT 0,
                new_weight REAL DEFAULT 0,
                details_json TEXT DEFAULT '{}',
                archived_at REAL NOT NULL
            );
            """
        )
        self._conn.commit()

        # 迁移旧数据
        now = time.time()
        archived = self._conn.execute(
            """
            INSERT INTO zhongdao_corrections_archive
            (id, timestamp, session_id, agent_id, type, law_id, law_name,
             usage_ratio, old_weight, new_weight, details_json, archived_at)
            SELECT id, timestamp, session_id, agent_id, type, law_id, law_name,
                   usage_ratio, old_weight, new_weight, details_json, ?
            FROM zhongdao_corrections
            WHERE timestamp < ?
            """,
            (now, cutoff),
        ).rowcount

        if archived > 0:
            self._conn.execute(
                "DELETE FROM zhongdao_corrections WHERE timestamp < ?",
                (cutoff,),
            )
            self._conn.commit()

        return archived

    def close(self):
        self._conn.close()
