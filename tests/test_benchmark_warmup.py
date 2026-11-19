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


class _FakeEpisodic:
    def __init__(self):
        self.deleted: List[str] = []

    def delete(self, mid: str) -> bool:
        self.deleted.append(mid)
        return True


class _FakeMemory:
    def __init__(self):
        self.episodic = _FakeEpisodic()


class FakeFocus:
    """只有 dimension —— 预热真正 encode 的就是这个字段。"""

    def __init__(self, problem: str):
        self.law_id = "law"
        self.dimension = f"dimension:{problem}"


class FakeAgent:
    """记录预热走过的路径，不碰真模型、不碰真库。"""

    def __init__(self, log: List, embedder: Optional[FakeEmbedder] = None):
        self.log = log
        self.embedder = embedder
        self.closed = False
        self.hub = self  # 预热用 agent.hub.activate，这里让 agent 自己当 hub
        self.memory = _FakeMemory()
        self._n = 0

    def decompose(self, problem: str):
        self.log.append(("decompose", problem))
        return [FakeFocus(problem)]

    def activate(self, foci, user_id: str = ""):
        self.log.append(("activate", tuple(foci)))
        return []

    def remember(self, content, context=None, importance=0.5, user_id="", **kw):
        self._n += 1
        return f"warm_{self._n}"

    def query_memory(self, q, top_k=5, user_id="", **kw):
        return []

    def close(self):
        self.closed = True


def _fake_run_full_benchmark(agent, ablation_data=None, version="",
                             user_id="", eval_path=None):
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
    # v2.0.35：默认**不**关闭 —— 下游的 factory 常返回进程级共享实例，
    # 关掉会连带关掉共享 SQLite 连接，下一轮直接崩。
    # 需要关闭时显式传 dispose_agents=True（见 test_benchmark_eval_path.py）。
    assert warm_agent.closed is False


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


def test_warmup_activate_count_is_respected():
    """`questions` 控制真跑 activate 的题数；拆解数由 warmup_dataset_size 决定。"""
    log: List = []
    agent = FakeAgent(log=log, embedder=FakeEmbedder())

    _warmup_process_caches(agent, questions=1, warmup_dataset_size=5)

    activates = [e for e in log if e[0] == "activate"]
    decomposes = [e for e in log if e[0] == "decompose"]
    assert len(activates) == 1, f"activate 跑了 {len(activates)} 题"
    assert len(decomposes) == 5, f"decompose 跑了 {len(decomposes)} 题"


def test_all_dimensions_are_encoded():
    """★ 预热必须把数据集拆解出的**全部** dimension 文本编码一遍。

    下游实测：15 题产生 70 条唯一 dimension，逐条首次编码 10.7ms；
    预热只拆 3 题时，剩下 67 条全落在首轮计分里（164ms/次）。
    """
    agent = FakeAgent(log=[], embedder=FakeEmbedder(is_loaded=True))

    _warmup_process_caches(agent, questions=1, warmup_dataset_size=5)

    # fixture 的数据集 5 题，每题 1 条 dimension
    assert len(agent.embedder.encode_calls) == 5, (
        f"只编码了 {len(agent.embedder.encode_calls)} 条 dimension，"
        f"应为 5 条")

def test_dimension_encode_deduplicates(monkeypatch):
    """同一题重复出现时，dimension 只编码一次。"""
    monkeypatch.setattr(
        benchmarks, "_load_test_dataset",
        lambda: [{"problem": "同一个问题"} for _ in range(5)],
    )
    agent = FakeAgent(log=[], embedder=FakeEmbedder(is_loaded=True))

    _warmup_process_caches(agent, questions=1, warmup_dataset_size=5)

    assert len(agent.embedder.encode_calls) == 1, (
        f"去重失效，编码了 {len(agent.embedder.encode_calls)} 次")


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
