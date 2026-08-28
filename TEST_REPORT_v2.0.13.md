# SOMA v2.0.13 测试报告

## 版本
- **soma-wisdom 2.0.13**（记忆时间感知优化）
- 2026-08-28

## 本次变更
1. **`explain_activation()` 返回时间信息**（`soma/hub/_core.py`）：`timestamp` / `age_days` / `memory_type` —— 记忆串台根因修复
2. **`query_memory()` 暴露 `max_age_days`**（`soma/agent.py` → `hub.activate` → `retriever.retrieve` → `memory.query` 四层透传）：时间窗口硬截断

## 新增测试（+5）
`tests/test_memory_time_aware.py`：
- `explain_activation` 返回 timestamp/age_days/memory_type ✓
- 远期记忆 age_days 正确反映年龄 ✓
- `query_memory(max_age_days)` 透传不抛错 + 时间字段保留 ✓
- 底层 `max_age_days` 硬截断远期记忆（40 天记忆被截掉）✓
- 端到端：`query_memory(max_age_days=30)` 不含远期记忆 ✓

## 全量测试
```
858 passed in 187.82s
```
- 原有 853 用例 + 新增 5 用例，**零回归**
- 覆盖：认知循环 / 三层记忆 / 多智能体 / 知识门控 / 向量索引一致性 / 时间感知等

## 验证亮点
- 真实场景复现：存一条 40 天前「睡眠不好」记忆 + 一条新「睡眠不错」记忆，`query_memory("睡眠", max_age_days=30)` 正确截断远期记忆，返回结果含 `age_days` 供接入方时间标注
- 记忆串台修复闭环：LLM 注入层现在能拿到记忆时间（`age_days`），不再把旧状态当当前状态

## wheel
- `dist/soma_wisdom-2.0.13-py3-none-any.whl`（262 KB）
