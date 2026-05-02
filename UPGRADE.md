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

### 安全加固（0.4.0 生产审查）

0.4.0 经全面安全审查后修复了以下问题：

| 问题 | 修复 |
|------|------|
| LIKE 兜底路径 user_id 隔离失效 | OR 条件改为 AND，保证过滤条件不被绕过 |
| 语义图 namespace 过滤缺漏 | LIKE 路径改为 SQLite 查询，确保 namespace 和时间窗口生效 |
| LLM 短时缓存跨用户泄漏 | 缓存键加入 user_id |
| API Key 前端 HTML 注入 | 移除注入，改为 `/api/auth/status` + sessionStorage |
| v-html XSS 风险 | LLM 输出先转义 HTML 实体再 Markdown 渲染 |
| CORS 过于宽松 | 从 `*` 改为 localhost 白名单（SOMA_CORS_ORIGINS 环境变量可配） |
| FTS 双引号未转义 | 关键词中 `"` 转义为 `""`，防止 FTS5 语法损坏 |
| skill.py 缺时间窗口 | 添加默认 90 天时间窗口 |
| 异常静默吞没 | 添加 logging.error 记录完整 traceback |
| 数据库迁移顺序错误 | ALTER TABLE 移到 CREATE INDEX 之前，旧库首次启动不再崩溃 |
| 三元组/技能去重缺失 | add_triple / add_skill 添加去重检查，同 namespace/user 不重复插入 |
| access_count 未持久化 | respond/chat 路径调用 increment_access，访问计数跨会话保留 |
| Dash DevSidecar 代理拦截 | _http_get_json 绕过系统代理 + SSL 证书回退 |
| Dash 认证流程断裂 | App.vue 调用 initAuth()，修复「请设置 X-API-Key」错误 |
| SOMA_API_KEY 未设置 | 启动时自动生成随机密钥 + localhost 跳过认证 |

仪表盘新增安全端点 `GET /api/auth/status` 供前端检测认证状态。

### Pre-commit 验证脚本

提交前运行 `python scripts/verify_before_commit.py` 自动执行 5 步 15 项检查：

| 步骤 | 检查内容 |
|------|----------|
| 1. 全量单元测试 | 196 项 pytest |
| 2. 数据隔离端到端 | 三库跨用户交叉查询 |
| 3. 时间窗口行为 | opt-in 过滤 + 边界值 |
| 4. LLM 缓存隔离 | user_id 缓存键唯一性 |
| 5. 数据库迁移兼容 | 旧库 → 新代码自动迁移 |

全部通过退出码 0，否则退出码 1。

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
