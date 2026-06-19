# Changelog / 变更日志

All notable changes to SOMA will be documented in this file. / 本文档记录 SOMA 所有重要变更。

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.1.9] — 2026-06-19

### soma.reason() Zero-LLM Autonomous Reasoning / 零LLM自主推理

**v1.1.9 introduces autonomous reasoning: full pipeline without external LLM.**
**v1.1.9 实现自主推理管道，无需外部LLM。**

### Added / 新增
- soma.reason(): Decompose(7 laws) → Activate(memories) → Reason(causal+analogy+hypothesis) → Synthesize(templates+evidence). Zero LLM, offline, ~500ms.
- soma_reason MCP tool
- Benchmark: Overall 80.0, Evolution 78.2 (all-time high)

## [1.1.8] — 2026-06-18

### force_evolve + Finance Sync + MCP / 进化修复 + 金融同步 + MCP扩展

**Evolution recovered from 70.2 to 76.4 via force_evolve threshold tuning.**
**进化分从70.2恢复到76.4。**

### Added / 新增
- evolve(force=True): lower thresholds, bigger adjustments, every 30th session
- soma_force_evolve MCP tool
- Finance Edition synced FAISS HNSW

## [1.1.7] — 2026-06-17

### v1.1.4 Baseline Rebuild / v1.1.4 基线重构

**v1.1.7 rebuilds from v1.1.4 baseline with only proven improvements. Benchmark: 83.4 (historical best), Memory 91.6, Wisdom 77.8, Latency 58ms (2x faster).**
**v1.1.7 从 v1.1.4 基线重构，仅保留验证有效的改进。基准 83.4 分（历史最佳），记忆 91.6，智慧 77.8，延迟 58ms（快 2 倍）。**

### Added / 新增
- FAISS HNSW efSearch=64: Recall 0.7→0.9 (Codex P0 validated)
- orchestrator.cross_validate(): Multi-agent cross-review on demand
- orchestrator.share_law_discovery(): >=2 agent consensus law sharing (every 20 solves)
- orchestrator.consensus_evolve(): Weighted-average consensus evolution (every 20 solves)

### Removed / 移除
- _auto_tune_from_history (opened analytics DB on init, caused latency)
- Adaptive recall_threshold (wisdom -2.0 regression)
- Index tolerance window (recall 0.9→0.5)
- Query cache (ineffective)

## [1.1.6] — 2026-06-11

### 跨会话自适应 + 反思闭环 + SSE实时推送 / Cross-Session Auto-Tuning + Reflection + SSE Push

**v1.1.6 让中道引擎从单会话优化升级为跨会话持续进化。**
**v1.1.6 upgrades Zhongdao from single-session optimization to cross-session continuous evolution.**

### Added / 新增

- **A 跨会话参数自适应 / Cross-Session Auto-Tuning**: 启动时自动从历史校正数据加载最优中道参数（≥5条时生效）。`auto_tune(days)` 手动触发。 / Auto-loads optimal Zhongdao params from history (>=5 corrections). Manual trigger available.
- **B 反思闭环 / Reflection Loop**: `soma.reflect()` 无参数时复盘最近20条决策记忆，识别模式+生成建议并写入记忆库。 / Batch reviews 20 recent decisions, identifies error/success patterns, generates suggestions, writes to memory.
- **D SSE实时推送 / SSE Push**: `GET /api/zhongdao/events` SSE端点，chat接口自动推送最近3条校正事件。 / SSE endpoint for real-time correction events, auto-pushes last 3 to frontend.

### Changed / 变更

- `soma/__init__.py` `__version__` → 1.1.6
- `pyproject.toml` version → 1.1.6
- `.github/SECURITY.md` supported versions: 1.1.6 is latest

---

## [1.1.5] — 2026-06-08

### 中道引擎智能激活 — Zhongdao Auto-Activation

**v1.1.5 引入中道引擎智能激活模式**，不再需要手动判断是否开启。

### Changed

- **智能激活 (`soma/config.py`)**: `enable_zhongdao` 新增 `"auto"` 选项。设为 `"auto"` 时，SOMA 根据问题复杂度自动决定：L1 简单问题跳过中道（零开销），L2+ 复杂问题自动启用偏差校正。
- **Agent 自适应 (`soma/agent.py`)**: `respond()` 和 `chat()` 管道在 auto 模式下自动跳过 L1 问题的中道校正步骤，节省不必要的开销。
- **SOMA 门面 (`soma/__init__.py`)**: `SOMA(enable_zhongdao="auto")` 一行配置即可启用智能模式。
- **Dash 默认 (`dash/server.py`)**: 生产环境默认使用 `"auto"` 模式。
- 100% 向后兼容：`True`/`False` 行为不变。

---

## [1.1.4] — 2026-06-04

### 中道引擎闭环与智能化 — Correction Effectiveness + Auto-Tuning + Archiving

**v1.1.4 闭合中道引擎反馈环路**，让校正从"执行"到"验证"到"优化"形成完整闭环。

### Added

- **B1 校正效果追踪 (`soma/analytics.py`)**: `get_correction_effectiveness(days)` — 返回每日校正次数趋势、各规律被校正频率分布、平均权重变化幅度。Dash 中道视图新增趋势柱状图和各规律校正频率面板。
- **B2 自动调参建议 (`soma/analytics.py`)**: `suggest_optimal_params(days)` — 基于历史校正数据智能推荐最优 threshold_ratio/penalty_factor/boost_factor/min_samples。Dash 中道视图新增调参建议卡片（当前 vs 推荐参数对比 + 文字建议）。
- **B3 Dash 趋势可视化 (`dash/frontend/src/views/ZhongdaoView.vue`)**: 新增校正趋势柱状图（14天）、各规律校正频率分布、智能调参建议卡片、归档清理按钮、时间范围选择器（7/14/30/90天）。
- **B4 自动归档清理 (`soma/analytics.py`)**: `archive_old_corrections(days=90)` — 将旧校正记录迁移到 `zhongdao_corrections_archive` 表，防止 DB 膨胀。Dash 提供一键归档按钮。
- **B5 零熵反馈修复**: Dash 移动端适配优化、API 端点冷却保护、中道视图 i18n 完善。
- **6 项新测试 (`tests/test_zhongdao.py`)**: 校正效果追踪/空数据/有数据、调参建议/无数据/过载场景、归档清理/空表/旧记录。
- **3 个新 API 端点** (`dash/server.py`): `GET /api/zhongdao/effectiveness`、`GET /api/zhongdao/suggest`、`POST /api/zhongdao/archive`。

### Changed

- `soma/__init__.py` `__version__` → 1.1.4
- `pyproject.toml` version → 1.1.4
- 测试从 644 → 650

---

## [1.1.3] — 2026-06-01

### 中道引擎深化 — 参数可配+可视化+跨Agent协调+持久化日志 (Zhongdao Deepening)

**v1.1.3 深化中道引擎**，基于零熵智库 v1.1.2 线上验证反馈（Wisdom +1.4, gini 0.2498→0.2226）进行四项升级。

### Added

- **A1 参数可配置化 (`soma/config.py`, `soma/__init__.py`)**: 中道引擎四个参数暴露为 `SOMAConfig` 字段：`zhongdao_threshold_ratio`(0.40)、`zhongdao_penalty_factor`(0.20)、`zhongdao_boost_factor`(0.15)、`zhongdao_min_samples`(5)。`SOMA(enable_zhongdao=True, zhongdao_threshold_ratio=0.30)` 一行配置。
- **A2 Dash 仪表盘可视化 (`dash/frontend/src/views/ZhongdaoView.vue`, `dash/server.py`)**: 侧边栏新增 ☯️ 中道引擎视图 — 规律热力图 + 校正时间线。3个API端点：`GET /api/zhongdao/status`、`GET /api/zhongdao/history`、`POST /api/zhongdao/reset`。支持中英双语。
- **A3 跨Agent趋同检测 (`soma/multi_agent/orchestrator.py`)**: `_detect_cross_agent_convergence` — ≥2个Agent在同一规律上过度使用>40%时自动标记，共识回答末尾附带中道协调提示脚注。中道配置通过 orchestrator 透传到各Agent。
- **A4 持久化校正日志 (`soma/analytics.py`)**: 新增 `zhongdao_corrections` SQLite表 + `record_zhongdao_correction`/`get_zhongdao_history`/`get_zhongdao_summary` 三个方法。每次校正事件写入数据库，支持按规律/类型过滤查询。
- **22项新测试 (`tests/test_zhongdao.py` +292行)**: 跨Agent趋同/持久化/参数化全覆盖。
- **安装脚本** (`scripts/install_v1.1.3.bat`, `scripts/install_v1.1.3.sh`, `scripts/verify_install.py`): Windows/Linux 一键安装 + 4项验证。

