"""v2.0.34: run_multi_benchmark 的预热阶段 —— 计分前消掉冷启动。

下游实测（2.0.33，benchmark_runs id=187）：首轮 avg_activate 910ms → wisdom 71.8，
后三轮 210ms → 77.6。**5.8 分的极差全部来自首轮**，而首轮慢的原因是三笔进程级的
一次性成本，不是数据规模。

这里的判据盯的是「预热真的在计分前跑了、且绝不污染分数」，不测真实耗时
（那需要 ONNX，慢且不稳）。
"""
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pytest

from soma import benchmarks
from soma.benchmarks import (
    BenchmarkRun,
    EvolutionBenchmark,
    MemoryBenchmark,
    ScalabilityBenchmark,
    WisdomBenchmark,
    _warmup_process_caches,
    run_multi_benchmark,
)


# ── 测试替身 ──────────────────────────────────────────────────

@dataclass
class FakeEmbedder:
    """只记录 warmup 被同步调用了没有。"""
    is_loaded: bool = False
    warmup_calls: int = 0
    encode_calls: List[str] = field(default_factory=list)

    def warmup(self) -> bool:
        self.warmup_calls += 1
        self.is_loaded = True
        return True

    def encode(self, text: str):
        self.encode_calls.append(text)
        return [0.0]


class FakeAgent:
    """记录预热走过的路径，不碰真模型、不碰真库。"""

    def __init__(self, log: List, embedder: Optional[FakeEmbedder] = None):
        self.log = log
        self.embedder = embedder
        self.closed = False
        self.hub = self  # 预热用 agent.hub.activate，这里让 agent 自己当 hub

    def decompose(self, problem: str):
        self.log.append(("decompose", problem))
        return [f"focus:{problem}"]

    def activate(self, foci):
        self.log.append(("activate", tuple(foci)))
        return []

    def close(self):
        self.closed = True


def _fake_run_full_benchmark(agent, ablation_data=None, version=""):
    """替换真实四维评测：本文件只测调度逻辑，不测分数怎么算。"""
    return BenchmarkRun(
        version=version,
        timestamp=time.time(),
        memory=MemoryBenchmark(),
        wisdom=WisdomBenchmark(),
        evolution=EvolutionBenchmark(),
        scalability=ScalabilityBenchmark(),
        scores={"overall": 90.0, "wisdom": 77.0},
        data_scale="small",
    )


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    """默认把网络/磁盘依赖都换掉：固定 3 道题 + 假的完整评测。"""
    monkeypatch.setattr(
        benchmarks, "_load_test_dataset",
        lambda: [{"problem": f"问题{i}"} for i in range(5)],
    )
    monkeypatch.setattr(benchmarks, "run_full_benchmark", _fake_run_full_benchmark)


# ── 判据 ──────────────────────────────────────────────────────

def test_warmup_runs_before_scoring_and_is_not_counted():
    """预热真的建了一个 agent 并跑了题，但结果里的轮数只统计正式轮。"""
    made = []

    def factory():
        agent = FakeAgent(log=[], embedder=FakeEmbedder())
        made.append(agent)
        return agent

    result = run_multi_benchmark(factory, runs=2, version="9.9.9")

    # 3 个 agent = 1 个预热 + 2 个正式轮
    assert len(made) == 3
    assert result.runs == 2
    assert result.warmup_performed is True
    assert result.warmup_s >= 0.0

    # 预热 agent 确实走了 decompose + activate
    warm_agent = made[0]
    verbs = [entry[0] for entry in warm_agent.log]
    assert "decompose" in verbs
    assert "activate" in verbs
    # 预热 agent 用完必须关掉，否则数据库句柄会累积
    assert warm_agent.closed is True


def test_warmup_disabled_makes_no_extra_agent():
    made = []

    def factory():
        agent = FakeAgent(log=[], embedder=FakeEmbedder())
        made.append(agent)
        return agent

    result = run_multi_benchmark(factory, runs=2, version="9.9.9", warmup=False)

    assert len(made) == 2  # 没有预热 agent
    assert result.warmup_performed is False
    assert result.warmup_s == 0.0


def test_warmup_failure_does_not_break_the_run():
    """预热炸了必须降级继续 —— 它不属于评测本身。"""
    calls = {"n": 0}

    def factory():
        calls["n"] += 1
        if calls["n"] == 1:  # 第一个（预热用的）agent 构造失败
            raise RuntimeError("模拟模型加载失败")
        return FakeAgent(log=[], embedder=FakeEmbedder())

    result = run_multi_benchmark(factory, runs=2, version="9.9.9")

    assert result.runs == 2          # 两轮正式评测照常完成
    assert result.warmup_performed is False
    assert result.scores["wisdom"].mean == 77.0


def test_warmup_question_count_is_respected():
    log: List = []
    agent = FakeAgent(log=log, embedder=FakeEmbedder())

    _warmup_process_caches(agent, questions=1)

    decomposes = [e for e in log if e[0] == "decompose"]
    assert len(decomposes) == 1


def test_warmup_synchronously_loads_embedder():
    """构造时只在后台线程里起加载 —— 预热必须等它真的就位。"""
    emb = FakeEmbedder(is_loaded=False)
    agent = FakeAgent(log=[], embedder=emb)

    _warmup_process_caches(agent, questions=1)

    assert emb.warmup_calls == 1
    assert emb.is_loaded is True


def test_warmup_skips_already_loaded_embedder():
    """共享单例已经加载好时不该再跑一遍（那是白等）。"""
    emb = FakeEmbedder(is_loaded=True)
    agent = FakeAgent(log=[], embedder=emb)

    _warmup_process_caches(agent, questions=1)

    assert emb.warmup_calls == 0


def test_warmup_falls_back_to_encode_without_dataset(monkeypatch):
    """数据集缺失时至少把模型和分词走一遍。"""
    monkeypatch.setattr(benchmarks, "_load_test_dataset", lambda: [])
    emb = FakeEmbedder(is_loaded=True)
    agent = FakeAgent(log=[], embedder=emb)

    _warmup_process_caches(agent, questions=0)

    assert len(emb.encode_calls) == 1


def test_warmup_info_reaches_both_reports():
    """预热状态要能被读报告的人看到，不能只在返回值里。"""
    def factory():
        return FakeAgent(log=[], embedder=FakeEmbedder())

    result = run_multi_benchmark(factory, runs=1, version="9.9.9")

    md = benchmarks.generate_markdown_report(result)
    js = benchmarks.generate_json_report(result)

    assert "预热" in md
    assert js["warmup_performed"] is True
    assert js["warmup_s"] >= 0.0
