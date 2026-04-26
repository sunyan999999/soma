"""SOMA 智慧记忆能力对比测试 — Mock模式 vs 真实模型

Mock模式: 纯 SOMA 管道（拆解→激活→模拟合成），测试记忆检索质量
真实模式: 完整管道 + LLM 深度合成，测试端到端能力

对比维度:
  - 拆解维度数 & 触发规律
  - 激活记忆数 & 来源分布
  - 回答深度 & 结构层次
"""
import json
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

# ── 10 个测试问题（覆盖不同思维类型）─────────────────────────
QUESTIONS = [
    ("逻辑推理", "如果所有的A都是B，所有的B都是C，那么所有的A都是C吗？请分析这个三段论的正确性，并说明可能存在的例外情况。"),
    ("系统思维", "一个城市交通拥堵严重，请从系统思维角度分析可能的多层次原因和反馈回路，而不是简单归因于车辆过多。"),
    ("第一性原理", "使用第一性原理分析：为什么电池成本在过去十年下降了90%？这种下降趋势能否持续？"),
    ("决策分析", "如果你是一家公司的CEO，面临裁员20%以维持现金流 vs 保留团队以抓住市场复苏机会的两难选择，请用二八法则和决策矩阵分析。"),
    ("元认知", "什么是元认知？请说明如何通过培养元认知能力来提高个人决策质量，并给出一个30天的具体训练计划。"),
    ("逆向思考", "使用逆向思考分析：为什么很多创业公司即使产品很好也失败了？不是从'如何成功'出发，而是从'如何必然失败'反推。"),
    ("矛盾分析", "用矛盾分析法分析：AI技术进步与社会就业之间的矛盾。识别主要矛盾和矛盾的主要方面。"),
    ("类比推理", "将人体免疫系统与企业风险管理体系做类比，分析企业应如何构建多层次的'免疫防御'机制。"),
    ("进化视角", "从进化论视角分析：为何互联网公司的平均寿命远短于传统制造业公司？这种'进化压力'对行业生态意味着什么？"),
    ("第一性+系统思维", "综合运用第一性原理和系统思维：分析电动汽车是否真的比燃油车更环保？请从全生命周期角度分析。"),
]


def call_api(problem: str) -> dict:
    """通过 API 发起一次 SOMA 分析"""
    import urllib.request
    import urllib.error

    url = "http://localhost:8765/api/chat"
    data = json.dumps({"problem": problem}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.reason}", "raw": e.read().decode()[:300]}
    except Exception as e:
        return {"error": str(e)[:300]}


