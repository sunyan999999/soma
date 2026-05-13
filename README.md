# SOMA — Somatic Wisdom Architecture

<p align="center">
  <strong>Wisdom over Memory — 智慧超越记忆</strong><br>
  <em>AI agents shouldn't just remember. They should <strong>understand</strong>.</em>
</p>

```bash
pip install soma-wisdom     # 5 minutes from zero to thinking agent
```

```python
from soma import SOMA

soma = SOMA()
soma.remember("First-principles thinking: deconstruct to fundamentals...",
              context={"domain": "philosophy"}, importance=0.9)
answer = soma.respond("How to analyze our growth bottleneck?")
# → decomposes through 7 thinking laws → activates relevant memories → returns reasoned answer
```

**Why SOMA instead of a vector database?** Traditional memory (ChromaDB, Mem0) stores and retrieves. SOMA **thinks first**: a 7-law reasoning network decomposes problems *before* fetching memories. The result: agents that systematically analyze, not just pattern-match.

| | Vector DBs | Mem0 | **SOMA** |
|---|---|---|---|
| Stores & retrieves | ✓ | ✓ | ✓ |
| Reasoning framework | ✗ | ✗ | **✓ 7 thinking laws** |
| Self-evolution | ✗ | ✗ | **✓ weights auto-tune** |
| Consolidation + forgetting | ✗ | partial | **✓ Ebbinghaus decay** |
| Causal reasoning | ✗ | ✗ | **✓ graph chain inference** |
| Cross-domain analogy | ✗ | ✗ | **✓ structural pattern matching** |
| Conflict detection | ✗ | ✗ | **✓ contradiction flagging** |
| Multi-agent collaboration | ✗ | ✗ | **✓ expert routing + consensus** |
| Frame anchoring awareness | ✗ | ✗ | **✓ cognitive bias nudge** |
| Offline / zero infra | varies | ✗ (OpenAI) | **✓ ONNX, SQLite** |

<p align="center">
  <a href="https://github.com/sunyan999999/soma"><img src="https://img.shields.io/github/stars/sunyan999999/soma?style=social" alt="GitHub stars"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue" alt="License"></a>
  <a href="#"><img src="https://img.shields.io/badge/version-0.9.1-blue" alt="Version"></a>
  <a href="#"><img src="https://img.shields.io/badge/python-3.10%2B-green" alt="Python"></a>
  <a href="#benchmarks"><img src="https://img.shields.io/badge/semantic_recall-100%25-brightgreen" alt="Semantic Recall"></a>
  <a href="#benchmarks"><img src="https://img.shields.io/badge/overall_score-80.5%2F100-blue" alt="Overall Score"></a>
  <a href="#"><img src="https://img.shields.io/badge/tests-485%2F486-brightgreen" alt="Tests"></a>
  <a href="CHANGELOG.md"><img src="https://img.shields.io/badge/changelog-v0.9.1-success" alt="Changelog"></a>
</p>

