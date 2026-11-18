# -*- coding: utf-8 -*-
"""L3 画像的自动触发：「达到或超过阈值」而不是「正好整除」。

## 背景（2026-11-24，下游生产实测）

用户攒了 **19 条场景**，`profile_entries` 一直是 **0**。根因在
`capture.py`：

```python
total = self._total_scenes_created.get(uid, 0)          # 进程内内存计数
if total > 0 and total % self._cfg.profile_scene_interval == 0:   # 必须正好整除
    self.update_profile(uid, force=force)
```

两个缺陷叠加：

1. **必须"正好"是 10 的倍数**。实测场景增长序列是 8 → 13 → 19 → 25
   （每次捕获 3~8 条），每次都跨过 10/20，永远不相等 → **一次都没触发过**。
   批量不固定时这是必然踩中的。
2. **计数是进程内的内存字典**，不持久、不跨 worker。CLI 新进程读到空 dict，
   重启归零，多 worker 各记各的。

## 修法

- 计数改用库里的真实场景数（`scene_store.count()`，持久 + 跨进程）
- 阈值存 `capture_lease.last_profile_at`
- 判断改成「`total >= marker + interval` 就触发并推进」，用一条带条件的
  UPDATE 保证多 worker 同时到达时只触发一次

## 注入自证

  · 判断改回 `total % interval == 0`  → TestThresholdCrossing 红
  · 计数改回内存 `_total_scenes_created` → TestPersistedCounter 红
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from soma import SOMA  # noqa: E402
from soma.memory.capture import (  # noqa: E402
    CaptureConfig, CapturePipeline,
)
from soma.memory.profile import ProfileStore  # noqa: E402
from soma.memory.scene import SceneStore  # noqa: E402


class _SceneExtractor:
    """每次返回一条固定标题的场景（便于精确控制总数）。"""

    def __init__(self):
        self.n = 0

    def extract(self, memories, existing):
        self.n += 1
        return [{"title": f"场景{self.n}", "summary": "s", "tags": ["t"],
                 "importance": 0.7, "evidence_ids": ["1"]}]


class _ProfileExtractor:
    def __init__(self):
        self.calls = 0

    def extract(self, scenes, existing):
        self.calls += 1
        return [{"trait_type": "preference", "trait_key": f"k{self.calls}",
                 "trait_value": "v", "confidence": 0.9}]


def _add_scenes(store, user_id, n, start=0):
    for i in range(start, start + n):
        store.add_scene(title=f"预置场景{i}", summary="s", user_id=user_id)


class TestThresholdCrossing:
    """★ 核心回归：跨过阈值也要触发。"""

    def test_sequence_8_13_19_25(self, tmp_path):
        """生产实测的增长序列 8 → 13 → 19 → 25。

        旧实现（total % 10 == 0）在这里**一次都不触发**。
        """
        st = SceneStore(tmp_path)
        try:
            fired = []
            for total in (8, 13, 19, 25):
                fired.append(st.try_advance_profile_marker("u1", total, 10))
            assert fired == [False, True, False, True], (
                f"阈值触发序列不对：{fired}（应为 [False,True,False,True]）")
        finally:
            st.close()

    def test_batch_jump_triggers_once(self, tmp_path):
        """一次从 0 跳到 19（批量导入）只触发一次，不会被欠账追着补。"""
        st = SceneStore(tmp_path)
        try:
            assert st.try_advance_profile_marker("u1", 19, 10) is True
            assert st.try_advance_profile_marker("u1", 19, 10) is False, (
                "同一批场景触发了两次画像更新")
            assert st.profile_marker("u1") == 19
        finally:
            st.close()

    def test_interval_zero_is_safe(self, tmp_path):
        """interval=0 不能让判断恒真或除零。"""
        st = SceneStore(tmp_path)
        try:
            assert st.try_advance_profile_marker("u1", 1, 0) is True
        finally:
            st.close()


class TestPersistedCounter:
    """★ 计数与阈值必须持久、跨进程。"""

    def test_marker_survives_new_instance(self, tmp_path):
        a = SceneStore(tmp_path)
        try:
            a.try_advance_profile_marker("u1", 13, 10)
        finally:
            a.close()
        b = SceneStore(tmp_path)
        try:
            assert b.profile_marker("u1") == 13, "阈值没持久化"
            assert b.try_advance_profile_marker("u1", 19, 10) is False, (
                "新进程不知道已经触发过，会重复更新画像")
        finally:
            b.close()

    def test_count_derived_from_store_not_memory(self, tmp_path):
        """端到端：场景数由库里 count 派生，不依赖进程内计数。"""
        scenes = SceneStore(tmp_path)
        pipeline = CapturePipeline(
            scenes, ProfileStore(tmp_path), CaptureConfig(),
            scene_extractor=_SceneExtractor(),
            profile_extractor=_ProfileExtractor(),
            memory_provider=lambda uid: [{"content": "记忆"}],
        )
        try:
            # 预置 12 条真实场景（模拟历史数据，内存计数是 0）
            _add_scenes(scenes, "u1", 12)
            assert scenes.count("u1") == 12

            # 再捕获 1 条 → 库里 13 条 → 跨过阈值 10，应触发画像
            pipeline.capture_from_memories(
                [{"content": "记忆"}], user_id="u1", force=True)
            assert scenes.count("u1") == 13
            assert pipeline._profile_store.count("u1") >= 1, (
                "库里已有 13 条场景却没更新画像 —— 计数没从库里派生")
        finally:
            scenes.close()
            pipeline._profile_store.close()

    def test_restart_does_not_retrigger(self, tmp_path):
        """重启后（新 pipeline）不该把同一批场景再算一次。"""
        scenes = SceneStore(tmp_path)
        _add_scenes(scenes, "u1", 13)
        p1 = CapturePipeline(
            scenes, ProfileStore(tmp_path), CaptureConfig(),
            scene_extractor=_SceneExtractor(),
            profile_extractor=_ProfileExtractor(),
            memory_provider=lambda uid: [{"content": "记忆"}],
        )
        try:
            p1.capture_from_memories([{"content": "记忆"}], user_id="u1", force=True)
            after_first = p1._profile_store.count("u1")
            assert after_first >= 1
        finally:
            scenes.close()
            p1._profile_store.close()

        # 新实例（模拟重启）再来一次，场景数仍是 13~14，不该再触发
        scenes2 = SceneStore(tmp_path)
        p2 = CapturePipeline(
            scenes2, ProfileStore(tmp_path), CaptureConfig(),
            scene_extractor=_SceneExtractor(),
            profile_extractor=_ProfileExtractor(),
            memory_provider=lambda uid: [{"content": "记忆"}],
        )
        try:
            p2.capture_from_memories([{"content": "记忆"}], user_id="u1", force=True)
            assert p2._profile_store.count("u1") == after_first, (
                "重启后又触发了一次画像更新 —— 阈值没跨进程共享")
        finally:
            scenes2.close()
            p2._profile_store.close()


class TestSomaEndToEnd:
    """★ 门面层：真实 SOMA 实例上能自动产出画像。"""

    def test_profile_produced_without_manual_force(self, tmp_path):
        s = SOMA(llm="mock", persist_dir=str(tmp_path),
                 use_vector_search=False, warmup_on_init=False)
        try:
            s._ensure_layered_memory()
            s._capture_pipeline._scene_extractor = _SceneExtractor()
            s._capture_pipeline._profile_extractor = _ProfileExtractor()

            # 预置 9 条场景，再走**真实的 remember 自动捕获** → 10 条，
            # 正好跨过阈值（这也顺带验证了自动链路，不是只有手动调用才行）
            _add_scenes(s._scene_store, "u1", 9)
            s.remember("一条真实的记忆内容", user_id="u1", importance=0.7)

            assert s._scene_store.count("u1") == 10
            assert s._profile_store.count("u1") >= 1, (
                "攒到 10 条场景仍没产出画像 —— 自动触发没生效")
            assert s.get_layered_stats("u1")["profile_entries"] >= 1
        finally:
            s.close()
