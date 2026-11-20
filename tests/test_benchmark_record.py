"""v2.0.39: 基准记录必须自解释。

## 三个可变因素，只有一个曾被完整记录

    caliber                    评分算法版本        多轮记录里没有
    eval_path                  评估路径            2.0.35 加了
    mem_precision_applicable   false 时剔除该项、  没有
                               分母权重整体放大

第三条最隐蔽：同一份库、同一版本，仅因为路径不同就 82.8 vs 68.7，
而记录里看不出是「剔除了一项」还是「真的低」。

## 注入自证

  · 记录去掉 caliber              → TestRecordFields 红
  · wisdom.items 只存均值         → TestRecordFields 红
  · applicable 压成一个 bool      → TestApplicability 红
  · 落库结构与对外结构不一致       → TestRecordMatchesStorage 红
  · eval_path 为空时静默写空串     → TestUnknownPath 红
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from soma.benchmarks import (
    BENCHMARK_RECORD_SCHEMA,
    MultiRunResult,
    RunStatistics,
    build_benchmark_record,
)


def _stats(values):
    n = len(values)
    mean = sum(values) / n if n else 0.0
    return RunStatistics(
        mean=round(mean, 4), std=0.0,
        ci95_low=mean, ci95_high=mean, cv_pct=0.0,
        min_val=min(values) if values else 0.0,
        max_val=max(values) if values else 0.0,
        values=list(values),
    )


def _result(**overrides):
    base = dict(
        version="9.9.9",
        runs=4,
        timestamp=0.0,
        scores={"overall": _stats([84.5, 84.6, 84.6, 84.5]),
                "wisdom": _stats([68.6, 68.7, 68.5, 68.6])},
        detail_scores={},
        data_scale="small",
        total_duration_s=120.0,
        warmup_performed=True,
        warmup_s=1.97,
        eval_path="per_user",
        caliber="v2-normalized",
        eval_user_id="1",
        wisdom_items={
            "relevance": _stats([0.14, 0.139, 0.139, 0.138]),
            "mem_precision": _stats([0.0568, 0.057, 0.0566, 0.0569]),
        },
        wisdom_weights={
            "relevance": _stats([0.2, 0.2, 0.2, 0.2]),
        },
        mem_precision_applicable=[True, True, True, True],
    )
    base.update(overrides)
    return MultiRunResult(**base)


class TestRecordFields:
    def test_has_caliber_and_path(self):
        rec = build_benchmark_record(_result())

        assert rec["schema"] == BENCHMARK_RECORD_SCHEMA
        assert rec["caliber"] == "v2-normalized"
        assert rec["eval_path"] == "per_user"
        assert rec["eval_user_id"] == "1"

    def test_caliber_missing_becomes_unknown(self):
        rec = build_benchmark_record(_result(caliber=""))
        assert rec["caliber"] == "unknown", (
            "caliber 缺失必须显式标 unknown，不能静默留空")

    def test_items_keep_per_run_values(self):
        """★ 只存均值就看不出「稳定在 0.139」还是「0.05~0.22 之间跳」。"""
        rec = build_benchmark_record(_result())

        rel = rec["wisdom"]["items"]["relevance"]
        assert "values" in rel and len(rel["values"]) == 4
        assert "mean" in rel
        assert rec["wisdom"]["weights"]["relevance"]["mean"] == 0.2

    def test_scores_keep_values(self):
        rec = build_benchmark_record(_result())
        assert len(rec["scores"]["wisdom"]["values"]) == 4


class TestApplicability:
    def test_flags_recorded_per_run(self):
        rec = build_benchmark_record(_result())
        assert rec["wisdom"]["mem_precision_applicable"] == [True] * 4
        assert rec["wisdom"]["unstable_applicability"] is False

    def test_inconsistent_flags_are_flagged(self):
        """★ 四轮里 true/false 混着 —— 分母变过，分数不可比。"""
        rec = build_benchmark_record(
            _result(mem_precision_applicable=[True, False, True, True]))

        assert rec["wisdom"]["unstable_applicability"] is True
        assert rec["wisdom"]["partial"] is True

    def test_empty_flags_not_flagged_unstable(self):
        rec = build_benchmark_record(_result(mem_precision_applicable=[]))
        assert rec["wisdom"]["unstable_applicability"] is False


class TestUnknownPath:
    def test_empty_path_becomes_unknown_not_empty_string(self):
        rec = build_benchmark_record(_result(eval_path=""))
        assert rec["eval_path"] == "unknown", (
            "空 eval_path 静默写空串，下游会以为『没标路径』而不是『不知道』")


class TestRecordMatchesStorage:
    def test_storage_json_equals_record(self, tmp_path):
        """★ 对外结构与落库结构必须是同一个函数生成的。

        下游踩过：scores 里不带 caliber → record 把新记录全写成 v1-legacy。
        根因就是两处各写一份。
        """
        from soma.analytics import AnalyticsStore

        result = _result()
        expected = build_benchmark_record(result)

        a = AnalyticsStore(tmp_path / "an1")
        try:
            run_id = a.record_multi_benchmark(result)
            assert run_id > 0
            rows = a._conn.execute(
                "SELECT multi_run_stats_json FROM benchmark_runs WHERE id=?",
                (run_id,)).fetchall()
            stored = json.loads(rows[0]["multi_run_stats_json"])
        finally:
            a.close()

        assert stored == expected, "落库结构与 build_benchmark_record 不一致"

    def test_storage_accepts_prebuilt_record(self, tmp_path):
        from soma.analytics import AnalyticsStore

        result = _result()
        rec = build_benchmark_record(result)
        rec["extra_marker"] = "from-caller"

        a = AnalyticsStore(tmp_path / "an2")
        try:
            run_id = a.record_multi_benchmark(result, record=rec)
            rows = a._conn.execute(
                "SELECT multi_run_stats_json FROM benchmark_runs WHERE id=?",
                (run_id,)).fetchall()
            stored = json.loads(rows[0]["multi_run_stats_json"])
        finally:
            a.close()

        assert stored["extra_marker"] == "from-caller"

    def test_legacy_top_level_keys_still_present(self):
        """2.0.34~2.0.38 的下游按这两个键读，不能丢。"""
        rec = build_benchmark_record(_result())
        assert rec["warmup_performed"] is True
        assert rec["warmup_s"] == 1.97
        assert "runs" in rec


class TestFacade:
    def test_soma_exposes_build_record(self):
        import soma
        assert hasattr(soma.SOMA, "benchmark_record")
