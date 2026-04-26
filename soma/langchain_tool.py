"""LangChain 集成 — 将 SOMA_Agent 封装为标准 Tool"""

from typing import Optional, Type

from soma.agent import SOMA_Agent


def _get_langchain_types():
    """懒导入 LangChain 类型，避免未安装时导入报错"""
    from langchain_core.tools import BaseTool
    from langchain_core.callbacks import CallbackManagerForToolRun

    return BaseTool, CallbackManagerForToolRun


def create_soma_tool(
    soma_agent: SOMA_Agent,
    name: str = "soma_wisdom",
    description: Optional[str] = None,
) -> "BaseTool":
    """
    创建 LangChain Tool 封装。

    Args:
        soma_agent: 已初始化的 SOMA_Agent 实例
        name: Tool 名称
        description: Tool 描述（用于 Agent 决定何时调用）

    Returns:
        LangChain BaseTool 子类实例
    """
    BaseTool, CallbackManagerForToolRun = _get_langchain_types()

    desc = description or (
        "使用思维框架进行深度分析并回答问题。"
        "输入一个问题，返回综合多维度思维规律和过往记忆资粮的深度回答。"
        "适用于需要多角度分析、根本原因探究、系统化思考的复杂问题。"
    )

    tool_name = name
    tool_desc = desc
    tool_agent = soma_agent

    class SOMATool(BaseTool):
        name: str = ""
        description: str = ""

        def _run(
            self,
            query: str,
            run_manager: Optional[CallbackManagerForToolRun] = None,
        ) -> str:
            return tool_agent.respond(query)

    tool = SOMATool(name=tool_name, description=tool_desc)
    return tool
