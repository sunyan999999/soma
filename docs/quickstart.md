# Quick Start

Get SOMA running in 5 minutes and give your Agent a thinking soul.

## Installation

```bash
pip install soma-core
```

Requires **Python 3.10+**. The embedding engine uses ONNX Runtime for CPU inference — no CUDA, Docker, or external services needed.

On first run, a small ONNX model (~100 MB, bilingual Chinese-English) is downloaded automatically.

## Verify Installation

```bash
python -m soma
```

This runs a built-in verification that initializes the wisdom framework, creates the memory store, and tests the full pipeline.

## 5-Minute Walkthrough

```python
from soma import SOMA

# 1. Initialize — zero config needed
soma = SOMA()

# 2. Store some memories
soma.remember(
    "First-principles thinking: deconstruct problems to their fundamental elements "
    "and derive solutions from base truths, unconstrained by existing experience.",
    context={"domain": "philosophy", "type": "theory"},
    importance=0.9
)

soma.remember(
    "Our Q3 growth bottleneck was traced to onboarding friction. "
    "After reducing signup steps from 5 to 2, conversion improved 34%.",
    context={"domain": "business", "type": "case_study"},
    importance=0.85
)

# 3. Ask a question — full wisdom pipeline
answer = soma.respond("How should we analyze our product's growth stagnation?")
print(answer)

# 4. Query specific memories
memories = soma.query_memory("growth strategy", top_k=5)
for m in memories:
    print(f"[{m['source']}] score={m['activation_score']:.3f}: {m['content'][:80]}...")

# 5. Check framework state
print(soma.stats)
print(soma.get_weights())
```

## What Happens Under the Hood

When you call `soma.respond(problem)`:

1. **Decompose** — WisdomEngine matches the problem against 7 thinking laws, producing analysis foci
2. **Activate** — ActivationHub retrieves relevant memories via hybrid search (semantic ×2 + keyword ×1 RRF)
3. **Synthesize** — Selected memories are assembled into a prompt with framework context, sent to the LLM
4. **Evolve** — Outcome is recorded; every 10 sessions, law weights auto-adjust

## Running in Mock Mode

No LLM API key? SOMA runs in mock mode by default — it still decomposes problems and activates memories, just skips the LLM call and returns structured analysis.

```python
# Mock mode (default, no API key needed)
soma = SOMA()
answer = soma.respond("How to improve team productivity?")
# Returns: decomposition results + activated memory snippets

# Connect a real LLM
soma = SOMA(llm="deepseek-chat")
# Uses LiteLLM — set DEEPSEEK_API_KEY or OPENAI_API_KEY as env var
```

## Using the REST API

```bash
# Start the server
python dash/server.py
# → http://localhost:8765

# Chat endpoint
curl -X POST http://localhost:8765/api/chat \
  -H "Content-Type: application/json" \
  -d '{"problem": "Analyze our growth bottleneck"}'

# SSE streaming
curl -X POST http://localhost:8765/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"problem": "How to improve team productivity?"}'

# Memory search
curl -X POST http://localhost:8765/api/memory/search \
  -H "Content-Type: application/json" \
  -d '{"query": "growth strategy", "top_k": 10}'
```

## LangChain Integration

```python
from soma.langchain_tool import create_soma_tool
from soma import SOMA

soma = SOMA()
tool = create_soma_tool(soma._agent)
result = tool.run("Analyze this problem with systems thinking...")
```

## Next Steps

- [Philosophy](philosophy.md) — understand the "Framework First" design
- [Architecture](architecture.md) — module map, data flow, class diagrams
- [API Reference](api/) — complete method signatures and examples
- [Customization Guide](guides/customization.md) — custom frameworks, storage backends, LLM config
