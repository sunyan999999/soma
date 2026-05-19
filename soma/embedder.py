from typing import List

import numpy as np

from soma.abc import BaseEmbedder
from soma.config import SOMAConfig


class SOMAEmbedder(BaseEmbedder):
    """文本嵌入器 — 封装 fastembed ONNX 推理，毫秒级编码延迟"""

    def __init__(self, config: SOMAConfig):
        self._config = config
        self._model = None
        self._dim = config.vector_dim
        self._warmed_up = False

    def warmup(self) -> bool:
        """预热嵌入模型：预下载模型文件，避免首次调用时阻塞。

        返回 True 表示预热成功，False 表示首次下载中（稍后自动重试）。
        """
        try:
            self._ensure_model()
            # 编码一个短文本验证模型已就绪
            self.encode("warmup")
            self._warmed_up = True
            return True
        except Exception:
            return False

    def _ensure_model(self):
        if self._model is None:
            from fastembed import TextEmbedding

            self._model = TextEmbedding(
                self._config.embedding_model_name,
                threads=4,
            )

    def encode(self, text: str) -> np.ndarray:
        self._ensure_model()
        vecs = list(self._model.embed([text]))
        arr = np.asarray(vecs[0], dtype=np.float32)
        return SOMAEmbedder.normalize(arr)

    def encode_batch(self, texts: List[str]) -> np.ndarray:
        self._ensure_model()
        all_vecs = []
        for vec in self._model.embed(texts):
            all_vecs.append(np.asarray(vec, dtype=np.float32))
        arr = np.stack(all_vecs, axis=0)
        return SOMAEmbedder.normalize(arr)

    @property
    def dimension(self) -> int:
        return self._dim

    @staticmethod
    def normalize(vectors: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(vectors, axis=-1, keepdims=True)
        norms = np.where(norms == 0, 1.0, norms)
        return vectors / norms
