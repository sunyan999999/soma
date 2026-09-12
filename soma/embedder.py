import gc
import threading
import time
from typing import Dict, List, Optional

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

    def close(self) -> None:
        """释放 ONNX 推理会话（v2.0.16）。

        断开 fastembed → onnxruntime 的引用链并触发 GC，使原生会话内存可被回收。

        只应释放**自己持有**的模型；共享/注入的实例由其所有者统一释放
        （SOMA 会跳过注入进来的 embedder，见 SOMA_Agent.close）。
        可安全重复调用。
        """
        model = self._model
        self._model = None
        self._warmed_up = False
        if model is None:
            return
        # fastembed.TextEmbedding.model -> OnnxTextModel.model -> InferenceSession
        # 逐层断开引用，否则 onnxruntime 会话会因残留引用而不释放
        try:
            inner = getattr(model, "model", None)
            if inner is not None and hasattr(inner, "model"):
                inner.model = None
            if hasattr(model, "model"):
                model.model = None
        except Exception:
            pass
        del model
        gc.collect()

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


# ── 进程级共享嵌入器（v2.0.16）────────────────────────────────────────
#
# 背景：fastembed 的 TextEmbedding 持有一份 onnxruntime InferenceSession，
# 每份会话占用大量原生内存。若每个 SOMA 实例各建一份，多租户/多 worker
# 场景会随实例数线性增长（实测单实例增量数十至数百 MB，随平台而异）。
#
# 共享实例由调用方掌握生命周期：SOMA 只关闭自己创建的 embedder，
# 注入进来的（含本工厂产出的）一律不动。

_SHARED_EMBEDDERS: Dict[str, SOMAEmbedder] = {}
_SHARED_LOCK = threading.Lock()


def _shared_key(config: SOMAConfig) -> str:
    return f"{config.embedding_model_name}::{config.vector_dim}"


def get_shared_embedder(config: Optional[SOMAConfig] = None) -> SOMAEmbedder:
    """获取进程级共享嵌入器（v2.0.16）。

    同一进程内，模型名 + 维度相同的调用返回**同一实例**，因此多个 SOMA
    实例可以复用同一份 ONNX 推理会话，不再随实例数线性增长。

    用法::

        from soma import SOMA
        from soma.embedder import get_shared_embedder

        shared = get_shared_embedder()
        s1 = SOMA(persist_dir=d1, embedder=shared)
        s2 = SOMA(persist_dir=d2, embedder=shared)   # 复用，不新建会话

    首次调用只创建对象，模型按 ``warmup()`` / 首次 ``encode()`` 惰性加载，
    与 SOMA 原有预热行为一致（受 ``warmup_on_init`` 控制）。

    注意：共享实例不在任何单个 SOMA 的 close() 中释放，需要时由调用方
    显式调用 :func:`release_shared_embedders` 或 ``shared.close()``。
    """
    cfg = config or SOMAConfig()
    key = _shared_key(cfg)
    with _SHARED_LOCK:
        inst = _SHARED_EMBEDDERS.get(key)
        if inst is None:
            inst = SOMAEmbedder(cfg)
            _SHARED_EMBEDDERS[key] = inst
        return inst


def release_shared_embedders() -> int:
    """释放全部进程级共享嵌入器，返回释放数量（v2.0.16）。

    供进程收尾或测试清理使用；调用后再取会得到新实例。
    """
    with _SHARED_LOCK:
        instances = list(_SHARED_EMBEDDERS.values())
        _SHARED_EMBEDDERS.clear()
    for inst in instances:
        inst.close()
    return len(instances)
