# SOMA — Somatic Wisdom Architecture

<p align="center">
  <strong>Wisdom over Memory — 智慧超越记忆</strong><br>
  <em>Framework-First Cognitive Architecture for AI Agents</em>
</p>

<p align="center">
  <a href="https://github.com/sunyan999999/soma"><img src="https://img.shields.io/github/stars/sunyan999999/soma?style=social" alt="GitHub stars"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue" alt="License"></a>
  <a href="#"><img src="https://img.shields.io/badge/version-0.7.0-blue" alt="Version"></a>
  <a href="#"><img src="https://img.shields.io/badge/python-3.10%2B-green" alt="Python"></a>
  <a href="#benchmarks"><img src="https://img.shields.io/badge/semantic_recall-100%25-brightgreen" alt="Semantic Recall"></a>
  <a href="#benchmarks"><img src="https://img.shields.io/badge/overall_score-84.8%2F100-blue" alt="Overall Score"></a>
  <a href="#"><img src="https://img.shields.io/badge/tests-342%2F342-brightgreen" alt="Tests"></a>
  <a href="TEST_REPORT_v0.7.0_FINAL.md"><img src="https://img.shields.io/badge/test_report-v0.7.0-success" alt="Test Report"></a>
  <a href="#"><img src="https://img.shields.io/badge/stability-production_ready-brightgreen" alt="Stability"></a>
</p>

---

**SOMA** is a lightweight, pluggable cognitive framework that gives AI agents the ability to *think*, not just retrieve. It organizes memory around an explicit **wisdom framework** — seven thinking laws that form a reasoning network, not a flat list. Laws chain through relations, combine into synthesized perspectives, and self-correct against cognitive bias. The result: agents that decompose problems systematically, activate relevant knowledge bidirectionally, and evolve their own reasoning over time.

> **Not "make AI remember more." Make AI *understand deeper*.**

📖 **[中文文档](README_zh.md)** | **[Documentation](docs/)** | **[Test Reports](reports/)** | **[Changelog](CHANGELOG.md)** | **[Contributing](CONTRIBUTING.md)**

<p align="center">
  <img src="https://raw.githubusercontent.com/sunyan999999/soma/main/docs/images/demo-pipeline.gif" alt="SOMA Pipeline Demo" width="720">
</p>

## ⚡ Five-Minute Integration

```bash
pip install soma-wisdom
python -m soma          # one-command verification
```

```python
from soma import SOMA

soma = SOMA()                                        # zero-config start

soma.remember(
    "First-principles thinking: deconstruct to fundamentals...",
    context={"domain": "philosophy", "type": "theory"},
    importance=0.9,
)

answer = soma.respond("How to analyze our growth bottleneck?")
print(answer)
```

No API key required for mock mode. Set `llm="deepseek-chat"` (or any LiteLLM model) for real LLM responses.

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           SOMA Agent (v0.7)                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐            │
│  │ WisdomEngine  │→│ActivationHub │→│     MemoryCore        │            │
│  │ · 关键词匹配  │  │ · 双向激活   │  │ · episodic/semantic   │            │
│  │ · 规律链传播  │  │ · 反视角检索 │  │ · skill/sqlite+vector │            │
│  │ · 组合模板    │  │ · 可用性修正 │  │ · 加权RRF+时间衰减    │            │
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
│  │  v0.6 Reasoning Engine              │  v0.6 Causal Extraction     │   │
│  │  · 17 reasoning templates           │  · Auto-extract triples     │   │
│  │  · Hypothesis + evidence matrix     │  · Lightweight LLM (~200tk) │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────┘

Twelve-Stage Wisdom Pipeline:
  Assess → Decompose → Chain → Combine → Semantic-fallback
         → Context-sort → Activate → Anti-bias → Reason
         → Synthesize → Causal-extract → Evolve
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

SOMA v0.7.0 — benchmarked with 1,752 real production memories from 零熵智库:

### Overall Score: 84.8/100

| Dimension | Score | Grade |
|-----------|:---:|:---:|
| **Overall** | **84.8** | Excellent |
| **Memory** | **92.2** | Excellent — 100% recall, <4ms latency |
| **Wisdom** | **80.7** | Good — exploration factor active, diversity entropy 0.87 |
| **Evolution** | **71.9** | Good — 942 reflections, weight auto-adaptation |
| **Scalability** | **100.0** | Excellent — linear scaling at 1K |

### Key Metrics

| Metric | Value | Stability |
|--------|:----:|:---:|
| Semantic Recall Rate | 100% | ● Stable |
| Dedup Ratio | 100% | ● Stable |
| Avg Insert Latency | 3.44ms | ◐ Acceptable |
| 1K Query Latency | 3.74ms | ● Stable |
| Decomposition Coverage | 100% | ● Stable |
| Thinking Diversity Entropy | 0.87 | ● Stable |
| Cross-Domain Activation | 100% | ● Stable |

### Live Competitor Comparison

| System | Recall@5 | Reasoning | Evolution | Consolidation | Forgetting |
|--------|:---:|:---:|:---:|:---:|:---:|
| **SOMA v0.7** | **100%** | **✓** | **✓** | **✓** | **✓** |
| ChromaDB | 2.5% | ✗ | ✗ | ✗ | ✗ |
| Mem0 | * | ✗ | ✗ | ✓ | ✗ |
| Zep | * | ✗ | ✗ | ✓ | ✗ |

> SOMA is the only system combining a reasoning framework, evolutionary self-optimization, memory consolidation, and active forgetting — all without external services.

Full report: [TEST_REPORT_v0.7.0_FINAL.md](TEST_REPORT_v0.7.0_FINAL.md) | [CHANGELOG.md](CHANGELOG.md)

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

pytest -v --cov=soma --cov-report=term    # 342 tests, ~97% coverage

python -m soma                              # quickstart verification

python dash/server.py                       # API server (http://localhost:8765)
```

### Project Structure

```
soma-core/
├── soma/                  # Core library
│   ├── __init__.py        # SOMA facade (zero-config entry)
│   ├── __main__.py        # python -m soma quickstart
│   ├── agent.py           # SOMA_Agent: pipeline orchestrator
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
│   ├── analytics.py       # Usage analytics & benchmark storage
│   ├── benchmarks.py      # 5D benchmark engine (memory/wisdom/evolution/scalability/overall)
│   ├── wisdom_laws.yaml   # Default thinking framework (bundled)
│   └── memory/
│       ├── core.py        # MemoryCore: unified memory facade
│       ├── episodic.py    # EpisodicStore: SQLite + vector BLOB
│       ├── semantic.py    # SemanticStore: knowledge triples
│       ├── skill.py       # SkillStore: learned patterns
│       ├── consolidation.py  # ConsolidationEngine: memory dedup
│       ├── forgetting.py     # ForgettingEngine: Ebbinghaus decay
│       ├── external.py       # External knowledge import (Markdown/JSON/URL)
│       └── search_utils.py   # FTS5 shared search utilities
├── dash/                  # Dashboard & API server
│   ├── server.py          # FastAPI (REST + SSE streaming + auth)
│   ├── providers.py       # LLM provider manager
│   └── frontend/          # Vue 3 dashboard UI (i18n: EN/ZH)
├── docs/                  # Documentation (EN + ZH bilingual)
├── tests/                 # 196 tests, ~97% coverage
├── examples/              # Usage examples
└── pyproject.toml         # Build config
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
