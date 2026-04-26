"""ABC 注册验证 — 确保所有核心组件正确继承抽象基类"""
import pytest
import numpy as np

from soma.abc import BaseMemoryStore, BaseEmbedder, BaseFrameworkEngine, BaseLLM


class TestABCRegistration:
    def test_abc_cannot_instantiate(self):
        # BaseMemoryStore: count() is abstract, so instantiation fails
        with pytest.raises(TypeError):
            BaseMemoryStore()

        with pytest.raises(TypeError):
            BaseEmbedder()

        with pytest.raises(TypeError):
            BaseFrameworkEngine()

        with pytest.raises(TypeError):
            BaseLLM()

    def test_base_memory_store_defaults(self):
        """store/query/delete 有默认实现，子类不强制覆写"""

        class MinimalStore(BaseMemoryStore):
            def count(self) -> int:
                return 0

        store = MinimalStore()
        assert store.count() == 0
        with pytest.raises(NotImplementedError):
            store.store("test")
        with pytest.raises(NotImplementedError):
            store.query("test")

    def test_base_embedder_contract(self):
        """BaseEmbedder 定义了完整契约"""

        class DummyEmbedder(BaseEmbedder):
            def encode(self, text: str) -> np.ndarray:
                return np.zeros(512, dtype=np.float32)

            def encode_batch(self, texts):
                return np.zeros((len(texts), 512), dtype=np.float32)

            @property
            def dimension(self) -> int:
                return 512

        e = DummyEmbedder()
        assert e.dimension == 512
        v = e.encode("hello")
        assert v.shape == (512,)
        batch = e.encode_batch(["a", "b"])
        assert batch.shape == (2, 512)

    def test_base_llm_contract(self):
        """BaseLLM 定义了完整契约"""

        class DummyLLM(BaseLLM):
            def complete(self, prompt: str) -> str:
                return f"echo: {prompt}"

            def complete_stream(self, prompt: str):
                for ch in prompt:
                    yield ch

        llm = DummyLLM()
        assert llm.complete("hi") == "echo: hi"
        assert list(llm.complete_stream("ab")) == ["a", "b"]
