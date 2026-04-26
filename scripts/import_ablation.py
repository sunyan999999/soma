"""将 ablation_results.json 导入 AnalyticsStore (analytics.db)

同时导入 A组(裸LLM) 和 B组(SOMA增强) 数据，session_id 标记 _raw / _soma 以利对比。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from soma.analytics import AnalyticsStore


def main():
    result_path = Path(__file__).parent.parent / "dashboard_data" / "ablation_results.json"
    if not result_path.exists():
        print(f"❌ 找不到 {result_path}")
        return

    with open(result_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    store = AnalyticsStore(persist_dir=result_path.parent)

    # 清理旧的 ablation 数据
    old = store._conn.execute(
        "SELECT id FROM sessions WHERE id LIKE 'ablate_%'"
    ).fetchall()
    for r in old:
        store._conn.execute("DELETE FROM sessions WHERE id = ?", (r["id"],))
    store._conn.commit()
    print(f"  已清理 {len(old)} 条旧 ablation 记录")

    questions = data.get("questions", [])
    detail = data.get("detail", {})

    imported = 0
    failed = 0

    for pid, pdata in detail.items():
        model_name = pdata["model"]
        for r in pdata["results"]:
            qi = r["question_idx"]
            qtext = questions[qi - 1]["text"] if qi <= len(questions) else ""

            # ── A组: 裸 LLM ──
            raw = r.get("raw", {})
            raw_id = f"ablate_{pid}_q{qi:02d}_raw"
            raw_answer = raw.get("answer", "")
            if raw.get("status") != "success":
                raw_answer = f"[ERROR] {raw.get('error', 'Unknown')}"

            raw_data = {
                "id": raw_id,
                "problem": qtext,
                "provider_used": pid,
                "mock_mode": False,
                "response_time_ms": raw.get("response_time_ms", 0),
                "foci": [],
                "activated_memories": [],
                "answer": raw_answer,
                "weights": {},
                "memory_stats": {},
                "ablation_group": "raw",
            }

            try:
                store.record_session(raw_data)
                imported += 1
            except Exception as e:
                failed += 1
                print(f"  ❌ A组导入失败 {raw_id}: {e}")

            # ── B组: SOMA ──
            soma = r.get("soma", {})
            soma_id = f"ablate_{pid}_q{qi:02d}_soma"
            soma_answer = soma.get("answer", "")
            if soma.get("status") != "success":
                soma_answer = f"[ERROR] {soma.get('error', 'Unknown')}"

            # 构造 SOMA 的 foci 和 activated_memories 数据
            foci_laws = soma.get("foci_laws", [])
            foci_data = [
                {"law_id": lid, "weight": 0.5} for lid in foci_laws
            ]
            srcs = soma.get("activated_sources", [])
            activated_data = [
                {"source": s, "activation_score": 0.5} for s in srcs
            ]

            soma_data = {
                "id": soma_id,
                "problem": qtext,
                "provider_used": pid,
                "mock_mode": False,
                "response_time_ms": soma.get("response_time_ms", 0),
                "foci": foci_data,
                "activated_memories": activated_data,
                "answer": soma_answer,
                "weights": {},
                "memory_stats": {
                    "foci_count": soma.get("foci_count", 0),
                    "activated_count": soma.get("activated_count", 0),
                },
                "ablation_group": "soma",
            }

            try:
                store.record_session(soma_data)
                imported += 1
            except Exception as e:
                failed += 1
                print(f"  ❌ B组导入失败 {soma_id}: {e}")

    print(f"\n  导入完成: {imported} 条成功, {failed} 条失败")
    print(f"  数据库总记录数: {store.count()}")

    # 按 provider + 模式统计
    rows = store._conn.execute(
        "SELECT provider, "
        "  SUM(CASE WHEN id LIKE '%_raw' THEN 1 ELSE 0 END) as raw_cnt,"
        "  SUM(CASE WHEN id LIKE '%_soma' THEN 1 ELSE 0 END) as soma_cnt,"
        "  ROUND(AVG(CASE WHEN id LIKE '%_raw' THEN response_time_ms END)) as raw_time,"
        "  ROUND(AVG(CASE WHEN id LIKE '%_soma' THEN response_time_ms END)) as soma_time,"
        "  ROUND(AVG(CASE WHEN id LIKE '%_raw' THEN answer_length END)) as raw_len,"
        "  ROUND(AVG(CASE WHEN id LIKE '%_soma' THEN answer_length END)) as soma_len"
        " FROM sessions WHERE id LIKE 'ablate_%'"
        " GROUP BY provider ORDER BY provider"
    ).fetchall()

    print(f"\n  入库统计 (A组=裸LLM / B组=SOMA):")
    print(f"  {'模型':<12} {'A组':>4} {'B组':>4} {'A平均字':>7} {'B平均字':>7} {'Δ字':>6} "
          f"{'A平均ms':>7} {'B平均ms':>7}")
    print(f"  {'─'*12} {'─'*4} {'─'*4} {'─'*7} {'─'*7} {'─'*6} {'─'*7} {'─'*7}")
    for r in rows:
        delta_len = (r["soma_len"] or 0) - (r["raw_len"] or 0)
        print(f"  {r['provider']:<12} {r['raw_cnt']:>4} {r['soma_cnt']:>4} "
              f"{r['raw_len'] or 0:>6.0f} {r['soma_len'] or 0:>6.0f} "
              f"{delta_len:>+6.0f} "
              f"{r['raw_time'] or 0:>6.0f} {r['soma_time'] or 0:>6.0f}")

    store.close()


if __name__ == "__main__":
    main()
