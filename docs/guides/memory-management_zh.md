# 记忆管理与真实用量 —— 接入方的正式入口

*适用于 soma-wisdom >= 2.0.19*

「用户能看到并改掉 SOMA 记住了什么」这件事，此前没有正式接口。接入方只能这样拿数据：

```python
# 实际发生过的写法（某接入方的记忆管理页）
ep = soma._agent.memory.episodic
rows = ep._conn.execute(
    "SELECT id, content, importance FROM episodic_memories ORDER BY importance DESC LIMIT 20"
).fetchall()
```

三层私有属性穿透 + 一句裸 SQL。三个问题都是真的：

1. **没有作用域** —— SQL 里不写 `WHERE user_id = ?`，就把别人的记忆一起列出来了。
   云端多用户时这是越权，不是性能问题。
2. **锁死演进** —— 表结构是内部实现。外部一旦依赖 `episodic_memories.content`，
   改列名就是 breaking change，存储再也动不了。
3. **绕过一致性** —— 下面这段裸 SQL 改内容时，`content_hash` 和向量都留在旧值上：
   去重判断失准，语义搜索还在召回改前的内容。

```python
# 同样发生过（改记忆）
ep._conn.execute("UPDATE episodic_memories SET content=?, content_hash=? WHERE id=?", ...)
```

v2.0.19 把这些收成两个正式入口：**`soma.memories`**（记忆管理）与
**`soma.token_usage`**（真实用量）。

---

## 一、`soma.memories` —— 记忆管理

### 列举与翻页

```python
page = soma.memories.list(user_id="u1", limit=20)
for m in page["items"]:
    print(m["created_at"], m["nature"], m["importance"], m["content"][:40])

# 续翻：把上一页的游标原样传回
page2 = soma.memories.list(user_id="u1", limit=20, after=page["next_cursor"])
```

每条记忆的形状（字段白名单固定，内部字段加减不会破坏它）：

| 字段 | 含义 |
|------|------|
| `id` | 记忆 ID |
| `content` | 内容（`preview=N` 可截断，配合 `truncated` 判断） |
| `timestamp` / `created_at` | UTC 秒 / ISO 字符串，界面直接用后者 |
| `age_days` | 距今天数 |
| `importance` | 重要性 0-1 |
| `nature` | `state` / `fact` / `event`（见[记忆时效](memory-recency_zh.md)） |
| `is_stale` | 状态类记忆是否已过时效窗口 |
| `access_count` / `memory_type` / `context` | 访问次数 / 类型 / 上下文 |
| `user_id` / `session_id` / `agent_id` | 作用域三维 |

**游标而不是 OFFSET。** 管理页翻到第 20 页时若有人新增或删除记忆，`OFFSET` 会
错位（同一条重复出现，或整条被跳过）。这里用 `(排序键, id)` 复合游标：

```python
cursor = page["next_cursor"]        # 例如 "t:0x1.aad6b4269c3ebp+30:7068ab..."
page2 = soma.memories.list(user_id="u1", after=cursor)
```

游标带排序维度标记，**不能跨 `order_by` 复用** —— 拿 importance 页的游标去接
recent 页会抛 `ValueError`，而不是安静地返回错页。

两种排序：

```python
soma.memories.list(order_by="recent")       # 默认，按时间
soma.memories.list(order_by="importance")   # 「最重要的记忆」
```

### 单条读取 / 编辑

```python
m = soma.memories.get(memory_id, user_id="u1")   # 不属于该用户 -> None

soma.memories.update(memory_id, content="记错了，我其实是 2019 年毕业的")
soma.memories.update(memory_id, importance=0.9)
soma.memories.update(memory_id, nature="fact")
soma.memories.update(memory_id, context={"domain": "职业"})
```

改 `content` 会连带重算 `content_hash` 与语义向量（FTS5 由触发器自动同步）。
这是接口存在的核心理由 —— 裸 SQL 做不到这件事。

**越权改写返回 `not_found`，不是 `forbidden`。** 后者会泄露「这个 id 属于别人」
这一事实。

`importance` 超出 0-1 会被夹到边界；`nature` 非法值直接 `ValueError`；
一个字段都不传也报错（避免「调用成功但什么都没改」）。

### 删除与反悔

```python
soma.memories.delete(memory_id)             # 默认归档
soma.memories.archived(user_id="u1")        # 最近删除
soma.memories.restore(memory_id)            # 反悔
soma.memories.delete(memory_id, hard=True)  # 真删，不留归档
```

默认**归档而非硬删** —— 用户点错还能找回。恢复时连带重建向量：归档会把该条
向量清掉，只回插主表的话这条记忆语义搜索永远召不回，「恢复」就只恢复了半条。

