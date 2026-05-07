# 升级指南

## 0.6.1 → 0.7.0

### 破坏性变更

**无。** 所有新增功能均带默认值，现有代码无需修改即可正常运行。

### 重要新增：记忆智能 v0.7.0

v0.7.0 引入三大记忆管理机制，模仿人脑记忆管理模式：

#### 1. 摘要合并 — 相似记忆自动归并

```
合并前: 3条高度相似的"第一性原理"记忆（各200字，大量重复）
合并后: 1条主体记忆 + 独特信息补充（300字，零冗余）
```

`evolve()` 每次自动扫描最近30天记忆，将相似度 >85% 的记忆对合并：
- 高重要性记忆保留为主体，独特信息追加为"补充："段
- 低重要性记忆标记为 `importance=-0.1`（14天宽限期后自动删除）
- 合并日志记录到 `memory_merges` 表，可追溯

```python
changes = soma.evolve()
# changes 中包含 {"type": "memory_consolidation", "merged_count": N}
```

#### 2. 主动遗忘 — Ebbinghaus 指数衰减

模仿人脑遗忘曲线，三层策略：

| 层级 | 策略 | 触发条件 |
|------|------|---------|
| 1. 时间衰减 | `strength = importance × e^(-λ × days) × (1 + recall_count × 0.2)` | strength < 0.05 |
| 2. 访问频率 | 30天未访问 + 低重要性 | access_count=0 + importance < 0.5 |
| 3. 冗余清理 | 合并废记忆14天宽限期后删除 | importance < 0 + 14天 |

**类别差异化衰减率**: 策略(0.07) < 事实(0.10) < 洞察(0.12) < 决策(0.15) < 外部(0.20)

**遗忘 = 归档，非真删除**。归档到 `episodic_archived` 表，可随时恢复：

```python
# 浏览归档
store = soma._agent.memory.episodic
archived = store.recall_archived(query="关键词")

# 恢复指定记忆
store.restore_archived(memory_id)
```

#### 3. 外部知识集成 — 批量导入

支持从文件和 URL 批量导入知识：

```python
# 导入 Markdown 文件（自动分块）
store = soma._agent.memory.episodic
ids = store.import_knowledge("docs/strategy.md", user_id="user_1")

# 导入 JSON 知识库
ids = store.import_knowledge("data/knowledge_base.json")

# 检查过期知识
from soma.memory.external import ExternalKnowledgeImporter
importer = ExternalKnowledgeImporter(store)
expired = importer.check_expired()
```

支持格式：`.md` `.txt` `.json` `.jsonl` `.yaml` `.yml`

默认 30 天过期（可通过 `context._expires_in_days` 配置），到期自动降低 importance。

### 数据库变更

**自动执行，无需手动干预。** 首次启动时自动创建三张新表：
- `memory_merges` — 合并日志
- `episodic_archived` — 归档记忆
- 外部知识导入使用现有 `episodic_memories` 表（标记 `memory_type='external'`）

### 安装

```bash
pip install --upgrade soma-wisdom
```

### 验证升级

```python
from soma import SOMA

soma = SOMA()
# 验证记忆智能功能可用
assert hasattr(soma._agent.memory.episodic, 'consolidate')
assert hasattr(soma._agent.memory.episodic, 'forget')
assert hasattr(soma._agent.memory.episodic, 'import_knowledge')

# 验证 evolve 管道包含新阶段
changes = soma.evolve()
print("v0.7.0 升级成功，变更列表:", changes)
```

---

## 0.6.0 → 0.6.1

### 破坏性变更

**无。** 纯修复版本，所有 API 不变。

### 新增：客观测试体系

v0.6.1 建立了四支柱客观测试评估体系，任何开发者可一键复现：

```bash
# 多轮统计基准 (5轮, 独立数据库)
python -m soma.benchmarks --full --runs 5 --output reports/

# 活体竞品实测 (需 chromadb)
python scripts/live_benchmark.py --full --output reports/
```

