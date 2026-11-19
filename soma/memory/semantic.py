import logging
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import networkx as nx

from soma.abc import BaseMemoryStore
from soma.base import MemoryUnit
from soma.db import close_store_connection, open_store_connection

_log = logging.getLogger("soma.memory.semantic")


class SemanticStore(BaseMemoryStore):
    """语义记忆存储 — NetworkX 有向图 + SQLite 持久化"""

    def __init__(self, persist_dir: Optional[Path] = None):
        self.graph = nx.DiGraph()
        if persist_dir is None:
            persist_dir = Path(os.environ.get("SOMA_DATA_DIR", "soma_data"))
        persist_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = persist_dir / "semantic.db"
        self._conn = open_store_connection(self._db_path)
        self._create_table()
        self._load_from_db()

    def _create_table(self):
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA cache_size=-4000")       # 4MB 缓存（语义数据量较小）
        self._conn.execute("PRAGMA busy_timeout=15000")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS semantic_triples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject TEXT NOT NULL,
                predicate TEXT NOT NULL,
                object TEXT NOT NULL,
                confidence REAL DEFAULT 1.0,
                created_at REAL NOT NULL,
                namespace TEXT NOT NULL DEFAULT '',
                kind TEXT NOT NULL DEFAULT 'fact'
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_semantic_subject ON semantic_triples(subject)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_semantic_object ON semantic_triples(object)"
        )
        # 先迁移列，再创建索引（旧数据库可能无 namespace 列）
        try:
            self._conn.execute(
                "ALTER TABLE semantic_triples ADD COLUMN namespace TEXT NOT NULL DEFAULT ''"
            )
        except sqlite3.OperationalError:
            pass
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_semantic_namespace ON semantic_triples(namespace)"
        )
        # v2.0.37：kind —— 这条三元组「用来做什么」。
        #
        #   fact     = 能直接回答用户问题的事实（会进 prompt）
        #   relation = 导航/关联边（只参与图扩展，不注入）
        #
        # 与 namespace 互补：namespace 管「谁能看见」，kind 管「这条用来做什么」。
        # 下游踩过的坑：1.5 万条 wiki 关联图落在 namespace='' 里，include_global
        # 一开就挤掉用户情节记忆 70% —— 那次靠 namespace 隔离修，但漏传一次
        # 就会复发，且分数面板看不出来。kind 让它在结构上可过滤。
        try:
            self._conn.execute(
                "ALTER TABLE semantic_triples ADD COLUMN kind TEXT NOT NULL DEFAULT 'fact'"
            )
        except sqlite3.OperationalError:
            pass
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_semantic_kind ON semantic_triples(kind)"
        )
        self._create_fts5()
        self._conn.commit()

    def _create_fts5(self):
        """创建 FTS5 trigram 全文索引"""
        self._conn.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS semantic_fts USING fts5(
                subject,
                predicate,
                object,
                content='semantic_triples',
                content_rowid='rowid',
                tokenize='trigram'
            )
            """
        )
        self._conn.executescript("""
            CREATE TRIGGER IF NOT EXISTS semantic_fts_ai AFTER INSERT ON semantic_triples BEGIN
                INSERT INTO semantic_fts(rowid, subject, predicate, object)
                VALUES (new.rowid, new.subject, new.predicate, new.object);
            END;
            CREATE TRIGGER IF NOT EXISTS semantic_fts_ad AFTER DELETE ON semantic_triples BEGIN
                INSERT INTO semantic_fts(semantic_fts, rowid, subject, predicate, object)
                VALUES ('delete', old.rowid, old.subject, old.predicate, old.object);
            END;
            CREATE TRIGGER IF NOT EXISTS semantic_fts_au AFTER UPDATE ON semantic_triples BEGIN
                INSERT INTO semantic_fts(semantic_fts, rowid, subject, predicate, object)
                VALUES ('delete', old.rowid, old.subject, old.predicate, old.object);
                INSERT INTO semantic_fts(rowid, subject, predicate, object)
                VALUES (new.rowid, new.subject, new.predicate, new.object);
            END;
        """)
        populated = self._conn.execute(
            "SELECT COUNT(*) FROM semantic_fts"
        ).fetchone()[0]
        if populated == 0:
            self._conn.execute(
                "INSERT INTO semantic_fts(rowid, subject, predicate, object) "
                "SELECT rowid, subject, predicate, object FROM semantic_triples"
            )

    def _load_from_db(self):
        """启动时从 SQLite 重建 NetworkX 图"""
        import time
        rows = self._conn.execute(
            "SELECT subject, predicate, object, confidence FROM semantic_triples"
        ).fetchall()
        for row in rows:
            self.graph.add_node(row["subject"], type="concept")
            self.graph.add_node(row["object"], type="concept")
            self.graph.add_edge(
                row["subject"], row["object"],
                predicate=row["predicate"],
                confidence=row["confidence"],
            )

    def get_all_triples(self) -> List[dict]:
        """返回全部语义三元组（v2.0.9: 补接口，供 MemoryManager 冲突检测使用）。"""
        try:
            rows = self._conn.execute(
                "SELECT subject, predicate, object, confidence, namespace, kind "
                "FROM semantic_triples"
            ).fetchall()
        except Exception:
            return []
        return [
            {
                "subject": r["subject"],
                "predicate": r["predicate"],
                "object": r["object"],
                "confidence": float(r["confidence"]),
                "namespace": r["namespace"] or "",
                "kind": (r["kind"] if "kind" in r.keys() else "fact") or "fact",
            }
            for r in rows
        ]

    def add_triple(
        self, subject: str, predicate: str, object_: str,
        confidence: float = 1.0,
        namespace: str = "",
        kind: str = "fact",
    ) -> None:
        """添加三元组并持久化到 SQLite（同 namespace 内去重）。

        `kind`（v2.0.37）：`fact`（默认，会进 prompt）或 `relation`
        （导航/关联边，只参与图扩展）。也接受自定义字符串。
        去重键不含 kind —— 同一条边改 kind 不算新边，会直接返回。
        """
        import time

        # 去重检查：同 namespace 内相同的 (subject, predicate, object) 不重复插入
        existing = self._conn.execute(
            "SELECT rowid FROM semantic_triples WHERE subject = ? AND predicate = ? "
            "AND object = ? AND namespace = ? LIMIT 1",
            (subject, predicate, object_, namespace),
        ).fetchone()
        if existing:
            return

        self.graph.add_node(subject, type="concept")
        self.graph.add_node(object_, type="concept")
        self.graph.add_edge(
            subject, object_, predicate=predicate, confidence=confidence
        )
        self._conn.execute(
            """
            INSERT INTO semantic_triples
                (subject, predicate, object, confidence, created_at, namespace, kind)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (subject, predicate, object_, confidence, time.time(), namespace,
             kind or "fact"),
        )
        self._conn.commit()

    def query_by_keywords(
        self, keywords: List[str], top_k: int = 5,
        namespace: str = "",
        max_age_days: Optional[float] = None,
        include_global: bool = False,
        max_like_keywords: int = 3,
        include_kinds: Optional[Sequence[str]] = None,
    ) -> List[MemoryUnit]:
        """按关键词查语义三元组。

        `include_global`（2026-11-25，下游实测）：为 True 时，除了 `namespace`
        精确匹配，**还纳入 `namespace = ''` 的全局知识**。

        为什么需要：下游生产有 15,312 条三元组**全部** namespace = ''（全局
        知识，如「数字分身—基于—命理八字」），而 `MemoryCore.query` 传的是
        `agent_id or user_id` —— 查 `namespace='1'` 返回 0 行。
        结果：**知识图谱对真实用户完全没生效**，每次只是空转 0.3ms。

        `namespace=''` 在本方法的历史语义是「不过滤」（返回所有用户的三元组），
        不是「只查全局」—— 所以不能靠它来修。
        """
        if not keywords:
            return []

        results: List[MemoryUnit] = []
        seen_ids: set = set()
        if namespace and include_global:
            ns_clause = "AND (st.namespace = ? OR st.namespace = '')"
        elif namespace:
            ns_clause = "AND st.namespace = ?"
        else:
            ns_clause = ""

        # v2.0.37：kind 过滤。None = 不过滤（完全向后兼容）；空集合也当
        # 不过滤 —— 「什么都不要」应该用 top_k=0 表达，不是一个隐式空 IN。
        # 典型注入只传 ("fact",)，让导航边不进入 prompt。
        kind_clause = ""
        kind_params: List[str] = []
        if include_kinds:
            kinds = [k for k in include_kinds if k]
            if kinds:
                kind_clause = "AND st.kind IN (" + ", ".join("?" * len(kinds)) + ")"
                kind_params = kinds
        time_clause = ""
        time_params = []
        if max_age_days is not None:
            import time
            min_ts = time.time() - max_age_days * 86400.0
            time_clause = "AND st.created_at >= ?"
            time_params = [min_ts]

        # 路径1: FTS5 trigram 全文搜索（3字及以上关键词）
        fts_keywords = [kw for kw in keywords if len(kw) >= 3]
        if fts_keywords:
            fts_query = " OR ".join(
                '"' + kw.replace('"', '""') + '"' for kw in fts_keywords
            )
            try:
                params = [fts_query] + time_params
                sql = f"""
                    -- 2.0.18.2：同 search_utils.py，写成 rowid IN (子查询)，
                    -- 避免 SQLite 逐行去 FTS 虚拟表探导致的固定开销。
                    SELECT st.* FROM semantic_triples st
                    WHERE st.rowid IN (
                        SELECT rowid FROM semantic_fts WHERE semantic_fts MATCH ?
                    )
                    {time_clause} {ns_clause} {kind_clause}
                    ORDER BY st.confidence DESC, st.id DESC
                    LIMIT ?
                """
                if namespace:
                    params.append(namespace)
                params.extend(kind_params)
                params.append(top_k)
                rows = self._conn.execute(sql, params).fetchall()
                for row in rows:
                    u, v, pred = row["subject"], row["object"], row["predicate"]
                    edge_id = f"sem_edge_{u}_{pred}_{v}"
                    if edge_id not in seen_ids:
                        seen_ids.add(edge_id)
                        results.append(
                            MemoryUnit(
                                id=edge_id,
                                content=f"{u} --[{pred}]--> {v}",
                                context={
                                    "subject": u,
                                    "predicate": pred,
                                    "object": v,
                                    "confidence": row["confidence"],
                                    "kind": row["kind"],
                                },
                                memory_type="semantic",
                                importance=0.7,
                            )
                        )
            except sqlite3.OperationalError:
                _log.info("语义 FTS5 搜索语法错误，降级到 LIKE 搜索")

        # 路径2: LIKE 兜底（短关键词，SQLite 查询确保 namespace 过滤正确）
        #
        # ★ 2026-11-25（下游生产实测）：两个改动。
        #   1) `include_global` 也必须在这里生效 —— 这条路径是**独立构造 SQL** 的，
        #      不走上面的 `ns_clause`，第一版修完发现全局知识在 FTS 路径能查到、
        #      在短词路径查不到，行为不一致。
        #   2) `max_like_keywords`：LIKE '%x%' 用不上索引，每个词都要在
        #      **每一行**上评估一次 —— 成本是 O(词数 × 行数)。下游实测
        #      4 词 55ms / 8 词 94ms / 10 词 111ms（32k 库），而一次 activate
        #      会传 8~20 个 2 字词。截到 3 个（focus 自带词排前面）能砍掉大头。
        like_keywords = [kw for kw in keywords if len(kw) < 3][:max(1, max_like_keywords)]
        remaining = top_k - len(results)
        if like_keywords and remaining > 0:
            conditions = [] if max_age_days is None else ["st.created_at >= ?"]
            params: list = [] if max_age_days is None else time_params.copy()
            if namespace:
                if include_global:
                    conditions.append("(st.namespace = ? OR st.namespace = '')")
                else:
                    conditions.append("st.namespace = ?")
                params.append(namespace)
            if include_kinds:
                kinds = [k for k in include_kinds if k]
                if kinds:
                    conditions.append(
                        "st.kind IN (" + ", ".join("?" * len(kinds)) + ")")
                    params.extend(kinds)
            if seen_ids:
                # 用 rowid 构造唯一 ID 去重: sem_edge_{subject}_{predicate}_{object}
                # 排除已由 FTS 路径返回的边
                pass  # seen_ids 基于 edge_id 字符串，SQL 不易直接排除，改为后处理
            kw_conds = []
            for kw in like_keywords:
                pattern = f"%{kw}%"
                kw_conds.append(
                    "(st.subject LIKE ? OR st.predicate LIKE ? OR st.object LIKE ?)"
                )
                params.extend([pattern, pattern, pattern])
            conditions.append("(" + " OR ".join(kw_conds) + ")")
            sql = f"""
                SELECT st.* FROM semantic_triples st
                WHERE {' AND '.join(conditions)}
                ORDER BY st.confidence DESC, st.id DESC
                LIMIT ?
            """
            params.append(remaining * 2)  # 过取以弥补后处理去重
            rows = self._conn.execute(sql, params).fetchall()
            for row in rows:
                u, v, pred = row["subject"], row["object"], row["predicate"]
                edge_id = f"sem_edge_{u}_{pred}_{v}"
                if edge_id not in seen_ids:
                    seen_ids.add(edge_id)
                    results.append(
                        MemoryUnit(
                            id=edge_id,
                            content=f"{u} --[{pred}]--> {v}",
                            context={
                                "subject": u,
                                "predicate": pred,
                                "object": v,
                                "confidence": row["confidence"],
                                "kind": row["kind"],
                            },
                            memory_type="semantic",
                            importance=0.7,
                        )
                    )
                    if len(results) >= top_k:
                        break

        return results[:top_k]

    def get_neighbors(self, node: str, depth: int = 1) -> Dict[str, Any]:
        if node not in self.graph:
            return {"node": node, "neighbors": [], "edges": []}

        subgraph_nodes = [node]
        subgraph_edges = []
        frontier = {node}
        for _ in range(depth):
            next_frontier = set()
            for n in frontier:
                for _, v, data in self.graph.out_edges(n, data=True):
                    subgraph_nodes.append(v)
                    subgraph_edges.append(
                        {"from": n, "to": v, "predicate": data.get("predicate", "")}
                    )
                    next_frontier.add(v)
            frontier = next_frontier

        return {"node": node, "neighbors": subgraph_nodes, "edges": subgraph_edges}

    def expand_query_terms(
        self, nodes: List[str], depth: int = 2, max_terms: int = 10,
    ) -> List[str]:
        """从起始节点沿图BFS遍历，返回邻居节点标签作为扩展搜索词。

        权重按图距离衰减：1跳×0.6, 2跳×0.36。
        返回按衰减权重降序排列的邻居标签列表。
        """
        if not nodes:
            return []

        expanded: Dict[str, float] = {}  # node_label → decay_weight
        frontier = set(nodes)
        visited = set(nodes)

        decay = 1.0
        for d in range(depth):
            decay *= 0.6
            next_frontier = set()
            for n in frontier:
                if n not in self.graph:
                    continue
                for _, v in self.graph.out_edges(n):
                    if v not in visited:
                        visited.add(v)
                        next_frontier.add(v)
                        expanded[v] = max(expanded.get(v, 0), decay)
            frontier = next_frontier
            if not frontier:
                break

        # 次键按名称排序：同一跳的邻居权重完全相同（0.6 / 0.36 两档），
        # 只按权重排会让 `max_terms` 截断在并列处取谁不定 —— 上游关键词
        # 一变，下游命中的三元组就跟着变（表现为激活结果不稳定）。
        ranked = sorted(expanded.items(), key=lambda x: (-x[1], x[0]))
        return [term for term, _ in ranked[:max_terms]]

    def list_nodes(self) -> List[str]:
        return list(self.graph.nodes)

    def count(self) -> int:
        return self.graph.number_of_edges()

    def count_triples(self) -> int:
        return self.count()

    def close(self):
        close_store_connection(self._conn)
