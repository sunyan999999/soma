"""
SOMA MCP Server — 将 SOMA 智慧记忆系统暴露为 MCP 工具。

通过 stdio 传输与 Claude Code 等 MCP 客户端通信。
只调用 SOMA 公共 API，版本自感知，能力动态适配。

用法:
    python -m soma.mcp_server

Claude Code 配置 (~/.claude/settings.json):
    {
      "mcpServers": {
        "soma": {
          "command": "python",
          "args": ["-m", "soma.mcp_server"],
          "env": {
            "SOMA_DATA_DIR": "~/.soma/claude",
            "SOMA_LLM": "deepseek-chat"
          }
        }
      }
    }

升级流程:
    1. pip install --upgrade soma-wisdom  (或 pip install . 从 soma-core)
    2. 重启 Claude Code（MCP 服务会自动加载新版本）
    3. 调用 soma_stats 确认版本已更新
"""

import json
import os
import sys
from importlib.metadata import version as _pkg_version
from pathlib import Path

MCP_SERVER_VERSION = "1.1.0"


def _get_soma_version() -> str:
    try:
        return _pkg_version("soma-wisdom")
    except Exception:
        return "unknown"


def _get_soma():
    """懒加载 SOMA 单例。只使用公共 API，不访问内部模块。"""
    global _soma_instance
    if _soma_instance is not None:
        return _soma_instance

    from soma import SOMA

    persist_dir = os.environ.get("SOMA_DATA_DIR", str(Path.home() / ".soma" / "claude"))
    llm = os.environ.get("SOMA_LLM", "mock")

    _soma_instance = SOMA(
        persist_dir=persist_dir,
        llm=llm,
        top_k=5,
    )
    return _soma_instance


_soma_instance = None


# ── 能力检测 ─────────────────────────────────────────────
# 不同版本 SOMA 可能新增/移除功能，通过 hasattr 动态检测


def _capabilities() -> dict:
    soma = _get_soma()
    return {
        "chat": hasattr(soma, "chat"),
        "respond": hasattr(soma, "respond"),
        "evolve": hasattr(soma, "evolve"),
        "discover_laws": hasattr(soma, "discover_laws"),
        "approve_law": hasattr(soma, "approve_law"),
        "remember_semantic": hasattr(soma, "remember_semantic"),
        "get_weights": hasattr(soma, "get_weights"),
        "adjust_weight": hasattr(soma, "adjust_weight"),
        "get_thought_templates": hasattr(soma, "get_thought_templates"),
        "register_expert": hasattr(soma, "register_expert"),
        "solve_multi": hasattr(soma, "solve_multi"),
        "query_memory": hasattr(soma, "query_memory"),
        "remember": hasattr(soma, "remember"),
        "reflect": hasattr(soma, "reflect"),
        "decompose": hasattr(soma, "decompose"),
        # v0.10.0: 记忆分层
        "get_scenes": hasattr(soma, "get_scenes"),
        "get_profile": hasattr(soma, "get_profile"),
        "capture_scenes": hasattr(soma, "capture_scenes"),
        "update_profile": hasattr(soma, "update_profile"),
        "get_layered_stats": hasattr(soma, "get_layered_stats"),
        "enable_layered_memory": hasattr(soma, "enable_layered_memory"),
    }


# ── MCP 服务 ─────────────────────────────────────────────


def _new_mcp():
    """创建 FastMCP 实例（延迟导入以支持版本检测）。"""
    from mcp.server.fastmcp import FastMCP

    soma_ver = _get_soma_version()
    mcp = FastMCP(
        name="SOMA 智慧记忆引擎",
        instructions=f"""SOMA v{soma_ver} — 多维度记忆与智慧推理系统。

编程决策辅助 (v1.1.0):
- 问题拆解: soma_decompose — 用7条思维规律多角度拆解问题，纯本地零LLM
- 深度分析: soma_analyze — 完整管道：拆解→激活记忆→推理→合成，附风险分析
- 方案对比: soma_compare — 多方案多维度结构化对比，自动综合推荐

记忆管理:
- 语义搜索: soma_recall — 按关键词检索历史记忆
- 记忆记录: soma_save — 持久化开发决策、Bug修复、约束发现
- 记忆列表: soma_list — 浏览最近的记忆条目
- 统计概览: soma_stats — 记忆库规模、SOMA版本、可用能力

深度分析:
- soma_chat — 多维度问题拆解+记忆激活+智慧合成

记忆分层 (v1.0+):
- 场景块: soma_scenes — 搜索用户场景块（主题聚合）
- 用户画像: soma_profile — 查看用户特征画像
- 场景捕获: soma_capture — 手动触发场景提取
- 分层统计: soma_layered_stats — 含Scene/Profile的完整统计
- 白盒输出: soma_scene_markdown — 场景的Markdown可读文档

使用场景:
- 遇到技术决策时: 先用 soma_decompose 多角度审视 → 再用 soma_analyze 深度分析
- 多方案对比时: 用 soma_compare 结构化评估 → 按综合推荐决策
- 每次决策后: 用 soma_save 记录决策和理由，下次类似问题可检索

进化机制: 权值自动调整 / 记忆合并 / 主动遗忘 / 规律发现""",
    )
    return mcp