📖 **[中文文档](README_zh.md)** | **[Docs](https://sunyan999999.github.io/soma/)** | **[Demo](https://github.com/sunyan999999/soma-demo)** | **[Roadmap](ROADMAP.md)** | **[Changelog](CHANGELOG.md)** | **[Contributing](CONTRIBUTING.md)**

<p align="center">
  <img src="https://raw.githubusercontent.com/sunyan999999/soma/main/docs/images/demo-pipeline.gif" alt="SOMA Pipeline Demo" width="720">
</p>

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         SOMA Agent (v0.9.1)                                    │
│                                                                                │
│  ┌──────────────────────────────────────────────────────────────────┐        │
│  │  v0.9.1 Sunyata Awareness Layer ⚡ — 零熵觉察层                    │        │
│  │  FrameAnchoringDetector · 框架锁定检测 · 觉察提示（脚注式低干扰） │        │
│  └──────────────────────────────────────────────────────────────────┘        │
│                                                                                │
│  ┌──────────────────────────────────────────────────────────────────┐        │
│  │  v0.9.0 Multi-Agent Collaboration ⚡ — 多智能体协作                │        │
│  │  AgentRegistry · ExpertRouter · ConsensusProtocol · DistributedEvolver │   │
│  └──────────────────────────────────────────────────────────────────┘        │
│                                                                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────────────┐    │
│  │ WisdomEngine  │→│ActivationHub │→│           MemoryCore               │    │
│  │ · 关键词匹配  │  │ · 双向激活   │  │ · episodic/semantic/skill         │    │
│  │ · 规律链传播  │  │ · 反视角检索 │  │ · SQLite + vector + FTS5          │    │
│  │ · 组合模板    │  │ · 冲突检测⚡ │  │ · 加权RRF + 时间衰减              │    │
│  │ · 语义兜底    │  │ · 反向传播⚡ │  │ · 图谱扩展检索⚡                  │    │
│  │ · 语境排序    │  │ · MMR重排    │  │ · 跨域类比引擎⚡                  │    │
│  └──────────────┘  └──────────────┘  └──────────────────────────────────┘    │
│         │                  │                        │                        │
│         ▼                  ▼                        ▼                        │
│  ┌──────────────┐  ┌──────────────────────────────────────────────────┐      │
│  │ 复杂度评估    │  │              MetaEvolver                         │      │
│  └──────────────┘  │ · 偏差检测 → 自动调权 → 技能固化                  │      │
│         │          │ · 触发词扩展 · 思维模板挖掘 · 动态步长            │      │
│         ▼          └──────────────────────────────────────────────────┘      │
│  ┌──────────────────────────────────────────────────────────────────┐       │
│  │  v0.6 Reasoning Engine           │  v0.8 Causal + Conflict ⚡     │       │
│  │  · 17 reasoning templates        │  · CausalGraph 因果链推理      │       │
│  │  · Hypothesis + evidence matrix  │  · ConflictDetector 矛盾检测   │       │
│  │  · Auto-extract triples          │  · QualityEvaluator 反思评分   │       │
│  └──────────────────────────────────────────────────────────────────┘       │
└──────────────────────────────────────────────────────────────────────────────┘

Thirteen-Stage Wisdom Pipeline:
  Assess → Decompose → Chain → Combine → Semantic-fallback
         → Context-sort → Activate → Conflict-detect⚡ → Frame-anchoring⚡ → Anti-bias
         → Reason → Synthesize → Causal-extract → Backward-propagate⚡ → Evolve
```

## Screenshots

<p align="center">
  <strong>🧠 Wisdom Chat</strong> &nbsp;·&nbsp; <strong>📊 5D Benchmark</strong> &nbsp;·&nbsp; <strong>💻 IDE Integration</strong> &nbsp;·&nbsp; <strong>🔌 REST API</strong>
</p>

<table>
<tr>
<td width="50%"><a href="https://raw.githubusercontent.com/sunyan999999/soma/main/docs/images/screenshot-chat.jpeg"><img src="https://raw.githubusercontent.com/sunyan999999/soma/main/docs/images/screenshot-chat.jpeg" alt="SOMA ChatView — 智者对话" width="100%"></a></td>
<td width="50%"><a href="https://raw.githubusercontent.com/sunyan999999/soma/main/docs/images/screenshot-benchmark.jpeg"><img src="https://raw.githubusercontent.com/sunyan999999/soma/main/docs/images/screenshot-benchmark.jpeg" alt="SOMA BenchmarkView — 五维基准雷达图" width="100%"></a></td>
</tr>
<tr>
<td align="center"><b>Wisdom Chat</b> — 7条规律分解问题，双向记忆激活，LLM流式响应</td>
<td align="center"><b>5D Benchmark</b> — 记忆/智慧/进化/伸缩/综合，竞品实时对比</td>
</tr>
<tr>
<td width="50%"><a href="https://raw.githubusercontent.com/sunyan999999/soma/main/docs/images/screenshot-ide.jpeg"><img src="https://raw.githubusercontent.com/sunyan999999/soma/main/docs/images/screenshot-ide.jpeg" alt="SOMA IDE Integration — Claude Code 集成" width="100%"></a></td>
<td width="50%"><a href="https://raw.githubusercontent.com/sunyan999999/soma/main/docs/images/screenshot-api.jpeg"><img src="https://raw.githubusercontent.com/sunyan999999/soma/main/docs/images/screenshot-api.jpeg" alt="SOMA REST API — 完整接口文档" width="100%"></a></td>
</tr>
<tr>
<td align="center"><b>IDE Integration</b> — Claude Code / VS Code 一键接入，记忆自动持久化</td>
<td align="center"><b>REST API</b> — FastAPI + SSE 流式，多模型管理，API Key 认证</td>
</tr>
</table>

## Dashboard

Start the API server and open `http://localhost:8765`:

```bash
SOMA_API_KEY=test python dash/server.py
```

Vue 3 dashboard with i18n (English / 中文), 6 views: Chat · Framework · Memory · Analytics · Benchmark · Settings.

## Installation

```bash
pip install soma-wisdom
```

Requires **Python 3.10+**. The embedding engine uses ONNX Runtime for CPU inference — no CUDA, no Docker, no external services.

First run downloads a small ONNX model (~100 MB, Chinese-English bilingual).

```bash
python -m soma          # verify everything works in one command
soma-quickstart         # or use the CLI entry point
```

## Core Concepts

### 1. Wisdom Framework — 7 Thinking Laws

| Law | Description | Weight |
|-----|-------------|:---:|
| `first_principles` | Reduce to fundamentals, derive from base elements | 0.90 |
| `systems_thinking` | See interconnected wholes, identify feedback loops | 0.85 |
| `contradiction_analysis` | Find opposing forces, identify principal contradictions | 0.80 |
| `pareto_principle` | Focus on the vital 20% that drives 80% of outcomes | 0.75 |
| `inversion` | Think backwards — how could this fail? | 0.70 |
| `analogical_reasoning` | Map structures across domains | 0.65 |
| `evolutionary_lens` | Observe change over time, identify lifecycle stages | 0.60 |

Customize in `wisdom_laws.yaml` (bundled in the package — always available).

**New in v0.5**: Laws are no longer a flat list — they form a **reasoning network**. When a law triggers, its `relations` propagate activation to related laws (×0.35–0.50 bonus). When two laws fire together, synthesized perspectives emerge (e.g., "First Principles × Systems Thinking → Root-Cause System Analysis").

### 2. Bidirectional Activation — Hybrid RRF

Memories are matched through **weighted Reciprocal Rank Fusion**:
- Vector semantic similarity (×2 weight) via ONNX embeddings
- Keyword exact match (×1 weight)

Both directions compete and complement, producing true relevance scores.

### 3. Meta-Evolution — Self-Optimization

SOMA tracks success/failure of each thinking law across sessions. Every 5 sessions, `evolve()` automatically:
- **Memory consolidation**: similar memories automatically merged, reducing redundancy
- **Active forgetting**: low-value memories archived with Ebbinghaus decay curves
- **Bias detection**: laws used >40% of the time get penalized (-0.05) to prevent thinking ruts; underused high-success laws get boosted (+0.03)
- **Dynamic step sizing**: adjustment magnitude scales with sample count (0.01 → 0.02 → 0.03)
- **Skill solidification**: successful (law, domain, outcome) patterns become permanent skills after 3+ occurrences

### 4. Memory Types

| Type | Storage | Search |
|------|---------|--------|
| **Episodic** | SQLite + vector BLOB | Hybrid (semantic + keyword RRF) |
| **Semantic** | SQLite triple store | Keyword + graph traversal |
| **Skill** | SQLite pattern store | Keyword + domain matching |

### 5. v0.8.0 — Knowledge Graph & Reasoning Engine

Six new capabilities that upgrade SOMA from a memory store to a reasoning system:

**Graph Retrieval Expansion** — Keywords are no longer isolated. `_expand_via_semantic_graph()` traverses the knowledge graph (BFS depth=2) to discover neighbor concepts, breaking retrieval silos. O(1) hash lookup replaces full node scan.

**Causal Reasoning** — `CausalGraph` builds causal chains from semantic triples. `causal_analyze()` traces root causes and downstream effects, answering "why" questions with graph-backed evidence chains.

**Conflict Detection** — `ConflictDetector` identifies logically contradictory memories (e.g., "price drop → churn" vs "service quality → churn"). Conflicts are flagged with similarity-weighted scores and penalized in activation ranking. Batch ONNX encoding ensures sub-100ms detection.

**Bidirectional Activation v2** — High-activation memories now propagate backward to suggest new thinking foci (`_backward_propagate()`). The memory→focus feedback loop discovers perspectives the initial decomposition missed.

**Cross-Domain Analogy Engine** — `AnalogyEngine` maps structural patterns across domains. When two unrelated domains share identical graph topology (e.g., "supply chain bottleneck" ≈ "blood vessel blockage"), SOMA bridges them automatically. Structural signature caching avoids repeated graph scans.

**Quality Evaluation** — `QualityEvaluator` scores reasoning output on consistency (answer vs memory alignment), coherence (structure and logic), and actionability (concrete steps). Low-quality answers are flagged with `needs_reflection` for downstream handling.

> **Performance**: v0.8.0 query latency 209ms (v0.7.0: 33ms baseline, 1098ms pre-optimization). The 6x increase over v0.7.0 buys graph expansion + causal chains + conflict detection + cross-domain analogy — all in a single query path. For raw speed, use `query_memory()` which skips framework overhead.

### 6. v0.9.0 — Multi-Agent Collaboration

Four new modules that upgrade SOMA from a single thinking agent to a collaborative team:

**Agent Registry** — `AgentRegistry` formalizes agent expertise. Each agent registers with domain tags (e.g., "法律/合同/诉讼"), and `find_experts()` matches queries to specialists via exact (1.0) or fuzzy (0.7) tag matching. Zero external dependencies — pure in-memory dict + dataclass.

**Expert Router** — `ExpertRouter` uses a 3-tier routing strategy: L1 keyword match (8 domains × 80+ keywords, sub-ms), L2 semantic match (cosine similarity via ONNX), L3 default fallback. Zero LLM calls in routing decisions. Supports single-expert and multi-expert routing.

**Consensus Protocol** — `ConsensusProtocol` synthesizes multiple expert opinions through 3 strategies: L1 weighted voting (success-rate weighted), L2 LLM arbitration (for high-stakes decisions), L3 dialectic synthesis (thesis + antithesis → synthesis). Works without LLM in pure-rule mode.

**Distributed Evolution** — `DistributedEvolver` lets each agent evolve independently while periodically merging global weights (sample-count-weighted average). Conflict arbitration kicks in when weight divergence exceeds 0.2, preserving individual specialization while sharing collective experience.

**Memory Isolation** — Three-state memory isolation via `agent_id` + `group_id`: private (agent_id=self), group-shared (shared_group_id), and global (agent_id=""). All retrieval paths transparently respect isolation boundaries.

### 7. v0.9.1 — Sunyata Awareness Layer

A new dimension: **awareness**. SOMA now detects when you're over-anchored to a single cognitive frame and gently nudges — without blocking, forcing, or changing the pipeline.

**Frame Anchoring Detector** — `FrameAnchoringDetector` with 8 cognitive frame pairs (技术/商业/管理/法律/短期/长期/内求/外求). Pure keyword matching — zero LLM/embedder dependency. Detects when ≥60% of recent 5 turns fall into the same frame, then suggests neglected opposite frames as a blockquote footnote at the prompt's end.

**Backward Compatible by Design** — All new features controlled by `enable_frame_detection: bool = False`. Existing code upgrades with zero changes. The awareness nudge uses low-interference blockquote formatting at the prompt's end — it won't dominate the reasoning flow.

```python
soma = SOMA()
soma._agent.config.enable_frame_detection = True  # opt-in
# SOMA now notices when you're stuck in one perspective
# and adds a gentle footnote: "您已连续5轮从「技术视角」分析..."
```

## API Reference

### SOMA Facade (Python SDK)

```python
from soma import SOMA

soma = SOMA(
    framework_config=None,        # default: bundled wisdom_laws.yaml
    llm="deepseek-chat",          # LiteLLM model string
    use_vector_search=True,       # ONNX semantic search
    persist_dir="soma_data",      # persistence directory
    recall_threshold=0.01,        # minimum activation score
    top_k=5,                      # default recall count
    agent_id="",                  # v0.9.0: agent identity for multi-agent
    group_id="",                  # v0.9.0: group for shared memory
)

# Wisdom pipeline
soma.respond(problem: str) -> str
soma.chat(problem: str) -> dict          # structured: foci + memories + weights

# Memory operations
soma.remember(content, context, importance) -> str  # returns memory_id
soma.remember_semantic(subject, predicate, object_, confidence)
soma.query_memory(query: str, top_k: int) -> list

# Introspection & evolution
soma.decompose(problem: str) -> list     # show thinking dimensions
soma.reflect(task_id, outcome) -> None   # record outcome for evolution
soma.evolve() -> list                    # trigger automatic weight adjustment
soma.get_weights() -> dict               # current law weights
soma.adjust_weight(law_id, new_weight)   # manual override
soma.discover_laws() -> dict | None      # autonomous law discovery
soma.approve_law(candidate) -> bool      # approve a discovered law
soma.stats -> dict                       # memory store statistics

# v0.9.1: opt-in frame anchoring awareness
# soma._agent.config.enable_frame_detection = True
```

### REST API (Language-Agnostic)

```bash
# Start server
SOMA_API_KEY=your-key python dash/server.py    # → http://localhost:8765

# Standard chat
curl -X POST http://localhost:8765/api/chat \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"problem": "How to improve team productivity?"}'

# SSE streaming (decompose → activate → delta → done)
curl -X POST http://localhost:8765/api/chat/stream \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"problem": "Analyze our growth bottleneck"}'

# Memory search
curl -X POST http://localhost:8765/api/memory/search \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"query": "growth strategy", "top_k": 10}'
```

Set `SOMA_API_KEY` env var to enable authentication. Leave unset for local development.

### LangChain Tool

```python
from soma.langchain_tool import create_soma_tool
from soma.agent import SOMA_Agent
from soma.config import SOMAConfig, load_config

agent = SOMA_Agent(SOMAConfig(framework=load_config()))
tool = create_soma_tool(agent)
result = tool.run("Analyze this problem...")
```

### AI Coding Agent Integration (Claude Code / VS Code / JetBrains)

SOMA runs alongside AI coding tools as a persistent wisdom backend — it learns from every debug session, code review, and architectural decision.

```bash
# 1. Start SOMA server (once)
SOMA_API_KEY=dev-key python dash/server.py
```

**Claude Code (Agent SDK)** — use as a custom MCP server or REST tool:

```python
# In your custom Claude Agent tool — persist insights across sessions
import requests
requests.post("http://localhost:8765/api/memory/remember",
    headers={"X-API-Key": "dev-key"},
    json={"content": "Bug: N+1 query in OrderService.getOrders, root cause: missing @BatchSize on items relation, fix: add Hibernate batch annotation + integration test", "importance": 0.9})
```

**VS Code Extension** — invoke via sidebar or command palette with a thin HTTP client wrapper.

**Any IDE / CLI tool** — just curl the REST API. No SDK required.

```bash
# Record a debug finding
curl -s -X POST http://localhost:8765/api/memory/remember \
  -H "X-API-Key: dev-key" -H "Content-Type: application/json" \
  -d '{"content":"Race condition in WebSocket handler: concurrent map writes on client.buf, root cause: missing mutex on write path, fix: sync.RWMutex around buffer ops","importance":0.9}'

# Recall relevant knowledge before starting a new task
curl -s -X POST http://localhost:8765/api/memory/search \
  -H "X-API-Key: dev-key" -H "Content-Type: application/json" \
  -d '{"query":"concurrency websocket golang","top_k":5}'
```

### Real-World Impact

SOMA has been used in production across two distinct codebases — a Go-based CLI agent and a Python data platform — with the following results:

- **Bug reoccurrence dropped significantly.** When a bug fix is recorded as a SOMA memory (root cause + fix pattern), later sessions on the same codebase automatically retrieve it. Developers no longer re-debug the same class of issues across sprints.
- **Architectural decisions became searchable.** Each trade-off ("chose SQLite WAL over multi-worker for simplicity") is persisted with rationale context. Six months later, new team members can query "why single worker?" and get the original reasoning — not folklore.
- **Cross-project knowledge transfer worked.** A concurrency pattern learned in one codebase (the Go project) activated during debugging in the other (the Python project), because SOMA's semantic search matched "race condition" across language boundaries.
- **Zero adoption friction.** The Python project integrated via `pip install soma-wisdom` + 3 lines of code. The Go project integrated via REST API with a thin HTTP client (~50 lines). Neither required schema design, vector database setup, or infrastructure changes.
- **Evolution is automatic.** After ~50 sessions, SOMA's auto-weighting surfaced that "Inversion" (thinking backwards from failure) was consistently the most useful lens for debugging tasks, while "Analogical Reasoning" shined during architecture discussions. The framework self-tuned — no manual knob-twisting needed.

## Benchmarks

SOMA v0.9.1 — benchmarked with production memories from 零熵智库:

### Overall Score: 80.5/100

| Dimension | Score | Grade |
|-----------|:---:|:---:|
| **Overall** | **80.5** | Excellent |
| **Memory** | **88.4** | Excellent — 100% recall, 209ms query (graph+conflict+causal) |
| **Wisdom** | **85.5** | Excellent — causal analysis + cross-domain analogy active |
| **Evolution** | **68.7** | Good — 1,000+ reflections, weight auto-adaptation |
| **Scalability** | **100.0** | Excellent — linear scaling at 1K |

> Score change from v0.7.0 (84.8→80.5): v0.8.0 adds causal reasoning, conflict detection, and analogy to the scoring rubric. Memory dimension reflects new graph-expanded search overhead (209ms vs 3.74ms in v0.7.0 bare keyword path).

### Key Metrics

| Metric | Value | Stability |
|--------|:----:|:---:|
| Semantic Recall Rate | 100% | ● Stable |
| Dedup Ratio | 100% | ● Stable |
| Avg Insert Latency | 3.44ms | ◐ Acceptable |
| Query Latency (framework) | 209ms | ● Stable |
| Query Latency (simple) | ~30ms | ● Stable |
| Causal Chain Accuracy | 100% | ● Stable |
| Conflict Detection | <100ms (batch) | ● Stable |
| Decomposition Coverage | 100% | ● Stable |
| Thinking Diversity Entropy | 0.87 | ● Stable |

### Live Competitor Comparison

| System | Recall@5 | Reasoning | Evolution | Causal | Analogy | Conflict |
|--------|:---:|:---:|:---:|:---:|:---:|:---:|
| **SOMA v0.8** | **100%** | **✓** | **✓** | **✓** | **✓** | **✓** |
| ChromaDB | 2.5% | ✗ | ✗ | ✗ | ✗ | ✗ |
| Mem0 | * | ✗ | ✗ | ✗ | ✗ | ✗ |
| Zep | * | ✗ | ✗ | ✗ | ✗ | ✗ |

> SOMA is the only system combining a reasoning framework, causal analysis, conflict detection, cross-domain analogy, evolutionary self-optimization, memory consolidation, and active forgetting — all without external services.

Full report: [CHANGELOG.md](CHANGELOG.md)

### Reproducibility

```bash
pip install soma-wisdom chromadb
python -m soma.benchmarks --full --runs 5 --output reports/    # statistical benchmark
python scripts/live_benchmark.py --full --output reports/       # live competitor test
```

## Development

```bash
git clone https://github.com/soma-project/soma-core.git
cd soma-core
pip install -e ".[dev]"

pytest -v --cov=soma --cov-report=term    # 485+ tests, ~97% coverage

python -m soma                              # quickstart verification

python dash/server.py                       # API server (http://localhost:8765)
```

### Project Structure

```
soma-core/
├── soma/                  # Core library
│   ├── __init__.py        # SOMA facade (zero-config entry)
│   ├── __main__.py        # python -m soma quickstart
│   ├── agent.py           # SOMA_Agent: pipeline orchestrator + awareness ⚡
│   ├── engine.py          # WisdomEngine: problem decomposition
│   ├── hub.py             # ActivationHub: bidirectional activation
│   ├── evolve.py          # MetaEvolver: reflection + auto-evolution
│   ├── embedder.py        # SOMAEmbedder: fastembed + ONNX encoding
│   ├── vector_store.py    # NumpyVectorIndex: faiss ANN search
│   ├── config.py          # Pydantic configuration models + frame detection ⚡
│   ├── base.py            # Data models (Focus, MemoryUnit, etc.)
│   ├── abc.py             # Abstract base classes
│   ├── langchain_tool.py  # LangChain BaseTool wrapper
│   ├── law_discovery.py   # Autonomous law discovery from clusters
│   ├── retry.py           # LLM retry with exponential backoff
│   ├── plugin.py          # Entry-points plugin auto-discovery
│   ├── quality.py         # QualityEvaluator: reasoning output scoring ⚡
│   ├── analogy.py         # AnalogyEngine: cross-domain structural matching ⚡
│   ├── competitors.py     # Live competitor benchmark adapters
│   ├── analytics.py       # Usage analytics & benchmark storage
│   ├── benchmarks.py      # 5D benchmark engine (memory/wisdom/evolution/scalability/overall)
│   ├── wisdom_laws.yaml   # Default thinking framework (bundled)
│   ├── hub/
│   │   ├── _core.py       # ActivationHub: bidirectional activation + frame detection ⚡
│   │   ├── _conflict.py   # ConflictDetector: contradiction detection ⚡
│   │   ├── _frame_detector.py  # FrameAnchoringDetector: cognitive bias nudge ⚡
│   │   ├── _retriever.py  # MemoryRetriever: multi-path recall
│   │   ├── _scorer.py     # RelevanceScorer: weighted scoring
│   │   └── _ranker.py     # MMRRanker: diversity re-ranking
│   ├── multi_agent/       # v0.9.0 Multi-Agent Collaboration ⚡
│   │   ├── registry.py    # AgentRegistry: expert registration + matching
│   │   ├── router.py      # ExpertRouter: 3-tier routing (keyword/semantic/fallback)
│   │   ├── consensus.py   # ConsensusProtocol: vote/LLM/dialectic synthesis
│   │   └── evolve.py      # DistributedEvolver: independent evolution + weight merge
│   └── memory/
│       ├── core.py        # MemoryCore: unified memory facade + 3-state isolation ⚡
│       ├── episodic.py    # EpisodicStore: SQLite + vector BLOB
│       ├── semantic.py    # SemanticStore: knowledge triples + causal graph ⚡
│       ├── skill.py       # SkillStore: learned patterns
│       ├── causal.py      # CausalGraph: causal chain reasoning ⚡
│       ├── consolidation.py  # ConsolidationEngine: memory dedup
│       ├── forgetting.py     # ForgettingEngine: Ebbinghaus decay
│       ├── external.py       # External knowledge import (Markdown/JSON/URL)
│       └── search_utils.py   # FTS5 shared search utilities
├── dash/                  # Dashboard & API server
│   ├── server.py          # FastAPI (REST + SSE streaming + auth, version auto-detect ⚡)
│   ├── providers.py       # LLM provider manager
│   └── frontend/          # Vue 3 dashboard UI (i18n: EN/ZH)
├── docs/                  # Documentation (EN + ZH bilingual)
│   ├── contribution-audit-standards.md  # Law contribution audit standards (D4) ⚡
│   ├── v0.9.0-capabilities.md           # v0.9.0 capability overview
│   └── v0.9.1-零熵整合方案.md            # v0.9.1 integration plan
├── tests/                 # 485+ tests, ~97% coverage
├── examples/              # Usage examples
└── pyproject.toml         # Build config (version auto-detect)
```

## Citation

```bibtex
@software{soma2025,
  title        = {SOMA: Somatic Wisdom Architecture},
  author       = {SOMA Project Team},
  year         = {2025},
  url          = {https://github.com/soma-project/soma-core},
  note         = {Apache 2.0},
}
```

## License

Apache License 2.0. See [LICENSE](LICENSE).

---

<p align="center">
  <sub>🧠 五分钟接入，给你的 Agent 一个会思考的灵魂</sub>
</p>
