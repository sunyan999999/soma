"""将 mock_vs_real_results.json 导入 AnalyticsStore (analytics.db)"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from soma.analytics import AnalyticsStore


def main():
    result_path = Path(__file__).parent.parent / "dashboard_data" / "mock_vs_real_results.json"
    if not result_path.exists():
        print(f"❌ 找不到 {result_path}")
        return

    with open(result_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    store = AnalyticsStore(persist_dir=result_path.parent)

    # 清理旧的 mock_vs_real 数据
    old = store._conn.execute(
        "SELECT id FROM sessions WHERE id LIKE 'mvr_%'"
    ).fetchall()
    for r in old:
        store._conn.execute("DELETE FROM sessions WHERE id = ?", (r["id"],))
    store._conn.commit()
    print(f"  已清理 {len(old)} 条旧 mock_vs_real 记录")

    questions = data.get("questions", [])
    imported = 0
    failed = 0

    for group_key, group_label in [("mock", "Mock模式"), ("real", "真实模型")]:
        results = data.get(group_key, [])
        for r in results:
            qi = r["idx"]
            qtext = questions[qi - 1]["text"] if qi <= len(questions) else ""

            sid = f"mvr_{group_key}_q{qi:02d}"

            # 构建 foci 数据
            foci_data = [
                {"law_id": lid, "weight": 0.5}
                for lid in r.get("foci_laws", [])
            ]
            # 构建 activated_memories 数据
            sources = r.get("activated_sources", [])
            activated_data = [
                {"source": s, "activation_score": 0.5} for s in sources
            ]

            answer = r.get("answer", "")
            if r.get("status") != "success":
                answer = f"[ERROR] {r.get('error', 'Unknown')}"

            session_data = {
                "id": sid,
                "problem": qtext,
                "provider_used": f"{group_key}_qwen",
                "mock_mode": group_key == "mock",
                "response_time_ms": 0,
                "foci": foci_data,
                "activated_memories": activated_data,
                "answer": answer,
                "weights": {},
                "memory_stats": {
                    "test_group": group_label,
                    "question_type": r.get("type", ""),
                },
            }

            try:
                store.record_session(session_data)
                imported += 1
            except Exception as e:
                failed += 1
                print(f"  ❌ 导入失败 {sid}: {e}")

    print(f"\n  导入完成: {imported} 条成功, {failed} 条失败")
    print(f"  数据库总记录数: {store.count()}")

    # 按分组统计
    rows = store._conn.execute(
        "SELECT "
        "  SUM(CASE WHEN id LIKE 'mvr_mock_%' THEN 1 ELSE 0 END) as mock_cnt,"
        "  SUM(CASE WHEN id LIKE 'mvr_real_%' THEN 1 ELSE 0 END) as real_cnt,"
        "  ROUND(AVG(CASE WHEN id LIKE 'mvr_mock_%' THEN answer_length END)) as mock_len,"
        "  ROUND(AVG(CASE WHEN id LIKE 'mvr_real_%' THEN answer_length END)) as real_len,"
        "  ROUND(AVG(CASE WHEN id LIKE 'mvr_mock_%' THEN foci_count END), 1) as mock_foci,"
        "  ROUND(AVG(CASE WHEN id LIKE 'mvr_real_%' THEN foci_count END), 1) as real_foci,"
        "  ROUND(AVG(CASE WHEN id LIKE 'mvr_mock_%' THEN activated_count END), 1) as mock_mem,"
        "  ROUND(AVG(CASE WHEN id LIKE 'mvr_real_%' THEN activated_count END), 1) as real_mem"
        " FROM sessions WHERE id LIKE 'mvr_%'"
    ).fetchone()

    if rows:
        print(f"\n  入库统计:")
        print(f"  {'组别':<10} {'数量':>4} {'平均维度':>7} {'平均记忆':>7} {'平均字数':>7}")
        print(f"  {'─'*10} {'─'*4} {'─'*7} {'─'*7} {'─'*7}")
        print(f"  {'Mock':<10} {rows['mock_cnt']:>4} {rows['mock_foci']:>6} {rows['mock_mem']:>6} {rows['mock_len']:>6}")
        print(f"  {'Real':<10} {rows['real_cnt']:>4} {rows['real_foci']:>6} {rows['real_mem']:>6} {rows['real_len']:>6}")

    store.close()


if __name__ == "__main__":
    main()