def switch_provider(provider_id: str) -> bool:
    """切换 API 提供商"""
    import urllib.request

    url = "http://localhost:8765/api/config/providers/switch"
    data = json.dumps({"provider_id": provider_id}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"},
                                 method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception:
        return False


def analyze_result(r: dict) -> dict:
    """从 API 响应中提取关键指标"""
    if "error" in r:
        return {"status": "error", "error": r["error"]}
    return {
        "status": "success",
        "mock_mode": r.get("mock_mode", False),
        "foci_count": len(r.get("foci", [])),
        "foci_laws": [f["law_id"] for f in r.get("foci", [])],
        "activated_count": len(r.get("activated_memories", [])),
        "activated_sources": [am["source"] for am in r.get("activated_memories", [])],
        "avg_activation_score": round(
            sum(am["activation_score"] for am in r.get("activated_memories", [])) / max(len(r.get("activated_memories", [])), 1), 4
        ),
        "answer_length": len(r.get("answer", "")),
        "answer": r.get("answer", ""),
        "provider": r.get("provider_used", "unknown"),
        "weights": r.get("weights", {}),
    }


def main():
    print(f"{'='*70}")
    print(f"  SOMA 智慧记忆能力对比测试")
    print(f"  A组: Mock 模式 — 纯 SOMA 管道 + 模拟合成")
    print(f"  B组: 真实模型 — 完整管道 + LLM 深度合成")
    print(f"  问题: {len(QUESTIONS)} 个")
    print(f"{'='*70}")

    # ── Group A: Mock 模式 ────────────────────────────────────
    print(f"\n{'─'*70}")
    print(f"  A组: Mock 模式 (切换到 custom 提供商, 无 API Key → 自动启用 Mock)")
    print(f"{'─'*70}")

    switch_provider("custom")
    time.sleep(0.5)

    mock_results = []
    for i, (qtype, question) in enumerate(QUESTIONS, 1):
        print(f"  [{i:2d}/10] {qtype}: {question[:50]}...", end=" ", flush=True)
        resp = call_api(question)
        analysis = analyze_result(resp)
        mock_results.append({
            "idx": i,
            "type": qtype,
            "question": question,
            **analysis,
        })
        if analysis["status"] == "success":
            print(f"✅ {analysis['foci_count']}维度 {analysis['activated_count']}记忆 "
                  f"{analysis['answer_length']}字 [{', '.join(analysis['foci_laws'][:3])}]")
        else:
            print(f"❌ {analysis.get('error', '')[:60]}")

    # ── Group B: 真实模型 ─────────────────────────────────────
    # 使用当前配置的真实提供商（qwen）
    print(f"\n{'─'*70}")
    print(f"  B组: 真实模型 (切换到 qwen)")
    print(f"{'─'*70}")

    switch_provider("qwen")
    time.sleep(0.5)

    real_results = []
    for i, (qtype, question) in enumerate(QUESTIONS, 1):
        print(f"  [{i:2d}/10] {qtype}: {question[:50]}...", end=" ", flush=True)
        resp = call_api(question)
        analysis = analyze_result(resp)
        real_results.append({
            "idx": i,
            "type": qtype,
            "question": question,
            **analysis,
        })
        if analysis["status"] == "success":
            print(f"✅ {analysis['foci_count']}维度 {analysis['activated_count']}记忆 "
                  f"{analysis['answer_length']}字 [{', '.join(analysis['foci_laws'][:3])}]")
        else:
            print(f"❌ {analysis.get('error', '')[:60]}")

    # ── 对比汇总 ──────────────────────────────────────────────
    print(f"\n\n{'='*70}")
    print(f"  智慧记忆能力对比汇总")
    print(f"{'='*70}")

    mock_ok = [r for r in mock_results if r["status"] == "success"]
    real_ok = [r for r in real_results if r["status"] == "success"]

    if mock_ok and real_ok:
        avg_mock_foci = sum(r["foci_count"] for r in mock_ok) / len(mock_ok)
        avg_real_foci = sum(r["foci_count"] for r in real_ok) / len(real_ok)
        avg_mock_mem = sum(r["activated_count"] for r in mock_ok) / len(mock_ok)
        avg_real_mem = sum(r["activated_count"] for r in real_ok) / len(real_ok)
        avg_mock_len = sum(r["answer_length"] for r in mock_ok) / len(mock_ok)
        avg_real_len = sum(r["answer_length"] for r in real_ok) / len(real_ok)
        avg_mock_score = sum(r["avg_activation_score"] for r in mock_ok) / len(mock_ok)
        avg_real_score = sum(r["avg_activation_score"] for r in real_ok) / len(real_ok)

        print(f"\n  {'指标':<20} {'Mock模式':>12} {'真实模型':>12} {'差值':>10}")
        print(f"  {'─'*20} {'─'*12} {'─'*12} {'─'*10}")
        print(f"  {'拆解维度数':<18} {avg_mock_foci:>11.1f} {avg_real_foci:>11.1f} {avg_real_foci - avg_mock_foci:>+9.1f}")
        print(f"  {'激活记忆数':<18} {avg_mock_mem:>11.1f} {avg_real_mem:>11.1f} {avg_real_mem - avg_mock_mem:>+9.1f}")
        print(f"  {'平均激活分数':<18} {avg_mock_score:>11.4f} {avg_real_score:>11.4f} {avg_real_score - avg_mock_score:>+9.4f}")
        print(f"  {'回答长度(字)':<18} {avg_mock_len:>11.0f} {avg_real_len:>11.0f} {avg_real_len - avg_mock_len:>+9.0f}")

        # 规律命中统计
        from collections import Counter
        mock_laws = Counter()
        real_laws = Counter()
        for r in mock_ok:
            for lid in r.get("foci_laws", []):
                mock_laws[lid] += 1
        for r in real_ok:
            for lid in r.get("foci_laws", []):
                real_laws[lid] += 1

        all_laws = sorted(set(list(mock_laws.keys()) + list(real_laws.keys())))
        print(f"\n  📊 思维规律命中频率 (10题中):")
        print(f"  {'规律':<28} {'Mock':>6} {'真实':>6}")
        print(f"  {'─'*28} {'─'*6} {'─'*6}")
        for lid in all_laws:
            print(f"  {lid:<28} {mock_laws.get(lid, 0):>5}次 {real_laws.get(lid, 0):>5}次")

        # 记忆来源分布
        mock_sources = Counter()
        real_sources = Counter()
        for r in mock_ok:
            for s in r.get("activated_sources", []):
                mock_sources[s] += 1
        for r in real_ok:
            for s in r.get("activated_sources", []):
                real_sources[s] += 1

        print(f"\n  🧩 记忆来源分布:")
        print(f"  {'来源':<15} {'Mock':>6} {'真实':>6}")
        print(f"  {'─'*15} {'─'*6} {'─'*6}")
        for src in sorted(set(list(mock_sources.keys()) + list(real_sources.keys()))):
            print(f"  {src:<15} {mock_sources.get(src, 0):>5}次 {real_sources.get(src, 0):>5}次")

        # 逐题对比
        print(f"\n  📋 逐题对比:")
        print(f"  {'#':<3} {'题型':<18} {'M-维度':>6} {'R-维度':>6} {'M-记忆':>6} {'R-记忆':>6} {'M-字数':>7} {'R-字数':>7}")
        print(f"  {'─'*3} {'─'*18} {'─'*6} {'─'*6} {'─'*6} {'─'*6} {'─'*7} {'─'*7}")
        for i in range(len(QUESTIONS)):
            m = mock_ok[i] if i < len(mock_ok) else {}
            r = real_ok[i] if i < len(real_ok) else {}
            print(f"  {i+1:<3} {QUESTIONS[i][0]:<18} "
                  f"{m.get('foci_count', 0):>5} {r.get('foci_count', 0):>5} "
                  f"{m.get('activated_count', 0):>5} {r.get('activated_count', 0):>5} "
                  f"{m.get('answer_length', 0):>6} {r.get('answer_length', 0):>6}")

    # ── 保存结果 ──────────────────────────────────────────────
    output_dir = Path(__file__).parent.parent / "dashboard_data"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "mock_vs_real_results.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "description": "SOMA 智慧记忆能力对比: Mock vs Real",
            "timestamp": time.time(),
            "questions": [{"type": t, "text": q} for t, q in QUESTIONS],
            "mock": mock_results,
            "real": real_results,
        }, f, ensure_ascii=False, indent=2)

    print(f"\n  详细结果已保存到: {output_path}")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
