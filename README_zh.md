# SOMA v1.1.2 — AI Agent 认知内核

<p align="center">
  <strong>Wisdom over Memory — 智慧超越记忆</strong><br>
  <em>五条能力线。七条思维规律。一个能记忆、能推理、能协作、能进化的认知内核。</em>
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

| | 向量数据库 | Mem0 | **SOMA v1.1.2** |
|---|---|---|---|
| 存取记忆 | ✓ | ✓ | ✓ |
| 推理框架 | ✗ | ✗ | **✓ 7条思维规律** |
| 自我进化 | ✗ | ✗ | **✓ 权重自动调优** |
| 三层记忆 (L1/L2/L3) | ✗ | ✗ | **✓ 碎片→场景→画像** |
| 合并+遗忘 | ✗ | 部分 | **✓ 艾宾浩斯衰减** |
| 因果推理 | ✗ | ✗ | **✓ 因果链推理** |
| 跨域类比 | ✗ | ✗ | **✓ 结构模式匹配** |
| 冲突检测 | ✗ | ✗ | **✓ 矛盾标记** |
| 多Agent协作 | ✗ | ✗ | **✓ 专家路由+共识协议** |
| 框架锚定觉察 | ✗ | ✗ | **✓ 认知偏差提醒** |
| 实时偏差校正 | ✗ | ✗ | **✓ 中道引擎（新增）** |
| 离线零依赖 | 部分 | ✗ (需OpenAI) | **✓ ONNX+SQLite** |

<p align="center">
  <a href="https://github.com/sunyan999999/soma"><img src="https://img.shields.io/github/stars/sunyan999999/soma?style=social" alt="GitHub stars"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue" alt="License"></a>
  <a href="#"><img src="https://img.shields.io/badge/version-1.1.1-blue" alt="Version"></a>
  <a href="#"><img src="https://img.shields.io/badge/python-3.10%2B-green" alt="Python"></a>
  <a href="#基准测试"><img src="https://img.shields.io/badge/语义召回-100%25-brightgreen" alt="语义召回率"></a>
  <a href="#基准测试"><img src="https://img.shields.io/badge/综合评分-85.5%2F100-blue" alt="综合评分"></a>
  <a href="#"><img src="https://img.shields.io/badge/测试-639%2F639-brightgreen" alt="测试"></a>
  <a href="CHANGELOG.md"><img src="https://img.shields.io/badge/变更日志-v1.1.2-success" alt="变更日志"></a>
  <a href="#"><img src="https://img.shields.io/badge/里程碑-1.1.1-ff6b6b" alt="里程碑"></a>
</p>

