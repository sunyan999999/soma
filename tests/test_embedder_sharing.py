"""嵌入器共享与生命周期测试（v2.0.16）

背景（DSH 协作反馈，2026-09-11）：
SOMA 每个实例各建一份 fastembed TextEmbedding → onnxruntime InferenceSession，
原生内存随实例数线性增长。生产 4 worker 在 4 小时内涨到 4.4 / 6.8 / 9.2 / 12 GB，
两次撑爆 cgroup 触发 OOM 全站 502。

DSH 定位准确：他们接入层事后替换 `soma._agent.embedder` 无效 —— SOMA 在实例
初始化阶段已建好自己的会话，换引用后旧会话仍被内部持有。

本次改造（DSH 建议 1/2/3）：
1. get_shared_embedder()：进程级单例，同模型同维度只建一份会话
2. SOMAEmbedder.close()：显式断开 fastembed → onnxruntime 引用链并 GC
3. SOMA(embedder=...)：门面透传 + 所有权语义 —— 自建的才释放，注入的不动

本地实测（Windows）：自建 +140/+95/+96 MB 线性增长；注入 +97/+0/+0 MB 平坦。

覆盖：
- 单例唯一性 / release 后重建
- 门面注入透传与 _owns_embedder 标记
- 自建实例 close 释放自己的会话
- 注入实例 close 不得动共享会话（多实例共享时的关键回归点）
- 注入没有 warmup/is_loaded 的第三方 embedder 不崩（BaseEmbedder 契约不含它们）
"""
import numpy as np
import pytest

from soma import SOMA
from soma.abc import BaseEmbedder
from soma.config import SOMAConfig
from soma.embedder import (
    _SHARED_EMBEDDERS,
    SOMAEmbedder,
    get_shared_embedder,
    release_shared_embedders,
)


class FakeEmbedder(BaseEmbedder):
    """最小嵌入器：只实现 BaseEmbedder 契约（故意不带 warmup/is_loaded）。

    用于验证 SOMA 不会对注入对象调用契约外的方法。
    """

    def __init__(self, dim: int = 8):
        self._dim = dim
        self.close_calls = 0
        self.encode_calls = 0

    def encode(self, text: str) -> np.ndarray:
        self.encode_calls += 1
        return np.ones(self._dim, dtype=np.float32)

    def encode_batch(self, texts):
        self.encode_calls += 1
        return np.ones((len(texts), self._dim), dtype=np.float32)

    @property
    def dimension(self) -> int:
        return self._dim

    def close(self) -> None:
        self.close_calls += 1


@pytest.fixture(autouse=True)
def _clean_shared():
    """每个用例前后都清空进程级单例，避免相互污染"""
    release_shared_embedders()
    yield
    release_shared_embedders()


@pytest.fixture
def no_real_load(monkeypatch):
    """拦截真实 ONNX 加载：自建路径只验证生命周期，不下载模型"""
    monkeypatch.setattr(SOMAEmbedder, "warmup", lambda self: True)


def _facade(tmp_path, name="soma_data", **kwargs):
    return SOMA(persist_dir=str(tmp_path / name), **kwargs)


class TestSharedSingleton:
    def test_same_config_returns_same_instance(self):
        a = get_shared_embedder()
        b = get_shared_embedder()
        assert a is b

    def test_different_model_key_returns_different_instance(self):
        cfg1 = SOMAConfig()
        cfg2 = SOMAConfig()
        cfg2.embedding_model_name = "other/model"
        a = get_shared_embedder(cfg1)
        b = get_shared_embedder(cfg2)
        assert a is not b

    def test_different_dim_returns_different_instance(self):
        cfg1 = SOMAConfig()
        cfg2 = SOMAConfig()
        cfg2.vector_dim = 256
        assert get_shared_embedder(cfg1) is not get_shared_embedder(cfg2)

    def test_release_clears_and_rebuilds(self, monkeypatch):
        calls = []
        monkeypatch.setattr(SOMAEmbedder, "close", lambda self: calls.append(self))
        first = get_shared_embedder()
        assert release_shared_embedders() == 1
        assert len(calls) == 1, "release 应释放手上的共享实例"
        assert _SHARED_EMBEDDERS == {}
        assert get_shared_embedder() is not first

    def test_release_on_empty_is_noop(self):
        assert release_shared_embedders() == 0


