import logging
import os
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from importlib.metadata import version as _get_version
    __version__ = _get_version("soma-wisdom")
except Exception:
    __version__ = "2.0.19"

from soma.config import SOMAConfig, load_config
from soma.db import set_shared_enabled
from soma.base import MemoryUnit, Focus, ActivatedMemory
from soma.agent import SOMA_Agent
from soma.evolve import MetaEvolver
from soma.law_discovery import LawDiscovery
from soma.embedder import SOMAEmbedder
from soma.langchain_tool import create_soma_tool
from soma.llamaindex_tool import create_soma_llamaindex_tools, SOMALlamaIndexMemory
from soma.crewai_tool import create_soma_crewai_tools, SOMACrewMemory
from soma.autogen_tool import create_soma_autogen_tools, SOMAAutoGenMemory
from soma.audit import AuditLogger
from soma.rbac import RBACManager
from soma.multi_agent.orchestrator import OrchestrationResult
from soma.memory.scene import SceneStore
from soma.memory.profile import ProfileStore
from soma.memory.capture import CapturePipeline, CaptureConfig
from soma.code_memory import CodeAnalyzer, CodeStructure
from soma.memory_api import MemoryApi
from soma.usage import TokenUsage, UsageRecorder
from soma.memory_manager import MemoryManager, MaintenanceReport, ConflictReport
from soma.knowledge_gate import KnowledgeGate, GateResult, ExternalKnowledge
from soma.graph_builder import AutoGraphBuilder, GraphBuildReport
from soma.autonomous import (
    AUTONOMOUS_MAX_CONSECUTIVE_ERRORS,
    AUTONOMOUS_RETRY_BASE_SECONDS,
    AUTONOMOUS_RETRY_MAX_SECONDS,
    META_LAST_SESSION_END,
    META_RECENT_GOALS,
    RECENT_GOAL_WINDOW_HOURS,
    SESSION_GAP_SECONDS,
    BackgroundRunner,
    GoalGenerator,
    human_gap,
)

# 包内置默认思维框架 — 确保 pip install 后在任何目录都能找到
_PACKAGE_DIR = Path(__file__).parent
_DEFAULT_FRAMEWORK = _PACKAGE_DIR / "wisdom_laws.yaml"

__all__ = [
    "SOMA",
    "SOMA_Agent",
    "SOMAConfig",
    "SOMAEmbedder",
    "MetaEvolver",
    "LawDiscovery",
    "load_config",
    "create_soma_tool",
    "create_soma_llamaindex_tools",
    "SOMALlamaIndexMemory",
    "create_soma_crewai_tools",
    "SOMACrewMemory",
    "create_soma_autogen_tools",
    "SOMAAutoGenMemory",
    "AuditLogger",
    "RBACManager",
    "MemoryApi",
    "TokenUsage",
    "UsageRecorder",
    "CodeAnalyzer",
    "CodeStructure",
    "MemoryManager",
    "MaintenanceReport",
    "ConflictReport",
    "KnowledgeGate",
    "GateResult",
    "ExternalKnowledge",
    "AutoGraphBuilder",
    "GraphBuildReport",
    "MemoryUnit",
    "Focus",
    "ActivatedMemory",
    "OrchestrationResult",
    "CapturePipeline",
    "CaptureConfig",
]

_log = logging.getLogger("soma")


