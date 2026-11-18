# -*- coding: utf-8 -*-
"""wisdom 的 v2-normalized 口径 —— 让分数跨环境可比。

## 背景（2026-11-24，下游三组对照实验）

同一份代码，只换库：

    生产 32,233 条（用户聊天记忆）  wisdom 64.5
    干净小库 20 条                  wisdom 72.9
    小库 + 按基准 tags 种 50 条     wisdom 91.2

差 26 分里，**42 分权重的三项结构性依赖环境**：

· `mem_precision` (12 分) —— 测的是「记忆语料是否与基准题同源」。
  真实聊天记录里没有「进化论」「组织变革」这类基准 tag，必然接近 0。
  种入带 tag 的记忆后 0.034 → 0.932。
· `cross_domain` (10 分) —— 原来是「非语义激活 / 总激活」的**占比**，
  库越大语义命中越多，占比单调下降 —— 等于惩罚规模化。
· `efficiency` (10 分) —— 200ms 硬阈值。32k 库实测 548ms → 0 分；
  优化到 344ms 仍是 0。

## 归一化

· mem_precision 交集为 0 时**不计入**，12 分权重按比例分给其他六项
· cross_domain 改成「每查询非语义激活数 / 2.0」（绝对量，不随库规模漂移）
· efficiency 预算随库规模对数增长：`100 × (1 + log10(max(N,1000)/1000))`

旧公式保留为 `wisdom_legacy`，并在 `caliber` 字段标注口径。

## 注入自证

  · efficiency 改回 200ms 硬阈值     → TestEfficiencyBudget 红
  · cross_domain 改回占比            → TestCrossDomainAbsolute 红
  · mem_precision 不适用时仍按原权重 → TestMemPrecisionApplicability 红
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from soma.benchmarks import (  # noqa: E402
    CALIBER_VERSION, _efficiency_budget_ms, _wisdom_normalized,
    calculate_scores_v2, BenchmarkRun, WisdomBenchmark,
)


def _full_wisdom(**overrides):
    """一个「各项都不错」的基准，便于隔离单项影响。

    `tag_intersections` / `tag_unions` / `cross_domain_activations` /
    `n_queries_scored` 不是 dataclass 字段 —— 它们在 `details` 里
    （`run_wisdom_benchmark` 就是这么写的），所以这里单独拣出来。
    """
    detail_keys = ("tag_intersections", "tag_unions",
                   "cross_domain_activations", "n_queries_scored")
    details = {k: overrides.pop(k) for k in list(overrides) if k in detail_keys}
    base = dict(
        decomposition_coverage=1.0, law_recall=1.0,
        thinking_diversity_entropy=1.0, memory_precision=0.5,
        memory_relevance_score=0.8, cross_domain_activation_rate=0.5,
        avg_decompose_time_ms=1.0, avg_activate_time_ms=1.0,
        details=details,
    )
    base.update(overrides)
    return WisdomBenchmark(**base)


class TestCaliberMarker:
    def test_caliber_field_present(self):
        scores = calculate_scores_v2(BenchmarkRun(wisdom=_full_wisdom()))
        assert scores["caliber"] == CALIBER_VERSION == "v2-normalized"

    def test_legacy_kept(self):
        """旧值必须保留 —— 历史数据靠它对照。"""
        scores = calculate_scores_v2(BenchmarkRun(wisdom=_full_wisdom()))
        assert "wisdom_legacy" in scores
        assert isinstance(scores["wisdom_legacy"], (int, float))

    def test_items_and_weights_exposed(self):
        scores = calculate_scores_v2(BenchmarkRun(wisdom=_full_wisdom()))
        assert set(scores["wisdom_items"]) == {
            "coverage", "law_recall", "diversity",
            "mem_precision", "relevance", "cross_domain", "efficiency"}
        assert abs(sum(scores["wisdom_weights"].values()) - 100.0) < 0.5, (
            "权重之和应为 100")


class TestMemPrecisionApplicability:
    """★ 语料不同源时，mem_precision 不该计入。"""

    def test_not_applicable_when_no_tag_hit(self):
        """tag 交集为 0（真实聊天记录）→ 该项不适用，权重分给其他六项。"""
        detail = _wisdom_normalized(
            {"decomposition_coverage": 1.0, "law_recall": 0.8,
             "thinking_diversity_entropy": 0.9, "memory_relevance_score": 0.7,
             "cross_domain_activations": 3, "n_queries_scored": 15,
             "avg_decompose_time_ms": 1, "avg_activate_time_ms": 50,
             "tag_intersections": 0, "tag_unions": 88},
            32233,
        )
        assert detail["mem_precision_applicable"] is False
        assert "mem_precision" not in detail["weights"]
        assert abs(sum(detail["weights"].values()) - 100.0) < 0.5, (
            "去掉 mem_precision 后权重要重新分配到 100")

    def test_applicable_when_tag_hit(self):
        detail = _wisdom_normalized(
            {"decomposition_coverage": 1.0, "law_recall": 0.8,
             "thinking_diversity_entropy": 0.9, "memory_relevance_score": 0.7,
             "cross_domain_activations": 3, "n_queries_scored": 15,
             "avg_decompose_time_ms": 1, "avg_activate_time_ms": 50,
             "tag_intersections": 20, "tag_unions": 25},
            32233,
        )
        assert detail["mem_precision_applicable"] is True
        assert "mem_precision" in detail["weights"]

    def test_same_capability_scores_higher_without_tag_corpus(self):
        """★ 核心目标：语料里没有基准 tag 时，不该因此少 12 分。

        两个环境只有 tag 差异，归一化后的分差应显著小于 legacy 口径的分差。
        """
        common = dict(
            decomposition_coverage=1.0, law_recall=0.8,
            thinking_diversity_entropy=0.9, memory_relevance_score=0.7,
            cross_domain_activation_rate=0.3,
            avg_decompose_time_ms=1.0, avg_activate_time_ms=50.0,
            cross_domain_activations=4, n_queries_scored=15,
        )
        # legacy 口径读的是 `memory_precision` 字段，归一化读的是 details 里的
        # tag 交并集 —— 两个都要设，否则 legacy 那边根本没差距，判据就失去意义
        scored = _full_wisdom(memory_precision=0.8, tag_intersections=20,
                              tag_unions=25, **common)
        unscored = _full_wisdom(memory_precision=0.0, tag_intersections=0,
                                tag_unions=25, **common)

        a = calculate_scores_v2(BenchmarkRun(wisdom=scored))
        b = calculate_scores_v2(BenchmarkRun(wisdom=unscored))

        legacy_gap = a["wisdom_legacy"] - b["wisdom_legacy"]
        norm_gap = a["wisdom"] - b["wisdom"]
        assert legacy_gap > 8, f"构造有问题：legacy 口径下应有明显差距，实际 {legacy_gap}"
        assert norm_gap < legacy_gap * 0.5, (
            f"归一化后差距仍有 {norm_gap:.1f}（legacy 是 {legacy_gap:.1f}）—— "
            f"语料同源性仍在影响分数")


class TestCrossDomainAbsolute:
    """★ cross_domain 要用绝对量，不能用占比。"""

    def test_rate_does_not_depend_on_total_activations(self):
        """同样 6 个非语义激活、同样 15 个查询，只是总激活数不同 → 分应相同。

        旧口径是「非语义 / 总激活」，总激活一变占比就变；新口径是绝对量。
        """
        base = {"decomposition_coverage": 1.0, "law_recall": 0.8,
                "thinking_diversity_entropy": 0.9, "memory_relevance_score": 0.7,
                "avg_decompose_time_ms": 1, "avg_activate_time_ms": 50,
                "tag_intersections": 5, "tag_unions": 10,
                "cross_domain_activations": 6, "n_queries_scored": 15}
        a = _wisdom_normalized(dict(base, cross_domain_activation_rate=0.6), 10000)
        b = _wisdom_normalized(dict(base, cross_domain_activation_rate=0.1), 10000)
        assert a["items"]["cross_domain"] == b["items"]["cross_domain"], (
            "cross_domain 仍随激活总数变化 —— 还在用占比")

    def test_more_activations_higher_score(self):
        base = {"decomposition_coverage": 1.0, "law_recall": 0.8,
                "thinking_diversity_entropy": 0.9, "memory_relevance_score": 0.7,
                "avg_decompose_time_ms": 1, "avg_activate_time_ms": 50,
                "tag_intersections": 5, "tag_unions": 10,
                "n_queries_scored": 15}
        low = _wisdom_normalized(dict(base, cross_domain_activations=3), 10000)
        high = _wisdom_normalized(dict(base, cross_domain_activations=12), 10000)
        assert high["items"]["cross_domain"] > low["items"]["cross_domain"]


class TestEfficiencyBudget:
    """★ 效率预算必须随库规模缩放。"""

    def test_budget_grows_with_corpus(self):
        small = _efficiency_budget_ms(1000)
        mid = _efficiency_budget_ms(10000)
        big = _efficiency_budget_ms(100000)
        assert small < mid < big
        assert abs(small - 100.0) < 1e-6
        assert abs(mid - 200.0) < 1e-6
        assert abs(big - 300.0) < 1e-6

    def test_same_latency_scores_differently_by_corpus(self):
        """★ 344ms 在小库是灾难，在 100k 库是可接受 —— 这才是「相对效率」。"""
        base = {"decomposition_coverage": 1.0, "law_recall": 0.8,
                "thinking_diversity_entropy": 0.9, "memory_relevance_score": 0.7,
                "cross_domain_activations": 5, "n_queries_scored": 15,
                "avg_decompose_time_ms": 4, "avg_activate_time_ms": 340,
                "tag_intersections": 5, "tag_unions": 10}
        small = _wisdom_normalized(base, 1000)
        big = _wisdom_normalized(base, 100000)
        assert big["items"]["efficiency"] > small["items"]["efficiency"], (
            "同样 344ms，大库的效率分没有更高 —— 预算没随规模缩放")

    def test_32k_corpus_optimized_latency_gets_score(self):
        """下游 2.0.30 实测激活 344ms —— 旧口径下 0 分，新口径应有分。

        32k 库的预算 = 100*(1+log10(32.2)) ≈ 251ms，2 倍即 502ms 归零。
        344ms → 1 - 344/502 ≈ 0.31。这是「优化到 344ms 却仍拿 0」的正面回应。
        """
        detail = _wisdom_normalized(
            {"decomposition_coverage": 1.0, "law_recall": 0.8,
             "thinking_diversity_entropy": 0.9, "memory_relevance_score": 0.7,
             "cross_domain_activations": 5, "n_queries_scored": 15,
             "avg_decompose_time_ms": 4, "avg_activate_time_ms": 340,
             "tag_intersections": 0, "tag_unions": 88},
            32233,
        )
        assert detail["items"]["efficiency"] > 0.2, (
            f"32k 库 344ms 的效率分只有 {detail['items']['efficiency']} —— "
            f"预算缩放没生效")

    def test_32k_corpus_548ms_still_low(self):
        """548ms 在 32k 库仍应接近 0（它确实超了 2 倍预算 502ms）。

        不为了「好看」放宽到能拿高分 —— 那会掩盖真实的性能问题。
        """
        detail = _wisdom_normalized(
            {"avg_decompose_time_ms": 4, "avg_activate_time_ms": 544,
             "decomposition_coverage": 1.0, "law_recall": 0.8,
             "thinking_diversity_entropy": 0.9, "memory_relevance_score": 0.7,
             "cross_domain_activations": 5, "n_queries_scored": 15,
             "tag_intersections": 0, "tag_unions": 88},
            32233,
        )
        assert detail["items"]["efficiency"] <= 0.05