📖 **[English README](README.md)** | **[文档](https://sunyan999999.github.io/soma/)** | **[变更日志](CHANGELOG.md)** | **[贡献指南](CONTRIBUTING.md)**

<p align="center">
  <img src="https://raw.githubusercontent.com/sunyan999999/soma/main/docs/images/demo-pipeline.gif" alt="SOMA Pipeline Demo" width="720">
</p>

---

## v1.1.2 — 中道引擎

**v1.1.2 引入中道引擎（Zhongdao Engine）** — 会话内实时规律使用偏差检测与自校正。当单条思维规律在一次会话中占比超过 40%（最少 5 次采样），SOMA 自动检测到偏差，临时降权过度使用的规律（×0.80），并注入被忽略的互补规律（×1.15 提权，最多 2 条）——保持推理的多样性和平衡。

SOMA 三层认知校正系统：

| 层级 | 机制 | 作用域 | 持久化 |
|---|---|---|---|
| FrameAnchoringDetector | 用户侧框架锁定检测 | 每轮 | 无（仅提醒） |
| **ZhongdaoEngine（新增）** | **AI侧规律过度使用校正** | **每会话** | **临时（单次调用）** |
| MetaEvolver | 跨会话趋势校正 | 批量（每5次会话） | SQLite（持久化） |

**基准验证** 于零熵智库（Run#38 vs #39）：智慧评分 +1.4，基尼系数 0.2498→0.2226（思维更均衡）。零 LLM 依赖，默认关闭，100% 向后兼容。

从 v0.1 埋下的每一颗种子，到 v1.1.2 长成的完整系统：

| 能力线 | 核心问题 | v1.1.2 的答案 |
|---|---|---|
| **记忆** | AI如何像人一样管理记忆？ | 三层架构：碎片 → 场景 → 画像 |
| **推理** | 找到信息后如何用来思考？ | 因果链 + 冲突检测 + 跨域类比 |
| **协作** | 多个AI如何组队工作？ | 专家路由 + 共识协议 + 分布式进化 |
| **进化** | AI能从自己的经验中学习吗？ | 反思 → 调权 → 固化 → 分享（三层校正） |
| **工程** | 如何证明这些能力是真实的？ | 639测试 + 五维基准 + 竞品对比 |

**所有新功能默认关闭。从任何 0.x 版本升级，零代码改动。**

---

## 架构

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         SOMA v1.1.2 — 认知内核                                   │
│                                                                                │
│  ┌──────────────────────────────────────────────────────────────────┐        │
│  │  L3 用户画像 — "理解你是个什么样的人"                                │        │
│  │  自动提取特质：偏好、技能、知识盲区、目标                              │        │
│  └──────────────────────────────────────────────────────────────────┘        │
│                                    ↑                                          │
│  ┌──────────────────────────────────────────────────────────────────┐        │
│  │  L2 场景块 — "理解你的工作上下文"                                    │        │
│  │  自动聚合的工作场景（"正在做一个Python数据分析项目"）                   │        │
│  └──────────────────────────────────────────────────────────────────┘        │
│                                    ↑                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────────┐        │
│  │ WisdomEngine  │→│ActivationHub │→│  L1 情节记忆（基石能力）         │        │
│  │ · 7条思维规律 │  │ · 双向激活   │  │ · SQLite + 向量 + FTS5        │        │
│  │ · 规律链传播  │  │ · 冲突检测   │  │ · 加权RRF + 时间衰减           │        │
│  │ · 组合合成    │  │ · MMR重排    │  │ · 知识图谱 + 因果链            │        │
│  │ · 复杂度评估  │  │ · 框架觉察   │  │ · 跨域类比引擎                 │        │
│  └──────────────┘  └──────────────┘  └──────────────────────────────┘        │
│         │                  │                        │                        │
│         ▼                  ▼                        ▼                        │
│  ┌──────────────────────────────────────────────────────────────────┐       │
│  │  多Agent协作层             │  进化循环                              │       │
│  │  · AgentRegistry          │  · MetaEvolver: 偏差检测→调权→        │       │
│  │  · ExpertRouter (3级路由)  │    固化→分享                          │       │
│  │  · ConsensusProtocol      │  · CapturePipeline: 自动L2+L3提取     │       │
│  │  · DistributedEvolver     │  · FrameAnchoringDetector             │       │
│  └──────────────────────────────────────────────────────────────────┘       │
└──────────────────────────────────────────────────────────────────────────────┘

智者思维十五步管道：
  复杂度评估 → 问题拆解 → 规律链传播 → 组合模板合成 → 语义兜底
            → 语境排序 → 双向激活 → 冲突检测 → 框架觉察 → 反偏误
            → 推理构建 → 方案合成 → 因果抽取 → 反向传播 → 进化
```

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

**思维规律构成推理网络。** 当一条规律被触发时，其 `relations` 字段将激活传播到关联规律（×0.35–0.50 加成）。当两条规律同时触发时，会产生合成视角（如"第一性原理 × 系统思维 → 根因系统分析"）。权重随实际使用的成功/失败自动调节——一个创业团队和一个大型企业的 SOMA 实例，最终会演化出完全不同的权重分布。

### 2. 三层记忆体系

v1.1.2 延续了自动记忆分层——系统在你使用的过程中，默默构建对你的理解：

| 层级 | 是什么 | 示例 |
|------|--------|------|
| **L1 情节碎片** | 一条条具体信息 | "修复了OrderService的N+1查询bug" |
| **L2 场景块** | 自动聚合的工作上下文 | "正在做一个Python数据分析项目" |
| **L3 用户画像** | 提取的用户特征 | "偏好函数式编程，擅长调试，正在学习系统设计" |

整个过程全自动。你只需正常使用 SOMA，背后 `CapturePipeline` 会自动将碎片聚合为场景，再从场景提炼画像。

### 3. 双向激活 — 加权 RRF 混合检索

记忆匹配采用**加权倒数排序融合**（RRF）三路检索：
- 向量语义相似度（权重 ×2）— ONNX 加速嵌入
- 关键词精确匹配（权重 ×1）
- 知识图谱扩展检索（权重 ×0.5）

三路竞争互补，产生反映真正相关性的激活分数——而不只是关键词重叠。

### 4. 元认知进化 — 自动自我优化

SOMA 跟踪每条思维规律在每轮对话中的成功/失败。每 5 次会话，`evolve()` 自动：
- **记忆合并**：相似记忆自动归并，减少冗余
- **主动遗忘**：低价值记忆按艾宾浩斯衰减曲线归档
- **偏差检测**：使用频率 >40% 的规律降权 0.05（防思维固化），<3% 但成功率高的规律提权 0.03（发掘被忽视的优质规律）
- **动态步长**：权重调整幅度随样本量自适应（0.01 → 0.02 → 0.03）
- **技能固化**：将成功的（规律、领域、结果）模式固化为永久技能（需 3 次以上）

### 5. 知识图谱与推理引擎

六大认知能力，让 SOMA 从记忆库升级为推理系统：

- **因果链推理**：沿因果图追溯到根本原因——"为什么用户流失上升？"→ 追溯到"三个月前API变更导致响应变慢"
- **冲突检测**：标记记忆间的逻辑矛盾，防止LLM被矛盾信息误导
- **跨域类比**：在无关领域间映射结构模式——如"供应链瓶颈" ≈ "血管堵塞"
- **质量自评**：每次推理输出后在一致性、连贯性、可操作性三个维度自评，低分触发反思改进
- **图谱检索扩展**：关键词不再孤立——BFS遍历（depth=2）发现邻居概念，打破检索孤岛
- **反向传播**：高激活记忆反向建议新的思维焦点——记忆→焦点反馈环发现初始拆解遗漏的视角

### 6. 多Agent协作

多个 SOMA Agent 以团队形式协作：

- **专家分工**：每个Agent拥有独立记忆、独立进化路径、领域专长
- **自动路由**：问题自动分发给最匹配的专家——零LLM参与路由决策，毫秒级完成
- **共识协议**：专家意见不一致时——L1加权投票 → L2 LLM仲裁 → L3辩证综合
- **分布式进化**：各专家独立进化，定期合并群体经验
- **记忆隔离**：三态隔离（agent_id + group_id）——私有、团队共享、全局

### 7. 零熵觉察层

当用户连续从单一视角分析问题，SOMA 温和提醒——不强制、不阻断、不改变管道。

- **8对认知框架**：技术/商业、管理/法律、短期/长期、内求/外求
- **纯规则匹配**：零 LLM/嵌入器依赖
- **低干扰设计**：脚注形式注入 prompt 末尾，不干扰核心推理
- **默认关闭**：`enable_frame_detection=False`，100%向后兼容

```python
soma = SOMA()
soma._agent.config.enable_frame_detection = True  # 手动开启
# SOMA 现在能察觉你陷入了单一视角，并温和提醒
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
    agent_id="",                  # v1.1.2: 多Agent身份标识
    group_id="",                  # v1.1.2: 团队/组织级共享
)

