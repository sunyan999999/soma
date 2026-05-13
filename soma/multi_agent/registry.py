"""Agent 注册表 — 管理多个专家 agent 的生命周期和元数据"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import logging

_log = logging.getLogger("soma.multi_agent")


@dataclass
class AgentInfo:
    """子 agent 的元数据描述"""
    agent_id: str
    expertise: List[str]  # 专长领域标签，如 ["law", "contract", "compliance"]
    description: str = ""  # 人类可读的描述
    group_id: str = ""  # 所属协作组
    session_count: int = 0  # 已处理会话数
    success_rate: float = 0.5  # 成功率（0-1）

    def match_score(self, domain: str) -> float:
        """计算此 agent 与目标领域的匹配度（0-1）"""
        domain_lower = domain.lower()
        for exp in self.expertise:
            exp_lower = exp.lower()
            if exp_lower == domain_lower:
                return 1.0
            if exp_lower in domain_lower or domain_lower in exp_lower:
                return 0.7
        return 0.0


class AgentRegistry:
    """子 agent 注册表 — 管理所有专家 agent 实例及其专长标签"""

    def __init__(self):
        self._agents: Dict[str, object] = {}  # agent_id → SOMA_Agent 实例
        self._info: Dict[str, AgentInfo] = {}  # agent_id → AgentInfo 元数据
        self._default_agent: Optional[object] = None  # 通用回退 agent

    def register(
        self,
        agent: object,  # SOMA_Agent 实例
        expertise: List[str],
        description: str = "",
        is_default: bool = False,
    ) -> str:
        """注册一个专家 agent。

        返回 agent_id。若 is_default=True，设为此 registry 的默认回退 agent。
        """
        agent_id = getattr(agent, 'agent_id', '') or f"agent_{len(self._agents)}"
        group_id = getattr(agent, 'group_id', '')

        info = AgentInfo(
            agent_id=agent_id,
            expertise=expertise,
            description=description,
            group_id=group_id,
        )
        self._agents[agent_id] = agent
        self._info[agent_id] = info

        if is_default:
            self._default_agent = agent

        _log.info("注册专家 agent: %s 专长=%s 默认=%s", agent_id, expertise, is_default)
        return agent_id

    def unregister(self, agent_id: str) -> bool:
        """注销一个 agent"""
        if agent_id in self._agents:
            del self._agents[agent_id]
            del self._info[agent_id]
            return True
        return False

    def find_experts(
        self, domain: str, min_score: float = 0.3,
    ) -> List[Tuple[object, float]]:
        """查找与目标领域匹配的专家 agent，按匹配度降序"""
        scored = []
        for agent_id, info in self._info.items():
            score = info.match_score(domain)
            if score >= min_score:
                scored.append((self._agents[agent_id], score))
        scored.sort(key=lambda x: -x[1])
        return scored

    def get_default(self) -> Optional[object]:
        """获取默认回退 agent"""
        return self._default_agent

    def get(self, agent_id: str) -> Optional[object]:
        """按 ID 获取 agent 实例"""
        return self._agents.get(agent_id)

    def get_info(self, agent_id: str) -> Optional[AgentInfo]:
        """获取 agent 元数据"""
        return self._info.get(agent_id)

    def list_agents(self) -> List[AgentInfo]:
        """列出所有注册 agent 的元数据"""
        return list(self._info.values())

    def record_session(self, agent_id: str, success: bool) -> None:
        """记录一次会话结果，更新成功率统计"""
        info = self._info.get(agent_id)
        if info is None:
            return
        info.session_count += 1
        # 增量更新成功率：指数移动平均
        alpha = 0.1
        info.success_rate = (
            info.success_rate * (1 - alpha) + (1.0 if success else 0.0) * alpha
        )

    @property
    def agent_count(self) -> int:
        return len(self._agents)
