"""SOMA CLI — 任何 Agent 通过 shell 命令即可调用 SOMA 智慧分析

用法:
    python -m soma                       快速验证
    python -m soma decompose <问题>       多角度拆解（零 LLM）
    python -m soma analyze <问题>         深度分析
    python -m soma compare <方案1|方案2>  多方案对比

示例:
    python -m soma decompose "如何设计消息队列"
    python -m soma analyze "微服务还是单体" --context "电商日均100万订单"
    python -m soma compare "自建MQ|云MQ|事件流" --criteria "成本,运维,扩展性"
"""
import os
import sys
import json
import warnings

os.environ.setdefault("LITELLM_LOG", "ERROR")
warnings.filterwarnings("ignore", category=UserWarning, module="jieba")
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", message=".*pkg_resources.*")


def _get_soma():
    from soma import SOMA
    return SOMA(
        persist_dir=os.environ.get("SOMA_DATA_DIR", str(__import__('pathlib').Path.home() / ".soma" / "cli")),
        llm=os.environ.get("SOMA_LLM", "mock"),
        top_k=5,
    )


def cmd_decompose(problem: str) -> None:
    """多维度问题拆解 — 纯本地，零 LLM 调用"""
    soma = _get_soma()
    foci = soma.decompose(problem)
    if not foci:
        print("(拆解失败)")
        return
    print(f"\n问题: {problem}\n")
    for i, f in enumerate(foci, 1):
        law_id = getattr(f, 'law_id', f.get('law_id', '?'))
        weight = getattr(f, 'weight', f.get('weight', 0))
        dim = getattr(f, 'dimension', f.get('dimension', ''))
        print(f"{i}. [{law_id}] (权重 {weight:.2f})")
        print(f"   {dim[:200]}\n")


def cmd_analyze(problem: str, context: str = "") -> None:
    """深度分析 — 完整 SOMA 管道"""
    soma = _get_soma()
    full = f"[背景] {context}\n[问题] {problem}" if context else problem

    try:
        result = soma.chat(full)
    except Exception:
        result = soma.respond(full)

    foci = result.get("foci", [])
    answer = result.get("answer", result.get("response", str(result)))
    memories = result.get("activated_memories", [])

    print(f"\n═══ SOMA 深度分析 ═══\n")
    print(f"问题: {problem}")
    if context:
        print(f"背景: {context}")

    if foci:
        print(f"\n▶ 拆解维度 ({len(foci)} 个):")
        for f in foci:
            lid = f.get('law_id', '?')
            dim = f.get('dimension', '')[:120]
            print(f"  [{lid}] {dim}")

    if memories:
        print(f"\n▶ 激活记忆 ({len(memories)} 条):")
        for m in memories[:5]:
            src = m.get('source', '?')
            score = m.get('activation_score', 0)
            print(f"  [{src}] score={score:.3f}")

    print(f"\n▶ 分析结论:\n{answer[:3000]}\n")


def cmd_compare(options: str, criteria: str = "") -> None:
    """多方案结构化对比"""
    soma = _get_soma()
    opts = [o.strip() for o in options.split("|") if o.strip()]
    crits = [c.strip() for c in criteria.split(",") if c.strip()] if criteria else [
        "可行性", "扩展性", "维护成本", "实施难度", "风险控制"
    ]

    if len(opts) < 2:
        print("至少需要 2 个方案（用 | 分隔）")
        return

    print(f"\n═══ SOMA 方案对比 ═══")
    print(f"方案 ({len(opts)}): {', '.join(opts)}")
    print(f"维度 ({len(crits)}): {', '.join(crits)}\n")

    for i, opt in enumerate(opts, 1):
        problem = f"评估方案: {opt}。维度: {', '.join(crits)}。给每个维度打分(0-10)并给理由。"
        try:
            result = soma.chat(problem)
        except Exception:
            result = soma.respond(problem)
        answer = result.get("answer", result.get("response", ""))
        print(f"── 方案 {i}: {opt} ──")
        print(answer[:600])
        print()

    # 综合推荐
    summary = f"综合对比: {' vs '.join(opts)}。评估维度: {', '.join(crits)}。给出最终推荐。"
    try:
        result = soma.chat(summary)
    except Exception:
        result = soma.respond(summary)
    final = result.get("answer", result.get("response", ""))
    print(f"▶ 综合推荐:\n{final[:1200]}\n")


def cmd_quickstart() -> None:
    """快速验证模式（默认）"""
    from soma import SOMA
    import soma
    ver = getattr(soma, '__version__', '?')
    print(f"SOMA v{ver} — 编程决策辅助 CLI")
    print(f"用法: python -m soma <命令> [参数]")
    print(f"命令: decompose | analyze | compare")


def main():
    if len(sys.argv) < 2:
        cmd_quickstart()
        return

    cmd = sys.argv[1]
    # 收集剩余参数，支持 --context / --criteria
    args = " ".join(sys.argv[2:])
    context = ""
    criteria = ""

    if "--context" in args:
        parts = args.split("--context")
        args = parts[0].strip()
        ctx_part = parts[1].strip()
        if "--criteria" in ctx_part:
            cp = ctx_part.split("--criteria")
            context = cp[0].strip()
            criteria = cp[1].strip()
        else:
            context = ctx_part
    elif "--criteria" in args:
        parts = args.split("--criteria")
        args = parts[0].strip()
        criteria = parts[1].strip()

    problem = args.strip()

    if cmd == "decompose":
        cmd_decompose(problem)
    elif cmd == "analyze":
        cmd_analyze(problem, context)
    elif cmd == "compare":
        cmd_compare(problem, criteria)
    elif cmd in ("help", "--help", "-h"):
        print(__doc__)
    else:
        # 未知命令时，作为问题直接分析
        cmd_analyze(" ".join(sys.argv[1:]))