# 智者管道
soma.respond(problem: str) -> str
soma.chat(problem: str) -> dict          # 结构化返回（含拆解和激活详情）

# 记忆操作
soma.remember(content, context, importance) -> str  # 返回 memory_id
soma.remember_semantic(subject, predicate, object_, confidence)
soma.query_memory(query: str, top_k: int) -> list

# v1.1.2: 三层记忆
soma.get_scenes(user_id="", top_k=10) -> list
soma.get_profile(user_id="") -> list
soma.capture_scenes(user_id="", force=False) -> int
soma.update_profile(user_id="", force=False) -> int

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

SOMA v1.1.2 — 使用 1,050 条零熵智库生产记忆，5轮统计基准测试：

### 综合评分: 85.5/100

| 维度 | 评分 | 等级 |
|-----------|:---:|:---:|
| **综合** | **85.5** | 优秀 |
| **记忆** | **97.6** | 优秀 — 召回率100%，三层记忆体系运行 |
| **智慧** | **87.3** | 优秀 — 因果分析+跨域类比+冲突检测全激活 |
| **进化** | **60.2** | 良好 — 权重自适应，反思循环运行中 |
| **可伸缩** | **100.0** | 优秀 — 1K数据量线性扩展验证通过 |

### 活体竞品对比

| 系统 | Recall@5 | 推理框架 | 三层记忆 | 进化 | 多Agent | 觉察 |
|--------|:---:|:---:|:---:|:---:|:---:|:---:|
| **SOMA v1.1.2** | **100%** | **✓** | **✓** | **✓** | **✓** | **✓** |
| ChromaDB | 2.5% | ✗ | ✗ | ✗ | ✗ | ✗ |
| Mem0 | * | ✗ | ✗ | ✗ | ✗ | ✗ |
| Zep | * | ✗ | ✗ | ✗ | ✗ | ✗ |

> SOMA 是唯一同时具备推理框架、三层记忆、因果分析、冲突检测、跨域类比、进化式自优化、多Agent协作和认知觉察的系统——全部无需外部服务。

