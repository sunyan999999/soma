# v2.0.39 方案：口径统一下放

*状态：待确认 · 2026-11-20*

## 一、要解决的问题

现在是三个可变因素叠在一起，而**只有一个被完整记录**：

| 因素 | 影响 | 现在是否落库 |
|---|---|---|
| `caliber`（评分算法版本） | wisdom 的算法口径 | ❌ 只在单次结果里，多轮记录没有 |
| `eval_path`（评估路径） | 候选集不同，分数差 14 分 | ✅ 2.0.35 加了 |
| `mem_precision_applicable` | **false 时该项被剔除，分母权重整体放大** | ❌ 没落库 |

第三条是最隐蔽的。同一套数据、同一版本，仅因为路径不同：

```
namespaceless：被 wiki 图边淹没 → tag 交集 0 → applicable=false
               → mem_precision 权重被移除，其余六项按比例放大
               → wisdom 82.8（虚高）
per_user     ：候选干净 → applicable=true
               → wisdom 68.7（真实）
```

下游踩过一次：他们把面板写入口径改成四维中位后，`scores` 里不再带
`caliber`，record 把新记录全写成 `v1-legacy`。这是「记录模板缺失」
导致的，不是他们的问题。

## 二、设计目标

> **任何一次记录都必须自解释：看一条记录就能知道「这个分数是用什么口径、
> 走哪条路径、哪些子项参与了」——不需要去翻当时的代码版本。**

三条具体规则：

1. **口径元数据必填**：`caliber` / `eval_path` / `eval_user_id` 缺失时
   写 `"unknown"` 并打 warning，**不静默**
2. **子项与权重一起存**：`wisdom.items` / `wisdom.weights` 逐轮记录，
   否则「82.8 与 68.7 差在哪」永远只能靠猜
3. **适用性逐轮记录**：`mem_precision_applicable` 不是布尔常量，四次运行
   可能不一致 —— 不一致本身就是信息

## 三、新增统一记录结构

```python
# soma/benchmarks.py
BENCHMARK_RECORD_SCHEMA = "benchmark-record/1"

def build_benchmark_record(multi_result) -> dict:
    """把 MultiRunResult 转成自解释的记录（下游写库/出报告都用它）。"""
```

结构：

```json
{
  "schema": "benchmark-record/1",
  "version": "2.0.39",
  "timestamp": 1763...,
  "caliber": "v2-normalized",
  "eval_path": "per_user",
  "eval_user_id": "1",
  "warmup": {"performed": true, "s": 1.97},
  "runs": 4,
  "scores": {
    "wisdom": {"mean": 68.6, "std": 0.2, "values": [...], "stability": "stable"},
    "overall": {...}, "memory": {...}, ...
  },
  "wisdom": {
    "items":   {"coverage": 1.0, "law_recall": 0.7619, "mem_precision": 0.0568,
                "relevance": 0.139, "cross_domain": 1.0, "efficiency": 0.31, ...},
    "weights": {"coverage": 0.22, "law_recall": 0.18, ...},
    "mem_precision_applicable": [true, true, true, true],
    "unstable_applicability": false,
    "avg_activate_ms": {"mean": 309.1, "max": 315.8}
  }
}
```

字段来源逐轮收集，`items` / `weights` / `applicable` 取均值时要保留原始数组
（`values`），否则又变成「只有一个数，看不出分布」。

## 四、API 变更

### `MultiRunResult` 补字段

```python
caliber: str = ""
eval_user_id: str = ""
wisdom_items: Dict[str, RunStatistics] = ...
wisdom_weights: Dict[str, RunStatistics] = ...
mem_precision_applicable: List[bool] = ...
```

`run_multi_benchmark` 从每轮的 `run.wisdom.details` / `normalize_scores`
的返回里收集。

### `record_multi_benchmark` 改用它

```python
def record_multi_benchmark(self, multi_result, record: Optional[dict] = None) -> int:
    # 没传 record 就内部 build，保证落库与对外结构一致
```

`multi_run_stats_json` 直接存 `build_benchmark_record(...)` 的结果。
旧的顶层字段（`runs` / `total_duration_s` / `warmup_s` / `eval_path`）
继续保留，避免下游已有解析失效。