class TestFacadeInjection:
    def test_embedder_passes_through_to_agent(self, tmp_path):
        """门面 SOMA(embedder=...) 必须真的落到 agent 上（改造前被静默忽略）"""
        fake = FakeEmbedder()
        s = _facade(tmp_path, use_vector_search=False, embedder=fake)
        try:
            assert s._agent.embedder is fake
        finally:
            s.close()

    def test_injected_embedder_not_owned(self, tmp_path):
        fake = FakeEmbedder()
        s = _facade(tmp_path, use_vector_search=False, embedder=fake)
        try:
            assert s._agent._owns_embedder is False
        finally:
            s.close()

    def test_default_embedder_is_shared_not_owned(self, tmp_path, no_real_load):
        """★ 语义变更（2026-11-24）：默认构造走**进程级单例**，实例不拥有它。

        原来是「每个 SOMA 自建一个 embedder 并拥有它」，实测跑全量测试时
        onnxruntime 直接 `bad allocation`（N 个实例 = N 份 ONNX 会话）。
        v2.0.16 的单例机制本来就是为这个设计的，只是这条主路径没接上。

        现在 `_owns_embedder` 恒为 False —— 生命周期由
        `release_shared_embedders()` 管。
        """
        s = _facade(tmp_path, use_vector_search=True)
        try:
            assert isinstance(s._agent.embedder, SOMAEmbedder)
            assert s._agent._owns_embedder is False, (
                "实例仍宣称拥有 embedder —— 会导致每实例一份 ONNX 会话")
        finally:
            s.close()

    def test_multiple_instances_share_one_embedder(self, tmp_path, no_real_load):
        """★ 核心回归：多个实例必须复用同一个嵌入器对象。"""
        stores = [_facade(tmp_path, name=f"m{i}", use_vector_search=True) for i in range(3)]
        try:
            ids = {id(s._agent.embedder) for s in stores}
            assert len(ids) == 1, f"3 个实例拿到 {len(ids)} 个 embedder —— 没共享"
        finally:
            for s in stores:
                s.close()

    def test_no_embedder_when_vector_search_off(self, tmp_path):
        s = _facade(tmp_path, use_vector_search=False)
        try:
            assert s._agent.embedder is None
        finally:
            s.close()

    def test_injected_embedder_without_warmup_does_not_crash(self, tmp_path):
        """BaseEmbedder 契约里没有 warmup/is_loaded，注入第三方实现不能崩"""
        fake = FakeEmbedder()
        s = _facade(tmp_path, use_vector_search=False, embedder=fake,
                    warmup_on_init=True)
        s.close()


class TestLifecycle:
    def test_shared_not_closed_on_instance_close(self, tmp_path, monkeypatch, no_real_load):
        """★ 语义变更：实例 close() **不能**释放共享单例。

        否则第一个实例关闭会把所有实例正在用的会话拆掉
        （多 worker / 多用户实例场景下就是灾难）。
        """
        from soma.embedder import release_shared_embedders
        release_shared_embedders()
        calls = []
        monkeypatch.setattr(SOMAEmbedder, "close", lambda self: calls.append(self))
        s = _facade(tmp_path, use_vector_search=True)
        assert calls == [], "构造阶段不该释放"
        s.close()
        assert calls == [], (
            "实例 close() 释放了共享的嵌入器 —— 其它实例会拿到死会话")
        release_shared_embedders()

    def test_injected_not_closed_on_instance_close(self, tmp_path):
        """关键回归点：多实例共享时，第一个 close 的实例不能释放共享会话"""
        fake = FakeEmbedder()
        s1 = _facade(tmp_path, name="d1", use_vector_search=False, embedder=fake)
        s2 = _facade(tmp_path, name="d2", use_vector_search=False, embedder=fake)
        s1.close()
        assert fake.close_calls == 0, "注入的实例由调用方管理，实例无权释放"
        s2.close()
        assert fake.close_calls == 0

    def test_shared_embedder_survives_multiple_closes(self, tmp_path, monkeypatch):
        """端到端：共享 embedder 被多个实例复用，任何实例 close 都不能释放它"""
        calls = []
        monkeypatch.setattr(SOMAEmbedder, "close", lambda self: calls.append(self))
        shared = get_shared_embedder()
        s1 = _facade(tmp_path, name="s1", embedder=shared)
        s2 = _facade(tmp_path, name="s2", embedder=shared)
        assert s1._agent.embedder is s2._agent.embedder is shared
        s1.close()
        s2.close()
        assert calls == [], "共享实例不能被任何实例的 close 释放"
        assert get_shared_embedder() is shared

    def test_close_is_idempotent(self):
        e = SOMAEmbedder(SOMAConfig())
        e.close()
        e.close()  # 未加载时也安全


class TestOwnershipAcrossManyInstances:
    def test_many_injected_instances_share_one_session(self, tmp_path, no_real_load):
        """模拟 DSH 生产形态：一个 worker 内多个用户实例共用一份嵌入会话"""
        shared = get_shared_embedder()
        instances = [
            _facade(tmp_path, name=f"user{i}", embedder=shared) for i in range(5)
        ]
        try:
            assert all(s._agent.embedder is shared for s in instances)
            assert all(s._agent._owns_embedder is False for s in instances)
        finally:
            for s in instances:
                s.close()
        # 全部关闭后共享实例依旧存活
        assert get_shared_embedder() is shared
