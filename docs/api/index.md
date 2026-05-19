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

Structured response including decomposition foci, activated memories, reasoning framework (v0.6.0+), and memory stats.

```python
result = soma.chat("What is first-principles thinking?")
# {
#   "problem": "...",
#   "answer": "...",
#   "foci": [{"law_id": "...", "dimension": "...", "keywords": [...], "weight": 0.9, "rationale": "..."}],
#   "activated_memories": [{"content": "...", "source": "episodic", "activation_score": 0.89}],
#   "reasoning": [{"index": 1, "dimension": "...", "template": "...", "hypothesis": "...", "evidence": [...], "counter_evidence": [...]}],
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

### `agent.respond(problem: str, user_id: str = "") -> str`

Same pipeline as `SOMA.respond`, without the auto-evolution counter.

Pipeline (v0.6.0): complexity assess → decompose → activate → anti-bias search → **reasoning framework** → build prompt → call LLM → **causal extraction** → record.

### `agent.decompose(problem: str) -> List[Focus]`

Raw decomposition result.

### `agent.remember(content, context, importance, user_id="", session_id="") -> str`

Direct memory storage, same as facade.

### `agent.remember_semantic(subject, predicate, object_, confidence=1.0, namespace="") -> None`

Store a semantic triple (knowledge graph edge).

### `agent.query_memory(query: str, top_k: int = 5, user_id: str = "") -> List[Dict]`

Direct memory search, bypassing framework decomposition.

### `agent.reflect(task_id, outcome) -> None`

Record session outcome for meta-evolution tracking.

### `agent.close() -> None`

Close all sub-component connections (memory + evolver). Supports context manager (`with SOMA_Agent(config) as agent:`).

### v0.6.0 Reasoning Engine (Internal)

#### `agent._assess_complexity(problem: str) -> int`

Static method. Returns 1 (simple), 2 (medium), or 3 (complex) based on text length (>100 chars) and depth keywords (为什么/如何/深层/根本/系统/矛盾 etc.).

#### `agent._execute_reasoning(problem, foci, activated, anti_memories) -> List[Dict]`

Build structured reasoning framework for each focus. Matches reasoning templates, hypothesis templates, collects supporting and counter evidence. Caps at 7 foci for L3. Returns list of reasoning blocks, each containing: `index`, `dimension`, `weight`, `template`, `hypothesis`, `evidence` (up to 3), `counter_evidence` (up to 2).

#### `agent._match_template(law_id: str, templates: Dict[str, str]) -> str`

Match a law_id to a reasoning/hypothesis template. Supports exact match, prefix match, and bidirectional substring match for combo templates.

#### `agent._extract_causal_relations(problem: str, answer: str) -> None`

Lightweight LLM call (~200 tokens) to extract "subject|predicate|object" triples from answer. Only triggers when `config.causal_extraction=True` and complexity >= `config.causal_extraction_complexity`. Failures are silently ignored.

#### `agent._last_reasoning: List[Dict]`

Instance variable storing the most recent reasoning framework. Readable by dashboards and external callers for observability.

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

---

## SOMAOrchestrator (v1.1.0)

Multi-agent orchestration: route → **parallel dispatch** → collect → consensus → **evolve**.

v1.1.0 adds parallel agent calling (4.9x speedup) and DistributedEvolver integration.

```python
from soma import SOMA

soma = SOMA(orchestration_mode="multi")

# Register domain experts
soma.register_expert("analyst", expertise=["商业分析", "战略"], description="商业战略分析师")
soma.register_expert("engineer", expertise=["技术", "架构"], description="技术架构师")

# Solve with multi-agent consensus — agents called in parallel since v1.1.0
result = soma.solve_multi("如何平衡技术投入与业务增长？")
print(result.answer)
print(result.consensus.agreement_level)   # float: 0.0–1.0
print(result.agents_involved)             # ["analyst", "engineer"]
print(result.routing_strategy)            # "l1" | "l2" | "fallback"
```

### New in v1.1.0: Parallel Dispatch

5 agents × 100ms each: 502ms (serial) → **102ms (parallel), 4.9x speedup**.

Controlled by `SOMAConfig.orchestration_parallel` (default: `True`). Auto-degrades to serial for single-agent.

### New in v1.1.0: Distributed Evolution

After each `solve()`, agent participation is recorded. Every N solves (default: 10), global weights are merged via `DistributedEvolver.merge_weights()` and pushed back to all agents.

Controlled by:
- `SOMAConfig.orchestration_evolution_enabled` (default: `True`)
- `SOMAConfig.orchestration_evolution_interval` (default: `10`)

### `orch.stats` (updated v1.1.0)

```python
stats = orch.stats
# {
#   "agent_count": 3,
#   "solve_count": 25,
#   "parallel_enabled": True,
#   "evolution_enabled": True,
#   "evolution": {"agent_count": 3, "merge_count": 2, ...}
# }
```

### `SOMAOrchestrator(config: SOMAConfig)`

Direct constructor for fine-grained control:

```python
from soma.multi_agent.orchestrator import SOMAOrchestrator

