# SOMA — 体悟式智慧架构

<p align="center">
  <strong>Wisdom over Memory — 智慧超越记忆</strong><br>
  <em>为 AI Agent 构建的框架优先式认知架构</em>
</p>

<p align="center">
  <a href="https://github.com/sunyan999999/soma"><img src="https://img.shields.io/github/stars/sunyan999999/soma?style=social" alt="GitHub stars"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue" alt="License"></a>
  <a href="#"><img src="https://img.shields.io/badge/version-0.6.1-blue" alt="Version"></a>
  <a href="#"><img src="https://img.shields.io/badge/python-3.10%2B-green" alt="Python"></a>
  <a href="#基准测试"><img src="https://img.shields.io/badge/语义召回-100%25-brightgreen" alt="语义召回率"></a>
  <a href="#基准测试"><img src="https://img.shields.io/badge/综合评分-65.7%2F100-blue" alt="综合评分"></a>
  <a href="#"><img src="https://img.shields.io/badge/测试-223%2F223-brightgreen" alt="测试"></a>
  <a href="reports/"><img src="https://img.shields.io/badge/测试报告-v0.6.1-success" alt="测试报告"></a>
  <a href="#"><img src="https://img.shields.io/badge/稳定性-CV%3D0.07%25-brightgreen" alt="稳定性"></a>
</p>

---

**SOMA**（Somatic Wisdom Architecture，体悟式智慧架构）是一个轻量、可拔插的 AI Agent 认知框架。与传统记忆库把记忆当被动存储不同，SOMA 以**显式思维框架**为索引来组织记忆——七条底层思考规律构成推理网络，而非平铺列表。规律间通过关联链传播激活、组合生成合成视角、自我纠正认知偏差。结果：Agent 能系统拆解问题、双向激活知识、随时间自我进化。

> **不是让 AI 记更多，而是让 AI 悟更深。**

📖 **[English README](README.md)** | **[文档](docs/)** | **[测试报告](reports/)** | **[变更日志](CHANGELOG.md)** | **[贡献指南](CONTRIBUTING.md)**

<p align="center">
  <img src="https://raw.githubusercontent.com/sunyan999999/soma/main/docs/images/demo-pipeline.gif" alt="SOMA Pipeline Demo" width="720">
</p>

## ⚡ 五分钟接入

```bash
pip install soma-wisdom
python -m soma          # 一行命令验证全部功能
```

```python
from soma import SOMA

soma = SOMA()                                        # 零配置启动

soma.remember(
    "第一性原理：回归事物最基本的要素，从底层逻辑出发推导...",
    context={"domain": "哲学", "type": "理论"},
    importance=0.9,
)

answer = soma.respond("如何系统性地分析公司增长瓶颈？")
print(answer)
```

无需 API Key 即可在 Mock 模式下运行。设置 `llm="deepseek-chat"`（或任意 LiteLLM 模型）接入真实 LLM。

## 架构

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           SOMA Agent (v0.6)                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐            │
│  │ WisdomEngine  │→│ActivationHub │→│     MemoryCore        │            │
│  │ · 关键词匹配  │  │ · 双向激活   │  │ · 情节/语义/技能      │            │
│  │ · 规律链传播  │  │ · 反视角检索 │  │ · SQLite+向量+RRF    │            │
│  │ · 组合模板    │  │ · 可用性修正 │  │ · 时间衰减            │            │
│  │ · 语义兜底    │  └──────────────┘  └──────────────────────┘            │
│  │ · 语境排序    │         │                  │                          │
│  └──────────────┘         ▼                  ▼                          │
│         │         ┌──────────────────────────────────────────────────┐   │
│         ▼         │               MetaEvolver                        │   │
│  ┌──────────┐     │ · 偏差检测 → 自动调权 → 技能固化                  │   │
│  │复杂度评估 │     │ · 触发词扩展 · 思维模板挖掘 · 动态步长            │   │
│  └──────────┘     └──────────────────────────────────────────────────┘   │
│         │                                                                 │
│         ▼                                                                 │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  v0.6.0 推理引擎                    │  v0.6.0 因果抽取             │   │
│  │  · 推理模板匹配（17个）              │  · L3问题自动抽取三元组      │   │
│  │  · 假设检验 + 正反证据对照           │  · 轻量LLM调用（~200tokens） │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────┘

