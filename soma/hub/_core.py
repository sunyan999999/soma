from typing import Dict, List, Optional, Tuple

from soma.base import ActivatedMemory, Focus
from soma.hub._conflict import ConflictDetector
from soma.hub._frame_detector import FrameAnchoringDetector
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
        conflict_detector=None,
        frame_detector=None,
    ):
        self.top_k = top_k
        self.threshold = threshold
        self.mmr_lambda = mmr_lambda
        self.retriever = retriever or MemoryRetriever(memory_core)
        self.scorer = scorer or RelevanceScorer()
        self.ranker = ranker or MMRRanker(mmr_lambda)
        self.conflict_detector = conflict_detector or ConflictDetector(
            memory_core._embedder,
        )
        self.frame_detector = frame_detector or FrameAnchoringDetector(
            window=5,
        )
        # 最近一次激活检测到的冲突对
        self.last_conflicts: List[Tuple[ActivatedMemory, ActivatedMemory, float]] = []

    def activate(self, foci: List[Focus], user_id: str = "", laws=None,
                 agent_id: str = "", group_id: str = "") -> List[ActivatedMemory]:
        """
        双向激活：对每个 Focus 查询 MemoryCore，全局合并排序。

        1. 每个 Focus 过取 top_k * 2 条结果
        2. 计算 activation_score = focus.weight × memory.relevance_potential()
        3. 多 Focus 命中的记忆获得 0.5× 叠加加成
        4. 按分数降序排列
        5. MMR 多样性重排 + 阈值过滤，返回 Top-K
        6. v0.8.0: 冲突检测降权 + 记忆→焦点反向传播
        """
        candidates: Dict[str, list] = {}

        for focus in foci:
            results = self.retriever.retrieve(
                focus, top_k=self.top_k * 2, user_id=user_id,
                agent_id=agent_id, group_id=group_id,
            )

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

        # v0.8.0: 冲突检测 — 仅在完整框架会话中运行，简单查询跳过
        if laws:
            conflicts = self.conflict_detector.find_conflicts(mmr_pool)
            self.last_conflicts = conflicts
            if conflicts:
                penalized: set = set()
                for am_a, am_b, conflict_score in conflicts:
                    penalty = 1.0 - conflict_score * 0.4
                    if id(am_a) not in penalized:
                        am_a.activation_score *= penalty
                        penalized.add(id(am_a))
                    if id(am_b) not in penalized:
                        am_b.activation_score *= penalty
                        penalized.add(id(am_b))
                mmr_pool.sort(key=lambda am: am.activation_score, reverse=True)

        results = self.ranker.rerank(
            mmr_pool, self.top_k, self.threshold, self.mmr_lambda,
        )

        # v0.8.0: 反向传播 — 高激活记忆建议新的思维焦点
        if laws:
            self._backward_propagate(results, laws)

        return results

    def _backward_propagate(self, activated: List[ActivatedMemory], laws) -> None:
        """记忆→焦点反向传播：高激活记忆的领域标签映射到思维规律。

        限制：建议权重不超过任一直接触发规律权重的 50%。
        """
        if not laws:
            return
        max_weight = max((l.weight for l in laws), default=1.0)
        for am in activated:
            domain = (am.memory.context or {}).get("domain", "")
            if not domain or am.activation_score < 0.4:
                continue
            for law in laws:
                if any(domain in t or t in domain for t in law.triggers):
                    suggestion_weight = min(
                        law.weight * 0.5 * am.activation_score,
                        max_weight * 0.5,
                    )
                    am.suggested_focus = Focus(
                        law_id=law.id,
                        dimension=f"记忆反馈：{am.memory.content[:60]} → 建议从「{law.name}」角度审视",
                        keywords=[domain] + law.triggers[:3],
                        weight=suggestion_weight,
                        rationale=f"高激活记忆(领域: {domain})反向激活",
                    )
                    break

    def anti_confirmation_search(
        self, foci: List[Focus], user_id: str = "",
        agent_id: str = "", group_id: str = "",
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
                    agent_id=agent_id, group_id=group_id,
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

    def causal_analyze(self, foci: List[Focus]) -> Dict:
        """当 systems_thinking 律激活时，执行因果推理分析。

        从聚焦点关键词中提取匹配图谱节点的概念，
        找出根因节点和因果链，返回结构化因果上下文。
        """
        result: Dict = {"root_causes": {}, "chains": [], "cycles": []}
        has_systems = any(
            f.law_id == "systems_thinking" for f in foci
        )
        if not has_systems:
            return result

        cg = self.retriever.memory.get_causal_graph()
        edges = cg.get_causal_edges()
        if not edges:
            return result

        all_keywords = set()
        for f in foci:
            all_keywords.update(f.keywords)
        # O(K) 查找避免 O(N) 全图遍历
        graph = cg.store.graph
        matched = [kw for kw in all_keywords if kw in graph]

        for node in matched:
            roots = cg.find_root_causes(node)
            if roots:
                result["root_causes"][node] = roots

        # 如果匹配了多个概念，尝试找它们之间的因果路径
        if len(matched) >= 2:
            for i, a in enumerate(matched):
                for b in matched[i + 1:]:
                    chain = cg.get_causal_chain(a, b)
                    if chain:
                        result["chains"].append({"from": a, "to": b, "path": chain})

        # 检测因果环路
        cycles = cg.detect_cycles()
        if cycles:
            result["cycles"] = [
                " → ".join(c) for c in cycles[:5]
            ]

        return result

    def explain_activation(self, activated: ActivatedMemory) -> Dict:
        """返回激活记忆的详细解释信息"""
        mem = activated.memory
        info = {
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
        if activated.suggested_focus:
            sf = activated.suggested_focus
            info["suggested_focus"] = {
                "law_id": sf.law_id,
                "dimension": sf.dimension,
                "weight": sf.weight,
                "rationale": sf.rationale,
            }
        return info

    def detect_frame_anchoring(self, recent_turns: List[str]) -> Optional[dict]:
        """检测用户是否过度锁定在单一认知框架中（v0.9.1）。

        Args:
            recent_turns: 最近 N 轮用户输入文本列表（最新的在末尾）

        Returns:
            None 或 {"dominant_frame": str, "ratio": float, "reflection": str}
        """
        if self.frame_detector is None:
            return None
        try:
            return self.frame_detector.detect(recent_turns)
        except Exception:
            # G1: 错误隔离 — 检测器异常不得传播到核心管道
            return None
