#!/usr/bin/env python3
"""零熵智库 v0.7.0 运行诊断 — 采集合并/遗忘/进化/稳定性全量指标

用法：在零熵智库服务器上运行
    cd /opt/soma-core  # 或你的 SOMA 安装目录
    python scripts/server_diagnostic.py

输出：diagnostic_v070.json（发给本地开发者）
"""

import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path


def find_data_dir():
    """定位 SOMA 数据目录"""
    candidates = [
        os.environ.get("SOMA_DATA_DIR"),
        "soma_data",
        str(Path.home() / ".soma" / "soma-core"),
        str(Path.home() / ".soma"),
    ]
    for d in candidates:
        if d and Path(d).is_dir():
            return Path(d)
    raise FileNotFoundError("找不到 SOMA 数据目录，请设置 SOMA_DATA_DIR 环境变量")


def query_episodic(conn):
    """情节记忆核心指标"""
    total = conn.execute("SELECT COUNT(*) FROM episodic_memories").fetchone()[0]

    # 记忆类型分布
    type_dist = {}
    for row in conn.execute(
        "SELECT memory_type, COUNT(*) as cnt FROM episodic_memories "
        "GROUP BY memory_type ORDER BY cnt DESC"
    ):
        type_dist[row[0]] = row[1]

    # 时间跨度
    first = conn.execute(
        "SELECT MIN(timestamp) FROM episodic_memories WHERE timestamp > 0"
    ).fetchone()[0]
    last = conn.execute(
        "SELECT MAX(timestamp) FROM episodic_memories"
    ).fetchone()[0]
    age_days = (last - first) / 86400 if first and last else 0

    # importance 分布
    imp = {}
    for row in conn.execute(
        "SELECT "
        "  CASE "
        "    WHEN importance >= 0.8 THEN 'high(>=0.8)' "
        "    WHEN importance >= 0.5 THEN 'mid(0.5-0.8)' "
        "    WHEN importance >= 0.3 THEN 'low(0.3-0.5)' "
        "    ELSE 'cold(<0.3)' "
        "  END as bucket, COUNT(*) as cnt "
        "FROM episodic_memories GROUP BY bucket ORDER BY bucket"
    ):
        imp[row[0]] = row[1]

    # 最近 30 天新增
    thirty_days_ago = time.time() - 30 * 86400
    recent = conn.execute(
        "SELECT COUNT(*) FROM episodic_memories WHERE timestamp >= ?",
        (thirty_days_ago,),
    ).fetchone()[0]

    return {
        "total": total,
        "type_distribution": type_dist,
        "age_days": round(age_days, 1),
        "first_record_at": datetime.fromtimestamp(first, tz=timezone.utc).isoformat() if first else None,
        "last_record_at": datetime.fromtimestamp(last, tz=timezone.utc).isoformat() if last else None,
        "recent_30d": recent,
        "importance_distribution": imp,
    }


def query_consolidation(conn):
    """合并引擎指标"""
    total_merges = conn.execute("SELECT COUNT(*) FROM memory_merges").fetchone()[0]

    if total_merges == 0:
        return {"total_merges": 0, "note": "合并引擎尚未触发（需至少5次会话后 evolve() 执行）"}

    avg_sim = conn.execute(
        "SELECT AVG(similarity_score) FROM memory_merges"
    ).fetchone()[0]

    # 最近合并
    recent = conn.execute(
        "SELECT primary_id, secondary_id, similarity_score, timestamp "
        "FROM memory_merges ORDER BY timestamp DESC LIMIT 5"
    ).fetchall()

    # 去重率 = 合并数 / (合并数 + 当前记忆数)
    total_memories = conn.execute(
        "SELECT COUNT(*) FROM episodic_memories"
    ).fetchone()[0]
    dedup_rate = total_merges / (total_merges + total_memories) if (total_merges + total_memories) > 0 else 0

    return {
        "total_merges": total_merges,
        "avg_similarity_score": round(avg_sim, 4) if avg_sim else 0,
        "dedup_rate": round(dedup_rate, 4),
        "recent_merges": [
            {
                "primary": r[0][:20] + "...",
                "secondary": r[1][:20] + "...",
                "similarity": round(r[2], 4),
                "time": datetime.fromtimestamp(r[3], tz=timezone.utc).isoformat(),
            }
            for r in recent
        ],
    }


def query_forgetting(conn):
    """遗忘引擎指标"""
    archived = conn.execute("SELECT COUNT(*) FROM episodic_archived").fetchone()[0]

    if archived == 0:
        return {"total_archived": 0, "note": "遗忘引擎尚未触发"}

    # 遗忘原因分布
    reasons = {}
    for row in conn.execute(
        "SELECT archive_reason, COUNT(*) as cnt FROM episodic_archived "
        "GROUP BY archive_reason"
    ):
        reasons[row[0]] = row[1]

    # 遗忘率 = 归档数 / (归档数 + 当前记忆数)
    total_memories = conn.execute(
        "SELECT COUNT(*) FROM episodic_memories"
    ).fetchone()[0]
    forget_rate = archived / (archived + total_memories) if (archived + total_memories) > 0 else 0

    return {
        "total_archived": archived,
        "archive_reasons": reasons,
        "forget_rate": round(forget_rate, 4),
    }


