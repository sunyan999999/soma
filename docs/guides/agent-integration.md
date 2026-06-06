# SOMA 多 Agent 接入指南

> 让本机的任何 AI Agent（Cursor、Codex、Qoder、Claude Code 等）都能调用 SOMA 进行编程决策辅助。

## 三种接入方式

| 方式 | 适用场景 | 命令示例 |
|------|---------|---------|
| **CLI 命令行** | 任何能执行 shell 的 Agent | `python -m soma decompose "问题"` |
| **HTTP API** | 支持 HTTP 的 Agent | `curl http://localhost:8765/api/chat` |
| **MCP 协议** | MCP 兼容 Agent（Claude Code 等） | 自动注册 `soma_*` 工具 |

---

## 方式一：CLI 命令行（推荐，最通用）

### 1. 确认安装

```bash
python -m soma
# 应显示: SOMA v1.1.4 — 编程决策辅助 CLI
```

### 2. 三个核心命令

#### 问题拆解（零 LLM 调用）
```bash
python -m soma decompose "如何设计一个高可用的消息队列系统"
```
输出：4-5 个思考维度，每个维度有分析方向

#### 深度分析
```bash
python -m soma analyze "微服务还是单体架构" --context "电商平台，日均100万订单，团队15人"
```
输出：拆解维度 + 激活记忆 + 完整分析结论

#### 多方案对比
```bash
python -m soma compare "自建MQ|云服务MQ|事件流平台" --criteria "成本,运维,可靠性,扩展性"
```
输出：各方案独立分析 + 综合推荐

### 3. Agent 如何调用

```python
# Cursor/Codex 等 Python Agent 调用示例
import subprocess, json

def soma_analyze(problem: str, context: str = "") -> str:
    cmd = ["python", "-m", "soma", "analyze", problem]
    if context:
        cmd += ["--context", context]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    return result.stdout
```

```javascript
// VS Code / Node.js Agent 调用示例
const { execSync } = require('child_process');
function somaDecompose(problem) {
  return execSync(`python -m soma decompose "${problem}"`, 
    { encoding: 'utf-8', timeout: 30000 });
}
```

---

## 方式二：HTTP API

如果 SOMA Dash 服务在运行（端口 8765），可直接调 REST API：

```bash
# 深度分析
curl -X POST http://localhost:8765/api/chat \
  -H "Content-Type: application/json" \
  -d '{"problem": "微服务还是单体架构"}'

# 记忆搜索
curl "http://localhost:8765/api/memory/search?q=消息队列&top_k=5"

# 中道引擎状态
curl http://localhost:8765/api/zhongdao/status

# 中道效果追踪
curl http://localhost:8765/api/zhongdao/effectiveness?days=30
```

启动 Dash（如果未运行）：
```bash
soma-dash
# 或
python -m soma.dash.server
```

---

## 方式三：MCP 协议

MCP 兼容的 Agent（Claude Code、Cursor 等）直接配置即可自动注册工具：

```json
{
  "mcpServers": {
    "soma": {
      "command": "python",
      "args": ["-m", "soma.mcp_server"],
      "env": {
        "SOMA_DATA_DIR": "~/.soma/mcp",
        "SOMA_LLM": "deepseek-chat"
      }
    }
  }
}
```

配置后 Agent 自动获得以下工具：
- `soma_decompose` — 多角度拆解
- `soma_analyze` — 深度分析
- `soma_compare` — 方案对比
- `soma_recall` — 记忆搜索
- `soma_save` — 记录决策
- ... 共 13 个工具

---

## 各 Agent 接入清单

| Agent | 工作目录 | 推荐方式 | 状态 |
|-------|---------|---------|:----:|
| Claude Code | C:\SOMA | MCP + Skill | ✅ 已接入 |
| Cursor | C:\sfjr | CLI + HTTP | 📋 待接入 |
| Codex | C:\mojiaxuanshu | CLI | 📋 待接入 |
| Qoder | 零熵智库 | CLI + HTTP | 📋 待接入 |
| Reasonix | AppData | HTTP API | 📋 待接入 |

## 快速接入步骤

1. 确认 SOMA 已安装：`pip install soma-wisdom>=1.1.4`
2. 选择一个方式（推荐 CLI，最简单）
3. Agent 在需要决策时调用对应命令
4. 将 SOMA 的输出作为上下文注入到 Agent 的 LLM prompt 中
