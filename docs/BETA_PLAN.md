# SOMA Beta 阶段开发计划

> 版本：v0.3.x → v0.4.0
> 创建：2026-04-30
> 状态：执行中

---

## Beta 阶段目标

从 AI 智能记忆库 → 生产可用、可度量、可推广的开源产品

---

## 一、基准测试 v2 — 数据量自适应评分

### 背景

当前 `soma/benchmarks.py` 的评分直接取平均值，没有归一化。在不同数据量下测试记忆容量的分数会"假降分"——10万条记忆时必然比1千条慢，但这不是系统的错。

### 方案

**数据量自适应归一化**：

```python
def _normalize_score(raw_value: float, data_count: int, metric: str) -> float:
    """根据数据量和指标类型归一化到 0-100"""
    if metric == "recall_speed_ms":
        # 搜索时间与 log(N) 成正比（B-tree索引），以此为基准
        # 归一化：实际时间 / O(log₂(N))
        expected = 10 * math.log2(max(data_count, 1) + 1)
        return max(0, min(100, (1 - (raw_value - expected) / expected) * 100))
    elif metric == "recall_precision":
        # 精准度不随数据量变化
        return raw_value * 100
    elif metric == "storage_efficiency":
        # 存储效率：每条的字节数
        expected = 2000  # 每条约2KB基准
        return max(0, min(100, (1 - (raw_value - expected) / expected) * 100))
    ...
```

**新增指标维度**：
- 数据量伸缩性：1K → 10K → 100K 时的查询延迟曲线
- FTS5 vs LIKE 加速比（当前应 > 20x）
- 记忆去重准确率
- 并发吞吐量（读/写 ops/s）

### 任务清单

- [ ] 改写 `soma/benchmarks.py` 的 `_calculate_scores()`
- [ ] 新增 `DataScale` 枚举（SMALL/MEDIUM/LARGE）
- [ ] 新增伸缩性维度 `scalability`
- [ ] CLI：`soma-bench run --scale medium --data-count 10000`
- [ ] Dashboard BenchmarkView 展示自适应评分历史

---

## 二、服务器性能调优

### 背景

SOMA 服务器 (47.94.149.121) 运行 uvicorn + FastAPI。当前问题：
- 多 worker 导致 WAL 文件冲突
- top_k / recall_threshold 未按数据量调整
- LLM 调用无重试机制

### 方案

**2.1 uvicorn 单 worker 配置**（WAL 兼容）

```bash
# 生产启动命令
uvicorn dash.server:app \
  --host 0.0.0.0 --port 8765 \
  --workers 1 \          # 单 worker 避免 WAL 冲突
  --limit-concurrency 20 \
  --timeout-keep-alive 30
```

**2.2 自适应 top_k / recall_threshold**

当前硬编码 top_k=5, recall_threshold=0.01。改进：
- 数据量 < 1000 时：top_k=3, threshold=0.05（少量数据需要更严格的过滤）
- 数据量 1K-10K 时：top_k=5, threshold=0.02
- 数据量 > 10K 时：top_k=8, threshold=0.01（大数据量放宽以捕获更多候选）

**2.3 LLM 请求重试**

```python
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=30))
async def call_llm_with_retry(prompt: str, provider) -> str:
    ...
```

**2.4 连接管理**
- SQLite PRAGMA 参数调优（cache_size, mmap_size, synchronous）
- 不活跃连接 30 分钟自动关闭

### 任务清单

- [ ] uvicorn 启动参数标准化（单 worker）
- [ ] `recall_threshold` 自适应调整逻辑
- [ ] LLM 请求 exponential backoff 重试
- [ ] SQLite PRAGMA 调优参数
- [ ] 连接池超时自动回收

---

## 三、开源推广

### 3.1 Awesome List 收录

**目标列表：**
- https://github.com/e2b-dev/awesome-ai-agents — 最大的 AI Agent 列表
- https://github.com/tensorchord/Awesome-LLMOps — LLM 运维工具
- https://github.com/steven2358/awesome-generative-ai — 生成式 AI

**PR 模板：**
```
# SOMA — Self-Organizing Memory Architecture

A wisdom-framework-driven memory system for AI agents.
7 philosophical laws (First Principles, Systems Thinking,
Contradiction Analysis...) guide memory recall with bidirectional
activation (semantic ×2 + keyword ×1), FTS5 full-text indexing,
and autonomous law discovery via DBSCAN clustering.

- GitHub: https://github.com/sunyan999999/soma
- PyPI: https://pypi.org/project/soma-wisdom/
- 100+ tests, 97% coverage, Python 3.10/3.11/3.12
```

### 3.2 技术文章大纲

**标题选择（3选1）：**

1. "AI Agent 记忆系统设计：从语义搜索到智慧框架驱动"
2. "SOMA：一个会反思自己思考方式的 AI 记忆架构"
3. "不只是 RAG —— 为什么 AI Agent 需要「智慧框架」而非「知识库」"

