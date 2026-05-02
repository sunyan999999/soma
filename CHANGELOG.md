# Changelog

All notable changes to SOMA will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

---
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