智者思维十二步管道：
  复杂度评估 → 问题拆解 → 规律链传播 → 组合模板合成 → 语义兜底
            → 语境排序 → 双向激活 → 反偏误检测 → 推理框架构建
            → 方案合成 → 因果抽取 → 进化
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
soma.evolve() -> list                    # 触发自动进化
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

SOMA v0.6.1 — 5轮独立统计基准测试 (2026-05-06)：

### 统计严谨性验证 (N=5, 独立数据库)

| 指标 | 均值 ± 标准差 | 95%置信区间 | CV% | 稳定性 |
|--------|:---:|:---:|:---:|:---:|
| **综合** | **65.72 ± 0.04** | [65.68, 65.76] | 0.07% | ● 稳定 |
| **记忆** | **96.78 ± 0.15** | [96.65, 96.91] | 0.15% | ● 稳定 |
| **智慧** | **76.04 ± 0.05** | [75.99, 76.09] | 0.07% | ● 稳定 |
| **查询延迟(1K)** | 4.62 ± 0.15ms | [4.48, 4.76] | 3.24% | ◐ 可接受 |

### 活体竞品对比 (实测, 非模拟)

| 系统 | Recall@5 | 查询 P50 | 去重 | 推理 | 进化 |
|--------|:---:|:---:|:---:|:---:|:---:|
| **SOMA** | **30.0%** 🔴 | 10.10ms 🔴 | **✓** | **✓** | **✓** |
| ChromaDB | 2.5% 🔴 | 1.22ms 🔴 | ✗ | ✗ | ✗ |
| Mem0 | ⚫ | ⚫ | ✓ | ✗ | ✗ |
| Zep | ⚫ | ⚫ | ✓ | ✗ | ✗ |

> 🔴 = 实测  |  ⚫ = 不可用 (需要 API Key / 服务端)  
> ChromaDB 召回低是因为缺少内置 embedding 模型，SOMA ONNX 模型开箱即用。  
> SOMA 是唯一具备推理框架和自我进化能力的系统。

完整报告：[`reports/TEST_REPORT_v0.6.1.md`](reports/TEST_REPORT_v0.6.1.md) | [`reports/LIVE_BENCH_2026-05-06.md`](reports/LIVE_BENCH_2026-05-06.md)

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

pytest -v --cov=soma --cov-report=term    # 196 测试，~97% 覆盖率

python -m soma                              # 快速验证

python dash/server.py                       # API 服务 (http://localhost:8765)
```

### 项目结构

```
soma-core/
├── soma/                  # 核心库
│   ├── __init__.py        # SOMA 门面（零配置入口）
│   ├── __main__.py        # python -m soma 快速验证
│   ├── agent.py           # SOMA_Agent：管道编排器
│   ├── engine.py          # WisdomEngine：问题拆解
│   ├── hub.py             # ActivationHub：双向激活调度
│   ├── evolve.py          # MetaEvolver：反思 + 自动进化
│   ├── embedder.py        # SOMAEmbedder：fastembed + ONNX 编码
│   ├── vector_store.py    # NumpyVectorIndex：faiss 近邻搜索
│   ├── config.py          # Pydantic 配置模型
│   ├── base.py            # 数据模型（Focus, MemoryUnit 等）
│   ├── abc.py             # 抽象基类
│   ├── langchain_tool.py  # LangChain BaseTool 封装
│   ├── law_discovery.py   # 自主发现新规律
│   ├── plugin.py          # Entry-points 插件自动发现
│   ├── analytics.py       # 使用分析 & 基准存储
│   ├── benchmarks.py      # 三维基准测试引擎
│   ├── wisdom_laws.yaml   # 默认思维框架（包内置）
│   └── memory/
│       ├── core.py        # MemoryCore：统一记忆门面
│       ├── episodic.py    # EpisodicStore：SQLite + 向量
│       ├── semantic.py    # SemanticStore：知识三元组
│       └── skill.py       # SkillStore：学习模式
├── dash/                  # 仪表盘 & API 服务
│   ├── server.py          # FastAPI（REST + SSE 流式 + 认证）
│   ├── providers.py       # LLM 提供商管理
│   └── frontend/          # Vue 3 仪表盘界面（中英文切换）
├── docs/                  # 文档（中英双语）
├── tests/                 # 196 测试，~97% 覆盖率
├── examples/              # 使用示例
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
