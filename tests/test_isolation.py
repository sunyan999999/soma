"""v0.4.0 数据隔离测试 — 验证 user_id / namespace 正确隔离记忆"""

import pytest

from soma.memory.episodic import EpisodicStore
from soma.memory.semantic import SemanticStore
from soma.memory.skill import SkillStore


@pytest.fixture
def ep_store(tmp_path):
    s = EpisodicStore(tmp_path)
    yield s
    s.close()


@pytest.fixture
def sem_store(tmp_path):
    s = SemanticStore(tmp_path)
    yield s
    s.close()


@pytest.fixture
def sk_store(tmp_path):
    s = SkillStore(tmp_path)
    yield s
    s.close()


class TestEpisodicIsolation:
    """情节记忆 user_id 隔离测试"""

    def test_different_users_cannot_see_each_other(self, ep_store):
        ep_store.add("用户A的秘密", user_id="user_a")
        ep_store.add("用户B的计划", user_id="user_b")

        a_results = ep_store.query_by_keywords(["秘密"], user_id="user_a")
        assert len(a_results) == 1
        assert "用户A" in a_results[0].content

        b_results = ep_store.query_by_keywords(["秘密"], user_id="user_b")
        assert len(b_results) == 0

    def test_same_content_different_users_not_deduped(self, ep_store):
        """同内容+不同用户应分别存储，不去重"""
        id_a = ep_store.add("相同的问题", user_id="user_a")
        id_b = ep_store.add("相同的问题", user_id="user_b")
        assert id_a != id_b
        assert ep_store.count() == 2

    def test_same_content_same_user_is_deduped(self, ep_store):
        """同内容+同用户应去重"""
        id1 = ep_store.add("重复的问题", user_id="user_a")
        id2 = ep_store.add("重复的问题", user_id="user_a")
        assert id1 == id2
        assert ep_store.count() == 1

    def test_empty_user_id_sees_all_non_isolation(self, ep_store):
        """不传 user_id 时返回全部（向后兼容）"""
        ep_store.add("记忆1", user_id="user_a")
        ep_store.add("记忆2", user_id="user_b")
        results = ep_store.query_by_keywords(["记忆"], top_k=10)
        assert len(results) == 2

    def test_like_fallback_isolation(self, ep_store):
        """LIKE 兜底路径的 user_id 隔离（关键词 < 3字）"""
        ep_store.add("凤凰项目", user_id="user_a")
        ep_store.add("凤凰涅槃", user_id="user_b")
        # "凤凰" 两个汉字 < 3字，走 LIKE 兜底
        results = ep_store.query_by_keywords(["凤凰"], user_id="user_a")
        assert len(results) == 1
        assert results[0].content == "凤凰项目"


class TestSemanticIsolation:
    """语义记忆 namespace 隔离测试"""

    def test_different_namespaces_isolated(self, sem_store):
        sem_store.add_triple("SOMA", "使用", "智慧框架", namespace="ns_a")
        sem_store.add_triple("Glaude", "使用", "Go语言", namespace="ns_b")

        a_results = sem_store.query_by_keywords(["SOMA"], namespace="ns_a")
        assert len(a_results) == 1

        b_results = sem_store.query_by_keywords(["SOMA"], namespace="ns_b")
        assert len(b_results) == 0

    def test_empty_namespace_sees_all(self, sem_store):
        sem_store.add_triple("A", "关联", "B", namespace="ns_a")
        sem_store.add_triple("C", "关联", "D", namespace="ns_b")
        results = sem_store.query_by_keywords(["关联"], top_k=10)
        assert len(results) == 2

    def test_like_fallback_namespace_isolation(self, sem_store):
        """短关键词 LIKE 路径的 namespace 隔离"""
        sem_store.add_triple("零熵智库", "采用", "SOMA", namespace="org_ls")
        sem_store.add_triple("墨甲玄枢", "采用", "SOMA", namespace="org_mj")
        # "零" 单字 < 3字，走 LIKE 兜底
        results = sem_store.query_by_keywords(["零"], namespace="org_ls")
        assert len(results) == 1
        assert "零熵智库" in results[0].content


class TestSkillIsolation:
    """技能记忆 user_id 隔离测试"""

    def test_different_users_skills_isolated(self, sk_store):
        sk_store.add_skill("用户A技能", "pattern_a", user_id="user_a")
        sk_store.add_skill("用户B技能", "pattern_b", user_id="user_b")

        a_results = sk_store.query_by_keywords(["用户A技能"], user_id="user_a")
        assert len(a_results) == 1

        b_results = sk_store.query_by_keywords(["用户A技能"], user_id="user_b")
        assert len(b_results) == 0

    def test_like_fallback_skill_isolation(self, sk_store):
        """短关键词 LIKE 路径的 user_id 隔离"""
        sk_store.add_skill("三体问题", "分析模式", user_id="user_1")
        sk_store.add_skill("三体运动", "模拟模式", user_id="user_2")
        # "三体" 两个汉字 < 3字 → LIKE
        results = sk_store.query_by_keywords(["三体"], user_id="user_1")
        assert len(results) == 1
        assert results[0].content == "技能: 三体问题 — 分析模式"
