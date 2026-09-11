# Memory Recency — The Three Mechanisms, and Which One to Rely On

*Applies to soma-wisdom ≥ 2.0.15*

If you inject memories into an LLM prompt, the hardest failure to notice is **the model
treating an old state as a current one**:

> User (3 months ago): "I've been sleeping badly."
> LLM today: "Since you've been sleeping badly, here's some advice…" ← wrong, that's stale

SOMA has three separate mechanisms that address this. They are **not** three layers of the
same defense — they operate at different stages and one of them is a backstop, not the
front line. Getting this wrong leads to the wrong integration. This page is the map.

## The three mechanisms

| # | Mechanism | Where it acts | Effect |
|---|-----------|---------------|--------|
| 1 | **Recency decay** `exp(-days/7)` | Scoring, before the activation threshold | Old memories score lower and *fall out of recall entirely* |
| 2 | **`max_age_days`** | Query-time hard filter | "Only give me memories from the last N days" |
| 3 | **`is_stale`** (nature=`state` only) | `explain_activation` output, after recall | Flags a recalled state memory as possibly outdated |

### 1. Recency decay — the actual front line

Every memory's activation score is multiplied by an exponential decay with a **7-day half-life**:

| Age | Weight |
|-----|--------|
| 0d | 1.00 |
| 3d | 0.65 |
| 7d | 0.37 |
| 14d | 0.14 |
| 30d | 0.014 |
| 40d | **0.003** |

**This is what actually keeps old memories out.** By 30 days a memory retains under 2% of its
weight — far below SOMA's default activation threshold. A 40-day-old memory does not get
recalled "with a low score"; it does not get recalled **at all**, even at importance 0.95.

> **Consequence:** if you were planning to rely on `is_stale` to catch old state memories,
> it will almost never fire for memories older than 30 days — decay already removed them.
> `is_stale` is a backstop, not the main defense.

### 2. `max_age_days` — explicit window, when you want one

Decay is a soft, score-based mechanism. When you want a hard cut — "I only want things from
this month" — pass `max_age_days`:

```python
from soma import SOMA

soma = SOMA()

# Only memories from the last 30 days; older ones are filtered out entirely
results = soma.query_memory("sleep", top_k=5, max_age_days=30)

# No window (default) — decay still applies, but nothing is hard-filtered
results = soma.query_memory("sleep", top_k=5)
```

Every returned item carries its own time metadata:

```python
for item in results:
    print(item["age_days"], item["timestamp"], item["nature"], item["is_stale"])
```

Use `max_age_days` when the *question itself* is time-bounded. Don't use it as a generic
safety net — recency decay already handles that.

### 3. `is_stale` — the backstop

`nature` marks what kind of thing a memory is:

| `nature` | Meaning | Examples | Time-sensitive? |
|----------|---------|----------|-----------------|
| `state` | A condition that changes | "hasn't been sleeping well", "feeling anxious", "in Beijing this week" | **Yes** |
| `fact` | Knowledge, skills, traits | "writes Python", "prefers terse APIs", wiki content | No |
| `event` | A thing that happened (default) | "attended the design review" | Mildly |

A `state` memory older than 30 days (`STATE_TTL_DAYS`) has `is_stale = True` in
`explain_activation` output. Use it to soften the phrasing in your prompt:

```python
for item in soma.query_memory("sleep", top_k=5):
    if item["nature"] == "state" and item["is_stale"]:
        # Rendered 40 days ago — present it as history, not as current state
        prompt += f"[{int(item['age_days'])} days ago, may have changed] {item['content_preview']}\n"
    elif item["nature"] == "event":
        prompt += f"[{int(item['age_days'])} days ago] {item['content_preview']}\n"
    else:  # fact — timeless
        prompt += f"{item['content_preview']}\n"
```

**What `is_stale` is good for:** a state memory from 10–30 days ago. It still passes the
activation threshold (decay at 10d is ~0.24), so it *will* be recalled and injected — and
without the flag, the LLM may present it as current. This is the real window where the
backstop earns its place.

**What it is not for:** memories older than ~30 days. Decay has already dropped those below
the recall threshold; `is_stale` never gets a chance to run on them.

## Tagging memories correctly

Tag at write time whenever you know the nature:

```python
soma.remember("User hasn't been sleeping well lately", nature="state")
soma.remember("User writes Python", nature="fact")
soma.remember("User attended the design review")            # defaults to event
```

Code memories default to `fact` (a codebase skill doesn't expire):

```python
soma.remember_code("def add(a, b): return a + b", file_path="calc.py")
```

## Backfilling existing memories

If your store predates `nature`, or everything is still defaulted to `event`, run the built-in
reclassifier. It is **dry-run by default** and backs up before writing:

```bash
# Preview — nothing is modified
soma reclassify

# Apply (writes a backup to <memory-dir>/nature_backups/)
soma reclassify --apply

# Undo a run
soma reclassify --rollback ~/.soma/shared/nature_backups/nature_backup_20260911-134025.json
```

From Python:

```python
print(soma.reclassify_nature())              # dry run
print(soma.reclassify_nature(dry_run=False)) # apply, auto-backup
soma.rollback_nature(backup_path)
```

Rules are keyword-based (zero LLM calls) and fully replaceable:

```python
from soma.nature import NatureClassifier

clf = NatureClassifier(
    state_keywords=("insomnia", "anxious", "migraine"),
    fact_keywords=("writes", "specializes in"),
    fact_min_len=300,          # long documents count as knowledge
    fact_sources=("wiki", "knowledge", "doc"),
)
print(clf.classify("User writes Rust", {}))   # 'fact'
soma.reclassify_nature(classifier=clf, dry_run=False)
```

By default the reclassifier only touches memories whose `nature` is still `event` — anything
already classified (by you or by hand) is left alone. Pass `only_nature=None` to override.

## Long-running processes: `reload()`

If another process writes to the same memory directory (a CLI, a second agent, a batch job),
your long-running instance needs its in-memory vector index refreshed. SQLite reads are
already live; the faiss index is what lags.

```python
stats = soma.reload()
# {'reloaded_vectors': 26574, 'total': 26574}
```

Note that `similarity_search` already self-heals when the indexed count diverges from the DB
count, so a plain new memory is usually picked up on the next search anyway. `reload()` is for
when you want the refresh to happen **now**, and it also catches the case self-healing misses:
an external process that deletes N memories and adds N more leaves the count unchanged, so the
index keeps the deleted vectors and never sees the new ones until you reload.

## Summary

- **Recency decay is the front line.** It silently removes old memories; nothing else is needed
  for the 40-day-old-state problem.
- **`max_age_days`** is an explicit window for time-bounded questions, not a safety net.
- **`is_stale` is a backstop** for the 10–30 day window, where a state memory still gets
  recalled. It is not a defense against old memories — decay already handled those.
