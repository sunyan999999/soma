"""记忆库脏数据自愈（v2.0.17）。

背景：``context`` 字段历史上可能被写入非 JSON 对象的值 —— 调用方把字符串直接
传给 ``remember(context=...)`` 时，``json.dumps("文本")`` 产出的是合法但非对象的
JSON，读回来就是 str。检索热路径上的 ``mem.context["_vector_score"] = score``
一旦拿到 str 就抛 TypeError，**全库两万多条里 1 条脏数据就能让整次全库检索崩溃**
（DSH 2026-09-12 在官方基准上撞到：26,872 条中 1 条 str 让 query_by_vector 炸掉）。

2.0.17 起读写双向都做了防御（见 ``soma/memory/context_utils.py``），脏数据不再致崩；
本模块负责把**存量**脏数据扫出来并规范化，供接入方自助执行：

    python -m soma.cli repair-context            # 预览
    python -m soma.cli repair-context --apply    # 落地（自动备份）

或走 API::

    soma.repair_context()                 # dry_run 预览
    soma.repair_context(dry_run=False)    # 修复
    soma.rollback_context(backup_path)    # 回滚

安全默认：``dry_run=True`` 只预览不改；落盘前自动写备份，失败即中止（宁可不动，
也不留无法回滚的改动）。
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# (表名, 主键列, context 列, user_id 列) —— 白名单，回滚时也用它校验表名
_TARGETS: List[Tuple[str, str, str, str]] = [
    ("episodic_memories", "id", "context_json", "user_id"),
    ("skills", "id", "context_json", "user_id"),
]

_TABLES = {t[0] for t in _TARGETS}


def _normalize_value(raw: Any) -> Tuple[Dict[str, Any], bool]:
    """返回 ``(规范化后的 dict, 是否为脏数据)``。

    判据与 ``context_utils.parse_context`` 保持一致：解析不出 JSON 对象的即为脏。
    """
    if raw is None:
        return {}, False
    if isinstance(raw, (bytes, bytearray, memoryview)):
        raw = bytes(raw).decode("utf-8", errors="replace")

    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return {}, False
        try:
            value = json.loads(text)
        except (ValueError, TypeError):
            return {"_raw": raw}, True
    else:
        value = raw

    if isinstance(value, dict):
        return value, False
    return {"_raw": value}, True


def _table_exists(conn, table: str) -> bool:
    try:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        return row is not None
    except Exception:
        return False


def repair_context(
    store,
    dry_run: bool = True,
    backup_dir: Optional[str] = None,
    user_id: str = "",
    limit: Optional[int] = None,
    batch_size: int = 500,
) -> Dict[str, Any]:
    """扫描并修复 context 非 JSON 对象的存量脏数据。

    修复方式：把原值收进 ``{"_raw": <原值>, "_repaired_at": <ISO 时间>}`` ——
    **不丢数据**，且与读取路径的规范化结果一致，修复前后取出的内容不变，
    只是库里不再存在会破坏 SQL / FTS 假设的形状。

    Args:
        store: EpisodicStore（需有 ._conn；裸 sqlite3.Connection 亦可）
        dry_run: True 只统计不改库（默认）
        backup_dir: 备份目录，默认记忆库同目录下 context_backups/
        user_id: 只处理某用户（空 = 全部）
        limit: 最多修复多少条（None = 不限）
        batch_size: 每批提交条数

    Returns:
        {dry_run, scanned, dirty, repaired, by_table, samples, backup_path, elapsed_ms}
    """
    conn = getattr(store, "_conn", store)
    t0 = time.time()
    result: Dict[str, Any] = {
        "dry_run": dry_run,
        "scanned": 0,
        "dirty": 0,
        "repaired": 0,
        "by_table": {},
        "samples": [],
        "backup_path": None,
        "elapsed_ms": 0,
    }

    changes: List[Tuple[str, str, str, Any]] = []  # (表, id, 新 JSON 文本, 原值)
    stop = False

    for table, id_col, ctx_col, user_col in _TARGETS:
        if stop or not _table_exists(conn, table):
            continue
        sql = f"SELECT {id_col}, {ctx_col} FROM {table}"
        params: List[Any] = []
        if user_id and user_col:
            sql += f" WHERE {user_col} = ?"
            params.append(user_id)
        try:
            rows = conn.execute(sql, params).fetchall()
        except Exception:
            continue

        for row in rows:
            result["scanned"] += 1
            raw = row[ctx_col]
            norm, dirty = _normalize_value(raw)
            if not dirty:
                continue

            result["dirty"] += 1
            result["by_table"][table] = result["by_table"].get(table, 0) + 1
            if len(result["samples"]) < 5:
                result["samples"].append({
                    "table": table,
                    "id": row[id_col],
                    "raw": (raw if isinstance(raw, str) else repr(raw))[:200],
                })

            norm["_repaired_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            changes.append(
                (table, row[id_col], json.dumps(norm, ensure_ascii=False), raw)
            )
            if limit and result["dirty"] >= limit:
                stop = True
                break

    if dry_run or not changes:
        result["elapsed_ms"] = int((time.time() - t0) * 1000)
        return result

    # 备份：回滚时按 (表, id) 还原原文本
    if backup_dir:
        bdir = Path(backup_dir)
    else:
        db_path = getattr(store, "_db_path", None) or getattr(store, "persist_dir", None)
        bdir = (Path(db_path).parent if db_path else Path(".")) / "context_backups"
    try:
        bdir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        bpath = bdir / f"context_backup_{stamp}.json"
        bpath.write_text(
            json.dumps(
                {
                    "created": stamp,
                    "changes": [
                        {"table": t, "id": i, "old": o} for t, i, _new, o in changes
                    ],
                },
                ensure_ascii=False,
                indent=1,
            ),
            encoding="utf-8",
        )
        result["backup_path"] = str(bpath)
    except OSError as e:  # 备份失败就不改库 —— 宁可不动，也不留无法回滚的改动
        result["error"] = f"备份写入失败，已中止：{e}"
        result["elapsed_ms"] = int((time.time() - t0) * 1000)
        return result

    done = 0
    for table, mid, new_json, _old in changes:
        conn.execute(f"UPDATE {table} SET context_json=? WHERE id=?", (new_json, mid))
        done += 1
        if done % batch_size == 0:
            conn.commit()
    conn.commit()

    result["repaired"] = done
    result["elapsed_ms"] = int((time.time() - t0) * 1000)
    return result


def rollback_context(store, backup_path: str) -> Dict[str, Any]:
    """按 repair_context 的备份文件回滚一次修复。"""
    conn = getattr(store, "_conn", store)
    data = json.loads(Path(backup_path).read_text(encoding="utf-8"))
    restored = 0
    for c in data.get("changes", []):
        table = c.get("table")
        old = c.get("old")
        if table not in _TABLES or old is None:  # 表名白名单，防备份文件被改后注入
            continue
        conn.execute(f"UPDATE {table} SET context_json=? WHERE id=?", (old, c["id"]))
        restored += 1
    conn.commit()
    return {"restored": restored, "backup_path": backup_path}
