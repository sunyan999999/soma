# Philosophy — Wisdom over Memory

> **Not "make AI remember more." Make AI *understand deeper*.**

## The Problem with Memory-First AI

Most AI memory systems treat memory as passive storage: store everything, retrieve by similarity, hope it's relevant. This is the "high-IQ archive clerk" model — impressive recall, but no framework for understanding what matters and why.

Humans with genuine insight don't rely on eidetic memory. They possess a mental framework — a set of thinking patterns that decompose any problem into its essential dimensions. Memories aren't files to retrieve; they're nourishment for the present moment.

## Framework First, Memory Second

SOMA inverts the conventional paradigm. Instead of "store → search → maybe relevant", SOMA asks:

> *"What thinking patterns does this problem activate, and what memories become nourishment under those patterns?"*

The wisdom framework is the **index**. Memory is the **raw material**. The framework decides what's relevant; memory supplies the substance.

## The Four-Step Wisdom Pipeline

```
Problem → Decompose → Activate → Synthesize → Evolve
```

### 1. Decompose (拆解)

The problem is analyzed through 7 thinking laws. Each law that matches contributes an analysis focus — a lens through which to view the problem. A growth stagnation question might activate:

- **First Principles**: What are the fundamental drivers of growth?
- **Systems Thinking**: What feedback loops are at play?
- **Pareto Principle**: Which 20% of factors drive 80% of the bottleneck?
- **Contradiction Analysis**: What opposing forces create the tension?

### 2. Activate (激活)

Each focus triggers a **bidirectional memory search**:

- **Top-down** (semantic): Vector similarity search across episodic memories
- **Bottom-up** (keyword): Direct term matching across semantic triples and skills

Results fuse via **weighted Reciprocal Rank Fusion** (semantic ×2, keyword ×1), producing activation scores that reflect true relevance — not just surface similarity.

### 3. Synthesize (合成)

Activated memories become **nourishment (资粮)**. They're assembled into a structured prompt alongside the framework context:

```
You are a wise thinker. Here are the thinking lenses to use:
  1. First Principles (weight 0.90): ...
  2. Systems Thinking (weight 0.85): ...

Here is relevant nourishment from past experience:
  [Memory A] score=0.89: ...
  [Memory B] score=0.76: ...

Current problem: ...
```

The LLM receives not just facts, but a *thinking structure* with curated supporting material.

### 4. Evolve (进化)

After every session, SOMA records which thinking laws were used and whether the outcome was successful. Every 10 sessions:

- Law weights auto-adjust (+2% for high-success laws, -2% for low)
- Successful (law, domain, outcome) patterns solidify into skills
- The framework becomes progressively more attuned to real problem-solving patterns

## The Seven Thinking Laws

| Law | Weight | Description |
|-----|:---:|------|
| First Principles | 0.90 | Reduce to fundamentals, derive from base truths |
| Systems Thinking | 0.85 | See interconnected wholes, identify feedback loops |
| Contradiction Analysis | 0.80 | Find opposing forces, identify principal contradictions |
| Pareto Principle | 0.75 | Focus the vital few that drive most outcomes |
| Inversion | 0.70 | Think backwards — how could this fail? |
| Analogical Reasoning | 0.65 | Map structures across domains |
| Evolutionary Lens | 0.60 | Observe change over time, identify lifecycle stages |

Weights are starting defaults. They evolve through use.

## Memory as Nourishment, Not Archive

Conventional memory systems treat memories as files. SOMA treats them as **资粮 (zī liáng)** — a Zen term for the nourishment a practitioner gathers along the path, to be consumed when needed.

A memory's relevance isn't static. It depends on:

- **Importance**: How significant was this when stored?
- **Recency**: How recently was it created or accessed?
- **Frequency**: How often has it been activated?
- **Context match**: How well does its domain align with the current problem?

The **Relevance Potential** formula captures this:

```
R(m) = recency_decay × importance × (1 + 0.1 × access_count)
```

## Meta-Evolution: The System That Improves Itself

SOMA doesn't just use the framework — it observes how well the framework works, and adjusts it. This is **meta-cognition**:

1. **Track**: Every session records which laws were activated and the outcome
2. **Reflect**: After 10 sessions, compare success rates across laws
3. **Adjust**: Strengthen laws that correlate with success, weaken those that don't
4. **Solidify**: Successful (law, domain, outcome) patterns become permanent skills

This creates a virtuous cycle: better framework → better answers → better feedback → better framework.

## Why This Matters

| Conventional Memory | SOMA Wisdom |
|------|------|
| "Find similar stuff" | "Find what matters under this lens" |
| Static relevance scores | Dynamic, context-dependent activation |
| Storage-centric | Framework-centric |
| More data = better | Better framework = better |
| No self-improvement | Continuous meta-evolution |
