"""v0.8.0 因果推理链 — 从语义图谱中提取因果子图并执行推理。

提供根因分析、影响链路、因果路径查询和环路检测。
所有操作仅在明确调用时触发，不影响普通检索性能。
"""

from collections import deque
from typing import Any, Dict, List, Optional, Set

import networkx as nx

from soma.memory.semantic import SemanticStore

# 因果谓词集合（外部可通过 add_causal_predicate 扩展）
CAUSAL_PREDICATES: Set[str] = {
    "causes", "leads_to", "prevents",
    "increases", "decreases", "results_in",
    "triggers", "blocks", "contributes_to",
}


def add_causal_predicate(predicate: str) -> None:
    """注册新的因果谓词"""
    CAUSAL_PREDICATES.add(predicate.lower())


class CausalGraph:
    """从语义图谱中提取因果子图，提供因果推理操作。

    因果边 = 语义三元组中 predicate 属于 CAUSAL_PREDICATES 的边。
    prevents/blocks 在传播中反转方向（负向因果）。
    """

    def __init__(self, semantic_store: SemanticStore):
        self.store = semantic_store

    @staticmethod
    def is_causal_predicate(predicate: str) -> bool:
        return predicate.lower() in CAUSAL_PREDICATES

    def get_causal_edges(self) -> List[Dict[str, Any]]:
        """获取全部因果边"""
        edges = []
        for u, v, data in self.store.graph.edges(data=True):
            pred = data.get("predicate", "")
            if self.is_causal_predicate(pred):
                edges.append({
                    "from": u,
                    "to": v,
                    "predicate": pred,
                    "confidence": data.get("confidence", 1.0),
                })
        return edges

    @property
    def _graph(self) -> nx.DiGraph:
        return self.store.graph

    def find_root_causes(self, node: str, max_depth: int = 10) -> List[str]:
        """从 node 出发沿因果边反向BFS，找出所有无因果前驱的叶子节点（根因）。

        对于 prevents/blocks 边，也视为负向因果参与反向遍历。
        """
        if node not in self._graph:
            return []

        # 反向BFS：沿因果边逆流而上
        visited: Set[str] = {node}
        frontier = {node}
        root_causes: List[str] = []

        for _ in range(max_depth):
            next_frontier: Set[str] = set()
            for n in frontier:
                predecessors = set(self._graph.predecessors(n))
                causal_preds = {
                    p for p in predecessors
                    if self.is_causal_predicate(
                        self._graph.edges[p, n].get("predicate", "")
                    )
                }
                if not causal_preds:
                    # 无因果前驱 → 这是一个根因
                    if n not in root_causes:
                        root_causes.append(n)
                else:
                    for p in causal_preds:
                        if p not in visited:
                            visited.add(p)
                            next_frontier.add(p)
            if not next_frontier:
                break
            frontier = next_frontier

        # BFS 按发现顺序排列，去重保持顺序
        return root_causes

    def find_effects(self, node: str, depth: int = 5) -> List[str]:
        """从 node 出发沿因果边正向BFS，找出所有下游影响节点。

        prevents/blocks 边也视为因果传播路径。
        """
        if node not in self._graph:
            return []

        visited: Set[str] = {node}
        frontier = {node}
        effects: List[str] = []

        for _ in range(depth):
            next_frontier: Set[str] = set()
            for n in frontier:
                for _, v, data in self._graph.out_edges(n, data=True):
                    if self.is_causal_predicate(data.get("predicate", "")):
                        if v not in visited:
                            visited.add(v)
                            effects.append(v)
                            next_frontier.add(v)
            if not next_frontier:
                break
            frontier = next_frontier

        return effects

    def get_causal_chain(
        self, start: str, end: str, max_depth: int = 10,
    ) -> Optional[List[str]]:
        """BFS 查找 start→end 的最短因果路径。返回节点列表或 None。"""
        if start not in self._graph or end not in self._graph:
            return None
        if start == end:
            return [start]

        queue = deque([(start, [start])])
        visited = {start}

        while queue:
            node, path = queue.popleft()
            if len(path) > max_depth:
                continue

            for _, v, data in self._graph.out_edges(node, data=True):
                if not self.is_causal_predicate(data.get("predicate", "")):
                    continue
                if v == end:
                    return path + [v]
                if v not in visited:
                    visited.add(v)
                    queue.append((v, path + [v]))

        return None

    def detect_cycles(self) -> List[List[str]]:
        """在因果子图中检测环路。返回每条环路中涉及的节点列表。"""
        cycles = []
        try:
            raw_cycles = list(nx.simple_cycles(self._graph))
        except Exception:
            return cycles

        for cycle in raw_cycles:
            # 检查环路上是否至少有一条边是因果边
            has_causal = False
            for i in range(len(cycle)):
                u, v = cycle[i], cycle[(i + 1) % len(cycle)]
                if self._graph.has_edge(u, v):
                    data = self._graph.edges[u, v]
                    if self.is_causal_predicate(data.get("predicate", "")):
                        has_causal = True
                        break
            if has_causal:
                cycles.append(cycle)

        return cycles