def query_evolution(conn):
    """进化引擎指标"""
    weights = {}
    for row in conn.execute("SELECT law_id, weight FROM weights ORDER BY weight DESC"):
        weights[row["law_id"]] = row["weight"]

    reflection_count = conn.execute("SELECT COUNT(*) FROM reflection_log").fetchone()[0]

    # 反思成功率
    success = conn.execute(
        "SELECT COUNT(*) FROM reflection_log WHERE outcome='success'"
    ).fetchone()[0]
    fail = reflection_count - success
    success_rate = success / reflection_count if reflection_count > 0 else 0

    # 触发词候选
    triggers = {}
    for row in conn.execute(
        "SELECT law_id, word, session_count FROM candidate_triggers "
        "ORDER BY session_count DESC LIMIT 20"
    ):
        triggers[f"{row['law_id']}:{row['word']}"] = row["session_count"]

    # 思维模板
    templates = conn.execute("SELECT COUNT(*) FROM focus_patterns").fetchone()[0]

    return {
        "weights": weights,
        "weight_count": len(weights),
        "reflection_count": reflection_count,
        "reflection_success_rate": round(success_rate, 4),
        "candidate_triggers": triggers,
        "thought_templates": templates,
    }


def query_retry_stats(log_dir=None):
    """LLM 重试统计（从日志文件）"""
    if log_dir is None:
        log_dir = Path("logs")
    log_dir = Path(log_dir)

    retry_count = 0
    retry_success = 0
    last_retries = []

    for log_file in sorted(log_dir.glob("*.log"), key=os.path.getmtime, reverse=True)[:3]:
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    if "llm_retry" in line.lower() or "retry" in line.lower():
                        retry_count += 1
                        if "success" in line.lower() or "recovered" in line.lower():
                            retry_success += 1
                        last_retries.append(line.strip()[-200:])
        except Exception:
            pass

    return {
        "retry_events_found": retry_count,
        "retry_success_events": retry_success,
        "note": "从最近3个日志文件扫描，可能不完整",
        "sample_lines": last_retries[-5:],
    }


def main():
    data_dir = find_data_dir()
    print(f"数据目录: {data_dir}")

    result = {
        "report_title": "SOMA v0.7.0 零熵智库运行诊断",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_dir": str(data_dir),
        "sections": {},
    }

    # 1. 情节记忆
    try:
        conn = sqlite3.connect(str(data_dir / "episodic.db"))
        conn.row_factory = sqlite3.Row
        result["sections"]["episodic"] = query_episodic(conn)
        result["sections"]["consolidation"] = query_consolidation(conn)
        result["sections"]["forgetting"] = query_forgetting(conn)
        conn.close()
        print(f"  情节记忆: {result['sections']['episodic']['total']} 条")
        print(f"  合并: {result['sections']['consolidation'].get('total_merges', 0)} 次")
        print(f"  遗忘: {result['sections']['forgetting'].get('total_archived', 0)} 条归档")
    except Exception as e:
        result["sections"]["episodic_error"] = str(e)
        print(f"  episodic 错误: {e}")

    # 2. 进化
    try:
        conn = sqlite3.connect(str(data_dir / "evolver.db"))
        conn.row_factory = sqlite3.Row
        result["sections"]["evolution"] = query_evolution(conn)
        conn.close()
        print(f"  进化: {result['sections']['evolution']['reflection_count']} 次反思")
    except Exception as e:
        result["sections"]["evolution_error"] = str(e)
        print(f"  evolver 错误: {e}")

    # 3. 语义
    try:
        conn = sqlite3.connect(str(data_dir / "semantic.db"))
        triples = conn.execute("SELECT COUNT(*) FROM semantic_triples").fetchone()[0]
        result["sections"]["semantic"] = {"total_triples": triples}
        conn.close()
        print(f"  语义: {triples} 条三元组")
    except Exception as e:
        result["sections"]["semantic_error"] = str(e)

    # 4. 技能
    try:
        conn = sqlite3.connect(str(data_dir / "skills.db"))
        skills = conn.execute("SELECT COUNT(*) FROM skills").fetchone()[0]
        result["sections"]["skills"] = {"total_skills": skills}
        conn.close()
        print(f"  技能: {skills} 个模板")
    except Exception as e:
        result["sections"]["skills_error"] = str(e)

    # 5. LLM 重试
    result["sections"]["retry"] = query_retry_stats(data_dir.parent / "logs")

    # 6. 文件大小
    sizes = {}
    for db in ["episodic.db", "semantic.db", "skills.db", "evolver.db", "analytics.db"]:
        fp = data_dir / db
        if fp.exists():
            sizes[db] = fp.stat().st_size
    result["sections"]["file_sizes"] = sizes

    # 输出
    out_path = data_dir / "diagnostic_v070.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n诊断报告已生成: {out_path}")
    print("请将此文件发送给本地开发者。")


if __name__ == "__main__":
    main()
