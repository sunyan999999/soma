# SOMA — 体悟式智慧架构

<p align="center">
  <strong>Wisdom over Memory — 智慧超越记忆</strong><br>
  <em>AI Agent 不该只是"记住"，应该<strong>悟到</strong>。</em>
</p>

```bash
pip install soma-wisdom     # 五分钟，从零到会思考的 Agent
```

```python
from soma import SOMA

soma = SOMA()
soma.remember("第一性原理：回归事物最基本的要素，从底层逻辑出发推导...",
              context={"domain": "哲学"}, importance=0.9)
answer = soma.respond("如何系统性地分析公司增长瓶颈？")
# → 7条思维规律拆解问题 → 双向激活检索记忆 → 返回结构化分析
```

**为什么用 SOMA 而非向量数据库？** 传统记忆库（ChromaDB、Mem0）只管存和搜。SOMA **先思考再检索**：7条思维规律组成推理网络，分析问题的维度决定了要激活什么记忆。结果是能系统拆解问题的 Agent，而不是只会模式匹配的机器人。

| | 向量数据库 | Mem0 | **SOMA** |
|---|---|---|---|
| 存取记忆 | ✓ | ✓ | ✓ |
| 推理框架 | ✗ | ✗ | **✓ 7条思维规律** |
| 自我进化 | ✗ | ✗ | **✓ 权重自动调优** |
| 合并+遗忘 | ✗ | 部分 | **✓ 艾宾浩斯衰减** |
| 因果推理 | ✗ | ✗ | **✓ 因果链推理** |
| 跨域类比 | ✗ | ✗ | **✓ 结构模式匹配** |
| 冲突检测 | ✗ | ✗ | **✓ 矛盾标记** |
| 多Agent协作 | ✗ | ✗ | **✓ 专家路由+共识协议** |
| 框架锚定觉察 | ✗ | ✗ | **✓ 认知偏差提醒** |
| 离线零依赖 | 部分 | ✗ (需OpenAI) | **✓ ONNX+SQLite** |

<p align="center">
  <a href="https://github.com/sunyan999999/soma"><img src="https://img.shields.io/github/stars/sunyan999999/soma?style=social" alt="GitHub stars"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue" alt="License"></a>
  <a href="#"><img src="https://img.shields.io/badge/version-0.9.1-blue" alt="Version"></a>
  <a href="#"><img src="https://img.shields.io/badge/python-3.10%2B-green" alt="Python"></a>
  <a href="#基准测试"><img src="https://img.shields.io/badge/语义召回-100%25-brightgreen" alt="语义召回率"></a>
  <a href="#基准测试"><img src="https://img.shields.io/badge/综合评分-80.5%2F100-blue" alt="综合评分"></a>
  <a href="#"><img src="https://img.shields.io/badge/测试-485%2B-brightgreen" alt="测试"></a>
  <a href="CHANGELOG.md"><img src="https://img.shields.io/badge/变更日志-v0.9.1-success" alt="变更日志"></a>
</p>

