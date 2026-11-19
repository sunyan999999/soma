# 激活确定性 —— 排序稳定 ≠ 分数稳定

*适用于 soma-wisdom ≥ 2.0.35*

同一句问题问两次，SOMA 召回的记忆应该一致。这条不变量在 2.0.34 ~ 2.0.35
之间被彻底钉住，但需要先说清楚**哪一层成立、哪一层不成立**——否则验收写错了，
要么放过真问题，要么永远修不完。

## 三层确定性

| 层 | 断言 | 现状 |
|---|---|---|
| **L1 位级** | 同一 memory id 的 `activation_score` 多次调用完全相等 | **同一秒内成立**；跨秒不成立（见下） |
| **L2 序列** | 激活 id 的序列（含顺序）完全一致 | ✅ 成立 |
| **L3 集合** | 候选集合（忽略顺序）完全一致 | ✅ 成立 |

**验收门槛应该定在 L2 / L3。** L1 只在「同一秒内重复调用」这个前提下才是硬指标。

## 为什么 L1 跨秒不成立

`relevance_potential()` 里有近因衰减：

```python
days = max(now - memory.timestamp, 0) / 86400.0
recency = math.exp(-days / effective_half_life())
```

`now` 是查询时刻。两条查询相隔 0.5 秒，`days` 就大了一点，`recency` 就小了
一点。这是**设计**——「越近越重要」本来就是时间函数，不是 bug。

2.0.35 之前的问题是这个漂移量级**恰好落在排序的敏感区**：

```
同一次 activate 内，两条候选分数差 < 1e-6
跨查询 recency 漂移 1e-9 ~ 1e-6
→ 谁在前就翻转了
```

实测（下游 32k 库，38 条抖动）：

```
38/38 全部单调下降（0.95685673 → 0.95685630 → 0.95685602）
其中 semantic 三元组 0 条（已跳过近因衰减）
```

所以它看起来像「随机抖动」，实际是**确定性的时间漂移**。这也解释了为什么
「同一秒内连跑」测不出来、而「间隔一段时间再跑」就能复现。

## 2.0.35 做了什么

| 改动 | 效果 |
|---|---|
| `now` 量化到 `math.floor(...)` | 同一秒内 L1 位级一致 |
| 语义三元组跳过近因衰减 | 知识没有过期语义，语义分数完全恒定 |
| 检索 SQL 补 `id DESC` / `rowid DESC` | 完全并列时按插入顺序，L2/L3 稳定 |
| 图扩展排序补名称次键 | `max_terms` 截断不再看迭代顺序 |
| `activate` 的 Python 排序补 `memory.id` 次键 | 多 Focus 合并后仍然稳定 |

> ⚠️ 仍有近并列（分数差 < 1e-6）的候选会在**跨秒**调用时换位。这是时间
> 衰减的固有结果。如果你需要严格可复现的评测，请在同一秒内批量调用，
> 或固定 `now`（评测框架可以 monkey-patch `datetime`）。

## 怎么验

```python
foci = agent.decompose("你的问题")          # 只拆一次
runs = [agent.hub.activate(foci) for _ in range(3)]

# L2：序列
assert len({tuple(a.memory.id for a in r) for r in runs}) == 1

# L3：集合
assert len({frozenset(a.memory.id for a in r) for r in runs}) == 1

# L1：同一秒内位级
assert len({tuple(a.activation_score for a in r) for r in runs}) == 1
```

`tests/test_hybrid_stability.py::TestTieBreakStability` 是这套判据的落地版本。

## 一条实践建议

不要用「跑两次比分数」来验版本改进 —— 噪声（时间漂移）会淹没真实差异。
要看**排序**（L2/L3）和**均值**（多轮中位），不要看单次的浮点数值。

---

*本文的 38 条抖动数据来自下游生产环境实测（2026-11-19，episodic 32,267 条）。*
