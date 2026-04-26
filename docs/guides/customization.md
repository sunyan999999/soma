# Customization Guide

## Custom Wisdom Framework

Create your own `my_wisdom.yaml`:

```yaml
framework:
  name: "My Thinking Framework"
  version: "1.0.0"

  laws:
    - id: "first_principles"
      name: "First Principles"
      description: "Reduce to fundamentals, derive from base truths"
      weight: 0.90
      triggers: ["why", "essence", "fundamental", "root cause", "foundation"]
      relations: ["systems_thinking"]

    - id: "systems_thinking"
      name: "Systems Thinking"
      description: "See interconnected wholes, identify feedback loops"
      weight: 0.85
      triggers: ["system", "feedback", "loop", "interconnected", "whole", "structure"]
      relations: ["first_principles", "contradiction_analysis"]

    # Add your own laws...
    - id: "design_thinking"
      name: "Design Thinking"
      description: "Empathize, define, ideate, prototype, test"
      weight: 0.70
      triggers: ["user", "design", "empathy", "prototype", "experience"]
      relations: ["systems_thinking"]
```

Load it:

```python
from soma import SOMA

soma = SOMA(framework_config="my_wisdom.yaml")
```

### Law Properties

| Field | Required | Description |
|-------|:--:|------|
| `id` | yes | Unique identifier, snake_case |
| `name` | yes | Human-readable display name |
| `description` | yes | What this lens does and how to apply it |
| `weight` | yes | Starting weight (0.0–1.0), evolves over time |
| `triggers` | yes | Keywords that activate this law. Match against problem text. Include at least 5, ideally 10+ |
| `relations` | no | IDs of related laws. Used for graph traversal and cross-activation |

### Tips for Writing Good Triggers

- **Be specific but not too specific**: "feedback loop" is better than just "loop"
- **Include synonyms**: "bottleneck", "constraint", "limitation", "blocker"
- **Chinese + English**: If targeting Chinese users, include both: `["系统", "system", "整体", "whole"]`
- **Test against real problems**: Run `soma.decompose("your test problem")` and check which laws activate

---

## Switching Storage Backends

### Default: SQLite + FAISS

The zero-config default. Suitable for up to ~100K memories on a single machine.

### Custom Backend

Implement `BaseMemoryStore` (from `soma.abc`):

```python
from soma.abc import BaseMemoryStore
from soma.base import MemoryUnit
from typing import List

class RedisMemoryStore(BaseMemoryStore):
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        import redis
        self.client = redis.from_url(redis_url)

    def store(self, memory: MemoryUnit) -> str:
        # Serialize and store in Redis
        data = memory.model_dump_json()
        self.client.set(f"mem:{memory.id}", data)
        return memory.id

    def query(self, query_text: str, top_k: int = 10) -> List[MemoryUnit]:
        # Implement your retrieval logic
        # For production use, combine with a vector index
        keys = self.client.keys("mem:*")
        results = []
        for key in keys[:top_k]:
            data = self.client.get(key)
            results.append(MemoryUnit.model_validate_json(data))
        return results

    def delete(self, memory_id: str) -> bool:
        return bool(self.client.delete(f"mem:{memory_id}"))
```

### Switching Vector Stores

Implement `NumpyVectorIndex`-compatible interface:

```python
class PineconeVectorIndex:
    def __init__(self, api_key: str, environment: str):
        import pinecone
        pinecone.init(api_key=api_key, environment=environment)
        self.index = pinecone.Index("soma-memories")

    def add(self, vectors: np.ndarray, ids: List[str]):
        self.index.upsert(vectors=[(id, vec.tolist()) for id, vec in zip(ids, vectors)])

    def search(self, query: np.ndarray, k: int) -> tuple:
        results = self.index.query(vector=query.tolist(), top_k=k)
        ids = [m.id for m in results.matches]
        scores = [m.score for m in results.matches]
        return ids, scores
```

---

## Connecting LLMs

