import pytest

from soma.evolve import MetaEvolver


class FakeEngine:
    """简易 Engine 替身"""
    def __init__(self):
        self.laws = []


@pytest.fixture
def evolver():
    return MetaEvolver(FakeEngine())


class TestMetaEvolver:
    def test_reflect_logs(self, evolver):
        evolver.reflect("task_1", "success")
        evolver.reflect("task_2", "failure")

        log = evolver.get_log()
        assert len(log) == 2
        assert log[0]["task_id"] == "task_1"
        assert log[0]["outcome"] == "success"
        assert "timestamp" in log[0]

    def test_initial_log_empty(self, evolver):
        assert len(evolver.get_log()) == 0

    def test_clear_log(self, evolver):
        evolver.reflect("t1", "ok")
        evolver.clear_log()
        assert len(evolver.get_log()) == 0
