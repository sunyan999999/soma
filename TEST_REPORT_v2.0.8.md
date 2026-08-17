# TEST_REPORT — SOMA v2.0.8

> 生成日期：2026-08-17
> 版本：v2.0.8（部署与分身隔离改进）

## 测试结果总览

| 轮次 | 通过 | 失败 | 耗时 |
|------|------|------|------|
| 第 1 轮 | 763 | 0 | 103.10s |
| 第 2 轮 | 763 | 0 | 100.42s |

> 叠加 v2.0.7 阶段 3 轮（759/760/760），本项目 v2.0.8 前后共 5 轮全量测试零回归，满足铁律 3（≥3 轮）。

**结论：全量测试零回归。**

## 测试环境

- Python 3.13.9
- pytest 8.4.2 + pluggy 1.5.0
- fastembed 0.7.4（锁定）
- 平台：Windows 11 Home China 10.0.26200

## 本次改动摘要

### 新增
- **`query_memory(agent_id=, group_id=)`**: 公开方法支持显式分身/组隔离维度，为空回退到当前实例（向后兼容）
- **`warmup_on_init=True`**: SOMA 构造时同步加载嵌入模型，消除首请求热路径卡顿
- **多进程部署文档** (`docs/guides/deployment.md`)

### 变更
- **`engine.decompose` 语义兜底**: embedder 未加载（`is_loaded=False`）时跳过向量语义匹配，避免热路径触发模型加载
- **`reason()` 文档明确 use_llm 三档**: `False`=纯本地零 LLM / `"auto"`=智能路由 / `True`=强制 LLM
- **激活异常日志**: 记忆激活失败时记录异常类型 + traceback 首行

### 修复
- **依赖版本锁定**: `litellm>=1.96.2,<1.97.0`、`fastembed==0.7.4`，防升级漂移

## 新增测试

- `tests/test_agent.py` +3：query_memory 隔离透传（mock 验证）/ warmup 配置 / decompose 跳过语义兜底（encode 不调用）

## 回归风险

- 全部改动向后兼容：`query_memory` 新参数有默认空串、`warmup_on_init` 默认 False、decompose 兜底仅影响「embedder 未加载 + 无关键词匹配」的边界场景
- 记忆隔离、多智能体共识、核心检索路径未改动
