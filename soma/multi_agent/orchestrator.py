"""多Agent编排器 — v0.9.2

SOMAOrchestrator 将已有的 Registry、Router、ConsensusProtocol 串联为完整的多Agent求解管道。
不修改 multi_agent/ 下任何现有文件，纯连线层。
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from soma.config import SOMAConfig
from soma.multi_agent.registry import AgentRegistry
from soma.multi_agent.router import ExpertRouter
from soma.multi_agent.consensus import ConsensusProtocol, AgentOpinion, ConsensusResult

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
        if self.default_agent is not None and getattr(self.default_agent, 'agent_id', '') == agent_id:
            self.default_agent = None
            remaining = self.registry.list_agents()
            if remaining:
                self.default_agent = self.registry.get(remaining[0].agent_id)
        return True

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
        if not experts:
            if self.default_agent is not None:
                experts = [(self.default_agent, 0.1, "fallback")]
            else:
                return OrchestrationResult(
                    question=problem,
                    answer="没有可用的专家Agent处理此问题。请先注册至少一个Agent。",
                    routing_strategy="fallback",
                )

        # ── 2. 分发：向各专家提问（v0.9.2 串行） ──
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
                    agent_id=agent_id,
                    answer=answer,
                    confidence=score,
                ))
            except Exception as exc:
                _log.warning("Agent %s 回答失败: %s", agent_id, exc)

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

        return OrchestrationResult(
            question=problem,
            answer=consensus_result.consensus_answer,
            agents_involved=agents_involved,
            routing_strategy=",".join(routing_strategies),
            consensus=consensus_result,
        )

    # ── 属性 ────────────────────────────────────────────────────

    @property
    def agent_count(self) -> int:
        return self.registry.agent_count

    @property
    def stats(self) -> dict:
        return {
            "agent_count": self.agent_count,
            "router": self.router.stats,
            "consensus_sessions": self.consensus.session_count,
        }