orch = SOMAOrchestrator(config)
```

### `orch.create_agents(specs: List[Dict]) -> List[str]`

Batch-create and register agents. Each spec:

| Field | Required | Description |
|-------|:--:|------|
| `agent_id` | yes | Unique agent identifier |
| `expertise` | yes | List of expertise tags |
| `description` | no | Human-readable description |
| `group_id` | no | Collaboration group |
| `persist_dir` | no | Per-agent persistence directory |
| `is_default` | no | Set as fallback agent |

### `orch.solve(problem, strategy="voting", top_k=3) -> OrchestrationResult`

End-to-end multi-agent pipeline. Strategies:

| Strategy | Description |
|----------|-------------|
| `voting` | Weighted majority vote (default, zero LLM cost) |
| `llm_arbitration` | LLM reviews all opinions and picks the best |
| `dialectical_synthesis` | LLM synthesizes a new answer from conflicting views |

### `OrchestrationResult`

```python
@dataclass
class OrchestrationResult:
    question: str                    # Original problem
    answer: str                      # Final consensus answer
    agents_involved: List[str]       # Participating agent IDs
    routing_strategy: str            # "l1" | "l2" | "fallback"
    consensus: ConsensusResult       # Full consensus details
```

### `ConsensusResult`

```python
@dataclass
class ConsensusResult:
    consensus_answer: str            # Final answer
    agreement_level: float           # 0.0–1.0 inter-agent agreement
    disagreements: List[str]         # Points of disagreement
    minority_view: str               # Minority opinion (if any)
    opinions: List[AgentOpinion]     # Individual agent responses
```

---

## SceneStore (v1.0.0 L2)

Scene blocks — topic aggregation from multiple episodic memories.

```python
from soma.memory.scene import SceneStore
from pathlib import Path

store = SceneStore(persist_dir=Path("soma_data"), collection_name="scenes")
```

### `store.store(memory: MemoryUnit) -> str`

Store a scene block. Returns scene ID.

### `store.query(query_text: str, top_k: int = 5) -> List[MemoryUnit]`

Semantic search over scene blocks.

### `store.get_by_user(user_id: str) -> List[MemoryUnit]`

Retrieve all scenes for a specific user.

---

## ProfileStore (v1.0.0 L3)

User profile — stable traits extracted across scene blocks.

```python
from soma.memory.profile import ProfileStore

store = ProfileStore(persist_dir=Path("soma_data"))
```

### `store.upsert_trait(user_id, trait_type, trait_key, trait_value, confidence) -> str`

Insert or update a profile trait. Trait types: `preference`, `skill`, `habit`, `knowledge_gap`, `goal`.

### `store.get_profile(user_id: str) -> List[Dict]`

Get all profile entries for a user, grouped by trait type.

---

## CapturePipeline (v1.0.0 Auto-Capture)

Background pipeline that automatically extracts scenes and profiles from episodic memories.

```python
from soma.memory.capture import CapturePipeline, CaptureConfig

config = CaptureConfig(
    scene_extraction_enabled=True,
    profile_extraction_enabled=True,
    scene_extraction_warmup=5,
)
pipeline = CapturePipeline(memory_core, scene_store, profile_store, config)

# Trigger a capture cycle (typically called automatically)
result = pipeline.capture(user_id="default")
print(result.scenes_created)
print(result.profiles_updated)
```

---

## MCP Server (v1.0.0)

Expose SOMA as an MCP (Model Context Protocol) server for Claude Code and other MCP clients.

```bash
python -m soma.mcp_server
```

Claude Code configuration (`~/.claude/settings.json`):

```json
{
  "mcpServers": {
    "soma": {
      "command": "python",
      "args": ["-m", "soma.mcp_server"],
      "env": {
        "SOMA_DATA_DIR": "~/.soma/claude",
        "SOMA_LLM": "deepseek-chat"
      }
    }
  }
}
```

Exposed tools: `soma_remember`, `soma_recall`, `soma_chat`, `soma_evolve`, `soma_stats`.

Auto-detects installed capabilities and adjusts tool list accordingly. No LLM → memory-only mode. v0.9.0 → no scene/profile tools.