mcp = None  # 延迟初始化


def _ensure_mcp():
    global mcp
    if mcp is None:
        mcp = _new_mcp()
        _register_tools()
    return mcp


def _register_tools():
    """注册所有 MCP 工具。放在独立函数中以支持热重载。"""

    # ── 记忆工具 ──

    @mcp.tool()
    def soma_recall(query: str, top_k: int = 5) -> str:
        """语义搜索 SOMA 记忆库。返回与 query 最相关的前 top_k 条记忆。

        用于: 会话启动时检索相关上下文、查找历史决策/Bug修复/约束。
        返回每条记忆的 内容文本 + 相关度分数(0-1)。
        """
        try:
            soma = _get_soma()
            results = soma.query_memory(query, top_k=top_k)
            if not results:
                return "(未找到相关记忆)"

            soma_ver = _get_soma_version()
            lines = [f"SOMA v{soma_ver} | 查询: {query} | 找到 {len(results)} 条:\n"]
            for i, m in enumerate(results, 1):
                score = m.get("activation_score", 0)
                content = m.get("content", m.get("content_preview", str(m)))
                mid = m.get("id", m.get("memory_id", "?"))
                lines.append(f"--- 记忆 {i} (相关度: {score:.3f}, ID: {mid}) ---")
                lines.append(f"  {content[:300]}")
                lines.append("")
            return "\n".join(lines)
        except Exception as exc:
            return f"[SOMA recall 错误] {exc}"

    @mcp.tool()
    def soma_save(content: str, importance: float = 0.7, task: str = "") -> str:
        """记录一条记忆到 SOMA。返回记忆 ID。

        触发场景:
        - 设计决策: "决定用X方案替代Y，因为Z"
        - Bug修复: "Bug: X导致Y，根因是Z，修复用W"
        - 约束发现: "约束: X模块不能动，会影响Y"
        - 用户纠正: "纠正: 用户偏好X而非Y"
        - 阶段完成: "完成Phase N: 具体做了什么"

        importance 范围 0-1，决策/约束用 0.85-0.95，普通记录用 0.5-0.7。
        """
        try:
            soma = _get_soma()
            context = {"task": task} if task else None
            mid = soma.remember(content, context=context, importance=importance)
            return f"[已记录] ID: {mid} | 重要性: {importance}\n  内容: {content[:200]}"
        except Exception as exc:
            return f"[SOMA save 错误] {exc}"

    @mcp.tool()
    def soma_list(query: str = "", n: int = 10) -> str:
        """列出 SOMA 中最近的 n 条记忆。可选 query 过滤关键词。

        用于: 快速浏览记忆库内容，了解当前项目的记忆状态。
        """
        try:
            soma = _get_soma()
            results = soma.query_memory(query or "", top_k=n)
            if not results:
                return "(记忆库为空)"

            soma_ver = _get_soma_version()
            lines = [f"SOMA v{soma_ver} | 记忆列表 (最多 {len(results)} 条):\n"]
            for i, m in enumerate(results, 1):
                content = m.get("content", m.get("content_preview", str(m)))
                preview = content[:120].replace("\n", " ")
                mid = m.get("id", m.get("memory_id", "?"))
                score = m.get("activation_score", 0)
                lines.append(f"{i:3d}. [{score:.2f}] {preview}")
            return "\n".join(lines)
        except Exception as exc:
            return f"[SOMA list 错误] {exc}"

    # ── 元信息工具 ──

    @mcp.tool()
    def soma_stats() -> str:
        """返回 SOMA 记忆库统计信息，包括 SOMA 版本、MCP 版本、能力清单。

        用于: 确认 SOMA 连接正常、版本信息、记忆库规模。
        每次 SOMA 升级后，调用此工具确认新版本生效。
        """
        try:
            soma = _get_soma()
            s = soma.stats
            caps = _capabilities()
            soma_ver = _get_soma_version()

            available = [k for k, v in caps.items() if v]
            unavailable = [k for k, v in caps.items() if not v]

            lines = [
                f"SOMA 版本: {soma_ver}",
                f"MCP 服务: v{MCP_SERVER_VERSION}",
                f"──────────────────────",
                f"情景记忆: {s.get('episodic', s.get('episodic_count', s.get('total', '?')))} 条",
                f"语义三元组: {s.get('semantic', s.get('semantic_count', '?'))} 条",
                f"技能记忆: {s.get('skill', s.get('skill_count', '?'))} 条",
            ]
            # v0.10.0: 分层统计（如可用）
            if s.get("scenes") is not None:
                lines.append(f"场景块 (L2): {s['scenes']} 个")
            if s.get("profile_entries") is not None:
                lines.append(f"画像条目 (L3): {s['profile_entries']} 条")
            lines.extend([
                f"持久化: {os.environ.get('SOMA_DATA_DIR', '~/.soma/claude')}",
                f"──────────────────────",
                f"可用能力 ({len(available)}): {', '.join(available)}",
            ])
            if unavailable:
                lines.append(f"不可用 ({len(unavailable)}): {', '.join(unavailable)}")
            return "\n".join(lines)
        except Exception as exc:
            return f"[SOMA stats 错误] {exc}"

    # ── 深度分析工具 ──

    @mcp.tool()
    def soma_chat(problem: str) -> str:
        """SOMA 深度分析——多维度拆解问题 + 激活相关记忆 + 智慧合成回答。

        返回: 拆解维度、激活的记忆、智者回答、当前权重。

        用于: 复杂技术决策需要多角度分析时。轻量记忆搜索用 soma_recall。
        注意: 此工具需要 LLM 支持，Mock 模式下分析深度受限。
        """
        try:
            soma = _get_soma()
            if not _capabilities().get("chat"):
                return "[SOMA chat 不可用] 当前版本不支持 chat 方法，请升级 soma-wisdom"

            result = soma.chat(problem)

            parts = []
            parts.append(f"问题: {result.get('problem', problem)}\n")

            # 拆解维度
            foci = result.get("foci", [])
            if foci:
                parts.append(f"拆解维度 ({len(foci)} 个):")
                for f in foci:
                    parts.append(
                        f"  [{f.get('law_id', '?')}] {f.get('dimension', '')[:100]} "
                        f"(权重: {f.get('weight', 0):.2f})"
                    )
                parts.append("")

            # 激活记忆
            memories = result.get("activated_memories", [])
            if memories:
                parts.append(f"激活记忆 ({len(memories)} 条):")
                for m in memories[:5]:
                    if isinstance(m, dict):
                        parts.append(f"  [{m.get('source', '?')}] 分数: {m.get('activation_score', 0):.3f}")
                parts.append("")

            # 智者回答
            answer = result.get("answer", "")
            if answer:
                parts.append(f"智者回答:\n{answer[:2000]}")

            return "\n".join(parts)
        except Exception as exc:
            return f"[SOMA chat 错误] {exc}"

    # ── v0.10.0: 记忆分层工具 ──

    @mcp.tool()
    def soma_scenes(query: str = "", user_id: str = "", top_k: int = 10) -> str:
        """搜索 SOMA 场景块（L2 主题聚合）。场景是从多条记忆中自动提取的主题摘要。

        每个场景包含: 标题、摘要、标签、重要性、证据记忆ID。
        用于: 了解用户的工作主题分布、发现跨会话的上下文模式。
        """
        try:
            soma = _get_soma()
            if not _capabilities().get("get_scenes"):
                return "[SOMA scenes 不可用] 当前版本不支持场景块，请升级 soma-wisdom >= v1.0.0"

            scenes = soma.get_scenes(user_id=user_id, top_k=top_k)
            if not scenes:
                return "(暂无场景块 — 记录更多记忆后将自动提取)"

            soma_ver = _get_soma_version()
            lines = [f"SOMA v{soma_ver} | 场景块 (最多 {len(scenes)} 个):\n"]
            for i, s in enumerate(scenes, 1):
                title = s.get("title", "?")
                summary = s.get("summary", "")[:150]
                tags = s.get("tags", [])
                imp = s.get("importance", 0)
                evidence = len(s.get("evidence_ids", []))
                tag_str = ", ".join(tags[:5]) if tags else "(无标签)"

                lines.append(f"--- 场景 {i}: {title} (重要性: {imp:.2f}) ---")
                lines.append(f"  摘要: {summary}")
                lines.append(f"  标签: {tag_str} | 证据: {evidence} 条记忆")
                if query and query.lower() not in title.lower() and query.lower() not in summary.lower():
                    lines[-1] += " [关键词匹配]"
                lines.append("")
            return "\n".join(lines)
        except Exception as exc:
            return f"[SOMA scenes 错误] {exc}"

    @mcp.tool()
    def soma_profile(user_id: str = "") -> str:
        """查看 SOMA 用户画像（L3 稳定特征）。从多个场景块中提取的长期用户特征。

        特征类型: preference(偏好), skill(技能), habit(习惯),
                  knowledge_gap(知识缺口), goal(目标)
        每项含: 特征类型、特征名、特征值、置信度(0-1)。
        """
        try:
            soma = _get_soma()
            if not _capabilities().get("get_profile"):
                return "[SOMA profile 不可用] 当前版本不支持用户画像，请升级 soma-wisdom >= v1.0.0"

            entries = soma.get_profile(user_id=user_id)
            if not entries:
                return "(暂无用户画像 — 积累更多场景块后将自动提取)"

            soma_ver = _get_soma_version()
            lines = [f"SOMA v{soma_ver} | 用户画像 ({len(entries)} 条):\n"]

            type_names = {
                "preference": "偏好", "skill": "技能", "habit": "习惯",
                "knowledge_gap": "知识缺口", "goal": "目标",
            }
            for trait_type in ["preference", "skill", "habit", "knowledge_gap", "goal"]:
                typed = [e for e in entries if e.get("trait_type") == trait_type]
                if not typed:
                    continue
                lines.append(f"## {type_names.get(trait_type, trait_type)}")
                for e in typed:
                    conf = e.get("confidence", 0)
                    lines.append(
                        f"  - {e.get('trait_key', '?')}: {e.get('trait_value', '?')} "
                        f"(置信度: {conf:.2f})"
                    )
                lines.append("")
            return "\n".join(lines)
        except Exception as exc:
            return f"[SOMA profile 错误] {exc}"

    @mcp.tool()
    def soma_capture(user_id: str = "", force: bool = True) -> str:
        """手动触发场景提取 — 从近期记忆自动聚合场景块。

        force=True 跳过最小间隔限制立即执行。
        返回本次创建的场景数。
        需要 LLM 支持（配置 SOMA_LLM 环境变量）。
        """
        try:
            soma = _get_soma()
            if not _capabilities().get("capture_scenes"):
                return "[SOMA capture 不可用] 当前版本不支持场景提取，请升级 soma-wisdom >= v1.0.0"

            # 收集近期记忆供提取器使用
            recent = soma.query_memory("", top_k=20)
            memories = [
                {"content": m.get("content", str(m)), "id": m.get("id", str(i))}
                for i, m in enumerate(recent)
            ]

            created = soma.capture_scenes(user_id=user_id, force=force, memories=memories)
            if created == 0:
                return (
                    "未创建新场景。可能原因:\n"
                    "  - LLM 未配置（设置 SOMA_LLM 环境变量）\n"
                    "  - 间隔保护未过期（用 force=true）\n"
                    "  - 没有足够的新记忆可供提取"
                )

            scenes = soma.get_scenes(user_id=user_id, top_k=5)
            parts = [f"场景提取完成: 新增 {created} 个场景\n"]
            for s in scenes[:created]:
                parts.append(f"  - {s.get('title', '?')}: {s.get('summary', '')[:100]}")
            return "\n".join(parts)
        except Exception as exc:
            return f"[SOMA capture 错误] {exc}"

    @mcp.tool()
    def soma_layered_stats(user_id: str = "") -> str:
        """返回 SOMA 分层记忆统计，含 Scene + Profile 状态。

        包含: 管道状态(warmup阈值/新记忆计数)、场景数、画像条目数。
        用于: 了解记忆分层系统的运行状态。
        """
        try:
            soma = _get_soma()
            if not _capabilities().get("get_layered_stats"):
                return "[SOMA layered_stats 不可用] 当前版本不支持分层记忆，请升级 soma-wisdom >= v1.0.0"

            stats = soma.get_layered_stats()
            soma_ver = _get_soma_version()

            lines = [
                f"SOMA v{soma_ver} | 分层记忆统计",
                f"──────────────────────",
                f"情景记忆 (L1): {stats.get('episodic', '?')} 条",
                f"语义三元组: {stats.get('semantic', '?')} 条",
                f"技能记忆: {stats.get('skill', '?')} 条",
                f"向量索引: {stats.get('indexed_vectors', '?')} 条",
                f"──────────────────────",
                f"场景块 (L2): {stats.get('scenes', '?')} 个",
                f"画像条目 (L3): {stats.get('profile_entries', '?')} 条",
            ]

            cap_state = stats.get("capture_state", {})
            if cap_state:
                lines.append(f"──────────────────────")
                lines.append(f"捕获管道: {'启用' if cap_state.get('enabled') else '停用'}")
                lines.append(f"  新记忆计数: {cap_state.get('new_count', 0)}")
                lines.append(f"  warmup阈值: {cap_state.get('warmup_threshold', '?')}")
                lines.append(f"  累计场景: {cap_state.get('total_scenes', 0)}")

            return "\n".join(lines)
        except Exception as exc:
            return f"[SOMA layered_stats 错误] {exc}"

    # ── v1.1.5: 编程决策辅助工具 ──

    @mcp.tool()
    def soma_decompose(problem: str) -> str:
        """问题多维度拆解——用7条思维规律分解问题，不调用LLM，纯本地推理。

        返回每个维度的分析方向和建议聚焦点。
        用于: 编程方案制定前先多角度审视问题，避免单一视角决策。
        """
        try:
            soma = _get_soma()
            if not _capabilities().get("decompose"):
                return "[SOMA decompose 不可用] 当前版本不支持"

            foci = soma.decompose(problem)
            if not foci:
                return "(拆解失败 — 尝试提供更具体的问题描述)"

            lines = [f"问题拆解 ({len(foci)} 个维度):\n"]
            for i, f in enumerate(foci, 1):
                law_id = f.get("law_id", "?")
                law_name = f.get("law_name", law_id)
                dimension = f.get("dimension", "")[:200]
                weight = f.get("weight", 0)
                lines.append(f"--- 维度 {i}: {law_name} (权重: {weight:.2f}) ---")
                lines.append(f"  分析方向: {dimension}")
                lines.append("")
            return "\n".join(lines)
        except Exception as exc:
            return f"[SOMA decompose 错误] {exc}"

    @mcp.tool()
    def soma_analyze(problem: str, context: str = "") -> str:
        """深度分析——完整SOMA管道：拆解→激活记忆→推理框架→合成答案。

        与 soma_chat 不同，此工具专门为编程/技术决策场景优化：
        - 自动检索相关历史决策记忆
        - 注入假设检验框架
        - 提供多角度风险分析

        context 参数可附带项目背景、技术栈、约束条件等上下文。
        需要 LLM 支持（设置 SOMA_LLM 环境变量）。
        """
        try:
            soma = _get_soma()
            full_problem = problem
            if context:
                full_problem = f"[背景] {context}\n[问题] {problem}"

            if _capabilities().get("chat"):
                result = soma.chat(full_problem)
            else:
                result = soma.respond(full_problem)

            answer = result.get("answer", result.get("response", str(result)))
            foci = result.get("foci", [])
            memories = result.get("activated_memories", [])

            lines = ["══════════════════════"]
            lines.append(f"问题: {problem[:200]}")
            if context:
                lines.append(f"背景: {context[:200]}")
            lines.append("══════════════════════\n")

            if foci:
                lines.append(f"▶ 拆解维度 ({len(foci)} 个):")
                for f in foci:
                    lines.append(f"  [{f.get('law_id','?')}] {f.get('dimension','')[:120]}")
                lines.append("")

            if memories:
                lines.append(f"▶ 激活记忆 ({len(memories)} 条):")
                for m in memories[:5]:
                    lines.append(f"  [{m.get('source','?')}] score={m.get('activation_score',0):.3f}")
                lines.append("")

            lines.append(f"▶ 分析结论:\n{answer[:3000]}")
            return "\n".join(lines)
        except Exception as exc:
            return f"[SOMA analyze 错误] {exc}"

    @mcp.tool()
    def soma_compare(options: str, criteria: str = "") -> str:
        """多方案对比分析——对多个方案从多个维度进行结构化对比。

        options: 多个方案描述，用 '|' 分隔。例如 "微服务架构|单体优先|模块化单体"
        criteria: 评估维度，用 ',' 分隔。例如 "扩展性,开发效率,运维成本,数据一致性"

        返回每个方案在各维度的评分、权重和综合排名。
        用于: 技术选型、架构决策等需要多方案对比的场景。
        """
        try:
            soma = _get_soma()
            opts = [o.strip() for o in options.split("|") if o.strip()]
            crits = [c.strip() for c in criteria.split(",") if c.strip()] if criteria else [
                "可行性", "扩展性", "维护成本", "实施难度", "风险控制"
            ]

            if len(opts) < 2:
                return "至少需要 2 个方案进行对比（用 | 分隔）"

            lines = ["══════════════════════"]
            lines.append(f"方案对比 ({len(opts)} 个方案 × {len(crits)} 个维度)")
            lines.append("══════════════════════\n")

            # 对每个方案单独分析
            scores = {}
            for opt in opts:
                problem = f"评估以下技术方案: {opt}。评估维度: {', '.join(crits)}。给出每个维度的评分(0-10)和理由。"
                try:
                    if _capabilities().get("chat"):
                        result = soma.chat(problem)
                    else:
                        result = soma.respond(problem)
                    answer = result.get("answer", result.get("response", str(result)))
                except Exception:
                    answer = f"(分析出错: {opt})"
                scores[opt] = answer

            lines.append("▶ 各方案分析:\n")
            for i, (opt, analysis) in enumerate(scores.items(), 1):
                lines.append(f"── 方案 {i}: {opt} ──")
                lines.append(analysis[:800])
                lines.append("")

            # 综合建议
            all_opts_str = " vs ".join(opts)
            summary_problem = f"综合对比以下方案: {all_opts_str}。评估维度: {', '.join(crits)}。给出最终推荐和理由。"
            try:
                if _capabilities().get("chat"):
                    summary = soma.chat(summary_problem)
                else:
                    summary = soma.respond(summary_problem)
                final = summary.get("answer", summary.get("response", ""))
            except Exception:
                final = "(综合建议生成失败)"

            lines.append("▶ 综合推荐:\n")
            lines.append(final[:1500])

            return "\n".join(lines)
        except Exception as exc:
            return f"[SOMA compare 错误] {exc}"

    @mcp.tool()
    def soma_scene_markdown(scene_id: str) -> str:
        """获取指定场景的白盒 Markdown 文档。展示场景的完整内容和元信息。

        用于: 深入了解某个场景块的具体内容，验证提取质量。
        """
        try:
            soma = _get_soma()
            if not _capabilities().get("get_scenes"):
                return "[SOMA scene_markdown 不可用] 当前版本不支持场景块，请升级 soma-wisdom >= v1.0.0"

            md = soma.get_scene_markdown(scene_id)
            if not md:
                return f"(未找到场景: {scene_id})"
            return md
        except Exception as exc:
            return f"[SOMA scene_markdown 错误] {exc}"


# ── 入口 ──


def main():
    """MCP 服务入口，通过 stdio 与 Claude Code 通信。"""
    soma_ver = _get_soma_version()
    caps = _capabilities()

    # 启动时输出版本信息到 stderr（不干扰 MCP stdio 协议）
    available = [k for k, v in caps.items() if v]
    print(
        f"[SOMA MCP] 启动中... SOMA v{soma_ver}, MCP v{MCP_SERVER_VERSION}, "
        f"可用能力: {len(available)}/{len(caps)}",
        file=sys.stderr,
    )

    mcp_instance = _ensure_mcp()
    print(
        f"[SOMA MCP] 已注册 {len(_capabilities())} 项能力检测, 10 个 MCP 工具, "
        f"等待客户端连接...",
        file=sys.stderr,
    )

    mcp_instance.run(transport="stdio")


if __name__ == "__main__":
    main()
