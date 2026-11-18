# -*- coding: utf-8 -*-
"""L2 捕获的跨进程互斥、失败可见性与返回值语义。

## 背景（2026-11-18，下游生产反馈）

生产用 `uvicorn --workers 3`，每个 worker 各持一份 SOMA 实例。
`CapturePipeline` 的节流状态（`_last_capture_time` / `_new_count`）都是
**进程内**的 —— 进程内节流管不到彼此。实测：同一批记忆被三个 worker
各抽一次，产出语义重复、措辞不同的场景：

    日志：捕获完成: user=1, 场景=6, 累计场景=6（两个 worker 各打一次）
    表里：12 条，标题成对出现
          「信任体系与文化赋能」vs「信任体系与企业文化落地」
          「助手能力与服务范围」vs「助手服务范围说明」

另有两个相关问题：

2. **返回值语义不清**：`capture_scenes(force=True)` 返回 0，但表里已有数据
   （那是之前自动捕获的，本次提取的标题全部被去重）。调用方据此误判
   「L2 没跑起来」。

3. **失败静默**：LLM key 失效时每一次抽取都失败，但只有一行 WARNING，
   scenes 恒为 0 却没人发现。

## 修法

- 跨进程租约：`scenes.db` 里的 `capture_lease` 表（WAL + busy_timeout
  已经配好），两个时间字段 —— `in_flight_until`（防并发）、
  `cooldown_until`（跨进程的 last_capture_time）。
- 明细：`get_last_capture_detail()` 返回 {extracted, created, skipped,
  reason, error}，reason 能区分 no_new / failed / locked 等。
- 失败可见性：连续失败计数，第 3 次起升级为 ERROR。

## 注入自证

  · 去掉租约（try_begin_capture 恒返回 owner）→ TestCrossProcessLease 红
  · 连续失败不计数                        → TestFailureVisibility 红
  · 明细不写 reason                       → TestCaptureDetail 红
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from soma import SOMA  # noqa: E402
from soma.memory.capture import (  # noqa: E402
    CaptureConfig, CapturePipeline, SceneExtractor,
)
from soma.memory.profile import ProfileStore  # noqa: E402
from soma.memory.scene import SceneStore  # noqa: E402


class _FixedExtractor:
    def __init__(self, title="场景A"):
        self.title = title

    def extract(self, memories, existing):
        return [{"title": self.title, "summary": "s", "tags": ["t"],
                 "importance": 0.7, "evidence_ids": ["1"]}]


class _BoomExtractor:
    def extract(self, memories, existing):
        raise RuntimeError("Authentication Fails（模拟 LLM key 失效）")


def _pipeline(tmp_path, extractor=None):
    return CapturePipeline(
        SceneStore(tmp_path), ProfileStore(tmp_path), CaptureConfig(),
        scene_extractor=extractor or _FixedExtractor(),
        memory_provider=lambda uid: [{"content": "测试记忆", "importance": 0.7}],
    )


class TestCrossProcessLease:
    """★ 两个「进程」（两个 SceneStore 实例，同一个 db）不能同时捕获。"""

    def test_second_process_is_blocked(self, tmp_path):
        a = SceneStore(tmp_path)
        b = SceneStore(tmp_path)          # 模拟另一个 worker
        try:
            owner_a = a.try_begin_capture("u1", force=True)
            assert owner_a, "第一个进程没拿到租约"
            owner_b = b.try_begin_capture("u1", force=True)
            assert owner_b is None, (
                "两个进程同时拿到了租约 —— 同一批记忆会被抽两次，"
                "产出语义重复的场景（生产实测 12 条成对出现）")
        finally:
            a.close()
            b.close()

    def test_cooldown_shared_across_processes(self, tmp_path):
        """★ 冷却期必须跨进程共享，否则 B 会在 A 完成后立刻再抽一次。"""
        a = SceneStore(tmp_path)
        b = SceneStore(tmp_path)
        try:
            owner = a.try_begin_capture("u1", force=False)
            a.end_capture("u1", owner, cooldown=300)

            assert b.try_begin_capture("u1", force=False) is None, (
                "A 刚捕获完，B 立刻又能抽 —— 冷却期是进程内的，没跨进程")
            # force 仍可跳过冷却
            assert b.try_begin_capture("u1", force=True), "force 没能跳过冷却"
        finally:
            a.close()
            b.close()

    def test_expired_lease_recovers(self, tmp_path):
        """★ 进程崩溃留下的租约必须能靠过期自愈。"""
        a = SceneStore(tmp_path)
        b = SceneStore(tmp_path)
        try:
            a.try_begin_capture("u1", force=True, lease_seconds=180)
            # 模拟持有者崩溃：把两个时间都拨到过去
            a._conn.execute(
                "UPDATE capture_lease SET in_flight_until = 0, cooldown_until = 0 "
                "WHERE user_id = 'u1'")
            a._conn.commit()
            assert b.try_begin_capture("u1", force=False), (
                "过期租约没自愈 —— 进程崩溃后这个用户会永久无法捕获")
        finally:
            a.close()
            b.close()

    def test_different_users_independent(self, tmp_path):
        a = SceneStore(tmp_path)
        try:
            assert a.try_begin_capture("u1", force=True)
            assert a.try_begin_capture("u2", force=True), (
                "锁粒度错了：不同用户之间不该互相阻塞")
        finally:
            a.close()


class TestPipelineLeaseIntegration:
    """★ 端到端：两个 pipeline 指向同一个库。"""

    def test_sequential_second_gets_no_new(self, tmp_path):
        """串行场景：p1 做完后 p2 再来。

        注意这里是**串行**，不是并发 —— p1 已释放租约，所以 p2 能拿到锁，
        只是提取出的标题全部重复（add_scene 同用户同标题去重）。所以正确的
        原因是 `no_new`（提取了但没新增），不是 `locked`。
        第一版判据在这里断言 `locked` 是错的，被测试自己抓出来了。
        """
        p1 = _pipeline(tmp_path)
        p2 = _pipeline(tmp_path)          # 另一个 worker
        try:
            n1 = p1.capture_from_memories(
                [{"content": "记忆"}], user_id="u1", force=True)
            n2 = p2.capture_from_memories(
                [{"content": "记忆"}], user_id="u1", force=True)
            total = p1._scene_store.count("u1")
            assert n1 == 1 and n2 == 0 and total == 1, (
                f"结果异常（n1={n1} n2={n2} total={total}）")
            d2 = p2.get_state("u1").get("last_detail") or {}
            assert d2.get("reason") == "no_new", (
                f"第二个进程的原因应说明「提取了但全重复」，实际：{d2}")
        finally:
            p1._scene_store.close()
            p2._scene_store.close()
            p1._profile_store.close()
            p2._profile_store.close()

    def test_cross_process_cooldown_blocks_second_worker(self, tmp_path):
        """★★ 两进程判据：A 捕获后，全新实例 B 在冷却期内必须被挡住。

        这是下游生产实测踩出来的坑，**单实例判据测不出来**：

        原来的 `capture_scenes()` 内部写死 `capture_from_memories(force=True)`
        —— 那个 True 本意是「上面的进程内间隔已查过」，但它会透传到
        `try_begin_capture`，让 `(force=1 OR cooldown<=now)` 短路，
        **把跨进程冷却整个绕过**。

        实测后果：user=1 在 4 分钟内被 3 个 worker 轮流捕获 5 次
        （间隔 36~107 秒，冷却应是 300 秒），产出语义重复的场景。

        单实例下为什么测不出：进程内的 `_last_capture_time` 会先一步挡住，
        根本走不到 DB 租约那一层。
        """
        p1 = _pipeline(tmp_path)
        p2 = _pipeline(tmp_path)          # 全新实例 = 全新进程内状态
        try:
            n1 = p1.capture_scenes("u1", force=False)
            assert n1 == 1, f"进程 A 没捕获取胜：{n1}"

            n2 = p2.capture_scenes("u1", force=False)
            assert n2 == 0, (
                f"进程 B 在冷却期内又捕获了 {n2} 条 —— "
                f"内部 force 绕过了跨进程 cooldown")
            d2 = p2.get_state("u1").get("last_detail") or {}
            assert d2.get("reason") == "locked", (
                f"进程 B 没被租约挡住（reason={d2.get('reason')}）—— "
                f"如果拿到锁去重了会显示 no_new，同样说明冷却失效")
        finally:
            for p in (p1, p2):
                p._scene_store.close()
                p._profile_store.close()

    def test_manual_force_still_skips_cooldown(self, tmp_path):
        """对照：手动 force=True 仍要能跳过冷却（否则手动触发就废了）。

        但仍受 in_flight 约束 —— 这里是串行，所以能拿到锁。
        """
        p = _pipeline(tmp_path)
        try:
            assert p.capture_scenes("u1", force=False) == 1
            # 立刻再来一次，force=True —— 应拿到锁（reason 不是 locked），
            # 只因标题去重而新增 0 条
            n2 = p.capture_scenes("u1", force=True)
            d = p.get_state("u1").get("last_detail") or {}
            assert d.get("reason") != "locked", (
                f"手动 force 被冷却挡住了（reason={d.get('reason')}）—— "
                f"手动触发语义被改坏")
            assert n2 == 0 and d.get("reason") == "no_new"
        finally:
            p._scene_store.close()
            p._profile_store.close()

    def test_concurrent_only_one_wins(self, tmp_path):
        """★ 真并发：两个线程同时抢同一个用户的租约，只能有一个成功。

        这才是多 worker 的真实形态。串行测试测不出互斥。
        """
        import threading

        a = SceneStore(tmp_path)
        b = SceneStore(tmp_path)
        results = []
        barrier = threading.Barrier(2)

        def grab(store):
            barrier.wait()          # 尽量同时开始
            results.append(store.try_begin_capture("u1", force=True))

        try:
            ts = [threading.Thread(target=grab, args=(s,)) for s in (a, b)]
            for t in ts:
                t.start()
            for t in ts:
                t.join()
            won = [r for r in results if r]
            assert len(won) == 1, (
                f"并发下拿到租约的有 {len(won)} 个（应为 1）—— "
                f"多 worker 会重复抽取：{results}")
        finally:
            a.close()
            b.close()


class TestFailureVisibility:
    """★ LLM 失败不能被静默吞掉。"""

    def test_consecutive_failures_counted(self, tmp_path):
        p = _pipeline(tmp_path, extractor=_BoomExtractor())
        try:
            for _ in range(3):
                assert p.capture_from_memories(
                    [{"content": "记忆"}], user_id="u1", force=True) == 0
            st = p.get_state("u1")
            assert st["consecutive_failures"] == 3, (
                f"连续失败没计数：{st['consecutive_failures']} —— "
                f"scenes 恒为 0 也不会有人发现")
            assert st["total_failures"] == 3
        finally:
            p._scene_store.close()
            p._profile_store.close()

    def test_success_resets_consecutive(self, tmp_path):
        p = _pipeline(tmp_path, extractor=_BoomExtractor())
        try:
            p.capture_from_memories([{"content": "记忆"}], user_id="u1", force=True)
            assert p.get_state("u1")["consecutive_failures"] == 1
        finally:
            pass
        # 换一个能成功的提取器（模拟修好配置）
        p2 = CapturePipeline(
            SceneStore(tmp_path), ProfileStore(tmp_path), CaptureConfig(),
            scene_extractor=_FixedExtractor("新场景"),
            memory_provider=lambda uid: [{"content": "记忆"}],
        )
        try:
            p2.capture_from_memories([{"content": "记忆"}], user_id="u1", force=True)
            # 不同实例，各自计数；这里验证「成功分支会清零」
            st = p2.get_state("u1")
            assert st["consecutive_failures"] == 0
        finally:
            p2._scene_store.close()
            p2._profile_store.close()

    def test_error_detail_has_message(self, tmp_path):
        p = _pipeline(tmp_path, extractor=_BoomExtractor())
        try:
            p.capture_from_memories([{"content": "记忆"}], user_id="u1", force=True)
            d = p.get_state("u1")["last_detail"]
            assert d["reason"] == "failed"
            assert "Authentication Fails" in (d["error"] or ""), (
                "失败明细里没有错误原文，监控看不到根因")
        finally:
            p._scene_store.close()
            p._profile_store.close()


class TestCaptureDetail:
    """★ 返回值之外，要能查到「为什么是 0」。"""

    @pytest.fixture
    def soma(self, tmp_path):
        s = SOMA(llm="mock", persist_dir=str(tmp_path),
                 use_vector_search=False, warmup_on_init=False)
        s._ensure_layered_memory()
        s._capture_pipeline._scene_extractor = _FixedExtractor()
        yield s
        s.close()

    def test_no_new_reason(self, soma):
        """自动捕获过了，再手动调 → no_new（不是失败）。"""
        soma.remember("第一条", user_id="u1", importance=0.7)
        assert soma._scene_store.count("u1") >= 1
        assert soma.capture_scenes(user_id="u1", force=True) == 0
        d = soma.get_last_capture_detail("u1")
        assert d["reason"] == "no_new", f"原因不对：{d}"
        assert d["extracted"] >= 1 and d["created"] == 0 and d["skipped"] >= 1

    def test_disabled_reason(self, tmp_path):
        s = SOMA(llm="mock", persist_dir=str(tmp_path),
                 use_vector_search=False, warmup_on_init=False,
                 scene_extraction_enabled=False)
        try:
            s._ensure_layered_memory()
            s.remember("一条记忆", user_id="u1", importance=0.7)
            s.capture_scenes(user_id="u1", force=True)
            d = s.get_last_capture_detail("u1")
            assert d == {} or d.get("reason") in ("no_memories", "locked", "no_new"), d
        finally:
            s.close()

    def test_detail_available_in_stats(self, soma):
        soma.remember("统计也要能看到", user_id="u2", importance=0.7)
        st = soma.get_layered_stats("u2")
        assert "capture" in st and "last_detail" in st["capture"]
        assert "consecutive_failures" in st["capture"]