- **统计驱动**: 均值±标准差, 95%置信区间, CV%变异系数, 稳定性评级
- **活体竞品**: 真实库实测 (非 mock), 同数据同查询, 诚实标记不可用系统
- **CI 自动化**: PR 轻量测试, Release 全量 + 活体对比, 结果自动附加
- **Docker 标准化**: `Dockerfile.bench` 固定环境, 消除"我的机器上能跑"问题

### 重要修复

#### SSE 流式端点会话记录补全

0.6.0 中 `/api/chat/stream` 端点未调用 `AnalyticsStore.record_session()`，导致所有 SSE 流式请求不进入仪表盘分析面板。0.6.1 在 "done" 事件后添加会话记录，包含问题、完整答案、foci、激活记忆、响应耗时、记忆统计和权重。

#### 向量维度修正

`BAAI/bge-small-zh-v1.5` 实际输出 **512 维**向量，不是 384 维。`config.py` 中 `vector_dim` 已恢复为 `512`。如果之前因维度错误导致数据库损坏，0.6.1 启动时会自动检测并重建向量索引。

#### FTS5 搜索代码整合

`episodic.py` 和 `skill.py` 的 `query_by_keywords()` 现在共用 `soma/memory/search_utils.py` 中的 `fts5_keyword_search()`，消除约 80 行重复代码。

### 安装

```bash
pip install --upgrade soma-wisdom
```

### 验证升级

```python
from soma import SOMA

soma = SOMA()
result = soma.chat("测试会话记录")
# 检查 dash 仪表盘中分析面板是否出现新会话
print("升级成功: v0.6.1")
```

---

## 0.5.x → 0.6.0

### 破坏性变更

**无。** 所有新增参数均带默认值，现有代码无需修改即可正常运行。

### 重要新增

#### 结构化推理引擎

v0.6.0 在 LLM 调用前增加了 SOMA 自己的推理步骤。`respond()` 管道新增两个阶段：

| 阶段 | 位置 | 说明 |
|------|------|------|
| Step 2.6 | LLM调用前 | 构建结构化推理框架（模板+假设+证据对照） |
| Step 4.5 | LLM调用后 | 自动抽取因果关系三元组 |

推理框架结果存储在 `agent._last_reasoning` 中，可通过 `soma.chat()` 的 `reasoning` 字段获取：

```python
result = soma.chat("如何分析增长瓶颈？")
for block in result["reasoning"]:
    print(f"{block['dimension']}: {block['hypothesis']}")
```

#### 因果抽取

默认关闭。开启方式：

```python
from soma import SOMA
import soma.config

soma = SOMA()
soma._agent.config.causal_extraction = True
soma._agent.config.causal_extraction_complexity = 2  # L2以上问题触发
```

从 LLM 回答中自动提取"主语|谓语|宾语"三元组，以 confidence=0.4 存入语义记忆。仅 L3（默认）或指定复杂度以上问题触发，失败不影响主流程。

#### 触发词自动扩展

每次成功会话后，问题中与规律共现的关键词被追踪。同一词跨 5 次不同会话共现后自动提升为正式触发词，无需手动编辑 YAML。

调用 `soma.evolve()` 时自动执行提升和模板挖掘：

```python
changes = soma.evolve()
# 返回包含 "trigger_promoted" 和 "thought_template" 类型的变更列表
```

#### 推理模板体系

| 模板层 | 数量 | 说明 |
|--------|------|------|
| `_REASONING_TEMPLATES` | 7 | 每条规律3个引导问题 |
| `_HYPOTHESIS_TEMPLATES` | 7 | 每条规律1个可检验假设 |
| `_COMBO_REASONING` | 6 | 双规律联动专属框架 |

### 数据库变更

**自动执行，无需手动干预。** 首次启动时自动创建 `candidate_triggers` 和 `focus_patterns` 两张新表。

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
# 检查推理引擎是否正常
result = soma.chat("什么是系统思维？")
assert "reasoning" in result
assert len(result["reasoning"]) >= 1
print("v0.6.0 升级成功")
```

---

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
