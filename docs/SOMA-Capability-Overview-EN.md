# SOMA v1.0: The Cognitive Kernel for AI Agents

> A comprehensive capability-focused overview, covering v0.1.0 through the v1.0.0 milestone.

---

## I. What SOMA Is

SOMA (Somatic Wisdom Architecture) is a long-term memory and cognitive reasoning kernel for AI agents. It is not a database. It is not a vector store. It is a **cognitive core that remembers, reasons, collaborates, self-reflects, and continuously evolves**.

In one line: **If the LLM is the cerebral cortex, SOMA is the hippocampus plus the prefrontal cortex.**

---

## II. Five Capability Lines

SOMA's versioning does not chase feature count. It deepens along five capability lines, each answering a fundamental question.

### 2.1 Memory — From "Store It" to "Make Sense of It"

**Core question: How can AI manage memory the way humans do?**

| Stage | Version | Capability | What it means |
|-------|---------|------------|---------------|
| Store | v0.1–0.3 | Episodic memory + semantic search | Remembers conversations, retrieves by meaning |
| Curate | v0.7.0 | Merge + forget + import | Auto-deduplicates, archives stale info, ingests external knowledge |
| Connect | v0.8.0 | Knowledge graph + causal reasoning | Links memories together, traces "why this happened" |
| Layer | v1.0.0 | Three-tier memory system | Fragments → Scenes → Profile. From "what you said" to "who you are" |

**The v1.0.0 three-tier architecture:**

- **L1 Episodic fragments**: Individual pieces of information (the original capability, always present)
- **L2 Scene blocks**: Auto-aggregated work contexts ("working on a Python data analysis project")
- **L3 User profile**: Traits extracted from multiple scenes (preferences, skills, knowledge gaps, goals)

The entire process is automatic. The user simply uses SOMA normally; behind the scenes, it quietly aggregates and distills.

---

### 2.2 Reasoning — From "Find It" to "Understand It"

**Core question: Once you've found relevant information, how do you use it to think?**

v0.8.0 marks the watershed. Before it, SOMA was an excellent search engine — find the most relevant memories and hand them to the LLM. After it, SOMA **participates in the reasoning process itself**:

- **Causal chain tracing**: Not just "this memory is relevant," but tracing the causal graph to root causes. E.g., following "user churn is rising" back to "an API change three months ago slowed response times"
- **Conflict detection**: When memories contain contradictory claims (e.g., "lowering prices reduced churn" vs. "service quality is what retains users"), flag and down-weight automatically, preventing the LLM from being misled
- **Cross-domain analogy**: Use knowledge from domain A to reason about domain B. E.g., bridge "symbiosis in biology" with "corporate partnerships," building connections between seemingly unrelated knowledge
- **Reflection quality scoring**: After each reasoning output, self-evaluate on three dimensions (consistency, coherence, actionability). Below-threshold outputs automatically trigger reflective improvement

**Key design principle**: Reasoning results are injected into the LLM context as "activated memories." They do not alter the LLM's own reasoning logic. SOMA prepares the thinking materials; the LLM makes the final judgment. Each does its part; neither interferes with the other.

---

### 2.3 Collaboration — From "One Mind" to "Many Minds"

**Core question: A single AI has limits. How do multiple AIs work as a team?**

v0.9.0 achieved the paradigm leap from individual to collective. Multiple SOMA agents collaborate as a team:

- **Expert specialization**: Each agent has an independent memory store, independent evolution path, and domain expertise. The tech expert accumulates technical memories; the business expert accumulates business cases
- **Automatic routing**: Incoming problems are dispatched to the most suitable expert via keyword matching + semantic similarity. **Zero LLM involvement in routing decisions** — completed in milliseconds
- **Consensus protocols**: When experts disagree, three-tier fallback: L1 weighted voting → L2 LLM arbitration → L3 dialectical synthesis
- **Distributed evolution**: Each expert evolves independently in their domain (reflect → adjust weights → solidify skills), while periodically merging global experience. Individual expertise preserved; collective wisdom shared

v0.9.1 added a special capability on top — **frame anchoring awareness**. When the user analyzes problems through the same thinking pattern for multiple consecutive rounds, the system gently appends a footnote: "Would another angle help?" No force, no interruption, no decision alteration — just making cognitive inertia visible.

---

### 2.4 Evolution — From "Use Once" to "Gets Better with Use"

**Core question: Can AI learn from its own experience?**

SOMA has a built-in, complete evolution loop. This loop is not a set of preset rule updates; it is self-optimization driven by actual usage:

1. **Reflect**: After each response, the system reflects based on outcomes — was this thinking approach correct? Should the weights be adjusted?
2. **Re-weight**: The seven thinking laws' weights rise and fall with success/failure automatically. Successful laws gain weight and get triggered by more problems; failing laws lose weight
3. **Solidify**: When a law accumulates enough samples with stable success rates, it is automatically solidified into a "skill" — from a temporary tool to a permanent capability
4. **Share**: In multi-agent mode, each expert's evolution results are periodically merged. Good experience spreads across the team

**Key design point**: Evolution is data-driven, not rule-preset. The system doesn't give "First Principles" high weight because it's philosophically important; it gives it high weight because it actually helped solve more problems in practice.

