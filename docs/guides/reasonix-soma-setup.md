# Reasonix SOMA 集成指南

Reasonix 是 CodeMonitor 服务端，无需额外安装。直接通过 HTTP API 调用 SOMA。

## 调用方式（HTTP API）

SOMA Dash 运行在 `http://localhost:8765`：

```python
import requests

# 深度分析
resp = requests.post("http://localhost:8765/api/chat", json={
    "problem": "微服务还是单体架构"
})
analysis = resp.json()

# 记忆搜索
resp = requests.get("http://localhost:8765/api/memory/search", params={
    "q": "消息队列", "top_k": 5
})

# 中道引擎建议
resp = requests.get("http://localhost:8765/api/zhongdao/suggest", params={"days": 30})
```

## 自动触发规则

在 Reasonix 的系统 prompt 中增加:

```
当被问到技术决策类问题时，自动调用 SOMA HTTP API 获取多维度分析:
- POST /api/chat — 深度分析
- GET /api/memory/search — 检索历史决策
- GET /api/zhongdao/suggest — 获取参数建议
```

HTTP API 比 CLI 更适合 Reasonix——无需 subprocess，直接 requests 调用。
