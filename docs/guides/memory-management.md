# Memory Management & Real Token Usage — The Integrator's Entry Point

*For soma-wisdom >= 2.0.19*

Until now there was no official way to let users see and correct what SOMA
remembers about them. Integrators had to reach through private layers:

```python
# What an integrator's memory-management page actually did
ep = soma._agent.memory.episodic
rows = ep._conn.execute(
    "SELECT id, content, importance FROM episodic_memories ORDER BY importance DESC LIMIT 20"
).fetchall()
```

Three private attribute hops plus raw SQL. All three problems were real:

1. **No scoping** — a SQL string without `WHERE user_id = ?` lists other
   users' memories too. In a multi-tenant cloud deployment that is a privilege
   escalation, not a performance nit.
2. **Frozen evolution** — the schema is an implementation detail. Once external
   code depends on `episodic_memories.content`, renaming a column becomes a
   breaking change.
3. **Consistency bypassed** — raw-SQL content edits leave `content_hash` and the
   embedding vector stale: dedup goes wrong and semantic search keeps returning
   the pre-edit text.

v2.0.19 turns these into two first-class entry points: **`soma.memories`** and
**`soma.token_usage`**.

---

## 1. `soma.memories`

### Listing and paging

```python
page = soma.memories.list(user_id="u1", limit=20)
for m in page["items"]:
    print(m["created_at"], m["nature"], m["importance"], m["content"][:40])

page2 = soma.memories.list(user_id="u1", limit=20, after=page["next_cursor"])
```

Each item is a fixed field whitelist — adding or removing internal columns
cannot break it: `id`, `content` (truncated with `preview=N`, see `truncated`),
`timestamp`/`created_at`, `age_days`, `importance`, `nature`, `is_stale`, `access_count`,
`memory_type`, `context`, and the three scope fields `user_id`/`session_id`/`agent_id`.

**Keyset cursor, not OFFSET.** Paging to page 20 while someone inserts or
deletes a memory shifts every OFFSET page (duplicates or skipped rows). The
cursor encodes `(sort key, id)` and carries its sort dimension — reusing an
`order_by="importance"` cursor on a `recent` page raises `ValueError` rather
than silently returning the wrong page.

```python
soma.memories.list(order_by="recent")       # default
soma.memories.list(order_by="importance")   # "most important memories" view
```

### Read one / edit

```python
m = soma.memories.get(memory_id, user_id="u1")   # None if not owned by u1

soma.memories.update(memory_id, content="Actually I graduated in 2019")
soma.memories.update(memory_id, importance=0.9)
soma.memories.update(memory_id, nature="fact")
```

Editing `content` recomputes `content_hash` and re-embeds the vector (FTS5 syncs via
trigger). That is the core reason the interface exists — raw SQL cannot do it.

Cross-user writes return `not_found`, not `forbidden` — the latter leaks that the
id belongs to someone else. `importance` is clamped to 0-1; an invalid `nature`
raises; calling with no fields raises (no silent no-op).

### Delete and undo

```python
soma.memories.delete(memory_id)             # archived by default
soma.memories.archived(user_id="u1")        # recently deleted
soma.memories.restore(memory_id)            # undo
soma.memories.delete(memory_id, hard=True)  # real delete
```

Delete archives rather than destroys, so a misclick is recoverable. Restore
re-embeds the vector: archiving clears it, and re-inserting the row alone would
leave a memory semantic search can never recall again.

On a fresh store the archive table does not exist yet — `archived()` returns
an empty list instead of raising.

### Export

```python
out = soma.memories.export_memories(user_id="u1")           # in-memory list
soma.memories.export_memories(user_id="u1", path="b.jsonl")  # NDJSON, streamed
for m in soma.memories.iter_memories(user_id="u1", batch=200):
    send(m)                                                  # migration / sync
```

`iter_memories` streams in batches — materialising 26k memories at once costs
hundreds of MB, exactly the debt v2.0.16/17 paid down.

### Multi-tenancy: pass `user_id` explicitly

Same convention as `query_by_filters`: an empty `user_id` means *no filter*
(single-tenant norm). In multi-tenant deployments forgetting to pass it exposes
the whole library — treat "every memory call carries user_id" as a hard review
gate; no API can catch the omission for you.

---

## 2. `soma.token_usage` — real usage, not character estimates

SOMA previously exposed no token usage, so integrators estimated with
"chars / 2". Estimates cannot back billing — they do not match provider
invoices.

```python
snap = soma.token_usage
# {'calls': 12, 'prompt_tokens': 4120, 'completion_tokens': 980,
#  'total_tokens': 5100, 'estimated_calls': 0,
#  'by_model': {'deepseek-chat': {...}}}

recent = soma.recent_usage(20)   # newest first, per-call detail
```

Provider values are recorded verbatim. When a response carries no usage
(custom base_url / proxies), the record falls back to a character estimate and
is **always flagged `estimated=True`**:

```python
snap["estimated_calls"] > 0   # N calls were estimated — never bill these
```

Honest labelling is part of the design. A usage page that mixes real and
estimated numbers without distinguishing them is lying to the user.

### Reporting to your billing system

SOMA does not price anything and manages no quotas (billing is a separate
project). It only hands usage over:

```python
def on_usage(u):
    bill_client.report(u.to_dict())   # {prompt_tokens, model, user_id, estimated, ...}

soma.usage.on_usage(on_usage)
```

Callbacks run outside the lock — a slow HTTP callback cannot stall concurrent
threads — and callback exceptions never break the main path.

### Verified behaviours

- **Cache hits are not billed.** A `_call_llm` short-cache hit means no request
  went out, so zero tokens are recorded.
- **Concurrent calls attribute per user.** Under multi-expert orchestration
  LLM calls come from many threads; `user_id` travels via thread-local context
  (6-thread test shows no cross-attribution).
- **All-zero usage counts as missing.** A provider returning zeros is treated
  as "no real usage" and falls back to the flagged estimate.

---

## 3. CLI

```bash
soma memories --user-id u1 -n 20                # list
soma memories --user-id u1 --order importance   # most important
soma memories --id <ID> --user-id u1            # full record
soma memories --id <ID> --set-content "fixed" --user-id u1
soma forget <ID> --user-id u1                   # delete (archived)
soma forget --list --user-id u1                 # recently deleted
soma forget --restore <ID>                      # undo
soma export --user-id u1 -o backup.jsonl        # NDJSON export
soma usage                                      # cumulative real usage
soma usage --recent 20                          # per-call detail
```

Every subcommand accepts `--project <name>` (after the subcommand) for store
namespacing.

---

## 4. Migration table for existing integrators

| Before | Now |
|--------|-----|
| `soma._agent.memory.episodic._conn.execute("SELECT ...")` | `soma.memories.list(...)` / `.get(id)` |
| `...episodic.delete(id)` | `soma.memories.delete(id)` (restorable) |
| `UPDATE episodic_memories SET content=...` | `soma.memories.update(id, content=...)` |
| char/2 token guessing | `soma.token_usage` / `soma.usage.on_usage(cb)` |

Reaching through private attributes is expensive not because it is inelegant,
but because **it feels stable right up until an upgrade proves otherwise**.
These interfaces are registered in [API stability](../api_stability.md) with
compatibility guaranteed through 1.0.0.

> External writes to the database are not picked up by a loaded instance's
> faiss index — call `soma.reload()` (v2.0.15). Going through
> `memories.update()` makes that a non-issue.