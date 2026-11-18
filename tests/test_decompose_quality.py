# -*- coding: utf-8 -*-
"""拆解质量：日常表达能被识别、短问题不被过度触发。

## 背景（2026-11-24）

攻 wisdom 短板时先把「漏掉 / 多触发」拉出来看：

    漏掉（FN）最多：evolutionary_lens 13、contradiction_analysis 12、
                    inversion 11、pareto_principle 8
    多触发（FP）最多：systems_thinking 29、first_principles 16、inversion 15

两类问题的根因不同：

**漏掉**：触发词覆盖的是「术语」，不是「日常表达」。
用户说「这个方案落地的**挑战**是什么」，触发词表里是「矛盾/冲突/对立」。
「这个行业为什么在**衰落**」—— 表里是「演化/趋势/阶段」。
「**根本原因**」—— 表里是「最重要/最关键/瓶颈」。

**多触发（短问题）**：语义兜底阈值 0.35 太松。用 6 类普通问题实测，
0.35 时一共触发 14 个规律 —— 「这个函数为什么报内存溢出」会匹配到
演进视角，「公司明年预算多少」也会。

## 修法与实测

1. 补日常表达词（矛盾 +挑战/阻力/障碍/张力/难点；演进 +多年/衰落/时代/
   长期；二八 +根本原因）
2. 语义兜底阈值 0.35 → **0.42**

四档实测（50 题基准 + 6 类普通问题）：

    0.35  recall 0.6319  precision 0.4919  普通问题触发 14
    0.42  recall 0.6389  precision 0.5027  普通问题触发  8   ← 选中
    0.50  recall 0.5347  precision 0.4936  普通问题触发  8
    0.58  recall 0.5278  precision 0.4872  普通问题触发  8

加上触发词后的最终值：recall 0.6667 / precision 0.5106
（命中 91→96、多余 94→92、漏 53→48）。

## 注入自证

  · 阈值改回 0.35                 → TestSemanticThreshold 红
  · 删掉日常表达词                → TestDailyExpression 红
  · recall 回退（删跨域词/改坏匹配）→ TestRegressionFloor 红
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from soma import SOMA  # noqa: E402
from soma.benchmarks import _load_test_dataset  # noqa: E402
from soma.engine import _SEMANTIC_MATCH_THRESHOLD  # noqa: E402


@pytest.fixture(scope="module")
def soma(tmp_path_factory):
    d = tmp_path_factory.mktemp("dq")
    s = SOMA(llm="mock", persist_dir=str(d),
             use_vector_search=True, warmup_on_init=True)
    yield s
    s.close()


def _ids(soma, problem):
    return [f.law_id for f in soma._agent.decompose(problem)]


class TestSemanticThreshold:
    """★ 短问题的语义兜底不能太松。"""

    def test_threshold_not_lowered(self):
        """0.42 是实测甜点，再降回去会让普通问题被过度触发。"""
        assert _SEMANTIC_MATCH_THRESHOLD >= 0.42, (
            f"语义阈值被降到 {_SEMANTIC_MATCH_THRESHOLD} —— "
            f"实测 0.35 时 6 类普通问题会触发 14 个规律")

    @pytest.mark.parametrize("problem", [
        "如何用 Python 读取 CSV 文件？",
        "如何优化数据库查询速度？",
        "公司明年的预算是多少？",
        "这个函数为什么会报内存溢出？",
        "帮我写一个排序算法",
        "服务器 CPU 占用 90% 怎么办？",
    ])
    def test_plain_question_not_over_triggered(self, soma, problem):
        """普通问题不该一次触发一大堆规律（每条 ≤3 个）。"""
        ids = _ids(soma, problem)
        assert len(ids) <= 3, f"「{problem}」触发了 {len(ids)} 个：{ids}"

    def test_plain_questions_total_bounded(self, soma):
        """★ 6 类普通问题的触发总数要有上限。

        实测：阈值 0.35 时 14 个、0.42 时 8 个。这里钉在 10，
        留一点余量但能抓住「阈值被调回去」。
        """
        plain = [
            "如何用 Python 读取 CSV 文件？", "如何优化数据库查询速度？",
            "公司明年的预算是多少？", "这个函数为什么会报内存溢出？",
            "帮我写一个排序算法", "服务器 CPU 占用 90% 怎么办？",
        ]
        total = sum(len(_ids(soma, p)) for p in plain)
        assert total <= 10, (
            f"6 类普通问题共触发 {total} 个规律（阈值 0.42 时是 8）—— "
            f"语义兜底又放宽了")

    @pytest.mark.parametrize("problem", [
        "如何用 Python 读取 CSV 文件？",
        "帮我写一个排序算法",
        "服务器 CPU 占用 90% 怎么办？",
    ])
    def test_technical_question_not_cross_domain(self, soma, problem):
        """技术问题绝不能触发「类比推理」（跨域句式词不该误伤）。"""
        assert "analogical_reasoning" not in _ids(soma, problem), (
            f"「{problem}」被误判为跨域类比")


class TestDailyExpression:
    """★ 日常表达要能映射到规律，而不是只认术语。"""

    @pytest.mark.parametrize("problem,expected", [
        ("这个方案落地时最大的挑战是什么？", "contradiction_analysis"),
        ("推行时会遇到什么阻力？", "contradiction_analysis"),
        ("实施过程中的主要障碍在哪？", "contradiction_analysis"),
        ("这个行业为什么在衰落？", "evolutionary_lens"),
        ("这个趋势能持续多久？", "evolutionary_lens"),
        ("这个问题的根本原因是什么？", "pareto_principle"),
    ])
    def test_daily_expression_triggers_law(self, soma, problem, expected):
        """用户不会说「请用矛盾分析」，他会说「有什么挑战/阻力/障碍」。"""
        ids = _ids(soma, problem)
        assert expected in ids, (
            f"「{problem}」没触发 {expected}，实际：{ids}")


class TestRegressionFloor:
    """★ 回归哨兵：拆解质量不能回退。"""

    def test_recall_and_precision_floor(self, soma):
        """全 50 题召回/精确度不能回退。

        ⚠️ 基线分两档：embedder 是**进程级单例**（v2.0.16），前序测试调用
        `release_shared_embedders()` 后本模块拿到的是未加载的实例 ——
        那种情况下语义兜底不参与，召回天然低一截（0.5694 vs 0.6667）。
        这不是能力回退，所以按环境分档而不是一刀切。

        有 embedder：recall ≥ 0.64 / precision ≥ 0.49（当前 0.6667 / 0.5106）
        无 embedder：recall ≥ 0.54（当前 0.5694）
        """
        emb = getattr(soma._agent, "embedder", None)
        emb_ready = bool(emb is not None and getattr(emb, "is_loaded", False))
        recall_floor = 0.64 if emb_ready else 0.54
        tp = fp = fn = 0
        for q in _load_test_dataset():
            actual = {f.law_id for f in soma._agent.decompose(q["problem"])
                      if not f.law_id.startswith("combo_")}
            expected = set(q.get("expected_laws", []))
            if not expected:
                continue
            tp += len(actual & expected)
            fp += len(actual - expected)
            fn += len(expected - actual)
        recall = tp / (tp + fn)
        precision = tp / (tp + fp)
        assert recall >= recall_floor, (
            f"recall 回退到 {recall:.4f}（embedder_ready={emb_ready}，"
            f"基线 {'0.6667' if emb_ready else '0.5694'}）")
        if emb_ready:
            assert precision >= 0.49, (
                f"precision 回退到 {precision:.4f}（基线 0.5106）")

    def test_cross_domain_still_works(self, soma):
        """上一轮修的跨域触发不能被这次改动破坏。"""
        from soma.benchmarks import _load_test_dataset as load
        qmap = {q["id"]: q["problem"] for q in load()}
        for qid in ("cross_03", "cross_09", "cross_10"):
            assert "analogical_reasoning" in _ids(soma, qmap[qid]), (
                f"{qid} 的跨域识别回退了")
