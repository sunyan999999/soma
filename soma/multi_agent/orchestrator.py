"""多Agent编排器 — v1.1.2

SOMAOrchestrator 将已有的 Registry、Router、ConsensusProtocol、DistributedEvolver
串联为完整的多Agent求解管道。v1.1.0 新增并行分发与分布式权重演化，v1.1.1 补齐路由与Agent映射。
不修改 multi_agent/ 下任何现有文件，纯连线层。
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from soma.config import SOMAConfig
from soma.multi_agent.registry import AgentRegistry
from soma.multi_agent.router import ExpertRouter
from soma.multi_agent.consensus import ConsensusProtocol, AgentOpinion, ConsensusResult
from soma.multi_agent.evolve import DistributedEvolver

_log = logging.getLogger("soma.multi_agent")


@dataclass
class OrchestrationResult:
    """多Agent编排求解结果"""
    question: str
    answer: str                              # 最终共识回答
    agents_involved: List[str] = field(default_factory=list)
    routing_strategy: str = ""               # "l1"/"l2"/"fallback"/"error"
    consensus: Optional[ConsensusResult] = None  # 共识详情


class SOMAOrchestrator:
    """多Agent编排器 — 管理生命周期、路由、共识形成

    使用示例::

        from soma.multi_agent import SOMAOrchestrator

        orch = SOMAOrchestrator(config)
        orch.create_agents([
            {"agent_id": "analyst", "expertise": ["商业分析", "战略"],
             "description": "商业战略分析师"},
            {"agent_id": "engineer", "expertise": ["技术", "架构"],
             "description": "技术架构师"},
        ])
        result = orch.solve("如何平衡技术投入与业务增长？")
        print(result.answer)
    """

    def __init__(self, config: SOMAConfig):
        self.config = config
        self.registry = AgentRegistry()
        self.router = ExpertRouter(registry=self.registry)
        self.consensus = ConsensusProtocol()
        self.default_agent: Any = None
        self._agents: Dict[str, Any] = {}  # agent_id → agent 实例

        # v1.1.0: 分布式权重演化
        self._evolver: Optional[DistributedEvolver] = None
        self._solve_count: int = 0
        self._agent_session_counts: Dict[str, int] = {}
        if config.orchestration_evolution_enabled:
            persist_dir = config.episodic_persist_dir / "evolution"
            persist_dir.mkdir(parents=True, exist_ok=True)
            self._evolver = DistributedEvolver(
                persist_dir=persist_dir,
                merge_strategy="weighted_by_success",
            )

    # ── Agent 生命周期管理 ──────────────────────────────────────

    def create_agents(self, specs: List[Dict[str, Any]]) -> List[str]:
        """按规格批量创建 SOMA_Agent 实例并注册到 registry。

        每个 spec 可包含:
        - agent_id (必填): Agent 标识
        - expertise (必填): 专长领域列表
        - description: 人类可读描述
        - group_id: 所属协作组
        - persist_dir: 独立持久化目录（默认继承 config）
        - is_default: 设为默认回退 Agent

        返回创建的 agent_id 列表。
        """
        # 延迟导入，避免 multi_agent 包强制加载 agent 模块
        from soma.agent import SOMA_Agent

        agent_ids: List[str] = []
        for spec in specs:
            agent_id = spec["agent_id"]
            expertise = spec.get("expertise", [])
            description = spec.get("description", "")
            group_id = spec.get("group_id", "")
            persist_dir = spec.get("persist_dir", str(self.config.episodic_persist_dir))
            is_default = spec.get("is_default", False)

            # 基于主 config 创建独立的 Agent 配置
            framework_path = self.config.framework_path
            if framework_path is None:
                framework_path = Path(__file__).parent.parent / "wisdom_laws.yaml"
            agent_config = SOMAConfig(
                framework_path=framework_path,
                episodic_persist_dir=Path(persist_dir),
                llm_model=self.config.llm_model,
                llm_api_key=self.config.llm_api_key,
                llm_base_url=self.config.llm_base_url,
                use_vector_search=self.config.use_vector_search,
                recall_threshold=self.config.recall_threshold,
                default_top_k=self.config.default_top_k,
                enable_frame_detection=self.config.enable_frame_detection,
                frame_detection_window=self.config.frame_detection_window,
                # v1.1.3: 中道引擎配置透传
                enable_zhongdao=self.config.enable_zhongdao,
                zhongdao_threshold_ratio=self.config.zhongdao_threshold_ratio,
                zhongdao_penalty_factor=self.config.zhongdao_penalty_factor,
                zhongdao_boost_factor=self.config.zhongdao_boost_factor,
                zhongdao_min_samples=self.config.zhongdao_min_samples,
            )
            agent = SOMA_Agent(agent_config, agent_id=agent_id, group_id=group_id)

            # 第一个 agent 自动成为默认
            if is_default or self.default_agent is None:
                self.default_agent = agent
                is_default = True

            self.registry.register(
                agent, expertise=expertise,
                description=description, is_default=is_default,
            )
            self._agents[agent_id] = agent  # v1.1.1: 维护实例映射
            # v1.1.0: 注册到分布式演化器
            if self._evolver is not None:
                self._evolver.register_agent(
                    agent_id, agent.evolver,
                    session_count=0, success_rate=0.5,
                )
                self._agent_session_counts[agent_id] = 0
            agent_ids.append(agent_id)
            _log.info("创建Agent: %s 专长=%s 默认=%s", agent_id, expertise, is_default)

        return agent_ids

    def set_default(self, agent: Any) -> None:
        """手动设置默认回退 Agent"""
        agent_id = getattr(agent, 'agent_id', '')
        self.default_agent = agent
        if agent_id and agent_id not in {i.agent_id for i in self.registry.list_agents()}:
            self.registry.register(agent, expertise=["通用"], description="默认回退", is_default=True)

    def remove_agent(self, agent_id: str) -> bool:
        """移除一个 Agent，必要时自动切换默认"""
        self.registry.unregister(agent_id)
        self._agents.pop(agent_id, None)  # v1.1.1: 清理实例映射
        if self._evolver is not None:
            self._evolver.unregister_agent(agent_id)
        self._agent_session_counts.pop(agent_id, None)
        if self.default_agent is not None and getattr(self.default_agent, 'agent_id', '') == agent_id:
            self.default_agent = None
            remaining = self.registry.list_agents()
            if remaining:
                self.default_agent = self.registry.get(remaining[0].agent_id)
        return True

    def list_agents(self) -> List[Dict[str, Any]]:
        """v1.1.1: 列出所有已创建的Agent实例信息。

        返回 [{"agent_id": str, "expertise": [...], "description": str, ...}]
        """
        result = []
        for info in self.registry.list_agents():
            entry = {
                "agent_id": info.agent_id,
                "expertise": info.expertise,
                "description": info.description,
            }
            entry["session_count"] = self._agent_session_counts.get(info.agent_id, 0)
            result.append(entry)
        return result

    # ── 多Agent求解管道 ─────────────────────────────────────────

    def solve(
        self,
        problem: str,
        strategy: str = "voting",
        top_k: int | None = None,
    ) -> OrchestrationResult:
        """端到端多Agent求解：路由 → 分发 → 收集 → 共识

        Args:
            problem: 用户问题
            strategy: 共识策略 ("voting"/"llm_arbitration"/"dialectical_synthesis")
            top_k: 最多参与专家数（默认使用 config.orchestration_top_k）

        Returns:
            OrchestrationResult: 含共识回答、参与Agent、路由策略等
        """
        if top_k is None:
            top_k = self.config.orchestration_top_k

        try:
            return self._solve_impl(problem, strategy, top_k)
        except Exception as exc:
            _log.error("多Agent编排异常: %s", exc, exc_info=True)
            return OrchestrationResult(
                question=problem,
                answer=f"多Agent编排过程出错: {exc}",
                agents_involved=[],
                routing_strategy="error",
                consensus=None,
            )

    def _solve_impl(
        self, problem: str, strategy: str, top_k: int,
    ) -> OrchestrationResult:
        # ── 1. 路由：找最匹配的专家 ──
        experts = self.router.route_multi(problem, top_k=top_k)

        # v1.1.1: 确保所有已注册Agent都参与（路由过于保守时补齐）
        if len(experts) < len(self._agents):
            seen_ids = set()
            for agent, _score, _strat in experts:
                seen_ids.add(getattr(agent, 'agent_id', ''))
            for agent_id, agent in self._agents.items():
                if agent_id not in seen_ids:
                    experts.append((agent, 0.15, "supplement"))
                    seen_ids.add(agent_id)
            # 仍然遵守top_k上限
            if len(experts) > top_k:
                experts = experts[:top_k]

        if not experts:
            if self.default_agent is not None:
                experts = [(self.default_agent, 0.1, "fallback")]
            else:
                return OrchestrationResult(
                    question=problem,
                    answer="没有可用的专家Agent处理此问题。请先注册至少一个Agent。",
                    routing_strategy="fallback",
                )

        # ── 2. 分发：向各专家提问（v1.1.0 支持并行） ──
        use_parallel = self.config.orchestration_parallel and len(experts) > 1

        if use_parallel:
            opinions, agents_involved, routing_strategies = self._dispatch_parallel(
                problem, experts,
            )
        else:
            opinions, agents_involved, routing_strategies = self._dispatch_serial(
                problem, experts,
            )

        if not opinions:
            return OrchestrationResult(
                question=problem,
                answer="所有专家Agent均未能回答此问题。",
                agents_involved=agents_involved,
                routing_strategy=",".join(routing_strategies) if routing_strategies else "error",
            )

        # ── 3. 共识：综合多专家意见 ──
        consensus_result = self.consensus.form_consensus(
            problem, opinions, strategy=strategy,
        )

        # ── 3.5: 跨Agent中道协调（v1.1.3）检测群体趋同 ──
        cross_convergence = self._detect_cross_agent_convergence(opinions)
        if cross_convergence:
            _log.info(
                "跨Agent中道: 检测到群体趋同 law=%s agents=%s",
                cross_convergence["law_id"],
                cross_convergence["agents"],
            )
            # 在共识回答末尾附加多样性提醒（脚注格式，低干扰）
            diversity_note = (
                f"\n\n> ⚠️ *中道协调提示*：{len(cross_convergence['agents'])}位专家"
                f"均侧重「{cross_convergence['law_name']}」，"
                f"请注意从{cross_convergence['suggested_laws']}等互补视角重新审视。"
            )
            consensus_result.consensus_answer += diversity_note

        # ── 4. 演化：记录结果 + 定期全局合并（v1.1.0） ──
        self._evolve_after_solve(opinions)

        return OrchestrationResult(
            question=problem,
            answer=consensus_result.consensus_answer,
            agents_involved=agents_involved,
            routing_strategy=",".join(routing_strategies),
            consensus=consensus_result,
        )

    # ── 分发策略 ────────────────────────────────────────────────

    def _dispatch_serial(self, problem: str, experts) -> tuple:
        """串行分发（兼容模式）"""
        opinions: List[AgentOpinion] = []
        agents_involved: List[str] = []
        routing_strategies: set[str] = set()

        for agent, score, route_strategy in experts:
            agent_id = getattr(agent, 'agent_id', 'unknown')
            agents_involved.append(agent_id)
            routing_strategies.add(route_strategy)
            try:
                answer = agent.respond(problem)
                opinions.append(AgentOpinion(
                    agent_id=agent_id, answer=answer, confidence=score,
                ))
            except Exception as exc:
                _log.warning("Agent %s 回答失败: %s", agent_id, exc)

        return opinions, agents_involved, routing_strategies

    def _dispatch_parallel(self, problem: str, experts) -> tuple:
        """并行分发（v1.1.0） — 用 ThreadPoolExecutor 同时问所有专家"""
        opinions: List[AgentOpinion] = []
        agents_involved: List[str] = []
        routing_strategies: set[str] = set()

        # 构建 agent_id → (score, route_strategy) 映射
        agent_map: Dict[str, tuple] = {}
        for agent, score, route_strategy in experts:
            agent_id = getattr(agent, 'agent_id', 'unknown')
            agents_involved.append(agent_id)
            routing_strategies.add(route_strategy)
            agent_map[agent_id] = (agent, score, route_strategy)

        max_workers = min(len(experts), 8)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for agent, score, _route_strategy in experts:
                agent_id = getattr(agent, 'agent_id', 'unknown')
                futures[executor.submit(agent.respond, problem)] = agent_id

            for future in as_completed(futures):
                agent_id = futures[future]
                try:
                    answer = future.result(timeout=300)
                    score = agent_map[agent_id][1]
                    opinions.append(AgentOpinion(
                        agent_id=agent_id, answer=answer, confidence=score,
                    ))
                except Exception as exc:
                    _log.warning("Agent %s 并行调用失败: %s", agent_id, exc)

        # 并行结果按 agent_involved 顺序重排，确保确定性
        ordered = []
        for aid in agents_involved:
            for op in opinions:
                if op.agent_id == aid:
                    ordered.append(op)
                    break
        return ordered, agents_involved, routing_strategies

    # ── 跨Agent中道协调（v1.1.3） ───────────────────────────

    def _detect_cross_agent_convergence(
        self, opinions: List[AgentOpinion],
    ) -> Optional[dict]:
        """检测多Agent群体趋同：≥2个Agent在同一规律上过度使用。

        Returns:
            None 表示无趋同，dict 含 law_id/law_name/agents/suggested_laws。
        """
        if len(opinions) < 2:
            return None

        # 收集各Agent的中道使用统计
        agent_usage: Dict[str, Dict[str, int]] = {}
        for op in opinions:
            agent = self._agents.get(op.agent_id)
            if agent is None:
                continue
            z = getattr(agent, 'zhongdao', None)
            if z is None or not z.enabled or not z._session_usage:
                continue
            agent_usage[op.agent_id] = dict(z._session_usage)

        if len(agent_usage) < 2:
            return None

        # 统计每条规律被多少个Agent过度使用
        law_agent_count: Dict[str, List[str]] = {}
        for agent_id, usage in agent_usage.items():
            total = sum(usage.values())
            if total < 5:
                continue
            for law_id, count in usage.items():
                ratio = count / total
                if ratio > 0.40:  # 与 zhongdao 阈值一致
                    if law_id not in law_agent_count:
                        law_agent_count[law_id] = []
                    law_agent_count[law_id].append(agent_id)

        # 筛选≥2个Agent共同过度使用的规律
        for law_id, agents in law_agent_count.items():
            if len(agents) >= 2:
                law_name = law_id
                suggested = []
                # 从任意一个Agent的engine中查找规律信息
                for agent in self._agents.values():
                    eng = getattr(agent, 'engine', None)
                    if eng is None:
                        continue
                    for law in getattr(eng, 'laws', []):
                        if law.id == law_id:
                            law_name = law.name
                            # 从 relations 找未被使用的互补规律
                            all_used = set()
                            for usage in agent_usage.values():
                                all_used.update(usage.keys())
                            unused = [rid for rid in law.relations if rid not in all_used]
                            for rl in eng.laws:
                                if rl.id in unused[:2]:
                                    suggested.append(rl.name)
                            break
                    if law_name != law_id:
                        break

                return {
                    "law_id": law_id,
                    "law_name": law_name,
                    "agents": agents,
                    "suggested_laws": "、".join(suggested) if suggested else "其他维度",
                }

        return None

    # ── 分布式演化 ───────────────────────────────────────────────

    # ── v1.1.7: 多Agent深度协作 ─────────────────────────────

    def cross_validate(self, problem: str, agent_ids: list = None) -> dict:
        """交叉验证: 让多个Agent独立回答同一问题，然后互相审查对方的回答。

        返回每个Agent的独立分析 + 交叉评审矩阵 + 综合结论。
        """
        ids = agent_ids or list(self._agents.keys())[:3]
        if len(ids) < 2:
            return {"error": "需要至少2个Agent进行交叉验证"}

        # 各Agent独立分析
        independent = {}
        for aid in ids:
            agent = self._agents.get(aid)
            if agent is None:
                continue
            try:
                ans = agent.respond(problem)
            except Exception:
                ans = f"[{aid} 分析失败]"
            independent[aid] = ans

        # 互相审查
        cross_reviews = {}
        for reviewer in ids:
            reviews = {}
            for target in ids:
                if target == reviewer:
                    continue
                review_prompt = (
                    f"请审查以下Agent的分析:\n"
                    f"[{target}的分析]: {independent.get(target, '')}\n\n"
                    f"评估: 逻辑是否自洽？有无明显漏洞？评分(1-10)？"
                )
                try:
                    rev = self._agents[reviewer].respond(review_prompt) if self._agents.get(reviewer) else ""
                except Exception:
                    rev = ""
                reviews[target] = rev[:300]
            cross_reviews[reviewer] = reviews

        # 综合
        summary_prompt = (
            f"问题: {problem}\n\n各Agent分析:\n" +
            "\n".join(f"[{aid}]: {ans[:200]}" for aid, ans in independent.items()) +
            "\n\n请综合各Agent的分析和相互审查，给出最终结论。"
        )
        primary = self._agents.get(ids[0])
        try:
            final = primary.respond(summary_prompt) if primary else ""
        except Exception:
            final = ""

        return {
            "problem": problem,
            "independent_analyses": independent,
            "cross_reviews": cross_reviews,
            "final_conclusion": final[:2000],
        }

    def share_law_discovery(self, force: bool = False) -> dict:
        """跨Agent规律共享: 收集各Agent发现的规律，汇总去重，回写进各Agent的思维框架。

        v1.1.7-fix: 默认每10次solve才触发一次（可force=True强制）
        """
        self._solve_count = getattr(self, '_solve_count', 0)
        if not force and self._solve_count % 10 != 0:
            return {"status": "throttled", "solve_count": self._solve_count}
        discovered = {}
        for aid, agent in self._agents.items():
            try:
                laws = agent.discover_laws() if hasattr(agent, 'discover_laws') else []
            except Exception:
                laws = []
            if laws:
                discovered[aid] = laws

        if not discovered:
            return {"shared_laws": [], "agents_contributed": 0}

        # 去重: 按规律ID合并
        merged = {}
        for aid, laws in discovered.items():
            for law in (laws if isinstance(laws, list) else [laws]):
                lid = law.get("id", law.get("law_id", "")) if isinstance(law, dict) else str(law)
                if lid and lid not in merged:
                    merged[lid] = {"law": law, "discovered_by": [aid]}
                elif lid:
                    merged[lid]["discovered_by"].append(aid)

        # v1.1.7-fix: 质量过滤 — 只共享被 >=2 个 Agent 发现的规律（共识阈值）
        shared = [item for item in merged.values() if len(item["discovered_by"]) >= 2]

        # 回写到所有Agent（仅写入共识规律）
        for aid, agent in self._agents.items():
            for item in shared:
                if aid not in item["discovered_by"]:
                    try:
                        if hasattr(agent, 'approve_law'):
                            agent.approve_law(item["law"])
                    except Exception:
                        pass

        return {
            "shared_laws": shared,
            "agents_contributed": len(discovered),
            "total_unique_laws": len(shared),
        }

    def consensus_evolve(self, force: bool = False) -> dict:
        """共识进化: 收集各Agent的权重，计算共识权重，回写到所有Agent。

        仅在各Agent都有 evolve 能力时执行。
        v1.1.7-fix: 默认每10次solve才触发一次（可force=True强制）
        """
        self._solve_count = getattr(self, '_solve_count', 0)
        if not force and self._solve_count % 10 != 0:
            return {"status": "throttled", "solve_count": self._solve_count}
        all_weights = {}
        for aid, agent in self._agents.items():
            try:
                w = agent.get_weights() if hasattr(agent, 'get_weights') else {}
            except Exception:
                w = {}
            if w:
                all_weights[aid] = w

        if len(all_weights) < 2:
            return {"status": "insufficient_data", "agents": len(all_weights)}

        # v1.1.7-fix: 加权共识 — 按各Agent的会话数加权，而非简单平均
        # 经验更多的Agent权重更大，避免优质权重被稀释
        total_sessions = sum(self._agent_session_counts.values()) or 1
        law_ids = set()
        for w in all_weights.values():
            law_ids.update(w.keys())

        consensus = {}
        for lid in law_ids:
            weighted_sum = 0.0
            weight_total = 0.0
            for aid in all_weights:
                if lid in all_weights[aid]:
                    agent_weight = self._agent_session_counts.get(aid, 1) / total_sessions
                    weighted_sum += all_weights[aid][lid] * agent_weight
                    weight_total += agent_weight
            if weight_total > 0:
                consensus[lid] = round(weighted_sum / weight_total, 4)

        # 回写
        for aid, agent in self._agents.items():
            try:
                for lid, w in consensus.items():
                    agent.adjust_weight(lid, w)
            except Exception:
                pass

        return {
            "status": "evolved",
            "agents": len(all_weights),
            "laws_updated": len(consensus),
            "consensus_weights": consensus,
        }

    def _evolve_after_solve(self, opinions: List[AgentOpinion]) -> None:
        """每次 solve 后记录各 Agent 参与情况，定期触发全局权重合并"""
        if self._evolver is None:
            return

        self._solve_count += 1

        for op in opinions:
            try:
                sessions = self._agent_session_counts.get(op.agent_id, 0) + 1
                self._agent_session_counts[op.agent_id] = sessions
                self._evolver.update_stats(
                    op.agent_id,
                    session_count=sessions,
                    success_rate=op.confidence,
                )
            except Exception:
                pass

        # 定期全局合并
        interval = self.config.orchestration_evolution_interval
        if interval > 0 and self._solve_count % interval == 0:
            try:
                self._evolver.merge_weights()
                self._evolver.apply_all()
                _log.info("全局权重合并完成 (solve #%d)", self._solve_count)
            except Exception as exc:
                _log.warning("全局权重合并失败: %s", exc)

    # ── 属性 ────────────────────────────────────────────────────

    @property
    def agent_count(self) -> int:
        return self.registry.agent_count

    @property
    def stats(self) -> dict:
        base = {
            "agent_count": self.agent_count,
            "router": self.router.stats,
            "consensus_sessions": self.consensus.session_count,
            "solve_count": self._solve_count,
            "parallel_enabled": self.config.orchestration_parallel,
            "evolution_enabled": self._evolver is not None,
        }
        if self._evolver is not None:
            base["evolution"] = self._evolver.get_stats()
        return base
