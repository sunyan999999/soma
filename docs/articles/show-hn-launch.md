# Show HN Launch Package

## 标题

```
Show HN: SOMA – An open-source cognitive memory framework for AI agents
```

## 第一条评论（发布后立即粘贴）

---

We built SOMA because we found a gap in how AI agents handle memory.

Every agent memory system we tried — ChromaDB, Mem0, LangChain memory — did the same thing: store embeddings, retrieve by similarity. They were *storage* systems, not *thinking* systems.

The problem: our AI coding agent (Glaude) kept making the same class of mistakes. It could retrieve similar past bugs, but it couldn't *reason* about them differently. A bug that required systems thinking got the same "here are 5 similar memories" as a bug that required first-principles decomposition.

**What SOMA does differently:**

1. **A wisdom framework instead of a flat memory store.** Seven thinking laws (First Principles, Systems Thinking, Contradiction Analysis, Pareto, Inversion, Analogy, Evolution) form a reasoning network. When a problem arrives, SOMA decomposes it through these dimensions BEFORE retrieving memories. The right memories surface because the right questions are being asked.

2. **Bidirectional activation.** Most systems do query → vector → results. SOMA activates in both directions: the problem triggers relevant laws, those laws find memories, and those memories re-activate different laws for anti-perspective retrieval. You get memories from different angles, not just similar ones.

3. **Self-evolution.** Every `reflect(task_id, outcome)` tracks which thinking patterns succeed. After 5 sessions, `evolve()` auto-adjusts weights — penalizing overused patterns, boosting underused high-success ones. After 942 production reflections, the weights self-tuned to prioritize Systems Thinking (1.00) over Analogical Reasoning (0.77) for debugging tasks.

4. **Memory that manages itself (v0.7.0):** Consolidation merges similar memories. Active forgetting archives low-value ones (Ebbinghaus decay curves). External knowledge imports with configurable expiry.

5. **Zero infrastructure:** `pip install soma-wisdom` is it. Embeddings via ONNX (local CPU, ~100MB model). No Docker, no CUDA, no PostgreSQL. Mock mode for testing without API keys.

**Real numbers (not synthetic benchmarks):**
- 1,752 production memories from 零熵智库
- 100% semantic recall, <4ms query latency
- Overall score 84.8/100 (vs 69.1 for v0.6.1)
- 342 tests, all passing
- 7-day production uptime without restart

**Known limitations (being honest):**
- The Chinese-English bilingual embedding model (BGE-small-zh) works best for Chinese content; English-only workloads might prefer a dedicated English embedder
- The consolidation and forgetting engines need 5+ sessions of accumulated data before they kick in meaningfully
- Law discovery (autonomous identification of new thinking patterns) is experimental and off by default
- No multi-agent wisdom sharing yet (v0.8.0 target)

**We'd love feedback on:**
- Does the "wisdom framework" concept resonate, or does it feel over-engineered?
- Would you use this for non-AI-agent use cases (e.g., personal knowledge management)?
- What's the biggest missing piece before you'd try it in production?

**Quick start:**
```bash
pip install soma-wisdom
python -m soma
```

```python
from soma import SOMA
soma = SOMA()
soma.remember("First-principles thinking: reduce to fundamentals...",
              context={"domain": "philosophy"}, importance=0.9)
answer = soma.respond("How to analyze our growth bottleneck?")
print(answer)
```

Repo: https://github.com/sunyan999999/soma
PyPI: https://pypi.org/project/soma-wisdom/
Docs: https://sunyan999999.github.io/soma/
Benchmarks: https://github.com/sunyan999999/soma/blob/main/TEST_REPORT_v0.7.0_FINAL.md

---

## Reddit 帖子模板

### /r/Python (1.3M 订阅)

**标题**: I built an open-source memory layer for AI agents that thinks, not just retrieves

**正文**:
```
After trying ChromaDB, Mem0, and LangChain memory for my AI coding agent, 
I kept hitting the same wall: they're all storage systems. Vector search 
finds similar stuff, but the agent still makes the same class of mistakes 
because it can't REASON about what it remembers.

So I built SOMA — a cognitive framework that uses 7 thinking laws 
(First Principles, Systems Thinking, Pareto, etc.) to decompose problems 
BEFORE retrieving memories. The right memories surface because the right 
questions are being asked.

Key bits:
- pip install soma-wisdom (zero config, ONNX local embeddings)
- 100% semantic recall at <4ms on 1,752 production memories
- Self-evolving weights that adapt from usage
- Memory consolidation + active forgetting (Ebbinghaus decay)
- 342 tests, Apache 2.0

GitHub: https://github.com/sunyan999999/soma
PyPI: https://pypi.org/project/soma-wisdom/

Would love honest feedback from Python builders who've wrestled with 
agent memory.
```

