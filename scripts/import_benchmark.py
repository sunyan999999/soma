"""将 benchmark_results.json 导入 AnalyticsStore (analytics.db)"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from soma.analytics import AnalyticsStore


def main():
    # 读取 benchmark 结果
    result_path = Path(__file__).parent.parent / "dashboard_data" / "benchmark_results.json"
    if not result_path.exists():
        print(f"❌ 找不到 {result_path}")
        return

    with open(result_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    store = AnalyticsStore(persist_dir=result_path.parent)

    # 先清理旧的 benchmark 数据
    old = store._conn.execute(
        "SELECT id FROM sessions WHERE id LIKE 'bench_%'"
    ).fetchall()
    for r in old:
        store._conn.execute("DELETE FROM sessions WHERE id = ?", (r["id"],))
    store._conn.commit()
    print(f"  已清理 {len(old)} 条旧 benchmark 记录")

    # 逐个导入
    imported = 0
    failed_import = 0
    providers_data = data.get("detail", {})
    questions = data.get("questions", [])

    for pid, pdata in providers_data.items():
        model_name = pdata["model"]
        for r in pdata["results"]:
            qi = r["question_idx"]
            question = questions[qi - 1] if qi <= len(questions) else r.get("question", "")

            session_id = f"bench_{pid}_q{qi:02d}"

            answer = r.get("answer", "")
            if not answer and r["status"] == "error":
                answer = f"[ERROR] {r.get('error', 'Unknown error')}"

            session_data = {
                "id": session_id,
                "problem": question,
                "provider_used": pid,
                "mock_mode": False,
                "response_time_ms": r.get("response_time_ms", 0),
                "foci": [],  # benchmark 未捕获完整 pipeline 数据
                "activated_memories": [],
                "answer": answer,
                "weights": {},
                "memory_stats": {},
            }

            try:
                store.record_session(session_data)
                imported += 1
            except Exception as e:
                failed_import += 1
                print(f"  ❌ 导入失败 {session_id}: {e}")

    # 汇总
    print(f"\n  导入完成: {imported} 条成功, {failed_import} 条失败")
    print(f"  数据库总记录数: {store.count()}")
    print(f"  数据文件: {store._db_path}")

    # 按 provider 统计
    rows = store._conn.execute(
        "SELECT provider, COUNT(*) as cnt,"
        " AVG(response_time_ms) as avg_time, AVG(answer_length) as avg_len"
        " FROM sessions WHERE id LIKE 'bench_%' GROUP BY provider ORDER BY cnt DESC"
    ).fetchall()
    print(f"\n  入库统计:")
    for r in rows:
        print(f"    {r['provider']:<12} {r['cnt']:>3} 条 | avg {r['avg_time']:.0f}ms | avg {r['avg_len']:.0f}字")

    store.close()


if __name__ == "__main__":
    main()