### 新增 `SOMA.benchmark_record(...)`

下游不必自己拼：

```python
result = run_multi_benchmark(factory, runs=4, user_id="1")
record = soma.benchmark_record(result)      # 或从 benchmarks 直接 import
analytics.record_multi_benchmark(result, record)
```

## 五、`mem_precision_applicable` 的处理

不做「强行让分数可比」的改造 —— 那会把真实差异抹平。

只做三件事：

1. **逐轮记录** `mem_precision_applicable` 数组
2. **不一致时标 `unstable_applicability: true`**，并在 wisdom 上加
   `partial: true`（表示分母在几次运行间变过）
3. **文档明确**：`applicable=false` 的分数**不能**与 `applicable=true` 的
   分数直接比较，哪怕 caliber 和 eval_path 都相同

> 备选方案（不推荐）：强制所有子项参与，不适用的记 0。分数可比了，但
> 会把「测不出来」当成「测得差」，方向是错的。

## 六、默认路径

**不改 `run_full_benchmark(user_id="")` 的默认值。** 理由：

- 改成必填会破坏现有调用
- 改成默认 `"1"` 之类是魔法值，更糟

改为**显式标注**：`eval_path` 为空时记录写 `"unknown"` 并打 warning；
报告里已经会显示 `eval_path`（2.0.35 加的）。

下游要 per_user 就传 `user_id` —— 他们的面板已经这么做了。

## 七、兼容性

| 场景 | 保障 |
|---|---|
| 旧记录（无 caliber/items） | 读取时补 `"unknown"` / 空数组，不报错 |
| 下游已有的 `multi_run_stats_json` 解析 | 旧顶层字段全部保留 |
| 直接调 `record_multi_benchmark(result)` | 内部自动 build，行为向后兼容 |

## 八、判据

| # | 判据 | 注入后应红 |
|---|---|---|
| 1 | 记录含 `caliber` / `eval_path` / `eval_user_id` | 删字段 → 红 |
| 2 | 记录含 `wisdom.items` 与 `wisdom.weights` 的逐轮数组 | 只存均值 → 红 |
| 3 | `mem_precision_applicable` 逐轮记录 | 只存一个 bool → 红 |
| 4 | 四次运行状态不一致时 `unstable_applicability=true` | 硬编码 false → 红 |
| 5 | `eval_path` 为空时写 `"unknown"` 并 warning | 静默写空串 → 红 |
| 6 | `record_multi_benchmark` 落库结构与 `build_benchmark_record` 一致 | 两处各写一份 → 红 |
| 7 | 旧记录读取不报错、补默认值 | — |

第 6 条防的是「对外一个结构、落库另一个结构」—— 下游踩过这个坑（record
管道与结果顶层不一致，导致 caliber 丢失）。

## 九、工作量

| 部分 | 规模 |
|---|---|
| `build_benchmark_record` + schema | ~110 行 |
| `MultiRunResult` 补字段 + `run_multi_benchmark` 收集 | ~50 行 |
| `record_multi_benchmark` 改造 | ~25 行 |
| `SOMA.benchmark_record` 暴露 | ~10 行 |
| 测试（7 条判据 + 注入验证） | ~150 行 |
| 文档（输出格式说明） | — |

一个版本的量，不动评分算法本身。

## 十、需要确认的三件事

1. **`mem_precision_applicable=false` 时怎么处理？**
   我建议只标记、不修正（分数不可比就明说）。
   备选是强制全子项参与（可比但会低估）。我倾向前者。

2. **要不要把「基准默认路径」改成 per_user？**
   我建议不改默认值，只标注。因为 `run_full_benchmark` 是底层 API，
   改默认会让所有老脚本静默换路径 —— 那比分数虚高更危险。

3. **`wisdom.items` 存均值还是逐轮全部？**
   我建议两者都存（`values` 数组 + 均值）。存储成本可忽略（几十个浮点数），
   但能看出「均值 0.139 是稳定在 0.139，还是 0.05~0.22 之间跳」。

---

*方案确认后实现；不改评分算法，只补齐「让分数能被正确解读」的元数据。*