### Changed

- `soma/__init__.py` `__version__` → 1.1.3
- `pyproject.toml` version → 1.1.3
- `docs/index.md` API 参考版本标注更新
- `.github/SECURITY.md` 支持版本表：1.1.3 为 latest

---

## [1.1.2] — 2026-05-23

### 中道引擎 — 会话内实时规律使用偏差检测与自校正 (Zhongdao Engine)

**v1.1.2 引入中道引擎**，补齐 SOMA 认知校正体系最后一块拼图。SOMA 现拥有三层偏差校正：

| 层级 | 机制 | 作用域 | 持久化 |
|---|---|---|---|
| FrameAnchoringDetector | 用户侧框架锁定检测 | 每轮 | 无（仅提醒） |
| **ZhongdaoEngine (NEW)** | **AI侧规律过度使用校正** | **每会话** | **临时（单次调用）** |
| MetaEvolver | 跨会话趋势校正 | 批量（每5次会话） | SQLite（持久化） |

### Added

- **中道引擎 (`soma/zhongdao.py`)**: `ZhongdaoEngine` — 会话内实时规律使用偏差检测与自校正（~177行）。`track()` 记录每次 respond() 的规律使用，`detect_and_correct()` 当单条规律使用率 >40%（最少5次采样）触发：过度使用降权 ×0.80 + 被忽略关联规律提权注入 ×1.15（最多2条）。纯规则匹配，零 LLM 依赖，默认关闭。`reset()` 清空会话统计，`last_corrections` 暴露最近校正记录。
- **SOMAConfig 新字段 (`soma/config.py`)**: `enable_zhongdao: bool = False` — 默认关闭，100% 向后兼容。
- **SOMA_Agent 集成 (`soma/agent.py`)**: respond() 管道在 decompose() 之后插入中道校正（~10行），含详细日志输出（使用分布/降权详情/提权详情三行格式）。
- **SOMA 门面集成 (`soma/__init__.py`)**: `SOMA(enable_zhongdao=True)` 开启，chat() 返回字典含 zhongdao 校正信息。新增 `__version__` 属性。
- **12 项测试 (`tests/test_zhongdao.py`)**: 默认关闭/track累计/采样不足不触发/单条>40%触发降权/被忽略规律提权注入/权重打折加成/reset清空/last_corrections/端到端开启关闭/与FrameAnchoringDetector共存/rationale标记。

### Changed

- `__main__.py` 版本号 v0.6.0→v1.1.2（跨越5个版本未更新）
- `multi_agent/` 模块版本号 v1.1.1→v1.1.2
- `.github/SECURITY.md` 支持版本表：1.0.0→1.1.2 为 latest
- `docs/index.md` API 参考版本标注更新

### Benchmark (零熵智库验证)

- Run#38 (OFF) vs Run#39 (ON): Wisdom +1.4, gini 0.2498→0.2226, contradiction_analysis -9, pareto_principle +9, scalability 100.0 不变

---

## [1.1.1] — 2026-05-19

零熵智库本地测试反馈修复版本。核心修复：L1简单问题跳过推理框架（回复膨胀从25倍降至正常），多Agent路由补齐（所有已注册Agent均参与），嵌入模型预热。

### Fixed
- **回复严重膨胀**：L1简单问题跳过推理框架注入，用户"50字以内"要求从实际返回1268字降至约50字。`_build_prompt` 复杂度自适应（L1轻量/L2+完整框架），自动提取用户长度约束
- **多Agent仅激活1个**：`_solve_impl` 路由后补齐未匹配的已注册Agent（supplement策略），确保所有专家参与
- **嵌入模型首次失败**：`SOMAEmbedder.warmup()` 后台预热，`episodic.py` 错误信息增加"首次下载中"提示
- **Orchestrator API缺失**：新增 `list_agents()` 方法 + `_agents` 实例映射

### Changed
- `SOMA_Agent` 新增 `_current_complexity` 实例变量，跟踪问题复杂度
- `_build_prompt` 重构为两分支：L1轻量直答 / L2+完整推理框架
- `ExpertRouter.route_multi` 结果不足时自动补齐未匹配Agent

## [1.1.0] — 2026-05-19

### 协作深化 — 并行调度 + 分布式权重演化接入

**v1.0.0 的 SOMAOrchestrator 逐个串行问专家，3个专家每个200ms就得等600ms。v1.1.0 改为并行分发，同样3个专家只需等最慢那个。同时将 DistributedEvolver（268行，v1.0.0已写完但零调用）接入编排管道，每次求解自动记录各Agent表现，定期合并全局权重并回写校准。**

### Added

- **并行 Agent 调度 (`orchestrator.py`)**: `_dispatch_parallel` 方法，用 `ThreadPoolExecutor` 同时向所有专家提问。5专家实测加速比 **4.9x**（502ms → 102ms）。自动退化：单专家时不启动线程池。结果按注册顺序重排保证确定性。
- **分布式演化接入 (`orchestrator.py`)**: `_evolve_after_solve` 在每次 solve 后记录各 Agent 参与次数和成功率，每 N 次（默认10）自动调用 `DistributedEvolver.merge_weights()` + `apply_all()` 进行全局权重合并和回写。
- **3 个配置项 (`config.py`)**: `orchestration_parallel`（并行开关，默认True）、`orchestration_evolution_enabled`（演化开关，默认True）、`orchestration_evolution_interval`（合并间隔，默认10）。
- **14 项专项测试 (`tests/test_orchestrator_v1_1.py`)**: 覆盖串行/并行分发、失败隔离、确定性排序、单Agent退化、演化统计更新、定期合并、开关控制、注销清理、stats完整性、向后兼容。

### Changed

- `SOMAOrchestrator.__init__` 新增分布式演化器初始化、会话计数追踪
- `SOMAOrchestrator.create_agents` 自动注册 agent 到 DistributedEvolver
- `SOMAOrchestrator.remove_agent` 同步从演化器注销
- `SOMAOrchestrator.stats` 新增 `solve_count`、`parallel_enabled`、`evolution_enabled`、`evolution` 字段

### Compatibility

- 100% 向后兼容。存量 604 项测试全部通过。所有新功能在默认 `orchestration_mode="single"` 下不触发。
- SOMAConfig 新增字段均有默认值，现有配置无需修改。

---

## [1.0.0] — 2026-05-16

### 🏔️ v1.0 里程碑 — 五线交汇，认知内核成形

**从 v0.1.0 埋下第一颗种子，到 v1.0.0 五条能力线完整交汇。这不是功能堆叠出来的版本号，而是 SOMA 作为"AI Agent 认知内核"的架构宣言。**

v0.1 只有 5 条硬编码规律 + ChromaDB 存储。v1.0 拥有了完整的三层记忆体系（碎片→场景→画像）、七条自进化思维规律、因果推理+冲突检测+跨域类比引擎、多Agent协作系统、框架锚定觉察层、五维基准测试体系、以及 511 个全通过测试。

**设计原则贯彻始终**：所有新功能默认关闭，100% 向后兼容。从任何 0.x 版本升级到 v1.0.0，零代码改动。

### 五条能力线 v1.0 终态

| 能力线 | 始于 | 成于 | v1.0 核心交付 |
|--------|------|------|---------------|
| **记忆** | v0.1 ChromaDB | v1.0 三层体系 | L1情节碎片 + L2场景块(自动聚合) + L3用户画像(自动提炼) + 合并+遗忘+外部导入 |
| **推理** | v0.5 规律链 | v1.0 深度推理 | 因果链追溯 + 冲突检测 + 跨域类比 + 质量自评 + 图谱检索扩展 + 反向传播 |
| **协作** | v0.9.0 多Agent | v1.0 协作体系 | 专家注册+3级路由+3种共识+分布式进化+三态记忆隔离 |
| **进化** | v0.5 偏差检测 | v1.0 完整闭环 | 反思→调权→固化→分享 + 自动场景捕获 + 动态步长 |
| **工程** | v0.3 基准雏形 | v1.0 可信体系 | 511测试 + 五维基准(统计输出) + 50题标准数据集 + 竞品对比框架 |