📖 **[English README](README.md)** | **[文档](https://sunyan999999.github.io/soma/)** | **[变更日志](CHANGELOG.md)** | **[贡献指南](CONTRIBUTING.md)**

<p align="center">
  <img src="https://raw.githubusercontent.com/sunyan999999/soma/main/docs/images/demo-pipeline.gif" alt="SOMA Pipeline Demo" width="720">
</p>

无需 API Key 即可在 Mock 模式下运行。设置 `llm="deepseek-chat"`（或任意 LiteLLM 模型）接入真实 LLM。

## 架构

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         SOMA Agent (v0.9.1)                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐                 │
│  │ WisdomEngine  │→│ActivationHub │→│     MemoryCore        │                 │
│  │ · 关键词匹配  │  │ · 双向激活   │  │ · 情节/语义/技能      │                 │
│  │ · 规律链传播  │  │ · 反视角检索 │  │ · SQLite+向量+RRF    │                 │
│  │ · 组合模板    │  │ · 可用性修正 │  │ · 时间衰减            │                 │
│  │ · 语义兜底    │  │ · 框架检测   │  └──────────────────────┘                 │
│  │ · 语境排序    │  └──────────────┘         │                                 │
│  └──────────────┘         │                  ▼                                 │
│         │                 ▼   ┌──────────────────────────────────────────┐    │
│         ▼         ┌────────────────┐            MetaEvolver              │    │
│  ┌──────────┐     │ 零熵觉察层(v0.9.1)│ · 偏差检测 → 自动调权 → 技能固化   │    │
│  │复杂度评估 │     │· 框架锚定检测     │ · 触发词扩展· 思维模板挖掘· 动态步长│    │
│  └──────────┘     │· 认知偏差提醒     │ · 记忆合并 + 主动遗忘              │    │
│                   └────────────────┘ └──────────────────────────────────┘    │
│         │                  │                  │                              │
│         ▼                  ▼                  ▼                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  v0.8 深度推理层           │  v0.9.0 多Agent协作层                      │   │
│  │  · 因果推理（因果链传播）    │  · AgentRegistry（多实例管理）             │   │
│  │  · 类比推理（结构模式匹配）  │  · ExpertRouter（3级路由策略）             │   │
│  │  · 冲突检测（矛盾标记）      │  · ConsensusProtocol（3种共识策略）        │   │
│  │  · 假设检验 + 正反证据对照   │  · DistributedEvolver（分布式进化）        │   │
│  │  · 17个推理模板匹配         │  · 记忆隔离（agent_id/group_id）           │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────────┘

智者思维十三步管道：
  复杂度评估 → 问题拆解 → 规律链传播 → 组合模板合成 → 语义兜底
            → 语境排序 → 双向激活 → 反偏误检测 → 框架锚定觉察
            → 推理框架构建 → 方案合成 → 因果抽取 → 进化（含记忆合并+遗忘清理）
```

## 仪表盘界面

## 截图展示

<p align="center">
  <strong>🧠 智者对话</strong> &nbsp;·&nbsp; <strong>📊 五维基准</strong> &nbsp;·&nbsp; <strong>💻 IDE 集成</strong> &nbsp;·&nbsp; <strong>🔌 REST API</strong>
</p>

<table>
<tr>
<td width="50%"><a href="https://raw.githubusercontent.com/sunyan999999/soma/main/docs/images/screenshot-chat.jpeg"><img src="https://raw.githubusercontent.com/sunyan999999/soma/main/docs/images/screenshot-chat.jpeg" alt="SOMA 智者对话 — ChatView" width="100%"></a></td>
<td width="50%"><a href="https://raw.githubusercontent.com/sunyan999999/soma/main/docs/images/screenshot-benchmark.jpeg"><img src="https://raw.githubusercontent.com/sunyan999999/soma/main/docs/images/screenshot-benchmark.jpeg" alt="SOMA 五维基准 — BenchmarkView" width="100%"></a></td>
</tr>
<tr>
<td align="center"><b>智者对话</b> — 7条规律分解问题，双向记忆激活，LLM 流式响应</td>
<td align="center"><b>五维基准雷达图</b> — 记忆/智慧/进化/伸缩/综合，竞品实时对比</td>
</tr>
<tr>
<td width="50%"><a href="https://raw.githubusercontent.com/sunyan999999/soma/main/docs/images/screenshot-ide.jpeg"><img src="https://raw.githubusercontent.com/sunyan999999/soma/main/docs/images/screenshot-ide.jpeg" alt="SOMA IDE 集成 — Claude Code" width="100%"></a></td>
<td width="50%"><a href="https://raw.githubusercontent.com/sunyan999999/soma/main/docs/images/screenshot-api.jpeg"><img src="https://raw.githubusercontent.com/sunyan999999/soma/main/docs/images/screenshot-api.jpeg" alt="SOMA REST API — 接口文档" width="100%"></a></td>
</tr>
<tr>
<td align="center"><b>IDE 集成</b> — Claude Code / VS Code 一键接入，记忆自动持久化</td>
<td align="center"><b>REST API</b> — FastAPI + SSE 流式，多模型管理，API Key 认证</td>
</tr>
</table>

## 仪表盘

启动 API 服务后打开 `http://localhost:8765`：

```bash
SOMA_API_KEY=test python dash/server.py
```

Vue 3 仪表盘，支持中英文切换，6 个视图：智慧对话 · 思维框架 · 记忆资粮 · 分析看板 · 基准测试 · 设置。

## 安装

```bash
pip install soma-wisdom
```

需要 **Python 3.10+**。嵌入引擎使用 ONNX Runtime 进行 CPU 推理，无需 CUDA、Docker 或外部服务。

首次运行时自动下载一个小型 ONNX 模型（约 100 MB，中英双语）。

```bash
python -m soma          # 一行命令验证安装
soma-quickstart         # 或使用 CLI 入口
```

## 核心概念

### 1. 思维框架 — 7 条智慧规律

| 规律 | 描述 | 权重 |
|------|------|:---:|
| `first_principles` | 回归最基本要素，从底层逻辑推导 | 0.90 |
| `systems_thinking` | 视事物为相互关联的整体，识别反馈回路 | 0.85 |
| `contradiction_analysis` | 识别对立统一关系，找出主要矛盾 | 0.80 |
| `pareto_principle` | 聚焦影响最大的少数关键因素 | 0.75 |
| `inversion` | 反向思考——如何可能导致失败？ | 0.70 |
| `analogical_reasoning` | 将不同领域知识结构映射到当前问题 | 0.65 |
| `evolutionary_lens` | 从时间维度观察事物的演化规律 | 0.60 |

可通过 `wisdom_laws.yaml` 自定义（已内置在包中，无需额外配置）。

**v0.5 新特性**：规律不再是平铺列表——它们构成了**推理网络**。当一条规律被触发时，其 `relations` 字段将激活传播到关联规律（×0.35–0.50 加成）。当两条规律同时触发时，会产生合成视角（如"第一性原理 × 系统思维 → 根因系统分析"）。

### 2. 双向激活 — 加权 RRF 混合检索

记忆匹配采用**加权倒数排序融合**（RRF）：
- 向量语义相似度（权重 ×2）— ONNX 加速嵌入
- 关键词精确匹配（权重 ×1）

两个方向竞争互补，产生反映真正相关性的激活分数。

### 3. 元认知进化 — 自动自我优化

SOMA 跟踪每条思维规律在每轮对话中的成功/失败。每 10 次会话，`evolve()` 自动：
- **偏差检测**：使用频率 >40% 的规律降权 0.05（防思维固化），<3% 但成功率高的规律提权 0.03（发掘被忽视的优质规律）
- **动态步长**：权重调整幅度随样本量自适应（0.01 → 0.02 → 0.03），取代固定 ±0.02
- **技能固化**：将成功的（规律、领域、结果）模式固化为永久技能

### 4. 记忆类型

| 类型 | 存储方式 | 检索方式 |
|------|---------|--------|
| **情节记忆** | SQLite + 向量 BLOB | 混合检索（语义 + 关键词 RRF） |
| **语义记忆** | SQLite 三元组 | 关键词 + 图谱遍历 |
| **技能记忆** | SQLite 模式存储 | 关键词 + 领域匹配 |

### 5. 记忆智能（v0.7.0 新增）

模仿人脑记忆管理机制，让记忆库保持精悍高效：

| 机制 | 描述 | 触发方式 |
|------|------|---------|
| **摘要合并** | 相似度 >85% 的记忆自动归并，独特信息追加为"补充"段 | `soma.evolve()` 自动触发 |
| **主动遗忘** | Ebbinghaus 指数衰减 × 类别差异化衰减率，低价值记忆归档（可恢复） | `soma.evolve()` 自动触发 |
| **外部知识** | Markdown/JSON/JSONL/TXT/YAML 文件或 URL 批量导入，30 天自动过期 | `soma.import_knowledge(path)` |

### 6. 深度推理引擎（v0.8.0 新增）

从"记忆+推理"升级为真正的智慧系统：

| 能力 | 描述 | 示例 |
|------|------|------|
| **因果推理** | 从记忆三元组传播因果链，推断间接关系 | `soma.causal_infer("A")` → A→B→C 因果链 |
| **类比推理** | 跨域结构模式匹配，用已知领域映射未知问题 | `soma.analogical_infer(target_domain)` |
| **冲突检测** | 标记记忆间的逻辑矛盾，支持正反证据对照 | `soma.detect_conflicts(statement)` |
| **推理模板** | 17个推理模板（演绎/归纳/溯因/辩证/反事实...） | 假设检验 + 正反证据对照 |

### 7. 多Agent协作（v0.9.0 新增）

SOMA 支持多实例协作，从个人工具进化为团队智慧平台：

| 组件 | 描述 |
|------|------|
| **AgentRegistry** | 管理多个 SOMA 实例，按 agent_id 隔离记忆 |
| **ExpertRouter** | 3级路由策略：关键词匹配→领域匹配→语义兜底 |
| **ConsensusProtocol** | 3种共识策略：多数投票、加权平均、最佳论证 |
| **DistributedEvolver** | 跨实例知识蒸馏，提炼最佳规律权重 |
| **记忆隔离** | `agent_id` 和 `group_id` 维度隔离，支持个人/团队/组织三级 |

```python
# 多Agent协作示例
from soma import SOMA

# 创建不同专长的Agent
analyst = SOMA(agent_id="analyst", persist_dir="soma_data")
engineer = SOMA(agent_id="engineer", persist_dir="soma_data")

# 记忆按 agent_id 隔离
analyst.remember("市场数据显示用户增长放缓", domain="商业分析")
engineer.remember("微服务架构的性能瓶颈在数据库连接池", domain="系统架构")

# 各自独立回答，互不干扰
print(analyst.respond("如何提升用户留存？"))
print(engineer.respond("如何优化系统性能？"))
```

### 8. 零熵觉察层（v0.9.1 新增）

当用户连续多轮从同一视角分析问题，SOMA 温和提醒尝试其他维度：

| 特性 | 描述 |
|------|------|
| **框架锚定检测** | 纯规则匹配，8对认知框架关键词，窗口5轮阈值60% |
| **觉察提示** | 脚注形式注入 prompt 末尾，不干扰核心推理 |
| **冷却去重** | 同一框架1小时内不重复提示 |
| **错误隔离** | 检测器异常绝不传播到核心管道 |
| **默认关闭** | `enable_frame_detection=False`，100%向后兼容 |

```python
# 开启框架锚定觉察
soma = SOMA()
soma._agent.config.enable_frame_detection = True

# 连续5轮技术问题 → 提示"可尝试从商业视角重新审视"
for q in ["代码架构", "系统性能", "接口设计", "算法优化", "数据存储"]:
    soma.respond(q)
```

## API 参考

### SOMA 门面（Python SDK）

```python
from soma import SOMA

soma = SOMA(
    framework_config=None,        # 默认使用内置 wisdom_laws.yaml
    llm="deepseek-chat",          # LiteLLM 模型标识
    use_vector_search=True,       # ONNX 语义搜索
    persist_dir="soma_data",      # 持久化目录
    recall_threshold=0.01,        # 最低激活阈值
    top_k=5,                      # 默认召回数
    agent_id=None,                # v0.9.0 Agent标识（多Agent隔离）
    group_id=None,                # v0.9.0 组标识（团队/组织级共享）
)

# 智者管道
soma.respond(problem: str) -> str
soma.chat(problem: str) -> dict          # 结构化返回（含拆解和激活详情）

# 记忆操作
soma.remember(content, context, importance) -> str  # 返回 memory_id
soma.remember_semantic(subject, predicate, object_, confidence)
soma.query_memory(query: str, top_k: int) -> list

# 自省与进化
soma.decompose(problem: str) -> list     # 展示思维拆解维度
soma.reflect(task_id, outcome) -> None   # 记录结果供进化
soma.evolve() -> list                    # 自动进化 + 记忆合并 + 遗忘清理
soma.get_weights() -> dict               # 当前规律权重
soma.adjust_weight(law_id, new_weight)   # 手动调整权重
soma.discover_laws() -> dict | None      # 自主发现新规律
soma.approve_law(candidate) -> bool      # 审批通过候选规律
soma.stats -> dict                       # 记忆库统计
```

### REST API（语言无关）

```bash
# 启动服务
SOMA_API_KEY=your-key python dash/server.py    # → http://localhost:8765

# 标准问答
curl -X POST http://localhost:8765/api/chat \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"problem": "如何提升团队效能？"}'

# SSE 流式输出（decompose → activate → delta → done）
curl -X POST http://localhost:8765/api/chat/stream \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"problem": "分析我们的增长瓶颈"}'

# 记忆搜索
curl -X POST http://localhost:8765/api/memory/search \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"query": "增长策略", "top_k": 10}'
```

设置 `SOMA_API_KEY` 环境变量启用认证。本地开发可留空。

### LangChain Tool

```python
from soma.langchain_tool import create_soma_tool
from soma.agent import SOMA_Agent
from soma.config import SOMAConfig, load_config

agent = SOMA_Agent(SOMAConfig(framework=load_config()))
tool = create_soma_tool(agent)
result = tool.run("分析这个问题...")
```

## 基准测试

SOMA v0.9.0 — 基准测试使用 1,752 条零熵智库真实生产记忆：

### 综合评分: 80.5/100

| 维度 | 评分 | 等级 |
|-----------|:---:|:---:|
| **综合** | **80.5** | 优秀 |
| **记忆** | **88.0** | 优秀 — 召回率保持100% |
| **智慧** | **74.4** | 良好 — 多Agent协作额外开销 |
| **进化** | **71.4** | 良好 — 942 次反思，权重自适应 |
| **可伸缩** | **100.0** | 优秀 — 多实例线性扩展 |

### 活体竞品对比

| 系统 | Recall@5 | 推理 | 进化 | 合并 | 遗忘 | 多Agent |
|--------|:---:|:---:|:---:|:---:|:---:|:---:|
| **SOMA v0.9** | **100%** | **✓** | **✓** | **✓** | **✓** | **✓** |
| ChromaDB | 2.5% | ✗ | ✗ | ✗ | ✗ | ✗ |
| Mem0 | * | ✗ | ✗ | ✓ | ✗ | ✗ |
| Zep | * | ✗ | ✗ | ✓ | ✗ | ✗ |

> SOMA 是唯一同时具备推理框架、进化式自优化、记忆合并、主动遗忘、多Agent协作和认知偏差觉察的系统——全部无需外部服务。

完整报告：[`TEST_REPORT_v0.9.0.md`](TEST_REPORT_v0.9.0.md)

### 可复现性

```bash
pip install soma-wisdom chromadb
python -m soma.benchmarks --full --runs 5 --output reports/    # 统计基准
python scripts/live_benchmark.py --full --output reports/       # 活体竞品
```

## 开发指南

```bash
git clone https://github.com/soma-project/soma-core.git
cd soma-core
pip install -e ".[dev]"

pytest -v --cov=soma --cov-report=term    # 485+ 测试，~97% 覆盖率

python -m soma                              # 快速验证

python dash/server.py                       # API 服务 (http://localhost:8765)
```

### 项目结构

```
soma-core/
├── soma/                  # 核心库
│   ├── __init__.py        # SOMA 门面（零配置入口）
│   ├── __main__.py        # python -m soma 快速验证
│   ├── agent.py           # SOMA_Agent：管道编排器（含框架锚定觉察）
│   ├── engine.py          # WisdomEngine：问题拆解 + 因果/类比推理
│   ├── hub.py             # 已拆分为 hub/ 子包
│   ├── evolve.py          # MetaEvolver：反思 + 自动进化
│   ├── embedder.py        # SOMAEmbedder：fastembed + ONNX 编码
│   ├── vector_store.py    # NumpyVectorIndex：faiss 近邻搜索
│   ├── retry.py           # LLM 重试机制（tenacity 指数退避）
│   ├── config.py          # Pydantic 配置模型（含 frame_detection）
│   ├── base.py            # 数据模型（Focus, MemoryUnit 等）
│   ├── abc.py             # 抽象基类
│   ├── langchain_tool.py  # LangChain BaseTool 封装
│   ├── law_discovery.py   # 自主发现新规律
│   ├── plugin.py          # Entry-points 插件自动发现
│   ├── analytics.py       # 使用分析 & 基准存储
│   ├── benchmarks.py      # 三维基准测试引擎
│   ├── wisdom_laws.yaml   # 默认思维框架（包内置）
│   ├── hub/               # v0.9.1 重构的激活中心
│   │   ├── __init__.py    # 导出 ActivationHub, FrameAnchoringDetector
│   │   ├── _core.py       # ActivationHub：双向激活 + 框架检测
│   │   └── _frame_detector.py # FrameAnchoringDetector：认知框架锚定检测
│   ├── multi_agent/       # v0.9.0 多Agent协作
│   │   ├── __init__.py    # 多Agent系统导出
│   │   ├── registry.py    # AgentRegistry：多实例管理
│   │   ├── router.py      # ExpertRouter：3级路由策略
│   │   ├── consensus.py   # ConsensusProtocol：3种共识策略
│   │   ├── distributed_evolver.py # DistributedEvolver：分布式进化
│   │   └── coms.py        # Agent间通信协议
│   └── memory/
│       ├── core.py        # MemoryCore：统一记忆门面（支持 agent_id/group_id 隔离）
│       ├── episodic.py    # EpisodicStore：情节记忆
│       ├── semantic.py    # SemanticStore：知识三元组
│       ├── skill.py       # SkillStore：学习模式
│       ├── search_utils.py # FTS5 双路径搜索共用
│       ├── consolidation.py # v0.7.0 记忆摘要合并
│       ├── forgetting.py  # v0.7.0 主动遗忘引擎
│       └── external.py    # v0.7.0 外部知识集成
├── dash/                  # 仪表盘 & API 服务
│   ├── server.py          # FastAPI（REST + SSE 流式 + 认证）
│   ├── providers.py       # LLM 提供商管理
│   └── frontend/          # Vue 3 仪表盘界面（中英文切换）
├── docs/                  # 文档（中英双语，含审核标准）
├── tests/                 # 485+ 测试，97% 覆盖率
├── examples/              # 使用示例
├── scripts/               # 基准测试与工具脚本
└── pyproject.toml         # 构建配置
```

## 引用

如果在研究中使用了 SOMA，请引用：

```bibtex
@software{soma2025,
  title        = {SOMA: Somatic Wisdom Architecture},
  author       = {SOMA Project Team},
  year         = {2025},
  url          = {https://github.com/soma-project/soma-core},
  note         = {Apache 2.0},
}
```

## 许可证

Apache License 2.0。详见 [LICENSE](LICENSE)。

---

<p align="center">
  <sub>🧠 五分钟接入，给你的 Agent 一个会思考的灵魂</sub>
</p>
