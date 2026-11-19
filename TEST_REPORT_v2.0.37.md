# SOMA v2.0.37 测试报告

## 版本
- **soma-wisdom 2.0.37**（语义三元组 kind：事实 / 关系）
- 2026-11-20

## 本次变更

下游 1.5 万条 wiki 关联图落在 `namespace=''` 里，`include_global` 一开就把
用户情节记忆挤出 70%，而分数面板看不出来。他们用 namespace 隔离修好了，
但那次修复依赖「写的人记得传 namespace」，漏一次就复发。

### 设计：kind 只管注入，不管扩展

两条消费路径相互独立：图扩展走内存 NetworkX（只用节点名），
知识注入走 SQL。污染只发生在后者。所以 `kind` 只影响注入。

### Schema

```sql
ALTER TABLE semantic_triples ADD COLUMN kind TEXT NOT NULL DEFAULT 'fact';
CREATE INDEX idx_semantic_kind ON semantic_triples(kind);
```

幂等迁移；取值不锁死（`fact` / `relation` / 自定义）。

### ⚠️ 默认行为变化

`MemoryCore.query` 默认只注入 `kind='fact'`。
回滚开关：`SOMAConfig(semantic_inject_kinds=None)`。

### 迁移

`soma.reclassify_semantic_kind(dry_run=True)` / `soma semantic-kind [--apply]`。
默认只按 namespace 含 `graph` 判定；`''` 里的导航边需 predicate 规则。

## 新增测试（+15）

| 文件 | 数量 | 覆盖 |
|------|------|------|
| `tests/test_semantic_kind.py` | 15 | kind 往返 / 默认 fact / context 带 kind；include_kinds 过滤；**relation 仍参与图扩展**（2 条）；MemoryCore 默认只注入 fact；配置 None 回滚；reclassify 的 dry_run / apply / rollback / predicate 规则 / 备份失败中止 |

### 注入验证

```
去掉 kind 过滤条件（kind_clause 恒空）
  → test_include_kinds_filters_relation 红
  → test_query_injects_only_facts 红

让 relation 边不进内存图（模拟“为了干净连扩展也过滤”）
  → test_relation_edges_still_expand 红
  → test_mixed_kinds_both_expand 红
```

第二组是本次设计的核心不变量：如果哪天有人给图扩展也加了 kind 过滤，
wiki 的关联概念就不再参与召回扩展，下游会直接看到召回下降。

## 全量测试（3 轮）

```
1396 passed in 166.18s
1396 passed in 176.39s
1396 passed in 175.32s
```

原有 1381 + 新增 15 = 1396，**三轮零回归**（默认行为变化未破坏任何既有测试）。

## 文档

- `docs/guides/namespace-convention_zh.md` 新增「kind」章节与两维度配合表
- 方案文档：`docs/plan-v2.0.37-relation-kind.md`

## 待下游验证

1. `semantic_inject_kinds` 默认值对他们的影响：如果 `''` 里还有导航边，
   注入结果会变 —— 这是预期修复，建议先跑 `soma semantic-kind` 预览。
2. relation 边仍在图扩展中（可对比关键词扩展结果是否与 2.0.36 一致）。
