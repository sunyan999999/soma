# -*- coding: utf-8 -*-
"""「user_id + agent_id」组合查询必须走 (user_id, agent_id) 复合索引（v2.0.18.3）

背景
----
DSH 在 2.0.18.2 生产复验里报的（复验报告第四节）：生产 hub 调用恒带 user_id +
agent_id，此时 SQLite 会放着选择性更好的 idx_episodic_user 不用，去扫
idx_episodic_agent（agent_id 近乎覆盖全表）。本地 21k 行 / 203 用户复现：
只有 3 条记忆的长尾用户，单次「子集 COUNT 35ms + 取向量 35ms ≈ 70ms」，
对照「只带 user_id」是 0.05ms —— 差 1400×，**且代价与用户记忆数无关**。

根因不在 SQL，而在**缺索引**：调用方拼的子句一直是对的
（``AND user_id = ? AND agent_id = ?``），是索引组合里没有这个搭配，计划器只能
将就。所以修复就是补一条复合索引、一行 SQL 都不改 —— 也因此本文件的守卫重点是
**索引在不在**（新建库 / 老库升级两条路径），而不是某条 SQL 长什么样。

同一条索引同时覆盖三处同形查询：
  · 向量子集检索    soma/vector_store.py::_exact_filtered_search
  · 写路径去重      soma/memory/episodic.py::add（+ content_hash）
  · 关键词 LIKE 兜底 soma/memory/search_utils.py 路径 2（中文 1~2 字词）

「回退即失败」验证见 tmp/verify_index_fix_revert.py：把索引创建删掉，本文件必须
失败（exit=1），否则标明验证无效，不是测试结论。
"""
import sqlite3

from soma.memory.episodic import EpisodicStore
from soma.memory.skill import SkillStore

AGENT = "soma"

# 2.0.18.2 的 episodic_memories 形态：三个单列索引，没有复合索引
LEGACY_SCHEMA = """
CREATE TABLE episodic_memories (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL DEFAULT '',
    timestamp REAL NOT NULL,
    importance REAL DEFAULT 0.5,
    access_count INTEGER DEFAULT 0,
    context_json TEXT DEFAULT '{}',
    last_access REAL,
    memory_type TEXT DEFAULT 'episodic',
    user_id TEXT NOT NULL DEFAULT '',
    session_id TEXT NOT NULL DEFAULT '',
    agent_id TEXT NOT NULL DEFAULT '',
    shared_group_id TEXT NOT NULL DEFAULT '',
    nature TEXT NOT NULL DEFAULT 'event'
);
CREATE INDEX idx_timestamp ON episodic_memories(timestamp DESC);
CREATE INDEX idx_content_hash ON episodic_memories(content_hash);
CREATE INDEX idx_episodic_user ON episodic_memories(user_id);
CREATE INDEX idx_episodic_agent ON episodic_memories(agent_id);
CREATE INDEX idx_episodic_group ON episodic_memories(shared_group_id);
"""

COMPOSITE = "idx_episodic_user_agent"

# 三处同形查询（与生产代码里的 WHERE 形态一致）
SQL_VECTOR = ("SELECT id, vector FROM episodic_memories "
              "WHERE vector IS NOT NULL AND user_id = ? AND agent_id = ?")
SQL_DEDUP = ("SELECT id FROM episodic_memories "
             "WHERE user_id = ? AND agent_id = ? AND content_hash = ? LIMIT 1")
SQL_LIKE = ("SELECT * FROM episodic_memories "
            "WHERE user_id = ? AND agent_id = ? AND (content LIKE ?) "
            "ORDER BY timestamp DESC LIMIT ?")


def _index_names(conn, table="episodic_memories"):
    return {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name=?",
        (table,))}


def _plan(conn, sql, params=()):
    """EXPLAIN QUERY PLAN 的 detail 列拼起来 —— 索引名会出现在里面。"""
    return " | ".join(
        str(r[3]) for r in conn.execute("EXPLAIN QUERY PLAN " + sql, params))


class TestIndexExists:
    """守卫重点：索引必须真的建出来 —— 计划对不对是 SQLite 的事，索引在不在是我们的事。"""

    def test_new_episodic_db_has_composite_index(self, tmp_path):
        s = EpisodicStore(tmp_path)
        try:
            assert COMPOSITE in _index_names(s._conn)
        finally:
            s._conn.close()

    def test_new_skill_db_has_composite_index(self, tmp_path):
        s = SkillStore(persist_dir=tmp_path)
        try:
            assert "idx_skill_user_agent" in _index_names(s._conn, "skills")
        finally:
            s._conn.close()

    def test_single_column_indexes_are_kept(self, tmp_path):
        """复合索引是**新增**不是替换 —— 只带 user_id 或只带 agent_id 的查询
        仍要用单列索引，替换掉会让那些（单租户下更常见的）查询变慢。"""
        s = EpisodicStore(tmp_path)
        try:
            names = _index_names(s._conn)
        finally:
            s._conn.close()
        assert {"idx_episodic_user", "idx_episodic_agent",
                "idx_episodic_group"} <= names


