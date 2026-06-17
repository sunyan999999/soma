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
    __version__ = "1.1.7"

from soma.config import SOMAConfig, load_config
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
    "MemoryUnit",
    "Focus",
    "ActivatedMemory",
    "OrchestrationResult",
    "CapturePipeline",
    "CaptureConfig",
]

_log = logging.getLogger("soma")


class SOMA:
    """SOMA 顶层门面 — v1.1.7

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
            orchestration_mode=orchestration_mode,
            orchestration_top_k=orchestration_top_k,
            orchestration_consensus=orchestration_consensus,
            scene_extraction_enabled=scene_extraction_enabled,
            profile_extraction_enabled=profile_extraction_enabled,
            enable_zhongdao=enable_zhongdao,
            zhongdao_threshold_ratio=zhongdao_threshold_ratio,
            zhongdao_penalty_factor=zhongdao_penalty_factor,
            zhongdao_boost_factor=zhongdao_boost_factor,
            zhongdao_min_samples=zhongdao_min_samples,
        )
        self._agent = SOMA_Agent(self._config, agent_id=agent_id or "soma", group_id=group_id)
        self._session_count = 0

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

    def respond(self, problem: str, user_id: str = "") -> str:
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
        if self._session_count > 0 and self._session_count % 5 == 0:
            self._agent.evolver.evolve()
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

        mock_fallback = False

        try:
            answer = self._agent._call_llm(
                self._agent._build_prompt(problem, foci, activated),
                user_id,
            )
        except Exception:
            _log.error(
                "SOMA.chat() LLM调用失败，回退到mock响应:\n%s",
                traceback.format_exc(),
            )
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
        if self._session_count > 0 and self._session_count % 5 == 0:
            self._agent.evolver.evolve()

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
        }

        self._agent.record_session(problem, answer, foci, activated)
        return result

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
        auto_capture: bool | None = None,
    ) -> str:
        """存储一条情节记忆。auto_capture=None 时尊重全局配置。"""
        memory_id = self._agent.remember(content, context, importance,
                                         user_id=user_id, session_id=session_id)

        # v0.10.0: 自动捕获触发
        should_capture = auto_capture
        if should_capture is None:
            should_capture = self._config.scene_extraction_enabled
        if should_capture:
            self._ensure_layered_memory()
            if self._capture_pipeline:
                self._capture_pipeline.on_new_memory(user_id)

        return memory_id

    def remember_semantic(
        self, subject: str, predicate: str, object_: str, confidence: float = 1.0,
        namespace: str = "",
    ) -> None:
        self._agent.remember_semantic(subject, predicate, object_, confidence,
                                      namespace=namespace)

    def query_memory(self, query: str, top_k: int = 5, user_id: str = "") -> list:
        return self._agent.query_memory(query, top_k, user_id=user_id)

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

    # ── 生命周期 ──────────────────────────────────────────────

    def close(self) -> None:
        """关闭底层 agent 及所有子组件连接"""
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