class SOMA:
    """SOMA 顶层门面 — v2.0.12

    使用示例::

        from soma import SOMA

        # 单Agent模式（默认，v0.1–v1.1兼容）
        soma = SOMA()
        soma.remember("第一性原理：从最基本要素出发推导...")
        answer = soma.respond("如何系统性地分析公司增长瓶颈？")

        # 多Agent模式（v1.0+），v1.1.2支持并行调度+分布式演化+中道引擎
        soma = SOMA(orchestration_mode="multi")
        soma.register_expert("analyst", ["商业分析"])
        result = soma.solve_multi("如何平衡技术投入与业务增长？")

    五分钟接入，让你的 Agent 学会智者思维。
    """

    def __init__(
        self,
        framework_config: str = None,
        llm: str = "deepseek-chat",
        llm_api_key: str = "",          # v0.9.2: LLM API Key
        llm_base_url: str = "",         # v0.9.2: LLM 自定义 base_url
        use_vector_search: bool = True,
        persist_dir: str = None,
        recall_threshold: float = 0.01,
        top_k: int = 5,
        agent_id: str = "",
        group_id: str = "",
        # v2.0.8: 构造时立即加载嵌入模型（避免首请求热路径卡 30-100s）
        warmup_on_init: bool = False,
        # v2.0.16: 注入外部嵌入器（通常来自 get_shared_embedder()），使多个实例
        # 复用同一份 ONNX 会话，不再随实例数各自占用原生内存。
        # 注入的实例由调用方管理生命周期 —— 本实例 close() 不会释放它。
        embedder=None,
        # v0.9.2: 多Agent编排
        orchestration_mode: str = "single",
        orchestration_top_k: int = 3,
        orchestration_consensus: str = "voting",
        # v1.1.2: 中道引擎
        enable_zhongdao: bool = False,
        # v1.1.3: 中道引擎可调参数
        zhongdao_threshold_ratio: float = 0.40,
        zhongdao_penalty_factor: float = 0.20,
        zhongdao_boost_factor: float = 0.15,
        zhongdao_min_samples: int = 5,
        # v0.10.0: 记忆分层
        scene_extraction_enabled: bool = False,
        profile_extraction_enabled: bool = False,
        symbolic_memory_enabled: bool = False,
        # v2.0.18: 后台常驻自主循环。默认关闭 —— 开启后才允许 start_background()
        # 真正起线程；只是构造时传 True 也不会自动启动，仍需显式调用。
        autonomous_background_enabled: bool = False,
        autonomous_background_interval: int = 3600,
        autonomous_background_max_runtime: int = 120,
        autonomous_background_max_goals: int = 1,
        # v2.0.18.2: 后台循环要为其生成目标的用户。留空 = 单租户语义；"*" =
        # 自动枚举用户轮转；也可写逗号分隔的用户 id。多租户部署必须显式配置
        # —— 留空时若库里确实有多个用户，循环会拒绝产出目标（fail-safe）。
        autonomous_background_user_ids: str = "",
        autonomous_background_max_users_per_tick: int = 5,
        shared_sqlite_connection: bool = False,
    ):
        if persist_dir is None:
            persist_dir = os.environ.get("SOMA_DATA_DIR", "soma_data")
        if framework_config is None:
            framework_config = str(_DEFAULT_FRAMEWORK)
        framework_path = Path(framework_config)
        # 兜底：如果指定的文件不存在，尝试包内置 YAML
        if not framework_path.exists():
            framework_path = _DEFAULT_FRAMEWORK

        self._config = SOMAConfig(
            framework_path=framework_path,
            episodic_persist_dir=Path(persist_dir),
            llm_model=llm,
            llm_api_key=llm_api_key,
            llm_base_url=llm_base_url,
            use_vector_search=use_vector_search,
            recall_threshold=recall_threshold,
            default_top_k=top_k,
            warmup_on_init=warmup_on_init,
            orchestration_mode=orchestration_mode,
            orchestration_top_k=orchestration_top_k,
            orchestration_consensus=orchestration_consensus,
            scene_extraction_enabled=scene_extraction_enabled,
            profile_extraction_enabled=profile_extraction_enabled,
            autonomous_background_enabled=autonomous_background_enabled,
            autonomous_background_interval=autonomous_background_interval,
            autonomous_background_max_runtime=autonomous_background_max_runtime,
            autonomous_background_max_goals=autonomous_background_max_goals,
            autonomous_background_user_ids=autonomous_background_user_ids,
            autonomous_background_max_users_per_tick=autonomous_background_max_users_per_tick,
            enable_zhongdao=enable_zhongdao,
            zhongdao_threshold_ratio=zhongdao_threshold_ratio,
            zhongdao_penalty_factor=zhongdao_penalty_factor,
            zhongdao_boost_factor=zhongdao_boost_factor,
            zhongdao_min_samples=zhongdao_min_samples,
            shared_sqlite_connection=shared_sqlite_connection,
        )
        # v2.0.18: 共享开关是进程级的，必须在任何 store 建立连接之前设置。
        # 多专家架构下让指向同一 db 文件的 store 复用同一条连接。
        set_shared_enabled(self._config.shared_sqlite_connection)
        self._agent = SOMA_Agent(
            self._config,
            agent_id=agent_id or "soma",
            group_id=group_id,
            embedder=embedder,          # v2.0.16: 支持注入共享嵌入器
        )
        self._session_count = 0
        # v2.0.18: 自主目标生成 + 后台常驻循环（后者默认关闭，懒启动）
        self._goal_generator: Optional[GoalGenerator] = None
        self._background: Optional[BackgroundRunner] = None
        # 上次进化时的规律样本数 —— 用作"脏标记"，样本没变就不空跑进化
        self._last_evolve_samples: Optional[int] = None

        # v0.9.2: 多Agent编排器（默认关闭）
        self._orchestrator = None
        if orchestration_mode == "multi":
            from soma.multi_agent.orchestrator import SOMAOrchestrator
            self._orchestrator = SOMAOrchestrator(self._config)
            self._orchestrator.set_default(self._agent)

        # v0.10.0: 记忆分层组件（延迟初始化）
        self._scene_store: Optional[SceneStore] = None
        self._profile_store: Optional[ProfileStore] = None
        self._capture_pipeline: Optional[CapturePipeline] = None

    def __getattr__(self, name):
        """将未定义的公开属性委托给内部 SOMA_Agent 实例。

        这样外部代码（如 dash/server.py）可以直接访问 agent.hub、
        agent.memory、agent.evolver 等属性，无需绕过 SOMA 包装类。
        """
        if name.startswith('_'):
            raise AttributeError(
                f"'{type(self).__name__}' object has no attribute '{name}'"
            )
        return getattr(self._agent, name)

    def respond(self, problem: str, user_id: str = "", skip_record: bool = False) -> str:
        """完整智者管道：拆解→激活→合成→反思→进化检测

        v0.9.2: 当 orchestration_mode="multi" 时，走多Agent编排管道。
        """
        # v0.9.2: 多Agent编排模式
        if self._orchestrator is not None and self._orchestrator.agent_count > 0:
            try:
                result = self._orchestrator.solve(
                    problem, strategy=self._config.orchestration_consensus,
                )
                # 有共识结果（含单Agent回退）则返回，否则回退单Agent管道
                if result.consensus is not None:
                    return result.answer
            except Exception:
                _log.error("多Agent编排失败，回退单Agent:\n%s", traceback.format_exc())
                # 回退到单Agent

        mock_fallback = False
        try:
            answer = self._agent.respond(problem, user_id=user_id)
        except Exception:
            _log.error(
                "SOMA.respond() LLM调用失败，回退到mock响应:\n%s",
                traceback.format_exc(),
            )
            answer = self._mock_respond(problem)
            mock_fallback = True
        self._session_count += 1
        outcome = "failure" if mock_fallback else "success"
        self._agent.reflect(f"soma_{self._session_count}", outcome)
        # v1.1.8: 常规进化 + 深度进化；v2.0.18 起节拍改由配置驱动（原为硬编码 % 10 / % 30）
        self._maybe_evolve(force=self._is_deep_evolution_due())
        return answer

    def chat(self, problem: str, user_id: str = "") -> dict:
        """完整对话接口，返回结构化结果（供 API / Agent 使用）

        v0.9.2: 当 orchestration_mode="multi" 时，返回含orchestration字段。
        """
        # v0.9.2: 多Agent编排模式
        if self._orchestrator is not None and self._orchestrator.agent_count > 0:
            try:
                result = self._orchestrator.solve(
                    problem, strategy=self._config.orchestration_consensus,
                )
                # 有共识结果（含单Agent回退）则返回，否则回退单Agent管道
                if result.consensus is not None:
                    return {
                        "problem": problem,
                        "answer": result.answer,
                        "orchestration": {
                            "strategy": result.routing_strategy,
                            "agents_involved": result.agents_involved,
                            "consensus_agreement": (
                                result.consensus.agreement_level if result.consensus else None
                            ),
                            "consensus_strategy": (
                                result.consensus.strategy_used if result.consensus else None
                            ),
                            "minority_view": (
                                result.consensus.minority_view if result.consensus else None
                            ),
                        },
                        "memory_stats": self._agent.memory.stats(),
                        "weights": self._agent.evolver.get_weights(),
                    }
            except Exception:
                _log.error("多Agent编排失败，回退单Agent:\n%s", traceback.format_exc())
                # 回退到单Agent管道

        complexity = self._agent._assess_complexity(problem)

        # v0.9.1: 记录用户输入用于框架锚定检测
        if self._agent.config.enable_frame_detection:
            self._agent._recent_user_turns.append(problem)
            max_window = self._agent.config.frame_detection_window * 2
            if len(self._agent._recent_user_turns) > max_window:
                self._agent._recent_user_turns = (
                    self._agent._recent_user_turns[-max_window:]
                )
            self._agent._last_frame_anchoring = (
                self._agent.hub.detect_frame_anchoring(
                    self._agent._recent_user_turns
                )
            )

        foci = self._agent.decompose(problem)
        if complexity == 1 and len(foci) > 2:
            foci = foci[:2]

        original_top_k = self._agent.hub.top_k
        if complexity == 3:
            self._agent.hub.top_k = min(original_top_k * 2, 15)
        elif complexity == 1:
            self._agent.hub.top_k = max(original_top_k // 2, 2)
        try:
            activated = self._agent.hub.activate(
                foci, user_id=user_id, laws=self._agent.engine.laws,
                agent_id=self._agent.agent_id, group_id=self._agent.group_id,
            )
        finally:
            self._agent.hub.top_k = original_top_k

        # v0.8.0: 收集记忆建议的焦点，合并进推理框架
        suggested_foci = []
        for am in activated:
            if am.suggested_focus and am.suggested_focus.weight >= 0.1:
                suggested_foci.append(am.suggested_focus)
        if suggested_foci:
            foci = foci + suggested_foci

        # v1.1.2: 中道引擎 — 会话内实时偏差检测与校正
        if self._agent.zhongdao is not None:
            self._agent.zhongdao.track(foci)
            usage_snapshot = dict(self._agent.zhongdao._session_usage)
            foci, zhongdao_corrections = self._agent.zhongdao.detect_and_correct(
                foci, self._agent.engine.laws,
            )
            if zhongdao_corrections:
                total = sum(usage_snapshot.values())
                overuse_info = ", ".join(
                    f"{lid}={c}/{total}({c/total:.0%})"
                    for lid, c in usage_snapshot.items()
                )
                _log.info(
                    "中道校正触发: 总采样=%d, 使用分布=[%s], 校正项=%d",
                    total, overuse_info, len(zhongdao_corrections),
                )
                for c in zhongdao_corrections:
                    if c["type"] == "overuse_penalty":
                        _log.info(
                            "  └ 降权: %s(%s) %.4f→%.4f (使用率%.0f%%)",
                            c["law_name"], c["law_id"],
                            c["old_weight"], c["new_weight"],
                            c["usage_ratio"] * 100,
                        )
                    elif c["type"] == "neglect_boost":
                        _log.info(
                            "  └ 提权注入: %s(%s) 权重=%.4f",
                            c["law_name"], c["law_id"], c["weight"],
                        )

        # 确认偏误检测
        if complexity >= 2:
            self._agent._last_anti_memories = self._agent.hub.anti_confirmation_search(
                foci, user_id=user_id,
                agent_id=self._agent.agent_id, group_id=self._agent.group_id,
            )
        else:
            self._agent._last_anti_memories = []

        # v0.6.0: 构建推理框架
        self._agent._last_reasoning = self._agent._execute_reasoning(
            problem, foci, activated, self._agent._last_anti_memories,
        )
        # v2.0.4: ????? — L2轻量本地/L3 LLM增强，结果返回前端展示
        pre_analysis = ""
        pre_analysis_dimensions = []
        pre_analysis_mode = "none"
        if complexity >= 2:
            try:
                # L3用LLM增强预分析，L2用纯本地预分析
                _use_llm = (complexity >= 3)
                reason_result = self.reason(problem, use_llm=_use_llm,
                                            _foci=foci, _activated=activated)
                if reason_result.get("answer"):
                    pre_analysis = (
                        f"\n\n[SOMA 多维度预分析]:\n{reason_result['answer'][:800]}\n"
                        f"[置信度: {reason_result['confidence']:.0%} | "
                        f"维度: {len(reason_result.get('reasoning_steps',[]))} | "
                        f"模式: {reason_result.get('llm_mode','local')}]"
                    )
                    pre_analysis_dimensions = [
                        {"law_id": s["law_id"], "dimension": s.get("dimension","")[:120]}
                        for s in reason_result.get("reasoning_steps", [])
                    ]
                    pre_analysis_mode = "llm_enhanced" if _use_llm else "local"

                    # v2.0.5: L3 反事实推理 — 追问"如果反过来呢？"
                    if complexity >= 3:
                        try:
                            counter_prompt = (
                                f"对以下分析提出反事实推理:\n"
                                f"{reason_result['answer'][:400]}\n\n"
                                f"核心假设是什么？如果这些假设不成立会怎样？"
                                f"有什么被忽略的替代方案？给出2-3个反事实洞察。"
                            )
                            counter_result = self.reason(counter_prompt, use_llm=False)
                            if counter_result.get("answer"):
                                pre_analysis += (
                                    f"\n\n[反事实推理]:\n{counter_result['answer'][:400]}"
                                )
                        except Exception:
                            pass
            except Exception:
                pass

        mock_fallback = False

        try:
            base_prompt = self._agent._build_prompt(
                problem, foci, activated,
                # v2.0.18.1: 必须把 user_id 传下去 —— 漏传会让过期状态跨用户注入
                self._agent._stale_state_memories(problem, user_id=user_id),
            )
            if pre_analysis:
                # 注入预分析到系统提示词末尾
                enhanced_prompt = base_prompt + pre_analysis
            else:
                enhanced_prompt = base_prompt
            answer = self._agent._call_llm(enhanced_prompt, user_id)
        except Exception:
            _log.error(
                "SOMA.chat() LLM调用失败，回退到mock响应:\n%s",
                traceback.format_exc(),
            )
            answer = self._mock_respond(problem, foci, activated)
            mock_fallback = True
            answer = self._mock_respond(problem, foci, activated)
            mock_fallback = True

        # v0.6.0: 因果抽取
        if complexity >= self._agent.config.causal_extraction_complexity:
            self._agent._extract_causal_relations(problem, answer)

        # v0.8.0: 反思质量自评
        quality = self._agent.quality_evaluator.evaluate(
            answer=answer,
            memory_contents=[am.memory.content for am in activated],
            conflict_count=len(getattr(self._agent.hub, 'last_conflicts', [])),
        )
        if quality["needs_reflection"]:
            self._agent._last_quality_note = (
                f"[质量反馈] 综合分 {quality['overall']:.2f} ({quality['grade']}) — "
                f"一致性 {quality['consistency']:.2f} "
                f"连贯性 {quality['coherence']:.2f} "
                f"可操作性 {quality['actionability']:.2f}"
            )
        else:
            self._agent._last_quality_note = ""

        for am in activated:
            am.memory.access_count += 1
            if am.source == "episodic":
                self._agent.memory.episodic.increment_access(am.memory.id)
        self._agent.evolver.set_current_context(foci, activated, problem)
        self._session_count += 1
        outcome = "failure" if mock_fallback else "success"
        self._agent.reflect(f"soma_{self._session_count}", outcome)
        self._maybe_evolve()

        result = {
            "problem": problem,
            "answer": answer,
            "prompt": getattr(self._agent, '_last_prompt', ''),
            "foci": [
                {
                    "law_id": f.law_id,
                    "dimension": f.dimension,
                    "keywords": f.keywords[:8],
                    "weight": f.weight,
                    "rationale": f.rationale,
                }
                for f in foci
            ],
            "activated_memories": [
                self._agent.hub.explain_activation(am) for am in activated
            ],
            "memory_stats": self._agent.memory.stats(),
            "weights": self._agent.evolver.get_weights(),
            "reasoning": getattr(self._agent, '_last_reasoning', []),
            # v2.0.4: 预分析结果供前端展示
            "pre_analysis": {
                "text": pre_analysis,
                "dimensions": pre_analysis_dimensions,
                "mode": pre_analysis_mode,
                "active": len(pre_analysis_dimensions) > 0,
            },
        }

        self._agent.record_session(problem, answer, foci, activated)
        return result

    # ── v1.1.9: 自主推理（无需 LLM） ──────────────────────────

    def reason(self, problem: str, user_id: str = "", use_llm: str = "auto",
               _foci=None, _activated=None) -> dict:
        """自主推理管道 — 拆解→激活→推理→合成。

        管道: 拆解(7规律) → 激活(记忆) → 推理(因果链+类比+假设检验) → 合成(模板 或 LLM)

        v2.0.8 说明（use_llm 三档语义）：
        - use_llm=False: 纯本地推理，零 token、零网络、零 LLM 调用（推荐文档称「本地推理」）
        - use_llm="auto": 智能路由 — L1→纯本地；L2→LLM 增强（有 key 时）；L3→LLM 增强
        - use_llm=True: 强制 LLM 合成，质量最高
        （注意：auto/True 模式会调用 LLM，非「零 LLM」；纯本地请显式 use_llm=False）

        返回: {answer, foci, memories, confidence, reasoning_steps, tokens_saved, llm_mode}
        """
        t0 = time.time()

        # Step 1: 拆解（零 LLM，零网络）
        if _foci is not None:
            # 复用调用方已拆解的焦点，避免重复 decompose（chat() 预分析场景）
            foci = _foci
        else:
            # v1.1.9-fix: 保存原始向量搜索设置，避免 ONNX 下载 HuggingFace 模型
            orig_vector = self._agent.hub._use_vector if hasattr(self._agent.hub, '_use_vector') else True
            orig_embedder = self._agent.engine.embedder
            try:
                self._agent.engine.embedder = None  # 禁用 embedder，纯关键词拆解
                foci = self._agent.decompose(problem)
            finally:
                self._agent.engine.embedder = orig_embedder  # 恢复
            if not foci:
                foci = self._agent.decompose(problem)

        # Step 2: 激活记忆（零 LLM）
        if _activated is not None:
            activated = _activated
        else:
            try:
                activated = self._agent.hub.activate(foci)
            except Exception as e:
                # v2.0.8: 记录异常类型 + traceback 首行，避免激活失败被静默吞掉难定位
                _log.error(
                    "记忆激活失败 [%s]: %s\n%s",
                    type(e).__name__,
                    str(e)[:200],
                    traceback.format_exc(limit=3),
                )
                activated = []

        # Step 3: 推理框架（零 LLM — 因果链+类比+假设检验+矛盾分析）
        reasoning_steps = []
        agent = self._agent
        engine = agent.engine if hasattr(agent, 'engine') else None

        for f in foci[:4]:  # 最多4个维度
            law_id = getattr(f, 'law_id', str(f))
            step = {"law_id": law_id, "dimension": getattr(f, 'dimension', '')[:120]}
            reasoning = []

            # 因果链
            try:
                if hasattr(agent, '_execute_causal_chain'):
                    causal = agent._execute_causal_chain(problem, law_id)
                    if causal:
                        reasoning.append(f"[因果分析] {causal[:200]}")
            except Exception:
                pass

            # 跨域类比
            try:
                from soma.analogy import cross_domain_analogy
                analogy = cross_domain_analogy(problem, law_id, activated[:5] if activated else [])
                if analogy:
                    reasoning.append(f"[类比洞察] {analogy[:200]}")
            except Exception:
                pass

            # 假设检验
            try:
                if hasattr(agent, '_test_hypothesis'):
                    hypo = agent._test_hypothesis(f"假设: 从{law_id}角度看{problem[:50]}")
                    if hypo:
                        reasoning.append(f"[假设检验] {hypo[:200]}")
            except Exception:
                pass

            step["reasoning"] = reasoning
            reasoning_steps.append(step)

        # Step 4: 合成答案（模板 + 记忆证据，不调 LLM）
        answer_parts = [f"## 问题分析\n\n{problem}\n"]

        # 各维度分析
        for step in reasoning_steps:
            law_name = step["law_id"]
            for law in (engine.laws if engine else []):
                if law.id == law_name:
                    law_name = law.name
                    break
            answer_parts.append(f"### 从「{law_name}」出发\n")
            answer_parts.append(f"{step['dimension']}\n")
            for r in step["reasoning"]:
                answer_parts.append(f"{r}\n")
            answer_parts.append("")

        # 记忆证据
        if activated:
            answer_parts.append("## 相关记忆证据\n")
            for am in activated[:5]:
                content = getattr(am.memory, 'content', str(am))[:150] if hasattr(am, 'memory') else str(am)[:150]
                score = getattr(am, 'activation_score', 0)
                answer_parts.append(f"- (关联度 {score:.3f}) {content}\n")

        # 综合判断
        confidence = min(0.95, 0.4 + 0.1 * len(reasoning_steps) + 0.05 * len(activated))
        template_answer = "\n".join(answer_parts)

        # Step 4b: v2.0.2 — 智能 LLM 路由 (auto模式)
        # auto: L1→纯本地, L2→LLM(有key), L3→LLM
        llm_mode = "local"
        llm_used = False  # v2.0.3-fix: 确保所有分支都能访问
        complexity = len(reasoning_steps)
        has_key = bool(self._config.llm_api_key or self._config.llm_model != "mock")

        should_use_llm = (
            use_llm is True or
            (use_llm == "auto" and complexity >= 2 and has_key) or
            (use_llm == "auto" and complexity >= 3)
        )

        if should_use_llm:
            try:
                synthesis_prompt = (
                    f"基于以下多维度推理分析，生成一个结构化综合回答:\n\n"
                    f"问题: {problem}\n\n推理:\n{template_answer[:1500]}\n\n"
                    f"要求: 保留核心维度分析，语言更精炼，给出明确建议。"
                )
                llm_result = self._agent.respond(synthesis_prompt, skip_record=True)
                if llm_result and len(llm_result) > 50:
                    answer = llm_result[:3000]
                    llm_mode = "llm_enhanced"
                    llm_used = True
                else:
                    answer = template_answer
            except Exception:
                answer = template_answer
        else:
            answer = template_answer
            llm_used = False

        if not llm_used:
            answer_parts.append(f"\n> 置信度: {confidence:.0%} | 推理维度: {len(reasoning_steps)} | 证据: {len(activated)} 条")
            answer = "\n".join(answer_parts)

        elapsed_ms = (time.time() - t0) * 1000

        # 估算节省的 token
        estimated_prompt_tokens = len(problem) // 3 + 500  # 保守估算
        estimated_answer_tokens = len(answer) // 3
        tokens_saved = estimated_prompt_tokens + estimated_answer_tokens

        return {
            "answer": answer,
            "foci": [{"law_id": getattr(f, 'law_id', str(f)), "dimension": getattr(f, 'dimension', '')[:120]}
                     for f in foci],
            "memories": len(activated),
            "confidence": round(confidence, 3),
            "reasoning_steps": reasoning_steps,
            "tokens_saved": tokens_saved,
            "elapsed_ms": round(elapsed_ms, 1),
            "llm_mode": llm_mode,
        }

    # ── v2.0: 深度自主推理（多轮自我对话） ──────────────────

    def reason_deep(self, problem: str, rounds: int = 2) -> dict:
        """深度自主推理 — 多轮自我对话，模拟"苏格拉底式追问"。

        每轮: 回答 → 反方质疑 → 回应质疑 → 提炼修正。
        rounds=2 时: 初轮推理 + 反方辩论 + 综合结论。

        返回: {answer, confidence, rounds_detail, evolution_insights}
        """
        t0 = time.time()
        round_details = []

        # Round 1: 基础推理
        r1 = self.reason(problem)
        round_details.append({"round": 1, "role": "initial", "answer": r1["answer"][:500]})

        # Round 2: 反方辩论（自我质疑）
        devil_prompt = (
            f"对以下分析提出三点质疑或反驳:\n{r1['answer'][:800]}\n\n"
            f"质疑时考虑: 1)逻辑漏洞 2)遗漏的维度 3)过度自信的风险"
        )
        try:
            devil = self.reason(devil_prompt)
            round_details.append({"round": 2, "role": "devil_advocate", "answer": devil["answer"][:500]})
        except Exception:
            devil = {"answer": "", "confidence": 0}

        # Round 3: 综合修正（如果rounds>=2且devil有效）
        if rounds >= 2 and devil.get("answer", "").strip():
            synthesis_prompt = (
                f"原始问题: {problem}\n\n"
                f"初始分析: {r1['answer'][:500]}\n\n"
                f"反方质疑: {devil['answer'][:300]}\n\n"
                f"请综合双方观点，给出修正后的最终分析。"
            )
            try:
                final = self.reason(synthesis_prompt)
                round_details.append({"round": 3, "role": "synthesis", "answer": final["answer"][:500]})
            except Exception:
                final = r1
        else:
            final = r1

        # 计算跨轮置信度
        base_conf = r1.get("confidence", 0.5)
        if devil.get("answer", "").strip():
            base_conf = max(0.5, base_conf - 0.1)  # 有质疑时略微降低
        if rounds >= 2:
            base_conf = min(0.95, base_conf + 0.1)  # 多轮推理提升置信度

        elapsed_ms = (time.time() - t0) * 1000

        # 进化洞察：提取可学习的经验教训
        evolution_insights = []
        try:
            insight_prompt = (
                f"从以下推理过程中，提炼一条可复用的经验教训或规律:\n"
                f"问题: {problem}\n"
                f"结论: {final.get('answer', '')[:300]}"
            )
            insight = self.reason(insight_prompt)
            if insight.get("answer"):
                evolution_insights.append(insight["answer"][:200])
                # 记录到记忆
                self.remember(
                    f"推理洞察: {insight['answer'][:200]}",
                    importance=0.7,
                    context={"type": "reasoning_insight", "problem": problem[:100]},
                )
        except Exception:
            pass

        return {
            "answer": final.get("answer", r1.get("answer", "")),
            "confidence": round(base_conf, 3),
            "rounds_detail": round_details,
            "evolution_insights": evolution_insights,
            "elapsed_ms": round(elapsed_ms, 1),
            "dimensions": len(r1.get("reasoning_steps", [])),
            "memories_used": r1.get("memories", 0),
        }

    # ── v2.0: 自主认知循环 ────────────────────────────────────

    def perceive(self, problem: str) -> dict:
        """感知阶段: 评估问题是否需要 SOMA 介入、复杂度和记忆相关性。

        返回: {should_engage, complexity, memory_relevance, suggested_mode}
        - should_engage: SOMA 是否应该介入
        - suggested_mode: "reason" / "reason_deep" / "chat" / "skip"
        """
        complexity = self._agent._assess_complexity(problem)
        # 快速记忆相关性检查
        try:
            mem_results = self.query_memory(problem, top_k=3)
            mem_count = len(mem_results) if mem_results else 0
            max_score = max((m.get("activation_score", 0) for m in mem_results), default=0)
        except Exception:
            mem_count = 0
            max_score = 0

        # 判断是否介入
        should_engage = complexity >= 2 or max_score > 0.3
        if complexity >= 3:
            mode = "reason_deep"  # 复杂问题 → 多轮深度推理
        elif complexity >= 2 or max_score > 0.5:
            mode = "reason"  # 中等复杂或有强相关记忆 → 推理
        else:
            mode = "skip"  # 简单问题 → 跳过

        return {
            "should_engage": should_engage,
            "complexity": complexity,
            "memory_relevance": round(max_score, 3),
            "memory_count": mem_count,
            "suggested_mode": mode,
        }

    def act(self, problem: str, analysis: str = "") -> dict:
        """行动阶段: 基于分析生成具体的可执行建议。

        返回: {actions, priorities, risks, next_step}
        """
        if not analysis:
            reason_result = self.reason(problem)
            analysis = reason_result.get("answer", "")

        action_prompt = (
            f"基于以下分析，生成3-5条具体可执行的行动建议:\n"
            f"问题: {problem}\n分析: {analysis[:800]}\n\n"
            f"每条建议包含: 做什么、为什么、预期效果。按优先级排序。"
        )
        action_result: dict = {}
        try:
            action_result = self.reason(action_prompt)
            actions_text = action_result.get("answer", "")
        except Exception:
            actions_text = analysis[:500]
        if not isinstance(action_result, dict):
            action_result = {}

        # 提取风险提示
        risk_prompt = f"对于以下行动方案，列出2-3个关键风险:\n{actions_text[:500]}"
        try:
            risk_result = self.reason(risk_prompt)
            risks_text = risk_result.get("answer", "")
        except Exception:
            risks_text = ""

        return {
            "actions": actions_text[:2000],
            "risks": risks_text[:500],
            "next_step": actions_text.split("\n")[0] if actions_text else "无",
            "confidence": action_result.get("confidence", 0.5),
        }

    def loop(self, problem: str, max_cycles: int = 3) -> dict:
        """自主认知循环: 感知→推理→行动→反馈→进化 完整闭环

        max_cycles: 最大循环次数（每次循环都会自我质疑并修正）
        返回: {final_answer, actions, cycle_log, tokens_saved, insights_recorded}
        """
        t0 = time.time()
        cycle_log = []

        # Phase 1: 感知
        perception = self.perceive(problem)
        cycle_log.append({"phase": "perceive", "data": perception})
        if not perception["should_engage"]:
            return {"final_answer": "(SOMA 判断此问题无需深度介入)", "actions": {}, "cycle_log": cycle_log}

        # Phase 2: 推理
        mode = perception["suggested_mode"]
        if mode == "reason_deep":
            reasoning = self.reason_deep(problem)
        else:
            reasoning = self.reason(problem)
        cycle_log.append({"phase": "reason", "confidence": reasoning.get("confidence", 0)})

        # Phase 3: 行动
        actions = self.act(problem, reasoning.get("answer", ""))
        cycle_log.append({"phase": "act", "action_count": len(actions.get("actions", "").split("\n"))})

        # Phase 4: 反馈（记录结果到记忆）
        self.remember(
            f"自主推理: {problem[:100]} → 结论: {reasoning.get('answer','')[:200]}",
            importance=0.7,
            context={"type": "autonomous_loop", "complexity": perception["complexity"]},
        )
        cycle_log.append({"phase": "feedback", "recorded": True})

        # Phase 5: 进化（如有洞察则触发进化）
        evo_changes = []
        if reasoning.get("evolution_insights"):
            try:
                self._agent.reflect(f"loop_{int(time.time())}", "success")
                evo_changes = self._maybe_evolve()
            except Exception:
                pass
        cycle_log.append({"phase": "evolve", "changes": len(evo_changes)})

        elapsed_ms = (time.time() - t0) * 1000
        tokens_saved = reasoning.get("tokens_saved", 0) + 500  # 行动+反馈的估算

        return {
            "final_answer": reasoning.get("answer", ""),
            "actions": actions,
            "cycle_log": cycle_log,
            "tokens_saved": tokens_saved,
            "elapsed_ms": round(elapsed_ms, 1),
            "insights_recorded": len(reasoning.get("evolution_insights", [])),
        }

    # ── v2.0.1: 多Agent自主循环 ───────────────────────────────

    def loop_multi(self, problem: str, agent_ids: list = None) -> dict:
        """多Agent自主循环: 每个Agent独立运行完整loop，然后交叉验证+共识。

        agent_ids: 参与Agent列表，默认所有注册Agent（最多5个）。
        返回: {consensus, individual_results, cross_validation, actions}
        """
        t0 = time.time()
        orch = self._orchestrator
        if orch is None or orch.agent_count < 2:
            # 回退到单Agent loop
            result = self.loop(problem)
            return {"mode": "fallback_single", "result": result}

        ids = (agent_ids or list(orch._agents.keys()))[:5]
        individual = {}
        all_actions = []

        # Phase 1: 各Agent独立loop
        for aid in ids:
            agent = orch._agents.get(aid)
            if agent is None:
                continue
            # v2.0.18 修复：loop()/reason() 内部走的都是 self._agent，不临时换掉
            # 的话每个专家跑的都是同一个主 agent，"独立运行"名不副实。
            # （原先构造了一个 temp_soma 却从未使用，注释里的"agent 不同"也没做到。）
            prev_agent = self._agent
            try:
                self._agent = agent
                result = self.loop(problem)
                individual[aid] = {
                    "answer": result.get("final_answer", "")[:500],
                    "confidence": next(
                        (e.get("confidence", 0.5)
                         for e in result.get("cycle_log", [])
                         if e.get("phase") == "reason"),
                        0.5,
                    ),
                }
                if result.get("actions"):
                    all_actions.append(f"[{aid}]: {result['actions'].get('actions','')[:300]}")
            except Exception:
                individual[aid] = {"answer": f"[{aid} 分析失败]", "confidence": 0}
            finally:
                self._agent = prev_agent

        # Phase 2: 交叉验证
        try:
            cross = orch.cross_validate(problem, ids)
        except Exception:
            cross = {"final_conclusion": ""}

        # Phase 3: 共识进化
        try:
            orch.consensus_evolve(force=True)
        except Exception:
            pass

        # Phase 4: 综合结论
        combined = (
            f"多Agent自主循环完成。{len(individual)} 位专家参与:\n\n"
            + "\n".join(f"**[{aid}]** (置信度 {r['confidence']:.0%}): {r['answer'][:200]}"
                        for aid, r in individual.items())
            + f"\n\n**交叉验证结论**: {cross.get('final_conclusion', cross.get('final', ''))[:800]}"
        )

        elapsed_ms = (time.time() - t0) * 1000
        return {
            "mode": "multi_agent",
            "agents": len(individual),
            "consensus": combined[:3000],
            "individual_results": individual,
            "cross_validation": cross,
            "actions": "\n".join(all_actions)[:1500],
            "elapsed_ms": round(elapsed_ms, 1),
        }

    # ── v2.0.2: 自主行动执行 ──────────────────────────────────

    def execute(self, problem: str, actions: str = "", origin: str = "user") -> dict:
        """行动执行 — 把 loop() 生成的建议转化为实际执行步骤。

        执行内容: 1)记录决策到记忆 2)触发进化 3)生成下一步计划
        返回: {executed, next_steps, memory_recorded, evolution_triggered}

        origin: 这条执行计划的来源（"user" / "autonomous"）。自主循环自己产生的
        计划会带上 "autonomous" 标记，generate_goals() 据此跳过它们 —— 否则
        「自主目标 → 执行 → 写成新计划 → 又被当作新目标」会无限自我嵌套
        （v2.0.18 冒烟中实测到该问题）。
        """
        results = {"executed": [], "next_steps": "", "memory_recorded": 0, "evolution_triggered": False}

        # Step 1: 从actions中提取可执行项
        if not actions:
            action_result = self.act(problem)
            actions = action_result.get("actions", "")

        if actions:
            # 记录决策到记忆
            self.remember(
                f"执行计划: {problem[:100]} → {actions[:300]}",
                importance=0.8,
                context={"type": "execution_plan", "problem": problem[:100],
                         "origin": origin},
            )
            results["executed"].append("decision_logged")
            results["memory_recorded"] = 1

        # Step 2: 触发进化（如果有足够数据）
        try:
            changes = self._agent.evolver.evolve(force=True)
            if changes:
                results["evolution_triggered"] = True
                results["executed"].append(f"evolution({len(changes)} changes)")
        except Exception:
            pass

        # Step 3: 生成下一步建议
        if actions:
            next_prompt = f"已执行以下行动:\n{actions[:500]}\n\n基于此，下一步应该做什么？"
            try:
                next_result = self.reason(next_prompt)
                results["next_steps"] = next_result.get("answer", "")[:500]
            except Exception:
                results["next_steps"] = actions[:300]

        return results

    # ── v2.0.10: 全自主认知循环闭环 ────────────────────────────

    def run_autonomous(
        self, goal: str = None, max_rounds: int = 3,
        feedback_fn=None, max_goals: int = 1,
    ) -> dict:
        """全自主认知循环：迭代「感知→推理→行动→检查」直到完成、停滞或达上限。

        与 loop() 的区别：loop() 是单轮认知闭环；run_autonomous() 把多轮认知
        串成自主执行，每轮携带上轮结果继续推进目标，直到：
          - 外部反馈函数 feedback_fn 判定完成（最可靠）
          - 有 LLM key 时由 LLM 判断目标是否达成
          - 无 LLM 时由本地启发式识别"停滞"（连续两轮结论相同 / 本轮没有任何行动）
          - 否则跑满 max_rounds

        v2.0.18：goal 可以不给 —— 此时由 SOMA 自己生成一个目标（见 generate_goals()）；
        没有可用目标时直接返回 stop_reason="no_goal"，不空转。

        Args:
            goal: 要自主完成的目标/问题；None 表示由 SOMA 自己生成
            max_rounds: 最大迭代轮数（默认 3）
            feedback_fn: 可选外部完成判断函数 `fn(round_result, execution) -> bool`
            max_goals: goal 为 None 时，从生成的目标里最多挑几个（实际取优先级最高的一个）

        Returns:
            {goal, completed, stop_reason, rounds, round_count, final_answer, elapsed_ms}

            stop_reason ∈ completed / stalled / max_rounds / no_goal / error。
            注意 stalled 只表示"不再有进展"，**不等于完成** —— 无 LLM 时本地启发式
            没有能力判断目标是否真的达成，它只识别停滞，不会谎报完成。
        """
        t0 = time.time()

        if goal is None:
            generated = self.generate_goals(max_goals=max_goals)
            if not generated:
                return {
                    "goal": "", "completed": False, "stop_reason": "no_goal",
                    "rounds": [], "round_count": 0, "final_answer": "",
                    "elapsed_ms": round((time.time() - t0) * 1000, 1),
                }
            goal = generated[0]["goal"]

        rounds = []
        context = goal
        completed = False
        stop_reason = "max_rounds"
        consecutive_errors = 0
        prev_answer = ""

        for i in range(max_rounds):
            try:
                # 单轮认知闭环（感知→推理→行动→反馈→进化）
                round_result = self.loop(context, max_cycles=1)

                # 提取本轮行动文本并执行
                actions_obj = round_result.get("actions", {})
                actions_text = (
                    actions_obj.get("actions", "") if isinstance(actions_obj, dict) else ""
                )
                # origin="autonomous" 标记：这条计划是自主循环自己产的，
                # 不要再被 generate_goals() 当作新的待办目标收回去
                execution = self.execute(context, actions_text, origin="autonomous")
            except Exception:
                consecutive_errors += 1
                _log.warning(
                    "自主循环第 %d 轮失败（连续第 %d 次）",
                    i + 1, consecutive_errors, exc_info=True,
                )
                if consecutive_errors >= AUTONOMOUS_MAX_CONSECUTIVE_ERRORS:
                    stop_reason = "error"
                    break
                # 指数退避后重试本轮 —— 写锁竞争、LLM 抖动这类瞬时故障
                # 不该直接把整个目标判死
                time.sleep(min(
                    AUTONOMOUS_RETRY_BASE_SECONDS * (2 ** (consecutive_errors - 1)),
                    AUTONOMOUS_RETRY_MAX_SECONDS,
                ))
                continue
            consecutive_errors = 0

            verdict, verdict_reason = self._judge_goal(
                goal, round_result, execution, feedback_fn,
                prev_answer=prev_answer, actions_text=actions_text,
            )

            rounds.append({
                "round": i + 1,
                "perception": (round_result.get("cycle_log") or [{}])[0].get("data", {}),
                "answer": round_result.get("final_answer", ""),
                "actions": actions_text[:300],
                "execution": execution,
                "verdict": verdict,
                "verdict_reason": verdict_reason,
            })

            if verdict == "complete":
                completed, stop_reason = True, "completed"
                break
            if verdict == "stalled":
                stop_reason = "stalled"
                break

            # 未完成：携带本轮结果继续推进
            prev_answer = str(round_result.get("final_answer", ""))
            next_answer = prev_answer[:300]
            next_steps = str(execution.get("next_steps", ""))[:300]
            context = (
                f"{goal}\n\n"
                f"[第 {i + 1} 轮结果]\n"
                f"分析: {next_answer}\n"
                f"下一步: {next_steps}\n\n"
                f"请继续推进该目标。"
            )

        return {
            "goal": goal,
            "completed": completed,
            "stop_reason": stop_reason,
            "rounds": rounds,
            "round_count": len(rounds),
            "final_answer": rounds[-1]["answer"] if rounds else "",
            "elapsed_ms": round((time.time() - t0) * 1000, 1),
        }

    # ── v2.0.18: 自主目标来源 + 跨会话整合 + 后台常驻 ──────────

    def _goal_gen(self) -> GoalGenerator:
        if self._goal_generator is None:
            self._goal_generator = GoalGenerator(self)
        return self._goal_generator

    def _recent_goal_record(self) -> list:
        """近期已推进目标的原始记录（持久化在 episodic 的 KV 表里，跨进程有效）。"""
        try:
            raw = self._agent.memory.episodic.meta_get(META_RECENT_GOALS, []) or []
        except Exception:
            return []
        if not isinstance(raw, list):
            return []
        cutoff = time.time() - RECENT_GOAL_WINDOW_HOURS * 3600
        out = []
        for r in raw:
            if not isinstance(r, dict):
                continue
            try:
                at = float(r.get("at", 0))
            except (TypeError, ValueError):
                continue
            if at >= cutoff:
                out.append(r)
        return out

    def _recent_goal_keys(self) -> set:
        return {str(r["key"]) for r in self._recent_goal_record() if r.get("key")}

    def _mark_goal_advanced(self, key: str) -> None:
        """记录一个目标已推进，供下次生成时去重；失败不影响调用方。"""
        if not key:
            return
        try:
            store = self._agent.memory.episodic
        except Exception:
            return
        try:
            recent = self._recent_goal_record()
            recent.append({"key": key, "at": time.time()})
            store.meta_set(META_RECENT_GOALS, recent[-200:])
        except Exception:
            _log.debug("记录已推进目标失败", exc_info=True)

    def generate_goals(self, max_goals: int = 3, user_id: str = "") -> list:
        """自己找出值得推进的目标，按优先级排序（v2.0.18）。

        四个来源：过期的状态类记忆、尚未澄清的记忆冲突、跨会话遗留的执行计划、
        被埋没的重要记忆。每个目标都带 source 与 evidence，可追溯到具体记忆 ——
        不凭空造目标，产不出就返回空列表。

        近期（24 小时内）已推进过的目标不会重复产出，避免每次都推同一件事。
        返回 [{key, goal, source, priority, evidence}]。

        user_id (v2.0.18.2)：只从该用户的记忆里生成目标。**多租户部署必须传** ——
        留空是「系统级、不按用户过滤」的旧语义，会把不同用户的记忆混进同一个
        目标集（goal 文本里直接内嵌记忆原文），只适用于单租户部署。
        """
        try:
            goals = self._goal_gen().generate(
                max_goals=max_goals, recent_keys=self._recent_goal_keys(),
                user_id=user_id,
            )
        except Exception:
            _log.warning("自主目标生成失败", exc_info=True)
            return []
        return [g.to_dict() for g in goals]

    def run_self_directed(
        self, max_goals: int = 1, max_rounds: int = 2, user_id: str = "",
    ) -> dict:
        """自主跑一个自己生成的目标，并说明为什么选它（v2.0.18）。

        与 run_autonomous(goal=None) 的区别：这里把选中目标的来源与证据一并返回，
        调用方能知道"它为什么决定做这件事"，而不是只拿到一个结论。

        user_id (v2.0.18.2)：目标的来源范围。多租户部署必须传，否则会挑到
        别的用户的目标（见 generate_goals 的同名说明）。
        """
        goals = self.generate_goals(max_goals=max_goals, user_id=user_id)
        if not goals:
            return {
                "goal": "", "goal_key": "", "goal_source": "", "goal_evidence": [],
                "other_goals": [], "completed": False, "stop_reason": "no_goal",
                "rounds": [], "round_count": 0, "final_answer": "", "elapsed_ms": 0.0,
            }
        target = goals[0]
        result = self.run_autonomous(target["goal"], max_rounds=max_rounds)
        result["goal_source"] = target.get("source", "")
        result["goal_key"] = target.get("key", "")
        result["goal_evidence"] = target.get("evidence", [])
        result["other_goals"] = [g["goal"] for g in goals[1:]]
        self._mark_goal_advanced(target.get("key", ""))
        return result

    def integrate_session(self) -> dict:
        """跨会话整合（v2.0.18）：识别会话边界并收集上次会话留下的待办。

        返回 {is_new_session, gap_seconds, gap_human, pending_goals, pending_count,
        elapsed_ms}。

        本方法只读状态 + 记录会话边界，**不主动推进任何目标** —— 推进与否交给
        调用方（或后台常驻循环）决定，避免"调一次整合就顺带触发一堆 LLM 调用"。
        """
        t0 = time.time()
        store = None
        try:
            store = self._agent.memory.episodic
        except Exception:
            store = None

        last_end = None
        if store is not None:
            try:
                last_end = store.meta_get(META_LAST_SESSION_END)
            except Exception:
                last_end = None

        gap = None
        if isinstance(last_end, (int, float)):
            gap = max(0.0, time.time() - float(last_end))
        is_new_session = gap is None or gap > SESSION_GAP_SECONDS

        goals = self.generate_goals(max_goals=5)

        if store is not None:
            try:
                store.meta_set(META_LAST_SESSION_END, time.time())
            except Exception:
                pass

        return {
            "is_new_session": bool(is_new_session),
            "gap_seconds": round(gap, 1) if gap is not None else None,
            "gap_human": human_gap(gap),
            "pending_goals": goals,
            "pending_count": len(goals),
            "elapsed_ms": round((time.time() - t0) * 1000, 1),
        }

    def _background_runner(self) -> BackgroundRunner:
        if self._background is None:
            self._background = BackgroundRunner(self, self._config)
        return self._background

    def start_background(self) -> dict:
        """启动后台常驻自主循环。

        默认关闭：只有显式把 autonomous_background_enabled 配成 True 才允许启动，
        否则直接拒绝。开启后是一条 daemon 线程，任何时刻最多一个 tick 在跑，
        单次 tick 有墙钟上限，连续失败会自动停驻。
        """
        return self._background_runner().start()

    def stop_background(self, timeout: float = 10.0) -> dict:
        """停止后台常驻循环，等待当前 tick 结束（不强杀线程）。"""
        if self._background is None:
            return {"stopped": True, "was_running": False, "message": ""}
        return self._background.stop(timeout=timeout)

    def background_status(self) -> dict:
        """后台常驻循环的状态快照（未启动过也返回完整结构）。"""
        if self._background is None:
            return {
                "enabled": bool(getattr(
                    self._config, "autonomous_background_enabled", False)),
                "running": False,
                "tick_in_progress": False,
                "ticks": 0,
                "failures": 0,
                "consecutive_failures": 0,
                "interval": int(getattr(
                    self._config, "autonomous_background_interval", 3600)),
                "started_at": None,
                "stopped_reason": "",
                "last_result": None,
            }
        return self._background.status()

    def run_background_tick(self) -> dict:
        """同步跑一次后台 tick —— 不需要真开线程，便于验证与测试。"""
        return self._background_runner().run_once()

    def _judge_goal(
        self, goal: str, round_result: dict, execution: dict, feedback_fn=None,
        prev_answer: str = "", actions_text: str = "",
    ) -> tuple:
        """判断目标进展，返回 (verdict, reason)。

        verdict ∈ {"complete", "stalled", "continue"}：

        - complete：有确凿依据认为目标已达成（外部反馈函数 / LLM 判定）
        - stalled：本轮相对上轮没有实质进展（本地启发式，无 LLM 时的主要信号）
        - continue：仍在推进中

        优先级：外部反馈函数 → LLM → 本地启发式。

        本地启发式**只判停滞、不判完成** —— 无 LLM 时 SOMA 没有依据声称目标
        已达成，谎报完成比多跑几轮更糟。这一点在 v2.0.18 之前是缺失的：当时
        无 LLM 一律返回 False，唯一的表现就是闷头跑满轮数、外部看不出原因。
        """
        if feedback_fn is not None:
            try:
                if bool(feedback_fn(round_result, execution)):
                    return "complete", "外部反馈函数判定完成"
            except Exception:
                pass

        if self._has_llm():
            try:
                prompt = (
                    f"目标: {goal}\n\n"
                    f"本轮分析: {str(round_result.get('final_answer', ''))[:400]}\n\n"
                    f"判断目标是否已达成？只回答 true 或 false。"
                )
                resp = self._agent._call_llm(prompt, "")[:20].strip().lower()
                if "true" in resp:
                    return "complete", "LLM 判定目标已达成"
                return "continue", "LLM 判定目标未达成"
            except Exception:
                pass

        cur = str(round_result.get("final_answer", "")).strip()
        if prev_answer and cur and cur == prev_answer.strip():
            return "stalled", "本轮结论与上一轮完全相同，没有新进展"
        executed = execution.get("executed") if isinstance(execution, dict) else None
        if (
            not (actions_text or "").strip()
            and not executed
            and not ((execution or {}).get("next_steps") or "").strip()
        ):
            return "stalled", "本轮没有产生任何行动或后续步骤"
        return "continue", "仍在推进中"

    def _check_goal_complete(
        self, goal: str, round_result: dict, execution: dict,
        feedback_fn=None,
    ) -> bool:
        """判断目标是否达成（bool 视图）。

        优先级：外部反馈函数 → LLM（有 key）→ 本地兜底（返回 False，跑满轮数）。
        需要区分"完成 / 停滞 / 继续"三态时用 _judge_goal —— 停滞不算完成。
        """
        verdict, _ = self._judge_goal(
            goal, round_result, execution, feedback_fn,
        )
        return verdict == "complete"

    def _has_llm(self) -> bool:
        """当前是否配置了 LLM（有 key 或非 mock 模型）。"""
        return bool(
            getattr(self._config, "llm_api_key", "")
            or getattr(self._config, "llm_model", "mock") != "mock"
        )

    # ── v2.0.18: 进化触发（取代散落的硬编码 % 5 / % 10 / % 30） ──

    def _evolution_sample_count(self) -> int:
        """当前规律样本总数（成功+失败），读不到时返回 -1。

        与 MetaEvolver.evolve() 内部用的 total_samples 同源，取自内存里的
        _law_stats，不额外查库。
        """
        stats = getattr(getattr(self._agent, "evolver", None), "_law_stats", None)
        if not isinstance(stats, dict):
            return -1
        try:
            return sum(
                int(s.get("successes", 0)) + int(s.get("failures", 0))
                for s in stats.values() if isinstance(s, dict)
            )
        except Exception:
            return -1

    def _is_deep_evolution_due(self) -> bool:
        """是否到深度进化节拍（默认每 interval×deep_multiple 次会话）。"""
        interval = max(1, int(getattr(self._config, "evolution_interval", 5)))
        multiple = max(1, int(getattr(self._config, "evolution_deep_multiple", 6)))
        return self._session_count > 0 and self._session_count % (interval * multiple) == 0

    def _maybe_evolve(self, force: bool = False) -> list:
        """按配置节拍触发一次进化，未到节拍或无需进化时返回空列表。

        除了次数节拍，还有一道"脏标记"：自上次进化以来规律样本数没有增长时
        直接跳过 —— 没有新数据可学，跑一遍进化只是空转。所以把
        evolution_interval 调小只会让它更及时，不会带来额外开销。
        """
        interval = max(1, int(getattr(self._config, "evolution_interval", 5)))
        if self._session_count <= 0 or self._session_count % interval != 0:
            return []

        samples = self._evolution_sample_count()
        if (
            not force
            and samples >= 0
            and self._last_evolve_samples is not None
            and samples == self._last_evolve_samples
        ):
            return []

        try:
            changes = self._agent.evolver.evolve(force=force)
        except Exception:
            _log.warning("进化执行失败（不影响本轮）", exc_info=True)
            return []
        self._last_evolve_samples = samples
        return changes or []

    def _mock_respond(self, problem, foci=None, activated=None):
        """无 LLM 时的 mock 响应"""
        if foci is None:
            foci = self._agent.decompose(problem)
        if activated is None:
            activated = self._agent.hub.activate(foci)
        parts = [f"## 问题拆解\n从 {len(foci)} 个维度分析「{problem}」："]
        for f in foci:
            parts.append(f"- **{f.law_id}**（权重 {f.weight:.2f}）：{f.dimension[:120]}")
        if activated:
            parts.append(f"\n## 激活的相关记忆（{len(activated)} 条）")
            for am in activated[:5]:
                snippet = am.memory.content[:100]
                parts.append(f"- [{am.source}] {snippet}...")
        parts.append(f"\n> 未配置 LLM，此为 Mock 模式。设置 llm 参数连接真实模型。")
        return "\n".join(parts)

    def remember(
        self, content: str, context: dict = None, importance: float = 0.5,
        user_id: str = "", session_id: str = "",
        auto_capture: bool | None = None, nature: str = "event",
    ) -> str:
        """存储一条情节记忆。auto_capture=None 时尊重全局配置。

        v2.0.15: nature 门面透传（此前仅 agent 层支持，接入方走门面会 TypeError）。
        nature: state 状态类(失眠/情绪/健康, 时效强) / fact 事实技能类(长期有效)
        / event 一般事件(默认)。知识与技能类内容建议显式传 nature="fact"。
        """
        memory_id = self._agent.remember(content, context, importance,
                                         user_id=user_id, session_id=session_id,
                                         nature=nature)

        # v0.10.0: 自动捕获触发
        should_capture = auto_capture
        if should_capture is None:
            should_capture = self._config.scene_extraction_enabled
        if should_capture:
            self._ensure_layered_memory()
            if self._capture_pipeline:
                self._capture_pipeline.on_new_memory(user_id)

        return memory_id

    def remember_code(
        self, code: str, file_path: str = "", language: str = "python",
        importance: float = 0.8, user_id: str = "", session_id: str = "",
        nature: str = "fact",
    ) -> dict:
        """存储代码记忆 — AST 自动解析结构 + 生成语义三元组。

        v2.0.15: nature 默认 fact —— 代码/技能属长期有效能力，不随时间过时。

        示例::

            code = '''
            def fibonacci(n: int) -> int:
                if n <= 1:
                    return n
                return fibonacci(n-1) + fibonacci(n-2)
            '''
            result = soma.remember_code(code, file_path="math_utils.py")
            # → 存储结构化记忆 + 自动生成语义三元组

        返回: {"memory_id": ..., "structure": CodeStructure, "triples_count": int}
        """
        analyzer = CodeAnalyzer()
        enriched = analyzer.analyze_and_enrich(code, language)
        structure_data = enriched["structured_data"]
        triples = enriched["semantic_triples"]
        summary = enriched["summary"]

        # 构建上下文
        ctx = {
            "content_type": "code",
            "language": language,
            "file_path": file_path,
            "code_summary": summary,
        }

        # 存储情节记忆（带结构化数据）
        memory_id = self._agent.remember(
            f"[代码] {file_path or 'snippet'}: {summary}\n{code[:500]}",
            ctx,
            importance,
            user_id=user_id,
            session_id=session_id,
            nature=nature,
        )

        # 自动注入语义三元组（调用关系、继承关系）
        for subj, pred, obj in triples:
            try:
                self._agent.remember_semantic(
                    subject=subj,
                    predicate=pred,
                    object_=obj,
                    confidence=min(0.9, 0.5 + 0.1 * len(triples)),
                    namespace=f"code:{file_path}" if file_path else "code:snippet",
                )
            except Exception:
                pass

        return {
            "memory_id": memory_id,
            "structure": structure_data,
            "triples_count": len(triples),
        }

    def remember_semantic(
        self, subject: str, predicate: str, object_: str, confidence: float = 1.0,
        namespace: str = "",
    ) -> None:
        self._agent.remember_semantic(subject, predicate, object_, confidence,
                                      namespace=namespace)

    # ── v2.0.10: 多模态记忆 ────────────────────────────────────

    def remember_image(
        self, image_path: str = "", description: str = "",
        importance: float = 0.6, user_id: str = "", use_ocr: bool = True,
        nature: str = "event",
    ) -> dict:
        """存储图片记忆 — 图片引用 + 结构化描述（可选 OCR 增强）。

        示例::

            result = soma.remember_image(
                image_path="diagram.png",
                description="系统架构图：三个微服务通过消息队列解耦",
            )
            # → 存为文本记忆（含图片路径引用 + OCR 文字）

        返回: {"memory_id": ..., "meta": {...}}
        """
        from soma.multimodal import ImageMemory

        img = ImageMemory(image_path=image_path, description=description,
                          use_ocr=use_ocr)
        meta = img.analyze()
        content = img.to_memory_content(meta)

        ctx = {
            "content_type": "image",
            "image_path": image_path,
            "description": description,
            "meta": meta,
        }
        memory_id = self._agent.remember(content, ctx, importance,
                                         user_id=user_id, nature=nature)
        return {"memory_id": memory_id, "meta": meta}

    def remember_table(
        self, data: list = None, title: str = "",
        markdown_table: str = "", csv_text: str = "",
        importance: float = 0.6, user_id: str = "", nature: str = "event",
    ) -> dict:
        """存储表格记忆 — 结构化数据提取要点。

        支持三种输入：
          - data: List[Dict]，直接结构化数据
          - markdown_table: markdown 表格字符串（自动解析）
          - csv_text: CSV 字符串（自动解析）

        示例::

            result = soma.remember_table(
                data=[{"季度": "Q1", "营收": "100万"}, {"季度": "Q2", "营收": "150万"}],
                title="季度营收表",
            )

        返回: {"memory_id": ..., "meta": {...}}
        """
        from soma.multimodal import TableMemory

        table = TableMemory(
            title=title, data=data or [],
            markdown_table=markdown_table, csv_text=csv_text,
        )
        meta = table.analyze()
        content = table.to_memory_content(meta)

        ctx = {
            "content_type": "table",
            "title": title,
            "meta": meta,
        }
        memory_id = self._agent.remember(content, ctx, importance,
                                         user_id=user_id, nature=nature)
        return {"memory_id": memory_id, "meta": meta}

    def query_memory(self, query: str, top_k: int = 5, user_id: str = "",
                     agent_id: str = "", group_id: str = "",
                     max_age_days: Optional[float] = None) -> list:
        """直接查询记忆（绕过框架拆解）。

        v2.0.15: 门面透传 max_age_days（此前仅 agent 层支持，接入方走门面会
        TypeError —— 即 DSH 反馈的「四层透传少一层」缺口）。
        max_age_days: 时间窗口硬截断（如 30 = 只要 30 天内）；
        返回项含 timestamp / age_days / nature / is_stale。
        """
        return self._agent.query_memory(
            query, top_k, user_id=user_id, agent_id=agent_id, group_id=group_id,
            max_age_days=max_age_days)

    def reclassify_nature(
        self, classifier=None, dry_run: bool = True, backup_dir: str = None,
        user_id: str = "", only_nature: str = "event", limit: int = None,
    ) -> dict:
        """批量重分类存量记忆的业务性质 nature（v2.0.15）。

        把已有记忆按规则回填 state/fact/event —— 迁移期一次性动作，之后
        remember(nature=) 正常写入即可。

        **默认 dry_run=True 只预览不改库**；落盘会自动备份，可用
        rollback_nature() 按备份回滚。

        Args:
            classifier: 自定义 NatureClassifier（默认内置规则）
            dry_run: True 只统计不改
            backup_dir: 备份目录（默认记忆库同目录 nature_backups/）
            user_id: 只处理某用户
            only_nature: 只重分类该历史性质（默认 'event'，不动已分类的）
            limit: 最多处理条数

        Returns:
            {dry_run, scanned, changed, unchanged, by_nature, backup_path, samples}
        """
        return self._agent.reclassify_nature(
            classifier=classifier, dry_run=dry_run, backup_dir=backup_dir,
            user_id=user_id, only_nature=only_nature, limit=limit)

    def rollback_nature(self, backup_path: str) -> dict:
        """按 reclassify_nature 的备份文件回滚一次重分类（v2.0.15）"""
        return self._agent.rollback_nature(backup_path)

    def repair_context(self, dry_run: bool = True, backup_dir: str = None,
                       user_id: str = "", limit: int = None) -> dict:
        """扫描并修复 context 非 JSON 对象的存量脏数据（v2.0.17）。

        背景：context 字段可能被写入非 JSON 对象的值（调用方误传字符串），
        使任何全库检索在 ``mem.context["_vector_score"] = score`` 处抛 TypeError
        崩溃 —— 一条脏数据足以毁掉整次全库查询。2.0.17 起读写都已防御，
        本方法负责把**存量**脏数据扫出来并规范化。

        修复方式：原值收进 ``{"_raw": <原值>, "_repaired_at": ...}``，不丢数据；
        修复前后读出的内容一致，只是库里不再有会破坏 SQL/FTS 假设的形状。

        **默认 dry_run=True 只预览不改库**；落盘前自动备份，可用
        rollback_context() 按备份回滚。

        Args:
            dry_run: True 只统计不改（默认）
            backup_dir: 备份目录（默认记忆库同目录 context_backups/）
            user_id: 只处理某用户（空 = 全部）
            limit: 最多处理条数

        Returns:
            {dry_run, scanned, dirty, repaired, by_table, samples, backup_path}
        """
        return self._agent.repair_context(
            dry_run=dry_run, backup_dir=backup_dir, user_id=user_id, limit=limit)

    def rollback_context(self, backup_path: str) -> dict:
        """按 repair_context 的备份文件回滚一次修复（v2.0.17）"""
        return self._agent.rollback_context(backup_path)

    def reload(self) -> dict:
        """重载记忆索引，使外部进程的写入对本实例可见（v2.0.15）。

        长驻服务场景：CLI / 另一个 Agent 往同一个记忆库写了数据，SQLite 查询
        能立刻看到，但内存里的 faiss 索引还是旧的，语义检索会漏 —— 调本方法刷新。

        返回 {"reloaded_vectors": N, "total": M}。
        """
        return self._agent.reload()

    def prune_stale_vectors(self, background: bool = True) -> dict:
        """清理语义索引里「记忆已删除但向量仍在」的残留（v2.0.18）。

        faiss 无法精确删除向量，记忆被删除后索引里的残条会一直占着 top_k 名额，
        并让删除后的下一次搜索触发同步全量重建。本方法只清理这部分：从内存索引
        取出仍然有效的向量重建，**不重新编码**；默认后台执行，不阻塞调用方。

        返回 {"pruned": 移除条数, "remaining": 剩余条数,
              "rebuilt": 是否已重建, "scheduled": 是否已调度后台重建}。
        查询当前残留量用 count_stale_vectors()。
        """
        return self._agent.memory.episodic.prune_stale_vectors(
            background=background)

    def count_stale_vectors(self) -> int:
        """语义索引里过期（对应记忆已被删除）的向量条数（v2.0.18）。"""
        return self._agent.memory.episodic.count_stale_vectors()

    def decompose(self, problem: str) -> list:
        return self._agent.decompose(problem)

    def reflect(self, task_id: str, outcome: str) -> None:
        self._agent.reflect(task_id, outcome)

    def evolve(self) -> list:
        """执行自动进化（权重调整 + 记忆合并 + 遗忘清理）"""
        changes = self._agent.evolver.evolve()

        # v0.7.0: 记忆合并 — 相似记忆自动归并
        try:
            merged = self._agent.memory.episodic.consolidate(max_merges=10)
            if merged:
                changes.append({
                    "type": "memory_consolidation",
                    "merged_count": merged,
                })
        except Exception:
            pass

        # v0.7.0: 主动遗忘 — 低价值记忆归档
        try:
            forgotten = self._agent.memory.episodic.forget(max_archive=50)
            if any(forgotten.values()):
                changes.append({
                    "type": "memory_forgetting",
                    "details": forgotten,
                })
        except Exception:
            pass

        return changes

    def get_weights(self) -> dict:
        return self._agent.evolver.get_weights()

    def adjust_weight(self, law_id: str, new_weight: float) -> bool:
        return self._agent.evolver.adjust_weight(law_id, new_weight)

    def discover_laws(self) -> dict | None:
        """尝试从高关联记忆中自动发现新的思维规律。

        返回候选规律字典（供人工审核），或 None 表示当前无条件生成。
        建议每 50 次会话调用一次。需要 LLM 时设置 llm 参数。
        """
        return self._agent.evolver.discover_laws(
            embedder=self._agent.embedder,
            llm_model=self._config.llm_model if self._config.llm_model != "mock" else None,
        )

    def approve_law(self, candidate: dict) -> bool:
        """审批通过一条候选规律，加入思维框架。返回是否成功。"""
        return self._agent.evolver.approve_law(
            candidate, embedder=self._agent.embedder,
        )

    def get_thought_templates(self) -> list:
        """获取已挖掘的思维模板（v0.6.0）"""
        return self._agent.evolver.get_thought_templates()

    # ── v0.10.0: 记忆分层方法 ──────────────────────────────────

    def _ensure_layered_memory(self):
        """延迟初始化分层记忆组件（SceneStore + ProfileStore + CapturePipeline）"""
        if self._scene_store is None:
            persist = self._config.episodic_persist_dir
            self._scene_store = SceneStore(persist)
            self._profile_store = ProfileStore(persist)
            cap_cfg = CaptureConfig(
                scene_warmup=self._config.scene_extraction_warmup,
                scene_min_interval=self._config.scene_extraction_min_interval,
                scene_max_interval=self._config.scene_extraction_max_interval,
                scene_idle_timeout=self._config.scene_extraction_idle_timeout,
                profile_scene_interval=self._config.profile_extraction_scene_interval,
                enable_warmup=self._config.scene_extraction_warmup_enabled,
            )
            from soma.memory.capture import SceneExtractor, ProfileExtractor
            self._capture_pipeline = CapturePipeline(
                self._scene_store, self._profile_store, cap_cfg,
                scene_extractor=SceneExtractor(
                    llm_call=lambda prompt: self._agent._call_llm(prompt, "")
                ) if self._config.llm_model != "mock" else None,
                profile_extractor=ProfileExtractor(
                    llm_call=lambda prompt: self._agent._call_llm(prompt, "")
                ) if self._config.llm_model != "mock" else None,
            )
            if not self._config.scene_extraction_enabled:
                self._capture_pipeline.disable()

            # 注入分层存储到 MemoryCore，参与检索融合
            self._agent.memory.attach_stores(
                scene_store=self._scene_store,
                profile_store=self._profile_store,
            )

    def enable_layered_memory(
        self, scene_warmup: int = 5, profile_interval: int = 10,
    ) -> None:
        """启用记忆分层（Scene + Profile）。调用后每次 remember() 可触发自动捕获。"""
        self._ensure_layered_memory()
        self._config.scene_extraction_enabled = True
        self._config.profile_extraction_enabled = True
        self._config.scene_extraction_warmup = scene_warmup
        self._config.profile_extraction_scene_interval = profile_interval
        if self._capture_pipeline:
            self._capture_pipeline.enable()

    def disable_layered_memory(self) -> None:
        """禁用记忆分层，停止自动捕获。"""
        self._config.scene_extraction_enabled = False
        self._config.profile_extraction_enabled = False
        if self._capture_pipeline:
            self._capture_pipeline.disable()

    def get_scenes(
        self, user_id: str = "", top_k: int = 10,
    ) -> List[Dict]:
        """获取用户的场景块列表。"""
        self._ensure_layered_memory()
        return self._scene_store.get_scenes(user_id=user_id, top_k=top_k)

    def get_scene_markdown(self, scene_id: str) -> str:
        """获取指定场景的白盒 Markdown 输出。"""
        self._ensure_layered_memory()
        return self._scene_store.generate_markdown(scene_id)

    def get_profile(self, user_id: str = "") -> List[Dict]:
        """获取用户画像条目列表。"""
        self._ensure_layered_memory()
        return self._profile_store.get_entries(user_id=user_id)

    def get_profile_markdown(self, user_id: str = "") -> str:
        """获取用户画像的白盒 Markdown 输出。"""
        self._ensure_layered_memory()
        return self._profile_store.generate_markdown(user_id)

    def capture_scenes(
        self, user_id: str = "", force: bool = False,
        memories: Optional[List[Dict]] = None,
    ) -> int:
        """触发场景提取。force=True 跳过间隔限制。
        可传入 memories 列表直接提取，不传则从 episodic store 中取。
        返回新增场景数。
        """
        self._ensure_layered_memory()
        if memories:
            return self._capture_pipeline.capture_from_memories(
                memories, user_id=user_id, force=force,
            )
        return self._capture_pipeline.capture_scenes(user_id, force=force)

    def update_profile(
        self, user_id: str = "", force: bool = False,
    ) -> int:
        """触发用户画像更新。返回新增/更新条目数。"""
        self._ensure_layered_memory()
        return self._capture_pipeline.update_profile(user_id, force=force)

    def get_layered_stats(self) -> Dict[str, Any]:
        """返回分层记忆统计。"""
        self._ensure_layered_memory()
        base = self.stats
        base["scenes"] = self._scene_store.count()
        base["profile_entries"] = self._profile_store.count()
        return base

    # ── v0.9.2: 多Agent编排便利方法 ──────────────────────────

    def register_expert(
        self, agent_id: str, expertise: List[str],
        description: str = "", group_id: str = "",
    ) -> str:
        """注册一个专家Agent到编排器。

        仅当 orchestration_mode="multi" 时有效。
        返回 agent_id。
        """
        if self._orchestrator is None:
            raise RuntimeError(
                "register_expert() 需要在 orchestration_mode='multi' 模式下使用。"
                ' 请使用 SOMA(orchestration_mode="multi") 初始化。'
            )
        ids = self._orchestrator.create_agents([{
            "agent_id": agent_id,
            "expertise": expertise,
            "description": description,
            "group_id": group_id,
        }])
        return ids[0]

    def list_experts(self) -> list:
        """列出所有已注册的专家Agent信息。"""
        if self._orchestrator is None:
            return []
        infos = self._orchestrator.registry.list_agents()
        return [
            {
                "agent_id": i.agent_id,
                "expertise": i.expertise,
                "description": i.description,
                "session_count": i.session_count,
                "success_rate": i.success_rate,
            }
            for i in infos
        ]

    def solve_multi(
        self, problem: str, strategy: str = "voting",
    ) -> OrchestrationResult:
        """显式调用多Agent求解管道，返回完整 OrchestrationResult。

        仅当 orchestration_mode="multi" 时有效。
        """
        if self._orchestrator is None:
            raise RuntimeError(
                "solve_multi() 需要在 orchestration_mode='multi' 模式下使用。"
            )
        return self._orchestrator.solve(problem, strategy=strategy)

    # ── v2.0.19: 记忆管理与真实用量（接入方正式入口） ────────

    @property
    def memories(self) -> MemoryApi:
        """记忆管理的单一出口（列举 / 读取 / 编辑 / 删除 / 恢复 / 导出）。

        接入方请用它，不要再穿透 soma._agent.memory.episodic._conn 拼裸 SQL ——
        那条路没有作用域（多用户会互相看到），且把表结构变成了对外契约。

        示例::

            page = soma.memories.list(user_id="u1", limit=20)
            for m in page["items"]:
                print(m["created_at"], m["nature"], m["content"][:40])
            soma.memories.update(m_id, content="记错了，应该是……")
            soma.memories.delete(m_id)          # 归档，可 restore 反悔
        """
        if not hasattr(self, "_memory_api"):
            self._memory_api = MemoryApi(
                self._agent.memory.episodic, agent=self._agent)
        return self._memory_api

    @property
    def usage(self):
        """真实 token 用量的记录器（可注册回调 / 清零）。

        上报计费系统就挂回调：soma.usage.on_usage(lambda u: bill(u.to_dict()))
        回调在锁外执行，慢回调不会拖住并发线程。
        """
        return self._agent.usage

    @property
    def token_usage(self) -> dict:
        """累计真实 token 用量快照（与 stats 同为 property）。

        {"calls", "prompt_tokens", "completion_tokens", "total_tokens",
         "estimated_calls", "by_model": {model: {...}}}

        estimated_calls > 0 表示有若干条不是 provider 给的、而是本地按字符估的
        —— 那部分不能拿去计费。
        """
        return self._agent.usage.snapshot()

    def recent_usage(self, n: int = 20) -> list:
        """最近 n 次 LLM 调用的明细（最新在前），含 model / user_id / estimated。"""
        return self._agent.usage.recent(n)

    # ── 记忆健康管理 ──────────────────────────────────────────

    @property
    def memory_manager(self) -> MemoryManager:
        """惰性初始化记忆管理器"""
        if not hasattr(self, "_memory_mgr"):
            self._memory_mgr = MemoryManager(
                episodic_store=self._agent.memory.episodic,
                semantic_store=self._agent.memory.semantic,
                skill_store=self._agent.memory.skill,
            )
        return self._memory_mgr

    def memory_health(self) -> dict:
        """返回记忆系统健康报告。

        包含: 各库计数 / 衰减统计 / 冲突数量 / 可巩固组数
        """
        mgr = self.memory_manager
        report = mgr.health_report()

        # 补充巩固候选信息
        candidates = mgr.find_consolidation_candidates()
        report["consolidation_candidates"] = len(candidates)
        report["largest_group"] = len(candidates[0][1]) if candidates else 0

        return report

    def memory_maintenance(
        self, prune: bool = True, consolidate: bool = True, detect: bool = True,
    ) -> MaintenanceReport:
        """运行一轮主动记忆维护。

        维护步骤: 修剪过期 → 情节合并为语义 → 冲突检测

        建议每 N 次 evolution 或每天调用一次。
        """
        return self.memory_manager.run_maintenance(
            prune=prune, consolidate=consolidate, detect=detect,
        )

    # ── 外部知识学习 ──────────────────────────────────────────

    @property
    def knowledge_gate(self) -> KnowledgeGate:
        """惰性初始化知识门控（v2.0.9: 透传 config 的严格度/质量阈值）"""
        if not hasattr(self, "_knowledge_gate"):
            self._knowledge_gate = KnowledgeGate(
                self._agent,
                strictness=getattr(self._config, "knowledge_gate_strictness", "balanced"),
                min_quality=getattr(self._config, "knowledge_gate_min_quality", 0.35),
                min_corroboration=getattr(
                    self._config, "knowledge_gate_min_corroboration", 0.0
                ),
            )
        return self._knowledge_gate

    def learn_from_external(
        self, contents, problem_context: str = "", source_name: str = "external",
        strictness: str = "",
    ) -> GateResult:
        """从外部知识学习：五层质量过滤后自动存入记忆库。

        管道: 来源过滤 → 相关性过滤 → SOMA推理消化 → 内容质量 → 风格对齐
              → 一致性校验 → 事实印证 → 分级存储

        示例::

            # 从 Web 搜索结果学习
            result = soma.learn_from_external(
                ["外部文本1", "外部文本2"],
                problem_context="零熵智库的认知架构设计",
                source_name="web",
            )
            print(f"接受: {len(result.accepted)}, 隔离: {len(result.quarantined)}")

        Args:
            contents: str | List[str] — 外部文本
            problem_context: 当前分析主题，用于相关性判断
            source_name: 来源标识 (web/document/rag)
            strictness: v2.0.9 可选覆盖严格度档位（strict/balanced/permissive），
                        空则用 config 默认

        Returns:
            GateResult 含 accepted/quarantined/rejected 分类
        """
        if isinstance(contents, str):
            contents = [contents]
        gate = self.knowledge_gate
        # v2.0.9: strictness 非空时临时覆盖
        if strictness:
            gate._strictness = strictness
            gate._apply_strictness()
        return gate.ingest(contents, problem_context, source_name)

    @property
    def graph_builder(self) -> AutoGraphBuilder:
        """惰性初始化图谱构建器"""
        if not hasattr(self, "_graph_builder"):
            self._graph_builder = AutoGraphBuilder(
                episodic_store=self._agent.memory.episodic,
                semantic_store=self._agent.memory.semantic,
            )
        return self._graph_builder

    def build_knowledge_graph(self, max_memories: int = 200) -> GraphBuildReport:
        """运行一轮自动知识图谱构建。

        三路构建:
          1. 中文模式匹配: 因果/归属/依赖/相似关系 → 语义三元组
          2. 会话共现: 同会话记忆 → 关联边
          3. 关键词重叠: Jaccard > 0.3 → 相似边

        建议每次 memory_maintenance 时自动调用。
        """
        return self.graph_builder.build(max_memories=max_memories)

    # ── 生命周期 ──────────────────────────────────────────────

    def close(self) -> None:
        """关闭底层 agent 及所有子组件连接"""
        # v2.0.18: 先停后台常驻循环 —— 否则它会在线程里继续读已经关掉的库
        if self._background is not None:
            try:
                self._background.stop(timeout=10.0)
            except Exception:
                _log.warning("停止后台自主循环失败", exc_info=True)
        self._agent.close()
        if self._capture_pipeline is not None:
            self._capture_pipeline.close()
        if self._scene_store is not None:
            self._scene_store.close()
        if self._profile_store is not None:
            self._profile_store.close()

    def __enter__(self) -> "SOMA":
        return self

    def __exit__(self, *args) -> None:
        self.close()

    @property
    def stats(self) -> dict:
        base = self._agent.memory.stats()
        if self._scene_store is not None:
            base.setdefault("scenes", self._scene_store.count())
        if self._profile_store is not None:
            base.setdefault("profile_entries", self._profile_store.count())
        if self._capture_pipeline is not None:
            base["capture_state"] = self._capture_pipeline.get_state()
        return base
