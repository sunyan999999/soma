# 记忆时效 —— 三层机制，以及该依赖哪一层

*适用于 soma-wisdom ≥ 2.0.15*

把记忆注入 LLM 时，最难察觉的故障是 **模型把旧状态当成当前状态**：

> 用户（3 个月前）：「我最近睡眠不好。」
> LLM 今天：「既然您一直睡眠不好，这里有些建议……」← 错了，那是旧状态

SOMA 用三个独立机制处理这件事。它们**不是同一道防线的三层** —— 作用阶段不同，
其中一层是兜底而不是主防线。分不清会导致接入方式选错。本文是这张地图。

## 三层机制

| # | 机制 | 作用位置 | 效果 |
|---|------|----------|------|
| 1 | **近因衰减** `exp(-days/7)` | 打分阶段，激活阈值之前 | 旧记忆分数被压低，**直接掉出召回** |
| 2 | **`max_age_days`** | 查询期硬过滤 | 「只要最近 N 天」 |
| 3 | **`is_stale`**（仅 nature=`state`） | `explain_activation` 输出，召回之后 | 标记被召回的状态记忆可能已过时 |

### 1. 近因衰减 —— 真正的主防线

每条记忆的激活分数都会乘上一个 **半衰期 7 天** 的指数衰减：

| 年龄 | 权重 |
|------|------|
| 0 天 | 1.00 |
| 3 天 | 0.65 |
| 7 天 | 0.37 |
| 14 天 | 0.14 |
| 30 天 | 0.014 |
| 40 天 | **0.003** |

**这才是真正让旧记忆进不来的机制。** 到第 30 天，记忆只剩不到 2% 的权重 —— 远低于
SOMA 默认激活阈值。一条 40 天前的记忆不是「以低分被召回」，而是**根本不会被召回**，
哪怕 importance 是 0.95。

> **推论**：如果你打算靠 `is_stale` 去拦远期状态记忆，它几乎永远不会触发 ——
> 30 天以上的记忆早被衰减清出去了。`is_stale` 是兜底，不是主防线。

### 2. `max_age_days` —— 需要显式窗口时用它

衰减是软的、基于分数的机制。当你需要硬截断 —— 「我只要这个月的」—— 传 `max_age_days`：

```python
from soma import SOMA

soma = SOMA()

# 只看 30 天内；更早的直接被过滤掉
results = soma.query_memory("睡眠", top_k=5, max_age_days=30)

# 不传窗口（默认）—— 衰减依然生效，但不做硬过滤
results = soma.query_memory("睡眠", top_k=5)
```

返回项都带时间元数据：

```python
for item in results:
    print(item["age_days"], item["timestamp"], item["nature"], item["is_stale"])
```

当**问题本身**带时间约束时用 `max_age_days`。别把它当通用安全网 —— 那是衰减的活。

### 3. `is_stale` —— 兜底

`nature` 标记一条记忆是什么性质的东西：

| `nature` | 含义 | 例子 | 时效性 |
|----------|------|------|--------|
| `state` | 会变化的状态 | 「最近睡眠不好」「焦虑」「这周在北京」 | **强** |
| `fact` | 知识、技能、特质 | 「会写 Python」「偏好简洁接口」、wiki 内容 | 无 |
| `event` | 发生过的事（默认） | 「参加了设计评审」 | 弱 |

`state` 记忆超过 30 天（`STATE_TTL_DAYS`）后，`explain_activation` 返回
`is_stale = True`。用它来软化注入措辞：

```python
for item in soma.query_memory("睡眠", top_k=5):
    if item["nature"] == "state" and item["is_stale"]:
        # 40 天前的状态 —— 当历史讲，不当现状讲
        prompt += f"[{int(item['age_days'])} 天前，可能已变化] {item['content_preview']}\n"
    elif item["nature"] == "event":
        prompt += f"[{int(item['age_days'])} 天前] {item['content_preview']}\n"
    else:  # fact —— 无时效
        prompt += f"{item['content_preview']}\n"
```

**`is_stale` 真正有用的场景**：10–30 天前的状态记忆。它还能过激活阈值（10 天衰减约
0.24），所以**确实会被召回并注入** —— 没有这个标记，LLM 很可能当成现状讲。
这才是兜底机制发挥价值的窗口。

**它管不了的**：30 天以上的记忆。衰减早已把它们压到召回阈值之下，
`is_stale` 根本没机会在它们身上执行。

## 正确标注记忆

写入时知道性质就标上：

```python
soma.remember("用户最近睡眠不好", nature="state")
soma.remember("用户会写 Python", nature="fact")
soma.remember("用户参加了设计评审")            # 默认 event
```

代码记忆默认 `fact`（代码技能不会过期）：

```python
soma.remember_code("def add(a, b): return a + b", file_path="calc.py")
```

## 回填存量记忆

如果你的库早于 `nature`，或者全部还是默认的 `event`，用内置重分类工具。
**默认 dry-run 只预览**，落盘前自动备份：

```bash
# 预览 —— 不改任何东西
soma reclassify

# 落盘（备份写到 <记忆库目录>/nature_backups/）
soma reclassify --apply

# 回滚一次重分类
soma reclassify --rollback ~/.soma/shared/nature_backups/nature_backup_20260911-134025.json
```

Python 调用：

```python
print(soma.reclassify_nature())              # dry run
print(soma.reclassify_nature(dry_run=False)) # 落盘 + 自动备份
soma.rollback_nature(backup_path)
```

规则基于关键词（零 LLM 调用），可完全替换：

```python
from soma.nature import NatureClassifier

clf = NatureClassifier(
    state_keywords=("失眠", "焦虑", "偏头痛"),
    fact_keywords=("会", "擅长"),
    fact_min_len=300,          # 长文档视为知识
    fact_sources=("wiki", "knowledge", "doc"),
)
print(clf.classify("用户会写 Rust", {}))   # 'fact'
soma.reclassify_nature(classifier=clf, dry_run=False)
```

默认只处理 `nature` 仍为 `event` 的记忆 —— 已分类的（无论是你标的还是人工修的）一律不动。
传 `only_nature=None` 可覆盖。

## 长驻进程：`reload()`

如果另一个进程往同一个记忆库写数据（CLI、另一个 Agent、批处理任务），长驻实例需要
刷新内存里的向量索引。SQLite 读取本身是实时的，滞后的是 faiss 索引。

```python
stats = soma.reload()
# {'reloaded_vectors': 26574, 'total': 26574}
```

注意 `similarity_search` 自身在「索引计数与 DB 计数不一致」时已经会自愈重建，
所以单纯新增的记忆通常在下一次搜索就会被纳入。`reload()` 用于**想立刻生效**的场合，
并且能兜住自愈漏掉的情况：外部进程删 N 条又加 N 条，总数不变 —— 索引会留着已删向量、
看不到新向量，直到你手动 reload。

## 小结

- **近因衰减是主防线。** 它静默清掉旧记忆；「40 天前的状态」这类问题靠它就能解决。
- **`max_age_days`** 是给带时间约束的问题用的显式窗口，不是安全网。
- **`is_stale` 是兜底**，覆盖 10–30 天这个「状态记忆仍会被召回」的窗口。
  它不是拦远期记忆的手段 —— 那些衰减早就拦掉了。
