# SOMA: Wisdom over Memory

Most AI memory systems treat memory as passive storage — store everything, retrieve by similarity, hope it's relevant. This is the "high-IQ archive clerk" model: impressive recall, no framework for understanding what matters and why.

SOMA inverts this paradigm. Instead of asking "what stored knowledge is similar to this query?", it asks a deeper question: **"What thinking patterns does this problem activate, and what memories become relevant under those patterns?"**

At its core sits an explicit wisdom framework — seven thinking laws drawn from cognitive science and strategic reasoning: First Principles (regress to fundamentals), Systems Thinking (map interconnections), Contradiction Analysis (surface hidden tensions), Pareto Principle (find the critical few), Inversion (reason backwards), Analogical Reasoning (bridge domains), and Evolutionary Lens (track what adapts). Each law carries weighted keyword triggers and defined inter-relationships. When a problem arrives, SOMA decomposes it through these lenses, identifying which dimensions of thought apply and why — then assembles a structured prompt that guides the LLM rather than merely feeding it context.

This decomposition drives **bidirectional activation**. Rather than one-directional similarity search, SOMA computes the associative potential between each analysis focus and each stored memory — producing a ranked set of truly relevant knowledge, not just keyword-matched text. The framework acts as the index; memory supplies the substance.

The four-stage pipeline — Decompose, Activate, Synthesize, Evolve — runs with every query. After synthesis, SOMA reflects on which memories proved useful and adjusts law weights over time. Laws that consistently generate insight grow stronger; underused ones naturally fade. A law discovery module can even propose new thinking patterns from high-cohesion memory clusters, subject to human approval.

Built as a lightweight Python library with zero mandatory dependencies beyond the standard library, SOMA integrates in five minutes via pip. It ships with a REST API for remote access, a Vue.js dashboard for visual management, native LangChain tooling, and dual memory stores — episodic for experiences and semantic for knowledge triples — with optional vector search for cross-lingual semantic recall. The architecture is fully mockable: every LLM-dependent component accepts an interface, making it trivial to test without API calls. All 139 tests pass at 97% coverage. Zero API keys in the repository.

**Not "make AI remember more." Make AI understand deeper.**

---

# SOMA：智慧超越记忆

大多数 AI 记忆系统将记忆视为被动存储——存储一切，按相似度检索，希望它相关。这是"高智商档案管理员"模型：令人印象深刻的回忆能力，但没有框架来理解什么重要、为什么重要。

SOMA 颠覆了这一范式。它不问"什么存储的知识与这个查询相似？"，而是问一个更深层的问题：**"这个问题激活了哪些思维模式，在这些模式下哪些记忆变得相关？"**

其核心是一个显式的智慧框架——七条源自认知科学和战略推理的思维规律：第一性原理（回归最基本要素）、系统思维（映射相互关联）、矛盾分析（揭示隐藏的张力）、二八法则（找到关键的少数）、逆向思考（从结果反向推理）、类比推理（跨领域映射）、进化视角（追踪什么在适应）。每条规律都带有加权关键词触发器和明确的相互关系。当问题到来时，SOMA 通过这些视角拆解问题，识别哪些思维维度适用以及为什么——然后组装一个结构化提示，引导 LLM 而不仅仅是向其提供上下文。

这种拆解驱动了**双向激活**。不是单向的相似性搜索，SOMA 计算每个分析焦点与每个存储记忆之间的关联潜力——产生真正相关知识的排序集合，而不仅仅是关键词匹配的文本。框架充当索引；记忆提供内容。

四阶段管道——拆解、激活、合成、进化——在每个查询中运行。合成之后，SOMA 反思哪些记忆被证明有用，并随时间调整规律权重。持续产生洞察的规律自然增强；未被充分利用的规律逐渐衰减。规律发现模块甚至可以从高内聚的记忆簇中提出新的思维模式，需经人类审批。

作为零强制依赖的轻量级 Python 库，SOMA 通过 pip 五分钟即可集成。它提供 REST API 用于远程访问、Vue.js 仪表盘用于可视化管理、原生 LangChain 工具支持，以及双重记忆存储——用于经验的情景记忆和用于知识三元组的语义记忆——可选向量搜索用于跨语言语义召回。架构完全可模拟：每个依赖 LLM 的组件都接受接口，使得无需 API 调用即可轻松测试。全部测试通过，仓库中零 API 密钥。

**不是"让 AI 记住更多"。是让 AI 理解更深。**
