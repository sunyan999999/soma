"""v0.8.0 任务2: 记忆冲突检测测试"""
import hashlib
import numpy as np
import pytest
from pathlib import Path

from soma.config import SOMAConfig
from soma.base import Focus, MemoryUnit, ActivatedMemory
from soma.memory.core import MemoryCore
from soma.hub._conflict import ConflictDetector


class MockEmbedder:
    """基于字符三元组哈希的确定性模拟嵌入器。

    相似文本共享更多三元组 → 余弦相似度更高。
    不同话题的文本几乎不共享三元组 → 余弦相似度接近 0。
    使用 hashlib 确保确定性向量。
    """

    def __init__(self, dim: int = 128):
        self._dim = dim

    def encode(self, text: str) -> np.ndarray:
        vec = np.zeros(self._dim, dtype=np.float32)
        for i in range(len(text) - 2):
            trigram = text[i:i + 3]
            h = int(hashlib.md5(trigram.encode()).hexdigest(), 16) % self._dim
            vec[h] += 1.0
        norm = np.linalg.norm(vec)
        if norm > 1e-10:
            vec = vec / norm
        return vec

    def encode_batch(self, texts):
        return np.array([self.encode(t) for t in texts])

    @property
    def dimension(self):
        return self._dim


@pytest.fixture
def embedder():
    return MockEmbedder(128)


@pytest.fixture
def memory(tmp_path: Path, embedder):
    config = SOMAConfig(
        episodic_persist_dir=tmp_path / "data",
        use_vector_search=True,
    )
    return MemoryCore(config, embedder=embedder)


@pytest.fixture
def detector(memory):
    return ConflictDetector(memory._embedder)


class TestConflictDetector:
    def make_am(self, content: str, source: str = "episodic", importance: float = 0.8) -> ActivatedMemory:
        """快捷构造 ActivatedMemory"""
        return ActivatedMemory(
            memory=MemoryUnit(
                id="test_" + content[:8],
                content=content,
                context={},
                importance=importance,
                memory_type=source,
            ),
            activation_score=0.7,
            source=source,
            match_rationale="测试",
        )

    def test_no_conflict_similar_opinions(self, detector):
        """相似但不矛盾的观点不应检测为冲突"""
        a = self.make_am("价格是客户流失的主要原因，竞争者的价格更低")
        b = self.make_am("价格对客户流失有重要影响，但不是唯一因素")
        score = detector.conflict_score(a, b)
        assert score < 0.5

    def test_conflict_direct_contradiction(self, detector):
        """直接矛盾的记忆应检测为冲突"""
        a = self.make_am("价格是客户流失的主要原因")
        b = self.make_am("价格不是客户流失的原因，服务质量才是主要问题")
        score = detector.conflict_score(a, b)
        assert score >= 0.24  # 应检测到一定程度的矛盾（否定模式 + 话题相似）

    def test_no_conflict_different_topics(self, detector):
        """完全不同话题的记忆不应有冲突"""
        a = self.make_am("价格是客户流失的主要原因")
        b = self.make_am("天气模式影响农产品产量")
        score = detector.conflict_score(a, b)
        assert score < 0.3

    def test_find_conflicts_empty(self, detector):
        """空列表不报错"""
        conflicts = detector.find_conflicts([])
        assert conflicts == []

    def test_find_conflicts_single(self, detector):
        """单条记忆不报错"""
        conflicts = detector.find_conflicts([self.make_am("测试")])
        assert conflicts == []

    def test_conflict_score_range(self, detector):
        """冲突分数应在 [0, 1] 范围内"""
        a = self.make_am("测试A")
        b = self.make_am("测试B")
        score = detector.conflict_score(a, b)
        assert 0.0 <= score <= 1.0

    def test_semantic_triple_conflict(self, memory):
        """三元素存储中的直接矛盾应被检测"""
        memory.remember_semantic("价格", "causes", "客户流失")
        memory.remember_semantic("价格", "prevents", "客户流失")

        detector_with_graph = ConflictDetector(
            memory._embedder, semantic_store=memory.semantic,
        )
        triples1 = [
            {"subject": "价格", "predicate": "causes", "object": "客户流失"},
        ]
        triples2 = [
            {"subject": "价格", "predicate": "prevents", "object": "客户流失"},
        ]
        score = detector_with_graph.triple_conflict_score(triples1, triples2)
        assert score > 0.5  # 同一 subject/object 但 predicate 冲突
