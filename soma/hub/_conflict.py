"""v0.8.0 记忆冲突检测 — 在检索后识别潜在矛盾并降权。

原理：
1. 嵌入向量余弦相似度 > 阈值 → 可能讨论同一话题
2. 话题相同但断言相悖（否定模式 + 三元素冲突）→ 标记为潜在矛盾
3. 冲突记忆在排序中被降权，并在响应 prompt 中注入警告
"""

from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from soma.base import ActivatedMemory


class ConflictDetector:
    """记忆冲突检测器。

    在 ActivationHub 的激活结果返回后、排序前运行。
    检测高相似度记忆中是否存在逻辑矛盾。
    """

    # 否定模式词（中英文）
    NEGATION_PATTERNS = [
        "不是", "并非", "没有", "不会", "并非如此", "错误",
        "不对", "并非因为", "并非由于", "无关",
        "not", "no", "never", "isn't", "aren't", "wasn't",
        "weren't", "doesn't", "don't", "didn't", "won't",
    ]

    # 冲突谓词对：(正向, 反向)
    CONFLICTING_PREDICATES = [
        ({"causes", "leads_to", "increases", "contributes_to"},
         {"prevents", "blocks", "decreases", "reduces"}),
    ]

    def __init__(self, embedder):
        self._embedder = embedder
        self._similarity_threshold = 0.3
        self._conflict_threshold = 0.5

    def _encode(self, text: str) -> np.ndarray:
        if self._embedder is None:
            return np.array([])
        try:
            return np.array(self._embedder.encode(text))
        except Exception:
            return np.array([])

    def _encode_batch(self, texts: List[str]) -> List[np.ndarray]:
        """批量编码多条文本，单次 ONNX 推理替代逐条调用"""
        if self._embedder is None or not texts:
            return [np.array([])] * len(texts)
        try:
            vecs = self._embedder.encode_batch(texts)
            return [np.asarray(v, dtype=np.float32) for v in vecs]
        except Exception:
            return [np.array([]) for _ in texts]

    def _cosine_sim(self, a: np.ndarray, b: np.ndarray) -> float:
        if len(a) == 0 or len(b) == 0:
            return 0.0
        a_norm = a / (np.linalg.norm(a) + 1e-10)
        b_norm = b / (np.linalg.norm(b) + 1e-10)
        return float(np.dot(a_norm, b_norm))

    def _has_negation(self, text: str) -> bool:
        """检查文本是否包含否定模式"""
        text_lower = text.lower()
        return any(pat in text_lower for pat in self.NEGATION_PATTERNS)

    def conflict_score(
        self, am1: ActivatedMemory, am2: ActivatedMemory,
        emb1: Optional[np.ndarray] = None,
        emb2: Optional[np.ndarray] = None,
    ) -> float:
        """计算两条激活记忆之间的冲突分数 [0, 1]。

        0 = 无冲突（不同话题或观点一致）
        1 = 强烈矛盾（同一话题但断言完全相反）

        可传入预编码的嵌入向量避免重复编码。
        """
        t1, t2 = am1.memory.content, am2.memory.content

        if emb1 is None:
            emb1 = self._encode(t1)
        if emb2 is None:
            emb2 = self._encode(t2)
        if len(emb1) == 0 or len(emb2) == 0:
            return 0.0

        topic_sim = self._cosine_sim(emb1, emb2)
        if topic_sim < self._similarity_threshold:
            return 0.0

        neg1 = self._has_negation(t1)
        neg2 = self._has_negation(t2)

        if neg1 != neg2:
            return topic_sim * 0.8
        elif neg1 and neg2:
            return topic_sim * 0.2
        else:
            return topic_sim * 0.15

    def triple_conflict_score(
        self,
        triples1: List[Dict[str, str]],
        triples2: List[Dict[str, str]],
    ) -> float:
        """检测两组三元素之间的谓词冲突。

        例如: (价格, causes, 客户流失) vs (价格, prevents, 客户流失) → 高冲突
        """
        if not triples1 or not triples2:
            return 0.0

        max_conflict = 0.0
        for t1 in triples1:
            for t2 in triples2:
                if (t1.get("subject") == t2.get("subject")
                        and t1.get("object") == t2.get("object")):
                    p1 = t1.get("predicate", "").lower()
                    p2 = t2.get("predicate", "").lower()
                    if p1 != p2:
                        for pos_set, neg_set in self.CONFLICTING_PREDICATES:
                            if (p1 in pos_set and p2 in neg_set) or \
                               (p1 in neg_set and p2 in pos_set):
                                max_conflict = max(max_conflict, 0.9)
                            elif p1 != p2:
                                max_conflict = max(max_conflict, 0.5)
        return max_conflict

    def find_conflicts(
        self, activated: List[ActivatedMemory],
    ) -> List[Tuple[ActivatedMemory, ActivatedMemory, float]]:
        """在激活记忆列表中查找冲突对。

        返回 [(am_a, am_b, conflict_score), ...]，按冲突分数降序排列。
        预编码所有文本避免重复 ONNX 推理 —— 每条记忆只编码一次。
        """
        n = len(activated)
        if n < 2:
            return []

        # 批量编码：单次 ONNX 推理替代逐条编码，大幅降低延迟
        texts = [am.memory.content for am in activated]
        embeddings = self._encode_batch(texts)

        conflicts = []
        for i in range(n):
            emb_i = embeddings[i]
            if len(emb_i) == 0:
                continue
            for j in range(i + 1, n):
                emb_j = embeddings[j]
                if len(emb_j) == 0:
                    continue
                score = self.conflict_score(
                    activated[i], activated[j],
                    emb1=emb_i, emb2=emb_j,
                )
                if score >= self._conflict_threshold:
                    conflicts.append((activated[i], activated[j], score))

        conflicts.sort(key=lambda x: -x[2])
        return conflicts
