# SOMA API 稳定性承诺

v0.4.0 起，以下公共接口遵循语义化版本承诺：**主版本号变更前不破坏向后兼容**。

## 冻结接口（承诺兼容至 1.0.0）

### SOMA 门面类

| 方法 | 签名 | 说明 |
|------|------|------|
| `SOMA()` | `(framework_config, llm, use_vector_search, persist_dir, recall_threshold, top_k)` | 构造函数，新增参数只能带默认值 |
| `.respond(problem)` | `str → str` | 完整智者管道，返回合成答案 |
| `.chat(problem)` | `str → dict` | 结构化对话，返回 foci/activated/answer/weights |
| `.remember(content, context, importance)` | `→ str` | 写入情节记忆，返回记忆 ID |
| `.remember_semantic(subject, predicate, object_, confidence)` | `→ None` | 写入语义三元组 |
| `.query_memory(query, top_k)` | `→ list[dict]` | 搜索记忆库 |
| `.decompose(problem)` | `→ list[Focus]` | 思维拆解 |
| `.reflect(task_id, outcome)` | `→ None` | 反馈闭环 |
| `.evolve()` | `→ list[str]` | 触发自我进化 |
| `.get_weights()` | `→ dict` | 获取规律权重 |
| `.adjust_weight(law_id, new_weight)` | `→ bool` | 手动调权 |
| `.discover_laws()` | `→ dict | None` | 发现新规律候选 |
| `.approve_law(candidate)` | `→ bool` | 审批新规律 |
| `.stats` | `→ dict` | 只读属性，记忆库统计 |

### 数据模型

| 类 | 字段 | 稳定性 |
|----|------|:--:|
| `Focus` | `law_id, dimension, keywords, weight, rationale` | 冻结 |
| `MemoryUnit` | `id, content, source, importance, access_count` | 冻结 |
| `ActivatedMemory` | `memory, activation_score, source` | 冻结 |

### 工厂函数

| 函数 | 签名 | 稳定性 |
|------|------|:--:|
| `create_soma_tool()` | `→ BaseTool` | 冻结 |
| `load_config(path)` | `→ FrameworkConfig` | 冻结 |

### 配置

| 类 | 稳定性 |
|------|:--:|
| `SOMAConfig` | 冻结 — 字段可新增不可移除 |

### v2.0.19 新增：记忆管理与真实用量

| 方法 | 签名 | 说明 |
|------|------|------|
| `.memories` | `-> MemoryApi` | 只读属性，记忆管理单一出口（见下表） |
| `.token_usage` | `-> dict` | 只读属性，累计真实 token 用量快照 |
| `.recent_usage(n)` | `-> list[dict]` | 最近 n 次调用明细（最新在前） |
| `.usage` | `-> UsageRecorder` | 只读属性，`on_usage(cb)` / `reset()` |

`MemoryApi`（经 `soma.memories` 取用，不要自己 new）：

| 方法 | 说明 |
|------|------|
| `.list(user_id, agent_id, nature, min_importance, days, after, order_by, limit, preview)` | 键集游标分页列举；`order_by` = recent / importance |
| `.get(memory_id, user_id)` | 读一条全文；非本人返回 None |
| `.search(query, top_k, user_id, agent_id, group_id, max_age_days)` | 语义检索，与 `query_memory` 同一召回链路 |
| `.update(memory_id, user_id, content, importance, nature, context)` | 改字段；content 变了连带重算 hash 与向量 |
| `.delete(memory_id, user_id, hard, reason)` | 删除，**默认归档**（可 restore）；`hard=True` 才真删 |
| `.archived(...)` / `.restore(memory_id, user_id)` | 最近删除 / 反悔（恢复时重建向量） |
| `.export_memories(user_id, nature, path, order_by, batch, limit)` | 导出；给 `path` 则流式写 NDJSON，不入内存 |
| `.iter_memories(...)` | 生成器逐批遍历，供迁移与同步 |

**共同约定**：`user_id=""` 表示该维度不限（单租户常态）；多租户必须显式传，
否则等于全库可见 —— 与 `query_by_filters` 一致。跨用户读写一律返回「不存在」
而不是「无权限」，避免泄露 id 归属。

**游标不可跨 `order_by` 复用**（抛 `ValueError`），也不会因中途增删而错位。

→ [记忆管理与真实用量](guides/memory-management_zh.md)

### v2.0.19 新增：数据模型

| 类 | 字段 | 稳定性 |
|----|------|:--:|
| `TokenUsage` | `prompt_tokens, completion_tokens, total_tokens, model, user_id, purpose, latency_ms, estimated, timestamp` | 冻结 |

`estimated=True` 表示该条由字符估算兜底（provider 未返回 usage）—— **不可用于
计费**。SOMA 一定把这个标记带到出口，接入方必须区分。
## 高级接口（稳定但不推荐直接使用）

这些类暴露给需要深度定制的用户，接口保持稳定但内部实现可能优化：

- `SOMA_Agent` — Agent 编排器
- `MetaEvolver` — 进化引擎
- `LawDiscovery` — 规律发现
- `SOMAEmbedder` — 向量嵌入

## 内部接口（可能变化）

以下模块的 API 不承诺兼容：

- `soma.memory.*` — 记忆存储实现细节（**请走 `soma.memories`，不要穿透 `_conn` 拼裸 SQL —— v2.0.19 起已有正式接口）**
- `soma.hub` — ActivationHub 管道
- `soma.engine` — WisdomEngine
- `soma.vector_store` — 向量搜索后端
- `soma.benchmarks` — 基准测试
- `soma.competitors` — 竞品对比

## 弃用流程

如需变更冻结接口：
1. 旧接口标记 `@deprecated`，保留至少一个次版本
2. 新接口在同一个次版本中提供
3. 下一个主版本移除弃用接口

## 版本对应

| 版本 | 承诺期 |
|------|--------|
| 0.4.x | 冻结至 1.0.0 |
| 1.0.0+ | 严格遵守 SemVer |
