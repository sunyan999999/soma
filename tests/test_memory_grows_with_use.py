# -*- coding: utf-8 -*-
"""「越用越懂」的机制判据（2026-10-20）。

## 用户的原话

> 让超秘的各個能力真正变强、变得更好用……**无论在任何对话或者任务中发出的
> 需求和指令，都能有始有终，给用户最满意的结果和答复**。

「越用越懂」是这条里的核心 —— 如果聊了三个月它还不记得你是谁，
再多的功能也谈不上"懂"。

## 之前为什么做不到

两处叠加：

**① 检索排序不知道哪条重要**（`memory/core.py:_hybrid_search`）

    time_penalty = exp(-days / 7)      # 半衰期写死
    score *= time_penalty              # **不乘 importance**

「用户叫孙岩」和「今天天气不错」被乘上**同一个**系数。

**② 半衰期一律 7 天**（`base.py`）

    7 天 → 50%，30 天 → 1.4%，100 天 → 0.0001%

**任何**记忆都扛不过一个月 —— 包括一辈子有效的事实。

## 现在的语义

半衰期由三个因子决定（`MemoryUnit.effective_half_life()`）：

| 因子 | 作用 |
|---|---|
| `importance` > 0.6 | 开始保护，1.0 时半衰期 ×4（7 → 28 天） |
| `nature=fact` | ×3（事实/技能长期有效） |
| `nature=state` | ×0.5（状态快速过期） |
| `access_count` | 每次 +10%，封顶 +100%（被反复回忆的忘得慢） |

**`importance ≤ 0.6` 的普通记忆行为完全不变** —— 不是把所有记忆都延长。

## 注入自证

  · `effective_half_life` 里去掉 importance 保护 → `TestHalfLifeTiers` 红；
  · 去掉 nature 因子 → `test_fact_outlives_state` 红；
  · `_hybrid_search` 里不乘 importance → `TestRankingUsesImportance` 红。
"""
from __future__ import annotations

import datetime as _dt
import inspect
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from soma.base import (  # noqa: E402
    IMPORTANCE_PROTECT_FLOOR, NATURE_HALF_LIFE_FACTOR, RECENCY_HALF_LIFE_DAYS,
    MemoryUnit,
)


def _mu(days_old: float = 0, **kw) -> MemoryUnit:
    ts = _dt.datetime.now(_dt.timezone.utc).timestamp() - days_old * 86400
    return MemoryUnit(content="x", timestamp=ts, **kw)


class TestHalfLifeTiers:
    """★ 半衰期要**分级** —— 重要的事忘得慢。"""

    def test_ordinary_memory_unchanged(self):
        """★ 普通记忆（importance ≤ 0.6）行为**完全不变**。

        这条很重要：不能为了"越用越懂"把所有记忆都延长，
        否则记忆库会被琐事塞满、检索质量反而下降。
        """
        for imp in (0.1, 0.3, 0.5, IMPORTANCE_PROTECT_FLOOR):
            assert _mu(importance=imp).effective_half_life() == pytest.approx(
                RECENCY_HALF_LIFE_DAYS), f"importance={imp} 的普通记忆被改了"

    def test_importance_extends_half_life(self):
        """importance 越高，半衰期越长（单调）。"""
        hs = [_mu(importance=i / 10).effective_half_life() for i in range(11)]
        assert hs == sorted(hs), f"半衰期没有随 importance 单调增加：{hs}"
        assert hs[-1] > hs[0] * 2, "importance=1.0 的半衰期没明显长于 importance=0"

    def test_top_importance_is_four_times(self):
        """importance=1.0（没设 nature）时半衰期应达基准的 4 倍。"""
        m = _mu(importance=1.0, nature="event")
        assert m.effective_half_life() == pytest.approx(
            RECENCY_HALF_LIFE_DAYS * 4.0, rel=0.01)

    def test_fact_outlives_state(self):
        """★ 事实长期有效，状态快速过期 —— 同一 importance 下。"""
        fact = _mu(importance=0.9, nature="fact").effective_half_life()
        event = _mu(importance=0.9, nature="event").effective_half_life()
        state = _mu(importance=0.9, nature="state").effective_half_life()
        assert fact > event > state, (
            f"nature 没有拉开差距：fact={fact:.1f} event={event:.1f} state={state:.1f}")
        assert fact == pytest.approx(event * NATURE_HALF_LIFE_FACTOR["fact"])

    def test_recall_extends_half_life(self):
        """被反复回忆的事忘得慢（艾宾浩斯的"重复"效应）。"""
        cold = _mu(importance=0.8, access_count=0).effective_half_life()
        warm = _mu(importance=0.8, access_count=5).effective_half_life()
        hot = _mu(importance=0.8, access_count=50).effective_half_life()
        assert cold < warm < hot
        # 封顶 +100%：50 次和 10 次一样
        assert hot == pytest.approx(_mu(importance=0.8, access_count=10)
                                    .effective_half_life())


