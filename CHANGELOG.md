# Changelog

All notable changes to SOMA will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