完整报告：[CHANGELOG.md](CHANGELOG.md)

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

pytest -v --cov=soma --cov-report=term    # 639 测试，~97% 覆盖率

python -m soma                              # 快速验证

python dash/server.py                       # API 服务 (http://localhost:8765)
```

### 项目结构

```
soma-core/
├── soma/                  # 核心库
│   ├── __init__.py        # SOMA 门面（零配置入口）
│   ├── __main__.py        # python -m soma 快速验证
│   ├── agent.py           # SOMA_Agent：管道编排器（含觉察层）
│   ├── engine.py          # WisdomEngine：问题拆解
│   ├── hub.py             # ActivationHub：双向激活
│   ├── evolve.py          # MetaEvolver：反思 + 自动进化
│   ├── embedder.py        # SOMAEmbedder：fastembed + ONNX 编码
│   ├── vector_store.py    # NumpyVectorIndex：faiss 近邻搜索
│   ├── config.py          # Pydantic 配置模型
│   ├── base.py            # 数据模型（Focus, MemoryUnit 等）
│   ├── abc.py             # 抽象基类
│   ├── langchain_tool.py  # LangChain BaseTool 封装
│   ├── law_discovery.py   # 自主发现新规律
│   ├── retry.py           # LLM 重试机制
│   ├── plugin.py          # Entry-points 插件自动发现
│   ├── quality.py         # QualityEvaluator：推理输出评分
│   ├── analogy.py         # AnalogyEngine：跨域结构匹配
│   ├── competitors.py     # 活体竞品基准适配器
│   ├── analytics.py       # 使用分析 & 基准存储
│   ├── benchmarks.py      # 五维基准测试引擎
│   ├── wisdom_laws.yaml   # 默认思维框架（包内置）
│   ├── hub/
│   │   ├── _core.py       # ActivationHub：双向激活 + 框架检测
│   │   ├── _conflict.py   # ConflictDetector：矛盾检测
│   │   ├── _frame_detector.py  # FrameAnchoringDetector：认知框架觉察
│   │   ├── _retriever.py  # MemoryRetriever：多路召回
│   │   ├── _scorer.py     # RelevanceScorer：加权评分
│   │   └── _ranker.py     # MMRRanker：多样性重排
│   ├── multi_agent/       # 多Agent协作
│   │   ├── registry.py    # AgentRegistry：专家注册与匹配
│   │   ├── router.py      # ExpertRouter：3级路由策略
│   │   ├── consensus.py   # ConsensusProtocol：投票/LLM/辩证综合
│   │   └── evolve.py      # DistributedEvolver：分布式进化
│   └── memory/
│       ├── core.py        # MemoryCore：统一记忆门面 + 三态隔离
│       ├── episodic.py    # EpisodicStore：L1 情节记忆
│       ├── semantic.py    # SemanticStore：知识三元组 + 因果图
│       ├── skill.py       # SkillStore：学习模式
│       ├── scene.py       # SceneStore：L2 场景块
│       ├── profile.py     # ProfileStore：L3 用户画像
│       ├── capture.py     # CapturePipeline：自动 L2+L3 提取
│       ├── causal.py      # CausalGraph：因果链推理
│       ├── consolidation.py  # ConsolidationEngine：记忆合并
│       ├── forgetting.py     # ForgettingEngine：艾宾浩斯衰减
│       ├── external.py       # 外部知识导入
│       └── search_utils.py   # FTS5 双路径搜索共用
├── dash/                  # 仪表盘 & API 服务
│   ├── server.py          # FastAPI（REST + SSE 流式 + 认证）
│   ├── providers.py       # LLM 提供商管理
│   └── frontend/          # Vue 3 仪表盘界面（中英文切换）
├── docs/                  # 文档（中英双语）
├── tests/                 # 639 测试，~97% 覆盖率
├── examples/              # 使用示例
└── pyproject.toml         # 构建配置
```

## 引用

如果在研究中使用了 SOMA，请引用：

```bibtex
@software{soma2026,
  title        = {SOMA: Somatic Wisdom Architecture},
  author       = {SOMA Project Team},
  year         = {2026},
  url          = {https://github.com/sunyan999999/soma},
  note         = {Apache 2.0},
  version      = {1.1.1},
}
```

## 许可证

Apache License 2.0。详见 [LICENSE](LICENSE)。

---

<p align="center">
  <sub>🧠 五分钟接入。一个能记忆、能推理、能协作、能进化的认知内核。</sub>
</p>