class TestTheThingUsersFeel:
    """★ 用户能感知的那件事：三个月后它还记得你。"""

    def test_core_fact_survives_three_months(self):
        """**「用户叫孙岩」90 天后仍然检索得到。**

        旧机制：`exp(-90/7) × 0.95 = 0.00023` —— 等于不存在。
        """
        m = _mu(days_old=90, importance=0.95, nature="fact", access_count=8)
        score = m.relevance_potential()
        assert score > 0.15, (
            f"核心事实 90 天后只剩 {score:.4f} —— "
            f"用户会觉得「它根本不记得我」")

    def test_trivia_is_gone_after_three_months(self):
        """对照：**琐事**三个月后该基本消失（不能什么都记）。"""
        m = _mu(days_old=90, importance=0.2, nature="event")
        assert m.relevance_potential() < 0.001

    def test_state_expires_fast(self):
        """状态类（最近失眠）一周后明显弱化 —— 它本来就不该长期当"当前状态"。"""
        m = _mu(days_old=7, importance=0.7, nature="state")
        fresh = _mu(days_old=0, importance=0.7, nature="state")
        assert m.relevance_potential() < fresh.relevance_potential() * 0.5


class TestRankingUsesImportance:
    """★ 检索排序必须知道哪条重要（源码契约）。"""

    def test_hybrid_search_uses_effective_half_life(self):
        """★ 排序要同时用上**分级半衰期**和 **importance 权重**。

        ⚠️ 判据必须钉**完整语句**，不能只查 `"importance" in src` ——
        那行前面还有 `importance = max(...)` 的取值语句，把
        `score *= time_penalty * (0.3 + 0.7 * importance)` 改回
        `score *= time_penalty` 之后，`"importance"` **仍然在源码里**，
        判据照样绿（2026-10-20 注入自证实测踩到）。
        """
        from soma.memory import core as C
        src = inspect.getsource(C.MemoryCore._hybrid_search)
        assert "effective_half_life()" in src, (
            "检索排序还在用写死的半衰期 —— 老的重要记忆排不到前面")
        assert "score *= time_penalty * (0.3 + 0.7 * importance)" in src, (
            "检索排序没有把 importance 乘进分数 —— "
            "「用户叫孙岩」和「今天天气不错」会被同等对待")

    def test_two_decay_paths_agree(self):
        """★ 两套衰减机制要**一致**。

        `MemoryUnit.relevance_potential()` 和 `_hybrid_search` 的打分
        以前各写一套（一套乘 importance、一套不乘）—— 那正是审计 C01
        「多套机制互相冲突」的形状。现在两边都用 `effective_half_life()`。
        """
        from soma.memory import core as C
        src = inspect.getsource(C.MemoryCore._hybrid_search)
        assert "math.exp(-max(days, 0) / 7" not in src, \
            "检索里还硬编码着 7 天半衰期"
        # base 那边也必须用同一个函数
        from soma.base import MemoryUnit as M
        assert "effective_half_life()" in inspect.getsource(M.relevance_potential)
