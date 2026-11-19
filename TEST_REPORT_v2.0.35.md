# SOMA v2.0.35 测试报告

## 版本
- **soma-wisdom 2.0.35**（评估路径 + 预热安全 + L1 时间量化）
- 2026-11-19

## 本次变更

下游在 2.0.34 上验证后发来四条，全部落地。

### 1. 预热 `close()` 打死共享实例（下游崩溃）

`run_multi_benchmark` 预热和每轮结束都 `close()`。下游 factory 返回进程级
共享实例 → 共享 SQLite 连接被关 → `sqlite3.ProgrammingError`。

- 新增 `dispose_agents: bool = False`（默认不关）
- CLI 显式传 `True`（它自己创建临时实例）

### 2. `run_full_benchmark(user_id=...)` + `eval_path`

两条路径同一份库 wisdom 差 14 分（82.8 vs 68.9）。原因：基准路径不过滤
命名空间，被 1.5 万条 `wiki_graph` 图边淹没，`mem_precision_applicable`
变 false，12 分重分配 → 虚高。

- `run_full_benchmark` / `run_wisdom_benchmark` / `run_multi_benchmark`
  均支持 `user_id`
- `eval_path` 回传到 `BenchmarkRun`、`MultiRunResult`、Markdown、JSON、
  `multi_run_stats_json`
- CLI 新增 `--user-id`

### 3. 预热覆盖 memory 维度

首轮残留 77ms（per_user 157ms）来自「第一次写入」。预热增加
「写 3 条 → 查 1 次 → 删干净」，且带 `user_id`。

### 4. `days` 量化到秒

下游 38 条抖动全部单调递减（时间函数）。`now = math.floor(...)` 后
同一秒内位级一致。新增 `docs/guides/activation-determinism_zh.md`
说明 L1/L2/L3 三层门槛。

## 新增测试（+8）

| 文件 | 数量 | 覆盖 |
|------|------|------|
| `tests/test_benchmark_eval_path.py` | 7 | per_user / namespaceless 判定；user_id 透传到 wisdom；eval_path 进两种报告；共享实例默认不被关；dispose_agents=True 全关；预热写/查/删且带 user_id；memory_sample 可关 |
| `tests/test_hybrid_stability.py` | +1 | 同一秒内两次激活分数逐位相同 |

### 注入验证

```
close() 改回无条件   → test_shared_instance_is_not_closed_by_default 红
user_id 不透传       → test_per_user_when_user_id_given 红
去掉 math.floor      → test_same_second_scores_are_bit_identical 红
```

## 全量测试（3 轮）

```
1379 passed in 170.76s
1379 passed in 158.97s
1379 passed in 144.44s
```

原有 1371 + 新增 8 = 1379，**三轮零回归**。
