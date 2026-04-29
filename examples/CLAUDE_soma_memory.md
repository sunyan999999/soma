## SOMA 开发记忆系统

你连接了 SOMA 跨项目记忆库。记忆持久化在 `~/.soma/dev_memory/`，所有项目共享。

### 会话启动时

**必须执行**——在理解用户任务后，检索相关记忆：

```bash
python c:/SOMA/soma-core/examples/dev_memory.py recall "<任务关键词>"
```

如果检索到相关记忆，将其作为隐性约束纳入后续工作。

### 重要操作后自动记录

**主动判断**——以下场景必须记录：

| 触发条件 | 示例命令 |
|---------|---------|
| 做出设计决策 | `python c:/SOMA/soma-core/examples/dev_memory.py save -p 项目名 "决定用X方案替代Y，因为Z"` |
| 遇到并解决 bug | `python c:/SOMA/soma-core/examples/dev_memory.py save -p 项目名 --importance 0.9 "Bug: X导致Y，根因是Z，修复用W"` |
| 发现不可改动的约束 | `python c:/SOMA/soma-core/examples/dev_memory.py save -p 项目名 --importance 0.95 "约束: X模块不能动，会影响Y"` |
| 完成阶段性任务 | `python c:/SOMA/soma-core/examples/dev_memory.py save -p 项目名 "完成Phase N: 具体做了什么"` |
| 用户明确纠正你 | `python c:/SOMA/soma-core/examples/dev_memory.py save -p 项目名 --importance 0.85 "纠正: 用户偏好X而非Y"` |

### 工具路径

SOMA 记忆脚本路径: `c:/SOMA/soma-core/examples/dev_memory.py`

可用命令:
- `save "内容"` — 记录记忆（-p 项目名, -i 重要性0-1, -q 精简输出）
- `recall "关键词"` — 搜索记忆（-k 返回条数）
- `list -n 10` — 列出最近
- `stats` — 记忆库统计