### 关键技术指标 (v1.0.0)

- **511 项测试** 全部通过（v0.9.1: 485项）
- **五维基准综合评分**: 85.5/100（记忆97.6 / 智慧87.3 / 进化60.2 / 可伸缩100.0）
- **语义召回率**: 100%（1,050条生产记忆）
- **查询延迟**: 209ms（完整框架路径），~30ms（简单查询）
- **零外部服务依赖**: ONNX + SQLite + FAISS，纯 CPU 推理

### 从 v0.1 到 v1.0 的关键跃迁

```
v0.1.0        v0.5.0        v0.7.0        v0.8.0        v0.9.0        v0.9.1        v1.0.0
   │             │             │             │             │             │             │
会存储        会思考        会整理        会推理        会协作        会觉察        会分层
                                               ───────▶    ───────▶    ───────▶
                                   从"工具"到"认知伙伴"的演进方向
```

---

## [0.9.1] — 2026-05-13

### 零熵觉察层 — 从"解决问题"到"看见自己在怎么想"

**设计原则**: 100%向后兼容，所有新功能默认关闭。v0.8.0/v0.9.0 存量代码零改动升级。

v0.9.1 新增一个维度：**觉察**。在 v0.9.0 多Agent协作的基础上，SOMA 现在能察觉用户的认知框架锁定——当你连续从单一视角分析问题时，系统以脚注形式温和提醒，不强制、不阻断、不改变管道。

### Added

- **框架锚定检测器 (`soma/hub/_frame_detector.py`)**: `FrameAnchoringDetector` — 纯关键词匹配（零 LLM/嵌入器依赖），8对认知框架（技术/商业/管理/法律/短期/长期/内求/外求），对立框架自动建议。检测阈值：window=5轮，同一框架占比≥60%触发，冷却3600秒去重。
- **觉察提示注入 (`soma/agent.py`)**: `_build_prompt()` 在管道末尾以 blockquote 脚注形式注入觉察提示（修复前为 `##` 级标题插入问题前，干扰LLM输出——已修正为低干扰脚注格式）
- **ActivationHub 集成 (`soma/hub/_core.py`)**: 新增 `detect_frame_anchoring()` 方法，带 G1 错误隔离（try/except 包裹，异常绝不传播到核心管道）
- **SOMAConfig 新字段**: `enable_frame_detection: bool = False`（默认关闭）、`frame_detection_window: int = 5`
- **SOMA 门面集成 (`soma/__init__.py`)**: `respond()` 和 `chat()` 双路径均支持框架检测（仅在 config flag 开启时生效）
- **审核标准文档 (`docs/contribution-audit-standards.md`)**: 4类禁止内容 + 5柱接受量表（善行/善人/善心/善史/善修），审核员操作流程与10个边界案例

### Changed

- `ActivationHub.__init__` 新增可选 `frame_detector` 参数（末尾追加，不影响现有传参）
- `SOMA_Agent.__init__` 新增 `_recent_user_turns` 和 `_last_frame_anchoring` 实例变量
- `soma/hub/__init__.py` 导出 `FrameAnchoringDetector`

### Fixed

- **觉察提示干扰 LLM 输出质量**: 初版觉察提示以 `##` 级标题插入 `## 当前问题` 之前，且明确写出框架名称，与核心 prompt "不要在回答中提及任何规律/理论/框架的名称"产生指令矛盾，导致基准测试各项分数显著下降。修复：降级为 blockquote `>` 脚注、移至 prompt 最末尾（"重要"说明之后），视觉权重从核心段落级降为附注级。

### Compatibility

- 30+ 公开 API 签名零变更
- `SOMA()`, `SOMA.respond()`, `SOMA.chat()` 等所有公开方法行为不变（检测默认关闭）
- `pip install soma-wisdom==0.9.1` 直接替换 0.8.0/0.9.0，无需修改任何代码

---

## [0.9.0] — 2026-05-11

### 多智能体协作 — 从"单智者思考"到"多智者协作"

**生产验证**: 473项测试全通过。4个新模块（registry/router/evolve/consensus），~1,200行新增代码，零外部依赖增加。

v0.9.0 实现了从个体到群体的范式跃迁。多个 SOMA Agent 以团队形式协作，各自拥有独立记忆、独立进化路径和专长领域，通过专家路由、分布式演化和共识协议形成超越个体的集体智能。

### Added

- **Agent 注册表 (`soma/multi_agent/registry.py`)**: `AgentRegistry` — 专家注册/注销、专长标签匹配（精确1.0/模糊0.7/不匹配0.0）、会话统计自动追踪。纯内存字典+dataclass，零外部依赖。
- **专家路由器 (`soma/multi_agent/router.py`)**: `ExpertRouter` — 三层路由策略（L1关键词匹配8大领域80+关键词毫秒级 → L2语义匹配余弦相似度 → L3默认回退），零 LLM 参与路由决策。支持单专家路由和多专家路由（`route_multi()`）。
- **共识协议 (`soma/multi_agent/consensus.py`)**: `ConsensusProtocol` — 三层策略（L1加权投票/L2 LLM仲裁/L3辩证综合），输出带置信度的共识结果。支持无 LLM 的纯规则模式。
- **分布式演化 (`soma/multi_agent/evolve.py`)**: `DistributedEvolver` — 各Agent独立演化、定期合并全局权重（加权平均，样本量加权）、冲突仲裁（分歧>0.2时标记）。保留个体专长同时共享群体经验。
- **记忆三态隔离 (`soma/memory/core.py`)**: agent_id + group_id 维度的三态隔离——私有记忆（agent_id=自己）、组共享（shared_group_id）、全局记忆（agent_id=""）。所有检索路径透传隔离参数。
- **记忆检索增强**: `MemoryCore.query()` 新增跨域类比回退、图谱扩展BFS（O(1)哈希查找）、FTS5双路径（trigram + LIKE自动降级）

### Changed

- `SOMA.__init__` 新增 `agent_id` 和 `group_id` 参数（可选，默认""）
- `SOMA_Agent.__init__` 新增 `agent_id` 和 `group_id` 参数
- `MemoryCore` 所有检索方法支持 `agent_id`/`group_id` 隔离
- `ActivationHub` 管道新增反向传播（高激活记忆→建议焦点）
- 基准测试引擎支持多轮统计（均值±标准差/95%置信区间/CV%/稳定性评级）

### Compatibility

- 所有 v0.8.0 API 签名不变
- `agent_id` 和 `group_id` 为可选参数，不传则行为与 v0.8.0 一致

---

## [0.8.0] — 2026-05-09

### 知识图谱与推理引擎 — 从"记忆检索"到"认知推理"

**生产验证**: 零熵智库1752条真实记忆。基准测试综合80.5分（含因果推理+冲突检测+跨域类比新维度）。422项测试全通过。基准测试耗时181s→66s（-63%），查询延迟1098ms→209ms（-81%），系统负载0.97→0.13。

v0.8.0 引入六大认知能力：图谱检索扩展打破关键词孤岛，因果推理链回答"为什么"，冲突检测标记矛盾记忆，反向传播让记忆反向建议思维焦点，跨域类比在无关领域间架桥，质量评估自动评分反思输出。同时解决三项CPU性能瓶颈（逐条ONNX编码→批量、全图遍历O(N)→O(1)、AnalogyEngine无缓存重复扫描）。

### Added

- **图谱检索扩展 (`soma/memory/core.py`)**: `_expand_via_semantic_graph()` 从匹配关键词沿语义图谱BFS遍历（depth=2，衰减权重0.6→0.36），发现邻居概念作为扩展检索词。打破关键词检索孤岛——不再只搜用户输入的词，也搜图谱中关联的概念。O(K) hash查找替代O(N)全节点扫描。
- **因果推理引擎 (`soma/memory/causal.py`)**: `CausalGraph` 基于语义三元组构建因果链。`find_root_causes()` 回溯根本原因，`get_causal_chain()` 查找两节点间的因果路径。`hub.causal_analyze()` 在激活阶段自动追踪因果链路。支持环路检测与max_depth保护。
- **记忆冲突检测 (`soma/hub/_conflict.py`)**: `ConflictDetector` 在激活管道中识别逻辑矛盾的记忆对（如"降价→流失"vs"服务质量→流失"）。两阶段检测：(1) 否定模式匹配（中英双语），(2) 谓词冲突（causes↔prevents等高冲突对）。冲突分数≥0.5的记忆对自动降权（×0.4惩罚系数）。批量ONNX编码（单次推理替代逐条）确保<100ms延迟。
- **反向传播 (`soma/hub/_core.py`)**: `_backward_propagate()` — 高激活记忆（score≥0.4）的领域标签反向映射到思维规律，自动生成建议焦点。权重上限不超过任一直接触发规律的50%，防止偏离主线。
- **跨域类比引擎 (`soma/analogy.py`)**: `AnalogyEngine` 基于结构签名（in_predicates + out_predicates的frozenset）发现不同领域节点的拓扑同构。当两个看似无关的概念共享相同的图结构时自动桥接。节点扫描上限500、图谱上限2000防止大图CPU过载。结构签名缓存（边数变化时自动失效）。引擎实例在MemoryCore中惰性缓存复用。
- **反思质量评估 (`soma/quality.py`)**: `QualityEvaluator` 对LLM生成的推理输出进行三维评分（一致性、连贯性、可操作性），0-1分制。加权综合（一致性40% + 连贯性30% + 可操作性30%），输出质量等级（excellent/good/fair/poor）。低质量回答通过 `needs_reflection` 标记提示。

