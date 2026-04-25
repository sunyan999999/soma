# SOMA-core

**Wisdom over Memory**（智慧超越记忆）

SOMA（Somatic Wisdom Architecture，体悟式智慧架构）是一个轻量、可拔插、协议标准的记忆与调度框架。它不只是一个记忆库——它以**思维框架为索引**，通过**双向激活机制**调度记忆资粮，让任意 AI Agent 获得"智者思维"。

## 核心哲学

> 不是让 AI 记更多，而是让 AI 悟更深。

当前 LLM 的记忆研究多聚焦于存储容量与检索精度。但真正具备深邃洞察力的智慧，依赖的是一套可拆解万物的底层思维框架。SOMA 将思维规律作为记忆的组织维度，实现 **Framework First, Memory Second**。

## 智者思维四步循环

```
问题拆解 → 双向资粮激活 → 记忆拼图与方案合成 → 沉淀与进化
```

## 快速开始

```python
from soma import SOMA

# 初始化
soma = SOMA()

# 存储记忆
soma.remember(
    content="在市场推广中采用逆向思考，从失败案例中寻找成功路径...",
    context={"domain": "营销", "type": "案例"},
    importance=0.9
)

soma.remember_semantic(
    subject="快速决策",
    predicate="依赖",
    object_="第一性原理",
    confidence=1.0
)

# 智慧式应答
answer = soma.respond("新产品增长停滞怎么办？")
print(answer)
```

## 安装

```bash
pip install soma-core
```

## 架构

```
SOMA_Agent → WisdomEngine → ActivationHub → MemoryCore → MetaEvolver
```

- **WisdomEngine**：思维框架引擎，将问题按底层规律拆解为分析焦点
- **MemoryCore**：统一记忆存储（情节记忆 + 语义图谱 + 技能模式）
- **ActivationHub**：双向激活调度器，计算关联潜力并返回 Top-K 资粮
- **MetaEvolver**：元认知进化器，反思固化为新能力

## 许可证

Apache License 2.0

## 状态

积极开发中（Pre-Alpha）。API 可能变动。
