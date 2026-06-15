# SOMA v1.1.6 — The Cognitive Kernel for AI Agents

<p align="center">
  <strong>Wisdom over Memory — 智慧超越记忆</strong><br>
  <em>Five capability lines. Seven thinking laws. One cognitive kernel that remembers, reasons, collaborates, and evolves.</em>
</p>

```bash
pip install soma-wisdom     # 5 minutes from zero to thinking agent
```

<p align="center">
  <a href="https://codespaces.new/sunyan999999/soma">
    <img src="https://github.com/codespaces/badge.svg" alt="Open in GitHub Codespaces" height="40">
  </a>
  <br><strong>👆 点击即可在浏览器中体验 SOMA 面板 — 无需安装，一分钟启动</strong>
</p>

```python
from soma import SOMA

soma = SOMA()
soma.remember("First-principles thinking: deconstruct to fundamentals...",
              context={"domain": "philosophy"}, importance=0.9)
answer = soma.respond("How to analyze our growth bottleneck?")
# → decomposes through 7 thinking laws → activates relevant memories → returns reasoned answer
```

**Why SOMA instead of a vector database?** Traditional memory (ChromaDB, Mem0) stores and retrieves. SOMA **thinks first**: a 7-law reasoning network decomposes problems *before* fetching memories. The result: agents that systematically analyze, not just pattern-match.

| | Vector DBs | Mem0 | **SOMA v1.1.6** |
|---|---|---|---|
| Stores & retrieves | ✓ | ✓ | ✓ |
| Reasoning framework | ✗ | ✗ | **✓ 7 thinking laws** |
| Self-evolution | ✗ | ✗ | **✓ weights auto-tune** |
| Three-tier memory (L1/L2/L3) | ✗ | ✗ | **✓ fragment→scene→profile** |
| Consolidation + forgetting | ✗ | partial | **✓ Ebbinghaus decay** |
| Causal reasoning | ✗ | ✗ | **✓ graph chain inference** |
| Cross-domain analogy | ✗ | ✗ | **✓ structural pattern matching** |
| Conflict detection | ✗ | ✗ | **✓ contradiction flagging** |
| Multi-agent collaboration | ✗ | ✗ | **✓ expert routing + consensus** |
| Frame anchoring awareness | ✗ | ✗ | **✓ cognitive bias nudge** |
| Real-time bias correction | ✗ | ✗ | **✓ Zhongdao Engine (NEW)** |
| Offline / zero infra | varies | ✗ (OpenAI) | **✓ ONNX, SQLite** |

<p align="center">
  <a href="https://github.com/sunyan999999/soma"><img src="https://img.shields.io/github/stars/sunyan999999/soma?style=social" alt="GitHub stars"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue" alt="License"></a>
  <a href="#"><img src="https://img.shields.io/badge/version-1.1.6-blue" alt="Version"></a>
  <a href="#"><img src="https://img.shields.io/badge/python-3.10%2B-green" alt="Python"></a>
  <a href="#benchmarks"><img src="https://img.shields.io/badge/semantic_recall-100%25-brightgreen" alt="Semantic Recall"></a>
  <a href="#benchmarks"><img src="https://img.shields.io/badge/overall_score-85.5%2F100-blue" alt="Overall Score"></a>
  <a href="#"><img src="https://img.shields.io/badge/tests-639%2F639-brightgreen" alt="Tests"></a>
  <a href="CHANGELOG.md"><img src="https://img.shields.io/badge/changelog-v1.1.6-success" alt="Changelog"></a>
  <a href="#"><img src="https://img.shields.io/badge/milestone-1.1.6-ff6b6b" alt="Milestone"></a>
</p>

