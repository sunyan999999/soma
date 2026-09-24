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
            strictness=getattr(args, "strictness", ""),
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
# v2.0.19: 记忆管理与用量子命令
# ═══════════════════════════════════════════════════════════════

def cmd_memories(args):
    """列举 / 编辑 / 查看记忆（管理侧入口，作用域显式）"""
    try:
        soma = _get_soma(getattr(args, "project", ""))
        api = soma.memories

        mid = getattr(args, "id", "")
        uid = getattr(args, "user_id", "") or ""

        # 改写模式必须先判：否则下面的「只看」分支会先 return，改写永远走不到
        content = getattr(args, "set_content", "")
        if mid and content:
            out = api.update(mid, user_id=uid, content=content)
            print(json.dumps(out, ensure_ascii=False, indent=2))
            soma.close()
            return 0 if out.get("ok") else 1

        if mid:
            out = api.get(mid, user_id=uid)
            if out is None:
                print(json.dumps({"error": "记忆不存在或不属于该用户"},
                                  ensure_ascii=False))
                soma.close()
                return 1
            print(json.dumps(out, ensure_ascii=False, indent=2))
            soma.close()
            return 0

        out = api.list(
            user_id=getattr(args, "user_id", "") or "",
            nature=getattr(args, "nature", "") or None,
            order_by=getattr(args, "order", "recent"),
            limit=getattr(args, "limit", 20),
            preview=getattr(args, "preview", 80),
        )
        print(json.dumps(out, ensure_ascii=False, indent=2))
        if out.get("next_cursor"):
            print("\n（还有更多：--after <next_cursor> 续翻）", file=sys.stderr)
        soma.close()
        return 0
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        return 1


def cmd_forget(args):
    """删除一条记忆（默认归档，可 --restore 反悔）"""
    try:
        soma = _get_soma(getattr(args, "project", ""))
        api = soma.memories
        uid = getattr(args, "user_id", "") or ""

        if getattr(args, "list_archived", False):
            print(json.dumps(api.archived(user_id=uid, limit=args.limit),
                              ensure_ascii=False, indent=2))
            soma.close()
            return 0

        if getattr(args, "restore", ""):
            out = api.restore(args.restore, user_id=uid)
            print(json.dumps(out, ensure_ascii=False, indent=2))
            soma.close()
            return 0 if out.get("ok") else 1

        if not args.id:
            print(json.dumps({"error": "需要给出记忆 id，或用 --list/--restore"},
                              ensure_ascii=False))
            soma.close()
            return 1

        out = api.delete(args.id, user_id=uid, hard=getattr(args, "hard", False))
        print(json.dumps(out, ensure_ascii=False, indent=2))
        if out.get("archived"):
            print("\n（已归档，可 soma forget --restore %s 恢复）" % args.id,
                  file=sys.stderr)
        soma.close()
        return 0 if out.get("ok") else 1
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        return 1


def cmd_export(args):
    """导出记忆为 JSON / NDJSON（备份、迁移、云端同步）"""
    try:
        soma = _get_soma(getattr(args, "project", ""))
        out = soma.memories.export_memories(
            user_id=getattr(args, "user_id", "") or "",
            nature=getattr(args, "nature", "") or None,
            path=getattr(args, "output", "") or "",
            limit=getattr(args, "limit", 0),
        )
        # 导到文件时不把条目再打一遍屏，只报计数与路径
        if args.output:
            out.pop("items", None)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        soma.close()
        return 0
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        return 1


def cmd_usage(args):
    """真实 token 用量（累计快照 / 最近明细）"""
    try:
        soma = _get_soma(getattr(args, "project", ""))
        if getattr(args, "recent", 0):
            out = soma.recent_usage(args.recent)
        else:
            out = soma.token_usage
        print(json.dumps(out, ensure_ascii=False, indent=2))
        if not args.recent and out.get("estimated_calls"):
            print("\n（注意：%d 次调用没有 provider 返回的真实 usage，"
                  "按字符估算并已标记 estimated=true —— 这部分不能用于计费）"
                  % out["estimated_calls"], file=sys.stderr)
        soma.close()
        return 0
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        return 1


# ═══════════════════════════════════════════════════════════════
# CLI 定义
# ═══════════════════════════════════════════════════════════════

def cmd_reclassify(args):
    """批量重分类记忆的业务性质 nature（v2.0.15，迁移期一次性动作）

    默认只预览（dry_run），加 --apply 才落盘；落盘自动备份，可用 --rollback 回滚。
    """
    try:
        soma = _get_soma(getattr(args, "project", ""))

        # 回滚模式
        rb = getattr(args, "rollback", "")
        if rb:
            out = soma.rollback_nature(rb)
            print(json.dumps(out, ensure_ascii=False, indent=2))
            soma.close()
            return 0

        out = soma.reclassify_nature(
            dry_run=not getattr(args, "apply", False),
            user_id=getattr(args, "user_id", "") or "",
            limit=getattr(args, "limit", None),
        )
        print(json.dumps(out, ensure_ascii=False, indent=2))
        if out.get("dry_run") and out.get("changed"):
            print("\n（预览模式，未改动。确认无误后加 --apply 落盘）", file=sys.stderr)
        soma.close()
        return 0
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        return 1


