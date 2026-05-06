"""FTS5 + LIKE 关键词搜索共享工具。

episodic / skill 两个 store 的 query_by_keywords()
有相同的双路径搜索模式（FTS5 → LIKE 降级），此模块提取公共逻辑。

semantic store 因 FTS 列结构（subject/predicate/object 三列分开）
和 edge_id 去重逻辑差异较大，保持独立实现。
"""
from typing import Any, Callable, List, Optional
import sqlite3
import logging
from datetime import datetime, timezone

_log = logging.getLogger(__name__)


def fts5_keyword_search(
    conn: sqlite3.Connection,
    keywords: List[str],
    *,
    table_name: str,
    fts_table: str,
    search_cols: List[str],
    id_col: str = "id",
    time_col: str = "timestamp",
    importance_col: Optional[str] = "importance",
    user_col: str = "user_id",
    row_converter: Callable[[sqlite3.Row], Any],
    top_k: int = 5,
    user_id: str = "",
    max_age_days: Optional[float] = None,
) -> List[Any]:
    """FTS5 trigram + LIKE 降级的双路径关键词搜索。

    路径1: FTS5 MATCH（≥3字关键词，毫秒级）
    路径2: LIKE 兜底（1-2字短关键词）
    路径3: 纯 LIKE 回退（无FTS关键词时）

    search_cols 指定 LIKE 搜索的目标列，例如 ["content", "context_json"]。
    FTS 搜索使用 fts_table MATCH，列已在 FTS 虚拟表定义中固定。
    """
    if not keywords:
        return []

    fts_keywords = [kw for kw in keywords if len(kw) >= 3]
    like_keywords = [kw for kw in keywords if len(kw) < 3]

    seen_ids: set = set()
    results: List[Any] = []

    # ── 排序子句 ──────────────────────────────────────
    order_clause = f"t.{time_col} DESC"
    if importance_col is not None:
        order_clause += f", t.{importance_col} DESC"

    # ── 时间窗口 / 用户过滤 ────────────────────────────
    time_clause = ""
    time_params: list = []
    if max_age_days is not None:
        min_ts = datetime.now(timezone.utc).timestamp() - max_age_days * 86400.0
        time_clause = f"AND t.{time_col} >= ?"
        time_params = [min_ts]

    user_clause = ""
    user_params: list = []
    if user_id:
        user_clause = f"AND t.{user_col} = ?"
        user_params = [user_id]

    # ── 路径1: FTS5 trigram 全文搜索 ──────────────────
    if fts_keywords:
        fts_query = " OR ".join(
            '"' + kw.replace('"', '""') + '"' for kw in fts_keywords
        )
        try:
            params = [fts_query] + time_params + user_params + [top_k]
            sql = f"""
                SELECT t.* FROM {table_name} t
                INNER JOIN {fts_table} fts ON t.rowid = fts.rowid
                WHERE {fts_table} MATCH ?
                {time_clause} {user_clause}
                ORDER BY {order_clause}
                LIMIT ?
            """
            rows = conn.execute(sql, params).fetchall()
            for r in rows:
                obj = row_converter(r)
                oid = getattr(obj, id_col) if hasattr(obj, id_col) else obj.get(id_col)
                if oid not in seen_ids:
                    seen_ids.add(oid)
                    results.append(obj)
        except sqlite3.OperationalError:
            _log.info("FTS5 搜索语法错误，降级到 LIKE 搜索")

    # ── 路径2: LIKE 兜底（短关键词 1-2 字）────────────
    remaining = top_k - len(results)
    if like_keywords and remaining > 0:
        conditions: List[str] = []
        params: list = []

        if max_age_days is not None:
            conditions.append(f"{time_col} >= ?")
            params.extend(time_params)
        if user_id:
            conditions.append(f"{user_col} = ?")
            params.append(user_id)
        if seen_ids:
            placeholders = ",".join("?" * len(seen_ids))
            conditions.append(f"{id_col} NOT IN ({placeholders})")
            params.extend(seen_ids)

        kw_conds: List[str] = []
        for kw in like_keywords:
            pattern = f"%{kw}%"
            col_conds = " OR ".join(f"{col} LIKE ?" for col in search_cols)
            kw_conds.append(f"({col_conds})")
            params.extend([pattern] * len(search_cols))
        conditions.append("(" + " OR ".join(kw_conds) + ")")

        like_order = f"{time_col} DESC"
        if importance_col is not None:
            like_order += f", {importance_col} DESC"
        sql = f"""
            SELECT * FROM {table_name}
            WHERE {' AND '.join(conditions)}
            ORDER BY {like_order}
            LIMIT ?
        """
        params.append(remaining)
        rows = conn.execute(sql, params).fetchall()
        for r in rows:
            obj = row_converter(r)
            oid = getattr(obj, id_col) if hasattr(obj, id_col) else obj.get(id_col)
            if oid not in seen_ids:
                seen_ids.add(oid)
                results.append(obj)

    # ── 路径3: 纯 LIKE 回退 ──────────────────────────
    if not results and not fts_keywords:
        results = _like_only(
            conn,
            keywords,
            table_name=table_name,
            search_cols=search_cols,
            id_col=id_col,
            time_col=time_col,
            importance_col=importance_col,
            user_col=user_col,
            row_converter=row_converter,
            top_k=top_k,
            user_id=user_id,
            max_age_days=max_age_days,
        )

    return results


def _like_only(
    conn: sqlite3.Connection,
    keywords: List[str],
    *,
    table_name: str,
    search_cols: List[str],
    id_col: str,
    time_col: str,
    importance_col: Optional[str],
    user_col: str,
    row_converter: Callable[[sqlite3.Row], Any],
    top_k: int,
    user_id: str,
    max_age_days: Optional[float],
) -> List[Any]:
    """纯 LIKE 搜索（无 FTS5 可用时）。"""
    conditions: List[str] = []
    params: list = []
    if max_age_days is not None:
        min_ts = datetime.now(timezone.utc).timestamp() - max_age_days * 86400.0
        conditions.append(f"{time_col} >= ?")
        params.append(min_ts)
    if user_id:
        conditions.append(f"{user_col} = ?")
        params.append(user_id)
    for kw in keywords:
        pattern = f"%{kw}%"
        col_conds = " OR ".join(f"{col} LIKE ?" for col in search_cols)
        conditions.append(f"({col_conds})")
        params.extend([pattern] * len(search_cols))
    order_clause = f"{time_col} DESC"
    if importance_col is not None:
        order_clause += f", {importance_col} DESC"
    sql = f"""
        SELECT * FROM {table_name}
        WHERE {' AND '.join(conditions)}
        ORDER BY {order_clause}
        LIMIT ?
    """
    params.append(top_k)
    rows = conn.execute(sql, params).fetchall()
    return [row_converter(r) for r in rows]
