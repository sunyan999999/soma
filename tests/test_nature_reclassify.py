"""nature 批量重分类 + 实例索引重载测试（v2.0.15）

背景（DSH 协作反馈，2026-08-29）：接入方需要把存量记忆按业务性质回填
state/fact/event，当时只能裸 SQL UPDATE，且改完库后长驻实例的向量索引不刷新。

覆盖：
- NatureClassifier 规则：状态词 / 事实词 / 长文档 / 知识来源 / 状态词优先
- reclassify_nature：dry_run 不改库、落盘生效、自动备份、only_nature 保护
- rollback_nature：按备份还原
- EpisodicStore.reload_index：外部进程写入后，本实例语义检索可见
"""
import json
from pathlib import Path

import numpy as np
import pytest

from soma.memory.episodic import EpisodicStore
from soma.nature import (
    NATURE_EVENT,
    NATURE_FACT,
    NATURE_STATE,
    NatureClassifier,
    reclassify_nature,
    rollback_nature,
)
from tests.test_conflict import MockEmbedder


@pytest.fixture
def store(tmp_path):
    s = EpisodicStore(tmp_path, embedder=MockEmbedder(128), use_vector_search=True)
    yield s
    s.close()


def _add(store, content, nature="event", user_id="", context=None):
    return store.add(content, context or {}, importance=0.6,
                     user_id=user_id, nature=nature)


def _nature_of(store, mem_id):
    row = store._conn.execute(
        "SELECT nature FROM episodic_memories WHERE id=?", (mem_id,)).fetchone()
    return row["nature"]


class TestNatureClassifier:
    def test_state_keyword(self):
        """健康/情绪类状态词 → state"""
        clf = NatureClassifier()
        assert clf.classify("用户最近睡眠不好，经常失眠") == NATURE_STATE
        assert clf.classify("用户这两天焦虑，压力大") == NATURE_STATE
        assert clf.classify("用户感冒发烧了") == NATURE_STATE

    def test_fact_keyword(self):
        """技能/偏好类 → fact"""
        clf = NatureClassifier()
        assert clf.classify("用户会写 Python，擅长后端开发") == NATURE_FACT
        assert clf.classify("用户偏好简洁的接口设计") == NATURE_FACT

    def test_long_doc_is_fact(self):
        """超长文档视为知识 → fact"""
        clf = NatureClassifier(fact_min_len=50)
        assert clf.classify("设计要点。" * 20) == NATURE_FACT

    def test_source_is_fact(self):
        """wiki/知识来源 → fact"""
        clf = NatureClassifier()
        assert clf.classify("某个术语的解释", {"source": "wiki"}) == NATURE_FACT
        assert clf.classify("导入的文档片段", {"origin": "knowledge_base"}) == NATURE_FACT

    def test_state_beats_fact(self):
        """状态词优先于事实词（时效性才是最要紧的属性）"""
        clf = NatureClassifier()
        # 同时含「擅长」(fact 词) 与「失眠」(state 词)
        assert clf.classify("用户擅长熬夜，最近失眠严重") == NATURE_STATE

    def test_default_event(self):
        clf = NatureClassifier()
        assert clf.classify("用户昨天参加了产品评审会") == NATURE_EVENT

    def test_custom_rules(self):
        """规则可完全自定义"""
        clf = NatureClassifier(state_keywords=("心情不错",), fact_keywords=())
        assert clf.classify("今天心情不错") == NATURE_STATE
        assert clf.classify("今天很累") == NATURE_EVENT


