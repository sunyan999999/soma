# 升级指南

## 0.3.x → 0.4.0

### 破坏性变更

**无。** 所有新增参数均带默认值，现有代码无需修改即可正常运行。

### 重要新增

#### 记忆数据隔离

SOMA 现在支持按用户和会话维度隔离记忆。所有记忆读写方法新增可选参数：

| 方法 | 新参数 | 默认值 |
|------|--------|--------|
| `soma.remember()` | `user_id`, `session_id` | `""` |
| `soma.remember_semantic()` | `namespace` | `""` |
| `soma.respond()` | `user_id` | `""` |
| `soma.chat()` | `user_id` | `""` |
| `soma.query_memory()` | `user_id` | `""` |

**不传 user_id 的行为**：所有记忆共享（与 0.3.x 一致），无数据丢失。

**启用隔离**：

```python
# 存储时标记用户
soma.remember("用户说喜欢蓝色", user_id="user_123", session_id="chat_456")

# 检索时仅召回该用户的记忆
answer = soma.respond("推荐一个穿搭风格", user_id="user_123")
```

#### 近因衰减优化

时间衰减公式从 `1/(1+days)` 改为指数衰减 `exp(-days/7)`：

| 记忆年龄 | 旧权重 | 新权重 |
|----------|--------|--------|
| 当天 | 100% | 100% |
| 3天前 | 25% | 65% |
| 7天前 | 12.5% | 37% |
| 14天前 | 6.7% | 14% |
| 30天前 | 3.2% | <2% |

另外新增 30 天时间窗口过滤——超过 30 天的记忆默认不参与召回。

### 数据库迁移

**自动执行，无需手动干预。** 首次启动时 SOMA 自动为已有数据库添加 `user_id`/`session_id`/`namespace` 列。旧数据保留在原库中（user_id 为空字符串）。

### 安装

```bash
pip install --upgrade soma-wisdom
```

或从 GitHub 直接安装：

```bash
pip install --upgrade git+https://github.com/sunyan999999/soma.git
```

### 验证升级

```python
from soma import SOMA

soma = SOMA()
# 检查版本
import soma
print(soma.__version__)  # 0.4.0

# 验证隔离功能正常
mid = soma.remember("测试记忆", user_id="test_user")
assert "测试记忆" in soma.query_memory("测试", user_id="test_user")[0]["content_preview"]
print("升级成功")
```
