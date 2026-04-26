"""ABC 注册验证 — 确保所有核心组件正确继承抽象基类"""
import pytest

from soma.abc import BaseMemoryStore, BaseEmbedder, BaseFrameworkEngine
from soma.embedder import SOMAEmbedder
from soma.engine import WisdomEngine
from soma.memory.episodic import EpisodicStore
from soma.memory.semantic import SemanticStore
from soma.memory.skill import SkillStore
from soma.config import SOMAConfig


class TestABCRegistration:
    def test_episodic_is_base_memory_store(self):
        assert issubclass(EpisodicStore, BaseMemoryStore)

    def test_semantic_is_base_memory_store(self):
        assert issubclass(SemanticStore, BaseMemoryStore)

    def test_skill_is_base_memory_store(self):
        assert issubclass(SkillStore, BaseMemoryStore)

    def test_embedder_is_base_embedder(self):
        assert issubclass(SOMAEmbedder, BaseEmbedder)

    def test_engine_is_base_framework_engine(self):
        assert issubclass(WisdomEngine, BaseFrameworkEngine)

    def test_abc_cannot_instantiate(self):
        with pytest.raises(TypeError):
            BaseMemoryStore()

        with pytest.raises(TypeError):
            BaseEmbedder()

        with pytest.raises(TypeError):
            BaseFrameworkEngine()
