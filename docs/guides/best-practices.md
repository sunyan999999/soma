# Best Practices

This guide covers patterns that make SOMA work well in production. It draws from real usage across 14 PyPI releases and 1,600+ total downloads.

---

## 1. When to Choose SOMA

**SOMA fits when:**

- You need memory that self-organizes over time, not just append-only chat history
- Your use case spans many sessions where cross-session context matters
- You want the system to detect its own cognitive biases (frame anchoring)
- Multiple domain experts should collaborate on the same problem

**Plain RAG fits when:**

- You need simple FAQ lookup from a static document set
- Latency budget is under 20ms and you cannot afford the wisdom pipeline (~200ms)
- You have no need for memory evolution or multi-session context

---

## 2. Memory Organization

### Episodic Memory (L1): The Raw Feed

Store every meaningful interaction. Don't over-filter — SOMA's L2/L3 layers work better with more raw material.

```python
# Good: store with rich context
soma.remember(
    "用户询问了微服务拆分的具体策略，讨论了按领域拆分vs按团队拆分",
    context={"domain": "architecture", "topic": "microservices", "decision_pending": True},
    importance=0.8
)

# Avoid: context-free one-liners
soma.remember("user asked about microservices", context={}, importance=0.5)
```

Context keys matter. Consistent keys (`domain`, `topic`, `decision_pending`) make L2 scene aggregation produce coherent themes.

### Semantic Memory: The Knowledge Graph

Triples should be concrete and falsifiable:

```python
# Good
soma.remember_semantic("微服务拆分", "首选策略", "按业务领域边界", confidence=0.9)
soma.remember_semantic("按团队拆分", "适用于", "团队技能高度分化的场景", confidence=0.7)

# Avoid: vague or unfalsifiable
soma.remember_semantic("架构", "是", "重要的", confidence=1.0)
```

### L2 Scene & L3 Profile: Let the Machine Work

Enable auto-capture, then let it run. Don't micromanage scene extraction — the warmup mechanism exists precisely so you don't have to tune it.

```python
config = SOMAConfig(
    scene_extraction_enabled=True,
    profile_extraction_enabled=True,
    scene_extraction_warmup=5,    # Start extracting after 5 memories
)
```

The only parameter worth tuning: increase `scene_extraction_warmup` if your first few memories are unrepresentative (e.g., test data).

---

## 3. Wisdom Framework Tuning

### Start with Default Weights

The 7 default laws ship with weights calibrated on 1,050 production memories. Run at least 50 sessions before manual tuning — let the evolver do its job first.

### When to Intervene

```python
# Check if a law is over/under-active
foci = soma.decompose("your typical problem type")
for f in foci:
    print(f"{f.law_id}: weight={f.weight:.2f}, rationale={f.rationale}")
```

Adjust only when a law consistently fires when it shouldn't (or never fires when it should):

```python
# Dial down over-active law
soma.adjust_weight("pareto_principle", 0.55)  # Was 0.75, fires too often

# Boost under-used law
soma.adjust_weight("inversion", 0.80)  # Was 0.65, rarely activates
```

### Custom Laws for Domain-Specific Work

If your use case sits entirely in one domain (e.g., medical diagnosis, legal analysis), add 2-3 domain laws:

```yaml
- id: "differential_diagnosis"
  name: "鉴别诊断"
  description: "系统排除替代解释，评估概率而非确定性"
  weight: 0.85
  triggers: ["症状", "诊断", "鉴别", "排除", "可能性", "概率", "假阳性"]
  relations: ["first_principles", "contradiction_analysis"]
```

Keep total laws under 12 — more than that diffuses activation scores and hurts recall quality.

---

## 4. Multi-Agent Setup Patterns

### Pattern A: Specialist Panel (3-5 agents)

Best for problems that benefit from multiple perspectives on the same question.

```python
soma = SOMA(orchestration_mode="multi", orchestration_top_k=3, orchestration_consensus="voting")

soma.register_expert("business", ["商业分析", "战略", "市场"], "商业战略分析师")
soma.register_expert("tech", ["技术架构", "工程", "性能"], "技术架构师")
soma.register_expert("ux", ["用户体验", "设计", "交互"], "UX研究员")

# All three will weigh in, voting produces the consensus
result = soma.solve_multi("新功能应该优先移动端还是Web端？")
```

Use `voting` for fast decisions (zero LLM cost for consensus), `llm_arbitration` for nuanced topics.

### Pattern B: Single Expert + Generalist Fallback

Best for mixed workloads where most questions are domain-specific but some are general.

```python
soma.register_expert("code_reviewer", ["代码审查", "安全", "性能优化"])
soma.register_expert("general", ["通用"], is_default=True)

# Domain questions → code_reviewer
# Everything else → general (fallback)
```

### When NOT to Use Multi-Agent

Single problems that don't benefit from multiple perspectives. A "what is 2+2" question doesn't need a consensus protocol. Use `orchestration_mode="single"` for simple factual queries.

---

## 5. Performance