---

### 2.5 Engineering — From "It Runs" to "It's Trustworthy"

**Core question: How do you prove these capabilities are real?**

SOMA has built a complete testing system from unit to integration to benchmark:

- **511 unit tests**: Covering all modules, full regression before every commit
- **Five-dimension benchmark engine**: Memory (recall/latency/persistence/dedup), Wisdom (decomposition/laws/diversity), Evolution (reflection/success rate/solidification), Scalability (1K→10K→100K latency curves), Overall
- **50-question standardized dataset**: Covering strategic decision-making, innovative design, cross-domain reasoning, deep attribution, and experiential learning
- **Competitor comparison framework**: Quantifiable comparison data against Mem0, Letta (MemGPT), Zep, Hermis, and others
- **Multi-run statistical benchmarks**: N independent runs, outputting mean ± stddev, 95% confidence intervals, coefficient of variation, stability ratings

v1.0.0 on a medium-scale dataset of 1,050 memories scored: Memory 97.6 / Wisdom 87.3 / Evolution 60.2 / Scalability 100.0 / Overall 85.5.

---

## III. Architectural Philosophy

SOMA's design follows three core principles, consistent across all versions:

### 3.1 Memory First

Traditional AI agents follow the pattern "receive question → call tools → generate answer." SOMA's approach is **everything starts from memory**:

```
Question → Decompose into core foci → Activate relevant knowledge from memory → Use memory to drive reasoning → Generate answer → Store new experience back into memory
```

Memory is not just a database. It is the **contextual infrastructure** of the entire system. Every reasoning act is memory-driven. Every answer contributes new material back to memory.

### 3.2 Seven Thinking Laws

SOMA distills seven universal thinking patterns from human cognition, forming the cognitive kernel:

| Law | Meaning | Best used for |
|-----|---------|---------------|
| First Principles | Trace back to fundamentals, reason from the bottom up | Reframing problems, breaking assumptions |
| Systems Thinking | Focus on interconnections and feedback loops | Complex system analysis |
| Contradiction Analysis | Identify deep dialectical tensions beneath surface issues | Dilemmas and trade-offs |
| Pareto Principle | A few key factors drive the majority of outcomes | Resource allocation, prioritization |
| Inversion | Reason backward from the worst-case scenario | Risk assessment, breakthrough innovation |
| Analogical Reasoning | Use knowledge from one domain to understand another | Cross-domain innovation |
| Evolutionary Lens | Understand system change through variation, selection, retention | Long-term trends, industry patterns |

These seven laws are not a hardcoded rules engine. Each law has a **dynamic weight** that adjusts automatically based on success and failure in actual use. A startup team and a large enterprise's SOMA instance will eventually have completely different weight distributions.

### 3.3 Backward Compatibility

All new capabilities are **off by default**. Upgrading from v0.1.0 to v1.0.0 requires zero code changes. Behavior is identical unless new features are explicitly enabled. New capabilities are independent of each other; enabling one does not force-enable another.

---

## IV. Version Evolution at a Glance

| Version | Date | Core Capability | In one line |
|---------|------|-----------------|-------------|
| v0.1–0.3 | 2025.05–2026.04 | Episodic memory + semantic search + basic reasoning | Store and find |
| v0.4–0.6 | 2026.05 | Evolution loop + benchmark system | Gets better with use |
| v0.7.0 | 2026.05.07 | Memory merging + active forgetting + external import | Curates itself |
| v0.8.0 | 2026.05.09 | Knowledge graph + causal reasoning + conflict detection | Understands connections |
| v0.9.0 | 2026.05.11 | Multi-agent collaboration + distributed evolution | Works as a team |
| v0.9.1 | 2026.05.13 | Frame anchoring awareness | Notices thinking patterns |
| v1.0.0 | 2026.05.16 | Five-line convergence — three-tier memory + reasoning + multi-agent + awareness + evolution | Cognitive kernel |

---

## V. How SOMA Differs from Alternatives

SOMA is not another vector database or RAG framework. Its differentiation operates on three levels:

1. **It doesn't just retrieve — it reasons**: RAG is "find relevant documents → stitch into prompt." SOMA is "find relevant memories → trace causal chains → detect contradictions → draw cross-domain analogies → hand processed cognitive material to the LLM." There is an extra layer of **cognitive processing** in between.

2. **It doesn't just remember — it evolves**: Most memory systems are static — write, retrieve, unchanged. SOMA's memory is alive — similar content auto-merges, low-value information auto-forgets, thinking-law weights dynamically adjust with use.

3. **It doesn't just work alone — it collaborates**: Multiple SOMA agents can form teams, each with independent memory and expertise, forming collective intelligence beyond any individual through routing and consensus protocols. This is a native capability most agent frameworks lack.

---

## VI. Open Source & Ecosystem

- **PyPI**: `pip install soma-wisdom`
- **GitHub**: [github.com/sunyan999999/soma](https://github.com/sunyan999999/soma)
- **License**: Apache 2.0
- **Python**: ≥ 3.10
- **Core dependencies**: SQLite + FastEmbed + FAISS + NetworkX + LiteLLM

---

*SOMA — Wisdom over Memory.*
