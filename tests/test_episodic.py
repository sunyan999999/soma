import pytest

from soma.memory.episodic import EpisodicStore


@pytest.fixture
def store(tmp_path):
    s = EpisodicStore(tmp_path)
    yield s
    s.close()


class TestEpisodicStore:
    def test_add_and_get(self, store):
        mid = store.add("测试记忆内容", {"domain": "测试"})
        mem = store.get(mid)
        assert mem is not None
        assert mem.content == "测试记忆内容"
        assert mem.context == {"domain": "测试"}
        assert mem.memory_type == "episodic"

    def test_count(self, store):
        assert store.count() == 0
        store.add("记忆1")
        store.add("记忆2")
        assert store.count() == 2

    def test_delete(self, store):
        mid = store.add("待删除的记忆")
        assert store.count() == 1
        assert store.delete(mid) is True
        assert store.count() == 0
        assert store.get(mid) is None
        assert store.delete("nonexistent") is False

    def test_query_by_keywords(self, store):
        store.add("关于第一性原理的深度思考", {"domain": "哲学"})
        store.add("系统思维在企业管理的应用", {"domain": "管理"})
        store.add("完全不相关的内容", {"domain": "其他"})

        results = store.query_by_keywords(["第一性"], top_k=5)
        assert len(results) == 1
        assert "第一性原理" in results[0].content

        results = store.query_by_keywords(["系统"], top_k=5)
        assert len(results) == 1
        assert "系统思维" in results[0].content

        results = store.query_by_keywords(["思维"], top_k=5)
        assert len(results) == 1  # 只有 "系统思维..."

    def test_query_by_context(self, store):
        store.add("内容A", {"domain": "营销"})
        store.add("内容B", {"domain": "管理"})

        results = store.query_by_keywords(["营销"], top_k=5)
        assert len(results) == 1
        assert results[0].content == "内容A"

    def test_query_empty_keywords(self, store):
        store.add("一些内容")
        results = store.query_by_keywords([], top_k=5)
        assert len(results) == 0

    def test_persistence(self, tmp_path):
        """跨实例持久化测试"""
        s1 = EpisodicStore(tmp_path)
        mid = s1.add("持久化内容", {"test": True})
        s1.close()

        s2 = EpisodicStore(tmp_path)
        mem = s2.get(mid)
        assert mem is not None
        assert mem.content == "持久化内容"
        assert mem.context == {"test": True}
        s2.close()

    def test_top_k_limit(self, store):
        for i in range(10):
            store.add(f"相关记忆 {i}")
        results = store.query_by_keywords(["记忆"], top_k=3)
        assert len(results) == 3

    def test_importance_default(self, store):
        mid = store.add("测试")
        mem = store.get(mid)
        assert mem.importance == 0.5
