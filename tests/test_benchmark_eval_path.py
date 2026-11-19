"""v2.0.35: 评估路径（eval_path）+ 预热不再打死共享实例。

## 背景

下游生产实测：同一份库、同一版本，两条路径的 wisdom 差 14 分。

    基准路径（不传 user_id，历史面板口径）  wisdom 82.8
    生产路径（user_id=1，用户真实走的）      wisdom 68.9

原因是基准路径不过滤命名空间，会把 `wiki_graph` 的 1.5 万条图边一起搜出来，
把带标签的记忆挤出 top_k，`mem_precision_applicable` 变 false，12 分被按比例
分给其余项 —— 分数虚高。

另外他们第一次跑就崩了：`run_multi_benchmark` 的预热阶段 `close(warm_agent)`，
而他们的 factory 返回**进程级共享实例** → 共享 SQLite 连接被关 →
`sqlite3.ProgrammingError: Cannot operate on a closed database`。
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from soma import benchmarks
from soma.benchmarks import (
    BenchmarkRun,
    EvolutionBenchmark,
    MemoryBenchmark,
    ScalabilityBenchmark,
    WisdomBenchmark,
    run_full_benchmark,
    run_multi_benchmark,
)


# ── 替身 ──────────────────────────────────────────────────────

@dataclass
class FakeEmbedder:
    is_loaded: bool = True
    warmup_calls: int = 0
    encode_calls: List[str] = field(default_factory=list)

    def warmup(self) -> bool:
        self.warmup_calls += 1
        self.is_loaded = True
        return True

    def encode(self, text: str):
        self.encode_calls.append(text)
        return [0.0]


class FakeEpisodic:
    def __init__(self):
        self.deleted: List[str] = []

    def delete(self, mid: str) -> bool:
        self.deleted.append(mid)
        return True


class FakeMemory:
    def __init__(self):
        self.episodic = FakeEpisodic()


class FakeAgent:
    """记录 close / 写入 / 查询，不碰真库。"""

    def __init__(self):
        self.log: List[tuple] = []
        self.closed = False
        self.embedder = FakeEmbedder()
        self.hub = self
        self.memory = FakeMemory()
        self._next_id = 0

    def decompose(self, problem: str):
        self.log.append(("decompose", problem))
        return [f"focus:{problem}"]

    def activate(self, foci, user_id: str = ""):
        self.log.append(("activate", tuple(foci), user_id))
        return []

    def remember(self, content, context=None, importance=0.5, user_id="", **kw):
        self._next_id += 1
        mid = f"warm_mem_{self._next_id}"
        self.log.append(("remember", mid, user_id))
        return mid

    def query_memory(self, q, top_k=5, user_id="", **kw):
        self.log.append(("query_memory", q, user_id))
        return []

    def close(self):
        self.closed = True


def _fake_run(agent, ablation_data=None, version="", user_id="", eval_path=None):
    return BenchmarkRun(
        version=version, timestamp=0.0,
        memory=MemoryBenchmark(), wisdom=WisdomBenchmark(),
        evolution=EvolutionBenchmark(), scalability=ScalabilityBenchmark(),
        scores={"overall": 90.0, "wisdom": 77.0},
        eval_path=eval_path or ("per_user" if user_id else "namespaceless"),
    )


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    monkeypatch.setattr(
        benchmarks, "_load_test_dataset",
        lambda: [{"problem": f"问题{i}"} for i in range(5)],
    )


# ── eval_path ─────────────────────────────────────────────────

class TestEvalPath:
    def test_per_user_when_user_id_given(self, monkeypatch):
        monkeypatch.setattr(benchmarks, "run_memory_benchmark", lambda a: MemoryBenchmark())
        monkeypatch.setattr(benchmarks, "run_evolution_benchmark", lambda a: EvolutionBenchmark())
        monkeypatch.setattr(benchmarks, "run_scalability_benchmark", lambda a: ScalabilityBenchmark())
        captured = {}

        def fake_wisdom(agent, ablation_data=None, sample="first15", user_id=""):
            captured["user_id"] = user_id
            return WisdomBenchmark()

        monkeypatch.setattr(benchmarks, "run_wisdom_benchmark", fake_wisdom)

        run = run_full_benchmark(FakeAgent(), user_id="u1")

        assert run.eval_path == "per_user"
        assert captured["user_id"] == "u1", "user_id 没有透传到 wisdom"

    def test_namespaceless_when_user_id_empty(self, monkeypatch):
        monkeypatch.setattr(benchmarks, "run_memory_benchmark", lambda a: MemoryBenchmark())
        monkeypatch.setattr(benchmarks, "run_evolution_benchmark", lambda a: EvolutionBenchmark())
        monkeypatch.setattr(benchmarks, "run_scalability_benchmark", lambda a: ScalabilityBenchmark())
        monkeypatch.setattr(
            benchmarks, "run_wisdom_benchmark",
            lambda agent, ablation_data=None, sample="first15", user_id="": WisdomBenchmark(),
        )

        run = run_full_benchmark(FakeAgent())

        assert run.eval_path == "namespaceless"

    def test_eval_path_reaches_reports(self, monkeypatch):
        monkeypatch.setattr(benchmarks, "run_full_benchmark", _fake_run)

        def factory():
            return FakeAgent()

        result = run_multi_benchmark(factory, runs=1, version="9.9.9", user_id="u1")

        assert result.eval_path == "per_user"
        assert benchmarks.generate_json_report(result)["eval_path"] == "per_user"
        assert "per_user" in benchmarks.generate_markdown_report(result)


# ── dispose_agents ────────────────────────────────────────────

class TestDisposeAgents:
    def test_shared_instance_is_not_closed_by_default(self, monkeypatch):
        """★ 默认不 close —— 下游返回共享实例时，关了就是崩。"""
        monkeypatch.setattr(benchmarks, "run_full_benchmark", _fake_run)
        shared = FakeAgent()

        def factory():
            return shared  # 同一个实例，模拟进程级共享 SOMA

        result = run_multi_benchmark(factory, runs=3, version="9.9.9")

        assert shared.closed is False, (
            "默认把共享实例关掉了 —— 下一轮会 ProgrammingError")
        assert result.runs == 3  # 三轮都跑完了，没有因为关连接而中断

    def test_dispose_agents_closes_each(self, monkeypatch):
        monkeypatch.setattr(benchmarks, "run_full_benchmark", _fake_run)
        made: List[FakeAgent] = []

        def factory():
            a = FakeAgent()
            made.append(a)
            return a

        run_multi_benchmark(factory, runs=2, version="9.9.9", dispose_agents=True)

        # 1 个预热 + 2 个正式轮，全部应被关闭
        assert len(made) == 3
        assert all(a.closed for a in made), "dispose_agents=True 时有实例没关"


# ── 预热覆盖 memory 路径 ──────────────────────────────────────

class TestWarmupMemoryPath:
    def test_warmup_writes_queries_and_cleans(self):
        """预热要把「第一次写入」的成本付掉，且不留数据。"""
        agent = FakeAgent()

        benchmarks._warmup_process_caches(agent, questions=1, user_id="u1")

        writes = [e for e in agent.log if e[0] == "remember"]
        queries = [e for e in agent.log if e[0] == "query_memory"]
        activates = [e for e in agent.log if e[0] == "activate"]

        assert len(writes) == 3, f"预热应写 3 条，实际 {len(writes)}"
        assert len(queries) == 1, "预热应查 1 次"
        assert activates, "预热应跑 activate"
        # 写入和查询都要带 user_id，否则预热的是另一条路径
        assert all(e[2] == "u1" for e in writes)
        assert all(e[2] == "u1" for e in queries)
        assert all(e[2] == "u1" for e in activates)

        # 写进去的必须删干净
        assert len(agent.memory.episodic.deleted) == 3

    def test_memory_sample_can_be_disabled(self):
        agent = FakeAgent()

        benchmarks._warmup_process_caches(agent, questions=1, memory_sample=False)

        assert not [e for e in agent.log if e[0] == "remember"]
        assert all(e[2] == "" for e in agent.log if e[0] == "activate")
