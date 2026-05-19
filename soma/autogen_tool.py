"""AutoGen 集成 — SOMA 作为共享认知记忆"""

from typing import Any, Dict, List, Optional

from soma.agent import SOMA_Agent


def create_soma_autogen_tools(soma_agent: SOMA_Agent) -> tuple:
    """创建 AutoGen 工具注册所需的 function_map 和 tool_schemas。

    用法::

        import autogen
        from soma.autogen_tool import create_soma_autogen_tools

        function_map, tool_schemas = create_soma_autogen_tools(soma._agent)

        llm_config = {
            "config_list": [{"model": "deepseek-chat", "api_key": "..."}],
            "tools": tool_schemas,
        }

        assistant = autogen.AssistantAgent(name="assistant", llm_config=llm_config)
        user_proxy = autogen.UserProxyAgent(
            name="user_proxy",
            function_map=function_map,
        )
    """

    def soma_search(query: str) -> str:
        memories = soma_agent.query_memory(query, top_k=5)
        if not memories:
            return "未找到相关记忆。"
        return "\n".join(
            f"- [{m.get('source', 'memory')}] {m.get('content', '')[:400]}"
            for m in memories
        )

    def soma_store(content: str) -> str:
        mem_id = soma_agent.remember(
            content, context={"source": "autogen"}, importance=0.75,
        )
        return f"已存储到SOMA记忆，ID: {mem_id}"

    function_map = {
        "soma_search": soma_search,
        "soma_store": soma_store,
    }

    tool_schemas = [
        {
            "type": "function",
            "function": {
                "name": "soma_search",
                "description": "搜索SOMA长期记忆系统，找到与当前讨论相关的历史知识和经验。当需要参考过往上下文时使用。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "要搜索的问题或关键词",
                        },
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "soma_store",
                "description": "将重要结论或事实存储到SOMA长期记忆，供后续会话参考。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "要存储的内容",
                        },
                    },
                    "required": ["content"],
                },
            },
        },
    ]

    return function_map, tool_schemas


class SOMAAutoGenMemory:
    """SOMA 作为 AutoGen GroupChat 的集体记忆。

    在群聊中注入共享上下文，记录关键决策。

    用法::

        from soma.autogen_tool import SOMAAutoGenMemory

        memory = SOMAAutoGenMemory(soma._agent)

        # 每轮对话前
        context = memory.preload("当前讨论主题")

        # 关键决策后
        memory.record_decision("选择PostgreSQL作为主数据库", importance=0.9)
    """

    def __init__(self, soma_agent: SOMA_Agent, user_id: str = ""):
        self._agent = soma_agent
        self._user_id = user_id

    def preload(self, topic: str, top_k: int = 5) -> str:
        """群聊前注入相关历史。"""
        memories = self._agent.query_memory(topic, top_k=top_k, user_id=self._user_id)
        if not memories:
            return ""
        lines = ["[共享记忆 — 相关历史]"]
        for m in memories:
            lines.append(f"- {m.get('content', '')[:300]}")
        return "\n".join(lines)

    def record_decision(self, content: str, importance: float = 0.9) -> str:
        """记录群聊中的关键决策。"""
        return self._agent.remember(
            content,
            context={"source": "autogen", "type": "decision"},
            importance=importance,
            user_id=self._user_id,
        )

    def query(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        return self._agent.query_memory(query, top_k=top_k, user_id=self._user_id)
