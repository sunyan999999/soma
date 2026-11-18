# -*- coding: utf-8 -*-
"""激活排序的稳定性 + 文本编码缓存。

## 背景（2026-11-24）

下游提出「`_hybrid_search` 三路可以并行，预计再省 100ms」，并要求**并行版
必须带「激活排序稳定性」判据**（同一输入多次运行，激活序列一致）。

先测了现状：本地库 5 次 `query()` 的激活序列**完全一致** —— 这是个已经成立的
不变量，任何并行/优化都不能打破它。

同时按同一思路做了更安全的优化：`encode()` 的文本级 LRU（下游也提过
「focus.dimension 每次都重新编码」）。

## 为什么先没做并行

SQLite 在 `check_same_thread=False` 下 threadsafety=3（serialized）——
**同一连接的 SQL 调用在内部串行**。三个通道共用 `self._conn`，并行拿不到
真实收益，却要引入连接竞争和合并顺序问题。要做并行得给每条线程独立连接，
那又是一致性（WAL 快照）和创建开销的另一笔账。

所以这版先钉住「排序稳定」这个不变量 + 做确定的编码缓存；并行留到有
明确收益证据时再评估。

## 注入自证

  · encode 缓存命中记进延迟统计 → TestEncodeCache 红
  · 激活排序引入随机              → TestOrderStability 红
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from soma import SOMA  # noqa: E402
from soma.base import Focus  # noqa: E402


@pytest.fixture(scope="module")
def soma(tmp_path_factory):
    d = tmp_path_factory.mktemp("hybrid")
    s = SOMA(llm="mock", persist_dir=str(d),
             use_vector_search=True, warmup_on_init=True)
    for i in range(40):
        s.remember(f"系统思维与整体性的实践经验第{i}条", user_id="u1",
                   importance=0.6)
    yield s
    s.close()


def _focus():
    return Focus(law_id="t", dimension="系统思维如何应用",
                 keywords=["系统思维", "整体性"], weight=1.0, rationale="r")


class TestOrderStability:
    """★ 同一输入，激活序列必须逐位一致。

    下游要求这条作为「并行版」的前置判据 —— 并行最容易破坏的就是排序。
    """

    def test_query_order_is_stable(self, soma):
        runs = []
        for _ in range(5):
            ids = [am.memory.id
                   for am in soma._agent.memory.query(_focus(), top_k=10, user_id="u1")]
            runs.append(tuple(ids))
        assert len(set(runs)) == 1, (
            f"激活序列 5 次不一致：{len(set(runs))} 种顺序 —— "
            f"并行/优化不能破坏排序稳定性")

    def test_decompose_order_is_stable(self, soma):
        problem = "系统思维如何应用到产品设计"
        runs = [tuple(f.law_id for f in soma._agent.decompose(problem))
                for _ in range(5)]
        assert len(set(runs)) == 1

    def test_hybrid_search_deterministic(self, soma):
        """直接钉 _hybrid_search 本身（并行改动的目标函数）。"""
        mem = soma._agent.memory
        runs = []
        for _ in range(3):
            res = mem._hybrid_search(_focus(), 10, user_id="u1")
            runs.append(tuple(am.memory.id for am in res))
        assert len(set(runs)) == 1, "混合检索结果不稳定"


class TestEncodeCache:
    """★ 文本级 LRU：命中不重复编码，且不污染延迟统计。"""

    def test_same_text_encoded_once(self, soma):
        emb = soma._agent.embedder
        base = emb._total_encodes
        text = "缓存判据专用文本-甲"
        emb.encode(text)
        for _ in range(10):
            emb.encode(text)
        assert emb._total_encodes - base == 1, (
            f"同一文本编码了 {emb._total_encodes - base} 次 —— 缓存没生效")

    def test_cache_hit_not_counted_as_encode(self, soma):
        """★ 缓存命中不能进延迟统计。

        否则 `_total_encode_ms / _total_encodes` 会被大量 0ms 命中稀释，
        健康监控（单次 > 150ms 判不健康）再也发现不了真实退化。
        """
        emb = soma._agent.embedder
        text = "延迟统计判据专用文本-乙"
        emb.encode(text)
        base_encodes = emb._total_encodes
        base_ms = emb._total_encode_ms
        for _ in range(20):
            emb.encode(text)
        assert emb._total_encodes == base_encodes, "缓存命中被算成一次编码"
        assert emb._total_encode_ms == base_ms, "缓存命中被算进了总耗时"

    def test_different_texts_both_encoded(self, soma):
        emb = soma._agent.embedder
        base = emb._total_encodes
        emb.encode("文本-丙")
        emb.encode("文本-丁")
        assert emb._total_encodes - base == 2

    def test_lru_bound(self, soma):
        emb = soma._agent.embedder
        n = emb._encode_cache_max
        for i in range(n + 20):
            emb.encode(f"LRU 边界测试文本 {i}")
        assert len(emb._encode_cache) <= n, (
            f"缓存条目 {len(emb._encode_cache)} 超过上限 {n}")

    def test_returned_vector_is_normalized(self, soma):
        """缓存不能破坏归一化语义（向量要能直接做点积）。"""
        emb = soma._agent.embedder
        v = emb.encode("归一化判据文本")
        assert abs(float(np.linalg.norm(v)) - 1.0) < 1e-4


class TestCaliberInWisdom:
    """★ 抽样模式也要带 caliber（下游要求）。"""

    def test_wisdom_details_has_caliber(self, soma):
        from soma.benchmarks import run_wisdom_benchmark, CALIBER_VERSION
        for mode in ("first15", "stratified"):
            w = run_wisdom_benchmark(soma._agent, sample=mode)
            assert w.details.get("caliber") == CALIBER_VERSION, (
                f"sample={mode} 的 wisdom details 里没有 caliber —— "
                f"面板并排展示时仍需人工判断新旧口径")
            assert w.details.get("sample_mode") == mode
