# -*- coding: utf-8 -*-
"""语义三元组的全局知识通道 + 短关键词 LIKE 的封顶。

## 背景（2026-11-25，下游生产实测）

**① 知识图谱对真实用户完全没生效（功能性缺口）**

```
semantic_triples 共 15,312 条，全部 namespace = ''（全局知识）
MemoryCore.query 里 sem_namespace = agent_id or user_id
生产聊天传 user_id='1' → 查 namespace='1' 返回 0 行
```

15,312 条知识等于白存，每次查询只是空转 0.3ms。

修：`query_by_keywords(include_global=True)` —— 变成
`(st.namespace = ? OR st.namespace = '')`。

⚠️ `namespace=''` 在本方法的历史语义是「**不过滤**」（返回所有用户的），
不是「只查全局」—— 所以不能靠传空串来修。

⚠️ FTS 路径和 LIKE 路径是**两段独立构造的 SQL**，第一版只改了 FTS 路径，
短词查询仍然查不到全局知识（行为不一致），已一并修。

**② 2 字中文词走 LIKE 全表扫描**

FTS5 trigram 只接受 ≥3 字；1~2 字词走 `LIKE '%kw%'`，用不上索引，
每个词都要在**每一行**上评估 —— 成本 O(词数 × 行数)。

下游 32k 库实测：4 词 55ms / 8 词 94ms / 10 词 111ms，而一次 activate
会传 8~20 个 2 字词 → `episodic.query_by_keywords` 61.4ms × 18 次
= 184ms/激活（占 53%）。

修：`max_like_keywords` 默认 3（调用方保证主关键词排前面）。
本地 2 万条实测：10 词 15.8ms → 3 词 10.3ms，命中数不变。

## 注入自证

  · `include_global` 恒为 False        → TestGlobalTriples 红
  · LIKE 不截断                        → TestLikeCap 红
  · 全局通道写成「不过滤」导致跨用户泄漏 → TestNoCrossUserLeak 红
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from soma import SOMA  # noqa: E402
from soma.base import Focus  # noqa: E402
from soma.memory.search_utils import fts5_keyword_search  # noqa: E402


@pytest.fixture
def soma(tmp_path):
    s = SOMA(llm="mock", persist_dir=str(tmp_path),
             use_vector_search=False, warmup_on_init=False)
    sem = s._agent.memory.semantic
    sem.add_triple("数字分身", "基于", "命理八字", 0.9)          # 全局（namespace=''）
    sem.add_triple("大运流年", "影响", "运势走向", 0.85)          # 全局
    sem.add_triple("用户甲的偏好", "喜欢", "早上开会", 0.8, namespace="u1")
    sem.add_triple("用户乙的偏好", "喜欢", "晚上运动", 0.8, namespace="u2")
    yield s
    s.close()


def _semantic_hits(soma, keywords, user_id):
    focus = Focus(law_id="t", dimension="测试", keywords=keywords,
                  weight=1.0, rationale="r")
    res = soma._agent.memory.query(focus, top_k=20, user_id=user_id)
    return [am.memory.content for am in res if am.source == "semantic"]


class TestGlobalTriples:
    """★ 全局知识（namespace=''）必须能被用户查询命中。"""

    def test_global_included(self, soma):
        hits = _semantic_hits(soma, ["命理八字", "运势", "偏好"], "u1")
        joined = " ".join(hits)
        assert "命理八字" in joined, (
            f"全局三元组没被纳入 —— 15312 条知识等于白存。命中：{hits}")
        assert "早上开会" in joined, "用户自己的三元组也没了？"

    def test_global_included_for_any_user(self, soma):
        for uid in ("u1", "u2", "u999"):
            hits = _semantic_hits(soma, ["命理八字", "运势", "偏好"], uid)
            assert "命理八字" in " ".join(hits), f"user={uid} 拿不到全局知识"

    def test_default_off_for_compat(self, tmp_path):
        """直接调仓库方法时默认不纳入全局 —— 保持向后兼容。"""
        s = SOMA(llm="mock", persist_dir=str(tmp_path),
                 use_vector_search=False, warmup_on_init=False)
        try:
            sem = s._agent.memory.semantic
            sem.add_triple("全局概念", "关联", "另一个概念", 0.9)
            sem.add_triple("私有概念", "关联", "别的东西", 0.9, namespace="u9")
            got = sem.query_by_keywords(["全局概念", "私有概念"], top_k=10,
                                        namespace="u9")
            contents = " ".join(m.content for m in got)
            assert "私有概念" in contents
            assert "全局概念" not in contents, (
                "默认就纳入了全局 —— 改变了既有语义，应显式 include_global=True")
        finally:
            s.close()


class TestNoCrossUserLeak:
    """★ 纳入全局不能顺带把别的用户的三元组也放进来。"""

    def test_other_user_not_visible(self, soma):
        hits = _semantic_hits(soma, ["命理八字", "运势", "偏好"], "u1")
        joined = " ".join(hits)
        assert "晚上运动" not in joined, (
            f"user=u2 的三元组泄漏到了 u1 的结果里：{hits}")

    def test_each_user_sees_own(self, soma):
        a = " ".join(_semantic_hits(soma, ["偏好", "命理"], "u1"))
        b = " ".join(_semantic_hits(soma, ["偏好", "命理"], "u2"))
        assert "早上开会" in a and "早上开会" not in b
        assert "晚上运动" in b and "晚上运动" not in a


class TestLikeCap:
    """★ 短词 LIKE 必须封顶。"""

    def _db(self, tmp_path, n=400):
        import time, uuid
        from soma.memory.episodic import EpisodicStore
        st = EpisodicStore(tmp_path, use_vector_search=False)
        pool = ["系统", "整体", "关联", "反馈", "结构", "演化", "矛盾", "取舍"]
        now = time.time()
        st._conn.executemany(
            "INSERT INTO episodic_memories(id,content,content_hash,timestamp,"
            "importance,access_count,context_json,memory_type,user_id,"
            "session_id,agent_id,shared_group_id,nature) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [(uuid.uuid4().hex, f"{pool[i%8]}相关记录{i}", "h", now - i, 0.5, 0,
              "{}", "episodic", "u1", "", "", "", "event") for i in range(n)])
        st._conn.commit()
        return st

    def test_cap_limits_like_terms(self, tmp_path):
        """★ 只用一个「只有第 5 个词才能命中」的场景验证截断真的生效。

        前 4 个词在库里不存在，第 5 个词存在 —— 截到 3 就查不到。
        """
        import time, uuid
        st = self._db(tmp_path)
        try:
            st._conn.execute(
                "INSERT INTO episodic_memories(id,content,content_hash,timestamp,"
                "importance,access_count,context_json,memory_type,user_id,"
                "session_id,agent_id,shared_group_id,nature) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (uuid.uuid4().hex, "独一无二的辛烷标记", "h", time.time(), 0.5, 0,
                 "{}", "episodic", "u1", "", "", "", "event"))
            st._conn.commit()

            words = ["甲甲", "乙乙", "丙丙", "丁丁", "辛烷"]   # 全是 2 字
            def run(cap):
                return fts5_keyword_search(
                    st._conn, words, table_name="episodic_memories",
                    fts_table="episodic_fts",
                    search_cols=["content", "context_json"], id_col="id",
                    time_col="timestamp", importance_col="importance",
                    user_col="user_id", row_converter=st._row_to_memory,
                    top_k=10, user_id="u1", max_like_keywords=cap)

            assert any("辛烷" in r.content for r in run(10)), "不截断时该查得到"
            assert not any("辛烷" in r.content for r in run(3)), (
                "截到 3 个仍然查到了第 5 个词 —— 截断没生效")
        finally:
            st.close()

    def test_cap_does_not_hurt_when_topk_fills(self, tmp_path):
        """★ 截断的真实代价：只要前几个词就能填满 top_k，命中数不变。"""
        st = self._db(tmp_path)
        try:
            words = ["系统", "整体", "关联", "反馈", "结构"]
            def run(cap):
                return fts5_keyword_search(
                    st._conn, words, table_name="episodic_memories",
                    fts_table="episodic_fts",
                    search_cols=["content", "context_json"], id_col="id",
                    time_col="timestamp", importance_col="importance",
                    user_col="user_id", row_converter=st._row_to_memory,
                    top_k=10, user_id="u1", max_like_keywords=cap)
            assert len(run(5)) == len(run(3)) == 10
        finally:
            st.close()


class TestSemanticLikeConsistency:
    """★ 全局通道在 FTS 路径和 LIKE 路径必须一致。"""

    def test_short_keyword_finds_global(self, tmp_path):
        """短词（<3 字）走 LIKE 路径时也要能查到全局三元组。

        第一版只改了 FTS 路径的 ns_clause，LIKE 路径是独立构造的，漏了。
        """
        s = SOMA(llm="mock", persist_dir=str(tmp_path),
                 use_vector_search=False, warmup_on_init=False)
        try:
            sem = s._agent.memory.semantic
            sem.add_triple("八字", "关联", "五行", 0.9)     # 全局，2 字
            got = sem.query_by_keywords(["八字"], top_k=5, namespace="u1",
                                        include_global=True)
            assert any("八字" in m.content for m in got), (
                "短词路径查不到全局三元组 —— 两条路径行为不一致")
        finally:
            s.close()
