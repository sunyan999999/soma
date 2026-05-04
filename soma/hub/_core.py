from typing import Dict, List

from soma.base import ActivatedMemory, Focus
from soma.hub._retriever import MemoryRetriever
from soma.hub._scorer import RelevanceScorer
from soma.hub._ranker import MMRRanker


class ActivationHub:
    """双向激活调度器 — 计算关联潜力并返回 Top-K 相关记忆

    可通过 retriever / scorer / ranker 参数注入自定义实现，
    也可通过 pyproject.toml [project.entry-points."soma.plugins"] 注册。
    """

    def __init__(
        self,
        memory_core,
        top_k: int = 5,
        threshold: float = 0.3,
        mmr_lambda: float = 0.7,
        retriever=None,
        scorer=None,
        ranker=None,
    ):
        self.top_k = top_k
        self.threshold = threshold
        self.mmr_lambda = mmr_lambda
        self.retriever = retriever or MemoryRetriever(memory_core)
        self.scorer = scorer or RelevanceScorer()
        self.ranker = ranker or MMRRanker(mmr_lambda)

    def activate(self, foci: List[Focus], user_id: str = "") -> List[ActivatedMemory]:
        """
        双向激活：对每个 Focus 查询 MemoryCore，全局合并排序。

        1. 每个 Focus 过取 top_k * 2 条结果
        2. 计算 activation_score = focus.weight × memory.relevance_potential()
        3. 多 Focus 命中的记忆获得 0.5× 叠加加成
        4. 按分数降序排列
        5. MMR 多样性重排 + 阈值过滤，返回 Top-K
        """
        candidates: Dict[str, list] = {}

        for focus in foci:
            results = self.retriever.retrieve(focus, top_k=self.top_k * 2, user_id=user_id)

            for am in results:
                mid = am.memory.id
                score = self.scorer.compute_score(focus, am)
                if mid not in candidates:
                    am.activation_score = score
                    candidates[mid] = [am, 1]
                else:
                    prev_am, count = candidates[mid]
                    prev_am.activation_score += score * 0.5
                    candidates[mid] = [prev_am, count + 1]

        all_activated = [entry[0] for entry in candidates.values()]
        all_activated.sort(key=lambda am: am.activation_score, reverse=True)

        # MMR 多样性重排：在较宽的候选池上运行，最后再阈值过滤
        mmr_pool_size = (
            max(self.top_k, len(all_activated))
            if len(all_activated) <= self.top_k * 3
            else self.top_k * 3
        )
        mmr_pool = all_activated[:mmr_pool_size]

        return self.ranker.rerank(
            mmr_pool, self.top_k, self.threshold, self.mmr_lambda,
        )

    def anti_confirmation_search(
        self, foci: List[Focus], user_id: str = "",
    ) -> List[ActivatedMemory]:
        """确认偏误检测：为每个聚焦点构造反视角查询，检索反对证据。

        对每个 Focus，用否定词构造反查询（如"不是""反对""反面"），
        从记忆库中检索可能矛盾的记忆片段。
        返回反对视角的记忆列表，供 Prompt 合成时注入。
        """
        from soma.base import Focus as F

        negation_words = ["不是", "反对", "反面", "并非", "错误"]
        anti_memories: Dict[str, ActivatedMemory] = {}

        for focus in foci:
            anti_keywords = focus.keywords[:3] if focus.keywords else []
            if not anti_keywords:
                continue
            for neg in negation_words[:3]:
                anti_dimension = f"反对视角：{neg} {' '.join(anti_keywords)}"
                anti_focus = F(
                    law_id=f"{focus.law_id}_anti",
                    dimension=anti_dimension,
                    keywords=[neg] + anti_keywords,
                    weight=focus.weight * 0.5,
                    rationale=f"确认偏误检测（源于: {focus.law_id}）",
                )
                for am in self.retriever.retrieve(
                    anti_focus, top_k=2, user_id=user_id,
                ):
                    mid = am.memory.id
                    if mid not in anti_memories:
                        am.activation_score = am.memory.relevance_potential() * 0.6
                        am.match_rationale = f"反视角检索（查询: {anti_dimension[:60]}）"
                        anti_memories[mid] = am

        sorted_anti = sorted(
            anti_memories.values(),
            key=lambda am: am.activation_score, reverse=True,
        )
        return sorted_anti[:self.top_k]

    def explain_activation(self, activated: ActivatedMemory) -> Dict:
        """返回激活记忆的详细解释信息"""
        mem = activated.memory
        return {
            "memory_id": mem.id,
            "content_preview": mem.content[:200],
            "content": mem.content,
            "activation_score": activated.activation_score,
            "source": activated.source,
            "match_rationale": activated.match_rationale,
            "relevance_potential": mem.relevance_potential(),
            "importance": mem.importance,
            "context": getattr(mem, "context", {}) or {},
            "access_count": mem.access_count,
        }
