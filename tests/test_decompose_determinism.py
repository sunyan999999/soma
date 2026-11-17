# -*- coding: utf-8 -*-
"""拆解的确定性与跨域识别 —— 让基准可复现，让类比推理真的能被触发。

## 背景（2026-11-18）

排查「跨域题召回低」时先量了一次可复现性，结果发现**基准本身测不准**：

    同一份代码，同一个进程，连跑 10 次 15 题基准：
      recall = [0.6667, 0.5714, 0.5952, 0.6429, 0.6429,
                0.5476, 0.5952, 0.5714, 0.5476, 0.5714]
      → 极差 11.9 个百分点

后果：任何小于 ~12 个百分点的改进用单次测量都测不出来 —— 优化工作
无法被验证。根因是 `decompose()` 里有三处模块级 `random`：

    1. 阶段 1.5「探索因子」：匹配规律少时 `random.choice(unexplored)`
    2. 阶段 3 兜底：`random.choices(laws, weights=...)`
    3. 排序抖动：`random.uniform(-0.003, 0.003)`

**修法**：以问题文本的 SHA256 前 8 字节做种子，同一问题结果稳定、
不同问题仍保留探索差异。

## 另一个问题：跨域句式不触发类比推理

`analogical_reasoning` 的触发词原本是「类比/相似/借鉴/跨界/迁移…」——
全是**显式类比词**。但用户不会说「请用类比推理」，他会说：

  「围棋中的'弃子争先'策略，在产品设计中**如何应用**？」
  「语言学中'萨丕尔-沃尔夫假说'对公司内部沟通语言的设计有何**指导意义**？」

这类「A 领域的 X → B 领域」的结构没有显式类比词，实测 50 题里
`analogical_reasoning` 只触发 3 次，而预期含它的题有 10+ 道。

**修法**：补一组跨域句式词（如何应用 / 指导意义 / 应用到 / 用在 /
变通 / 有何启示 / 能用来解释）。实测全 50 题：命中 83→89、漏掉 61→55、
**多触发数不变（92）** —— 纯补漏、无副作用。

## 注入自证

  · 随机改回模块级 `random.choice`  → TestDeterminism 红
  · 删掉跨域句式触发词             → TestCrossDomainRecall 红
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from soma import SOMA  # noqa: E402
from soma.benchmarks import _load_test_dataset, run_wisdom_benchmark  # noqa: E402
from soma.engine import WisdomEngine  # noqa: E402


@pytest.fixture
def soma_instance(tmp_path):
    s = SOMA(llm="mock", persist_dir=str(tmp_path),
             use_vector_search=False, warmup_on_init=False)
    yield s
    s.close()


def _law_ids(soma, problem):
    return [f.law_id for f in soma._agent.decompose(problem)]


class TestDeterminism:
    """★ 同一个问题，结果必须可复现。"""

    def test_same_problem_same_result(self, soma_instance):
        problem = "围棋中的'弃子争先'策略，在产品设计中如何应用？"
        runs = [tuple(_law_ids(soma_instance, problem)) for _ in range(5)]
        assert len(set(runs)) == 1, (
            f"同一问题 5 次结果不一致：{set(runs)} —— 基准又测不准了")

    def test_across_instances(self, tmp_path):
        """换一个实例（等价于换一次进程）结果也要一致。"""
        problem = "军事战略中'集中优势兵力'原则，在资源有限的创业环境中如何变通应用？"
        a = SOMA(llm="mock", persist_dir=str(tmp_path / "a"),
                 use_vector_search=False, warmup_on_init=False)
        b = SOMA(llm="mock", persist_dir=str(tmp_path / "b"),
                 use_vector_search=False, warmup_on_init=False)
        try:
            assert tuple(_law_ids(a, problem)) == tuple(_law_ids(b, problem)), (
                "跨实例结果不同 —— 种子没跟问题绑定")
        finally:
            a.close()
            b.close()

    def test_no_bare_module_random(self):
        """★ 结构性判据：`decompose` 里不允许再用模块级 random。

        只测行为不够 —— 某处偶然没被触发到就漏网了。直接钉源码。
        """
        src = inspect.getsource(WisdomEngine.decompose)
        code = "\n".join(
            ln for ln in src.splitlines() if not ln.strip().startswith("#"))
        for bad in ("random.choice(", "random.choices(", "random.uniform("):
            assert bad not in code, (
                f"`decompose` 里还有模块级 `{bad}` —— 基准会不可复现")
        assert "_rng = random.Random(" in code, "没看到基于问题的确定性 RNG"

    def test_benchmark_is_reproducible(self, soma_instance):
        """★ 端到端：连跑两次基准，law_recall 必须完全一致。"""
        a = run_wisdom_benchmark(soma_instance._agent)
        b = run_wisdom_benchmark(soma_instance._agent)
        assert a.law_recall == b.law_recall, (
            f"两次基准 law_recall 不同：{a.law_recall} vs {b.law_recall}")


class TestCrossDomainRecall:
    """★ 跨域句式必须触发类比推理。"""

    CROSS_DOMAIN = {
        "cross_03": "围棋中的'弃子争先'策略，在产品设计中如何应用？",
        "cross_09": "语言学中'萨丕尔-沃尔夫假说'（语言影响思维方式）对公司内部沟通语言的设计有何指导意义？",
        "cross_10": "军事战略中'集中优势兵力'原则，在资源有限的创业环境中如何变通应用？",
    }

    def test_cross_domain_questions_trigger_analogical(self, soma_instance):
        missing = []
        for qid, problem in self.CROSS_DOMAIN.items():
            if "analogical_reasoning" not in _law_ids(soma_instance, problem):
                missing.append(qid)
        assert not missing, (
            f"这些跨域题没触发类比推理：{missing} —— "
            f"「A 领域的 X 在 B 领域如何应用」的结构识别不到")

    @pytest.mark.parametrize("problem", [
        "如何用 Python 读取 CSV 文件？",
        "这个函数为什么会报内存溢出？",
        "如何优化数据库查询速度？",
        "公司明年的预算是多少？",
    ])
    def test_plain_questions_do_not_trigger(self, soma_instance, problem):
        """★ 反向：普通技术/业务问题不该被误判成跨域类比。"""
        assert "analogical_reasoning" not in _law_ids(soma_instance, problem), (
            f"普通问题「{problem}」被误判成跨域类比 —— 触发词太宽")

    # 数据集中**确实是跨域结构**的题（A 领域的做法 → B 领域）。
    # 说明：数据集里另有 6 道也标了 `analogical_reasoning`，但标注本身牵强 ——
    #   strategy_08「行业老三的最优策略」= 竞争分析
    #   strategy_09「数据网络效应 vs 用户网络效应」= 对比分析
    #   design_03/05/07/08 = 创新设计 / 归因 / 包容性设计
    # 它们都不是「借另一个领域的结构」，硬要求触发类比推理等于为了分数
    # 把触发词放宽到失去区分力。**不作为判据**，也不改数据集标注
    # （改参考答案来让分数好看，是自欺）。
    TRUE_CROSS_DOMAIN = {
        "cross_03": "围棋的弃子争先 → 产品设计",
        "cross_09": "萨丕尔-沃尔夫假说 → 公司沟通语言设计",
        "cross_10": "集中优势兵力 → 创业资源分配",
        "experience_01": "丰田安灯绳 → 团队授权",
        "experience_07": "迪士尼表演文化 → B2B 企业",
    }

    def test_true_cross_domain_questions_covered(self, soma_instance):
        """★ 真跨域题必须全部触发类比推理。"""
        qmap = {q["id"]: q["problem"] for q in _load_test_dataset()}
        missing = [f"{qid}（{desc}）" for qid, desc in self.TRUE_CROSS_DOMAIN.items()
                   if "analogical_reasoning" not in _law_ids(soma_instance, qmap[qid])]
        assert not missing, (
            f"这些真跨域题没触发类比推理：{missing}")
