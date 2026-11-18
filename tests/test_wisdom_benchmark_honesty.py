# -*- coding: utf-8 -*-
"""智慧基准的两个口径错误 —— 让尺子先说真话。

## 背景（2026-11-17）

排查「智慧分 75.4 是四个维度里唯一短板」时，先把细分拉出来，结果发现
**这把尺子本身是坏的**：

    law_recall = 1.2381        ← 召回率超过 100%？

### 错误 1：分子用了「触发量」而不是「命中量」

```python
actual = set(f.law_id for f in foci)
law_hit_total += len(actual)        # ← 数了触发几个，不看对不对
law_expected_total += len(expected)
bm.law_recall = law_hit_total / law_expected_total
```

这不是召回率，是「触发了多少个 / 应该触发多少个」。后果：

- 结果可以超过 1.0（实测 1.2143）
- **方向是反的**：乱触发越多，分数越高。一个把七个规律全触发一遍的
  实现会拿到极高的「召回率」，哪怕一个都没猜对。

实测：预期规律 42 个，实际触发 51 个，**真命中只有 22 个**
→ 旧尺子 1.2143，真召回 0.5238。

### 错误 2：`combo_*` 被当成第 8 个规律

`combo_a_b` 是「规律 a 和 b 同时触发」时追加的复合视角
（`soma/engine.py` 阶段 2.5），不是基本规律。而预期数据集只标注
7 个基本规律 —— 于是：

- 算进 `law_hit_total` 会虚增触发数，且永远不可能匹配上预期
- 算进多样性熵的分母会让 `probs` 之和 < 1，熵值失真

## 注入自证

  · 分子改回 `len(actual)`          → TestRecallIsHitRate 红
  · 熵分母改回 `sum(law_hits.values())` → TestDiversityDenominator 红
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from soma.base import Focus  # noqa: E402
from soma.benchmarks import run_wisdom_benchmark, _load_test_dataset  # noqa: E402


class _FakeHub:
    def activate(self, foci, **kw):
        return []


class _FakeAgent:
    """返回固定 foci 的假 agent —— 把「模型行为」变成可控输入。"""

    def __init__(self, law_ids):
        self._law_ids = law_ids
        self.hub = _FakeHub()

    def decompose(self, problem):
        return [
            Focus(law_id=lid, dimension=f"测试视角 {lid}",
                  keywords=["测试"], weight=1.0, rationale="t")
            for lid in self._law_ids
        ]


def _run(law_ids):
    return run_wisdom_benchmark(_FakeAgent(law_ids))


class TestRecallIsHitRate:
    """★ 召回率必须是「命中 / 预期」，不能是「触发 / 预期」。"""

    def test_never_exceeds_one(self):
        """把七个规律全触发一遍，召回率也不该超过 1.0。

        这是最直接的回归线：旧实现下「全触发」会拿到远超 1 的分。
        """
        all_laws = [
            "first_principles", "systems_thinking", "contradiction_analysis",
            "pareto_principle", "inversion", "analogical_reasoning",
            "evolutionary_lens",
        ]
        bm = _run(all_laws)
        assert bm.law_recall <= 1.0, (
            f"law_recall = {bm.law_recall} > 1.0 —— 又算成触发量了")

    def test_spam_triggering_scores_zero_not_high(self):
        """★ 只触发一个「预期里不可能有」的规律 → 召回必须是 0。

        旧实现下这一项会得到一个正数（因为只看触发数量），
        这正是「乱触发反而得分」的根源。

        故意用一个不存在的 id：它保证不出现在任何预期里，判据不会因为
        数据集改动而变成 skip。
        """
        bm = _run(["not_a_real_law_id"])
        assert bm.law_recall == 0.0, (
            f"触发的规律一个都没命中预期，召回却是 {bm.law_recall}")

    def test_combo_not_counted_as_law(self):
        """★ 只触发 combo_* 时，召回必须是 0。

        combo 是复合视角，不是基本规律。旧实现会把它算进触发量。
        """
        bm = _run(["combo_first_principles_systems_thinking"])
        assert bm.law_recall == 0.0, (
            f"combo 被当成基本规律算进召回了：{bm.law_recall}")

    def test_correct_hit_is_counted(self):
        """对照：真的命中时要算进去（别修过头把召回改成恒 0）。"""
        # first_principles 在数据集里出现频率很高
        bm = _run(["first_principles"])
        assert bm.law_recall > 0, "命中了预期规律却算 0 —— 修过头了"
        assert bm.law_recall <= 1.0


class TestDiversityDenominator:
    """★ 多样性熵的分母只能是 7 个基本规律。"""

    def test_combo_only_gives_zero_entropy(self):
        """只触发 combo → 基本规律一个都没触发 → 熵应为 0。"""
        bm = _run(["combo_first_principles_systems_thinking"])
        assert bm.thinking_diversity_entropy == 0.0, (
            f"只触发了 combo，多样性熵却是 {bm.thinking_diversity_entropy}")

    def test_uniform_triggers_max_entropy(self):
        """七个规律均匀触发 → 归一化熵应接近 1.0。"""
        all_laws = [
            "first_principles", "systems_thinking", "contradiction_analysis",
            "pareto_principle", "inversion", "analogical_reasoning",
            "evolutionary_lens",
        ]
        bm = _run(all_laws)
        assert bm.thinking_diversity_entropy > 0.99, (
            f"均匀触发七个规律，熵只有 {bm.thinking_diversity_entropy}")

    def test_combo_does_not_dilute_entropy(self):
        """★ combo 不该稀释熵：加不加 combo，同样 7 规律的熵应一致。"""
        all_laws = [
            "first_principles", "systems_thinking", "contradiction_analysis",
            "pareto_principle", "inversion", "analogical_reasoning",
            "evolutionary_lens",
        ]
        without = _run(all_laws)
        with_combo = _run(all_laws + ["combo_first_principles_systems_thinking"])
        assert abs(without.thinking_diversity_entropy
                   - with_combo.thinking_diversity_entropy) < 1e-6, (
            "combo 稀释了多样性熵 —— 分母里混进了非基本规律")


class TestDecompositionPrecision:
    """★ 精准度同理：combo 不该参与基本规律的命中计算。"""

    def test_combo_does_not_raise_precision(self):
        with_combo = _run(["combo_first_principles_systems_thinking"])
        assert with_combo.decomposition_precision == 0.0, (
            f"combo 拉高了精准度：{with_combo.decomposition_precision}")


class TestSamplingModes:
    """★ 抽样口径（2026-11-24 新增）。

    背景：原来固定 `test_questions[:15]`，而这 15 题恰好全是
    「跨域推理 10 + 深层归因 5」—— 没有战略决策/创新设计/经验借鉴。
    下游核对标注时发现，对外报的 law_recall 只代表这个子集。
    """

    def test_default_is_first15_for_compat(self):
        """默认必须还是 first15 —— 改了会切断历史数据可比性。"""
        import inspect
        sig = inspect.signature(run_wisdom_benchmark)
        assert sig.parameters["sample"].default == "first15"

    def test_first15_is_biased(self):
        """留档：first15 的类别分布确实是偏置的（不是缺陷，是已知事实）。"""
        from soma.benchmarks import _sample_questions, _load_test_dataset
        picked = _sample_questions(_load_test_dataset(), "first15")
        cats = {q.get("category") for q in picked}
        assert cats == {"跨域推理", "深层归因"}, (
            f"前 15 题的类别变了：{cats} —— 如果数据集顺序调整过，"
            f"历史分数的可比性要重新评估")

    def test_stratified_is_balanced(self):
        """分层抽样每类都要有，且总题数仍是 15（便于与 first15 对照）。"""
        from soma.benchmarks import _sample_questions, _load_test_dataset
        picked = _sample_questions(_load_test_dataset(), "stratified")
        assert len(picked) == 15
        cats = [q.get("category") for q in picked]
        assert len(set(cats)) == 5, f"分层后仍只有 {set(cats)} 类"
        for c in set(cats):
            assert cats.count(c) == 3, f"{c} 抽了 {cats.count(c)} 题（应为 3）"

    def test_all_covers_dataset(self):
        from soma.benchmarks import _sample_questions, _load_test_dataset
        qs = _load_test_dataset()
        assert len(_sample_questions(qs, "all")) == len(qs)

    def test_sample_mode_recorded_in_details(self):
        """口径必须出现在 details 里，否则读分数的人不知道是哪种。"""
        bm = _run_with_mode("stratified")
        assert bm.details.get("sample_mode") == "stratified"
        assert bm.details.get("scored_questions") == 15
        assert bm.details.get("scored_categories")

    def test_stratified_is_reproducible(self):
        a = _run_with_mode("stratified")
        b = _run_with_mode("stratified")
        assert a.law_recall == b.law_recall


def _run_with_mode(mode):
    """用一个固定的假 agent 跑指定抽样模式。"""
    return run_wisdom_benchmark(
        _FixedAgent(["first_principles", "systems_thinking"]), sample=mode)


class _FixedHub:
    def activate(self, foci, **kw):
        return []


class _FixedAgent:
    def __init__(self, law_ids):
        self._law_ids = law_ids
        self.hub = _FixedHub()

    def decompose(self, problem):
        from soma.base import Focus
        return [Focus(law_id=lid, dimension=f"x{lid}", keywords=["t"],
                      weight=1.0, rationale="r") for lid in self._law_ids]
