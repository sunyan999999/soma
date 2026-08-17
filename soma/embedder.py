import time
from typing import List, Optional

import numpy as np

from soma.abc import BaseEmbedder
from soma.config import SOMAConfig


class SOMAEmbedder(BaseEmbedder):
    """文本嵌入器 — 封装 fastembed ONNX 推理，含延迟健康监控。

    健康阈值：
    - 单次编码 > 150ms → healthy=False（v2.0.5 ONNX 回归时达 280ms）
    - 正常延迟 ~60ms
    """

    # 延迟健康阈值（毫秒），基于 v2.0.4 基准 63ms + 2x 余量
    LATENCY_HEALTHY_THRESHOLD_MS = 150.0

    def __init__(self, config: SOMAConfig):
        self._config = config
        self._model = None
        self._dim = config.vector_dim
        self._warmed_up = False
        # 延迟监控
        self._last_encode_ms: float = 0.0
        self._total_encodes: int = 0
        self._total_encode_ms: float = 0.0
        self._peak_encode_ms: float = 0.0

    def warmup(self) -> bool:
        """预热嵌入模型：预下载模型文件，避免首次调用时阻塞。

        返回 True 表示预热成功，False 表示首次下载中（稍后自动重试）。
        """
        try:
            self._ensure_model()
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

    @property
    def is_loaded(self) -> bool:
        """模型是否已加载完成。v2.0.8: 供热路径判断是否可安全 encode。"""
        return self._model is not None

    def encode(self, text: str) -> np.ndarray:
        self._ensure_model()
        t0 = time.perf_counter()
        vecs = list(self._model.embed([text]))
        elapsed = (time.perf_counter() - t0) * 1000
        self._record_latency(elapsed)
        arr = np.asarray(vecs[0], dtype=np.float32)
        return SOMAEmbedder.normalize(arr)

    def encode_batch(self, texts: List[str]) -> np.ndarray:
        self._ensure_model()
        t0 = time.perf_counter()
        all_vecs = []
        for vec in self._model.embed(texts):
            all_vecs.append(np.asarray(vec, dtype=np.float32))
        elapsed = (time.perf_counter() - t0) * 1000
        self._record_latency(elapsed)
        arr = np.stack(all_vecs, axis=0)
        return SOMAEmbedder.normalize(arr)

    def _record_latency(self, ms: float):
        self._last_encode_ms = ms
        self._total_encodes += 1
        self._total_encode_ms += ms
        if ms > self._peak_encode_ms:
            self._peak_encode_ms = ms

    # ── 健康监控 API ────────────────────────────────────────────

    @property
    def last_latency_ms(self) -> float:
        """最近一次编码延迟（毫秒）"""
        return self._last_encode_ms

    @property
    def avg_latency_ms(self) -> float:
        """平均编码延迟（毫秒）"""
        if self._total_encodes == 0:
            return 0.0
        return self._total_encode_ms / self._total_encodes

    @property
    def peak_latency_ms(self) -> float:
        """历史最高编码延迟（毫秒）"""
        return self._peak_encode_ms

    @property
    def is_healthy(self) -> bool:
        """延迟是否在健康范围内。

        当平均延迟超过 150ms 阈值时返回 False，
        提示可能存在 ONNX 运行时性能回归。
        """
        if self._total_encodes == 0:
            return True
        return self.avg_latency_ms < self.LATENCY_HEALTHY_THRESHOLD_MS

    def latency_report(self) -> dict:
        """返回延迟健康报告，供仪表盘/健康检查使用。"""
        return {
            "last_ms": round(self._last_encode_ms, 1),
            "avg_ms": round(self.avg_latency_ms, 1),
            "peak_ms": round(self._peak_encode_ms, 1),
            "total_encodes": self._total_encodes,
            "healthy": self.is_healthy,
            "threshold_ms": self.LATENCY_HEALTHY_THRESHOLD_MS,
        }

    @property
    def dimension(self) -> int:
        return self._dim

    @staticmethod
    def normalize(vectors: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(vectors, axis=-1, keepdims=True)
        norms = np.where(norms == 0, 1.0, norms)
        return vectors / norms
