# Reasonix SOMA 集成指南

## 1. 安装 SOMA

```bash
pip install soma-wisdom>=1.1.4 --force-reinstall
python -m soma  # 确认安装成功
```

## 2. 调用方式（CLI subprocess — 不依赖 Dash 服务）

```python
import subprocess

def soma_analyze(problem: str, context: str = "") -> str:
    """深度分析 — 完整 SOMA 管道"""
    cmd = ["python", "-m", "soma", "analyze", problem]
    if context:
        cmd += ["--context", context]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return r.stdout

def soma_decompose(problem: str) -> str:
    """多角度拆解 — 零 LLM，纯本地推理"""
    r = subprocess.run(
        ["python", "-m", "soma", "decompose", problem],
        capture_output=True, text=True, timeout=30,
    )
    return r.stdout

def soma_compare(options: str, criteria: str = "") -> str:
    """多方案对比"""
    cmd = ["python", "-m", "soma", "compare", options]
    if criteria:
        cmd += ["--criteria", criteria]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return r.stdout
```

## 3. 自动触发规则

在 Reasonix 系统 prompt 中增加:

```
遇到以下场景时必须自动调用 SOMA:

1. 技术架构/方案设计 → subprocess.run(["python", "-m", "soma", "analyze", ...])
2. 多个可选方案对比 → subprocess.run(["python", "-m", "soma", "compare", ...])
3. 复杂问题多维度审视 → subprocess.run(["python", "-m", "soma", "decompose", ...])

CLI 方式不依赖 Dash 服务，只要 SOMA 包已安装即可使用。

每次技术决策后记录到 SOMA:
  from soma import SOMA
  SOMA(llm="deepseek-chat").remember("决定: X, 理由: Y", importance=0.9)
```

## 4. 对比

| 方式 | 依赖 | 适合 |
|------|------|------|
| CLI (推荐) | 仅需 pip install | 随时可用，无需服务运行 |
| HTTP API | 需要 Dash 运行 | Dash 在线时可用 |
