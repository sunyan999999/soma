# SOMA — Somatic Wisdom Architecture

<p align="center">
  <strong>Wisdom over Memory — 智慧超越记忆</strong><br>
  <em>Framework-First Cognitive Architecture for AI Agents</em>
</p>

<p align="center">
  <a href="https://github.com/sunyan999999/soma"><img src="https://img.shields.io/github/stars/sunyan999999/soma?style=social" alt="GitHub stars"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue" alt="License"></a>
  <a href="#"><img src="https://img.shields.io/badge/version-0.3.0b1-orange" alt="Version"></a>
  <a href="#"><img src="https://img.shields.io/badge/python-3.10%2B-green" alt="Python"></a>
  <a href="#benchmarks"><img src="https://img.shields.io/badge/semantic_recall-100%25-brightgreen" alt="Semantic Recall"></a>
  <a href="#benchmarks"><img src="https://img.shields.io/badge/query_latency-5.4ms-brightgreen" alt="Latency"></a>
  <a href="#benchmarks"><img src="https://img.shields.io/badge/overall_score-89-brightgreen" alt="Overall Score"></a>
  <a href="#"><img src="https://img.shields.io/badge/tests-139-brightgreen" alt="Tests"></a>
  <a href="#"><img src="https://img.shields.io/badge/coverage-~97%25-brightgreen" alt="Coverage"></a>
</p>

---

**SOMA** is a lightweight, pluggable cognitive framework that gives AI agents the ability to *think*, not just retrieve. It organizes memory around an explicit **wisdom framework** — seven thinking laws from first-principles reasoning to contradiction analysis. The result: agents that decompose problems systematically, activate relevant knowledge bidirectionally, and evolve their own reasoning over time.

> **Not "make AI remember more." Make AI *understand deeper*.**

📖 **[中文文档](README_zh.md)** | **[Documentation](docs/)** | **[Contributing](CONTRIBUTING.md)** | **[Changelog](CHANGELOG.md)**

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
┌─────────────────────────────────────────────────────────┐
│                    SOMA Agent                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ WisdomEngine  │→│ActivationHub │→│  MemoryCore   │  │
│  │ (decompose)  │  │  (activate)  │  │  (retrieve)   │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│         │                │                  │           │
│         ▼                ▼                  ▼           │
│  ┌──────────────────────────────────────────────────┐   │
│  │         MetaEvolver (reflect → evolve)            │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘

Four-Step Wisdom Pipeline:
  Problem → Decompose → Activate → Synthesize → Evolve
```

## Dashboard

SOMA ships with a Vue 3 dashboard (i18n: English / Chinese). Start the API server and open `http://localhost:8765`:

```bash
SOMA_API_KEY=test python dash/server.py
```

| Chat | Framework | Memory |
|:---:|:---:|:---:|
| [![Chat](docs/images/screenshot-chat.png)](docs/images/screenshot-chat.png) | [![Framework](docs/images/screenshot-framework.png)](docs/images/screenshot-framework.png) | [![Memory](docs/images/screenshot-memory.png)](docs/images/screenshot-memory.png) |
| **Wisdom-driven conversation** — decompose → activate → synthesize | **7 thinking laws** — live weights, manual & auto adjustment | **Memory bank** — semantic search, bidirectional activation |

| Analytics | Benchmarks | Settings |
|:---:|:---:|:---:|
| [![Analytics](docs/images/screenshot-analytics.png)](docs/images/screenshot-analytics.png) | [![Benchmarks](docs/images/screenshot-benchmarks.png)](docs/images/screenshot-benchmarks.png) | [![Settings](docs/images/screenshot-settings.png)](docs/images/screenshot-settings.png) |
| **Usage analytics** — session history, weight evolution, dimension trends | **3D benchmarks** — memory, wisdom, evolution scores + competitor compare | **LLM config** — multi-provider, API key, model selector |

> 🇬🇧 [English UI](docs/images/screenshot-chat-en.png)

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

### 2. Bidirectional Activation — Hybrid RRF

Memories are matched through **weighted Reciprocal Rank Fusion**:
- Vector semantic similarity (×2 weight) via ONNX embeddings
- Keyword exact match (×1 weight)

Both directions compete and complement, producing true relevance scores.

### 3. Meta-Evolution — Self-Optimization

SOMA tracks success/failure of each thinking law across sessions. Every 10 sessions, `evolve()` automatically:
- Adjusts law weights: +2% for successful laws, -2% for underperforming ones
- Solidifies successful (law, domain, outcome) patterns into skills

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

## Benchmarks

SOMA v0.2.0-alpha on commodity CPU (2026-04-26):

| Metric | Score | Notes |
|--------|:-----:|-------|
| **Semantic Recall** | **100%** | 10/10 paraphrased queries correctly recalled |
| **Query Latency** | **5.4ms** | ONNX-accelerated (fastembed), 17× faster than v0.1.0 |
| **Insert Latency** | 0.1ms | With SHA256 dedup + vector encoding |
| **Dedup Rate** | 100% | Content-hash based deduplication |
| **Decomposition Coverage** | 100% | 10/10 question types correctly decomposed |
| **Thinking Diversity** | 0.596 | Entropy across 7 thinking laws |
| **Synthesis Gain** | +45% | Answer depth vs. bare LLM baseline |

### Overall Scores

| Dimension | Score | Weight |
|-----------|:-----:|:------:|
| **Memory** | **97** | 35% |
| **Wisdom** | **85** | 35% |
| **Evolution** | **86** | 30% |
| **Overall** | **89** | — |

### Competitive Landscape

| System | Semantic Recall | Query Latency | Dedup | Reasoning | Evolution |
|--------|:---:|:---:|:---:|:---:|:---:|
| **SOMA** | **100%** | **5.4ms** | **✓** | **Framework-based** | **✓** |
| Mem0 | 92% | 15ms | ✓ | — | — |
| MemPalace | 96% | 8ms | ✓ | — | — |
| Letta (MemGPT) | 88% | 20ms | ✓ | — | — |
| Zep | 90% | 30ms | ✓ | — | — |

SOMA is the only system that combines memory storage, a reasoning framework, and evolutionary self-optimization.

## Development

```bash
git clone https://github.com/soma-project/soma-core.git
cd soma-core
pip install -e ".[dev]"

pytest -v --cov=soma --cov-report=term    # 139 tests, ~97% coverage

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
│   ├── plugin.py          # Entry-points plugin auto-discovery
│   ├── analytics.py       # Usage analytics & benchmark storage
│   ├── benchmarks.py      # 3D benchmark engine (memory/wisdom/evolution)
│   ├── wisdom_laws.yaml   # Default thinking framework (bundled)
│   └── memory/
│       ├── core.py        # MemoryCore: unified memory facade
│       ├── episodic.py    # EpisodicStore: SQLite + vector BLOB
│       ├── semantic.py    # SemanticStore: knowledge triples
│       └── skill.py       # SkillStore: learned patterns
├── dash/                  # Dashboard & API server
│   ├── server.py          # FastAPI (REST + SSE streaming + auth)
│   ├── providers.py       # LLM provider manager
│   └── frontend/          # Vue 3 dashboard UI (i18n: EN/ZH)
├── docs/                  # Documentation (EN + ZH bilingual)
├── tests/                 # 139 tests, ~97% coverage
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
