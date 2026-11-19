# v2.0.37 方案：语义三元组的 `kind`（事实 / 关系）

*状态：待确认 · 2026-11-20*

## 一、要解决的问题

语义库目前只有一个隔离维度 `namespace`，没有「这条数据用来做什么」的标记。
下游踩过的坑（2026-11-19，`req-20261119-wiki-graph-pollution`）：

```
15,312 条三元组里 15,299 条（99.9%）是 wiki 文章关联图
它们落在 namespace=''（全局）→ include_global 一开
→ 每次激活注入 70% 是「文章 A 关联概念 B」的导航边
→ 用户自己的情节记忆被挤掉 70%（192 → 58）
→ 而分数面板看不出来（wisdom 77.6 → 77.6）
```

下游已经在数据层用 `namespace='wiki_graph'` 隔离修好了。但那次修复依赖
**写的人记得传 namespace** —— 漏传一次，下一次 `include_global` 就会复发，
而且仍然静默。

`kind` 要把这件事从「靠约定」变成「结构上可过滤」。

## 二、关键设计：kind 只管注入，不管扩展

语义库有两条完全独立的消费路径：

| 路径 | 入口 | 用什么 | 输出 |
|---|---|---|---|
| **图扩展** | `_expand_via_semantic_graph` → `expand_query_terms` | 进程内 NetworkX 图 | 邻居节点名（加入关键词） |
| **知识注入** | `MemoryCore.query` → `query_by_keywords` | SQL | `MemoryUnit`（进 prompt） |

**污染只发生在第二条。** 图扩展只用节点名，不看边是什么类型 —— 而且它
本来就是辅助通道，多几个邻居词不构成污染。

所以 `kind` 的设计是：

> **`kind` 只在「注入」时过滤。图扩展完全不受影响。**

这与 `namespace` 形成互补：

| 维度 | 回答的问题 | 影响范围 |
|---|---|---|
| `namespace` | 谁**能看见** | 两条路径都受影响（图扩展虽然不查 SQL，但节点来自同一张内存图） |
| `kind` | 这条**用来做什么** | 只影响知识注入 |

## 三、Schema

```sql
ALTER TABLE semantic_triples ADD COLUMN kind TEXT NOT NULL DEFAULT 'fact';
CREATE INDEX IF NOT EXISTS idx_semantic_kind ON semantic_triples(kind);
```

- 用 `try/except sqlite3.OperationalError` 做幂等迁移（与 `namespace` 同款）
- 旧库自动补列，已有行全部是 `'fact'`

**为什么默认 `fact`**：`namespace=''` 的既定语义就是「真正的全局事实」
（见 `docs/guides/namespace-convention_zh.md`）。默认值与这个约定一致；
写导航图的人应该显式声明自己的意图。

**取值不锁死**：`fact` / `relation` 是约定值，但字段接受任意字符串，
下游可用 `rule` / `preference` / `nav` 等。过滤按调用方给的白名单匹配。

## 四、API 变更

### 写入

四层链路各加一个参数，默认值 `"fact"`（旧调用行为不变）：

```python
SOMA.remember_semantic(subject, predicate, object_, confidence=1.0,
                       namespace="", kind="fact")
SOMA_Agent.remember_semantic(...)      # 透传
MemoryCore.remember_semantic(...)      # 透传
SemanticStore.add_triple(..., kind="fact")
```

去重键保持不变 `(subject, predicate, object, namespace)` —— 同一条边
改 `kind` 不算新边，会直接返回（不更新）。**这是有意的**：kind 是写入时的
意图声明，改了意图应该先删再写，而不是静默覆盖。

### 查询

```python
SemanticStore.query_by_keywords(..., include_kinds: Optional[Sequence[str]] = None)
```

| 值 | 行为 |
|---|---|
| `None`（默认） | **不过滤**，完全向后兼容 |
| `("fact",)` | 只返回事实 |
| `()` 或 `[]` | 视为 `None`（空集合不表达「什么都不要」，那是 `top_k=0`） |

### 注入（`MemoryCore.query`）

新增配置项：

```python
SOMAConfig.semantic_inject_kinds: Optional[tuple] = ("fact",)
```

`MemoryCore.query` 把它传给 `query_by_keywords(include_kinds=...)`。

- 默认 `("fact",)` → **行为变化**：`''` 里的 `relation` 不再注入
- 设成 `None` → 回到 2.0.36 行为（回滚开关）

### 图扩展

**不改。** `_expand_via_semantic_graph` / `expand_query_terms` 完全不知道
`kind` 的存在。

## 五、数据迁移

