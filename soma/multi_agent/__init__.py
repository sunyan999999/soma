"""多智能体协作模块 — v1.1.1

提供专家注册、问题路由、分布式权重演化、共识形成协议、并行编排。
"""

from soma.multi_agent.registry import AgentRegistry, AgentInfo
from soma.multi_agent.router import ExpertRouter
from soma.multi_agent.evolve import DistributedEvolver
from soma.multi_agent.consensus import ConsensusProtocol, ConsensusResult, AgentOpinion
from soma.multi_agent.orchestrator import SOMAOrchestrator, OrchestrationResult

__all__ = [
    "AgentRegistry",
    "AgentInfo",
    "ExpertRouter",
    "DistributedEvolver",
    "ConsensusProtocol",
    "ConsensusResult",
    "AgentOpinion",
    "SOMAOrchestrator",
    "OrchestrationResult",
]
