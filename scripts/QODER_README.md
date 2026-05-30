# SOMA v1.1.3 中道引擎深化 — Qoder 部署指南

## 快速安装

### Windows
双击 `install.bat`，自动完成安装 + 验证。

### Linux
```bash
bash install.sh
```

### 手动
```bash
pip install soma_wisdom-1.1.2-py3-none-any.whl --force-reinstall
python verify_install.py
```

## 默认配置

中道引擎默认关闭，不影响现有管道。启用方式：

```python
from soma import SOMA
soma = SOMA(enable_zhongdao=True, llm="deepseek-chat")
```

## 本次测试重点

1. **A1 参数可配置化** — 用不同阈值/采样数测试，看校正灵敏度变化
2. **A2 Dash可视化** — 启动Dash，对话后在 ☯️ 视图观察规律分布
3. **A3 多Agent趋同** — 多Expert模式下是否会检测到群体思维盲区
4. **A4 持久化** — 校正是否正确写入 analytics.db

详细测试方案见 `SOMA_v1.1.3_测试说明.md`

## 反馈

测试完成后请回复：
- 测试环境、轮数
- 四项功能状态（正常/异常）
- 性能影响评估
- 改进建议

## 技术细节

- 代码变更: 15个文件, +410行, 0行删除
- 新增测试: 15项 (639→654)
- 向后兼容: 100%（默认关闭）
- 性能: track() <100μs/次
