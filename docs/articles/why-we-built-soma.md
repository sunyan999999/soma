# Why We Built SOMA — A Cognitive Framework, Not Just a Vector Store

> The AI agent ecosystem has dozens of "memory" solutions. What it doesn't have is a system that helps agents *think*. That's why we built SOMA.

---

## The Problem We Saw

In early 2026, we were building an AI coding agent (Glaude). It needed memory — to remember bugs it fixed, architectural decisions it made, patterns it learned. We tried the usual suspects:

- **ChromaDB** gave us vector search. It found semantically similar memories. But the agent still made the same class of mistakes in different contexts. It could *retrieve* but couldn't *understand*.

- **Mem0** was cleaner. It stored and retrieved memories with a nice API. But when our agent faced a complex debugging problem, the retrieved memories were a flat list. No structure. No reasoning chain. Just "here are 5 similar memories."

- **LangChain's memory** was fine for chat history. But our agent needed more than conversation — it needed to learn from its own debugging processes.

What was missing? **A thinking framework.** The agent could remember. It couldn't *reason about what it remembered*.

## The Core Insight: Memory ≠ Intelligence

Here's what we realized: intelligence isn't about how much you remember. It's about how you *organize and apply* what you remember.

Human experts don't solve problems by searching a mental database for the most similar past experience. They:
1. Decompose the problem into dimensions
2. Activate relevant knowledge frameworks
3. Combine perspectives from different domains
4. Test hypotheses against evidence
5. Self-correct when a pattern becomes a rut

Why should AI agents work any differently?

## What SOMA Does Differently

### 1. Wisdom Framework — 7 Thinking Laws

Instead of a flat memory store, SOMA provides a **reasoning network**. Seven thinking laws — from First Principles to Evolutionary Lens — form a connected graph. When one law triggers, its relations propagate activation to related laws. When two laws fire together, synthesized perspectives emerge.

```python
from soma import SOMA
soma = SOMA()

# Not "search memory for 'growth bottleneck'"
# But "decompose through 7 thinking dimensions"
soma.decompose("How to analyze our growth bottleneck?")
# → ['first_principles', 'systems_thinking', 'pareto_principle',
#    'contradiction_analysis', 'inversion']
```

### 2. Bidirectional Activation

Most memory systems work one way: query → vector → results. SOMA activates in both directions:
- **Forward**: Problem → Thinking laws → Related memories
- **Backward**: Retrieved memories → Re-activate different laws → Anti-perspective retrieval

This means you don't just get "similar" memories. You get memories that are *relevant from different angles*.

### 3. Self-Evolution

Every `soma.reflect(task_id, outcome)` records which thinking laws led to good outcomes. After every 5 sessions, `evolve()` automatically:
- Penalizes overused laws (preventing thinking ruts)
- Boosts underused high-success laws
- Promotes successful trigger words
- Solidifies recurring (law, domain, outcome) patterns into permanent skills

After 942 reflections on real production tasks, the weight distribution converged naturally — no manual tuning.

### 4. Memory That Manages Itself

v0.7.0 added three mechanisms inspired by human memory:
- **Consolidation**: Similar memories auto-merge (FTS5 + cosine >85%), preserving unique details
- **Active forgetting**: Ebbinghaus decay curve removes low-value memories (archived, not deleted)
- **External knowledge**: Import markdown/JSON/URLs with configurable expiry

### 5. Zero Infrastructure

```bash
pip install soma-wisdom   # done
python -m soma             # verify
```

No Docker. No CUDA. No PostgreSQL. No API keys (mock mode). Embeddings run locally via ONNX (~100 MB model). When you're ready for real LLM responses, set `llm="deepseek-chat"` or any LiteLLM model.

## What This Means in Practice

SOMA has been running in production at 零熵智库 for 7 days without restart, managing 1,752 episodic memories, 9,832 semantic triples, and 281 skill templates. The system self-tuned to prioritize:

| Thinking Law | Auto-Adapted Weight |
|---|---|
| Systems Thinking | 1.00 |
| First Principles | 0.90 |
| Contradiction Analysis | 0.90 |
| Inversion | 0.89 |
| Pareto Principle | 0.87 |
| Evolutionary Lens | 0.87 |
| Analogical Reasoning | 0.77 |

Notice: Systems Thinking (seeing interconnected wholes) emerged as the most useful lens — not because we hardcoded it, but because real debugging and architecture problems consistently benefited from it.

## Benchmarks (Reproducible)

| Dimension | Score | Evidence |
|---|---|---|
| Memory | 92.2 | 100% semantic recall, <4ms latency |
| Wisdom | 80.7 | Diversity entropy 0.87, cross-domain activation 100% |
| Evolution | 71.9 | 942 reflections, weight auto-adaptation |
| Scalability | 100.0 | Linear scaling at 1K, 324 inserts/sec |
| **Overall** | **84.8** | 1,752 real production memories |

342 tests, all passing. Reproducible via `python -m soma.benchmarks --full --runs 5`.

## The Road Ahead

We're not building "yet another vector database." We're building a framework that makes AI agents better thinkers over time. Next steps:
- v0.8.0: Multi-agent wisdom sharing — agents learn from each other's reasoning patterns
- v0.9.0: Autonomous law discovery from memory clusters
- v1.0.0: Stable API + plugin ecosystem

## Try It

```bash
pip install soma-wisdom
python -m soma
```

```python
from soma import SOMA
soma = SOMA()
soma.remember("First-principles thinking: deconstruct to fundamentals...", 
              context={"domain": "philosophy"}, importance=0.9)
answer = soma.respond("How to analyze our growth bottleneck?")
print(answer)
```

**5 minutes. That's it.**

---

*github.com/sunyan999999/soma · pypi.org/project/soma-wisdom · Apache 2.0*
