# SOMA v2.0.34 测试报告

## 版本
- **soma-wisdom 2.0.34**（基准首轮冷启动 + 图谱邻居封顶收一位）
- 2026-11-19

## 本次变更

### 1. `run_multi_benchmark` 增加不计分的预热阶段（修复 wisdom 虚低 5.8 分）

下游实测（2.0.33，`benchmark_runs id=187`，repeat=4）：

```
第 1 次 avg_activate 910.3ms → efficiency 0    → wisdom 71.8
后 3 次 avg_activate 210~213ms → efficiency 0.58 → wisdom 77.6
```

三笔进程级一次性成本只在首轮出现：ONNX 模型加载（构造时仅起后台线程）、
jieba 词典构建（约 0.4s）、嵌入器文本 LRU 为空。

- 新增 `_warmup_process_caches(agent, questions=3)`：同步等模型就位，再真跑
  几题把分词 / 编码 / 首次 SQLite 读一并触发
- `run_multi_benchmark(..., warmup=True, warmup_questions=3)`；预热用**用完
  即弃的 agent**，不产出分数、不计入 `runs`
- 预热失败只降级（警告后照常评测）
- `MultiRunResult` 新增 `warmup_performed` / `warmup_s`；Markdown、JSON、
  `benchmark_runs.multi_run_stats_json` 三处可见
- CLI 新增 `--no-warmup`

### 2. `_GRAPH_KEYWORD_CAP` 4 → 3

本地热态 A/B（50 题，同一实例，两轮重复取相同值）：

```
cap=4  召回 115 条  5.0ms/题
cap=3  召回 115 条  4.8ms/题
```

另两组独立构建的数据集同样 122/122、94/94。下游 32k 生产库结论一致
（召回几乎不变，单次再省约 8ms）。1 跳邻居权重高、排在前面，被截掉的
绝大多数是 2 跳。

## 新增测试（+13）

| 文件 | 数量 | 覆盖 |
|------|------|------|
| `tests/test_benchmark_warmup.py` | 8 | 预热在计分前执行且不计轮数；关闭预热不多建 agent；预热构造失败降级；题数上限；同步加载 embedder；已加载则跳过；数据集为空时退化为 encode；预热状态进入两种报告 |

### 注入验证

把 `if warmup:` 改成 `if False:` 后 **3 条变红**：

```
FAILED test_warmup_runs_before_scoring_and_is_not_counted
FAILED test_warmup_failure_does_not_break_the_run
FAILED test_warmup_info_reaches_both_reports
```

恢复后 8 条全绿。

## 文档

新增 `docs/guides/namespace-convention_zh.md`（语义三元组的 namespace 约定），
mkdocs nav 已加入。sdist 中包含该文档。

## 全量测试（源码目录内，4 轮）

```
（稳定性修复前）
1366 passed in 136.01s / 148.55s / 157.64s   # tmp/venv_218
1366 passed in 154.41s                        # soma-agent/.venv（约定环境）

（稳定性修复后）
1371 passed in 164.47s / 159.65s / 146.45s    # soma-agent/.venv × 3 轮
```

## 装包冒烟（源码目录之外）

```
python -m build --no-isolation
  → soma_wisdom-2.0.34.tar.gz / soma_wisdom-2.0.34-py3-none-any.whl

wheel 内容检查（红线）
  顶层条目: ['soma', 'soma_wisdom-2.0.34.dist-info']
  soma_agent 泄漏: 无 ✓
  sdist: 不含 soma_agent；16 份 guides 文档，含新增的 namespace-convention_zh.md

pip install --no-deps --target %TEMP%\soma_smoke_234 <wheel>
cd %TEMP% 后运行 smoke.py
  soma 路径: ...\soma_smoke_234\soma\__init__.py   ← 确认不是源码
  版本: 2.0.34
  _GRAPH_KEYWORD_CAP: 3
  基本召回: 1 条
  include_global 全局语义命中: 1 条
  warmup 参数: True / 3
  预热函数可执行 ✓
```

- 原有 1358 用例 + 新增 13 用例（8 预热 + 5 稳定性）= 1371，**三轮零回归**
- `tests/test_keyword_cap.py` 8 条在 cap=3 下全绿（含
  `test_one_hop_neighbours_survive`：1 跳邻居不能被截掉）

## 附加修复：激活结果重复不稳定

原计划排到 2.0.35，本轮一并修了 —— 它和冷启动是两条独立的线，且同样静默。

拆出三个独立来源：

| # | 来源 | 修法 | 判据 |
|---|------|------|------|
| 1 | 检索 SQL 只按 `confidence DESC` / `timestamp DESC` 排序，并列无次键 | 补 `id DESC` / `rowid DESC` | `test_tie_returns_newest_ids`、`test_episodic_tie_break_is_id_desc` |
| 2 | 图扩展按权重排序，两档权重并列时取谁不定 | 次键按节点名 | （由端到端判据覆盖） |
| 3 | `relevance_potential()` 用当前时刻，而语义单元 timestamp 是查询时刻 | semantic 跳过近因衰减 | `test_semantic_relevance_is_time_invariant` |

外加 `decompose` 的关键词去重从 `set` 改为保序（`dict.fromkeys`）—— 原来
set 打乱了关键词顺序，而 `max_like_keywords` 截断假设主关键词在前。

### 实测前后（50 题，两次完整 run）

```
修复前：集合不同 1 题 / 顺序不同 6 题；cap3 与 cap4 召回差 1 条
修复后：集合不同 0 题 / 顺序不同 0 题；cap3 与 cap4 完全一致（123/123）
```

### 注入验证

```
去掉 SQL 次键        → test_tie_returns_newest_ids、
                       test_episodic_tie_break_is_id_desc 变红
去掉 semantic 分支   → test_semantic_relevance_is_time_invariant 变红
                       （0.6999999999815509 vs 0.6999999999761896）
```

## 待下游验证

预热在本地小库（百毫秒级）无法复现 910ms 现象，需下游在 32k 生产库上
用 `--full --runs 4` 复测，确认：

1. 第 1 次的 avg_activate 与后 3 次接近
2. wisdom 的逐次极差从 5.8 收窄到 1 以内
3. `multi_run_stats_json` 里 `warmup_performed=true`