📖 **[中文文档](README_zh.md)** | **[Docs](https://sunyan999999.github.io/soma/)** | **[Demo](https://github.com/sunyan999999/soma-demo)** | **[Roadmap](ROADMAP.md)** | **[Changelog](CHANGELOG.md)** | **[Contributing](CONTRIBUTING.md)**

<p align="center">
  <img src="https://raw.githubusercontent.com/sunyan999999/soma/main/docs/images/demo-pipeline.gif" alt="SOMA Pipeline Demo" width="720">
</p>

---

## v1.1.6 — Zhongdao Closed Loop

**v1.1.6 closes the Zhongdao feedback loop** — from correction to verification to optimization:

| # | Feature | Description |
|---|---------|-------------|
| B1 | Correction effectiveness tracking | Daily trend charts + per-law correction frequency in Dash |
| B2 | Auto-tuning suggestions | ML-driven parameter recommendations based on historical data |
| B3 | Dash trend visualization | Bar charts + frequency panels + suggestion cards + time range selector |
| B4 | Auto-archiving | 90-day old corrections auto-archived to prevent DB bloat |
| B5 | Production refinements | Mobile optimization + i18n completion + cooldown protection |

**Benchmark validated** on 零熵智库 (v1.1.6): Overall 80.5 (+5.8 vs v1.1.2), Memory 79.7 (+20.2), Wisdom 76.2, Evolution 75.0, Scalability 100.0. 650 tests passed.

Every capability line that started as a seed in v0.1 has grown into a complete system:

| Capability Line | Core Question | v1.1.6 Answer |
|---|---|---|
| **Memory** | How can AI manage memory like humans do? | Three-tier: fragments → scenes → profile |
| **Reasoning** | How to use information to think? | Causal chains + conflict detection + cross-domain analogy |
| **Collaboration** | How do multiple AIs work as a team? | Expert routing + consensus protocols + distributed evolution |
| **Evolution** | Can AI learn from its own experience? | Reflect → re-weight → solidify → share (3-layer correction) |
| **Engineering** | How to prove these capabilities are real? | 639 tests + 5D benchmarks + competitor comparison |

**All new features default to off. Upgrade from any 0.x version with zero code changes.**

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         SOMA v1.1.6 — Cognitive Kernel                           │
│                                                                                │
│  ┌──────────────────────────────────────────────────────────────────┐        │
│  │  L3 User Profile — "Knows who you are"                             │        │
│  │  Auto-extracted traits: preferences, skills, knowledge gaps, goals │        │
│  └──────────────────────────────────────────────────────────────────┘        │
│                                    ↑                                          │
│  ┌──────────────────────────────────────────────────────────────────┐        │
│  │  L2 Scene Blocks — "Understands your context"                      │        │
│  │  Auto-aggregated work contexts ("building a Python data platform") │        │
│  └──────────────────────────────────────────────────────────────────┘        │
│                                    ↑                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────────────┐    │
│  │ WisdomEngine  │→│ActivationHub │→│  L1 Episodic Memory (the original) │    │
│  │ · 7 thinking  │  │ · bidirectional│ · SQLite + vector + FTS5           │    │
│  │   laws        │  │   activation  │ · weighted RRF + time decay         │    │
│  │ · law chaining│  │ · conflict    │ · knowledge graph + causal chains   │    │
│  │ · combo synth │  │   detection   │ · cross-domain analogy engine       │    │
│  │ · complexity  │  │ · MMR re-rank │                                      │    │
│  │   assessment  │  │ · frame nudge │                                      │    │
│  └──────────────┘  └──────────────┘  └──────────────────────────────────┘    │
│         │                  │                        │                        │
│         ▼                  ▼                        ▼                        │
│  ┌──────────────────────────────────────────────────────────────────┐       │
│  │  Multi-Agent Layer          │  Evolution Loop                     │       │
│  │  · AgentRegistry            │  · MetaEvolver: bias detect →       │       │
│  │  · ExpertRouter (3-tier)    │    re-weight → solidify → share     │       │
│  │  · ConsensusProtocol        │  · CapturePipeline: auto L2+L3      │       │
│  │  · DistributedEvolver       │  · FrameAnchoringDetector           │       │
│  └──────────────────────────────────────────────────────────────────┘       │
└──────────────────────────────────────────────────────────────────────────────┘

Fifteen-Stage Wisdom Pipeline:
  Assess → Decompose → Chain → Combine → Semantic-fallback
         → Context-sort → Activate → Conflict-detect → Frame-nudge → Anti-bias
         → Reason → Synthesize → Causal-extract → Backward-propagate → Evolve
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
<td align="center"><b>Wisdom Chat</b> — 7 thinking laws decompose problems, bidirectional memory activation, LLM streaming</td>
<td align="center"><b>5D Benchmark</b> — Memory/Wisdom/Evolution/Scalability/Overall, live competitor comparison</td>
</tr>
<tr>
<td width="50%"><a href="https://raw.githubusercontent.com/sunyan999999/soma/main/docs/images/screenshot-ide.jpeg"><img src="https://raw.githubusercontent.com/sunyan999999/soma/main/docs/images/screenshot-ide.jpeg" alt="SOMA IDE Integration — Claude Code 集成" width="100%"></a></td>
<td width="50%"><a href="https://raw.githubusercontent.com/sunyan999999/soma/main/docs/images/screenshot-api.jpeg"><img src="https://raw.githubusercontent.com/sunyan999999/soma/main/docs/images/screenshot-api.jpeg" alt="SOMA REST API — 完整接口文档" width="100%"></a></td>
</tr>
<tr>
<td align="center"><b>IDE Integration</b> — Claude Code / VS Code one-click access, auto-persistent memory</td>
<td align="center"><b>REST API</b> — FastAPI + SSE streaming, multi-model management, API Key auth</td>
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

**Thinking laws form a reasoning network.** When a law triggers, its `relations` propagate activation to related laws (×0.35–0.50 bonus). When two laws fire together, synthesized perspectives emerge (e.g., "First Principles × Systems Thinking → Root-Cause System Analysis"). Weights auto-tune based on actual success/failure — a startup team and a large enterprise will naturally evolve different weight distributions.

### 2. Three-Tier Memory System

v1.0 introduces automatic memory layering — the system quietly builds understanding while you work:

| Tier | What | Example |
|------|------|---------|
| **L1 Episodic** | Individual memory fragments | "Fixed N+1 query bug in OrderService" |
| **L2 Scene** | Auto-aggregated work contexts | "Working on a Python data analysis project" |
| **L3 Profile** | Extracted user traits | "Prefers functional programming, strong at debugging, learning systems design" |

The entire process is automatic. You use SOMA normally; behind the scenes, `CapturePipeline` aggregates fragments into scenes and distills scenes into your profile.

### 3. Bidirectional Activation — Hybrid RRF

Memories are matched through **weighted Reciprocal Rank Fusion**:
- Vector semantic similarity (×2 weight) via ONNX embeddings
- Keyword exact match (×1 weight)
- Knowledge graph expansion (×0.5 weight)

All three paths compete and complement, producing scores that reflect true relevance — not just keyword overlap.

### 4. Meta-Evolution — Self-Optimization

SOMA tracks success/failure of each thinking law across sessions. Every 5 sessions, `evolve()` automatically:
- **Memory consolidation**: similar memories auto-merged, reducing redundancy
- **Active forgetting**: low-value memories archived with Ebbinghaus decay curves
- **Bias detection**: laws used >40% of the time get penalized (-0.05) to prevent thinking ruts; underused high-success laws get boosted (+0.03)
- **Dynamic step sizing**: adjustment magnitude scales with sample count (0.01 → 0.02 → 0.03)
- **Skill solidification**: successful (law, domain, outcome) patterns become permanent skills after 3+ occurrences

### 5. Knowledge Graph & Reasoning Engine

Six cognitive capabilities that upgrade SOMA from a memory store to a reasoning system:

- **Causal Chain Tracing**: Follow the causal graph to root causes — "why did user churn rise?" → traces back to "an API change three months ago slowed response times"
- **Conflict Detection**: When memories contain contradictory claims, flag and down-weight automatically, preventing the LLM from being misled
- **Cross-Domain Analogy**: Map structural patterns across domains — e.g., "supply chain bottleneck" ≈ "blood vessel blockage"
- **Quality Evaluation**: Self-score each reasoning output on consistency, coherence, and actionability. Below-threshold outputs trigger reflective improvement
- **Graph Retrieval Expansion**: Keywords are no longer isolated — BFS traversal (depth=2) discovers neighbor concepts, breaking retrieval silos
- **Backward Propagation**: High-activation memories suggest new thinking foci — the memory→focus feedback loop discovers perspectives the initial decomposition missed

### 6. Multi-Agent Collaboration

Multiple SOMA agents work as a team:

- **Expert Specialization**: Each agent has independent memory, independent evolution path, and domain expertise
- **Automatic Routing**: Problems dispatched to the most suitable expert via keyword + semantic matching — zero LLM involvement, completed in milliseconds
- **Consensus Protocols**: When experts disagree — L1 weighted voting → L2 LLM arbitration → L3 dialectic synthesis
- **Distributed Evolution**: Each expert evolves independently while periodically merging global experience
- **Memory Isolation**: Three-state isolation via `agent_id` + `group_id` — private, group-shared, and global

### 7. Sunyata Awareness Layer

SOMA detects when you're over-anchored to a single cognitive frame and gently nudges — without blocking, forcing, or changing the pipeline.

- **8 cognitive frame pairs**: Technical/Business, Management/Legal, Short-term/Long-term, Internal/External
- **Pure keyword matching**: Zero LLM/embedder dependency
- **Low-interference**: Blockquote footnote at prompt end — won't dominate the reasoning flow
- **Default off**: `enable_frame_detection=False`, 100% backward compatible

```python
soma = SOMA()
soma._agent.config.enable_frame_detection = True  # opt-in
# SOMA now notices when you're stuck in one perspective
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
    agent_id="",                  # v1.0: agent identity for multi-agent
    group_id="",                  # v1.0: group for shared memory
)

# Wisdom pipeline
soma.respond(problem: str) -> str
soma.chat(problem: str) -> dict          # structured: foci + memories + weights

# Memory operations
soma.remember(content, context, importance) -> str  # returns memory_id
soma.remember_semantic(subject, predicate, object_, confidence)
soma.query_memory(query: str, top_k: int) -> list

# v1.0: Three-tier memory
soma.get_scenes(user_id="", top_k=10) -> list
soma.get_profile(user_id="") -> list
soma.capture_scenes(user_id="", force=False) -> int
soma.update_profile(user_id="", force=False) -> int

# Introspection & evolution
soma.decompose(problem: str) -> list     # show thinking dimensions
soma.reflect(task_id, outcome) -> None   # record outcome for evolution
soma.evolve() -> list                    # trigger automatic weight adjustment
soma.get_weights() -> dict               # current law weights
soma.adjust_weight(law_id, new_weight)   # manual override
soma.discover_laws() -> dict | None      # autonomous law discovery
soma.approve_law(candidate) -> bool      # approve a discovered law
soma.stats -> dict                       # memory store statistics
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

SOMA v1.0 — benchmarked with 1,050 production memories from 零熵智库 (5 runs, statistical output):

### Overall Score: 85.5/100

| Dimension | Score | Grade |
|-----------|:---:|:---:|
| **Overall** | **85.5** | Excellent |
| **Memory** | **97.6** | Excellent — 100% recall, three-tier memory active |
| **Wisdom** | **87.3** | Excellent — causal analysis + cross-domain analogy + conflict detection |
| **Evolution** | **60.2** | Good — weight auto-adaptation, reflection loop running |
| **Scalability** | **100.0** | Excellent — linear scaling verified at 1K |

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

| System | Recall@5 | Reasoning | Three-Tier Memory | Evolution | Multi-Agent | Awareness |
|--------|:---:|:---:|:---:|:---:|:---:|:---:|
| **SOMA v1.1.6** | **100%** | **✓** | **✓** | **✓** | **✓** | **✓** |
| ChromaDB | 2.5% | ✗ | ✗ | ✗ | ✗ | ✗ |
| Mem0 | * | ✗ | ✗ | ✗ | ✗ | ✗ |
| Zep | * | ✗ | ✗ | ✗ | ✗ | ✗ |

> SOMA is the only system combining a reasoning framework, three-tier memory, causal analysis, conflict detection, cross-domain analogy, evolutionary self-optimization, multi-agent collaboration, and frame anchoring awareness — all without external services.

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

pytest -v --cov=soma --cov-report=term    # 639 tests, ~97% coverage

python -m soma                              # quickstart verification

python dash/server.py                       # API server (http://localhost:8765)
```

### Project Structure

```
soma-core/
├── soma/                  # Core library
│   ├── __init__.py        # SOMA facade (zero-config entry)
│   ├── __main__.py        # python -m soma quickstart
│   ├── agent.py           # SOMA_Agent: pipeline orchestrator + awareness
│   ├── engine.py          # WisdomEngine: problem decomposition
│   ├── hub.py             # ActivationHub: bidirectional activation
│   ├── evolve.py          # MetaEvolver: reflection + auto-evolution
│   ├── embedder.py        # SOMAEmbedder: fastembed + ONNX encoding
│   ├── vector_store.py    # NumpyVectorIndex: faiss ANN search
│   ├── config.py          # Pydantic configuration models
│   ├── base.py            # Data models (Focus, MemoryUnit, etc.)
│   ├── abc.py             # Abstract base classes
│   ├── langchain_tool.py  # LangChain BaseTool wrapper
│   ├── law_discovery.py   # Autonomous law discovery from clusters
│   ├── retry.py           # LLM retry with exponential backoff
│   ├── plugin.py          # Entry-points plugin auto-discovery
│   ├── quality.py         # QualityEvaluator: reasoning output scoring
│   ├── analogy.py         # AnalogyEngine: cross-domain structural matching
│   ├── competitors.py     # Live competitor benchmark adapters
│   ├── analytics.py       # Usage analytics & benchmark storage
│   ├── benchmarks.py      # 5D benchmark engine
│   ├── wisdom_laws.yaml   # Default thinking framework (bundled)
│   ├── hub/
│   │   ├── _core.py       # ActivationHub: bidirectional activation + frame detection
│   │   ├── _conflict.py   # ConflictDetector: contradiction detection
│   │   ├── _frame_detector.py  # FrameAnchoringDetector: cognitive bias nudge
│   │   ├── _retriever.py  # MemoryRetriever: multi-path recall
│   │   ├── _scorer.py     # RelevanceScorer: weighted scoring
│   │   └── _ranker.py     # MMRRanker: diversity re-ranking
│   ├── multi_agent/       # Multi-Agent Collaboration
│   │   ├── registry.py    # AgentRegistry: expert registration + matching
│   │   ├── router.py      # ExpertRouter: 3-tier routing
│   │   ├── consensus.py   # ConsensusProtocol: vote/LLM/dialectic synthesis
│   │   └── evolve.py      # DistributedEvolver: independent evolution + weight merge
│   └── memory/
│       ├── core.py        # MemoryCore: unified memory facade + 3-state isolation
│       ├── episodic.py    # EpisodicStore: L1 episodic memory
│       ├── semantic.py    # SemanticStore: knowledge triples + causal graph
│       ├── skill.py       # SkillStore: learned patterns
│       ├── scene.py       # SceneStore: L2 scene blocks
│       ├── profile.py     # ProfileStore: L3 user profile
│       ├── capture.py     # CapturePipeline: auto L2+L3 extraction
│       ├── causal.py      # CausalGraph: causal chain reasoning
│       ├── consolidation.py  # ConsolidationEngine: memory dedup
│       ├── forgetting.py     # ForgettingEngine: Ebbinghaus decay
│       ├── external.py       # External knowledge import
│       └── search_utils.py   # FTS5 shared search utilities
├── dash/                  # Dashboard & API server
│   ├── server.py          # FastAPI (REST + SSE streaming + auth)
│   ├── providers.py       # LLM provider manager
│   └── frontend/          # Vue 3 dashboard UI (i18n: EN/ZH)
├── docs/                  # Documentation (EN + ZH bilingual)
├── tests/                 # 639 tests, ~97% coverage
├── examples/              # Usage examples
└── pyproject.toml         # Build config
```

## Citation

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

## License

Apache License 2.0. See [LICENSE](LICENSE).

---

<p align="center">
  <sub>🧠 Five minutes to integrate. A cognitive kernel that remembers, reasons, collaborates, and evolves.</sub>
</p>