### Changed

- `MemoryCore.query()` 新增图谱扩展关键词和跨域类比回退路径。检索顺序：关键词→图谱扩展→混合搜索→语义→技能→类比回退（仅当情节结果<3条时触发）
- `MemoryCore._hybrid_search()` 新增图谱扩展词检索通道（权重×0.5，低于向量×2和关键词×1）
- `MemoryCore._expand_via_semantic_graph()` 从 `list_nodes()` O(N)全量遍历 → `kw in graph` O(K)哈希查找
- `MemoryCore.get_analogy_engine()` 新增实例缓存——引擎首次创建后跨查询复用结构签名缓存
- `ActivationHub.activate()` 管道新增步骤6（冲突检测）和步骤8（反向传播）。冲突检测仅在框架会话（有laws参数）中运行
- `ActivationHub.causal_analyze()` 从 `list_nodes()` → `kw in graph` O(K)查找
- `ConflictDetector` 构造器移除未使用的 `semantic_store` 参数
- `AnalogyEngine` 新增节点扫描上限(500)、图谱上限(2000)、结构签名字典缓存及边数变化失效机制
- `SOMA.chat()` 管道新增suggested_foci收集和quality_evaluation评分
- `benchmarks.py` `BenchmarkRun.version` 默认值从 `"0.6.1"` → `""`（自动获取）
- `dash/server.py` FastAPI版本从 `"0.6.1"` → `importlib.metadata.version("soma-wisdom")` 自动检测
- `competitors.py`、`scripts/live_benchmark.py` 硬编码版本号 → `_get_version()` 自动获取

### Fixed

- **CPU 100% 问题（零熵智库生产环境）**: 三处O(N×E)图遍历在1752条生产数据上被基准测试触发~65次：(1) `AnalogyEngine.find_analogous_nodes()` 全图扫描 `for node in graph.nodes()` × `_predicate_sets()` 每条迭代所有入/出边；(2) `_expand_via_semantic_graph()` 调用 `list_nodes()` 将NodeView转list；(3) `causal_analyze` 同样 `list_nodes()` 问题。修复：节点上限+缓存+O(1)hash查找
- **ConflictDetector 重复ONNX编码**: 改进前每条候选记忆单独编码（M=15→~210次ONNX调用/查询）。改进后预编码每条一次（M次），v0.8.0进一步改为批量编码（1次ONNX调用替代M次）
- **查询延迟回归 33ms→1098ms**: 根因为冲突检测在每次查询（包括简单`query_memory`）中逐条ONNX编码候选记忆（~10次×100ms=1000ms）。修复：批量编码+框架会话门控（仅laws参数时运行）
- **版本号硬编码 "0.6.1"**: 6处硬编码版本号（dash/server.py、benchmarks.py×4、competitors.py、live_benchmark.py）统一改为 `importlib.metadata.version("soma-wisdom")` 自动获取
- **Benchmark端点无保护机制**: `POST /api/benchmarks/run` 无冷却时间、无并发控制、无超时保护，直接同步调用 `run_full_benchmark()` 阻塞请求线程。修复：三层防护——运行中检查(409)、冷却间隔检查(429, 300s)、后台线程+600s超时。由零熵智库生产部署中发现并回传。（感谢 Qoder）

### Performance

| 指标 | v0.7.0 | v0.8.0 (修复前) | v0.8.0 (修复后) |
|------|:---:|:---:|:---:|
| 查询延迟 | 33ms | 1098ms | **209ms** |
| 基准测试耗时 | — | 181s | **66s** |
| 系统负载 | — | 0.97 | **0.13** |
| Dash CPU | — | 40.9% | **8.6%** |

---

## [0.7.0] — 2026-05-07

### 记忆智能 — 从"只增不减"到"合并+遗忘+外部知识"

**生产验证**: 零熵智库1752条真实记忆，7天无重启。基准测试综合84.8分（v0.6.1: 65.7），进化闭环从0→71.9，可伸缩性100。342项测试全通过。

v0.7.0 引入人脑式记忆管理三大机制：相似记忆自动摘要合并、低价值记忆主动遗忘归档、外部知识批量导入。让 AI Agent 的记忆系统从被动日志升级为主动精炼的知识引擎。

### Added

- **记忆摘要合并 (`soma/memory/consolidation.py`)**: ConsolidationEngine 提供两阶段相似度检测（FTS5 粗筛 + embedding 余弦相似度精排）、自动合并策略（保留高重要性为主体、独特信息追加、次要记忆标记待归档）、合并日志记录。`evolve()` 每次自动扫描最近30天记忆对，合并相似度 >0.85 的冗余记忆。
- **主动遗忘引擎 (`soma/memory/forgetting.py`)**: ForgettingEngine 实现三层遗忘策略——(1) 时间衰减遗忘（Ebbinghaus 指数衰减 `strength = importance × e^(-λ × days) × (1 + recall_count × 0.2)`），(2) 访问频率遗忘（30天未访问+低重要性→冷记忆归档），(3) 冗余清理（合并后14天宽限期→永久删除）。类别差异化衰减率（策略0.07/事实0.10/洞察0.12/决策0.15/外部0.20）。归档到 `episodic_archived` 表，支持 `recall_archived()` 浏览和 `restore()` 恢复。
- **外部知识集成 (`soma/memory/external.py`)**: KnowledgeSource 抽象基类 + FileSource（.md/.txt/.json/.jsonl/.yaml）分块导入 + URLSource（HTML抓取） + ExternalKnowledgeImporter。导入记忆标记 `memory_type="external"`，默认30天过期自动归档。`EpisodicStore.import_knowledge()` 一站式入口。
- **LLM 重试机制 (`soma/retry.py`)**: tenacity 指数退避重试（3次、2s→30s）、可重试异常智能识别（网络超时/连接错误/5xx vs 认证失败/参数错误不重试）、`@llm_retry` 装饰器应用于所有 LLM 调用点（agent._do_llm_call / law_discovery / causal_extraction）。
- **FTS5 搜索工具共用 (`soma/memory/search_utils.py`)**: 公共函数 `fts5_keyword_search()`，三库（episodic/semantic/skill）共用，FTS5 trigram + LIKE 双路径自动降级。

### Changed

- `SOMA.evolve()` 管道新增记忆合并和遗忘清理阶段，返回变更列表含 `memory_consolidation` 和 `memory_forgetting` 条目
- `EpisodicStore` 新增 5 个公共方法：`consolidate()` / `forget()` / `recall_archived()` / `restore_archived()` / `import_knowledge()`
- `_text_overlap()` 和 `_extract_unique_info()` 改用 jieba 分词，修复正则匹配中文整段为单 token 的问题
- `_extract_json()` 拆分列表/字典两种解析分支，修复列表元素解包崩溃
- `forgetting.py` 中 sqlite3.Row 访问改用 `row["key"] if "key" in row.keys() else default` 模式，修复 `.get()` 不存在的问题

### Fixed

- 中文文本相似度计算：正则 `[一-鿿]+` 将无空格中文匹配为整段单token → 改用 jieba 分词
- JSON 列表导入解包崩溃：`_extract_json` 中 `enumerate` 返回 `(index, item)` 被错误解包为 `(k, item)` → 拆分为 list/dict 两分支
- sqlite3.Row 访问崩溃：`row.get()` 不存在 → 改用 `in row.keys()` 检查

---

