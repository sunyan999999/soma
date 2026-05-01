from typing import Any, Dict, List, Optional

from soma.base import ActivatedMemory, Focus, MemoryUnit
from soma.config import SOMAConfig
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

    def _hybrid_search(
        self, focus: Focus, top_k: int,
        user_id: str = "",
    ) -> List[ActivatedMemory]:
        """混合搜索：加权 RRF 融合 + 时间衰减因子"""
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

        # 3. 加权 RRF 融合 + 时间衰减因子
        # RRF base: 向量权重 ×2, 关键词 ×1
        # 同时施加时间衰减: exp(-days/7)，进一步压低远古记忆
        all_ids = set(vec_rank.keys()) | set(kw_rank.keys())
        rrf_scores = {}
        for mid in all_ids:
            score = 0.0
            if mid in vec_rank:
                score += 2.0 / (rrf_k + vec_rank[mid])
            if mid in kw_rank:
                score += 1.0 / (rrf_k + kw_rank[mid])
            # 时间衰减因子
            mem = vec_mem.get(mid) or kw_mem.get(mid)
            if mem is not None:
                days = (now_ts - mem.timestamp) / 86400.0
                time_penalty = math.exp(-max(days, 0) / 7.0)
                score *= time_penalty
            rrf_scores[mid] = score

        # 4. 按 RRF 分数降序排列
        ranked = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        ranked = ranked[:top_k]

        # 5. 构建 ActivatedMemory
        activated = []
        for mid, rrf_score in ranked:
            mem = vec_mem.get(mid) or kw_mem.get(mid)
            if mem is None:
                continue
            in_vec = mid in vec_rank
            in_kw = mid in kw_rank
            if in_vec and in_kw:
                rationale = f"混合匹配(RRF): {rrf_score:.4f}"
            elif in_vec:
                vec_score = mem.context.pop("_vector_score", 0)
                rationale = f"语义相似度: {vec_score:.4f}"
            else:
                matched = [kw for kw in keywords if kw.lower() in mem.content.lower()]
                rationale = f"关键词匹配: {', '.join(matched[:3])}"
            activated.append(
                ActivatedMemory(
                    memory=mem,
                    activation_score=0.0,
                    source="episodic",
                    match_rationale=rationale,
                )
            )

        return activated

    def query(
        self, focus: Focus, top_k: int = 5,
        user_id: str = "",
    ) -> List[ActivatedMemory]:
        """对单个 Focus 跨三个子库查询，返回 ActivatedMemory 列表

        支持可选 user_id 隔离：传入时仅检索该用户的记忆，不传入时检索全部（向后兼容）。
        """
        keywords = focus.keywords

        # 查询情节记忆 — 混合搜索或关键词
        if self.episodic.use_vector and self._embedder is not None:
            activated = self._hybrid_search(focus, top_k, user_id=user_id)
        else:
            activated: List[ActivatedMemory] = []
            episodic_results = self.episodic.query_by_keywords(keywords, top_k, user_id=user_id)
            for mem in episodic_results:
                matched = [kw for kw in keywords if kw.lower() in mem.content.lower()]
                activated.append(
                    ActivatedMemory(
                        memory=mem,
                        activation_score=0.0,
                        source="episodic",
                        match_rationale=f"关键词匹配: {', '.join(matched[:3])}",
                    )
                )

        # 查询语义记忆（namespace = user_id 实现隔离）
        semantic_results = self.semantic.query_by_keywords(keywords, top_k, namespace=user_id)
        for mem in semantic_results:
            matched = [kw for kw in keywords if kw.lower() in mem.content.lower()]
            activated.append(
                ActivatedMemory(
                    memory=mem,
                    activation_score=0.0,
                    source="semantic",
                    match_rationale=f"图谱匹配: {', '.join(matched[:3])}",
                )
            )

        # 查询技能记忆（user_id 隔离）
        skill_results = self.skill.query_by_keywords(keywords, top_k, user_id=user_id)
        for mem in skill_results:
            activated.append(
                ActivatedMemory(
                    memory=mem,
                    activation_score=0.0,
                    source="skill",
                    match_rationale="技能模式匹配",
                )
            )

        return activated

    def stats(self) -> Dict[str, int]:
        return {
            "episodic": self.episodic.count(),
            "semantic": self.semantic.count_triples(),
            "skill": self.skill.count(),
            "indexed_vectors": self.episodic.count_indexed(),
        }
