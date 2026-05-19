"""CrewAI 集成 — SOMA 作为 Crew 共享记忆层"""

from typing import Any, Dict, List, Optional

from soma.agent import SOMA_Agent


class SOMACrewMemory:
    """CrewAI 共享长期记忆 — 跨 Agent 持久化知识。

    在 Crew 运行前预加载相关记忆，运行后持久化关键发现。

    用法::

        from soma.crewai_tool import SOMACrewMemory
        from soma import SOMA

        soma = SOMA()
        memory = SOMACrewMemory(soma._agent)

        # Crew 运行前
        context = memory.preload("微服务架构最佳实践")
        # ... 运行 Crew，把 context 注入 task description ...

        # Crew 运行后
        memory.persist_result("微服务拆分应优先按业务领域边界", importance=0.9)
    """

    def __init__(self, soma_agent: SOMA_Agent, user_id: str = ""):
        self._agent = soma_agent
        self._user_id = user_id

    def preload(self, query: str, top_k: int = 5) -> str:
        """Crew 运行前：检索相关记忆作为上下文注入。

        Returns:
            格式化的上下文文本，可直接拼接到 Task description 中。
        """
        memories = self._agent.query_memory(query, top_k=top_k, user_id=self._user_id)
        if not memories:
            return ""

        lines = ["[SOMA 长期记忆 — 相关历史知识]"]
        for i, m in enumerate(memories, 1):
            content = m.get("content", "")[:500]
            score = m.get("activation_score", 0)
            lines.append(f"{i}. {content} (相关度:{score:.2f})")
        return "\n".join(lines)

    def persist_result(self, content: str, importance: float = 0.85, task_name: str = "") -> str:
        """Crew 运行后：持久化结论或发现。

        Args:
            content: 要记录的内容
            importance: 重要性 (0.0–1.0)
            task_name: 关联的任务名称
        """
        context = {"source": "crewai", "task": task_name} if task_name else {"source": "crewai"}
        return self._agent.remember(
            content, context=context, importance=importance, user_id=self._user_id,
        )

    def query(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """原始查询接口，返回完整记忆列表。"""
        return self._agent.query_memory(query, top_k=top_k, user_id=self._user_id)


def create_soma_crewai_tools(soma_agent: SOMA_Agent) -> List[Any]:
    """创建 CrewAI Tool 列表，可直接传给 CrewAI Agent。

    用法::

        from crewai import Agent
        from soma.crewai_tool import create_soma_crewai_tools

        tools = create_soma_crewai_tools(soma._agent)
        researcher = Agent(
            role="研究员",
            goal="调研并记录发现",
            tools=tools,
        )
    """
    try:
        from crewai_tools import tool
    except ImportError:
        raise ImportError("请先安装 CrewAI: pip install crewai")

    agent = soma_agent

    @tool("soma_search")
    def soma_search(query: str) -> str:
        """搜索SOMA长期记忆，获取历史知识和经验。"""
        memories = agent.query_memory(query, top_k=5)
        if not memories:
            return "未找到相关记忆。"
        return "\n".join(
            f"- {m.get('content', '')[:300]}" for m in memories
        )

    @tool("soma_memorize")
    def soma_memorize(content: str) -> str:
        """将重要发现存入SOMA长期记忆。"""
        agent.remember(content, context={"source": "crewai"}, importance=0.8)
        return f"已存入SOMA记忆。"

    return [soma_search, soma_memorize]
