# SOMA: Wisdom over Memory

Most AI memory systems treat memory as passive storage — store everything, retrieve by similarity, hope it's relevant. This is the "high-IQ archive clerk" model: impressive recall, no framework for understanding what matters and why.

SOMA inverts this paradigm. Instead of asking "what stored knowledge is similar to this query?", it asks a deeper question: **"What thinking patterns does this problem activate, and what memories become relevant under those patterns?"**

At its core sits an explicit wisdom framework — seven thinking laws drawn from cognitive science and strategic reasoning: First Principles (regress to fundamentals), Systems Thinking (map interconnections), Contradiction Analysis (surface hidden tensions), Pareto Principle (find the critical few), Inversion (reason backwards), Analogical Reasoning (bridge domains), and Evolutionary Lens (track what adapts). Each law carries weighted keyword triggers and defined inter-relationships. When a problem arrives, SOMA decomposes it through these lenses, identifying which dimensions of thought apply and why — then assembles a structured prompt that guides the LLM rather than merely feeding it context.

This decomposition drives **bidirectional activation**. Rather than one-directional similarity search, SOMA computes the associative potential between each analysis focus and each stored memory — producing a ranked set of truly relevant knowledge, not just keyword-matched text. The framework acts as the index; memory supplies the substance.

The four-stage pipeline — Decompose, Activate, Synthesize, Evolve — runs with every query. After synthesis, SOMA reflects on which memories proved useful and adjusts law weights over time. Laws that consistently generate insight grow stronger; underused ones naturally fade. A law discovery module can even propose new thinking patterns from high-cohesion memory clusters, subject to human approval.

Built as a lightweight Python library with zero mandatory dependencies beyond the standard library, SOMA integrates in five minutes via pip. It ships with a REST API for remote access, a Vue.js dashboard for visual management, native LangChain tooling, and dual memory stores — episodic for experiences and semantic for knowledge triples — with optional vector search for cross-lingual semantic recall. The architecture is fully mockable: every LLM-dependent component accepts an interface, making it trivial to test without API calls. All 139 tests pass at 97% coverage. Zero API keys in the repository.

**Not "make AI remember more." Make AI understand deeper.**