### Current Baseline

| Operation | Latency |
|-----------|---------|
| Memory store (episodic) | ~2ms |
| Memory recall (simple, no LLM) | ~30ms |
| Full respond() pipeline | ~209ms |
| Scene extraction (per cycle) | ~500ms |
| Profile update (per cycle) | ~300ms |

### Optimization Tips

1. **Batch semantic triples**: Store 10-50 triples at once rather than one at a time — each call acquires a write lock.
2. **WAL mode is default**: SQLite WAL mode is enabled. Don't change it.
3. **Disable features you don't use**: `causal_extraction=False`, `enable_frame_detection=False`, `scene_extraction_enabled=False` save ~100ms each when off.
4. **Use CPU embedder**: ONNX on CPU is 2-5x faster than calling an external embedding API for small batches.

### Scaling Beyond 100K Memories

The current SQLite+FAISS backend performs well to ~100K memories. Beyond that:

1. Shard by `user_id` — each user gets their own SQLite file
2. Switch to an external vector store (see customization guide)
3. Consider periodic archival of cold memories (importance < 0.2, older than 90 days)

---

## 6. Security

### API Key Management

Never hardcode API keys. Use environment variables:

```python
# Good
soma = SOMA(llm="deepseek-chat")  # reads DEEPSEEK_API_KEY from env

# The config field llm_api_key exists for programmatic setups
# but prefer env vars for production
```

### Data Isolation

Each `persist_dir` is a self-contained SQLite+FAISS database. Use separate directories for separate projects or users:

```python
project_a = SOMA(persist_dir="soma_data/project_a")
project_b = SOMA(persist_dir="soma_data/project_b")
# project_a.query_memory("...") never returns project_b data
```

### Memory Deletion

SOMA supports surgical deletion:

```python
# Delete a specific memory
soma._agent.memory_core.delete(memory_id)

# Delete by user (GDPR right-to-erasure)
for mem in soma._agent.memory_core.query_by_user(user_id):
    soma._agent.memory_core.delete(mem.id)
```

---

## 7. Observability

### Stats Endpoint

```python
stats = soma.stats
# {"episodic": 1050, "semantic": 234, "skills": 12, "indexed_vectors": 1050}
```

Monitor `episodic` growth rate. If it exceeds 500/day for a single user, consider enabling scene extraction to compress.

### Reasoning Inspection

After each `chat()`, inspect the reasoning chain:

```python
result = soma.chat("如何提升团队效率？")
for block in result.get("reasoning", []):
    print(f"[{block['dimension']}] {block['hypothesis']}")
    print(f"  证据: {block['evidence']}")
    print(f"  反证: {block['counter_evidence']}")
```

### Evolution Audit Trail

```python
# View weight change history
changes = soma.evolve()
for change in changes:
    print(change)  # "pareto_principle: 0.75 → 0.77"
```

---

# 最佳实践

## 1. 何时选择 SOMA

**SOMA 适合：**

- 需要记忆随时间自组织的场景，而非简单的聊天记录堆积
- 跨会话上下文重要的场景
- 希望系统检测自身认知偏差（框架锚定）
- 需要多个领域专家协作解决同一问题

**传统 RAG 适合：**

- 静态文档集的简单 FAQ 查找
- 延迟预算低于 20ms，不能接受智慧管道 (~200ms)
- 不需要记忆演化或跨会话上下文

## 2. 记忆组织

### 情节记忆 (L1)：原始素材

存储每次有意义的交互。不要过度过滤——SOMA 的 L2/L3 层需要充足的原始素材。

```python
# 好的做法：带丰富上下文
soma.remember(
    "用户询问了微服务拆分的具体策略，讨论了按领域拆分vs按团队拆分",
    context={"domain": "architecture", "topic": "microservices", "decision_pending": True},
    importance=0.8
)
```

### 语义记忆：知识图谱

三元组应该具体且可证伪。一致性高的 key 让 L2 场景聚合产生连贯的主题。

### L2 场景 & L3 画像：让机器自己工作

开启自动捕获，然后让它运行。不要微调场景提取——warmup 机制的存在就是为了让你不必手动调整。

## 3. 思维框架调优

50 次会话后再考虑手动调权重。让进化机制先发挥作用。

## 4. 多Agent模式

- **专家面板模式**（3-5个Agent）：同一问题多视角
- **单专家+通用回退**：混合工作负载
- **简单问题不需要多Agent**："2+2等于几"不需要共识协议

## 5. 性能

当前基线：存储 ~2ms，简单召回 ~30ms，完整管道 ~209ms。

关闭不用的功能（因果抽取、框架检测、场景提取）每个节省 ~100ms。

## 6. 安全

- 永远不硬编码 API Key，用环境变量
- 不同项目/用户用不同 `persist_dir` 隔离数据
- 支持精确删除单条记忆（GDPR 合规）

## 7. 可观测性

监控 `soma.stats`、检查推理链 (`chat()` 的 `reasoning` 字段)、审计进化轨迹 (`evolve()`)。
