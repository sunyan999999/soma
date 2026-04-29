from typing import Dict, List, Set

from soma.base import ActivatedMemory


def _bigram_set(text: str) -> Set[str]:
    text = text.lower()
    return {text[i:i+2] for i in range(len(text) - 1)} if len(text) >= 2 else {text}


def _jaccard_from_sets(sa: Set[str], sb: Set[str]) -> float:
    """基于预计算 bigram 集合的 Jaccard 相似度"""
    if not sa or not sb:
        return 0.0
    intersection = len(sa & sb)
    # |A ∪ B| = |A| + |B| - |A ∩ B| — 避免构造并集临时对象
    union = len(sa) + len(sb) - intersection
    return intersection / union if union > 0 else 0.0


class MMRRanker:
    """MMR 多样性重排器 — 平衡相关性与内容/来源多样性"""

    def __init__(self, mmr_lambda: float = 0.7):
        self.mmr_lambda = mmr_lambda

    def rerank(
        self, pool: List[ActivatedMemory], k: int, threshold: float,
        mmr_lambda: float | None = None,
    ) -> List[ActivatedMemory]:
        """MMR 贪心选择 + 阈值过滤，返回 Top-K"""
        lam = mmr_lambda if mmr_lambda is not None else self.mmr_lambda
        selected = self._mmr_select(pool, k, lam)
        return [am for am in selected if am.activation_score >= threshold]

    def _mmr_select(
        self, pool: List[ActivatedMemory], k: int, lam: float,
    ) -> List[ActivatedMemory]:
        if k >= len(pool):
            return pool

        selected: List[ActivatedMemory] = []
        remaining = list(pool)

        # 预计算所有候选记忆的 bigram 集合，避免 MMR 循环内重复构建
        bigram_cache: Dict[str, Set[str]] = {
            am.memory.id: _bigram_set(am.memory.content) for am in pool
        }

        max_score = max(am.activation_score for am in remaining) or 1.0
        source_bonus = 0.15

        first = remaining.pop(0)
        selected.append(first)
        covered_sources: Set[str] = {first.source}

        while len(selected) < k and remaining:
            best_idx = -1
            best_mmr = -1.0

            for i, am in enumerate(remaining):
                rel = am.activation_score / max_score
                am_bigrams = bigram_cache[am.memory.id]
                max_sim = max(
                    _jaccard_from_sets(am_bigrams, bigram_cache[s.memory.id])
                    for s in selected
                )
                if max_sim > 0.88:
                    continue
                src_div = source_bonus if am.source not in covered_sources else 0.0
                mmr = lam * rel - (1 - lam) * max_sim + src_div

                if mmr > best_mmr:
                    best_mmr = mmr
                    best_idx = i

            if best_idx < 0 or best_mmr < 0:
                break
            chosen = remaining.pop(best_idx)
            covered_sources.add(chosen.source)
            selected.append(chosen)

        return selected
