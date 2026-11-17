# -*- coding: utf-8 -*-
"""L2 场景 / L3 画像：从「开关打开了」到「真的转起来」。

## 背景（2026-11-17）

2.0.20 宣称「L2 场景 / L3 画像默认开启」，下游实测 `scenes 0 / profile_entries 0`。
当时归因为「要攒够 5 条场景才出画像」—— **归因错了**。真实情况是三重断点：

1. **双减默认值**：`soma/config.py` 里改成 True，但 `SOMA.__init__` 自己有一份
   `scene_extraction_enabled: bool = False`，且用它**显式**构造 SOMAConfig
   （`SOMAConfig(scene_extraction_enabled=scene_extraction_enabled)`）——
   门面默认值反向覆盖了配置默认值。走 `SOMA()` 的接入方拿到的永远是 False。

2. **`capture_scenes()` 硬编码 `return 0`**：
   ```python
   return 0  # 实际提取逻辑在 capture_from_memories()
   ```
   而唯一自动链路 `remember() → on_new_memory() → capture_scenes()` 每次都
   停在这一行。`capture_from_memories()` 只有手工传 memories 才能到。

3. **没有记忆来源**：CapturePipeline 不持有 episodic store，
   `SceneExtractor` 需要的记忆列表没人喂。

结果：「自动场景提取」自 v0.10.0 引入起来就没自动过。

## 修法

- 门面参数改 `Optional[bool] = None` —— None 表示**跟随 SOMAConfig**，
  显式传值才覆盖。配置层成为唯一真源，消除双减。
- `CapturePipeline` 新增 `memory_provider` 注入；`capture_scenes()` 用它取
  近期记忆再走 `capture_from_memories()`。**没有 provider 时保持原行为返回 0**
  （向后兼容，老调用方语义不变）。

## 注入自证

  · 门面参数默认改回 False            → TestFacadeDefaults 红
  · `capture_scenes` 改回 `return 0`  → TestAutoCapture 红
  · provider 返回空列表               → TestAutoCapture 红
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from soma import SOMA  # noqa: E402
from soma.config import SOMAConfig  # noqa: E402
from soma.memory.capture import CaptureConfig, CapturePipeline  # noqa: E402


class _FakeExtractor:
    """不依赖 LLM 的假场景提取器 —— mock 模式下默认提取器返回空列表。"""

    def __init__(self):
        self.calls = 0
        self.seen_memories = []

    def extract(self, memories, existing_scene_titles):
        self.calls += 1
        self.seen_memories = list(memories)
        return [{
            "title": f"场景-{self.calls}",
            "summary": "测试场景摘要",
            "tags": ["测试"],
            "importance": 0.7,
            "evidence_ids": ["1"],
        }]


def _soma(tmp_path, **kw):
    return SOMA(llm="mock", persist_dir=str(tmp_path),
                use_vector_search=False, warmup_on_init=False, **kw)


class TestFacadeDefaults:
    """★ 断点 1：门面默认值不能再覆盖配置默认值。"""

    def test_config_default_is_true(self):
        cfg = SOMAConfig()
        assert cfg.scene_extraction_enabled is True, "配置层默认值被改了"
        assert cfg.profile_extraction_enabled is True

    def test_soma_facade_follows_config(self, tmp_path):
        """★ `SOMA()` 不传参时，必须跟随配置（True），而不是门面自己的 False。"""
        s = _soma(tmp_path)
        try:
            assert s._config.scene_extraction_enabled is True, (
                "SOMA() 默认构造下场景提取是关的 —— 门面默认值又覆盖了配置")
            assert s._config.profile_extraction_enabled is True
        finally:
            s.close()

    def test_explicit_false_still_works(self, tmp_path):
        """显式关掉依然有效（后端兼容）。"""
        s = _soma(tmp_path, scene_extraction_enabled=False)
        try:
            assert s._config.scene_extraction_enabled is False
            # 没显式传的那个仍跟随配置
            assert s._config.profile_extraction_enabled is True
        finally:
            s.close()

    def test_explicit_true_on_other_axis(self, tmp_path):
        s = _soma(tmp_path, profile_extraction_enabled=False)
        try:
            assert s._config.scene_extraction_enabled is True
            assert s._config.profile_extraction_enabled is False
        finally:
            s.close()

    def test_defaults_are_none_not_bool(self):
        """★ 结构性判据：两个参数的默认值必须是 None。

        改回 `bool = False` / `bool = True` 都会重新制造双减：
        前者让配置失效，后者让「配置里关掉」失效。
        """
        sig = inspect.signature(SOMA.__init__)
        for name in ("scene_extraction_enabled", "profile_extraction_enabled"):
            assert sig.parameters[name].default is None, (
                f"{name} 的默认值是 {sig.parameters[name].default!r}，"
                f"应为 None（跟随 SOMAConfig）")


class TestAutoCapture:
    """★ 断点 2/3：remember() 必须真的能把记忆变成场景。"""

    def test_auto_capture_creates_scene(self, tmp_path):
        """端到端：存够 warmup 条数 → 场景落库。"""
        s = _soma(tmp_path)
        try:
            s._ensure_layered_memory()
            fake = _FakeExtractor()
            s._capture_pipeline._scene_extractor = fake

            for i in range(CaptureConfig().scene_warmup + 1):
                s.remember(f"关于排期的第{i}条备忘：内容{i}", user_id="u1",
                           importance=0.7)

            assert fake.calls >= 1, (
                "场景提取器一次都没被调用 —— remember() 到不了提取逻辑")
            assert s._scene_store.count("u1") >= 1, "提取器调了但场景没落库"
        finally:
            s.close()

    def test_provider_receives_real_memories(self, tmp_path):
        """★ provider 必须喂进真实记忆内容，而不是空壳。"""
        s = _soma(tmp_path)
        try:
            s._ensure_layered_memory()
            fake = _FakeExtractor()
            s._capture_pipeline._scene_extractor = fake

            s.remember("独一无二的标记文本-甲", user_id="u1", importance=0.8)
            for i in range(CaptureConfig().scene_warmup):
                s.remember(f"填充记忆{i}", user_id="u1", importance=0.6)

            assert fake.seen_memories, "提取器收到的记忆列表是空的"
            joined = " ".join(str(m.get("content", "")) for m in fake.seen_memories)
            assert "独一无二的标记文本-甲" in joined, (
                "provider 喂给提取器的记忆里没有真实内容 —— "
                "接线接错了地方")
        finally:
            s.close()

    def test_interval_throttle_caps_llm_cost(self, tmp_path):
        """★ 成本闸：连续写入不能每次触发一次 LLM 调用。

        这里有个容易误读的设计：`enable_warmup=True` 时**初始阈值是 1**
        （不是 scene_warmup），即「第一条记忆就产出一个场景」—— 渐进预热，
        之后阈值 1→2→4→5 翻倍拉长。

        真正的成本闸是 `scene_min_interval`（默认 300 秒）：首次捕获后，
        5 分钟内的后续写入一律不触发。这条判据钉住它。
        """
        s = _soma(tmp_path)
        try:
            s._ensure_layered_memory()
            fake = _FakeExtractor()
            s._capture_pipeline._scene_extractor = fake

            for i in range(10):
                s.remember(f"密集记忆{i}", user_id="u1", importance=0.6)

            assert fake.calls == 1, (
                f"连写 10 条触发了 {fake.calls} 次提取 —— "
                f"scene_min_interval 节流失效，接入方会按写入量烧 LLM 调用")
        finally:
            s.close()

    def test_first_write_produces_scene(self, tmp_path):
        """渐进预热的正面：第一条记忆就该能产出场景（不用等攒 5 条）。"""
        s = _soma(tmp_path)
        try:
            s._ensure_layered_memory()
            fake = _FakeExtractor()
            s._capture_pipeline._scene_extractor = fake

            s.remember("第一条记忆", user_id="u1", importance=0.8)
            assert fake.calls == 1
            assert s._scene_store.count("u1") == 1
        finally:
            s.close()

    def test_real_extractor_parses_llm_json(self, tmp_path):
        """★ 不 fake 提取器，只替换 LLM 调用 —— 走 prompt→JSON→落库整条真路径。

        `_FakeExtractor` 绕过了 `SceneExtractor.extract()` 和
        `_parse_response()`；万一 prompt 构造或 JSON 解析坏了，上面那些判据
        仍然全绿。这条把中间层都真跑一遍，只把「模型输出」换成固定值。
        """
        from soma.memory.capture import SceneExtractor

        s = _soma(tmp_path)
        try:
            s._ensure_layered_memory()
            s._capture_pipeline._scene_extractor = SceneExtractor(
                llm_call=lambda prompt: (
                    '{"scenes": [{"title": "排期管理", '
                    '"summary": "用户近期在处理排期", "tags": ["工作"], '
                    '"importance": 0.8, "evidence_ids": ["1"]}]}'
                )
            )

            s.remember("下周三要交排期表", user_id="u1", importance=0.8)

            scenes = s.get_scenes("u1")
            assert scenes, "真实解析路径没产出场景"
            assert scenes[0]["title"] == "排期管理", (
                f"场景标题对不上：{scenes[0].get('title')!r}")
        finally:
            s.close()

    def test_malformed_llm_output_does_not_crash(self, tmp_path):
        """LLM 返回废话时，remember() 不能被炸掉。"""
        from soma.memory.capture import SceneExtractor

        s = _soma(tmp_path)
        try:
            s._ensure_layered_memory()
            s._capture_pipeline._scene_extractor = SceneExtractor(
                llm_call=lambda prompt: "抱歉，我无法完成这个任务。"
            )
            s.remember("一条普通记忆", user_id="u1", importance=0.7)
            assert s._scene_store.count("u1") == 0
            # 记忆本身必须还在
            assert s._agent.memory.episodic.count() >= 1
        finally:
            s.close()

    def test_disabled_means_no_extraction(self, tmp_path):
        """显式关掉后，一条 LLM 都不该调。"""
        s = _soma(tmp_path, scene_extraction_enabled=False)
        try:
            s._ensure_layered_memory()
            fake = _FakeExtractor()
            s._capture_pipeline._scene_extractor = fake

            for i in range(CaptureConfig().scene_warmup + 2):
                s.remember(f"记忆{i}", user_id="u1", importance=0.7)

            assert fake.calls == 0, "关掉了还在提取"
            assert s._scene_store.count("u1") == 0
        finally:
            s.close()


class TestBackwardCompat:
    """★ 没有 provider 的老调用方，行为必须完全不变。"""

    def test_pipeline_without_provider_returns_zero(self, tmp_path):
        from soma.memory.scene import SceneStore
        from soma.memory.profile import ProfileStore

        pipe = CapturePipeline(
            SceneStore(tmp_path), ProfileStore(tmp_path), CaptureConfig(),
            scene_extractor=_FakeExtractor(),
        )
        assert pipe.capture_scenes("u1", force=True) == 0, (
            "没注入 memory_provider 却开始提取了 —— 老调用方语义被改")
        assert pipe.capture_scenes("u1") == 0

    def test_provider_exception_is_contained(self, tmp_path):
        """provider 抛异常不能冒泡到 remember()。"""
        from soma.memory.scene import SceneStore
        from soma.memory.profile import ProfileStore

        def boom(uid):
            raise RuntimeError("取数炸了")

        pipe = CapturePipeline(
            SceneStore(tmp_path), ProfileStore(tmp_path), CaptureConfig(),
            scene_extractor=_FakeExtractor(), memory_provider=boom,
        )
        assert pipe.capture_scenes("u1", force=True) == 0, (
            "provider 异常没被吞掉，会炸穿 remember()")


class TestSomaProviderWiring:
    """★ 门面必须真的把 provider 接上。"""

    def test_provider_is_wired(self, tmp_path):
        s = _soma(tmp_path)
        try:
            s._ensure_layered_memory()
            assert s._capture_pipeline._memory_provider is not None, (
                "CapturePipeline 没接上 memory_provider —— "
                "capture_scenes() 会永远 return 0")
        finally:
            s.close()

    def test_provider_reads_from_episodic(self, tmp_path):
        s = _soma(tmp_path)
        try:
            s.remember("provider 直读取证", user_id="u9", importance=0.9)
            mems = s._recent_memories_for_capture("u9")
            assert mems, "provider 取不到记忆"
            assert any("provider 直读取证" in m["content"] for m in mems)
            # 用户隔离
            assert s._recent_memories_for_capture("other") == [], (
                "provider 没按 user_id 隔离")
        finally:
            s.close()
