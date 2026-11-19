# SOMA v2.0.36 测试报告

## 版本
- **soma-wisdom 2.0.36**（预热覆盖评测维度集合 + memory 查询路径）
- 2026-11-19

## 本次变更

下游在 2.0.35 上验证后剩下的唯一问题：预热后首轮仍比稳态多 164ms/次。
他们的 cProfile 把范围缩到两处 —— SQL 耗时两遍持平（排除 FTS），
差异在于嵌入器 LRU（70 条唯一 dimension，10.7ms/条）与向量检索首次页缓存。

### 1. `warmup_dataset_size`（默认 15）

预热不再只拆 `warmup_questions`（3）题，而是拆到 wisdom first15 的深度，
把去重后的全部 `focus.dimension` 文本 encode 一遍。

### 2. memory 小样改用真实问题

从「查刚写的 3 条样本」改为「用数据集里的真实问题查一次」，
让向量索引首次页读提前发生。

## 实测（本地 800 条库，首轮 15 题）

| 预热模式 | 预热耗时 | 首轮 15 题总耗时 | activate 中位 | max |
|---|---|---|---|---|
| 2.0.35（拆 3 题） | 0.99s | **1,260ms** | 79.9ms | 131.9ms |
| 2.0.36（拆 15 题） | 1.43s | **335ms** | 20.6ms | 34.3ms |

首轮降 73%；预热多花 0.44s，净收益 0.93s。

## 新增测试（+2）

| 文件 | 数量 | 覆盖 |
|------|------|------|
| `tests/test_benchmark_warmup.py` | +2 | 全部 dimension 被编码；同一文本去重只编码一次 |

`test_warmup_question_count_is_respected` 改为
`test_warmup_activate_count_is_respected`（questions 与 dataset_size 已解耦）。

### 注入验证

```
去掉 _encode_all_dimensions(...) →
  test_all_dimensions_are_encoded 红
  test_dimension_encode_deduplicates 红
```

## 全量测试（3 轮）

```
1381 passed in 175.76s
1381 passed in 171.55s
1381 passed in 172.29s
```

原有 1379 + 新增 2 = 1381，**三轮零回归**。

## 待下游验证

以 DSH 给的基线为准：**首轮 15 题合计 ≤4.8s**（他们在 32k 库上当前 7.05s）。
本地小库的 1,260→335ms 只能证明机制有效，绝对量级以生产为准。
