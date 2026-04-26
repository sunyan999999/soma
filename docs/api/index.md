# API Reference

> Auto-generated from docstrings. For the full interactive API docs, see the Swagger UI at `http://localhost:8765/docs` when the server is running.

## SOMA Facade

```python
from soma import SOMA

soma = SOMA(
    framework_config="wisdom_laws.yaml",
    llm="deepseek-chat",
    use_vector_search=True,
    persist_dir="soma_data",
    recall_threshold=0.01,
    top_k=5,
)
```

### `soma.respond(problem: str) -> str`

Run the full wisdom pipeline: decompose → activate → synthesize → reflect.

```python
answer = soma.respond("How to analyze our growth bottleneck?")
```

### `soma.chat(problem: str) -> dict`

Structured response including decomposition foci, activated memories, and memory stats.

```python
result = soma.chat("What is first-principles thinking?")
# {
#   "problem": "...",
#   "answer": "...",
#   "foci": [{"law_id": "...", "dimension": "...", "keywords": [...], "weight": 0.9, "rationale": "..."}],
#   "activated_memories": [{"content": "...", "source": "episodic", "activation_score": 0.89}],
#   "memory_stats": {"episodic": 42, "semantic": 15, "indexed_vectors": 42},
#   "weights": {"first_principles": 0.90, ...}
# }
```

### `soma.remember(content, context, importance) -> str`

Store an episodic memory. Returns memory UUID.

```python
memory_id = soma.remember(
    "First-principles thinking: deconstruct to fundamentals.",
    context={"domain": "philosophy", "type": "theory"},
    importance=0.9
)
```

### `soma.remember_semantic(subject, predicate, object, confidence) -> None`

Store a semantic triple (knowledge graph edge).

```python
soma.remember_semantic("Fast decision", "depends_on", "First principles", confidence=1.0)
```

### `soma.query_memory(query: str, top_k: int = 5) -> list`

Direct memory search, bypassing framework decomposition.

```python
memories = soma.query_memory("growth strategy", top_k=10)
```

### `soma.decompose(problem: str) -> list`

Show the thinking decomposition without running the full pipeline.

```python
foci = soma.decompose("How to improve team productivity?")
for f in foci:
    print(f"{f.law_id} (w={f.weight}): {f.rationale}")
```

### `soma.reflect(task_id: str, outcome: str) -> None`

Record an outcome for meta-evolution tracking.

```python
soma.reflect("task_001", "success")
```

### `soma.evolve() -> list`

Trigger automatic evolution. Returns list of weight changes applied.

```python
changes = soma.evolve()
# ["pareto_principle: 0.75 → 0.77", "inversion: 0.70 → 0.68"]
```

### `soma.get_weights() -> dict`

Get current law weights.

```python
weights = soma.get_weights()
# {"first_principles": 0.90, "systems_thinking": 0.85, ...}
```

### `soma.adjust_weight(law_id: str, new_weight: float) -> bool`

Manually set a law's weight.

```python
soma.adjust_weight("pareto_principle", 0.82)
```

### `soma.stats -> dict`

Memory store statistics.

```python
stats = soma.stats
# {"episodic": 42, "semantic": 15, "skills": 3, "indexed_vectors": 42}
```

---

## SOMA_Agent (Internal)

```python
from soma.agent import SOMA_Agent
from soma.config import SOMAConfig, load_config
from pathlib import Path

config = SOMAConfig(
    framework=load_config(Path("wisdom_laws.yaml")),
    episodic_persist_dir=Path("soma_data"),
)
agent = SOMA_Agent(config)
```

### `agent.respond(problem: str) -> str`

Same pipeline as `SOMA.respond`, without the auto-evolution counter.

### `agent.decompose(problem: str) -> List[Focus]`

Raw decomposition result.

### `agent.remember(content, context, importance) -> str`

Direct memory storage, same as facade.

### `agent.reflect(task_id, outcome) -> None`

Record session outcome.

---

## WisdomEngine

```python
from soma.engine import WisdomEngine
from soma.config import load_config

framework = load_config("wisdom_laws.yaml")
engine = WisdomEngine(framework)
```

### `engine.decompose(problem: str) -> List[Focus]`

Decompose a problem using the wisdom framework. Returns a list of `Focus` objects:

```python
@dataclass
class Focus:
    law_id: str        # e.g. "first_principles"
    dimension: str     # Human-readable analysis lens
    keywords: List[str] # Extracted keywords for activation
    weight: float      # Law weight (0.0–1.0)
    rationale: str     # Why this law was activated
```

### `engine.laws: List[WisdomLaw]`

Access the loaded laws:

```python
@dataclass
class WisdomLaw:
    id: str
    name: str
    description: str
    weight: float
    triggers: List[str]
    relations: List[str]
```

---

## ActivationHub

```python
from soma.hub import ActivationHub
from soma.memory.core import MemoryCore

memory = MemoryCore(config)
hub = ActivationHub(memory, top_k=10, threshold=0.01)
```

### `hub.activate(foci: List[Focus]) -> List[ActivatedMemory]`

Bidirectional memory activation for given foci.

```python
@dataclass
class ActivatedMemory:
    memory: MemoryUnit   # The full memory object
    source: str          # "episodic" | "semantic" | "skill"
    activation_score: float  # Combined RRF score
```

### `hub.explain_activation(am: ActivatedMemory) -> dict`

Get a human-readable explanation of why a memory was activated.

---

## MetaEvolver

```python
from soma.evolve import MetaEvolver

evolver = MetaEvolver(engine, memory_core=memory, persist_dir="soma_data")
```

### `evolver.reflect(task_id: str, outcome: str) -> None`

Record a session's outcome for later analysis.

### `evolver.evolve() -> List[str]`

Run evolution. Returns human-readable list of changes applied.

### `evolver.get_weights() -> dict`

Get current law weights from the evolver's tracked state.

### `evolver.adjust_weight(law_id: str, new_weight: float) -> bool`

Manually set a law weight.

---

## LangChain Tool

```python
from soma.langchain_tool import create_soma_tool
from soma import SOMA

soma = SOMA()
tool = create_soma_tool(soma._agent)
result = tool.run("Analyze this problem...")
```

---

## REST API

When the server is running (`python dash/server.py` → `http://localhost:8765`):

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/chat` | POST | Wisdom pipeline chat |
| `/api/chat/stream` | POST | SSE streaming chat |
| `/api/memory/search` | POST | Direct memory search |
| `/api/config/llm` | GET | Current LLM configuration |
| `/api/config/providers/switch` | POST | Switch LLM provider |
| `/api/analytics/summary` | GET | Usage analytics summary |
| `/api/analytics/compare` | GET | Session comparison data |
| `/api/analytics/sessions` | GET | Recent sessions list |
| `/api/benchmarks/run` | POST | Run benchmark suite |
| `/api/benchmarks/latest` | GET | Latest benchmark results |
| `/api/benchmarks/compare` | GET | Compare benchmark runs |
| `/api/framework/stats` | GET | Framework state and weights |
| `/api/framework/log` | GET | Evolution change log |
| `/docs` | GET | Swagger UI (auto-generated) |
