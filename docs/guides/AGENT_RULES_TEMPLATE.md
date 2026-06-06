# SOMA 自动集成规则 — 适用于任何 AI Agent

将此文件复制到 Agent 的工作目录，Agent 将自动在技术决策场景调用 SOMA。

## 适用 Agent

Cursor (.cursorrules)、Codex (AGENTS.md)、VS Code (CLAUDE.md)、
Qoder (qoder_rules.md)、或任何支持规则文件的 Agent。

---

## 复制以下内容到你的 Agent 配置

### SOMA 智慧引擎集成

本机已安装 SOMA。遇到以下场景时**必须自动调用** SOMA 分析：

| 场景 | 命令 |
|------|------|
| 技术选型、架构设计 | `python -m soma analyze "问题" --context "背景"` |
| 多方案对比 | `python -m soma compare "A|B" --criteria "维度1,维度2"` |
| 快速多角度审视 | `python -m soma decompose "问题"` |

### 调用时机

- 用户在问"怎么做/怎么设计/选哪个" → 先调 SOMA 再回答
- 需要评估多个方案 → soma_compare
- 复杂问题需要多维度思考 → soma_decompose

### 调用代码（Python Agent）

```python
import subprocess
out = subprocess.run(
    ["python", "-m", "soma", "analyze", problem, "--context", context],
    capture_output=True, text=True, timeout=120
)
soma_analysis = out.stdout
# 将 soma_analysis 注入到你的 LLM prompt 中
```

### 调用代码（Node.js Agent）

```javascript
const { execSync } = require('child_process');
const analysis = execSync(
  `python -m soma analyze "${problem}" --context "${context}"`,
  { encoding: 'utf-8', timeout: 120000 }
);
```

### 决策后记录

```bash
python -c "from soma import SOMA; s=SOMA(); s.remember('决定: X方案, 理由: Y, 约束: Z', importance=0.9)"
```