## [0.6.1] — 2026-05-06

### 工程质量 + 客观测试体系

v0.6.1 包含两部分工作：(1) 修复 0.6.0 在生产环境暴露的三个工程问题；(2) 建立四支柱客观测试评估体系，支撑对外可信展示。

### Added

- **多轮统计基准测试 (`MultiRunBenchmark`)**: 支持 N 轮独立运行（`--runs N`），每轮独立数据库。输出均值±标准差、95%置信区间、变异系数(CV%)、稳定性评级。CLI: `python -m soma.benchmarks --full --runs 5 --output reports/`。
- **活体竞品基准测试**: `scripts/live_benchmark.py` — 使用真实库（ChromaDB）、同数据同查询实测竞品性能。输出 Recall@5/10、MRR、P50/P95 延迟、能力矩阵对比。所有数据标注"实测"或"不可用"，不使用 mock 数据。
- **竞品适配器重写 (`competitors.py`)**: 移除所有 Dict mock 回退逻辑。适配器不可用时标记 `available=False` 并说明原因。ChromaDB 适配器使用真实客户端。
- **标准化公开数据集扩展**: `test_dataset.json` v1.1 从 30 题扩展到 50 题（新增战略决策、创新设计两个领域），新增 `difficulty` 字段（1-3）。
- **大规模检索数据集**: `benchmark_data/retrieval_1k.json` — 1000 条中文段落 + 50 个标注查询，覆盖 20 个领域，固定种子(42)可复现生成。
- **统计存储扩展 (`analytics.py`)**: `benchmark_runs` 表新增 `runs_count` 和 `multi_run_stats_json` 列。新增 `record_multi_benchmark()` 和 `get_latest_multi_benchmark()` 方法。
- **CI 基准测试工作流**: `.github/workflows/benchmark.yml` — PR 时轻量测试(N=1)，Release 时全量测试(N=5)+活体竞品对比，结果自动附加到 Release。
- **Docker 标准化环境**: `Dockerfile.bench` — 固定 Python/依赖版本，消除环境差异。`docker run soma-bench --full --runs 5`。

### Fixed

- **SSE 流式端点会话记录补全**: `/api/chat/stream` 新增 `analytics.record_session()` 调用，在 "done" 事件后持久化会话数据（问题、答案、foci、激活记忆、响应耗时、记忆统计、权重）。修复前所有 SSE 流式请求不进入 AnalyticsStore，导致仪表盘分析面板缺少会话历史。
- **向量维度修复**: `config.py` 中 `vector_dim` 恢复为 512。BAAI/bge-small-zh-v1.5 模型实际输出 512 维向量，此前被错误改为 384 导致 `could not broadcast input array from shape (512,) into shape (384,)` 运行时异常。
- **`_token_stream` 重构**: 改为产出原始文本内容（而非预格式化 SSE 字符串），由流式端点包装 SSE 事件同时累积完整答案文本，确保会话记录包含完整回答。

### Changed

- **FTS5 搜索工具共用化**: 新增 `soma/memory/search_utils.py` 提供 `fts5_keyword_search()` 公共函数，支持双路径搜索（FTS5 trigram + LIKE 降级）。`episodic.py` 和 `skill.py` 的 `query_by_keywords()` 均委托至此。减少约 80 行重复代码。
- **`skill.py` 查询精简**: `query_by_keywords()` 从约 100 行缩减至约 25 行委托调用，移除独立的 `_escape_fts5` 静态方法。
- **异常日志增强**: SSE 会话记录失败时通过 `logging.getLogger("soma.dash").warning()` 输出完整 traceback，替换原先静默 `except Exception: pass`。

### Security

- **会话记录完整性**: SSE 流式端点现在与非流式端点行为一致，所有会话数据进入 AnalyticsStore 供仪表盘分析。

---

## [0.6.0] — 2026-05-04

### 推理引擎 — 从"提供角度"到"执行推理"

v0.6.0 的核心突破是在 LLM 调用之前插入 SOMA 自己的推理步骤。不再把问题直接丢给 LLM，而是先用模板将问题拆解为结构化推理任务——每条思维规律对应专属引导问题和可检验假设，并自动收集支持/反对证据对照。同时引入触发词自动扩展和思维模板挖掘，让 SOMA 的思维框架随使用自我生长。

### Added

- **结构化推理框架 (Pre-LLM Reasoning)**: `SOMA_Agent` 新增 `_REASONING_TEMPLATES`（7个）、`_HYPOTHESIS_TEMPLATES`（7个）、`_COMBO_REASONING`（6个）三层模板字典。`_execute_reasoning()` 在 LLM 调用前为每个 Focus 匹配专属推理模板、生成假设、收集正反证据，构建结构化推理框架注入 Prompt。
- **假设检验框架**: 每条规律对应一个含 `{problem}` 占位符的可检验假设模板（如第一性原理→"忽略所有现有方案，从基本要素重新构建会得到___"），LLM 需结合证据给出检验结论。
- **组合模板优先匹配**: `_match_template()` 对 combo_ 前缀的 law_id 优先匹配 `_COMBO_REASONING` 再回退 `_REASONING_TEMPLATES`，确保组合规律获得专属分析维度（如"根因系统分析""动态张力分析"等）。
- **Foci 上限控制**: L3 复杂度超过 7 个 foci 时按权重降序取前 7，防止 Prompt 过长。
- **触发词自动扩展**: `MetaEvolver.track_triggers()` 追踪问题关键词与成功规律的共现关系，同一词跨 5 次不同会话共现后 `_promote_triggers()` 自动提升为正式触发词。跳过 combo_ 和 _anti 规律防止污染。
- **思维模板挖掘**: `MetaEvolver.track_focus_pattern()` 记录"问题领域→规律组合"映射，同一 (domain, law_ids) 模式出现 5 次后 `_mine_thought_templates()` 固化为可复用思维模板。
- **因果关系自动抽取**: `SOMA_Agent._extract_causal_relations()` 在 L3 复杂问题回答后，用轻量 prompt（约 200 tokens）从 LLM 回答中提取"主语|谓语|宾语"三元组，以 confidence=0.4 存入语义记忆。失败不影响主流程。
- **反视角证据对照**: `_execute_reasoning()` 在收集支持证据的同时收集 `anti_confirmation_search()` 返回的反视角证据（L2/L3 问题），在 Prompt 中以"支持/反对证据对照"呈现。
- **推理框架可观察**: `_last_reasoning`、`_last_anti_memories`、`_last_prompt` 三个实例变量保存最近一次推理过程，供仪表盘和外部调试读取。
- **因果抽取配置**: `SOMAConfig` 新增 `causal_extraction: bool = False` 和 `causal_extraction_complexity: int = 3` 两个配置项，管控因果抽取的开关和触发阈值。
- **SQLite 持久化扩展**: `evolver.db` 新增 `candidate_triggers` 和 `focus_patterns` 两张表，触发词候选和思维模板模式跨会话持久化。

### Changed

- `SOMA_Agent._build_prompt()` 重构为"推理框架 + 假设检验 + 证据对照 + 反视角"四段结构
- `SOMA_Agent.respond()` 管道新增 Step 2.6（推理框架构建）和 Step 4.5（因果抽取）
- `MetaEvolver.set_current_context()` 新增 `problem` 参数，供触发词追踪使用
- `MetaEvolver.reflect()` 中 v0.6.0 追踪（触发词+思维模式）仅在成功时执行
- `MetaEvolver.clear_log()` 新增 v0.6.0 表的清理（candidate_triggers / focus_patterns）
- `SOMA.chat()` 返回字典新增 `reasoning` 键，供调用方获取推理框架结果

### Fixed

- `_promote_triggers()` 增加 `law_found` 标记——仅当对应规律存在时才删除候选词记录，避免候选词永存无法清理
- `_mine_thought_templates()` 不再删除已挖掘的 `focus_patterns` 记录，保留数据供后续分析
- `_match_template()` 支持前缀/双向子串匹配，确保 combo_ 模板不会因命名变体而遗漏

---

## [0.5.0] — 2026-05-04

### 思维框架深化 — 从"平铺列表"到"推理网络"

v0.5.0 的核心主题是激活已有的 `relations` 字段，让 7 条思维规律从独立触发升级为协同推理网络。
同时引入认知偏差检测、确认偏误防御、问题复杂度自适应等机制，让 SOMA 的思考更接近真正的"智者"。

### Added

