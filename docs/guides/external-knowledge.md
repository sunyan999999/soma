# SOMA 外部知识集成指南 / External Knowledge Ingestion Guide

> v2.0.9+ | 来源可信度 + 内容质量 + 事实印证 + 严格度过滤，让外部知识安全进入记忆库。

## 背景 / Background

SOMA 的外部知识门控（`KnowledgeGate`）是一条**多层质量过滤管道**，外部内容（Web / RAG / 文档）必须通过全部过滤层才能进入记忆库，避免低质、错误、营销内容污染记忆。

```
层0 来源可信度 → 层1 相关性 → 层2 SOMA推理消化 → 层2.5 内容质量
  → 层3 风格对齐 → 层4 一致性校验 → 层4.5 事实印证 → 分级存储
```

判定结果三类：**accepted**（接受入库）/ **quarantined**（隔离，需人工确认）/ **rejected**（拒绝）。

## 一、使用方式 / Usage

### CLI（一条命令）

```bash
# 让 SOMA 从外部文本学习，自动过全部过滤层
soma learn "外部文本内容" -c "当前主题" --strictness balanced

# 严格模式（质量/印证要求更高，孤立事实会降级）
soma learn "外部文本" -c "主题" --strictness strict

# 宽松模式（接受更多）
soma learn "外部文本" -c "主题" --strictness permissive
```

参数：
- `-c, --context`：问题上下文（用于相关性判断）。**建议用能体现主题的完整短语**，过短可能导致相关性过滤误拒（v2.0.9 已做弱 context 回退，但完整主题更准确）
- `-s, --source`：来源标识 `web / document / rag / manual`
- `--strictness`：严格度档位，默认 balanced

### Python API

```python
from soma import SOMA
soma = SOMA()  # 默认 balanced

result = soma.learn_from_external(
    ["外部文本1", "外部文本2"],
    problem_context="零熵智库的系统分析方法论",
    source_name="web",
    strictness="balanced",   # 可选，空则用 SOMAConfig 默认
)
print(f"接受 {len(result.accepted)}，隔离 {len(result.quarantined)}，拒绝 {len(result.rejected)}")

# 查看接受率
print(f"接受率: {result.acceptance_rate}")
```

### URL 导入（自动校验来源可信度）

```python
from soma.memory.external import URLSource, FileSource, ExternalKnowledgeImporter

# URL 抓取（自动过来源可信度校验，黑名单域名拒绝）
source = URLSource("https://github.com/xxx/article", trust=None)
# trust=None 用默认白/黑名单；也可传自定义 SourceTrust
importer = ExternalKnowledgeImporter(soma._agent.memory.episodic)
importer.import_source(source)

# 文件导入（.md/.txt/.json）
file_src = FileSource("docs/notes.md")
importer.import_source(file_src)
```

## 二、配置 / Configuration

### 严格度档位（strict / balanced / permissive）

| 档位 | min_quality | min_corroboration | 适用场景 |
|------|------------|-------------------|---------|
| **permissive** | 默认 -0.15 | 0.0 | 内容收集早期，宁多勿漏 |
| **balanced** | 0.40 | 0.0 | 默认，常规知识入库 |
| **strict** | 默认 +0.15 | 0.2 | 生产知识库，宁缺毋滥 |

### SOMAConfig 全局配置（v2.0.9+）

```python
from soma import SOMA
soma = SOMA(
    # 知识门控配置组
    # （通过 config 字段，见下方「源码级配置」）
)
```

源码级（`SOMAConfig` 字段）：
```python
knowledge_gate_strictness = "balanced"   # strict | balanced | permissive
knowledge_gate_min_quality = 0.40        # 内容质量最低阈值
knowledge_gate_min_corroboration = 0.0   # 事实印证最低阈值
```

### 自定义来源白/黑名单

```python
from soma.source_trust import SourceTrust, SourceTrustConfig

cfg = SourceTrustConfig(
    whitelist={"my-corp.com": 0.95, "docs.example.org": 0.9},  # 高可信域名
    blacklist={"ads-spam.com", "fake-news.net"},                # 拒绝域名
    default_score=0.5,                                          # 未知域名默认分
)
from soma.knowledge_gate import KnowledgeGate
gate = KnowledgeGate(soma._agent, trust_config=cfg)
```

### 可选 LLM 质量增强

有 LLM key（`llm_api_key` 或非 mock 模型）时，`ingest` 自动用 LLM 对内容质量/事实合理性二次评估（与本地启发式各占 50%）；无 key 时纯本地启发式兜底。**无需额外配置，自动探测。**

## 三、过滤层说明 / Filter Layers

| 层 | 能力 | 默认阈值 | 说明 |
|----|------|---------|------|
| 0 | 来源可信度 | 黑名单拒绝 | 域名白/黑名单 + 信誉分 |
| 1 | 相关性 | 命中 ≥2 关键词 | 内容与问题上下文匹配度 |
| 2 | SOMA 推理消化 | ≥1 个观点 | 7 规律拆解外部内容 |
| 2.5 | 内容质量 | ≥0.40 | 信息密度/重复率/营销词/空话/噪音 |
| 3 | 风格对齐 | ≥0.30 | 与记忆库高重要性记忆风格匹配 |
| 4 | 一致性校验 | 冲突 ≤2 | 与已有语义三元组矛盾检测 |
| 4.5 | 事实印证 | ≥0.0 (balanced) | 与已有记忆交叉验证，孤立事实降级（strict） |

## 四、验证 / Verification

```bash
# 正常知识应 accepted
soma learn "系统分析方法论强调从全局视角理解要素关联，识别反馈回路，这是复杂问题分析的核心框架。" -c "系统分析"

# 营销内容应 rejected
soma learn "限时抢购！全场五折！立即点击购买！免费红包！" --strictness strict -c "商业促销"

# 黑名单来源应 rejected
soma learn "内容" --strictness strict -c "主题"
# （配合 source_url 场景：URLSource 或 ingest(source_url=...)）
```

## 五、注意事项 / Notes

1. **`-c` context 用完整主题短语**：过短（如「哲学思维」）可能让相关性过滤误拒；v2.0.9 已做「弱 context 回退用内容拆解」，但完整主题最稳。
2. **来源 URL 校验**：`learn_from_external` 传 `source_url` 或 `URLSource` 会自动过层0；纯文本无 URL 则跳过层0。
3. **孤立事实降级**：balanced 模式默认不强制印证（min_corroboration=0.0），strict 模式才强制（0.2），避免普通内容因无印证被误隔离。
4. **LLM 增强是自动的**：有 key 自动用，无 key 纯本地，不改变 API。
