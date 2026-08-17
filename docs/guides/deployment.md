# SOMA 多进程部署指南 / Multi-Process Deployment Guide

> v2.0.8 新增 | 面向 uvicorn/gunicorn 多 worker、systemd 多进程等部署形态。

## 背景：embedder 与进程的关系 / Background

SOMA 的嵌入器（`SOMAEmbedder`）封装 ONNX 模型（默认 BAAI/bge-small-zh-v1.5，约 91MB，内存 ~100MB）。

**关键机制**：
- **进程内共享**：同一进程内多个 `SOMA_Agent` 可通过 `embedder=` 参数复用同一份模型（v2.0.7 起 `create_agents` 自动共享）。进程内 N 个分身 = 1 份模型。
- **跨进程不共享**：Python 进程内存隔离，每个 worker 进程各自加载一份模型。uvicorn `--workers 4` = 4 份模型 ≈ 364MB + 4 次冷加载（每次 ~270ms-数秒，取决于磁盘/网络）。

## 部署建议 / Recommendations

### 1. 进程内共享（已自动生效） / In-process sharing (automatic)

多 agent（分身）请用**同一进程**内的 `orchestration_mode="multi"` 或 `register_expert`，v2.0.7+ 会自动共享 embedder，无需额外配置。

```python
soma = SOMA(persist_dir="soma_data", orchestration_mode="multi")
soma.register_expert("analyst", ["商业分析"])
soma.register_expert("strategist", ["战略"])
# 3 个分身共享 1 份 ONNX 模型
```

### 2. 启动即加载（v2.0.8+） / Load-on-init

为避免**首个请求**在热路径触发模型加载而卡 30-100s（模型未缓存/网络不通时），构造 SOMA 时开启同步预热：

```python
soma = SOMA(persist_dir="soma_data", warmup_on_init=True)
```

> 默认 `warmup_on_init=False`（懒加载 + 后台线程预热），保持向后兼容。生产环境建议设为 `True`，把模型加载成本从「首请求」转移到「启动期」。

### 3. 多 worker 内存预算 / Memory budget

| workers | 模型份数 | 估算内存（仅 embedder） |
|---------|---------|------------------------|
| 1 | 1 | ~100MB |
| 2 | 2 | ~200MB |
| 4 | 4 | ~364MB |
| 8 | 8 | ~800MB |

- 按总内存规划 worker 数，预留每份 ~100MB。
- 若内存受限，优先**减少 worker 数 + 提升单 worker 吞吐**，而非压榨 embedder。

### 4. 预热时机 / Warm-up timing

推荐在**进程启动后、接受流量前**预热：

```python
# uvicorn/FastAPI 场景
@app.on_event("startup")
def warmup():
    from soma import SOMA
    s = SOMA(persist_dir="soma_data", warmup_on_init=True)
    s.close()  # 或复用全局实例
```

### 5. 离线环境 / Offline environments

- 首次加载会尝试 HuggingFace 下载（联网）。离线/内网环境设置 `HF_HUB_OFFLINE=1`，并确保模型已缓存到本地。
- 网络超时场景下模型加载可能卡 30-100s；v2.0.8 起 `decompose` 语义兜底在 embedder 未加载时自动跳过（不阻塞请求），配合 `warmup_on_init=True` 可彻底消除首请求卡顿。

## 依赖版本锁定 / Pinned dependencies

SOMA v2.0.8 锁定以下关键依赖（避免升级漂移引入兼容问题）：

| 依赖 | 版本约束 | 原因 |
|------|---------|------|
| `litellm` | `>=1.96.2,<1.97.0` | 1.97.0 存在 Pydantic 循环引用兼容错误（`model_rebuild()` 报错） |
| `fastembed` | `==0.7.4` | 0.8.0 起 ONNX 推理延迟回归 ~4.4x |

升级脚本请使用 `--no-deps` 或遵循上述约束，避免连带升级导致运行时错误。