SOMA uses LiteLLM as the unified LLM interface. Any [LiteLLM-supported model](https://docs.litellm.ai/docs/providers) works.

### DeepSeek

```bash
export DEEPSEEK_API_KEY="your-key"
```

```python
soma = SOMA(llm="deepseek-chat")
```

### OpenAI

```bash
export OPENAI_API_KEY="your-key"
```

```python
soma = SOMA(llm="gpt-4o")
```

### Anthropic Claude

```bash
export ANTHROPIC_API_KEY="your-key"
```

```python
soma = SOMA(llm="claude-sonnet-4-20250514")
```

### Ollama (Local)

```bash
ollama pull llama3
```

```python
soma = SOMA(llm="ollama/llama3")
```

### Custom LLM

Implement `BaseLLM` (from `soma.abc`):

```python
from soma.abc import BaseLLM
from typing import Iterator

class MyCustomLLM(BaseLLM):
    def __init__(self, endpoint: str):
        self.endpoint = endpoint

    def complete(self, prompt: str) -> str:
        # Call your LLM endpoint
        response = requests.post(self.endpoint, json={"prompt": prompt})
        return response.json()["text"]

    def complete_stream(self, prompt: str) -> Iterator[str]:
        response = requests.post(self.endpoint, json={"prompt": prompt, "stream": True}, stream=True)
        for line in response.iter_lines():
            if line:
                yield json.loads(line)["delta"]
```

---

## Custom Embedding Models

### Default: ONNX fastembed

Ships with a bilingual Chinese-English model (~100 MB). No configuration needed.

### Switching Models

Pass a different fastembed model name:

```python
from soma.embedder import SOMAEmbedder
from soma.config import SOMAConfig
from pathlib import Path

config = SOMAConfig(
    framework_path=Path("wisdom_laws.yaml"),
    episodic_persist_dir=Path("soma_data"),
    use_vector_search=True,
)

# Override embedder with custom model
embedder = SOMAEmbedder(config, model_name="BAAI/bge-small-en-v1.5")
```

Available fastembed models: [fastembed documentation](https://qdrant.github.io/fastembed/)

### Custom Embedder

Implement `BaseEmbedder`:

```python
from soma.abc import BaseEmbedder
import numpy as np

class OpenAIEmbedder(BaseEmbedder):
    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def encode(self, text: str) -> np.ndarray:
        response = self.client.embeddings.create(model=self.model, input=text)
        return np.array(response.data[0].embedding, dtype=np.float32)

    def encode_batch(self, texts: List[str]) -> np.ndarray:
        response = self.client.embeddings.create(model=self.model, input=texts)
        return np.array([d.embedding for d in response.data], dtype=np.float32)
```

---

## Adjusting Evolution Behavior

### Manual Weight Control

```python
soma = SOMA()

# Check current weights
print(soma.get_weights())
# {"first_principles": 0.90, "systems_thinking": 0.85, ...}

# Manually adjust
soma.adjust_weight("pareto_principle", 0.82)

# Force evolution (bypass the 10-session counter)
soma.evolve()  # → ["pareto_principle: 0.75 → 0.77", ...]
```

### Disable Auto-Evolution

Override the respond method to skip the evolve step:

```python
class StaticSOMA(SOMA):
    def respond(self, problem: str) -> str:
        answer = self._agent.respond(problem)
        self._session_count += 1
        # Skip: self._agent.evolver.evolve()
        return answer
```

### Custom Evolution Rules

```python
from soma.evolve import MetaEvolver

class ConservativeEvolver(MetaEvolver):
    def evolve(self) -> list:
        changes = []
        for law_id, stats in self._calculate_stats().items():
            if stats["success_rate"] > 0.8:      # Higher bar: 80% → +1%
                new_w = min(0.98, stats["weight"] + 0.01)
            elif stats["success_rate"] < 0.3:    # Lower bar: 30% → -1%
                new_w = max(0.30, stats["weight"] - 0.01)
            else:
                continue
            self.engine.adjust_weight(law_id, new_w)
            changes.append(f"{law_id}: {stats['weight']:.2f} → {new_w:.2f}")
        return changes
```

---

## Plugin Registration (Planned)

Future versions will support Python entry_points for auto-discovery:

```python
# pyproject.toml of your plugin package
[project.entry-points."soma.frameworks"]
my_framework = "my_plugin:create_framework"

[project.entry-points."soma.stores"]
my_store = "my_plugin:create_store"
```

---

# 自定义指南

## 自定义思维框架

创建你的 `my_wisdom.yaml`：

```yaml
framework:
  name: "我的思维框架"
  version: "1.0.0"

  laws:
    - id: "first_principles"
      name: "第一性原理"
      description: "回归最基本要素，从底层逻辑推导"
      weight: 0.90
      triggers: ["为什么", "本质", "根本", "根源", "基础", "底层"]
      relations: ["systems_thinking"]

    - id: "systems_thinking"
      name: "系统思维"
      description: "视事物为相互关联的整体，识别反馈回路"
      weight: 0.85
      triggers: ["系统", "整体", "关联", "循环", "回路", "闭环", "全局", "结构"]
      relations: ["first_principles", "contradiction_analysis"]

    # 添加你自己的规律...
    - id: "design_thinking"
      name: "设计思维"
      description: "同理心、定义、构思、原型、测试"
      weight: 0.70
      triggers: ["用户", "设计", "同理心", "原型", "体验", "产品"]
      relations: ["systems_thinking"]
```

加载：

```python
from soma import SOMA

soma = SOMA(framework_config="my_wisdom.yaml")
```

### 规律属性

| 字段 | 必填 | 描述 |
|-------|:--:|------|
| `id` | 是 | 唯一标识，snake_case |
| `name` | 是 | 展示名称 |
| `description` | 是 | 这个透镜的作用和应用方式 |
| `weight` | 是 | 初始权重 (0.0–1.0)，会随时间进化 |
| `triggers` | 是 | 激活此规律的关键词。至少5个，建议10+ |
| `relations` | 否 | 关联规律的ID列表，用于图遍历和交叉激活 |

### 编写良好触发词的技巧

- **具体但不过于具体**: "反馈回路"比"回路"更好
- **包含同义词**: "瓶颈"、"约束"、"限制"、"卡点"
- **中英双语**: 面向中文用户时包含中英文: `["系统", "system", "整体", "whole"]`
- **用真实问题测试**: 运行 `soma.decompose("你的测试问题")` 检查哪些规律被激活

## 切换存储后端

### 默认: SQLite + FAISS

零配置默认方案。单机最多支持约 100K 记忆。

### 自定义后端

实现 `BaseMemoryStore`（来自 `soma.abc`）:

```python
from soma.abc import BaseMemoryStore
from soma.base import MemoryUnit
from typing import List

class RedisMemoryStore(BaseMemoryStore):
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        import redis
        self.client = redis.from_url(redis_url)

    def store(self, memory: MemoryUnit) -> str:
        data = memory.model_dump_json()
        self.client.set(f"mem:{memory.id}", data)
        return memory.id

    def query(self, query_text: str, top_k: int = 10) -> List[MemoryUnit]:
        keys = self.client.keys("mem:*")
        results = []
        for key in keys[:top_k]:
            data = self.client.get(key)
            results.append(MemoryUnit.model_validate_json(data))
        return results

    def delete(self, memory_id: str) -> bool:
        return bool(self.client.delete(f"mem:{memory_id}"))
```

## 接入 LLM

SOMA 使用 LiteLLM 作为统一 LLM 接口。任何 LiteLLM 支持的模型都可以。

### DeepSeek

```bash
export DEEPSEEK_API_KEY="your-key"
```

```python
soma = SOMA(llm="deepseek-chat")
```

### Ollama (本地)

```bash
ollama pull llama3
```

```python
soma = SOMA(llm="ollama/llama3")
```

## 自定义嵌入模型

实现 `BaseEmbedder`:

```python
from soma.abc import BaseEmbedder
import numpy as np

class OpenAIEmbedder(BaseEmbedder):
    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def encode(self, text: str) -> np.ndarray:
        response = self.client.embeddings.create(model=self.model, input=text)
        return np.array(response.data[0].embedding, dtype=np.float32)

    def encode_batch(self, texts: List[str]) -> np.ndarray:
        response = self.client.embeddings.create(model=self.model, input=texts)
        return np.array([d.embedding for d in response.data], dtype=np.float32)
```

## 调整进化行为

```python
soma = SOMA()

# 查看当前权重
print(soma.get_weights())

# 手动调整
soma.adjust_weight("pareto_principle", 0.82)

# 强制进化（绕过10次会话计数器）
soma.evolve()
```
