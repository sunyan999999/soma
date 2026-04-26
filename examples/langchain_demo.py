"""LangChain 集成示例 — 将 SOMA 作为 Agent Tool 使用"""
from pathlib import Path

from soma.config import SOMAConfig, load_config
from soma.agent import SOMA_Agent
from soma.langchain_tool import create_soma_tool


def main():
    # 1. 初始化 SOMA Agent
    framework = load_config(Path("wisdom_laws.yaml"))
    config = SOMAConfig(
        framework=framework,
        episodic_persist_dir=Path("demo_data"),
        use_vector_search=False,
    )
    agent = SOMA_Agent(config)

    # 2. 注入示例记忆
    agent.remember(
        "第一性原理的核心是回归最基本的要素，从底层逻辑推导。"
        "在商业中，关注客户最根本的需求比关注竞争对手更重要。",
        context={"domain": "哲学", "type": "理论"},
        importance=0.95,
    )
    agent.remember(
        "系统思维：增长停滞是产品、市场、团队、流程等多要素负反馈的结果。",
        context={"domain": "思维", "type": "方法论"},
        importance=0.9,
    )
    agent.remember(
        "逆向思考案例：研究'用户为何流失'而非'如何增长'，反向改进实现增长突破。",
        context={"domain": "营销", "type": "案例"},
        importance=0.85,
    )

    # 3. 创建 LangChain Tool
    tool = create_soma_tool(
        agent,
        name="soma_deep_thinker",
        description=(
            "使用第一性原理、系统思维等思维框架进行深度分析。"
            "适用于需要多维度思考、根本原因探究的复杂问题。"
            "输入问题文本，返回综合分析和建议。"
        ),
    )

    # 4. 直接使用 Tool
    print("=" * 60)
    print("SOMA LangChain Tool 演示")
    print(f"Tool 名称: {tool.name}")
    print(f"Tool 描述: {tool.description}")
    print("=" * 60)

    # 5. 运行分析（需要有效的 LLM API key）
    problem = "为什么新产品增长停滞？"
    print(f"\n问题: {problem}")
    print("\n正在分析...")

    try:
        answer = tool._run(problem)
        print(f"\n回答:\n{answer}")
    except Exception as e:
        print(f"\nLLM 调用失败（检查 API key 配置）: {e}")

    # 6. 记忆统计
    print("\n" + "=" * 60)
    print("记忆统计:", agent.memory.stats())
    print("规律权重:", agent.evolver.get_weights())

    # 7. 记录反思
    agent.reflect("demo_task", "success")
    print(f"反思日志: {len(agent.evolver.get_log())} 条")


if __name__ == "__main__":
    main()
