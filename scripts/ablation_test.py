"""SOMA 消融实验 — 裸 LLM vs SOMA 增强管道，量化思维框架的价值

实验设计:
  A组 (裸LLM): 问题直接发给 LLM，无拆解、无记忆激活
  B组 (SOMA):  完整管道 (拆解 → 激活 → 合成)

对比指标:
  - 回答长度 (深度代理)
  - 响应时间
  - Markdown 标题数 (结构层次)
  - 列表条目数 (具体程度)
  - 编号条目数 (可执行性)
  - SOMA 专属: 拆解维度数、激活记忆数
"""
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dash.providers import get_provider_manager
from dash.server import call_llm, get_agent

# ── 测试问题 (精选5个覆盖不同思维类型) ────────────────────────
QUESTIONS = [
    ("逻辑推理", "如果所有的A都是B，所有的B都是C，那么所有的A都是C吗？请分析这个三段论的正确性，并说明可能存在的例外情况。"),
    ("系统思维", "一个城市交通拥堵严重，请从系统思维角度分析可能的多层次原因和反馈回路，而不是简单归因于车辆过多。"),
    ("第一性原理", "使用第一性原理分析：为什么电池成本在过去十年下降了90%？这种下降趋势能否持续？"),
    ("决策分析", "如果你是一家公司的CEO，面临裁员20%以维持现金流 vs 保留团队以抓住市场复苏机会的两难选择，请用二八法则和决策矩阵分析。"),
    ("元认知", "什么是元认知？请说明如何通过培养元认知能力来提高个人决策质量，并给出一个30天的具体训练计划。"),
]

# 使用在 benchmark 中表现稳定的模型
MODELS = ["deepseek", "kimi", "gemini", "qwen", "openai"]


def count_structure(text: str):
    """统计回答的结构化程度"""
    return {
        "h2_count": len(re.findall(r'^##\s', text, re.MULTILINE)),
        "h3_count": len(re.findall(r'^###\s', text, re.MULTILINE)),
        "bold_count": len(re.findall(r'\*\*.*?\*\*', text)),
        "bullet_count": len(re.findall(r'^[\s]*[-*]\s', text, re.MULTILINE)),
        "numbered_count": len(re.findall(r'^[\s]*\d+[\.\)]\s', text, re.MULTILINE)),
    }


def test_raw(provider: dict, question: str):
    """A组: 裸 LLM — 问题直接发送，无任何 SOMA 管道"""
    prompt = f"请深入分析以下问题，给出结构化的回答：\n\n{question}"
    t0 = time.time()
    try:
        answer = call_llm(prompt, provider)
        elapsed = (time.time() - t0) * 1000
        return {
            "status": "success",
            "answer": answer,
            "answer_length": len(answer),
            "response_time_ms": round(elapsed, 1),
            "structure": count_structure(answer),
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)[:300],
            "response_time_ms": round((time.time() - t0) * 1000, 1),
        }


def test_soma(agent, provider: dict, question: str):
    """B组: SOMA 增强 — 完整拆解→激活→合成管道"""
    t0 = time.time()

    foci = agent.decompose(question)
    activated = agent.hub.activate(foci)

    # 构建 SOMA prompt
    parts = [f"# 用户问题\n{question}\n"]
    if foci:
        parts.append("## 思维框架拆解")
        for i, f in enumerate(foci, 1):
            parts.append(f"{i}. [{f.law_id}] {f.dimension}")
            parts.append(f"   理由: {f.rationale}")
    if activated:
        parts.append("\n## 相关记忆")
        for i, am in enumerate(activated, 1):
            parts.append(f"{i}. [{am.source}] {am.memory.content[:300]}")
    parts.append("\n请基于以上框架和相关记忆，给出深度分析回答。")
    prompt = "\n".join(parts)

    try:
        answer = call_llm(prompt, provider)
        elapsed = (time.time() - t0) * 1000
        return {
            "status": "success",
            "answer": answer,
            "answer_length": len(answer),
            "response_time_ms": round(elapsed, 1),
            "structure": count_structure(answer),
            "foci_count": len(foci),
            "foci_laws": [f.law_id for f in foci],
            "activated_count": len(activated),
            "activated_sources": [am.source for am in activated],
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)[:300],
            "response_time_ms": round((time.time() - t0) * 1000, 1),
            "foci_count": len(foci),
            "activated_count": len(activated),
        }


