import pytest

from soma.memory.skill import SkillStore


@pytest.fixture
def store():
    s = SkillStore()
    s.add_skill("逆向决策", "遇到困境时，先假设目标已失败，反推可能原因", {"domain": "决策"})
    s.add_skill("系统映射", "将问题映射为要素-连接-目的的拓扑图", {"domain": "分析"})
    return s


class TestSkillStore:
    def test_add_and_count(self, store):
        assert store.count() == 2

    def test_query_by_keywords(self, store):
        results = store.query_by_keywords(["决策"])
        assert len(results) >= 1
        assert any("逆向决策" in r.content for r in results)

    def test_query_by_keywords_no_match(self, store):
        results = store.query_by_keywords(["不存在"])
        assert len(results) == 0

    def test_skill_memory_type(self, store):
        results = store.query_by_keywords(["系统"])
        assert all(r.memory_type == "skill" for r in results)
