import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

import networkx as nx

from soma.abc import BaseMemoryStore
from soma.base import MemoryUnit


class SemanticStore(BaseMemoryStore):
    """语义记忆存储 — NetworkX 有向图 + SQLite 持久化"""

    def __init__(self, persist_dir: Optional[Path] = None):
        self.graph = nx.DiGraph()
        if persist_dir is None:
            persist_dir = Path(os.environ.get("SOMA_DATA_DIR", "soma_data"))
        persist_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = persist_dir / "semantic.db"
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._create_table()
        self._load_from_db()

    def _create_table(self):
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA cache_size=-4000")       # 4MB 缓存（语义数据量较小）
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS semantic_triples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject TEXT NOT NULL,
                predicate TEXT NOT NULL,
                object TEXT NOT NULL,
                confidence REAL DEFAULT 1.0,
                created_at REAL NOT NULL
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_semantic_subject ON semantic_triples(subject)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_semantic_object ON semantic_triples(object)"
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

    def add_triple(
        self, subject: str, predicate: str, object_: str, confidence: float = 1.0
    ) -> None:
        """添加三元组并持久化到 SQLite"""
        import time
        self.graph.add_node(subject, type="concept")
        self.graph.add_node(object_, type="concept")
        self.graph.add_edge(
            subject, object_, predicate=predicate, confidence=confidence
        )
        self._conn.execute(
            """
            INSERT INTO semantic_triples (subject, predicate, object, confidence, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (subject, predicate, object_, confidence, time.time()),
        )
        self._conn.commit()

    def query_by_keywords(
        self, keywords: List[str], top_k: int = 5
    ) -> List[MemoryUnit]:
        if not keywords:
            return []

        results: List[MemoryUnit] = []
        seen_ids: set = set()

        # 路径1: FTS5 trigram 全文搜索（3字及以上关键词）
        fts_keywords = [kw for kw in keywords if len(kw) >= 3]
        if fts_keywords:
            fts_query = " OR ".join(f'"{kw}"' for kw in fts_keywords)
            try:
                rows = self._conn.execute(
                    """
                    SELECT st.* FROM semantic_triples st
                    INNER JOIN semantic_fts fts ON st.rowid = fts.rowid
                    WHERE semantic_fts MATCH ?
                    ORDER BY st.confidence DESC
                    LIMIT ?
                    """,
                    (fts_query, top_k),
                ).fetchall()
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
                                },
                                memory_type="semantic",
                                importance=0.7,
                            )
                        )
            except sqlite3.OperationalError:
                pass

        # 路径2: LIKE 兜底（短关键词，搜索节点+边）
        like_keywords = [kw for kw in keywords if len(kw) < 3]
        remaining = top_k - len(results)
        if like_keywords and remaining > 0:
            for kw in like_keywords:
                if len(results) >= top_k:
                    break
                kw_lower = kw.lower()
                # 搜索节点
                for node in self.graph.nodes:
                    if kw_lower in node.lower():
                        node_id = f"sem_node_{node}"
                        if node_id not in seen_ids:
                            seen_ids.add(node_id)
                            neighbors = list(self.graph.neighbors(node))
                            results.append(
                                MemoryUnit(
                                    id=node_id,
                                    content=f"概念: {node}，关联概念: {', '.join(neighbors) if neighbors else '无'}",
                                    context={"node": node, "neighbors": neighbors},
                                    memory_type="semantic",
                                    importance=0.7,
                                )
                            )
                        if len(results) >= top_k:
                            break
                # 搜索边
                if len(results) >= top_k:
                    break
                for u, v, data in self.graph.edges(data=True):
                    pred = data.get("predicate", "")
                    if kw_lower in u.lower() or kw_lower in v.lower() or kw_lower in pred.lower():
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
                                        "confidence": data.get("confidence", 1.0),
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

    def list_nodes(self) -> List[str]:
        return list(self.graph.nodes)

    def count(self) -> int:
        return self.graph.number_of_edges()

    def count_triples(self) -> int:
        return self.count()

    def close(self):
        self._conn.close()