class TestReclassify:
    def test_dry_run_does_not_change(self, store):
        """dry_run 只统计不改库"""
        mid = _add(store, "用户最近失眠严重")
        out = reclassify_nature(store, dry_run=True)
        assert out["dry_run"] is True
        assert out["changed"] == 1
        assert out["by_nature"][NATURE_STATE] == 1
        assert "samples" in out
        assert _nature_of(store, mid) == "event", "dry_run 不应改动库"
        assert out["backup_path"] is None

    def test_apply_changes_and_backs_up(self, store):
        """落盘生效 + 自动生成备份文件"""
        mid_state = _add(store, "用户最近失眠严重")
        mid_fact = _add(store, "用户会写 Python")
        mid_evt = _add(store, "用户昨天开会")

        out = reclassify_nature(store, dry_run=False)
        assert out["dry_run"] is False
        assert out["scanned"] == 3
        assert out["changed"] == 2
        assert out["backup_path"] and Path(out["backup_path"]).exists()

        assert _nature_of(store, mid_state) == NATURE_STATE
        assert _nature_of(store, mid_fact) == NATURE_FACT
        assert _nature_of(store, mid_evt) == "event"

        backup = json.loads(Path(out["backup_path"]).read_text(encoding="utf-8"))
        assert len(backup["changes"]) == 2

    def test_only_nature_protects_classified(self, store):
        """默认只重分类 event，不覆盖已分类的记忆"""
        mid_state = _add(store, "用户最近失眠", nature=NATURE_STATE)
        mid_evt = _add(store, "用户会写 Python")   # 应为 fact，当前是 event

        out = reclassify_nature(store, dry_run=False)
        assert out["scanned"] == 1, "只应扫描 event 的记忆"
        assert _nature_of(store, mid_state) == NATURE_STATE, "已分类的不该被动"
        assert _nature_of(store, mid_evt) == NATURE_FACT

    def test_user_id_filter(self, store):
        """user_id 过滤只处理目标用户"""
        _add(store, "用户最近失眠", user_id="u1")
        _add(store, "用户会写 Python", user_id="u2")
        out = reclassify_nature(store, dry_run=True, user_id="u1")
        assert out["scanned"] == 1

    def test_limit(self, store):
        _add(store, "用户最近失眠")
        _add(store, "用户会写 Python")
        out = reclassify_nature(store, dry_run=True, limit=1)
        assert out["scanned"] == 1

    def test_rollback_restores(self, store):
        """回滚把 nature 还原到备份时的值"""
        mid = _add(store, "用户最近失眠严重")
        out = reclassify_nature(store, dry_run=False)
        assert _nature_of(store, mid) == NATURE_STATE

        rb = rollback_nature(store, out["backup_path"])
        assert rb["restored"] == 1
        assert _nature_of(store, mid) == "event", "回滚后应还原为 event"

    def test_empty_store_noop(self, store):
        out = reclassify_nature(store, dry_run=False)
        assert out["scanned"] == 0
        assert out["changed"] == 0


class TestReloadIndex:
    def test_external_add_visible_after_reload(self, tmp_path):
        """外部进程新增记忆后，reload_index 立即可见（不必等下次搜索自愈）"""
        emb = MockEmbedder(128)
        s1 = EpisodicStore(tmp_path, embedder=emb, use_vector_search=True)
        s1.add("内部写入的关于算法复杂度的记忆", {}, 0.6)
        s1.query_by_vector(emb.encode("算法"), top_k=5)   # 先建好内存索引
        before = s1._vector_index._faiss_index.ntotal

        # 模拟另一个进程（独立连接）写入
        s2 = EpisodicStore(tmp_path, embedder=emb, use_vector_search=True)
        s2.add("外部进程写入的关于数据库索引的记忆", {}, 0.6)
        s2.close()

        n = s1.reload_index()
        assert n >= 2, f"重载应读到两条向量，实际 {n}"
        assert s1._vector_index._faiss_index.ntotal > before, \
            "重载后索引应包含外部写入的向量"

        hits = s1.query_by_vector(emb.encode("数据库索引"), top_k=5)
        assert any("数据库索引" in h.content for h in hits), \
            f"应能召回外部写入的记忆: {[h.content[:15] for h in hits]}"
        s1.close()

    def test_reload_catches_same_count_swap(self, tmp_path):
        """外部删一条加一条（总数不变）时计数自愈会漏 —— reload 兜住。

        similarity_search 的一致性检查只在 current_count != cached_count 时重建；
        外部「删 N 条 + 加 N 条」总数不变，索引里留着已删向量、缺新向量。
        """
        emb = MockEmbedder(128)
        s1 = EpisodicStore(tmp_path, embedder=emb, use_vector_search=True)
        old_id = s1.add("旧的关于算法复杂度的记忆内容", {}, 0.6)
        s1.query_by_vector(emb.encode("算法"), top_k=5)

        # 外部：删一条 + 加一条，总数不变
        s2 = EpisodicStore(tmp_path, embedder=emb, use_vector_search=True)
        s2.delete(old_id)
        s2.add("新的关于数据库分库分表的记忆内容", {}, 0.6)
        s2.close()

        s1.reload_index()
        hits = s1.query_by_vector(emb.encode("数据库分库分表"), top_k=5)
        assert any("数据库分库分表" in h.content for h in hits), \
            f"reload 后应能召回外部新写入的记忆: {[h.content[:15] for h in hits]}"
        s1.close()

    def test_reload_noop_without_vector(self, tmp_path):
        """未启用向量检索时 reload 返回 0，不抛错"""
        s = EpisodicStore(tmp_path, embedder=None, use_vector_search=False)
        assert s.reload_index() == 0
        s.close()
