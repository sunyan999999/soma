"""LlamaIndex 集成 — 将 SOMA 封装为 LlamaIndex Tool 和 Memory"""

from typing import Any, Dict, List, Optional

from soma.agent import SOMA_Agent


def create_soma_llamaindex_tools(soma_agent: SOMA_Agent) -> List[Any]:
    """创建 LlamaIndex FunctionTool 列表（记忆搜索 + 记忆存储）。

    返回两个工具：soma_recall（搜索记忆）、soma_remember（存储记忆）。

    用法::

        from llama_index.core.agent import ReActAgent
        from soma.llamaindex_tool import create_soma_llamaindex_tools

        tools = create_soma_llamaindex_tools(soma._agent)
        agent = ReActAgent.from_tools(tools, verbose=True)
        agent.chat("根据过往经验，我们应该怎么设计API网关？")
    """
    try:
        from llama_index.core.tools import FunctionTool
    except ImportError:
        raise ImportError("请先安装 LlamaIndex: pip install llama-index")

    agent = soma_agent

    def soma_recall(query: str) -> str:
        memories = agent.query_memory(query, top_k=5)
        if not memories:
            return "未找到相关记忆。"
        return "\n\n".join(
            f"[{m.get('source', 'memory')}, 相关度:{m.get('activation_score', 0):.2f}] "
            f"{m.get('content', '')[:500]}"
            for m in memories
        )

    def soma_remember(content: str, importance: float = 0.7) -> str:
        mem_id = agent.remember(content, context={}, importance=importance)
        return f"已存储，记忆ID: {mem_id}"

    return [
        FunctionTool.from_defaults(
            fn=soma_recall,
            name="soma_recall",
            description="搜索SOMA长期记忆，获取与当前问题相关的历史知识和经验。用于需要上下文背景的问题。",
        ),
        FunctionTool.from_defaults(
            fn=soma_remember,
            name="soma_remember",
            description="将重要事实或洞察存入SOMA长期记忆。输入要记住的内容。",
        ),
    ]


class SOMALlamaIndexMemory:
    """SOMA 作为 LlamaIndex ChatMemoryBuffer 的后备存储。

    在 LlamaIndex 的短期记忆（token buffer）之外提供长期持久化。

    用法::

        from soma.llamaindex_tool import SOMALlamaIndexMemory

        memory = SOMALlamaIndexMemory(soma._agent)
        memory.add("用户偏好 Python 和 FP 风格")  # 存到 SOMA
        context = memory.get("编程语言偏好")        # 从 SOMA 检索
    """

    def __init__(self, soma_agent: SOMA_Agent, user_id: str = ""):
        self._agent = soma_agent
        self._user_id = user_id

    def add(self, content: str, importance: float = 0.7) -> str:
        return self._agent.remember(
            content, context={}, importance=importance, user_id=self._user_id,
        )

    def get(self, query: str, top_k: int = 5) -> str:
        memories = self._agent.query_memory(query, top_k=top_k, user_id=self._user_id)
        if not memories:
            return ""
        return "\n".join(m.get("content", "")[:300] for m in memories)

    def get_all(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        return self._agent.query_memory(query, top_k=top_k, user_id=self._user_id)
