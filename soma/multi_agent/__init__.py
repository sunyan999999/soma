"""多智能体协作模块 — v0.9.0

提供专家注册、问题路由、分布式权重演化、共识形成协议。
"""

from soma.multi_agent.registry import AgentRegistry, AgentInfo
from soma.multi_agent.router import ExpertRouter
from soma.multi_agent.evolve import DistributedEvolver
from soma.multi_agent.consensus import ConsensusProtocol, ConsensusResult, AgentOpinion

__all__ = [
    "AgentRegistry",
    "AgentInfo",
    "ExpertRouter",
    "DistributedEvolver",
    "ConsensusProtocol",
    "ConsensusResult",
    "AgentOpinion",
]
