from unittest.mock import MagicMock

import numpy as np
import pytest

from soma.config import SOMAConfig
from soma.embedder import SOMAEmbedder


@pytest.fixture
def config():
    return SOMAConfig(
        embedding_model_name="BAAI/bge-small-zh-v1.5",
        vector_dim=512,
        embedder_device="cpu",
    )


@pytest.fixture
def embedder(config):
    return SOMAEmbedder(config)


def _inject_mock_model(embedder):
    """注入 mock 模型，绕过懒加载 — 模拟 fastembed API"""
    mock_model = MagicMock()
    # fastembed .embed() 返回生成器，每次 yield 一个 numpy 数组
    mock_model.embed.return_value = iter([np.ones(512, dtype=np.float32)])
    embedder._model = mock_model
    return mock_model


class TestSOMAEmbedder:
    def test_lazy_loading(self, embedder):
        assert embedder._model is None

    def test_encode_shape(self, embedder):
        mock_model = _inject_mock_model(embedder)

        vec = embedder.encode("测试文本")
        assert vec.shape == (512,)
        assert vec.dtype == np.float32

    def test_encode_batch_shape(self, embedder):
        mock_model = _inject_mock_model(embedder)
        # fastembed 批量返回：逐个 yield
        mock_model.embed.return_value = iter([
            np.ones(512, dtype=np.float32),
            np.ones(512, dtype=np.float32),
            np.ones(512, dtype=np.float32),
        ])

        vecs = embedder.encode_batch(["文本1", "文本2", "文本3"])
        assert vecs.shape == (3, 512)

    def test_dimension(self, embedder):
        assert embedder.dimension == 512

    def test_normalize(self):
        vecs = np.array([[3.0, 4.0], [1.0, 0.0]], dtype=np.float32)
        normalized = SOMAEmbedder.normalize(vecs)
        assert normalized.shape == vecs.shape
        assert abs(normalized[0, 0] - 0.6) < 0.01
        assert abs(normalized[0, 1] - 0.8) < 0.01
