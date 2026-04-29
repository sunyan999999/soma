"""
SOMA 开发记忆助手 — 单项目持久化记忆 CLI

每个项目独立记忆库，互不干扰。记忆持久化在 ~/.soma/<项目名>/。

用法：
  python dev_memory.py save "修改了 auth 模块的 token 刷新逻辑"
  python dev_memory.py recall "auth token"
  python dev_memory.py list -n 10
  python dev_memory.py stats

项目名自动从 git remote 或目录名推断，也可用 SOMA_PROJECT 环境变量指定。
"""

import argparse
import os
from pathlib import Path


def _persist_dir(project: str) -> str:
    return str(Path.home() / ".soma" / project)


def _get_soma(project: str):
    from soma import SOMA
    return SOMA(
        persist_dir=_persist_dir(project),
        llm=os.environ.get("SOMA_LLM", "mock"),
        top_k=5,
    )


def _guess_project() -> str:
    name = os.environ.get("SOMA_PROJECT", "")
    if name:
        return name
    try:
        import subprocess
        r = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, cwd=Path.cwd(),
        )
        if r.returncode == 0 and r.stdout.strip():
            url = r.stdout.strip()
            return url.rstrip("/").split("/")[-1].removesuffix(".git")
    except Exception:
        pass
    return Path.cwd().name


def cmd_save(args):
    project = args.project or _guess_project()
    soma = _get_soma(project)
    mid = soma.remember(
        args.content,
        context={"task": args.task or ""},
        importance=args.importance,
    )
    print(f"[已记录] {mid[:8]}... | 项目={project} | 重要性={args.importance}")
    if not args.quiet:
        print(f"  内容: {args.content[:120]}")


def cmd_recall(args):
    project = args.project or _guess_project()
    soma = _get_soma(project)
    results = soma.query_memory(args.query, top_k=args.top_k)
    if not results:
        print("(未找到相关记忆)")
        return
    print(f"项目={project}, 找到 {len(results)} 条:\n")
    for i, m in enumerate(results, 1):
        score = m.get("activation_score", 0)
        content = m.get("content", m.get("content_preview", ""))
        print(f"--- 记忆 {i} (相关度: {score:.3f}) ---")
        print(f"  内容: {content[:200]}")
        print()


def cmd_list(args):
    project = args.project or _guess_project()
    soma = _get_soma(project)
    results = soma.query_memory(args.query or "", top_k=args.n)
    if not results:
        print("(记忆库为空)")
        return
    print(f"项目={project}, 最近 {len(results)} 条:\n")
    for i, m in enumerate(results, 1):
        content = m.get("content", m.get("content_preview", ""))
        preview = content[:100].replace("\n", " ")
        print(f"{i:3d}. {preview}")


def cmd_stats(args):
    project = args.project or _guess_project()
    soma = _get_soma(project)
    s = soma.stats
    print(f"项目: {project}")
    print(f"持久化: {_persist_dir(project)}")
    print(f"情节记忆: {s.get('episodic_count', s.get('total', '?'))} 条")
    print(f"语义记忆: {s.get('semantic_count', '?')} 条")
    print(f"技能记忆: {s.get('skill_count', '?')} 条")


def main():
    parser = argparse.ArgumentParser(
        description="SOMA 开发记忆助手 — 单项目持久化记忆",
        epilog="记忆目录: ~/.soma/<项目名>/",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_save = sub.add_parser("save", help="记录一条开发记忆")
    p_save.add_argument("content", help="记忆内容")
    p_save.add_argument("--project", "-p", help="项目名（自动检测）")
    p_save.add_argument("--task", "-t", default="", help="任务名/模块名")
    p_save.add_argument("--importance", "-i", type=float, default=0.7, help="重要性 0-1")
    p_save.add_argument("--quiet", "-q", action="store_true", help="精简输出")
    p_save.set_defaults(func=cmd_save)

    p_recall = sub.add_parser("recall", help="搜索本项目记忆")
    p_recall.add_argument("query", help="搜索关键词")
    p_recall.add_argument("--project", "-p", default="", help="项目名（自动检测）")
    p_recall.add_argument("--top-k", "-k", type=int, default=5, help="返回条数")
    p_recall.set_defaults(func=cmd_recall)

    p_list = sub.add_parser("list", help="列出本项目记忆")
    p_list.add_argument("--project", "-p", default="", help="项目名（自动检测）")
    p_list.add_argument("--query", "-q", default="", help="过滤关键词")
    p_list.add_argument("-n", type=int, default=20, help="返回条数")
    p_list.set_defaults(func=cmd_list)

    p_stats = sub.add_parser("stats", help="记忆库统计")
    p_stats.add_argument("--project", "-p", default="", help="项目名（自动检测）")
    p_stats.set_defaults(func=cmd_stats)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
