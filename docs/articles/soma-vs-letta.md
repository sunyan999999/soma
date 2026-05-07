# SOMA vs Letta (MemGPT): Architecture and Philosophy Compared

> **Bottom line**: Letta gives agents a virtual "operating system" for memory. SOMA gives them a "mind" — a reasoning framework that decomposes problems, self-corrects bias, and evolves over time.

---

## Two Visions of Agent Memory

Letta (formerly MemGPT) pioneered the idea of treating LLM context as a virtual OS — with a main context window, archival storage, and recursive self-editing. It's an elegant OS metaphor applied to language models.

SOMA approaches the same problem from a different angle: **cognitive science**. Instead of an OS managing memory pages, SOMA implements seven thinking laws that form a reasoning network. Memory retrieval is driven by *problem decomposition*, not storage hierarchy.

Both approaches are valid. They just solve different problems.

---

## Architecture Deep Dive

| | SOMA | Letta (MemGPT) |
|---|---|---|
| **Metaphor** | Mind (wisdom framework) | OS (virtual memory) |
| **Memory model** | Episodic + Semantic + Skill | Core context + Archival storage |
| **Retrieval** | Bidirectional activation (vector ×2 + keyword ×1 RRF) | Recursive self-edit + archival search |
| **Reasoning** | 7 thinking laws × 17 templates × combo synthesis | LLM function calling on memory |
| **Self-evolution** | Weight auto-adaptation from reflection history | Not available |
| **Problem decomposition** | 12-stage wisdom pipeline (Assess → Decompose → Chain → ... → Evolve) | Not available |

## Memory Management Philosophy

### Letta: The OS Approach

Letta treats the LLM's context like RAM and external storage like disk:

- **Core memory**: Always in context (like loaded pages in RAM)
- **Archival memory**: Searched on-demand (like disk reads)
- **Self-editing**: The agent decides what to keep in core memory

This is powerful for long-running conversational agents that need to manage finite context windows. The agent actively decides what to "page in" and "page out."

### SOMA: The Mind Approach

SOMA organizes memory around *meaning structures*, not storage tiers:

- **Episodic memory**: Experiences stored with importance scoring, accessed via hybrid retrieval
- **Semantic memory**: Knowledge as (subject, predicate, object) triples with graph traversal
- **Skill memory**: Learned patterns triggered by keyword + domain matching

Memory retrieval isn't about "what fits in context" — it's about "what's relevant to the reasoning path." The 7 thinking laws determine what to look for, and bidirectional activation finds it.

## Self-Evolution: SOMA's Differentiator

Letta's memory management is *process-driven* — the agent follows the OS metaphor to manage storage. SOMA's is *outcome-driven* — the system watches which thinking patterns succeed and adapts:

| Evolution mechanism | How it works |
|---|---|
| **Bias detection** | Laws used >40% of the time get penalized (-0.05) |
| **Underused promotion** | High-success, low-frequency laws get boosted (+0.03) |
| **Trigger word evolution** | Repeated keyword-law co-occurrence promotes new triggers |
| **Skill solidification** | Successful (law, domain, outcome) → permanent skill after 3+ occurrences |
| **Dynamic step sizing** | Adjustment magnitude scales with sample count |

After 942 reflections across 1,752 production memories, SOMA's weights auto-converged to a distribution that reflects actual problem-solving utility — not someone's initial guess.

## Performance

| Metric | SOMA v0.7.0 | Letta |
|---|---|---|
| Setup | `pip install soma-wisdom` | `pip install letta` + server |
| External dependencies | None (ONNX local inference) | PostgreSQL (recommended) or SQLite |
| Embedding model | BGE-small-zh (512d, ONNX) | OpenAI or local |
| Production proven | 7-day uptime, 1752 memories | Yes |
| Test coverage | 342 tests, ~97% | Yes |

## When to Choose SOMA

- You want structured **problem decomposition** before memory retrieval
- You need **offline operation** with zero external services
- You value **self-adaptation** — weights that evolve from real usage
- You're building agents that need to **explain their reasoning**
- You think about agent cognition as more than context management

## When to Choose Letta

- You're building **long-running conversational agents** with bounded context
- You want the **OS metaphor** — it's intuitive and well-documented
- You need **multi-agent memory sharing** (Letta's server architecture)
- You prefer a **managed service** (Letta Cloud)

---

## The Real Answer: Different Philosophies

Letta asks: "How do we manage the finite context window efficiently?"

SOMA asks: "How do we make the agent think better about what it remembers?"

These aren't competing questions — they're complementary. A future integration where SOMA's wisdom framework drives Letta's memory management would be powerful. SOMA decides *what* to remember and *how* to reason. Letta manages *where* it lives in context.

---

*SOMA v0.7.0 — pip install soma-wisdom — github.com/sunyan999999/soma*
