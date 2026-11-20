# SOMA v2.0.39 测试报告

## 版本
- **soma-wisdom 2.0.39**（口径统一下放：基准记录自解释）
- 2026-11-20

## 本次变更

三个可变因素里只有一个曾被完整记录：`caliber`（算法版本）和
`mem_precision_applicable`（**false 时该项被剔除、分母权重放大**）都缺失。
同一份库、同一版本，仅因路径不同就 82.8 vs 68.7，而记录看不出原因。

### `build_benchmark_record()` + schema

`benchmark-record/1`，含 caliber / eval_path / eval_user_id /
wisdom.items / wisdom.weights / mem_precision_applicable（逐轮）/
unstable_applicability。

**落库与对外结构用同一个函数生成**——`record_multi_benchmark` 内部调用，
`generate_json_report` 嵌入。下游踩过的 caliber 丢失就是两处各写一份导致的。

### 适用性：只标记不修正

逐轮数组 + 不一致时 `unstable_applicability` / `partial`。
不强制全子项参与（那会把「测不出来」当成「测得差」）。

### 默认路径不改

仍是 namespaceless，空值记 `"unknown"` 并 warning。改默认会让老脚本静默换路径。

## 新增测试（+12）

| 文件 | 数量 | 覆盖 |
|------|------|------|
| `tests/test_benchmark_record.py` | 12 | 字段齐全；caliber 缺失→unknown；items/weights 保留 values；applicable 逐轮 + 不一致标记；落库结构与记录一致（2 条）；旧顶层键保留；门面暴露 |

### 注入验证

```
record_multi_benchmark 改成手写结构（两处各写一份）
  → test_storage_json_equals_record 红
  → test_storage_accepts_prebuilt_record 红
```

## 真实运行验证（本地 60 条库，runs=2，user_id=u1）

```
caliber: v2-normalized
eval_path: per_user | eval_user_id: u1
warmup: {'performed': True, 's': 2.09}
wisdom.items 键:   7 项（含 mem_precision）
wisdom.weights 键: 6 项（不含 mem_precision）
mem_precision_applicable: [False, False]
unstable_applicability: False
```

items 与 weights 的项数差异就是「剔除 + 重分配」的直接证据。

## 全量测试（3 轮）

```
1418 passed in 147.00s
1418 passed in 148.23s
1418 passed in 147.16s
```

原有 1406 + 新增 12 = 1418，**三轮零回归**。
（首轮曾出现 4 条失败：`run_multi_benchmark` 里误用了未定义的 `eval_path`，
已修并重跑。）

## 待下游验证

1. `record_multi_benchmark` 落库的 `multi_run_stats_json` 现在有
   `caliber` / `wisdom.items` / `wisdom.weights` / `mem_precision_applicable`
2. 旧记录读取不受影响（新增字段缺失时按 unknown / 空处理）