新库还没跑过遗忘时归档表并不存在 —— `archived()` 返回空列表，不会抛错。

### 导出

```python
# 小库：直接拿列表
out = soma.memories.export_memories(user_id="u1")     # {"count", "items", ...}

# 大库：逐批写文件，不把整库读进内存
soma.memories.export_memories(user_id="u1", path="backup.jsonl")   # NDJSON，一行一条

# 流式遍历（迁移 / 同步）
for m in soma.memories.iter_memories(user_id="u1", batch=200):
    send(m)
```

26k 条记忆的库一次性 `list()` 出来是几百 MB —— 生成器逐批取是为了不再制造
v2.0.16/17 那笔内存债。

### 多租户必须显式传 `user_id`

约定与既有 `query_by_filters` 一致：**`user_id=""` 表示该维度不限**（单租户常态）。

```python
soma.memories.list()                  # 单租户：全库
soma.memories.list(user_id="u1")      # 多租户：必须这样写
```

多租户部署漏传 `user_id` 就是全库可见。这是接口能做的边界，代码层面挡不住
「忘了传」—— 部署时请把「所有记忆调用必须带 user_id」当作硬性检查。

---

## 二、`soma.token_usage` —— 真实用量

### 为什么不能按字符估

SOMA 此前不暴露 token usage，接入方的用量页只能按「字符数 / 2」估算。
估算值对不上 provider 账单，也就不能用于计费。

```python
snap = soma.token_usage
# {'calls': 12, 'prompt_tokens': 4120, 'completion_tokens': 980,
#  'total_tokens': 5100, 'estimated_calls': 0,
#  'by_model': {'deepseek-chat': {'calls': 12, 'total_tokens': 5100, ...}}}

recent = soma.recent_usage(20)     # 最近 20 次明细，最新在前
```

provider 返回的真实值原样记账。给不出 usage 时（自定义 base_url / 代理），
用字符估算兜底，并且**一定标 `estimated=True`**：

```python
snap["estimated_calls"]    # > 0 就是「有 N 次是估的」—— 这部分不能拿去计费
```

诚实标注是接口设计的一部分。用量页如果混着真数和估数不区分，就是在骗人。

### 上报计费系统

SOMA **不算钱、不管额度**（计费是独立项目），只负责把用量交出去：

```python
def on_usage(u):
    bill_client.report(u.to_dict())   # {prompt_tokens, model, user_id, estimated, ...}

soma.usage.on_usage(on_usage)
```

回调在锁外执行 —— 接入方回调里做慢事（发 HTTP）不会拖住并发线程；
回调抛异常也不会影响主链路。

### 三条已验证的行为

- **缓存命中不重复计费**。`_call_llm` 命中短时缓存时没有真实请求，不产生 token。
- **并发按用户归属**。多专家编排下 LLM 调用来自多个线程，`user_id` 走
  thread-local 上下文，6 线程并发各记各的账（已测）。
- **全 0 usage 视为缺失**。provider 回一串 0 不等于「这次免费」，
  会走估算兜底并标 `estimated=True`。

---

## 三、CLI

```bash
soma memories --user-id u1 -n 20                  # 列举
soma memories --user-id u1 --order importance      # 最重要的记忆
soma memories --id <ID> --user-id u1               # 看全文
soma memories --id <ID> --set-content "改后的" --user-id u1
soma forget <ID> --user-id u1                      # 删除（归档）
soma forget --list --user-id u1                    # 最近删除
soma forget --restore <ID>                         # 反悔
soma export --user-id u1 -o backup.jsonl           # 导出 NDJSON
soma usage                                         # 累计真实用量
soma usage --recent 20                             # 明细
```

所有子命令都支持 `--project <名字>` 做记忆库命名空间隔离（放在子命令之后）。

---

## 四、给已接入方的迁移对照

如果代码里有下面这些，请替换：

| 原来的写法 | 换成 |
|------------|------|
| `soma._agent.memory.episodic._conn.execute("SELECT ...")` | `soma.memories.list(...)` / `.get(id)` |
| `...episodic.delete(id)` | `soma.memories.delete(id)`（还能 `restore`） |
| `UPDATE episodic_memories SET content=...` | `soma.memories.update(id, content=...)` |
| 自己按字符算 token | `soma.token_usage` / `soma.usage.on_usage(cb)` |

穿透私有属性最贵的地方不是「不优雅」，而是**它让你以为自己拥有稳定性**，
直到某次升级才发现问题。上面这些路径已登记进
[API 稳定性承诺](../api_stability.md)，兼容至 1.0.0。

> 外部直接改库之后，已加载实例的 faiss 索引不会自动感知 —— 需要
> `soma.reload()`（v2.0.15）。走 `memories.update()` 就不必操心这件事。