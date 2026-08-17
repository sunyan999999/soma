# TEST_REPORT — SOMA v2.0.7

> 生成日期：2026-08-16
> 版本：v2.0.7（安全修复 + 性能优化）

## 测试结果总览

| 轮次 | 通过 | 失败 | 耗时 |
|------|------|------|------|
| 第 1 轮 | 759 | 0 | 89.08s |
| 第 2 轮 | 760 | 0 | 89.08s |
| 第 3 轮 | 760 | 0 | 88.20s |

**结论：三轮全量测试零回归，满足铁律 3（重大修复后全量测试 ≥3 轮）。**

## 测试环境

- Python 3.13.9
- pytest 8.4.2 + pluggy 1.5.0
- fastembed 0.7.4（ONNX CPU 推理）
- 平台：Windows 11 Home China 10.0.26200

## 本次改动摘要

### 安全修复
- **路径穿越漏洞（高危）**：`soma` CLI `--project` 参数无路径校验，可读写 `~/.soma/` 外任意路径，加正则白名单 `^[A-Za-z0-9_-]+$`
- **recall 阈值 bug**：CLI 搜索场景被自适应激活阈值（~0.3）全过滤，CLI 场景清零阈值
- **importance 越界**：`record -i` 钳制到 [0,1]

### 性能优化
- **多分身共享 embedder**：`create_agents` 复用同一份 ONNX 模型（内存 N×100MB → 1×100MB）
- **decompose 缓存 jieba**：`_extract_keywords` 只算一次
- **chat 预分析复用检索**：`reason()` 复用主流程 foci/activated，减少一轮 decompose+activate

### 功能增强
- `soma` CLI `--project` 参数：项目记忆库 / 共享记忆库隔离

## 新增测试

- `tests/test_cli.py`：10 个（`--project` 路由、路径穿越拒绝、合法名、importance clamp 等）
- `tests/test_orchestrator.py`：+1（embedder 共享防回归）
- `tests/test_backward_compat.py`：测试隔离 fixture（修复既有 flaky）

## 回归风险

- 全部改动向后兼容：`--project` 默认空串（仍走共享库）、`reason()` 新参数有默认值、`SOMA_Agent` 新参数 `embedder=None` 保持原行为
- 语义隔离、多智能体共识、记忆分层等核心路径未改动
