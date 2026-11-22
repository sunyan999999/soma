# SOMA v2.0.40 测试报告

## 版本
- **soma-wisdom 2.0.40**（nature 误判修复 + API 别名 + CLI 扫描说明）
- 2026-11-22

## 本次变更

### 修复 1：时间副词不是状态

下游 `reclassify --data-dir` 扫到 221 条 event→state 未 apply。复现后发现
状态词表里的四个时间副词（`今天 / 这周 / 最近在 / 目前在`）和一个中性名词
（`睡眠`）会误伤：

```
今天上午在家做饭，下午去的父母家   → state ✗
最近在学 Python 的异步编程         → state ✗
这周完成了三个需求评审             → state ✗
目前在做一个数据迁移项目           → state ✗
我在学习睡眠科学的相关知识         → state ✗
```

移除这 5 个词后 8/8 符合预期；真实状态（「今天又失眠了」「最近压力大」）
仍靠具体词命中。

### 新增 2：`classify_with_reason()` + `by_reason`

dry-run 输出命中原因：

```json
{"by_reason": {"state_keyword:失眠": 12, "default": 17850},
 "samples": [{"id": "...", "from": "event", "to": "state", "reason": "state_keyword:失眠"}]}
```

### 修复 3：模块级 API 别名

`soma.benchmark_record` / `soma.build_benchmark_record` 均可用
（此前只有 SOMA 方法与 benchmarks 模块里的函数）。

### 修复 4：CLI 帮助写清扫描对象

`reclassify` → episodic；`semantic-kind` → semantic。

### 文档：基准环境守卫

下游发现 RAG 重建期间跑基准，wisdom 68.5→66.7，看起来像正常波动。
已写进 CHANGELOG 作为使用建议。

## 新增测试（+12）

| 文件 | 数量 | 覆盖 |
|------|------|------|
| `tests/test_nature_reclassify.py` | +9 | 时间副词不判 state（5 条）；真实状态仍命中（2 条）；reason 返回命中词；默认 reason |
| `tests/test_nature_reclassify.py` | +1 | dry-run 输出 by_reason 与含 reason 的 samples |
| `tests/test_cli_data_dir.py` | +2 | 两个命令的帮助含扫描对象；模块级别名可调用 |

### 注入验证

```
把「最近在/目前在/这周/今天」加回状态词表
  → test_time_adverbs_are_not_state 4 条红
```

## 全量测试（3 轮）

```
1430 passed in 170.98s
1430 passed in 161.33s
1430 passed in 151.29s
```

原有 1418 + 新增 12 = 1430，**三轮零回归**。

## 待下游验证

1. 重跑 `soma reclassify --data-dir ...` dry-run，确认 `changed` 从 221 下降
2. 看 `by_reason` 分布，判断剩余项是否值得 apply
3. `soma.benchmark_record(result)` 三种写法都可用
