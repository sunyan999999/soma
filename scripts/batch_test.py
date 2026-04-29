"""批量模型测试脚本 — 跨多模型运行复杂推理问题，收集统计结果"""
import json
import time
import urllib.request
import urllib.error
import sys
from pathlib import Path

BASE = "http://localhost:8765"
API_KEY = "test"
HEADERS = {"Content-Type": "application/json", "X-API-Key": API_KEY}

# 10 个复杂推理问题
QUESTIONS = [
    # 1: 第一性原理 + 系统思维 + 二八法则
    "为什么新能源汽车行业在补贴退坡后出现两极分化？回归最本质的商业逻辑，"
    "从底层推导这个现象。同时分析整个产业链的系统性关联，找出最关键的20%瓶颈因素。",

    # 2: 矛盾分析 + 逆向思考 + 演进视角
    "企业数字化转型中，技术投入与组织文化之间的主要矛盾是什么？"
    "如果从反面角度思考，很多企业转型失败的根本原因是什么？"
    "这一矛盾在未来5年会如何演化？",

    # 3: 第一性原理 + 类比推理 + 演进视角
    "人工智能的发展轨迹与生物进化有什么底层逻辑上的本质相似和根本差异？"
    "这种跨界类比能给我们什么关于AI未来趋势的启示？",

    # 4: 矛盾分析 + 二八法则 + 逆向思考
    "为什么说行业内卷本质上是价值创造与分配之间的结构性矛盾？"
    "如果想避免内卷，最关键的少数突破口在哪？如果不解决会有什么反面后果？",

    # 5: 系统思维 + 第一性原理 + 演进视角
    "全球供应链重组背后的系统性驱动因素有哪些？回归贸易的根本目的，"
    "从整体系统的角度看，未来十年的演化趋势是什么？",

    # 6: 逆向思考 + 矛盾分析 + 类比推理
    "与其研究成功企业的特征，不如研究企业为什么会失败——"
    "这个逆向视角揭示了哪些深层矛盾？不同行业的失败模式有什么结构上的相似性？",

    # 7: 二八法则 + 系统思维 + 演进视角
    "在人才成长体系中，哪些20%的关键节点决定了80%的发展质量？"
    "这个系统的反馈回路和全局联动是怎样的？未来人才发展模式会如何演进？",

    # 8: 类比推理 + 第一性原理 + 矛盾分析
    "城市发展与生物体新陈代谢在结构上有何映射关系？"
    "从最基础的功能需求出发，城市衰败与更新之间的核心矛盾是什么？",

    # 9: 演进视角 + 第一性原理 + 二八法则
    "从长周期演进视角看，编程范式从面向过程到面向对象再到函数式最后到AI辅助编程，"
    "遵循什么基本规律？这个系统的关键推动力是什么？最关键的少数突破点在哪？",

    # 10: 全规律综合
    "如何从多维度分析人口老龄化对社会经济的系统性冲击？"
    "涵盖根本原因、系统关联、核心矛盾、关键突破口、反面角度、国际经验类比、未来趋势。",
]

# 要测试的模型列表
MODELS = [
    "deepseek",
    "qwen",
    "gemini",
    "claude",
    "doubao",
    "openai",
    "zhipu",
    "minimax",
    "kimi",
]


def request(path, method="GET", body=None):
    url = BASE + path
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=HEADERS, method=method)
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        return {"error": str(e), "detail": err_body}


def switch_model(provider_id):
    return request("/api/config/providers/switch", "POST",
                   {"provider_id": provider_id})


def run_chat(problem):
    return request("/api/chat", "POST", {"problem": problem})


def main():
    results = {}
    total_models = len(MODELS)
    total_questions = len(QUESTIONS)

    for mi, model in enumerate(MODELS):
        print(f"\n{'='*60}")
        print(f"[{mi+1}/{total_models}] 切换到模型: {model}")
        print(f"{'='*60}")

        switch_result = switch_model(model)
        if "error" in switch_result:
            print(f"  ❌ 切换失败: {switch_result['error']} {switch_result.get('detail','')}")
            results[model] = {"error": "switch_failed", "detail": switch_result}
            continue

        print(f"  ✅ 已切换，当前提供商: {switch_result.get('current_provider', '?')}")

        model_results = []
        for qi, q in enumerate(QUESTIONS):
            q_id = f"Q{qi+1:02d}"
            print(f"  [{q_id}] {q[:60]}...", end=" ", flush=True)

            t0 = time.time()
            resp = run_chat(q)
            elapsed = time.time() - t0

            if "error" in resp:
                print(f"❌ {resp.get('error','')[:80]}")
                model_results.append({
                    "question_id": q_id,
                    "problem": q,
                    "error": resp.get("error", "unknown"),
                    "elapsed_s": round(elapsed, 1),
                })
            else:
                n_foci = len(resp.get("foci", []))
                n_mem = len(resp.get("activated_memories", []))
                law_ids = [f["law_id"] for f in resp.get("foci", [])]
                mock = resp.get("mock_mode", False)
                answer_len = len(resp.get("answer", ""))
                print(f"✅ {elapsed:.0f}s | foci={n_foci} {law_ids} | mem={n_mem} | mock={mock} | ans={answer_len}c")
                model_results.append({
                    "question_id": q_id,
                    "problem": q,
                    "foci": resp.get("foci", []),
                    "activated_count": n_mem,
                    "answer_preview": resp.get("answer", "")[:200],
                    "answer_length": answer_len,
                    "mock_mode": mock,
                    "memory_stats": resp.get("memory_stats", {}),
                    "elapsed_s": round(elapsed, 1),
                })

        results[model] = {
            "questions": model_results,
            "error_count": sum(1 for r in model_results if "error" in r),
            "success_count": sum(1 for r in model_results if "error" not in r),
        }

        # 每个模型跑完后获取统计
        stats = request("/api/framework/stats")
        results[model]["framework_stats"] = stats

        print(f"  📊 {model} 完成: {results[model]['success_count']}/{total_questions} 成功")
        print(f"     统计: {json.dumps(stats, ensure_ascii=False)}")

    # 汇总
    print(f"\n{'='*60}")
    print("📊 汇总报告")
    print(f"{'='*60}")
    for model, data in results.items():
        if "error" in data:
            print(f"  {model}: ❌ {data['error']}")
        else:
            print(f"  {model}: {data['success_count']}/{total_questions} 成功, "
                  f"{data['error_count']} 失败")
            if "framework_stats" in data:
                stats = data["framework_stats"]
                triggered = [k for k, v in stats.items() if v.get("total", 0) > 0]
                print(f"    触发规律: {triggered}")

    # 保存结果
    out_path = Path(__file__).parent / "batch_test_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n📁 结果已保存到: {out_path}")


if __name__ == "__main__":
    main()
