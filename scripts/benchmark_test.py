"""SOMA 跨模型基准测试 — 10 个问题 × 所有已配置模型"""
import json
import time
import sys
from pathlib import Path

# 确保 soma-core 在 path 中
sys.path.insert(0, str(Path(__file__).parent.parent))

from dash.providers import get_provider_manager
from dash.server import call_llm, _use_mock, get_agent

# ── 10 个测试问题 ──────────────────────────────────────────────

QUESTIONS = [
    # 1. 逻辑推理
    "如果所有的A都是B，所有的B都是C，那么所有的A都是C吗？请分析这个三段论的正确性，并说明可能存在的例外情况。",
    # 2. 系统思维
    "一个城市交通拥堵严重，请从系统思维角度分析可能的多层次原因和反馈回路，而不是简单归因于车辆过多。",
    # 3. 第一性原理
    "使用第一性原理分析：为什么电池成本在过去十年下降了90%？这种下降趋势能否持续？",
    # 4. 矛盾分析
    "企业在追求短期利润和长期创新投入之间存在什么矛盾？如何辩证地处理这种张力？",
    # 5. 决策分析
    "如果你是一家公司的CEO，面临裁员20%以维持现金流 vs 保留团队以抓住市场复苏机会的两难选择，请用二八法则和决策矩阵分析。",
    # 6. 认知偏差
    "在团队决策中，确认偏误（confirmation bias）如何影响判断质量？请提出三个具体的对抗策略，并分析每种策略的局限性。",
    # 7. 逆向思考
    "常规思维是'如何让用户更喜欢我们的产品'，请逆向思考：'如何让用户彻底讨厌我们的产品'，然后从反面推导出改进方向。",
    # 8. 战略规划
    "一家传统零售企业想转型线上，但缺乏技术基因。请制定一个分阶段战略规划，并识别每个阶段最大的风险和应对方案。",
    # 9. 复杂适应系统
    "从复杂适应系统角度分析：为什么区块链技术在被广泛看好的同时，实际大规模应用案例仍然有限？",
    # 10. 元认知
    "什么是元认知？请说明如何通过培养元认知能力来提高个人决策质量，并给出一个30天的具体训练计划。",
]

# ── 忽略的提供商（未配置密钥）─────────────────────────────────

SKIP_PROVIDERS = {"gemma", "custom"}

# ── 主流程 ─────────────────────────────────────────────────────

def build_prompt(agent, problem, foci, activated):
    """复制 agent._build_prompt 逻辑"""
    parts = []
    parts.append(f"# 用户问题\n{problem}\n")

    if foci:
        parts.append("## 思维框架拆解")
        for i, f in enumerate(foci, 1):
            parts.append(f"{i}. [{f.law_id}] {f.dimension}")
            parts.append(f"   理由: {f.rationale}")

    if activated:
        parts.append("\n## 相关记忆资粮")
        for i, am in enumerate(activated, 1):
            parts.append(f"{i}. [{am.source}] {am.memory.content[:300]}")

    parts.append("\n请基于以上框架和记忆资粮，给出深度分析回答。")
    return "\n".join(parts)


def test_single(provider_id: str, provider: dict, question: str, question_idx: int):
    """对单个模型测试单个问题"""
    agent = get_agent()

    # Step 1: 拆解
    foci = agent.decompose(question)
    # Step 2: 激活
    activated = agent.hub.activate(foci)
    # Step 3: 构建 prompt 并调用 LLM
    prompt = build_prompt(agent, question, foci, activated)

    t0 = time.time()
    try:
        answer = call_llm(prompt, provider)
        elapsed = (time.time() - t0) * 1000
        return {
            "status": "success",
            "answer": answer,
            "answer_length": len(answer),
            "response_time_ms": round(elapsed, 1),
        }
    except Exception as e:
        elapsed = (time.time() - t0) * 1000
        return {
            "status": "error",
            "error": str(e)[:500],
            "response_time_ms": round(elapsed, 1),
        }


def main():
    pm = get_provider_manager()
    all_providers = pm._config["providers"]

    # 筛选已配置的提供商
    active = {}
    for pid, p in all_providers.items():
        if pid in SKIP_PROVIDERS:
            continue
        if p.get("api_key"):
            active[pid] = p

    if not active:
        print("❌ 没有找到已配置 API Key 的提供商！")
        return

    print(f"{'='*70}")
    print(f"  SOMA 跨模型基准测试")
    print(f"  模型数: {len(active)} | 问题数: {len(QUESTIONS)} | 总测试: {len(active) * len(QUESTIONS)}")
    print(f"  Providers: {', '.join(active.keys())}")
    print(f"{'='*70}\n")

    all_results = {}
    summary = {}

    for pid, provider in active.items():
        model_name = provider["model"]
        print(f"\n{'─'*70}")
        print(f"  [{pid}] {model_name}")
        print(f"{'─'*70}")

        provider_results = []
        success_count = 0
        total_time = 0
        total_length = 0

        for qi, question in enumerate(QUESTIONS, 1):
            q_short = question[:50].replace("\n", " ")
            print(f"  Q{qi:02d}/{len(QUESTIONS):02d} [{q_short}...] ", end="", flush=True)

            result = test_single(pid, provider, question, qi)
            provider_results.append({
                "question_idx": qi,
                "question": question,
                **result,
            })

            if result["status"] == "success":
                success_count += 1
                total_time += result["response_time_ms"]
                total_length += result["answer_length"]
                print(f"✅ {result['response_time_ms']:.0f}ms ({result['answer_length']}字)")
            else:
                print(f"❌ {result['error'][:80]}")

        all_results[pid] = {
            "model": model_name,
            "results": provider_results,
        }

        summary[pid] = {
            "model": model_name,
            "total": len(QUESTIONS),
            "success": success_count,
            "failed": len(QUESTIONS) - success_count,
            "avg_response_time_ms": round(total_time / success_count, 1) if success_count else 0,
            "avg_answer_length": round(total_length / success_count, 1) if success_count else 0,
        }

        print(f"  ── 小结: {success_count}/{len(QUESTIONS)} 成功, "
              f"平均 {summary[pid]['avg_response_time_ms']:.0f}ms, "
              f"平均 {summary[pid]['avg_answer_length']:.0f}字")

    # ── 保存结果 ────────────────────────────────────────────────
    output_dir = Path(__file__).parent.parent / "dashboard_data"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "benchmark_results.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": time.time(),
            "summary": summary,
            "detail": all_results,
            "questions": QUESTIONS,
            "providers": {pid: {"model": p["model"]} for pid, p in active.items()},
        }, f, ensure_ascii=False, indent=2)

    # ── 汇总报告 ────────────────────────────────────────────────
    print(f"\n\n{'='*70}")
    print(f"  📊 汇总对比")
    print(f"{'='*70}")
    print(f"  {'提供商':<12} {'模型':<35} {'成功率':<10} {'平均耗时':<12} {'平均字数'}")
    print(f"  {'─'*12} {'─'*35} {'─'*10} {'─'*12} {'─'*10}")
    for pid, s in sorted(summary.items(), key=lambda x: x[1]["success"], reverse=True):
        success_rate = f"{s['success']}/{s['total']}"
        print(f"  {pid:<12} {s['model']:<35} {success_rate:<10} {s['avg_response_time_ms']:.0f}ms{'':>6} {s['avg_answer_length']:.0f}字")

    print(f"\n  详细结果已保存到: {output_path}")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
