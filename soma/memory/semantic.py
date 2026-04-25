import uuid
from typing import Any, Dict, List, Optional

import networkx as nx

from soma.base import MemoryUnit


class SemanticStore:
    """语义记忆存储 — 基于 NetworkX 有向图存储三元组"""

    def __init__(self):
        self.graph = nx.DiGraph()

    def add_triple(
        self, subject: str, predicate: str, object_: str, confidence: float = 1.0
    ) -> None:
        self.graph.add_node(subject, type="concept")
        self.graph.add_node(object_, type="concept")
        self.graph.add_edge(
            subject, object_, predicate=predicate, confidence=confidence
        )

    def query_by_keywords(
        self, keywords: List[str], top_k: int = 5
    ) -> List[MemoryUnit]:
        results: List[MemoryUnit] = []
        seen_ids: set = set()

        for kw in keywords:
            kw_lower = kw.lower()
            # Search nodes
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

            # Search edges
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

        # Sort by some heuristic — more matched keywords = more relevant
        return sorted(
            results,
            key=lambda m: sum(
                1 for kw in keywords if kw.lower() in m.content.lower()
            ),
            reverse=True,
        )[:top_k]

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

    def count_triples(self) -> int:
        return self.graph.number_of_edges()
