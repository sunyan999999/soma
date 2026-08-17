"""SOMA 统一 CLI — 所有开发智能体的共享智慧入口

用法::

    soma recall "goroutine泄漏怎么修"      # 搜索跨项目记忆
    soma record "修复了连接池耗尽问题"       # 记录经验到共享记忆库
    soma think "如何设计这个API"            # 多维度推理分析
    soma stats                             # 记忆库状态
    soma health                            # 健康检查
    soma maintain                          # 运行记忆维护（修剪+巩固+冲突检测）
    soma learn "外部知识文本..."             # 五层质量过滤后存入记忆库
    soma graph                            # 自动构建知识图谱

智能体集成::

    # 任何能执行终端命令的智能体只需在终端执行 soma 命令
    # Codex: 通过 exec_command 调用
    # Cursor: 在终端中直接使用
    # Qoder: 通过 CLI 调用
    # Claude Code: 通过 Bash tool 或 MCP 调用

设计原则:
    - 零配置：默认使用共享记忆库 (~/.soma/shared/)
    - 纯本地：不依赖外部服务，直接调用 SOMA SDK
    - 智能体友好：输出清晰，错误码明确
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path


# 共享记忆库目录 — 所有智能体写入同一位置
SHARED_MEMORY_DIR = str(Path.home() / ".soma" / "shared")

# 项目名只允许字母/数字/下划线/连字符，阻止路径穿越（--project ../.. 等）
_PROJECT_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _persist_dir(project: str = "") -> str:
    """解析记忆库目录：project 为空 → 共享库，非空 → 项目隔离库。

    校验 project 必须是安全目录名，否则抛出 ValueError。
    """
    if not project:
        return SHARED_MEMORY_DIR
    if not _PROJECT_NAME_RE.match(project):
        raise ValueError(
            f"非法项目名: {project!r}（只允许字母、数字、下划线、连字符）"
        )
    return str(Path.home() / ".soma" / project)


def _get_soma(project: str = ""):
    """惰性初始化 SOMA 实例。

    project 为空 → 共享记忆库 (~/.soma/shared/)
    project 非空 → 项目隔离记忆库 (~/.soma/<project>/)
    """
    from soma import SOMA

    soma = SOMA(
        persist_dir=_persist_dir(project),
        llm=os.environ.get("SOMA_LLM", "mock"),
        top_k=5,
    )
    # CLI 是「搜索」场景，非推理激活场景：把自适应激活阈值清零，
    # 让 recall 能召回关键词模糊匹配的低分记忆（否则默认阈值 ~0.3 会全过滤）
    soma._agent.hub.threshold = 0.0
    return soma


# ═══════════════════════════════════════════════════════════════
# 子命令实现
# ═══════════════════════════════════════════════════════════════

def cmd_health(args):
    """健康检查：验证 SOMA 可用性"""
    try:
        soma = _get_soma(getattr(args, "project", ""))
        stats = soma.stats
        print(json.dumps({
            "status": "ok",
            "version": soma.__class__.__module__.split(".")[0],
            "memory_stats": stats,
            "persist_dir": _persist_dir(getattr(args, "project", "")),
        }, ensure_ascii=False, indent=2))
        soma.close()
        return 0
    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False))
        return 1


def cmd_stats(args):
    """记忆库统计"""
    try:
        soma = _get_soma(getattr(args, "project", ""))
        stats = soma.stats
        # 补充健康信息
        try:
            health = soma.memory_health()
            stats["health"] = health
        except Exception:
            pass
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        soma.close()
        return 0
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        return 1


def cmd_recall(args):
    """搜索相关记忆"""
    query = args.query
    top_k = getattr(args, "top_k", 5)

    try:
        soma = _get_soma(getattr(args, "project", ""))
        results = soma.query_memory(query, top_k=top_k)

        if not results:
            print(json.dumps({"query": query, "results": [], "count": 0}, ensure_ascii=False))
            soma.close()
            return 0

        formatted = []
        for r in results:
            formatted.append({
                "id": r.get("memory_id", r.get("id", "")),
                "content": r.get("content_preview", r.get("content", ""))[:300],
                "type": r.get("memory_type", r.get("type", "")),
                "score": round(r.get("activation_score", r.get("score", 0)), 3),
                "importance": r.get("importance", 0),
            })

        print(json.dumps({
            "query": query,
            "count": len(formatted),
            "results": formatted,
        }, ensure_ascii=False, indent=2))
        soma.close()
        return 0
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        return 1


def cmd_record(args):
    """记录一条经验"""
    content = args.content
    importance = max(0.0, min(1.0, getattr(args, "importance", 0.7)))
    domain = getattr(args, "domain", "")

    if not content or len(content.strip()) < 3:
        print(json.dumps({"error": "内容太短，至少3个字符"}, ensure_ascii=False))
        return 1

    try:
        soma = _get_soma(getattr(args, "project", ""))
        ctx = {}
        if domain:
            ctx["domain"] = domain
        ctx["source"] = "cli"
        ctx["agent"] = os.environ.get("SOMA_AGENT", os.environ.get("USER", "unknown"))

        memory_id = soma.remember(content.strip(), ctx, importance=importance)
        print(json.dumps({
            "status": "recorded",
            "memory_id": memory_id,
            "importance": importance,
        }, ensure_ascii=False, indent=2))
        soma.close()
        return 0
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        return 1


def cmd_think(args):
    """多维度推理分析"""
    problem = args.problem

    if not problem or len(problem.strip()) < 5:
        print(json.dumps({"error": "问题太短，至少5个字符"}, ensure_ascii=False))
        return 1

    try:
        soma = _get_soma(getattr(args, "project", ""))

        # 拆解问题
        foci = soma.decompose(problem.strip())
        if not foci:
            print(json.dumps({
                "problem": problem,
                "analysis": "无法拆解该问题",
                "foci": [],
            }, ensure_ascii=False, indent=2))
            soma.close()
            return 0

        # 格式化输出
        foci_data = []
        for f in foci:
            foci_data.append({
                "law": getattr(f, "law_id", ""),
                "dimension": getattr(f, "dimension", ""),
                "rationale": getattr(f, "rationale", ""),
                "keywords": getattr(f, "keywords", []),
            })

        print(json.dumps({
            "problem": problem,
            "foci_count": len(foci_data),
            "foci": foci_data,
        }, ensure_ascii=False, indent=2))
        soma.close()
        return 0
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        return 1


def cmd_maintain(args):
    """运行记忆维护"""
    try:
        soma = _get_soma(getattr(args, "project", ""))
        report = soma.memory_maintenance(prune=True, consolidate=True, detect=True)

        conflicts_summary = [
            {"severity": c.severity, "description": c.description}
            for c in report.conflicts[:5]
        ]

        print(json.dumps({
            "status": "completed",
            "pruned": report.pruned_count,
            "consolidated_groups": report.consolidated_groups,
            "conflicts_detected": report.conflicts_detected,
            "top_conflicts": conflicts_summary,
            "duration_ms": report.duration_ms,
        }, ensure_ascii=False, indent=2))
        soma.close()
        return 0
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        return 1


def cmd_graph(args):
    """自动构建知识图谱"""
    max_memories = getattr(args, "max_memories", 200)
    try:
        soma = _get_soma(getattr(args, "project", ""))
        report = soma.build_knowledge_graph(max_memories=max_memories)
        print(json.dumps({
            "status": "completed",
            "new_triples": report.new_triples,
            "new_session_edges": report.new_session_edges,
            "new_keyword_edges": report.new_keyword_edges,
            "total_semantic": report.total_semantic_after,
            "duration_ms": report.duration_ms,
        }, ensure_ascii=False, indent=2))
        if report.sample_triples:
            samples = [f"{s} {p} {o}" for s, p, o in report.sample_triples[:3]]
            print(json.dumps({"sample_triples": samples}, ensure_ascii=False, indent=2))
        soma.close()
        return 0
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        return 1


def cmd_learn(args):
    """从外部知识学习（五层质量过滤）"""
    content = args.content
    source = getattr(args, "source", "manual")
    problem = getattr(args, "context", "")

    if not content or len(content.strip()) < 20:
        print(json.dumps({"error": "内容太短，至少20个字符"}, ensure_ascii=False))
        return 1

    try:
        soma = _get_soma(getattr(args, "project", ""))
        result = soma.learn_from_external(
            [content.strip()],
            problem_context=problem,
            source_name=source,
        )
        print(json.dumps({
            "status": "completed",
            "accepted": len(result.accepted),
            "quarantined": len(result.quarantined),
            "rejected": len(result.rejected),
            "acceptance_rate": result.acceptance_rate,
        }, ensure_ascii=False, indent=2))

        if result.accepted:
            ek = result.accepted[0]
            print(json.dumps({
                "details": {
                    "relevance": ek.relevance_score,
                    "quality": ek.quality_score,
                    "style_alignment": ek.style_alignment,
                    "conflicts": ek.conflicts,
                    "digested": ek.digested_content[:300],
                }
            }, ensure_ascii=False, indent=2))
        elif result.rejected:
            print(json.dumps({
                "reject_reason": result.rejected[0].reject_reason,
            }, ensure_ascii=False, indent=2))

        soma.close()
        return 0
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        return 1


# ═══════════════════════════════════════════════════════════════
# CLI 定义
# ═══════════════════════════════════════════════════════════════

def _add_project_arg(p: argparse.ArgumentParser) -> None:
    """为子命令添加 --project 命名空间参数（默认 shared 共享库）"""
    p.add_argument(
        "--project", type=str, default="",
        help="记忆库命名空间（默认 shared；项目记忆用 --project SOMA）",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="soma",
        description="SOMA 统一 CLI — 所有智能体的共享智慧入口",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  soma recall "goroutine泄漏怎么修"
  soma record "修复了连接池耗尽问题" --importance 0.9
  soma think "如何设计分布式锁"
  soma stats
  soma health
  soma maintain

环境变量:
  SOMA_LLM       LLM 模型名 (默认 mock，纯本地推理)
  SOMA_AGENT      调用方标识 (用于记录来源)
        """,
    )

    sub = parser.add_subparsers(dest="command", help="可用命令")

    # recall
    p_recall = sub.add_parser("recall", help="搜索共享记忆")
    _add_project_arg(p_recall)
    p_recall.add_argument("query", help="搜索查询")
    p_recall.add_argument("-n", "--top-k", type=int, default=5, help="返回条数 (默认5)")

    # record
    p_record = sub.add_parser("record", help="记录一条经验")
    _add_project_arg(p_record)
    p_record.add_argument("content", help="要记录的内容")
    p_record.add_argument("-i", "--importance", type=float, default=0.7,
                           help="重要性 0-1 (默认0.7)")
    p_record.add_argument("-d", "--domain", type=str, default="",
                           help="领域标签 (如 algorithms, devops)")

    # think
    p_think = sub.add_parser("think", help="多维度推理分析")
    _add_project_arg(p_think)
    p_think.add_argument("problem", help="要分析的问题")

    # stats
    _add_project_arg(sub.add_parser("stats", help="记忆库统计"))

    # health
    _add_project_arg(sub.add_parser("health", help="健康检查"))

    # maintain
    _add_project_arg(sub.add_parser("maintain", help="记忆维护（修剪+巩固+冲突检测）"))

    # learn
    p_learn = sub.add_parser("learn", help="从外部知识学习（五层质量过滤）")
    _add_project_arg(p_learn)
    p_learn.add_argument("content", help="外部文本内容")
    p_learn.add_argument("-s", "--source", type=str, default="manual",
                          help="来源标识 (web/document/rag)")
    p_learn.add_argument("-c", "--context", type=str, default="",
                          help="当前分析主题，用于相关性判断")

    # graph
    p_graph = sub.add_parser("graph", help="自动构建知识图谱")
    _add_project_arg(p_graph)
    p_graph.add_argument("-n", "--max-memories", type=int, default=200,
                          help="最多处理多少条记忆 (默认200)")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    dispatch = {
        "health": cmd_health,
        "stats": cmd_stats,
        "recall": cmd_recall,
        "record": cmd_record,
        "think": cmd_think,
        "maintain": cmd_maintain,
        "learn": cmd_learn,
        "graph": cmd_graph,
    }

    handler = dispatch.get(args.command)
    if handler is None:
        print(f"未知命令: {args.command}", file=sys.stderr)
        return 1

    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
