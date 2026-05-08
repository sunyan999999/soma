from typing import Any, Dict, List, Optional, Set

from soma.base import RECENCY_HALF_LIFE_DAYS, ActivatedMemory, Focus, MemoryUnit
from soma.config import SOMAConfig
from soma.memory.causal import CausalGraph
from soma.memory.episodic import EpisodicStore
from soma.memory.semantic import SemanticStore
from soma.memory.skill import SkillStore


class MemoryCore:
    """统一记忆存储门面"""

    def __init__(
        self,
        config: SOMAConfig,
        embedder=None,
    ):
        use_vector = config.use_vector_search and embedder is not None
        self.episodic = EpisodicStore(
            config.episodic_persist_dir,
            embedder=embedder,
            use_vector_search=use_vector,
        )
        self.semantic = SemanticStore(config.episodic_persist_dir)
        self.skill = SkillStore(config.episodic_persist_dir)
        self._embedder = embedder

    def remember(
        self,
        content: str,
        context: Optional[Dict[str, Any]] = None,
        importance: float = 0.5,
        user_id: str = "",
        session_id: str = "",
    ) -> str:
        """存储情节记忆"""
        return self.episodic.add(content, context, importance, user_id=user_id, session_id=session_id)

    def remember_semantic(
        self,
        subject: str,
        predicate: str,
        object_: str,
        confidence: float = 1.0,
        namespace: str = "",
    ) -> None:
        """存储语义三元组"""
        self.semantic.add_triple(subject, predicate, object_, confidence, namespace=namespace)

    def _expand_via_semantic_graph(self, keywords: List[str], max_terms: int = 8) -> List[str]:
        """通过语义图谱扩展关键词：从匹配节点沿图遍历获取邻居概念。

        对于出现在语义图谱中的关键词，沿边遍历获取相关概念作为扩展搜索词。
        扩展词用于增强情节记忆的关键词检索——打破检索孤岛。
        """
        if not keywords or self.semantic.count_triples() == 0:
            return []
        # 找出在图中有匹配节点的关键词
        graph_nodes = set(self.semantic.list_nodes())
        matched = [kw for kw in keywords if kw in graph_nodes]
        if not matched:
            return []
        expanded = self.semantic.expand_query_terms(matched, depth=2, max_terms=max_terms)
        # 排除已是原始关键词的扩展词
        return [t for t in expanded if t not in keywords]

    def _hybrid_search(
        self, focus: Focus, top_k: int,
        user_id: str = "",
        graph_keywords: Optional[List[str]] = None,
    ) -> List[ActivatedMemory]:
        """混合搜索：加权 RRF 融合 + 时间衰减因子 + 图谱扩展关键词"""
        import math
        import time as _time
        keywords = focus.keywords
        rrf_k = 60
        now_ts = _time.time()

        # 1. 向量语义搜索（更多候选，带用户隔离）
        query_vec = self._embedder.encode(focus.dimension)
        vec_results = self.episodic.query_by_vector(query_vec, top_k * 3, user_id=user_id)
        vec_rank = {mem.id: i + 1 for i, mem in enumerate(vec_results)}
        vec_mem = {mem.id: mem for mem in vec_results}

        # 2. 关键词精确匹配（带用户隔离和时间窗口）
        kw_results = self.episodic.query_by_keywords(keywords, top_k * 3, user_id=user_id)
        kw_rank = {mem.id: i + 1 for i, mem in enumerate(kw_results)}
        kw_mem = {mem.id: mem for mem in kw_results}

        # 2.5 图谱扩展关键词检索（权重低于直接匹配）
        graph_kw_rank: Dict[str, int] = {}
        graph_kw_mem: Dict[str, MemoryUnit] = {}
        if graph_keywords:
            gk_results = self.episodic.query_by_keywords(
                graph_keywords, top_k * 2, user_id=user_id,
            )
            graph_kw_rank = {mem.id: i + 1 for i, mem in enumerate(gk_results)}
            graph_kw_mem = {mem.id: mem for mem in gk_results}

        # 3. 加权 RRF 融合 + 时间衰减因子
        # RRF base: 向量权重 ×2, 关键词 ×1, 图谱扩展词 ×0.5
        all_ids = set(vec_rank.keys()) | set(kw_rank.keys()) | set(graph_kw_rank.keys())
        rrf_scores = {}
        for mid in all_ids:
            score = 0.0
            if mid in vec_rank:
                score += 2.0 / (rrf_k + vec_rank[mid])
            if mid in kw_rank:
                score += 1.0 / (rrf_k + kw_rank[mid])
            if mid in graph_kw_rank:
                score += 0.5 / (rrf_k + graph_kw_rank[mid])
            # 时间衰减因子
            mem = vec_mem.get(mid) or kw_mem.get(mid) or graph_kw_mem.get(mid)
            if mem is not None:
                days = (now_ts - mem.timestamp) / 86400.0
                time_penalty = math.exp(-max(days, 0) / RECENCY_HALF_LIFE_DAYS)
                score *= time_penalty
            rrf_scores[mid] = score

        # 4. 按 RRF 分数降序排列
        ranked = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        ranked = ranked[:top_k]

        # 5. 构建 ActivatedMemory
        all_mem = {**vec_mem, **kw_mem, **graph_kw_mem}
        activated = []
        for mid, rrf_score in ranked:
            mem = all_mem.get(mid)
            if mem is None:
                continue
            in_vec = mid in vec_rank
            in_kw = mid in kw_rank
            in_graph = mid in graph_kw_rank
            parts = []
            if in_vec and in_kw:
                parts.append(f"混合匹配(RRF): {rrf_score:.4f}")
            elif in_vec:
                vec_score = mem.context.pop("_vector_score", 0)
                parts.append(f"语义相似度: {vec_score:.4f}")
            elif in_kw:
                matched = [kw for kw in keywords if kw.lower() in mem.content.lower()]
                parts.append(f"关键词: {', '.join(matched[:3])}")
            if in_graph and graph_keywords:
                matched_gk = [kw for kw in graph_keywords if kw.lower() in mem.content.lower()]
                if matched_gk:
                    parts.append(f"图谱扩展: {', '.join(matched_gk[:2])}")
            activated.append(
                ActivatedMemory(
                    memory=mem,
                    activation_score=0.0,
                    source="episodic",
                    match_rationale="; ".join(parts) if parts else "匹配",
                )
            )

        return activated

    def query(
        self, focus: Focus, top_k: int = 5,
        user_id: str = "",
    ) -> List[ActivatedMemory]:
        """对单个 Focus 跨三个子库查询，返回 ActivatedMemory 列表

        支持可选 user_id 隔离：传入时仅检索该用户的记忆，不传入时检索全部（向后兼容）。

        v0.8.0: 通过语义图谱扩展关键词，打破检索孤岛。
        """
        keywords = focus.keywords

        # v0.8.0: 语义图谱扩展关键词 — 邻居概念参与检索
        graph_keywords = self._expand_via_semantic_graph(keywords)
        all_keywords = list(dict.fromkeys(keywords + graph_keywords))

        # 查询情节记忆 — 混合搜索或关键词
        if self.episodic.use_vector and self._embedder is not None:
            activated = self._hybrid_search(
                focus, top_k, user_id=user_id, graph_keywords=graph_keywords,
            )
        else:
            activated: List[ActivatedMemory] = []
            episodic_results = self.episodic.query_by_keywords(
                all_keywords, top_k, user_id=user_id,
            )
            for mem in episodic_results:
                matched = [kw for kw in all_keywords if kw.lower() in mem.content.lower()]
                activated.append(
                    ActivatedMemory(
                        memory=mem,
                        activation_score=0.0,
                        source="episodic",
                        match_rationale=f"关键词匹配: {', '.join(matched[:3])}",
                    )
                )

        # 查询语义记忆（namespace = user_id 实现隔离）
        semantic_results = self.semantic.query_by_keywords(
            all_keywords, top_k, namespace=user_id,
        )
        for mem in semantic_results:
            matched = [kw for kw in all_keywords if kw.lower() in mem.content.lower()]
            activated.append(
                ActivatedMemory(
                    memory=mem,
                    activation_score=0.0,
                    source="semantic",
                    match_rationale=f"图谱匹配: {', '.join(matched[:3])}",
                )
            )

        # 查询技能记忆（user_id 隔离）
        skill_results = self.skill.query_by_keywords(all_keywords, top_k, user_id=user_id)
        for mem in skill_results:
            activated.append(
                ActivatedMemory(
                    memory=mem,
                    activation_score=0.0,
                    source="skill",
                    match_rationale="技能模式匹配",
                )
            )

        # v0.8.0: 跨域类比 — 直接检索结果稀疏时触发
        episodic_count = sum(1 for am in activated if am.source == "episodic")
        if episodic_count < 3 and keywords:
            analogy_kw = self.get_analogy_engine().analogy_keywords(keywords, max_analogies=3)
            if analogy_kw:
                analogy_results = self.episodic.query_by_keywords(
                    analogy_kw, top_k=3, user_id=user_id,
                )
                for mem in analogy_results:
                    activated.append(
                        ActivatedMemory(
                            memory=mem,
                            activation_score=0.0,
                            source="analogy",
                            match_rationale=f"跨域类比: {', '.join(analogy_kw[:3])}",
                        )
                    )

        return activated

    def get_causal_graph(self) -> CausalGraph:
        """返回因果推理图（惰性构建）"""
        return CausalGraph(self.semantic)

    def get_analogy_engine(self):
        """返回跨域类比引擎（惰性构建）"""
        from soma.analogy import AnalogyEngine
        return AnalogyEngine(self.semantic)

    def query_root_causes(self, node: str, max_depth: int = 10) -> List[str]:
        """因果根因分析：找出 node 的所有根因节点"""
        return self.get_causal_graph().find_root_causes(node, max_depth)

    def query_causal_chain(
        self, start: str, end: str, max_depth: int = 10,
    ) -> Optional[List[str]]:
        """查找 start→end 的因果路径"""
        return self.get_causal_graph().get_causal_chain(start, end, max_depth)

    def close(self) -> None:
        """关闭所有子存储的连接"""
        self.episodic.close()
        self.semantic.close()
        self.skill.close()

    def __enter__(self) -> "MemoryCore":
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def stats(self) -> Dict[str, int]:
        return {
            "episodic": self.episodic.count(),
            "semantic": self.semantic.count_triples(),
            "skill": self.skill.count(),
            "indexed_vectors": self.episodic.count_indexed(),
        }
