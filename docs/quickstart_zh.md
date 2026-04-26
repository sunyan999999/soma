# 快速开始

5 分钟接入 SOMA，给你的 Agent 一个会思考的灵魂。

## 安装

```bash
pip install soma-core
```

需要 **Python 3.10+**。嵌入引擎使用 ONNX Runtime 进行 CPU 推理，无需 CUDA、Docker 或外部服务。

首次运行时自动下载一个小型 ONNX 模型（约 100 MB，中英双语）。

## 验证安装

```bash
python -m soma
```

内置验证脚本会初始化思维框架、创建记忆库并测试完整管道。

## 5 分钟上手

```python
from soma import SOMA

# 1. 初始化 — 零配置启动
soma = SOMA()

# 2. 存入一些记忆
soma.remember(
    "第一性原理：回归事物最基本的要素，从底层逻辑出发推导，"
    "不被既有经验束缚。",
    context={"domain": "哲学", "type": "理论"},
    importance=0.9
)

soma.remember(
    "Q3增长瓶颈最终追溯到注册流程摩擦。"
    "将注册步骤从5步简化到2步后，转化率提升了34%。",
    context={"domain": "商业", "type": "案例"},
    importance=0.85
)

# 3. 提问 — 完整的智者思维管道
answer = soma.respond("如何系统性地分析我们产品的增长停滞问题？")
print(answer)

# 4. 查询特定记忆
memories = soma.query_memory("增长策略", top_k=5)
for m in memories:
    print(f"[{m['source']}] 关联度={m['activation_score']:.3f}: {m['content'][:80]}...")

# 5. 查看框架状态
print(soma.stats)
print(soma.get_weights())
```

## 底层发生了什么

当你调用 `soma.respond(problem)` 时：

1. **拆解（Decompose）** — WisdomEngine 用 7 条思维规律匹配问题，生成分析焦点
2. **激活（Activate）** — ActivationHub 通过混合检索（语义×2 + 关键词×1 RRF）召回相关记忆
3. **合成（Synthesize）** — 被选中的记忆与框架上下文一起组装为 Prompt，发送给 LLM
4. **进化（Evolve）** — 记录本次结果；每 10 次会话自动调整规律权重

## Mock 模式运行

没有 LLM API Key？SOMA 默认以 Mock 模式运行 — 仍然拆解问题和激活记忆，只是跳过 LLM 调用，返回结构化分析结果。

```python
# Mock 模式（默认，无需 API Key）
soma = SOMA()
answer = soma.respond("如何提升团队效能？")
# 返回：拆解结果 + 激活的记忆片段

# 接入真实 LLM
soma = SOMA(llm="deepseek-chat")
# 使用 LiteLLM 统一接口 — 设置 DEEPSEEK_API_KEY 或 OPENAI_API_KEY 环境变量
```

## 使用 REST API

```bash
# 启动服务
python dash/server.py
# → http://localhost:8765

# 问答接口
curl -X POST http://localhost:8765/api/chat \
  -H "Content-Type: application/json" \
  -d '{"problem": "分析我们的增长瓶颈"}'

# SSE 流式输出
curl -X POST http://localhost:8765/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"problem": "如何提升团队效能？"}'

# 记忆搜索
curl -X POST http://localhost:8765/api/memory/search \
  -H "Content-Type: application/json" \
  -d '{"query": "增长策略", "top_k": 10}'
```

## LangChain 集成

```python
from soma.langchain_tool import create_soma_tool
from soma import SOMA

soma = SOMA()
tool = create_soma_tool(soma._agent)
result = tool.run("用系统思维分析这个问题...")
```

## 下一步

- [核心理念](philosophy.md) — 理解「框架优先」的设计哲学
- [架构手册](architecture.md) — 模块地图、数据流、类图
- [API 参考](api/) — 完整方法签名与示例
- [自定义指南](guides/customization.md) — 自定义框架、存储后端、LLM 配置