**结构：**
1. 问题：纯 RAG 的知识片段拼贴，缺乏结构化推理
2. 方案：7条思维规律驱动的双向激活机制
3. 实现：SQLite + FTS5 + FAISS 零依赖栈
4. 进化：自发现新规律的元认知闭环
5. 数据：100K记忆下 <10ms 查询，97% 测试覆盖率

**发布渠道：** 知乎、掘金、V2EX、Hacker News (Show HN)

### 3.3 演示 GIF/视频

**录制计划：**
1. CLI 演示：`python -m soma` 启动 → 输入问题 → 察看分析输出（15秒）
2. Dashboard 演示：打开浏览器 → 对话分析 → 展开可视化图表（30秒）
3. 基准对比：运行 benchmark → 查看对比图表（10秒）

**工具：** ScreenToGif (Windows) 或 terminalizer (CLI)

### 任务清单

- [ ] 提交 PR 到 awesome-ai-agents
- [ ] 提交 PR 到 Awesome-LLMOps
- [ ] 撰写技术文章（知乎/掘金/V2EX）
- [ ] 录制 CLI 演示 GIF
- [ ] 录制 Dashboard 演示 GIF
- [ ] Show HN 发布

---

## 四、SOMA ↔ Glaude 集成

### 背景

Glaude 是用 Go 实现的 AI Coding Agent（12 Phase 全部完成）。需要将 SOMA 作为其智慧记忆后端，让 Glaude 的每个开发会话都能自动存入 SOMA 并在后续会话中调取相关经验。

### 方案

**4.1 SOMA REST API 客户端（Go 实现）**

```go
// glaude/internal/soma/client.go
package soma

type Client struct {
    BaseURL    string
    APIKey     string
    HTTPClient *http.Client
}

func (c *Client) Remember(content string, context map[string]any, importance float64) (string, error)
func (c *Client) QueryMemory(query string, topK int) ([]MemoryUnit, error)
func (c *Client) Chat(problem string) (*ChatResponse, error)
func (c *Client) Stats() (map[string]int, error)
```

**4.2 Glaude MemoryStore 适配器**

```go
// glaude/internal/memory/soma_store.go
type SOMAStore struct {
    client *soma.Client
}

func (s *SOMAStore) Save(entry *MemoryEntry) error {
    // 将 Glaude 会话记忆推送到 SOMA
    _, err := s.client.Remember(entry.Content, map[string]any{
        "session_id": entry.SessionID,
        "type":       entry.Type, // "bug_fix", "refactor", "decision"
    }, entry.Importance)
    return err
}

func (s *SOMAStore) Search(query string, limit int) ([]*MemoryEntry, error) {
    // 从 SOMA 检索相关记忆
    units, err := s.client.QueryMemory(query, limit)
    ...
}
```

**4.3 Glaude SOMA Skill**

```markdown
---
name: soma-remember
description: 将当前会话的关键发现存入 SOMA 记忆库
allowedTools: [Bash]
---

/soma-remember <类型: bug_fix|decision|refactor|insight> <描述>
→ 调用 SOMA API 存储记忆，返回记忆 ID
```

```markdown
---
name: soma-recall
description: 从 SOMA 检索与当前任务相关的历史经验
allowedTools: [Bash]
---

/soma-recall <关键词>
→ 从 SOMA 双向激活检索相关记忆，展示在终端
```

**4.4 自动记录策略**

Glaude 在以下时机自动向 SOMA 记录：
- `post_tool_execute` Hook → 工具执行完成后记录关键操作
- `post_agent_response` Hook → Agent 响应完成后记录决策
- 用户显式 `/soma-remember` → 手动记录

### 任务清单

- [ ] Go 实现 SOMA REST API 客户端 (`soma.Client`)
- [ ] 实现 `SOMAStore` 适配器（实现 Glaude `MemoryStore` 接口）
- [ ] 实现 `/soma-remember` Skill（SkillTool 注册）
- [ ] 实现 `/soma-recall` Skill
- [ ] 注册 Hook：post_tool_execute / post_agent_response 自动推送到 SOMA
- [ ] 集成测试：Glaude 开发会话 → SOMA 记忆存储 → 下次会话召回

---

## 五、执行顺序

| 阶段 | 任务 | 预估 | 并行？ |
|------|------|:--:|:--:|
| **现在** | Alpha 收尾边界测试 | ✅ 完成 | — |
| **现在** | 起草 Beta 计划（本文件） | ✅ 完成 | — |
| **第1步** | 基准测试 v2 — 自适应评分 | 4h | 独立 |
| **第2步** | 服务器性能调优 | 2h | 可并行 |
| **第3步** | SOMA ↔ Glaude 集成 | 5h | 可并行 |
| **第4步** | 开源推广 — PR/文章/GIF | 3h | 可并行 |

---

## 六、Beta 结束里程碑

达成以下全部条件后进入 v0.4.0：

- [ ] 基准测试自适应评分上线 Dashboard
- [ ] 生产服务器单 worker + 重试策略稳定运行 7 天
- [ ] awesome-ai-agents PR 被合并
- [ ] 至少 1 篇技术文章发布
- [ ] Glaude 开发会话自动存入 SOMA，召回率 > 60%
- [ ] v0.3.2b1 发布到 PyPI
