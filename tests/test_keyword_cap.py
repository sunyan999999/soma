# -*- coding: utf-8 -*-
"""FTS 关键词上限 —— 图谱扩展不能把查询词膨胀到几十个。

## 背景（2026-11-24，下游生产 32k 条实测）

`MemoryCore.query()` 里：

```python
graph_keywords = self._expand_via_semantic_graph(keywords)   # 默认 max_terms=8
all_keywords = list(dict.fromkeys(keywords + graph_keywords))
self.semantic.query_by_keywords(all_keywords, ...)
```

focus 自带关键词只有 4~6 个，**图谱扩展后 all_keywords 中位 21 个、最多 37 个**
（一个词能连着扩展出很多邻居）。而 `semantic.query_by_keywords` 内部是
FTS5 trigram 的 OR 查询，成本随词数近似线性：

    4 词 13.1ms / 8 词 24.2ms / 14 词 46.4ms / 18 词 61.7ms

实测 58.5ms/次 × 6 次/激活 = **351ms**，是激活耗时里最大的一块。

## 修法

两层截断，主关键词优先：
  · 图谱邻居只保留 4 个（`_GRAPH_KEYWORD_CAP`）—— 它是辅助通道
  · 传给 FTS 的列表截到 10 个（`_FTS_KEYWORD_CAP`）—— focus 自带词在前

`all_keywords` 仍保留完整列表用于 `match_rationale` 展示。

## 召回影响（实测）

造了 8 条三元组的小图谱（1 跳 3 个词 + 2 跳 5 个词）：

    max_terms=8 → ['整体性','反馈回路','矛盾分析','延迟','增强回路','对立统一','取舍','杠杆点']
    max_terms=4 → ['整体性','反馈回路','矛盾分析','延迟']

丢掉的全是 **2 跳** 邻居（权重 0.36，1 跳是 0.6）。实测召回条数 7 → 7，不变。

## 注入自证

  · `_GRAPH_KEYWORD_CAP` 去掉 → TestGraphCap 红
  · FTS 改回用 all_keywords → TestFtsCap 红
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from soma import SOMA  # noqa: E402
from soma.base import Focus  # noqa: E402
from soma.memory.core import MemoryCore  # noqa: E402


@pytest.fixture(scope="module")
def soma(tmp_path_factory):
    d = tmp_path_factory.mktemp("kwcap")
    s = SOMA(llm="mock", persist_dir=str(d),
             use_vector_search=True, warmup_on_init=True)
    sem = s._agent.memory.semantic
    for a, p, b in [
        ("系统思维", "包含", "整体性"), ("系统思维", "包含", "反馈回路"),
        ("系统思维", "关联", "矛盾分析"), ("矛盾分析", "关联", "对立统一"),
        ("矛盾分析", "关联", "取舍"), ("整体性", "关联", "杠杆点"),
        ("反馈回路", "关联", "延迟"), ("反馈回路", "关联", "增强回路"),
    ]:
        sem.add_triple(a, p, b, 0.9)
    yield s
    s.close()


class TestGraphCap:
    """★ 图谱扩展的邻居数必须封顶。"""

    def test_caps_exist_and_sane(self):
        assert MemoryCore._GRAPH_KEYWORD_CAP > 0
        assert MemoryCore._FTS_KEYWORD_CAP >= MemoryCore._GRAPH_KEYWORD_CAP

    def test_query_passes_cap(self, soma):
        """★ 关键判据：`query()` 调用图谱扩展时必须**真的传**上限。

        只测 `_expand_via_semantic_graph(max_terms=4)` 是自证循环 ——
        把调用处的 `self._GRAPH_KEYWORD_CAP` 改回 999，判据照样绿
        （第一版就是这么漏的，注入验证抓出来了）。
        """
        captured = {}
        orig = soma._agent.memory._expand_via_semantic_graph
        def spy(keywords, max_terms=8):
            captured["max_terms"] = max_terms
            return orig(keywords, max_terms=max_terms)
        soma._agent.memory._expand_via_semantic_graph = spy
        try:
            focus = Focus(law_id="t", dimension="系统思维",
                          keywords=["系统思维", "关联"], weight=1.0, rationale="r")
            soma._agent.memory.query(focus, top_k=5, user_id="u1")
        finally:
            soma._agent.memory._expand_via_semantic_graph = orig

        assert captured.get("max_terms") == MemoryCore._GRAPH_KEYWORD_CAP, (
            f"query() 传给图谱扩展的是 max_terms={captured.get('max_terms')}，"
            f"应为 {MemoryCore._GRAPH_KEYWORD_CAP} —— 膨胀又回来了")

    def test_expand_respects_cap(self, soma):
        full = soma._agent.memory._expand_via_semantic_graph(
            ["系统思维", "关联"], max_terms=8)
        capped = soma._agent.memory._expand_via_semantic_graph(
            ["系统思维", "关联"], max_terms=MemoryCore._GRAPH_KEYWORD_CAP)
        assert len(capped) <= MemoryCore._GRAPH_KEYWORD_CAP
        assert capped == full[:len(capped)], "截断没保留权重最高的那些"

    def test_one_hop_neighbours_survive(self, soma):
        """★ 1 跳邻居（权重 0.6）必须全保留 —— 丢的应该只是 2 跳的。"""
        capped = soma._agent.memory._expand_via_semantic_graph(
            ["系统思维", "关联"], max_terms=MemoryCore._GRAPH_KEYWORD_CAP)
        # 系统思维的直接邻居：整体性 / 反馈回路 / 矛盾分析
        for must in ("整体性", "反馈回路", "矛盾分析"):
            assert must in capped, (
                f"1 跳邻居「{must}」被截掉了 —— 截断粒度太粗")


class TestFtsCap:
    """★ 送进 FTS 的词数必须封顶，但主关键词优先保留。"""

    def test_fts_receives_capped_list(self, soma):
        """查询走的词表不能超过 _FTS_KEYWORD_CAP。"""
        focus = Focus(law_id="t", dimension="系统思维",
                      keywords=["系统思维", "关联", "整体性", "反馈回路",
                                "矛盾分析", "延迟", "对立统一", "取舍",
                                "杠杆点", "增强回路", "多余词1", "多余词2"],
                      weight=1.0, rationale="r")
        captured = {}

        orig = soma._agent.memory.semantic.query_by_keywords
        def spy(kws, *a, **kw):
            captured["kws"] = list(kws)
            return orig(kws, *a, **kw)
        soma._agent.memory.semantic.query_by_keywords = spy
        try:
            soma._agent.memory.query(focus, top_k=5, user_id="u1")
        finally:
            soma._agent.memory.semantic.query_by_keywords = orig

        assert "kws" in captured, "没走到 semantic.query_by_keywords"
        assert len(captured["kws"]) <= MemoryCore._FTS_KEYWORD_CAP, (
            f"FTS 收到 {len(captured['kws'])} 个词，超过上限 "
            f"{MemoryCore._FTS_KEYWORD_CAP} —— 膨胀又回来了")

    def test_focus_keywords_kept_first(self, soma):
        """★ focus 自带的词必须排在被截断列表的前面（它们更重要）。"""
        focus = Focus(law_id="t", dimension="系统思维",
                      keywords=["系统思维", "关联"] + [f"填充{i}" for i in range(20)],
                      weight=1.0, rationale="r")
        captured = {}

        orig = soma._agent.memory.semantic.query_by_keywords
        def spy(kws, *a, **kw):
            captured["kws"] = list(kws)
            return orig(kws, *a, **kw)
        soma._agent.memory.semantic.query_by_keywords = spy
        try:
            soma._agent.memory.query(focus, top_k=5, user_id="u1")
        finally:
            soma._agent.memory.semantic.query_by_keywords = orig

        assert captured["kws"][:2] == ["系统思维", "关联"], (
            f"focus 自带词没排在最前：{captured['kws'][:4]}")


class TestRelevanceClamp:
    """★ activation_score 可以 > 1，评分时必须 clamp。"""

    def test_relevance_capped_at_one(self):
        """下游两次实测出现过 1.185 和 1.0012，导致 10 分的项贡献 11.85 分。

        判据必须把**其他项也灌满**才测得出 —— 只填 relevance 的话总分
        才 11 分，去掉 clamp 也超不过 100（第一版判据就是这么假绿的）。
        """
        from soma.benchmarks import calculate_scores_v2, BenchmarkRun, WisdomBenchmark

        def full_wisdom(relevance):
            return WisdomBenchmark(
                decomposition_coverage=1.0, law_recall=1.0,
                thinking_diversity_entropy=1.0, memory_precision=1.0,
                memory_relevance_score=relevance,
                cross_domain_activation_rate=1.0,
                avg_decompose_time_ms=1.0, avg_activate_time_ms=1.0,
            )

        ok = calculate_scores_v2(BenchmarkRun(wisdom=full_wisdom(1.0)))["wisdom"]
        assert ok <= 100, f"relevance=1.0 时已经超 100：{ok}"

        for raw in (1.185, 1.0012, 5.0):
            scores = calculate_scores_v2(BenchmarkRun(wisdom=full_wisdom(raw)))
            assert scores["wisdom"] <= 100, (
                f"relevance={raw} 时 wisdom={scores['wisdom']} 超了 100 —— clamp 失效")

    def test_relevance_not_zeroed(self):
        """clamp 不能把正常值也压没了。"""
        from soma.benchmarks import calculate_scores_v2, BenchmarkRun, WisdomBenchmark
        a = calculate_scores_v2(BenchmarkRun(
            wisdom=WisdomBenchmark(memory_relevance_score=0.5)))
        b = calculate_scores_v2(BenchmarkRun(
            wisdom=WisdomBenchmark(memory_relevance_score=1.0)))
        assert b["wisdom"] > a["wisdom"]