- **规律链推理 (Law Chaining)**: `WisdomEngine.decompose()` 新增阶段2——当规律A的关键词命中问题时，其 `relations` 中的关联规律B获得权重加成（部分命中 ×0.50，纯链式 ×0.35）。利用 `wisdom_laws.yaml` 中已定义但从未使用的 `relations` 字段。
- **规律组合模板**: `decompose()` 新增阶段2.5——当一对规律同时被直接触发时，生成第三个"合成视角"Focus（权重 = 两规律均值 ×1.1）。预定义 6 组组合：根因系统分析、动态张力分析、辩证反思、要素优先级排序、系统演进洞察、跨域本质映射。
- **认知偏差检测与纠正**: `MetaEvolver.evolve()` 新增阶段0——当某规律使用频率 >40% 时自动降权 0.05（防止思维固化）；当某规律使用频率 <3% 但成功率 >60% 时自动提权 0.03（发掘被忽视的优质规律）。
- **确认偏误检测**: `ActivationHub` 新增 `anti_confirmation_search()` 方法——为每个 Focus 用否定词（"不是""反对""反面"）构造反视角查询，检索可能矛盾的记忆证据。L2/L3 复杂度问题自动启用，反视角记忆注入 Prompt。
- **可用性启发式修正**: `RelevanceScorer.compute_score()` 新增认知修正——当记忆 `access_count > 20` 且 `importance < 0.5` 时，激活分数 ×0.7。防止"容易想起的记忆就是重要记忆"的认知偏差。
- **问题复杂度自动评级**: `SOMA_Agent._assess_complexity()` 根据问题长度和深度词（"为什么/如何/深层/根本/矛盾/机制"等12个）将问题分为 L1/L2/L3。L1 精简 foci 至 2 个、降低 top_k；L3 保留全部 foci、翻倍 top_k（上限 15）。
- **向量语义匹配兜底**: `WisdomEngine._semantic_match()` — 当关键词完全无匹配时，用 ONNX 嵌入向量计算问题与各规律的余弦相似度（阈值 0.35），替代纯随机选取。`WisdomEngine` 现在可选接收 `embedder` 参数。
- **动态权重调整步长**: `MetaEvolver._calc_step()` 根据样本量自适应——≥15 样本 → 0.03，≥5 样本 → 0.02，<5 样本 → 0.01。替代原先固定 ±0.02 步长。
- **LLM 缓存可配置**: `SOMAConfig` 新增 `llm_cache_ttl`（默认 600s）和 `llm_cache_max_size`（默认 50），替代 `_call_llm()` 中的魔法数字。
- **动态语境排序**: `decompose()` 的 Focus 排序策略改为 `weight × (1 + 关键词命中密度 × 0.3)`，让更贴合问题语境的规律排在前列。
- **反馈闭环修复**: `SOMA.respond()` 和 `SOMA.chat()` 现在正确区分 LLM 成功调用与 mock 回退，`outcome` 不再无条件标记为 "success"。

### Changed

- `WisdomEngine.__init__()` 新增可选 `embedder` 参数（向后兼容）
- `SOMA_Agent.__init__()` 将 embedder 创建移至引擎初始化之前
- `SOMA.chat()` 现在与 `respond()` 共享复杂度评估、top_k 自适应和确认偏误检测
- `_build_prompt()` 的 Prompt 模板新增"反面视角与潜在矛盾"段落

---

## [0.4.2] — 2026-05-04
## [0.4.0] — 2026-05-02

### Added
- **API 稳定性承诺**: `API_STABILITY.md` 明确冻结 SOMA 门面类的 13 个公共方法、3 个数据模型、2 个工厂函数，承诺主版本号变更前不破坏向后兼容
- **社区统计 sidebar**: 导航栏自动获取 GitHub Stars/Forks/Watchers/Contributors + 14日 Clones/Visitors 流量 + PyPI 下载量，1 小时缓存自动刷新
- **竞品 GitHub 星数实时获取**: BenchmarkView 竞品对比表格自动填充 live star count
- **MkDocs 文档站点**: MkDocs Material + mkdocstrings 自动 API 文档生成，GitHub Actions 自动部署到 GitHub Pages
- **Docker 部署**: Dockerfile + docker-compose.yml + .dockerignore，一键 `docker compose up -d` 部署
- **社区治理文件**: CODE_OF_CONDUCT.md、CONTRIBUTING.md 中英双语，GitHub 链接修正
- **Awesome List 提交**: 4 个 awesome list PR（e2b-dev/awesome-ai-agents、Shubhamsaboo/awesome-llm-apps、vinta/awesome-python、ikaijua/Awesome-AITools）
- **覆盖率 CI 集成**: CI 工作流添加 pytest-cov 覆盖率收集 + Codecov 上传，README 添加 Codecov badge
- **记忆数据隔离**: episodic/semantic/skill 三库均支持 `user_id`/`namespace`/`session_id` 维度隔离，全 API 链路（SOMA → Agent → Hub → Retriever → MemoryCore → Store）透传
- **时间衰减修复**: 近因衰减公式从 `1/(1+days)` 改为 `exp(-days/7)` 指数衰减（半衰期7天）；召回增加30天时间窗口过滤；RRF 融合施加时间惩罚因子
- **数据隔离测试**: 新增 `test_isolation.py`（10个用例）覆盖三库 user_id/namespace 隔离 + 去重 + LIKE兜底路径
- **时间窗口测试**: 新增 `test_time_window.py`（11个用例）覆盖三库 max_age_days 过滤 + 边界值 + 自定义参数
- **审计修复回归测试**: 新增 `test_audit_fixes.py`（13个用例）覆盖 LLM 缓存隔离 / access_count 持久化 / 三元组去重 / 技能去重 / 数据库迁移兼容
- **Pre-commit 验证脚本**: 新增 `scripts/verify_before_commit.py`（5步 15项检查）包含全量测试 + 数据隔离端到端 + 时间窗口 + 缓存隔离 + 迁移兼容性，退出码 0=通过
- **资源管理 close()**: MemoryCore / SOMA_Agent / SOMA 三层添加 `close()` 方法和 context manager 支持（`__enter__`/`__exit__`），SQLite 连接可显式释放
- **日志补齐**: 嵌入向量生成失败 → `logging.warning`；三库 FTS5 降级 LIKE → `logging.info`，生产环境可观测
- **配置清理**: `episodic_persist_dir` 默认值从 `chroma_data` 改为 `soma_data`；`base.py` 增加 `_RECENCY_HALF_LIFE_DAYS` 与时间窗口关系的注释
- **输入验证加固**: `ChatRequest.problem` 添加 `max_length=10000`；`ProviderUpdateRequest.base_url` 改为 `HttpUrl` 类型；`ReflectRequest.outcome` 改为 `Literal` 枚举

### Fixed
- **时间错乱**: 记忆检索不会再将7天前的事件以相近权重混入今日回复（30天外记忆权重<2%）
- **数据泄漏**: 所有记忆存储/查询均支持 user_id 级别的命名空间隔离，杜绝跨用户数据污染
- **`_like_fallback` 隔离失效**: episodic.py LIKE 兜底路径 OR 连接改为 AND，修复 user_id 过滤条件被绕过
- **语义图 namespace 过滤失效**: semantic.py LIKE 路径从内存图遍历改为 SQLite 查询，同时修复 namespace 缺漏和子串误判
- **LLM 缓存跨用户泄漏**: agent.py 缓存键加入 user_id，防止同内容查询命中其他用户的缓存响应
- **API Key 前端泄漏**: 移除 SOMA_API_KEY 的 HTML 注入，改为 `/api/auth/status` + sessionStorage
- **XSS 风险**: ChatView LLM 输出先转义 HTML 实体再 Markdown 渲染，防止 `<script>` 注入
- **CORS 过于宽松**: `allow_origins=["*"]` 改为可配置的 localhost 白名单（环境变量 SOMA_CORS_ORIGINS）
- **FTS 双引号未转义**: 三库 FTS5 查询关键词中的 `"` 正确转义为 `""`，防止语法损坏
- **skill.py 缺时间窗口**: 添加默认 90 天时间窗口过滤
- **异常静默吞没**: `__init__.py` 的 `except Exception` 添加 `logging.error` 记录完整 traceback
- **Dash DevSidecar 代理拦截**: `_http_get_json()` 绕过系统代理 + SSL 证书回退，修复 GitHub API 返回 500 错误
- **Dash 认证流程断裂**: App.vue `onMounted` 中调用 `initAuth()`，修复「请设置 X-API-Key」错误
- **API Key 自动生成**: 未设置 `SOMA_API_KEY` 时自动生成随机密钥 (`secrets.token_hex(16)`) 并打印控制台、localhost 自动跳过认证
- **三元组/技能去重缺失**: semantic `add_triple()` 和 skill `add_skill()` 添加去重检查，同 namespace/user_id 内相同内容不重复插入
- **access_count 未持久化**: `respond()` 和 `chat()` 路径调用 `increment_access()`，访问计数正确写入 SQLite 并跨会话保留
- **数据库迁移顺序**: ALTER TABLE 添加列移到 CREATE INDEX 之前，修复旧数据库首次启动崩溃

