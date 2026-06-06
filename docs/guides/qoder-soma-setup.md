# Qoder SOMA 自动集成指南

## 1. 升级 SOMA 到最新版

```bash
pip install soma-wisdom>=1.1.4 --force-reinstall
python -c "import soma; print(soma.__version__)"  # 确认 1.1.4
```

## 2. 配置自动调用

将以下内容添加到 Qoder 的系统 prompt 或配置文件中：

```
# SOMA 智慧引擎自动调用规则

遇到以下场景必须自动调用 SOMA（用 subprocess）:

1. 技术选型/架构决策:
   subprocess.run(["python", "-m", "soma", "analyze", problem, "--context", context])

2. 多方案对比:
   subprocess.run(["python", "-m", "soma", "compare", "方案A|方案B", "--criteria", "维度1,维度2"])

3. 复杂问题多角度审视:
   subprocess.run(["python", "-m", "soma", "decompose", problem])

调用示例:
  result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
  soma_analysis = result.stdout  # 注入到 LLM prompt

决策后记录:
  from soma import SOMA
  s = SOMA(llm="deepseek-chat")
  s.remember("决定: X方案, 理由: Y, 备选: Z", importance=0.9)
```

## 3. 验证

```bash
python -m soma decompose "如何优化数据库查询性能"
# 应输出 4-5 个维度的分析
```
