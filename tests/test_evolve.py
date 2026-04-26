import pytest
from pathlib import Path
from soma.evolve import MetaEvolver


class FakeEngine:
    """简易 Engine 替身"""
    def __init__(self):
        self.laws = []


@pytest.fixture
def evolver(tmp_path: Path):
    return MetaEvolver(FakeEngine(), persist_dir=tmp_path)


class TestMetaEvolver:
    def test_reflect_logs(self, evolver):
        evolver.reflect("task_1", "success")
        evolver.reflect("task_2", "failure")

        log = evolver.get_log()
        assert len(log) == 2
        # get_log() 返回最新在前, log[0] 是 task_2
        assert log[0]["task_id"] == "task_2"
        assert log[0]["outcome"] == "failure"
        assert log[1]["task_id"] == "task_1"
        assert log[1]["outcome"] == "success"
        assert "timestamp" in log[0]

    def test_initial_log_empty(self, evolver):
        assert len(evolver.get_log()) == 0

    def test_clear_log(self, evolver):
        evolver.reflect("t1", "ok")
        evolver.clear_log()
        assert len(evolver.get_log()) == 0
