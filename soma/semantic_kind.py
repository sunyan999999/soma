"""语义三元组的 kind 批量重分类（v2.0.37）。

与 `nature.py` 的三条安全原则一致：**dry_run 先预览、落盘前写备份、
备份失败就中止**，另外提供 `rollback_semantic_kind` 按备份还原。

## 为什么要这个工具

2.0.37 之前写入的三元组全是默认 `kind='fact'`。其中混着两类东西：

    fact      「数字分身 —基于→ 命理八字」       能直接回答用户问题
    relation  「《某文章》 —关联概念→ 经络」      只是「A 和 B 有关」

后者进 prompt 就是噪声（下游实测：1.5 万条导航边把用户情节记忆挤出 70%，
而分数面板看不出来）。

## 默认规则只按 namespace 猜

`namespace` 是唯一已有的结构信号：

    namespace 含 "graph"（wiki_graph / graph / mind_graph…）  → relation
    其余（''、user_id、agent_id）                              → 保持不动

为什么不在 `''` 里猜：那里本该只放事实。如果混进了导航边，说明写入方
已经违反了 namespace 约定，工具无从自动判断 —— 请接入方自己提供
`predicate_relation` 规则（例如 predicate 含「关联/参考/包含」）。
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

KIND_FACT = "fact"
KIND_RELATION = "relation"

# namespace 命中这些子串（小写比较）→ 视为导航图
DEFAULT_RELATION_NS_PATTERNS: Sequence[str] = ("graph",)


def reclassify_semantic_kind(
    store,
    dry_run: bool = True,
    backup_dir: Optional[str] = None,
    relation_namespaces: Optional[Sequence[str]] = None,
    predicate_relation: Optional[Sequence[str]] = None,
    limit: Optional[int] = None,
    batch_size: int = 500,
) -> Dict[str, Any]:
    """批量把导航图三元组的 kind 标成 relation。

    Args:
        store: SemanticStore（需有 `_conn`），或 MemoryCore（自动取 `.semantic`）
        dry_run: True 只统计不改库（默认）
        backup_dir: 备份目录，默认库同目录下 semantic_kind_backups/
        relation_namespaces: namespace 命中这些子串（小写）就标 relation。
            默认 ("graph",)。传空序列 = 不按 namespace 判定。
        predicate_relation: predicate 命中这些子串就标 relation（默认不启用）。
            用于清理 `''` 里混进的导航边。
        limit: 最多处理多少行
        batch_size: 每批提交条数

    Returns:
        {dry_run, scanned, changed, unchanged, by_kind, backup_path,
         elapsed_ms, samples}
    """
    if hasattr(store, "semantic"):          # MemoryCore
        store = store.semantic
    conn = store._conn

    ns_pats = [p.lower() for p in (
        DEFAULT_RELATION_NS_PATTERNS if relation_namespaces is None
        else relation_namespaces) if p]
    pred_pats = [p for p in (predicate_relation or []) if p]

    sql = "SELECT id, subject, predicate, object, namespace, kind FROM semantic_triples"
    params: List[Any] = []
    if limit:
        sql += " LIMIT ?"
        params.append(int(limit))

    try:
        rows = conn.execute(sql, params).fetchall()
    except Exception as e:                  # 旧库未迁移 kind 列
        return {"dry_run": dry_run, "error": f"读取失败（kind 列可能不存在）：{e}"}

    changes: List[tuple] = []               # (id, old_kind, new_kind)
    by_kind: Dict[str, int] = {}

    for r in rows:
        old = (r["kind"] if "kind" in r.keys() else KIND_FACT) or KIND_FACT
        by_kind[old] = by_kind.get(old, 0) + 1
        ns = (r["namespace"] or "").lower()
        pred = r["predicate"] or ""

        new = old
        if ns_pats and any(p in ns for p in ns_pats):
            new = KIND_RELATION
        elif pred_pats and any(p in pred for p in pred_pats):
            new = KIND_RELATION

        if new != old:
            changes.append((r["id"], old, new))

    result: Dict[str, Any] = {
        "dry_run": dry_run,
        "scanned": len(rows),
        "changed": len(changes),
        "unchanged": len(rows) - len(changes),
        "by_kind": by_kind,
        "backup_path": None,
        "elapsed_ms": 0,
    }

    if dry_run or not changes:
        if dry_run and changes:
            result["samples"] = [
                {"id": i, "from": o, "to": n} for i, o, n in changes[:5]
            ]
        return result

    t0 = time.time()

    # 备份：id → 原 kind。备份失败就不改库 —— 宁可不动，也不留无法回滚的改动
    db_path = getattr(store, "_db_path", None)
    bdir = Path(backup_dir) if backup_dir else (
        Path(db_path).parent if db_path else Path(".")) / "semantic_kind_backups"
    try:
        bdir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        bpath = bdir / f"semantic_kind_backup_{stamp}.json"
        bpath.write_text(json.dumps(
            {"created": stamp, "changes": [
                {"id": i, "from": o, "to": n} for i, o, n in changes]},
            ensure_ascii=False, indent=1), encoding="utf-8")
        result["backup_path"] = str(bpath)
    except OSError as e:
        result["error"] = f"备份写入失败，已中止：{e}"
        return result

    done = 0
    for mid, _old, new in changes:
        conn.execute("UPDATE semantic_triples SET kind=? WHERE id=?", (new, mid))
        done += 1
        if done % batch_size == 0:
            conn.commit()
    conn.commit()

    result["applied"] = done
    result["elapsed_ms"] = int((time.time() - t0) * 1000)
    return result


def rollback_semantic_kind(store, backup_path: str) -> Dict[str, Any]:
    """按 reclassify_semantic_kind 的备份文件还原 kind。"""
    if hasattr(store, "semantic"):
        store = store.semantic
    conn = store._conn
    data = json.loads(Path(backup_path).read_text(encoding="utf-8"))
    changes = data.get("changes", [])
    restored = 0
    for c in changes:
        if not c.get("from"):
            continue
        conn.execute("UPDATE semantic_triples SET kind=? WHERE id=?",
                     (c["from"], c["id"]))
        restored += 1
    conn.commit()
    return {"restored": restored, "backup_path": backup_path}