---
## [0.3.3b2] — 2026-05-01

### Added
- **五维雷达图**: BenchmarkView 新增 ECharts 雷达图，单次基准测试五维（综合/记忆/智慧/进化/伸缩性）直观展示
- **版本对比柱状图**: 最新两个版本并肩对比，hover 查看差值，柱顶显示数值
- **标准测试数据集 (30题)**: `soma/test_dataset.json`，三大类各10题（跨域推理/深层归因/经验借鉴），附参考解法和记忆标签，benchmark 引擎自动加载
- **离线批量注入脚本**: `scripts/migrate_to_soma.py`，支持 JSON/CSV/Markdown 三种格式，自动段落拆分和三元组抽取
- **uvicorn 生产模式**: 环境变量 `SOMA_PROD=1` 切换生产配置（单 worker、并发限制20、keepalive 30s、500请求自动重启）
- **开发者集成指南**: README 新增 Claude Code / VS Code / REST API 集成示例，含真实项目收益数据

### Fixed
- **adaptive_top_k 硬上限**: 基准测试语义召回 `max(20, total * 0.15)` → `min(max(20, total * 0.15), 50)`，大数据量（万条级）fastembed CPU 模式不再卡死，10 秒完成测试
- **伸缩性评分假满分**: 小数据集(<500条)禁用对数外推，标记为"数据不足"并重分配权重，不再显示100分
- **数据目录统一**: 4个模块（analytics/evolve/semantic/server）默认数据目录统一为 `soma_data/`，消除 dashboard 找不到 benchmark 历史的问题
- **BenchmarkView 空白页**: 修复 Vue computed 声明顺序导致 JS TDZ ReferenceError，watch/lifecycle 移至 script 末尾

---

## [0.3.3b1] — 2026-05-01

### Added
- **基准趋势折线图**: BenchmarkView 用 ECharts 五线折线图替换 CSS 条形图，5 条线（总分/记忆/智慧/进化/伸缩性），hover 看数值，中英文图例
- **伸缩性维度持久化**: `benchmark_runs` 表新增 `score_scalability` + `scalability_json` 列，自动迁移兼容旧库
- **SOMA Hook CLI 桥接**: Go 版 `cmd/soma-hook` + Shell 版 `soma-hook.sh`，实现 Glaude Hook 协议与 SOMA API 的桥梁
- **Glaude Skills**: `soma-remember` / `soma-recall`，存入 `~/.glaude/skills/`，Glaude 启动自动加载
- **Glaude Hook 配置**: 3 个生命周期 Hook（PostToolUse/SessionStart/Stop），自动记录工具执行结果到 SOMA

### Changed
- `AnalyticsStore.get_latest_benchmark()` / `get_benchmark_history()` 返回 scalability 分数和数据
- POST `/api/benchmarks/run` 响应增加 scalability 维度
- BenchmarkView 评分卡片 4→5（新增伸缩性），指标卡片 3→4（新增伸缩性指标）
- SOMA Go Client 修正所有 API 路径（/api/remember→/api/memory/add 等）

### Fixed
- Go Client `Stats()` 调用不存在的 `/api/stats` → 修正为 `/api/memory/stats`

---

## [0.3.2b1] — 2026-04-30

### Added
- **基准测试 v2**: 数据量自适应归一化评分（分档阈值），新增伸缩性维度（ScalabilityBenchmark）+ FTS5 加速比指标
- **自适应 top_k / recall_threshold**: Agent 根据记忆总量自动调整，消除大数据量"过度严格"和小数据量"过度宽松"
- **LLM exponential backoff**: 3 次重试 + 1s/2s 退避 + 不可重试错误（401/403/quota）识别
- **SQLite 性能 PRAGMA**: synchronous=NORMAL, cache_size=-8000, mmap_size=256MB, busy_timeout=5000
- **Alpha 收尾边界测试**: 21 个压力测试（1000+/5000+并发、WAL 压力、LLM 全故障、FTS5 正确性）
- **SOMA Go Client**: REST API 客户端 + Glaude MemoryStore 适配器 + Skill 文件

### Changed
- 语义召回测试 top_k 自适应：按数据量比例调整（max(20, total×0.15)）
- 进化评分改质量导向：最近30次反思成功率替代累积总数
- 合成增益降级：无消融数据时权重自动重分配
- `soma/benchmarks.py` 内部重构：新增 DataScale 枚举、normalize_score/normalize_scores

### Fixed
- SemanticStore LIKE 兜底路径缺少边搜索
- `/api/chat` LLM 失败返回 500 → 自动回退 Mock
- SQLite 并发异常崩溃 → 非关键操作异常隔离
- 版本号不一致 → 统一使用 app.version

---

## [0.3.1b1] — 2026-04-30

### Added
- **FTS5 全文索引**: EpisodicStore / SemanticStore / SkillStore 全部启用 FTS5 trigram 索引，3 字及以上中文关键词搜索从 LIKE 全表扫描（O(n)）降至 FTS5 MATCH（毫秒级）
- **WAL 日志模式**: 所有 SQLite 连接启用 Write-Ahead Logging，读写不再互斥，支持并发读取
- **自动迁移**: 存量数据库首次打开时自动创建 FTS 表并回填历史数据，零停机升级
- **基准测试 v2**: 数据量自适应归一化评分，分档阈值消除大数据量"假降分"；新增伸缩性维度（ScalabilityBenchmark）+ FTS5 加速比指标
- **Alpha 收尾边界测试**: 21 个新增压力测试（大规模并发 1000+/5000+、WAL 压力、LLM 全故障、FTS5 正确性、三库联合），全部通过
- **SOMA Go Client**: `soma-go-client/` 独立 Go 包 — REST API 客户端 + Glaude MemoryStore 适配器 + 2 个 Skill 文件 + Hook 集成
- **技术文章**: `docs/articles/why-wisdom-framework.md`（"不只是 RAG"）

### Changed
- `query_by_keywords()` 三库统一改为 FTS5 MATCH（长关键词）+ LIKE（短关键词兜底）双路径搜索
- SemanticStore 关键词搜索从纯 Python 内存遍历改为 FTS5 索引查询
- **自适应 top_k / recall_threshold**: Agent 根据记忆总量自动调整参数（3→5→8→10 / 0.05→0.02→0.01→0.005）
- **LLM 调用 exponential backoff**: 3 次重试 + 1s/2s 退避 + 不可重试错误（401/403/quota）识别
- **SQLite 性能 PRAGMA**: synchronous=NORMAL, cache_size=-8000, mmap_size=256MB, busy_timeout=5000
- **语义召回率测试 top_k 自适应**: 按数据量比例调整（max(20, total×0.15)），消除大数据量下测试记忆被淹没的问题
- **进化评分改质量导向**: 最近 30 次反思成功率替代累积总次数
- **合成增益降级**: 缺少消融数据时权重重分配（30→42, 25→33, 20→25），不再直接丢 25 分
- `soma/benchmarks.py` 内部重构：新增 DataScale 枚举、normalize_score/normalize_scores 自适应归一化函数
- `soma/config.py` 新增 adaptive_top_k/adaptive_recall_threshold 辅助函数

### Fixed
- 修复 SemanticStore LIKE 兜底路径缺少边搜索的问题（短关键词搜索谓词）
- 修复 `/api/chat` LLM 调用失败时直接返回 500 的问题，现在自动回退到 Mock 模式
- 修复 SQLite 并发访问异常（`increment_access`）导致整个请求崩溃的问题，数据库操作失败不再影响主流程
- 修复版本号不一致问题，统一使用 `app.version`

## [0.3.0b1] — 2026-04-29