### /r/MachineLearning (2.9M 订阅)

**标题**: [P] SOMA — A Cognitive Framework for AI Agent Memory (with reproducible benchmarks)

**正文**:
```
We built SOMA to explore a hypothesis: what if agent memory was 
organized around a reasoning framework rather than a flat vector store?

The system implements 7 thinking laws as a connected graph. When a 
problem arrives, laws chain through relations, activate memories 
bidirectionally (forward + anti-perspective), and combine into 
synthesized perspectives. A self-evolution loop tracks success/failure 
per law and auto-adjusts weights every 5 sessions.

We've been running it in production for 7 days with 1,752 real memories. 
Results:
- Memory: 92.2 (100% semantic recall, <4ms latency)
- Wisdom: 80.7 (thinking diversity entropy 0.87)
- Evolution: 71.9 (942 reflections, weights self-converged)
- Scalability: 100 (linear at 1K scale)

Full test report with methodology and competitor comparison:
https://github.com/sunyan999999/soma/blob/main/TEST_REPORT_v0.7.0_FINAL.md

Repo: https://github.com/sunyan999999/soma
Paper (draft): included in docs/

Open to discussion: is a "wisdom framework" a useful abstraction for 
agent memory, or is vector search + good prompting sufficient?
```

### /r/LocalLLaMA (300K 订阅)

**标题**: SOMA — Local-first agent memory with ONNX embeddings, zero cloud dependencies

**正文**:
```
If you're running local LLMs and want agent memory that doesn't phone 
home, check out SOMA.

It uses BGE-small-zh (512d) via ONNX Runtime for embeddings — runs on 
CPU, ~100MB model download. SQLite for storage. No CUDA, no Docker, 
no PostgreSQL, no API keys needed (mock mode for testing).

Beyond just "local": it organizes memory around 7 thinking laws that 
decompose problems before retrieval. Self-evolution auto-tunes which 
thinking patterns to use based on past success. Memory consolidation 
merges similar entries. Active forgetting archives stale ones.

pip install soma-wisdom
python -m soma  # one-command verification

GitHub: https://github.com/sunyan999999/soma
```

## 中文社区帖子模板

### LINUX DO「公益推广」

**标题**: 分享一个AI Agent认知记忆框架 SOMA - 让Agent学会"思考"而不只是"记忆"

**正文**:
```
做了三个月的项目，刚发布了v0.7.0版本，来分享一下。

SOMA是一个开源的AI Agent认知框架。和其他记忆系统（Mem0、ChromaDB）不同的是，
它不是简单的"存向量→搜相似"，而是在记忆检索之前先用7条思维规律拆解问题。

说人话：普通记忆系统像硬盘（存和读），SOMA像思维框架（拆问题→多角度激活→自我进化）。

几个亮点：
- 零依赖：pip install soma-wisdom 搞定，ONNX本地跑embedding，不依赖任何外部服务
- 能自我进化：每次用完后记录反思，每5次会话自动调整7条规律的权重
- v0.7新增：记忆自动合并（相似度>85%的去重）+ 主动遗忘（艾宾浩斯衰减曲线）+ 外部知识导入
- 1752条真实生产数据验证，语义召回率100%，查询延迟<4ms
- 342项测试全通过，Apache 2.0协议

已在零熵智库生产环境稳定运行7天。

GitHub: https://github.com/sunyan999999/soma
PyPI: https://pypi.org/project/soma-wisdom/
文档: https://sunyan999999.github.io/soma/

代码和文档都有中英文版本，欢迎star和反馈。
```

### V2EX「分享创造」

**标题**: [分享创造] SOMA - 给AI Agent一个会思考的灵魂（开源认知框架）

**正文**:
```
前几个月在做一个AI编程助手（Glaude，Go写的类Claude Code），遇到一个问题：
Agent需要记忆，但市面上所有的记忆方案（Mem0、ChromaDB、LangChain Memory）
都只是"存储"，不是"思考"。

举个例子，Agent修复了一个N+1查询的bug，记录为记忆。下次遇到另一个性能问题时，
ChromaDB只能返回"这里有5条相似记忆"。但Agent需要的是——
"这个问题应该从系统思维还是第一性原理去拆解？"

所以做了SOMA。核心设计：
1. 7条思维规律组成推理网络（第一性原理、系统思维、矛盾分析、帕累托、逆向、类比、进化）
2. 问题来了先拆解→再激活相关规律→最后检索记忆（双向的，正向+反向视角）
3. 每次用完记录反思，自动调整规律权重（防止思维定式）

v0.7.0刚发布，1752条真实数据跑下来综合84.8分，语义召回100%。
pip install soma-wisdom 一行搞定，零外部依赖。

GitHub: github.com/sunyan999999/soma
欢迎试用和拍砖。
```