class TestLegacyUpgrade:
    """接入方升级路径：库里先有数据，新代码打开时才补索引。

    这条比「新建库带索引」更重要 —— 生产库都是老库，如果索引只在建库时创建，
    升级后代码改了、库里却没索引，修复对存量部署等于没生效。
    """

    def _legacy_db(self, tmp_path):
        db = tmp_path / "episodic.db"
        c = sqlite3.connect(db)
        c.executescript(LEGACY_SCHEMA)
        c.execute(
            "INSERT INTO episodic_memories (id, content, timestamp, user_id, "
            "agent_id) VALUES ('old', '升级前就存在的记忆', 0.0, 'alice', ?)",
            (AGENT,))
        c.commit()
        assert COMPOSITE not in _index_names(c), "前提：老库确实没有该索引"
        c.close()

    def test_index_is_added_on_open(self, tmp_path):
        self._legacy_db(tmp_path)
        s = EpisodicStore(tmp_path)
        try:
            assert COMPOSITE in _index_names(s._conn), (
                "老库被新代码打开后应补上复合索引")
        finally:
            s._conn.close()

    def test_legacy_data_survives_migration(self, tmp_path):
        self._legacy_db(tmp_path)
        s = EpisodicStore(tmp_path)
        try:
            row = s._conn.execute(
                "SELECT content FROM episodic_memories WHERE id='old'").fetchone()
            assert row is not None and row["content"] == "升级前就存在的记忆"
        finally:
            s._conn.close()

    def test_migration_is_idempotent(self, tmp_path):
        """重复打开不能出错（CREATE INDEX IF NOT EXISTS 的语义保证）。"""
        s1 = EpisodicStore(tmp_path)
        s1._conn.close()
        s2 = EpisodicStore(tmp_path)
        try:
            assert COMPOSITE in _index_names(s2._conn)
        finally:
            s2._conn.close()


class TestQueryPlan:
    """计划断言：这些 SQL 在我们的 schema 下确实会被判给复合索引。

    守的是「将来有人加了别的索引 / 改了子句，把计划带回 idx_episodic_agent」——
    那会让长尾用户重新按全表代价收费，而且不会有任何报错。
    """

    def _seeded(self, tmp_path):
        s = EpisodicStore(tmp_path)
        # vector 列由 NumpyVectorIndex.ensure_table() 在启用向量搜索时才加
        # （生产上向量通道是常态），这里只测计划，手工补上即可。
        s._conn.execute("ALTER TABLE episodic_memories ADD COLUMN vector BLOB")
        s._conn.commit()
        for i in range(200):
            s.add(f"head-{i}", {"d": "x"}, user_id="head", agent_id=AGENT)
        for i in range(5):
            s.add(f"tail-{i}", {"d": "x"}, user_id="tail", agent_id=AGENT)
        return s

    def test_vector_subset_query(self, tmp_path):
        s = self._seeded(tmp_path)
        try:
            plan = _plan(s._conn, SQL_VECTOR, ("tail", AGENT))
        finally:
            s._conn.close()
        assert COMPOSITE in plan, f"向量子集查询未走复合索引：{plan}"
        assert "idx_episodic_agent" not in plan, (
            f"仍在扫 agent_id 单列索引（代价与用户记忆数无关）：{plan}")

    def test_insert_dedup_query(self, tmp_path):
        """写路径：每次 add() 都要付，选错索引就是每次记住一条记忆都白扫全表。"""
        s = self._seeded(tmp_path)
        try:
            plan = _plan(s._conn, SQL_DEDUP, ("tail", AGENT, "ch"))
        finally:
            s._conn.close()
        assert COMPOSITE in plan, f"写路径去重未走复合索引：{plan}"

    def test_like_fallback_query(self, tmp_path):
        """关键词 LIKE 兜底：中文 1~2 字词会走到这里（trigram 只吃 ≥3 字）。"""
        s = self._seeded(tmp_path)
        try:
            plan = _plan(s._conn, SQL_LIKE, ("tail", AGENT, "%睡眠%", 10))
        finally:
            s._conn.close()
        assert COMPOSITE in plan, f"LIKE 兜底未走复合索引：{plan}"

    def test_filter_clause_shape_still_matches_index(self, tmp_path):
        """索引之所以有用，前提是子句真长这样 —— 守住这个前提。

        如果哪天 _build_filter_clause 不再产出 user_id + agent_id 的等值组合，
        复合索引就失去意义，这条会先失败，提示重新评估。
        """
        from soma.vector_store import NumpyVectorIndex

        idx = NumpyVectorIndex(tmp_path / "x.db", 8)
        clause, params = idx._build_filter_clause("tail", AGENT, "", None)
        assert clause == " AND user_id = ? AND agent_id = ?"
        assert params == ["tail", AGENT]

    def test_agent_with_group_is_not_the_same_shape(self, tmp_path):
        """带 group 时是 OR 条件，单索引用不上 —— 本索引管不到，别误以为都覆盖了。"""
        from soma.vector_store import NumpyVectorIndex

        idx = NumpyVectorIndex(tmp_path / "x.db", 8)
        clause, _ = idx._build_filter_clause("tail", AGENT, "g1", None)
        assert "OR" in clause