def cmd_repair_context(args):
    """扫描并修复 context 非 JSON 对象的存量脏数据（v2.0.17）

    默认只预览（dry_run），加 --apply 才落盘；落盘自动备份，可用 --rollback 回滚。
    """
    try:
        soma = _get_soma(getattr(args, "project", ""))

        # 回滚模式
        rb = getattr(args, "rollback", "")
        if rb:
            out = soma.rollback_context(rb)
            print(json.dumps(out, ensure_ascii=False, indent=2))
            soma.close()
            return 0

        out = soma.repair_context(
            dry_run=not getattr(args, "apply", False),
            user_id=getattr(args, "user_id", "") or "",
            limit=getattr(args, "limit", None),
        )
        print(json.dumps(out, ensure_ascii=False, indent=2))
        if out.get("dry_run") and out.get("dirty"):
            print("\n（预览模式，未改动。确认无误后加 --apply 落盘）", file=sys.stderr)
        soma.close()
        return 0
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        return 1


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
    p_learn.add_argument("--strictness", type=str, default="",
                          choices=["strict", "balanced", "permissive", ""],
                          help="过滤严格度 (默认 balanced)")

    # graph
    p_graph = sub.add_parser("graph", help="自动构建知识图谱")
    _add_project_arg(p_graph)
    p_graph.add_argument("-n", "--max-memories", type=int, default=200,
                          help="最多处理多少条记忆 (默认200)")

    # reclassify（v2.0.15）
    p_rc = sub.add_parser("reclassify",
                          help="批量重分类记忆的业务性质 nature（迁移期一次性动作）")
    _add_project_arg(p_rc)
    p_rc.add_argument("--apply", action="store_true",
                       help="真正落盘（默认只预览 dry_run）")
    p_rc.add_argument("--user-id", type=str, default="",
                       help="只处理某用户的记忆")
    p_rc.add_argument("--limit", type=int, default=None,
                       help="最多处理条数")
    p_rc.add_argument("--rollback", type=str, default="",
                       help="按备份文件回滚一次重分类")

    # repair-context（v2.0.17）
    p_rp = sub.add_parser("repair-context",
                          help="修复 context 非 JSON 对象的存量脏数据")
    _add_project_arg(p_rp)
    p_rp.add_argument("--apply", action="store_true",
                       help="真正落盘（默认只预览 dry_run）")
    p_rp.add_argument("--user-id", type=str, default="",
                       help="只处理某用户的记忆")
    p_rp.add_argument("--limit", type=int, default=None,
                       help="最多处理条数")
    p_rp.add_argument("--rollback", type=str, default="",
                       help="按备份文件回滚一次修复")

    # memories（v2.0.19）
    p_mem = sub.add_parser("memories",
                           help="列举 / 查看 / 编辑记忆（管理侧入口）")
    _add_project_arg(p_mem)
    p_mem.add_argument("--id", type=str, default="",
                        help="看/改某一条记忆的全文")
    p_mem.add_argument("--set-content", type=str, default="",
                        help="配合 --id：改写这条记忆的内容")
    p_mem.add_argument("--user-id", type=str, default="",
                        help="只看某用户（多租户必须显式传）")
    p_mem.add_argument("--nature", type=str, default="",
                        choices=["", "state", "fact", "event"],
                        help="只按业务性质筛选")
    p_mem.add_argument("--order", type=str, default="recent",
                        choices=["recent", "importance"],
                        help="排序维度 (默认 recent)")
    p_mem.add_argument("-n", "--limit", type=int, default=20,
                        help="返回条数 (默认20)")
    p_mem.add_argument("--preview", type=int, default=80,
                        help="每条截断到 N 字 (0=不截断，默认80)")

    # forget（v2.0.19）
    p_fg = sub.add_parser("forget",
                          help="删除记忆（默认归档，可恢复）/ 列出归档 / 恢复")
    _add_project_arg(p_fg)
    p_fg.add_argument("id", nargs="?", default="", help="要删除的记忆 id")
    p_fg.add_argument("--user-id", type=str, default="",
                       help="多租户下校验归属")
    p_fg.add_argument("--hard", action="store_true",
                       help="真删除（不留归档，不可恢复）")
    p_fg.add_argument("--list", action="store_true", dest="list_archived",
                       help="列出最近删除（可恢复）的记忆")
    p_fg.add_argument("--restore", type=str, default="",
                       help="从归档恢复某条记忆")
    p_fg.add_argument("-n", "--limit", type=int, default=20,
                       help="--list 时返回条数 (默认20)")

    # export（v2.0.19）
    p_ex = sub.add_parser("export", help="导出记忆（备份 / 迁移 / 同步）")
    _add_project_arg(p_ex)
    p_ex.add_argument("--user-id", type=str, default="",
                       help="只导某用户")
    p_ex.add_argument("--nature", type=str, default="",
                       choices=["", "state", "fact", "event"],
                       help="只按业务性质导出")
    p_ex.add_argument("-o", "--output", type=str, default="",
                       help="写到文件（NDJSON，一行一条）；不传则打屏")
    p_ex.add_argument("-n", "--limit", type=int, default=0,
                       help="最多导出条数 (0=不限)")

    # usage（v2.0.19）
    p_us = sub.add_parser("usage", help="真实 token 用量（provider 返回值）")
    _add_project_arg(p_us)
    p_us.add_argument("--recent", type=int, default=0,
                       help="看最近 N 次调用明细（默认看累计快照）")

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
        "reclassify": cmd_reclassify,
        "repair-context": cmd_repair_context,
        "memories": cmd_memories,
        "forget": cmd_forget,
        "export": cmd_export,
        "usage": cmd_usage,
    }

    handler = dispatch.get(args.command)
    if handler is None:
        print(f"未知命令: {args.command}", file=sys.stderr)
        return 1

    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
