# SOMA v2.0.14 测试报告

## 版本
- **soma-wisdom 2.0.14**（记忆业务性质 + faiss 后台异步重建）
- 2026-08-31

## 本次变更
1. **记忆业务性质字段 nature（state/fact/event）**：MemoryUnit.nature + 存储 schema + remember 透传 + explain_activation 返回 nature/is_stale + 状态类时效窗口（STATE_TTL_DAYS=30）
2. **faiss 后台异步重建**：增量超限全量重建不再阻塞插入（后台线程执行）

## 新增测试（+9）
- nature 6 项：存取往返 / 默认 event / fact / explain_activation 返回 nature+is_stale / is_state_stale 语义（40天state=True、1天state=False、旧fact=False）/ 旧 state 召回 is_stale=True
- 后台重建 3 项：触发不阻塞主线程（<1s）/ 后台完成索引可用 / 重建期间增量自愈补入不丢

## 全量测试
```
867 passed in 132.97s
```
- 原有 858 用例 + 新增 9 用例，**零回归**

## 验证亮点
- 真实场景：`remember("用户睡眠不好", nature="state")` + 40 天后 → `explain_activation` 返回 `nature=state, is_stale=True, age_days=40`，注入层可提示「旧状态可能已变化」
- faiss 重建：触发 `_maybe_rebuild` 主线程返回 1ms（原同步 ~5s），后台线程重建完成索引可用

## wheel
- `dist/soma_wisdom-2.0.14-py3-none-any.whl`（263 KB）