def main():
    pm = get_provider_manager()
    all_providers = pm._config["providers"]

    results = {}
    agent = get_agent()

    total_tests = len(MODELS) * len(QUESTIONS) * 2  # ×2 for raw and soma
    current = 0

    print(f"{'='*70}")
    print(f"  SOMA 消融实验: 裸 LLM (A组) vs SOMA增强 (B组)")
    print(f"  模型: {', '.join(MODELS)}")
    print(f"  问题: {len(QUESTIONS)}")
    print(f"  总测试: {total_tests}")
    print(f"{'='*70}")

    for pid in MODELS:
        provider = all_providers.get(pid)
        if not provider or not provider.get("api_key"):
            print(f"\n  ⏭ 跳过 {pid}: 未配置")
            continue

        model_name = provider["model"]
        print(f"\n{'─'*70}")
        print(f"  [{pid}] {model_name}")
        print(f"{'─'*70}")

        model_results = []

        for qi, (qtype, question) in enumerate(QUESTIONS, 1):
            q_short = question[:40]

            # A组: 裸 LLM
            current += 1
            print(f"  [{current}/{total_tests}] {qtype} A组(裸LLM) ", end="", flush=True)
            raw = test_raw(provider, question)
            if raw["status"] == "success":
                print(f"✅ {raw['response_time_ms']:.0f}ms {raw['answer_length']}字")
            else:
                print(f"❌ {raw.get('error', '')[:60]}")

            # B组: SOMA
            current += 1
            print(f"  [{current}/{total_tests}] {qtype} B组(SOMA)  ", end="", flush=True)
            soma = test_soma(agent, provider, question)
            if soma["status"] == "success":
                delta_len = soma["answer_length"] - raw.get("answer_length", 0)
                delta_time = soma["response_time_ms"] - raw.get("response_time_ms", 0)
                sign_len = "+" if delta_len >= 0 else ""
                sign_time = "+" if delta_time >= 0 else ""
                print(f"✅ {soma['response_time_ms']:.0f}ms {soma['answer_length']}字 "
                      f"(Δ{sign_len}{delta_len}字 / Δ{sign_time}{delta_time:.0f}ms)")
            else:
                print(f"❌ {soma.get('error', '')[:60]}")

            model_results.append({
                "question_idx": qi,
                "question_type": qtype,
                "question": question,
                "raw": raw,
                "soma": soma,
            })

        results[pid] = {
            "model": model_name,
            "results": model_results,
        }

    # ── 汇总对比 ────────────────────────────────────────────────
    print(f"\n\n{'='*70}")
    print(f"  消融实验结果汇总")
    print(f"{'='*70}")

    summary_rows = []
    for pid in MODELS:
        if pid not in results:
            continue
        r = results[pid]
        raw_success = [t for t in r["results"] if t["raw"]["status"] == "success"]
        soma_success = [t for t in r["results"] if t["soma"]["status"] == "success"]

        if raw_success and soma_success:
            avg_raw_len = sum(t["raw"]["answer_length"] for t in raw_success) / len(raw_success)
            avg_soma_len = sum(t["soma"]["answer_length"] for t in soma_success) / len(soma_success)
            avg_raw_time = sum(t["raw"]["response_time_ms"] for t in raw_success) / len(raw_success)
            avg_soma_time = sum(t["soma"]["response_time_ms"] for t in soma_success) / len(soma_success)
            # 结构指标
            avg_raw_h2 = sum(t["raw"]["structure"]["h2_count"] for t in raw_success) / len(raw_success)
            avg_soma_h2 = sum(t["soma"]["structure"]["h2_count"] for t in soma_success) / len(soma_success)
            avg_raw_items = sum(
                t["raw"]["structure"]["bullet_count"] + t["raw"]["structure"]["numbered_count"]
                for t in raw_success
            ) / len(raw_success)
            avg_soma_items = sum(
                t["soma"]["structure"]["bullet_count"] + t["soma"]["structure"]["numbered_count"]
                for t in soma_success
            ) / len(soma_success)
            # SOMA 专属
            avg_foci = sum(t["soma"]["foci_count"] for t in soma_success) / len(soma_success)
            avg_activated = sum(t["soma"]["activated_count"] for t in soma_success) / len(soma_success)

            summary_rows.append({
                "model": pid,
                "raw_len": round(avg_raw_len),
                "soma_len": round(avg_soma_len),
                "len_delta": round(avg_soma_len - avg_raw_len),
                "len_delta_pct": round((avg_soma_len - avg_raw_len) / avg_raw_len * 100, 1),
                "raw_time": round(avg_raw_time),
                "soma_time": round(avg_soma_time),
                "raw_h2": round(avg_raw_h2, 1),
                "soma_h2": round(avg_soma_h2, 1),
                "raw_items": round(avg_raw_items, 1),
                "soma_items": round(avg_soma_items, 1),
                "avg_foci": round(avg_foci, 1),
                "avg_activated": round(avg_activated, 1),
            })

    # 打印表格
    print(f"\n  {'模型':<10} {'裸LLM':>8} {'SOMA':>8} {'Δ字数':>8} {'Δ%':>7} "
          f"{'裸标题':>6} {'S标题':>6} {'裸条目':>6} {'S条目':>6} {'Foci':>5} {'记忆':>4}")
    print(f"  {'─'*10} {'─'*8} {'─'*8} {'─'*8} {'─'*7} {'─'*6} {'─'*6} {'─'*6} {'─'*6} {'─'*5} {'─'*4}")
    for sr in summary_rows:
        print(f"  {sr['model']:<10} {sr['raw_len']:>6}字 {sr['soma_len']:>6}字 "
              f"{sr['len_delta']:>+7}字 {sr['len_delta_pct']:>+6}% "
              f"{sr['raw_h2']:>5.1f} {sr['soma_h2']:>5.1f} "
              f"{sr['raw_items']:>5.1f} {sr['soma_items']:>5.1f} "
              f"{sr['avg_foci']:>4.1f} {sr['avg_activated']:>4.1f}")

    # 计算整体 SOMA 增益
    if summary_rows:
        avg_len_gain = sum(sr["len_delta_pct"] for sr in summary_rows) / len(summary_rows)
        avg_h2_gain = sum(
            (sr["soma_h2"] - sr["raw_h2"]) / max(sr["raw_h2"], 0.1) * 100
            for sr in summary_rows
        ) / len(summary_rows)
        avg_items_gain = sum(
            (sr["soma_items"] - sr["raw_items"]) / max(sr["raw_items"], 0.1) * 100
            for sr in summary_rows
        ) / len(summary_rows)
        print(f"\n  📊 SOMA 管道整体增益:")
        print(f"     回答深度: +{avg_len_gain:.0f}% 字数")
        print(f"     结构层次: +{avg_h2_gain:.0f}% 标题数")
        print(f"     具体程度: +{avg_items_gain:.0f}% 条目数")

    # ── 保存结果 ────────────────────────────────────────────────
    output_dir = Path(__file__).parent.parent / "dashboard_data"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "ablation_results.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "description": "消融实验: 裸LLM(A组) vs SOMA增强(B组)",
            "timestamp": time.time(),
            "models_tested": MODELS,
            "questions": [{"type": t, "text": q} for t, q in QUESTIONS],
            "summary": summary_rows,
            "detail": results,
        }, f, ensure_ascii=False, indent=2)

    print(f"\n  详细结果已保存到: {output_path}")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
