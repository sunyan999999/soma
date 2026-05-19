# Integrations

SOMA works alongside popular LLM frameworks. This guide shows how to embed SOMA's cognitive memory into your existing stack.

---

## LangChain

SOMA ships with a native LangChain tool since v0.7.0.

```python
from soma.langchain_tool import create_soma_tool
from soma import SOMA
from langchain.agents import create_react_agent, Tool
from langchain.llms import OpenAI

# Create the tool
soma = SOMA()
soma_tool = create_soma_tool(soma._agent)

# Use in a LangChain agent
tools = [
    Tool(
        name="SOMA Memory",
        func=soma_tool.run,
        description="Search and reason with accumulated knowledge. Use for context-rich questions."
    )
]

agent = create_react_agent(llm=OpenAI(), tools=tools)
agent.invoke({"input": "Based on what we know, what's the best architecture choice?"})
```

The LangChain tool wraps `soma.respond()` — you get the full wisdom pipeline (decompose → activate → reason → synthesize) as a single tool call.

---

## LlamaIndex

SOMA can serve as a custom memory backend for LlamaIndex agents.

```python
from llama_index.core.agent import ReActAgent
from llama_index.core.tools import FunctionTool
from llama_index.core.memory import ChatMemoryBuffer
from soma import SOMA

soma = SOMA()

def soma_recall(query: str) -> str:
    """Search SOMA memory for relevant context."""
    memories = soma.query_memory(query, top_k=5)
    if not memories:
        return "No relevant memories found."
    return "\n\n".join(
        f"[{m.get('source', 'memory')}] {m.get('content', '')[:500]}"
        for m in memories
    )

def soma_remember(content: str, importance: float = 0.7) -> str:
    """Store something in SOMA memory."""
    mem_id = soma.remember(content, context={}, importance=importance)
    return f"Stored as {mem_id}"

soma_tool = FunctionTool.from_defaults(
    fn=soma_recall,
    name="soma_recall",
    description="Search long-term memory for relevant knowledge"
)

store_tool = FunctionTool.from_defaults(
    fn=soma_remember,
    name="soma_remember",
    description="Store a fact or insight into long-term memory"
)

agent = ReActAgent.from_tools(
    [soma_tool, store_tool],
    memory=ChatMemoryBuffer.from_defaults(token_limit=4096),
    verbose=True,
)
agent.chat("What do we know about the payment system architecture?")
```

### SOMA Ingest Pipeline for LlamaIndex Documents

Use SOMA's semantic triple extraction to build a knowledge graph from LlamaIndex ingested documents:

```python
from llama_index.core import SimpleDirectoryReader
from soma import SOMA

soma = SOMA()
documents = SimpleDirectoryReader("./docs").load_data()

for doc in documents:
    # Store document as episodic memory
    soma.remember(
        doc.text[:2000],
        context={"source": doc.metadata.get("file_name", "unknown")},
        importance=0.6,
    )
    # Extract key concepts as semantic triples
    soma.chat(f"提取关键概念三元组: {doc.text[:1000]}")
```

---

## CrewAI

SOMA as a shared memory layer across CrewAI agents.

```python
from crewai import Agent, Task, Crew, Process
from soma import SOMA

soma = SOMA()

# Agents with SOMA-backed memory
researcher = Agent(
    role="研究员",
    goal="深入调研并记录发现",
    backstory="你是一位资深研究员，善于从已有知识中寻找线索。",
    tools=[],  # SOMA is used implicitly via the memory layer
    verbose=True,
)

analyst = Agent(
    role="分析师",
    goal="基于研究发现提出建议",
    backstory="你是一位策略分析师，擅长综合信息做出判断。",
    verbose=True,
)

# Before a Crew run, preload relevant memories
def preload_context(query: str) -> str:
    memories = soma.query_memory(query, top_k=5)
    return "\n".join(m["content"][:300] for m in memories)

# After run, persist findings
def persist_findings(result: str):
    soma.remember(result, context={"source": "crewai"}, importance=0.85)

# Run the crew
task1 = Task(description="研究微服务架构的最新实践", expected_output="一份研究报告", agent=researcher)
task2 = Task(description="基于研究报告提出技术选型建议", expected_output="技术选型建议书", agent=analyst)

context = preload_context("微服务架构 技术选型")
crew = Crew(agents=[researcher, analyst], tasks=[task1, task2], process=Process.sequential)
result = crew.kickoff(inputs={"context": context})

persist_findings(str(result))
```

---

## AutoGen

SOMA as a shared cognitive memory for AutoGen agents.

```python
import autogen
from soma import SOMA

soma = SOMA()

# Shared SOMA tool functions
def soma_search(query: str) -> str:
    """Search shared memory."""
    memories = soma.query_memory(query, top_k=5)
    return "\n".join(f"- {m['content'][:200]}" for m in memories)

def soma_store(content: str) -> str:
    """Store in shared memory."""
    soma.remember(content, context={}, importance=0.75)
    return "Stored."

# Register as AutoGen tools
llm_config = {
    "config_list": [{"model": "deepseek-chat", "api_key": "sk-xxx"}],
    "tools": [
        {"type": "function", "function": {"name": "soma_search", "description": "Search shared long-term memory"}},
        {"type": "function", "function": {"name": "soma_store", "description": "Store a fact in shared memory"}},
    ],
}

assistant = autogen.AssistantAgent(name="assistant", llm_config=llm_config)
user_proxy = autogen.UserProxyAgent(
    name="user_proxy",
    code_execution_config=False,
    function_map={"soma_search": soma_search, "soma_store": soma_store},
)

user_proxy.initiate_chat(
    assistant,
    message="Based on our previous architecture discussions, what should we use for the API gateway?"
)
```

### Multi-Agent Co-memory Pattern

AutoGen's group chat + SOMA's shared memory create a "team with collective memory":

```python
groupchat = autogen.GroupChat(
    agents=[assistant, critic, executor],
    messages=[],
    max_round=10,
)

manager = autogen.GroupChatManager(groupchat=groupchat)

# Before each round, inject relevant SOMA memories
# After each round, persist key conclusions to SOMA
```

---

## Direct HTTP Integration

For non-Python stacks (Node.js, Go, Rust), use SOMA's REST API:

```bash
# Start the server
python dash/server.py
```

```javascript
// Node.js example
const response = await fetch("http://localhost:8765/api/chat", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ problem: "What architecture for a real-time dashboard?" })
});
const { answer, reasoning } = await response.json();
```

Or use SOMA as an MCP server for Claude Code and other MCP-compatible systems:

```bash
python -m soma.mcp_server
```

See the [API Reference](../api/) for the full REST endpoint list.

---

## 集成指南

## LangChain

SOMA 从 v0.7.0 开始内置 LangChain 工具。`create_soma_tool()` 封装了完整的智慧管道。

## LlamaIndex

SOMA 可以作为 LlamaIndex Agent 的自定义记忆后端，或用于从 LlamaIndex 文档构建知识图谱。

## CrewAI

SOMA 作为 CrewAI 多个 Agent 之间的共享记忆层——任务前预加载上下文，任务后持久化发现。

## AutoGen

SOMA 作为 AutoGen Agent 的共享认知记忆，支持群聊中的"团队集体记忆"模式。

## 直接 HTTP 集成

非 Python 技术栈通过 REST API 或 MCP 协议接入。启动服务后任何语言都能调用。