### Added
- **MMR diversity re-ranking**: ActivationHub now uses Maximal Marginal Relevance to balance relevance with content/source diversity, preventing near-duplicate memories from dominating results
- **Hub pluggable architecture**: `ActivationHub` decomposed into 3-stage pipeline — `MemoryRetriever` (recall), `RelevanceScorer` (scoring), `MMRRanker` (re-ranking) — all replaceable via constructor injection or `pyproject.toml` entry points
- **Entry points plugin system**: `[project.entry-points."soma.plugins"]` — external packages can register custom retriever/scorer/ranker implementations
- **Frontend route lazy loading**: Vue Router dynamic imports reduce initial JS payload by 75% (756KB → 188KB)

### Changed
- `soma/hub.py` → facade re-export; implementation moved to `soma/hub/` sub-package
- `hub.activate()` now applies threshold AFTER MMR re-ranking for wider candidate pool
- Hard dedup at >88% Jaccard similarity during MMR selection

### Fixed
- Version strings unified to "0.3.0b1" across all modules
- `benchmarksRun()` API function added to frontend

---

## [0.2.0-alpha] — 2026-04-26

### Added
- **Semantic Search**: ONNX-powered vector embeddings (fastembed) with FAISS ANN search, replacing pure keyword matching
- **Bidirectional Activation**: Weighted Reciprocal Rank Fusion (semantic ×2 + keyword ×1) for memory retrieval
- **WisdomEngine v2**: jieba Chinese tokenization with stopword filtering and expanded trigger sets
- **MetaEvolver**: Full evolution loop — auto-adjust law weights every 10 sessions (±2%), skill solidification
- **Memory Dedup**: SHA256 content-hash based deduplication for episodic memories
- **Dashboard**: Vue 3 + Vite frontend with 6 views (Chat, Framework, Memory, Analytics, Benchmark, Settings)
- **REST API**: FastAPI server with SSE streaming, API key auth, multi-provider LLM management
- **3D Benchmark Engine**: Memory / Wisdom / Evolution dimensions with competitor comparison data
- **AnalyticsStore**: SQLite-based session tracking with full context recording
- **LangChain Tool**: `create_soma_tool()` for LangChain agent integration
- **CLI Quickstart**: `python -m soma` for one-command verification
- **CI/CD**: GitHub Actions pipeline (ruff + mypy + pytest + build + benchmark) on Python 3.10/3.11/3.12

### Changed
- Vector store: ChromaDB → SQLite + FAISS (zero-dependency deployment)
- Embedding: OpenAI API → ONNX fastembed (CPU inference, offline capable)
- Keyword engine: simple split → jieba + stopword + punctuation filtering
- Wisdom law triggers expanded (5 → 12 items per law on average)

### Fixed
- Memory recall threshold tuning for better precision/recall balance
- Edge case: empty memory store graceful degradation
- Dedup race condition on concurrent inserts

---

## [0.1.0] — 2025-05

### Added
- **WisdomEngine**: Hardcoded 5-law wisdom framework with keyword trigger matching
- **MemoryCore**: ChromaDB episodic storage + NetworkX semantic graph
- **ActivationHub**: Keyword-match memory recall with simple relevance sorting
- **SOMA_Agent**: End-to-end `respond()` pipeline (decompose → recall → template synthesis)
- **Unit tests**: Core module test coverage
- **wisdom_laws.yaml**: Initial framework configuration

---

## 变更日志

格式基于 [Keep a Changelog](https://keepachangelogen/zh-CN/1.0.0/)。

### [0.3.1b1] — 2026-04-30

#### 新增
- **FTS5 全文索引**: EpisodicStore / SemanticStore / SkillStore 全部启用 FTS5 trigram 索引
- **WAL 日志模式**: 所有 SQLite 连接启用 WAL，读写不再互斥
- **自动迁移**: 存量数据库首次打开自动创建 FTS 表并回填历史数据
- **基准测试 v2**: 数据量自适应归一化评分，分档阈值消除大数据量假降分；新增伸缩性维度 + FTS5 加速比
- **Alpha 收尾边界测试**: 21 个压力测试（1000+/5000+并发、WAL 压力、LLM 全故障、FTS5 正确性）
- **SOMA Go Client**: REST API 客户端 + Glaude MemoryStore 适配器 + Skill + Hook 集成
- **技术文章**: "不只是 RAG — 为什么 AI Agent 需要智慧框架而非知识库"

#### 变更
- `query_by_keywords()` 三库统一改为 FTS5 MATCH + LIKE 兜底双路径
- SemanticStore 关键词搜索改为 FTS5 索引查询
- **自适应 top_k/recall_threshold**: 按记忆总量自动调整，消大数据量淹没
- **LLM exponential backoff**: 3 次重试 + 1s/2s 退避 + 不可重试错误识别
- **SQLite PRAGMA 性能调优**: synchronous=NORMAL, 8MB cache, 256MB mmap
- **语义召回测试 top_k 自适应**: 按数据量比例调整，消除大数据量测试记忆被淹没问题
- **进化评分质量导向**: 最近 30 次反思成功率替代累积总数
- **合成增益降级**: 无消融数据时权重自动重分配

#### 修复
- SemanticStore LIKE 兜底路径缺少边搜索的问题
- LLM 调用失败 500 错误 → 自动回退 Mock
- SQLite 并发异常崩溃 → 非关键操作异常隔离
- 版本号不一致 → 统一使用 app.version

### [0.3.0b1] — 2026-04-29

#### 新增
- **MMR 多样性重排**: ActivationHub 使用最大边界相关性算法平衡关联度与内容/来源多样性，避免高度重复记忆占据全部结果
- **Hub 可插拔架构**: `ActivationHub` 拆分为三段式管道 — `MemoryRetriever`（多路召回）、`RelevanceScorer`（相关性打分）、`MMRRanker`（多样性重排）— 均可通过构造器注入或 `pyproject.toml` entry points 替换
- **Entry points 插件体系**: `[project.entry-points."soma.plugins"]` — 外部包可注册自定义 retriever/scorer/ranker 实现
- **前端路由懒加载**: Vue Router 动态 import 将首屏 JS 体积压缩 75%（756KB → 188KB）

#### 变更
- `soma/hub.py` → 门面 re-export；实现迁移至 `soma/hub/` 子包
- `hub.activate()` 阈值过滤移至 MMR 重排之后，扩大候选池
- MMR 选择阶段 >88% Jaccard 相似度硬去重

#### 修复
- 全模块版本字符串统一为 "0.3.0b1"
- 前端补全 `benchmarksRun()` API 函数

### [0.2.0-alpha] — 2026-04-26

#### 新增
- **语义搜索**: ONNX 向量嵌入 (fastembed) + FAISS 近邻搜索，替代纯关键词匹配
- **双向激活**: 加权倒数排序融合（语义×2 + 关键词×1）记忆检索
- **WisdomEngine v2**: jieba 中文分词 + 停用词过滤 + 扩展触发词集
- **MetaEvolver**: 完整进化闭环 — 每10次会话自动调权(±2%)、技能固化
- **记忆去重**: 基于 SHA256 内容哈希的情节记忆去重
- **Dashboard**: Vue 3 + Vite 前端（6 个视图）
- **REST API**: FastAPI 服务 + SSE 流式 + API Key 认证 + 多模型管理
- **3D 基准引擎**: 记忆/智慧/进化三维评测 + 竞品对比数据
- **AnalyticsStore**: SQLite 会话追踪与完整上下文记录
- **LangChain 工具**: `create_soma_tool()` 集成
- **CLI 快速入口**: `python -m soma` 一键验证
- **CI/CD**: GitHub Actions (ruff + mypy + pytest + build + benchmark)，支持 Python 3.10/3.11/3.12

#### 变更
- 向量存储: ChromaDB → SQLite + FAISS
- 嵌入模型: OpenAI API → ONNX fastembed
- 关键词引擎: 简单分割 → jieba + 停用词 + 标点过滤
- 规律触发词扩充（平均 5 → 12 个）

#### 修复
- 记忆召回阈值微调，提升精确率/召回率平衡
- 空记忆库的优雅降级
- 并发写入的去重竞态

### [0.1.0] — 2025-05

#### 新增
- WisdomEngine: 5条硬编码规律 + 关键词触发匹配
- MemoryCore: ChromaDB 情节存储 + NetworkX 语义图谱
- ActivationHub: 关键词匹配召回 + 简单关联排序
- SOMA_Agent: 端到端 respond() 管道（拆解→召回→模板合成）
- 单元测试覆盖核心模块
- wisdom_laws.yaml 初始框架配置
