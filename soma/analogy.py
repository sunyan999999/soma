"""v0.8.0 跨领域类比引擎 — 在语义图谱中寻找结构相似的不同领域概念。

原理：
1. 提取查询关键词在图谱中的「结构指纹」— 入边/出边谓词集
2. 搜索图谱中具有相似谓词模式但位于不同领域的节点
3. 返回类比节点，供检索管道作为补充关键词使用
"""

from typing import Dict, FrozenSet, List, Optional, Set, Tuple

from soma.memory.semantic import SemanticStore


def _predicate_sets(store: SemanticStore, node: str) -> Tuple[FrozenSet[str], FrozenSet[str]]:
    """提取节点的结构指纹：(入边谓词集, 出边谓词集)。"""
    in_preds: Set[str] = set()
    out_preds: Set[str] = set()
    if node not in store.graph:
        return frozenset(), frozenset()
    for _, __, data in store.graph.in_edges(node, data=True):
        pred = (data.get("predicate") or "").lower()
        if pred:
            in_preds.add(pred)
    for _, __, data in store.graph.out_edges(node, data=True):
        pred = (data.get("predicate") or "").lower()
        if pred:
            out_preds.add(pred)
    return frozenset(in_preds), frozenset(out_preds)


def _jaccard(a: FrozenSet[str], b: FrozenSet[str]) -> float:
    if not a and not b:
        return 0.0
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union > 0 else 0.0


class AnalogyEngine:
    """跨领域类比引擎。

    从语义图谱中寻找与目标概念结构相似的其他领域概念，
    用于在直接检索结果不足时补充跨域视角。
    """

    def __init__(self, semantic_store: SemanticStore):
        self._semantic = semantic_store
        self._min_similarity = 0.3  # 结构相似度阈值

    def structural_signature(self, node: str) -> Dict:
        """返回节点的结构指纹描述。"""
        in_p, out_p = _predicate_sets(self._semantic, node)
        degree = 0
        if node in self._semantic.graph:
            degree = self._semantic.graph.degree(node)
        return {
            "node": node,
            "in_predicates": sorted(in_p),
            "out_predicates": sorted(out_p),
            "degree": degree,
        }

    def find_analogous_nodes(
        self, keywords: List[str], max_results: int = 5,
    ) -> List[Tuple[str, float, str]]:
        """为给定关键词搜索结构相似的类比节点。

        返回 [(节点名, 相似度, 结构描述), ...]，按相似度降序排列。
        """
        if not keywords or self._semantic.count_triples() == 0:
            return []

        # 收集所有关键词的联合结构指纹
        all_in_preds: Set[str] = set()
        all_out_preds: Set[str] = set()
        matched_nodes: Set[str] = set()

        for kw in keywords:
            if kw in self._semantic.graph:
                matched_nodes.add(kw)
                in_p, out_p = _predicate_sets(self._semantic, kw)
                all_in_preds.update(in_p)
                all_out_preds.update(out_p)

        if not all_in_preds and not all_out_preds:
            return []

        target_in = frozenset(all_in_preds)
        target_out = frozenset(all_out_preds)

        # 在图谱中搜索具有相似谓词模式的其他节点
        candidates: List[Tuple[str, float]] = []
        for node in self._semantic.graph.nodes():
            if node in matched_nodes:
                continue
            node_in, node_out = _predicate_sets(self._semantic, node)
            if not node_in and not node_out:
                continue
            in_sim = _jaccard(target_in, node_in)
            out_sim = _jaccard(target_out, node_out)
            # 综合相似度：入边 + 出边，入边权重略高
            sim = in_sim * 0.6 + out_sim * 0.4
            if sim >= self._min_similarity:
                candidates.append((node, sim))

        candidates.sort(key=lambda x: -x[1])
        results: List[Tuple[str, float, str]] = []
        for node, sim in candidates[:max_results]:
            sig = self.structural_signature(node)
            desc = f"入: {', '.join(sig['in_predicates'][:3]) or '无'} | 出: {', '.join(sig['out_predicates'][:3]) or '无'}"
            results.append((node, sim, desc))
        return results

    def analogy_keywords(
        self, keywords: List[str], max_analogies: int = 3,
    ) -> List[str]:
        """返回类比节点的名称列表（可直接作为扩展关键词使用）。"""
        nodes = self.find_analogous_nodes(keywords, max_results=max_analogies)
        return [node for node, _, __ in nodes]
