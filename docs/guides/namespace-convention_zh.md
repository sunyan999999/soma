# 语义三元组的 namespace 约定 —— `''` 只放真正的全局事实

*适用于 soma-wisdom ≥ 2.0.33*

一句话结论：

> **`namespace=''` 是「全局共享」。它只该放真正的事实。
> 导航图、关系图、文章关联这类「边」必须用独立 namespace。**

违反这一条的后果是**静默的**：分数看起来完全正常，但用户自己的记忆被挤掉了。

## 一个真实案例

下游生产环境（162 用户、32k 条记忆）把 wiki 文章的关联图写进了语义库，
**没有传 namespace**，于是落到默认值 `''`：

```
15,312 条三元组中 15,299 条（99.9%）是导航关系
  关联概念 7,306 (47.7%) / 参考指南 5,245 (34.3%) / 关联人物 2,748 (17.9%)
真正的事实性三元组只有 13 条
```

在 `include_global=True` 打开之后，同 20 题的前后对比：

| 指标 | 关闭全局 | 打开全局 |
|------|----------|----------|
| 语义激活占比 | 0% | **70%** |
| 情节记忆激活条数 | 192 | **58（被挤掉 70%）** |
| 被激活全局三元组的 LLM 相关性 | — | 直接相关 2% / 弱相关 44% / **无关 54%** |

分数面板看不出来（wisdom 只从 77.6 掉到 77.6），但「越用越懂你」这件事被
悄悄打断了 —— 用户自己的情节记忆被 1.5 万条导航边挤出了候选池。

把这些边迁移到 `namespace='wiki_graph'` 之后，同 20 题：

```
语义激活占比  70% → 1.0%（2/200）
情节记忆激活   58 → 189（94.5%）
剩下 2 条语义正好是相关且正确的事实三元组
```

## 为什么会这样：两个不同的「空 namespace」

这是最容易踩的地方 —— **写入时的 `''` 和查询时的 `''` 不是一回事。**

| 场景 | `namespace=''` 的含义 |
|------|----------------------|
| **写入** `remember_semantic(..., namespace='')` | 这条是全局知识，所有用户可见 |
| **查询** `query_by_keywords(..., namespace='')` | **不过滤**（历史语义，返回所有用户的三元组） |

所以想让用户同时看到「自己的三元组 + 全局知识」，不能靠传空串，
要显式传 `include_global=True`：

```python
# ❌ 错误：传空串是「不过滤」，会跨用户返回
sem.query_by_keywords(keywords, namespace="")

# ✅ 正确：查自己的，同时纳入全局事实
sem.query_by_keywords(keywords, namespace=user_id, include_global=True)
#   SQL 变成 AND (st.namespace = ? OR st.namespace = '')
```

> 这两段 SQL 是**独立构造**的（FTS 路径 + 短词 LIKE 路径），改一处漏一处
> 会导致「3 字以上查得到全局知识、2 字词查不到」。2.0.33 修过一次。

## 约定

| namespace | 放什么 | 例子 |
|-----------|--------|------|
| `''`（空） | **真正的全局事实** | 「数字分身 —基于→ 命理八字」 |
| `wiki_graph` | 文章关联/导航图 | 「《某文章》 —关联概念→ 经络」 |
| `user_id` / `agent_id` | 单个用户或 agent 的私有知识 | 用户自己录入的偏好 |
| `group_id` | 团队共享 | 团队规范 |

判断标准只有一条：

> **这条三元组能否直接回答一个用户问题？**
> 能 → 事实，可以进 `''`。不能（只是「A 和 B 有关」）→ 图边，用独立 namespace。

## 迁移 namespace 不影响图扩展

这点值得单独说，因为它让迁移变成一个**低风险操作**。

关键词扩展走的是 `MemoryCore._expand_via_semantic_graph` →
`SemanticStore.expand_query_terms`，遍历的是进程内的 NetworkX 图
（`self.graph`），**不按 namespace 过滤**：

```python
# core.py
graph = self.semantic.graph
matched = [kw for kw in keywords if kw in graph]
expanded = self.semantic.expand_query_terms(matched, depth=2, max_terms=...)
```

所以把 1.5 万条边从 `''` 挪到 `wiki_graph`：

- ✅ 图扩展完全不受影响（`expand(命理分析) → ['日主五行']` 照旧）
- ✅ 这些边不再被当知识注入 prompt
- ✅ 用户的情节记忆重新回到候选池

迁移只需要一条 `UPDATE semantic_triples SET namespace='wiki_graph' WHERE ...`，
不用重建索引。

## 怎么验证自己有没有这个问题

不想等到用户抱怨「它不懂我了」才发现。抽一批真实问句做前后对照：

```python
# 1. 开 / 关 include_global 各跑一遍同一批问题
# 2. 统计语义通道激活占比
sem_hits = sum(1 for am in activated if "semantic" in am.source.lower())
ratio = sem_hits / max(1, len(activated))

# 3. 语义激活占比健康值：个位数百分比
#    超过 30% 基本可以确定语义库里混进了图边
```

如果占比异常，按这个顺序查：

1. `SELECT namespace, COUNT(*) FROM semantic_triples GROUP BY namespace`
   —— `''` 里有多少是导航关系？
2. 抽 20 条被激活的全局三元组，让 LLM 判相关性
   —— 无关占比超过 30% 就该隔离了

## 已知缺口

目前语义库**没有区分「事实」和「图边」的类型字段**。上面的约定靠
namespace 手工维护，写错了不会报错。

后续版本计划增加 `kind`（`fact` / `relation`），在注入阶段按类型过滤，
让这一类错误在结构上不可能发生。在此之前，**写入方是自己 namespace 的
唯一守门人**。

---

*本文的案例数据来自下游生产环境实测（2026-11），已获授权引用。*
