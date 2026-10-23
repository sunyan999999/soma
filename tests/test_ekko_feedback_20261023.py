# -*- coding: utf-8 -*-
"""零熵智库（ekko）2026-10-23 上报的三条问题。

## ① 中文短词在「用户主动搜索」里查不到

ekko 的原始描述是「trigram FTS 产生不了二元组」。**但那个诊断不对** ——
`search_utils.fts5_keyword_search` 里 `len(kw) < 3` 本来就走 LIKE 兜底，
实测 `query_by_keywords(['艾灸'])` 能查到。

真因在**上一层**：`hub.activate()` 的 `threshold=0.3` 把老记忆全滤掉了。

    query_by_keywords('艾灸')        → 2 条
    activate(threshold=0.3)          → 1 条   ← 100 天前那条被滤掉

而 `threshold` 是给**自动召回**用的（只把够相关的注入 prompt）；
`query_memory()` 是**用户主动搜索** —— 用户明确搜"艾灸"，就该看到所有匹配。

**修法**：`activate()` 支持按次传 `threshold`；`query_memory()` 传 0.0。

## ② 前置过滤子集超过扫描上限 → 退回全局检索

`_MAX_FILTER_SCAN = 10000` 是**类常量写死**。生产有单用户 2 万+ 条记忆 ——
那种账号每次向量搜索都走退化路径（全局检索 + 30 倍候选），既慢、召回又可能不足。

**修法**：构造时可传 `filter_scan_limit`；默认提到 50000。
（第二道闸 `_MAX_FILTER_SHARE=0.15` 仍在 —— 子集占全库 >15% 时照样不做前置过滤，
所以提高上限不会让超大账号拖垮查询。）

## ③ `_mock_respond()` 不透传 user_id

无 LLM 时调 `hub.activate(foci)` **不传 user_id** —— 会把所有用户的记忆
都激活出来，和 `reason()` / `chat()` 的口径不一致。

**修法**：加 `user_id` 参数并传下去；两个调用点都补上。

## 注入自证

  · `query_memory` 去掉 `threshold=0.0` → `TestShortQuery` 红；
  · `_MAX_FILTER_SCAN` 改回 10000 且不准传 → `TestScanLimit` 红；
  · `_mock_respond` 不传 user_id → `TestMockRespondUserScope` 红。
"""
from __future__ import annotations

import datetime as _dt
import inspect
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from soma.base import Focus  # noqa: E402
from soma.config import SOMAConfig  # noqa: E402
from soma.memory.core import MemoryCore  # noqa: E402


@pytest.fixture
def core(tmp_path):
    return MemoryCore(SOMAConfig(episodic_persist_dir=str(tmp_path)))


def _age(core: MemoryCore, memory_id: str, days: float) -> None:
    """把一条记忆的 timestamp 改成 N 天前。"""
    core.episodic._conn.execute(
        "UPDATE episodic_memories SET timestamp = ? WHERE id = ?",
        (time.time() - days * 86400, memory_id),
    )
    core.episodic._conn.commit()


def _focus(kw: str = "艾灸") -> Focus:
    return Focus(law_id="q", dimension=kw, keywords=[kw], weight=1.0, rationale="t")


class TestShortQuery:
    """★ 用户主动搜一个词，就该看到所有匹配 —— 不管它多老。"""

    def test_old_memory_found_by_keyword(self, tmp_path):
        """★ 100 天前、importance 0.5 的记忆，**走用户真实路径 `query_memory`** 也要查得到。

        这就是「用户搜'艾灸'得到 0 条，而库里有」那条。

        ⚠️ 必须走 `query_memory()` 而不是直接调 `hub.activate()` ——
        前者才是用户点的那条路。第一版判据直接调 activate 并手动传
        `threshold=0.0`，于是把 `query_memory` 里的 `threshold=0.0` 删掉之后
        **判据照样绿**（2026-10-23 注入自证实测）。
        """
        from soma import SOMA

        s = SOMA(llm="mock", persist_dir=str(tmp_path),
                 use_vector_search=False, warmup_on_init=False)
        try:
            mid = s.remember("艾灸养生是老话题，三个月前听过",
                             importance=0.5, user_id="u1")
            s._agent.memory.episodic._conn.execute(
                "UPDATE episodic_memories SET timestamp = ? WHERE id = ?",
                (time.time() - 100 * 86400, mid))
            s._agent.memory.episodic._conn.commit()

            # 底层（无阈值）—— 先证明库里有
            raw = s._agent.memory.episodic.query_by_keywords(
                ["艾灸"], top_k=5, user_id="u1")
            assert len(raw) == 1, f"底层都查不到（{len(raw)} 条），先查 FTS"

            # ★ 用户真正走的那条路
            got = s.query_memory("艾灸", top_k=10, user_id="u1")
            assert len(got) == 1, (
                f"底层查到 1 条，`query_memory` 只剩 {len(got)} 条 —— "
                f"老记忆被相关度阈值滤掉了，用户看到的是「什么都没找到」")
        finally:
            try:
                s.close()
            except Exception:
                pass

    def test_threshold_still_works_for_recall(self, core):
        """★ 对照：**自动召回**那条路仍然要阈值（老记忆不该注入 prompt）。"""
        mid = core.remember("艾灸养生是老话题", importance=0.5)
        _age(core, mid, 100)

        from soma.hub import ActivationHub
        hub = ActivationHub(core)
        got = hub.activate([_focus("艾灸")], user_id="")   # 默认 threshold=0.3
        assert len(got) == 0, (
            "自动召回也返回了老记忆 —— 阈值被改坏了，"
            "prompt 里会塞进一堆陈年噪音")

    def test_query_memory_passes_zero_threshold(self):
        """★ 接线判据：`query_memory` 必须真的传 `threshold=0.0`。"""
        from soma.agent import SOMA_Agent
        src = inspect.getsource(SOMA_Agent.query_memory)
        assert "threshold=0.0" in src, (
            "query_memory 没关掉相关度阈值 —— 老记忆搜不到")


