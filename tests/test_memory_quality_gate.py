# -*- coding: utf-8 -*-
"""记忆写入的质量门控（2026-10-20）。

## 为什么

`remember()` 之前**什么都记**：'你好'、'好的'、'嗯'、用户重复说的话。
后果不是"存不下"，而是**检索时噪音压倒信号** —— 真正重要的事
（"用户叫孙岩"）和"好的"在同一个池子里竞争 top_k。

「越用越懂」的前提是**池子里装的是值得记的东西**。

## 三条设计约束

1. **不按长度挡** —— "用户叫孙岩" 6 个字，比 200 字的寒暄重要得多；
2. **寒暄用精确匹配** —— 模糊匹配会把"你好，我叫孙岩"当成寒暄杀掉；
3. **重复只做归一化全等** —— 相似度阈值松一点就会误杀
   （"用户喜欢 Python" / "用户不喜欢 Java" 很像，但都是真信息）。

## 注入自证

  · `check()` 里去掉寒暄判断 → `TestDropsNoise` 红；
  · `is_duplicate` 改成"包含即重复" → `test_similar_but_different_survives` 红；
  · `remember()` 里不调 `should_store` → `test_remember_actually_gates` 红。
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from soma.memory.quality import (  # noqa: E402
    check, is_duplicate, normalize, should_store,
)


class TestDropsNoise:
    """★ 噪音要被挡住 —— 但只挡**确定的**噪音。"""

    @pytest.mark.parametrize("noise", [
        "你好", "你好！", "您好", "好的", "嗯", "嗯嗯", "哦",
        "谢谢", "多谢", "收到", "OK", "ok", "hi", "hello",
    ])
    def test_greetings_are_dropped(self, noise):
        store, why = should_store(noise)
        assert not store, f"{noise!r} 被写进记忆了"
        assert why

    @pytest.mark.parametrize("empty", ["。。。", "……", " ", "\n\t", "!", "？"])
    def test_empty_content_is_dropped(self, empty):
        store, why = should_store(empty)
        assert not store, f"{empty!r} 被写进记忆了"


class TestNeverDropsRealInformation:
    """★★ **最重要的那一半** —— 真信息一条都不能丢。"""

    @pytest.mark.parametrize("real", [
        "用户叫孙岩",                        # 6 个字，但库里最值钱的东西
        "这个项目用 Python 3.13",
        "用户喜欢简洁的回答",
        "帮我分析这份数据",
        "明天下午三点开会",
    ])
    def test_short_but_important_survives(self, real):
        store, _ = should_store(real)
        assert store, f"真信息 {real!r} 被门控挡住了 —— 这比不挡更糟"

    def test_greeting_plus_content_survives(self):
        """★ 「你好，我叫孙岩」**不是寒暄**。

        这正是"寒暄必须精确匹配"的原因：用包含匹配的话，
        这句话会被整条丢掉，而真正要记的"我叫孙岩"就在里面。
        """
        store, why = should_store("你好，我叫孙岩")
        assert store, f"「你好，我叫孙岩」被当成寒暄丢了（原因：{why}）"

    def test_similar_but_different_survives(self):
        """★ 字面很像但意思不同 —— **不能算重复**。

        重复检测只做"归一化后全等"。一旦改成相似度/包含匹配，
        "用户不喜欢 Java" 会被"用户喜欢 Python"挡掉。
        """
        recent = ["用户喜欢 Python"]
        assert should_store("用户不喜欢 Java", recent=recent)[0], \
            "「不喜欢 Java」被当成「喜欢 Python」的重复丢掉了"

    def test_substring_is_not_duplicate(self):
        """★★ **短句被长句"包含"不等于重复** —— 这是包含匹配最典型的误杀。

        真实场景：
            recent = ["用户明天下午三点在会议室开会"]
            new    = "用户明天下午"          ← 更短，但可能是另一条独立信息

        如果重复判定写成 `target in recent`，上面这条会被整条丢掉。
        而"重复"在语义上要求**说的是同一件事** —— 归一化全等才够格。
        """
        recent = ["用户明天下午三点在会议室开会"]
        assert should_store("用户明天下午", recent=recent)[0], (
            "短句被长句包含就判成重复 —— 包含匹配的误杀")

    def test_longer_superset_is_not_duplicate(self):
        """反方向：新句子**包含**旧记忆，也不是重复（它在补信息）。"""
        recent = ["用户叫孙岩"]
        assert should_store("用户叫孙岩，住在杭州", recent=recent)[0], (
            "补充信息被当成重复丢掉了")


class TestDuplicate:
    """★ 归一化后完全相同 = 重复。"""

    def test_exact_duplicate(self):
        assert is_duplicate("用户叫孙岩", ["用户叫孙岩"])

    def test_punctuation_variant_is_duplicate(self):
        """★ 只差标点/空白 —— 这是同一句话说了两遍。"""
        for variant in ("用户叫孙岩。", "用户叫孙岩！", " 用户叫孙岩 "):
            assert is_duplicate(variant, ["用户叫孙岩"]), \
                f"{variant!r} 没被认成重复"

    def test_slightly_different_is_not_duplicate(self):
        assert not is_duplicate("用户叫孙岩岩", ["用户叫孙岩"])

    def test_empty_recent_never_blocks(self):
        assert not is_duplicate("用户叫孙岩", [])
        assert not is_duplicate("用户叫孙岩", None)


class TestNormalize:
    def test_strips_punctuation_and_space(self):
        assert normalize("  你好，世界！ ") == "你好世界"

    def test_lowercases(self):
        assert normalize("OK") == normalize("ok")


class TestSwitch:
    def test_can_be_disabled(self):
        """★ 关掉门控时**一条都不挡**（有些接入方要存全量日志）。"""
        assert should_store("你好", enabled=False)[0]
        assert should_store("。。。", enabled=False)[0]


class TestRememberActuallyGates:
    """★ 接线判据：`remember()` 要**真的**调门控。

    光有 `quality.py` 不算数 —— 不接进写入路径等于没做。
    """

    def test_remember_calls_should_store(self):
        from soma.memory import core as C
        src = inspect.getsource(C.MemoryCore.remember)
        assert "should_store" in src, \
            "`remember()` 没接质量门控 —— 门控模块写了等于没写"
        assert "return \"\"" in src or "return ''" in src, (
            "被挡时没返回空串 —— 调用方会以为写成功了")

    def test_gate_is_closeable_from_config(self):
        from soma.memory import core as C
        src = inspect.getsource(C.MemoryCore.__init__)
        assert "memory_quality_gate" in src, "配置开关没接到 MemoryCore"

    def test_end_to_end_blocks_greeting(self, tmp_path):
        """★ 端到端：真建一个库，写一句寒暄，库里的条数不该增加。"""
        from soma.config import SOMAConfig
        from soma.memory.core import MemoryCore

        cfg = SOMAConfig(episodic_persist_dir=str(tmp_path))
        core = MemoryCore(cfg)
        before = core.episodic.count()
        assert core.remember("你好") == "", "寒暄居然拿到了 memory_id"
        assert core.episodic.count() == before, "寒暄被写进库了"

        mid = core.remember("用户叫孙岩")
        assert mid, "真信息没写进去"
        assert core.episodic.count() == before + 1