新增 `SOMA.reclassify_semantic_kind()`，模式与 `reclassify_nature` 一致：

```python
soma.reclassify_semantic_kind(dry_run=True)   # 默认只预览
soma.reclassify_semantic_kind(dry_run=False)  # 落盘前自动写备份
soma.rollback_semantic_kind(backup_path)      # 按备份还原
```

默认规则（可通过 `rules` 参数覆盖）：

| 条件 | kind |
|---|---|
| `namespace LIKE '%graph%'`（`wiki_graph` / `graph` / `mind_graph`…） | `relation` |
| 其余（含 `''`、`user_id`、`agent_id`） | 保持 `fact` |

**为什么只按 namespace 猜**：namespace 是唯一已有的结构信号。`''` 里如果
混着导航边，工具无法自动判断，需要接入方提供规则（比如按 predicate 白名单：
`关联/参考/包含` → relation）。这个判断留给下游，我们只提供工具和预览。

CLI：`soma semantic-kind [--apply] [--rollback PATH]`

## 六、兼容性与回滚

| 场景 | 保障 |
|---|---|
| 旧库打开 | 幂等 ALTER，自动补列 |
| 旧代码调用 | 默认 `kind="fact"`，行为不变 |
| 直接调 `SemanticStore.query_by_keywords` | 默认不过滤，行为不变 |
| 走 `MemoryCore.query` 且不想过滤 | `SOMAConfig(semantic_inject_kinds=None)` |
| 迁移改错了 | 备份 + `rollback_semantic_kind` |

**已知会受影响的一类**：把导航边写在 `''` 且依赖它被注入的下游。
他们的注入结果会变（导航边消失）。这是**预期修复**，但必须在发布说明里
明确写出来，并给出回滚开关。

## 七、验收判据

| # | 判据 | 注入后应红 |
|---|---|---|
| 1 | `kind` 写入后能读回（fact / relation 各一） | 去掉列 → 红 |
| 2 | `include_kinds=("fact",)` 过滤掉 relation | 去掉过滤 → 红 |
| 3 | **relation 边仍能被图扩展命中** | 给扩展加 kind 过滤 → 红 |
| 4 | 不传 kind 时默认 fact（旧调用不变） | 改默认值 → 红 |
| 5 | `include_kinds=None` 时 store 层不丢结果 | 硬编码过滤 → 红 |
| 6 | `MemoryCore.query` 默认只注入 fact | 配置不生效 → 红 |
| 7 | `semantic_inject_kinds=None` 回滚到旧行为 | — |
| 8 | reclassify：dry_run 不改库 / apply 正确 / rollback 还原 | 任一处失效 → 红 |

第 3 条是**这次设计的核心不变量**：如果哪天有人为了「更干净」也给图扩展
加了 kind 过滤，wiki 的关联概念就不再参与扩展，下游会看到召回下降。
必须有判据盯着。

## 八、工作量

| 部分 | 规模 |
|---|---|
| `semantic.py`（schema + add_triple + query + 统计） | ~50 行 |
| `core.py` / `agent.py` / `__init__.py`（透传） | ~35 行 |
| `config.py`（`semantic_inject_kinds`） | ~4 行 |
| 迁移工具（`soma/semantic_kind.py`，仿 nature.py） | ~130 行 |
| 测试（8 条判据 + 注入验证） | ~180 行 |
| 文档更新（namespace 指南 + 新 CLI 说明） | — |

一个版本的量，不涉及引擎/调度层。

## 九、需要确认的四件事

1. **默认注入只 `fact`，可以接受吗？**
   这是行为变化。影响面：把导航边写在 `''` 的下游，注入结果会变。
   我的判断是可以 —— 这正是要修的。但发布说明必须写清楚。

2. **迁移规则要不要更激进？**
   目前只按 `namespace LIKE '%graph%'` 猜。如果下游的 `''` 里也混着
   导航边（像 DSH 迁移前那样），需要他们自己给 predicate 规则。
   要不要我们内置一套 predicate 启发式（`关联/参考/包含/属于` → relation）？

3. **`kind` 要不要参与图扩展的权重？**
   比如 relation 边的邻居降权（×0.5）而不是完全参与。
   我倾向**不做** —— 图扩展本来就是辅助，加权重要重新做 A/B。
   但这是一次设计机会，值得一次明确决定。

4. **枚举要不要锁死？**
   我倾向不锁死（接受任意字符串），代价是拼写错误不会报错。
   如果希望强约束，可以改为 `Literal["fact", "relation"]`。

---

*方案确认后实现，先在本地跑判据与注入验证，不直接发布。*