class TestScanLimit:
    """★ 前置过滤扫描上限：可配 + 默认放宽。"""

    def test_default_raised(self):
        from soma.vector_store import NumpyVectorIndex
        assert NumpyVectorIndex._MAX_FILTER_SCAN >= 50000, (
            "默认上限没提 — 生产单用户 2 万+ 条会永远走退化路径")

    def test_can_be_overridden_per_instance(self, tmp_path):
        from soma.vector_store import NumpyVectorIndex
        idx = NumpyVectorIndex(tmp_path / "x.db", 8, filter_scan_limit=1234)
        assert idx._filter_scan_limit == 1234, "构造参数没生效"
        idx2 = NumpyVectorIndex(tmp_path / "y.db", 8)
        assert idx2._filter_scan_limit == NumpyVectorIndex._MAX_FILTER_SCAN

    def test_config_actually_reaches_instance(self, tmp_path):
        """★ 接线判据：`SOMAConfig.vector_filter_scan_limit` 必须真的传到实例。

        第一版只加了构造参数，`EpisodicStore` 造索引时根本没传 ——
        日志里却写着"可用 vector_filter_scan_limit 调高"，而那个配置项
        当时**不存在**。参数可传 ≠ 用户可调。
        """
        import numpy as np

        cfg = SOMAConfig(episodic_persist_dir=str(tmp_path),
                         vector_filter_scan_limit=4242)

        class _Emb:
            dimension = 8

            def encode(self, texts, **kw):
                return np.zeros((len(texts), 8), dtype="float32")

        core = MemoryCore(cfg, embedder=_Emb())
        try:
            assert core.episodic._vector_index is not None, "向量索引没建起来"
            assert core.episodic._vector_index._filter_scan_limit == 4242, (
                "配置值没传到 NumpyVectorIndex —— 用户设了也不生效")
        finally:
            core.close()

    def test_share_guard_still_exists(self):
        """★ 第二道闸必须在 —— 否则提高上限会让超大账号拖垮查询。"""
        from soma.vector_store import NumpyVectorIndex
        assert hasattr(NumpyVectorIndex, "_MAX_FILTER_SHARE")
        assert 0 < NumpyVectorIndex._MAX_FILTER_SHARE < 1


class TestMockRespondUserScope:
    """★ 无 LLM 的 mock 路径也要按用户隔离。"""

    def test_signature_accepts_user_id(self):
        from soma import SOMA
        sig = inspect.signature(SOMA._mock_respond)
        assert "user_id" in sig.parameters, \
            "`_mock_respond` 不收 user_id —— 会把所有用户的记忆都激活出来"

    def test_passes_user_id_to_activate(self):
        from soma import SOMA
        src = inspect.getsource(SOMA._mock_respond)
        assert "user_id=user_id" in src, "拿到了 user_id 却没传给 activate"

    def test_call_sites_pass_it(self):
        from soma import SOMA
        src = inspect.getsource(SOMA)
        # 不能有裸调用（不带 user_id 的）
        bare = [ln.strip() for ln in src.splitlines()
                if "_mock_respond(problem)" in ln]
        assert not bare, f"还有没传 user_id 的调用点：{bare}"

    def test_real_mock_call_respects_user_scope(self, tmp_path):
        """★ 端到端：A 的记忆不该出现在 B 的 mock 回答里。"""
        from soma import SOMA

        s = SOMA(llm="mock", persist_dir=str(tmp_path),
                 use_vector_search=False, warmup_on_init=False)
        try:
            s.remember("用户A的私密笔记：我在研究艾灸", user_id="A", importance=0.9)
            out_b = s._mock_respond("艾灸", user_id="B")
            assert "用户A的私密笔记" not in out_b, (
                "B 的 mock 回答里出现了 A 的记忆 —— user_id 没生效")
        finally:
            try:
                s.close()
            except Exception:
                pass
