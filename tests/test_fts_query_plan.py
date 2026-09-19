# -*- coding: utf-8 -*-
"""FTS5 关键词通道的查询计划必须是「FTS 命中物化 + rowid 比对」(v2.0.18.2)

背景
----
接入方报「FTS5 比 LIKE 慢」，实测复现并定位到**不是 FTS5 本身慢，是写法**：

    -- 慢（原写法）：SQLite 选成「t 驱动 → 逐行去 FTS 虚拟表探」
    SELECT t.* FROM episodic_memories t
    INNER JOIN episodic_fts fts ON t.rowid = fts.rowid
    WHERE episodic_fts MATCH ? AND t.user_id = ?

    -- 快（本版写法）：FTS 命中先物化成 rowid 列表，再拿 idx_episodic_user
    -- 扫该用户的行去比对
    SELECT t.* FROM episodic_memories t
    WHERE t.rowid IN (SELECT rowid FROM episodic_fts WHERE episodic_fts MATCH ?)
      AND t.user_id = ?

27000 条 / 130 用户的本地实测（中位数）：

    场景                        JOIN 写法     子查询写法    倍数
    稠密命中（37%）             137.71ms       16.53ms     8.3×
    稀疏命中（u1 命中 0 条）     38.57ms        0.45ms    86×
    LIKE 对照                    0.36ms        0.24ms     —

稀疏那行是关键：**一条都没命中，JOIN 写法仍要固定付 38ms** —— 这笔开销与命中
多少无关，只要带 user_id 就每次照付。这是每次关键词检索的固定税，不是密度问题。

本文件守住三件事：
  1. 生成的 SQL 里不能再出现对 FTS 表的 JOIN
  2. 执行计划必须是物化子查询（LIST SUBQUERY），不是逐行探
  3. 改写后结果集与原来一致（隔离 / 顺序 / LIMIT / 时间窗 / 去重）

「回退即失败」验证见 tmp/verify_fts_plan_revert.py：把写法改回 JOIN，本文件必须
失败（exit=1），否则标明验证无效，不是测试结论。
"""
import sqlite3
import time

import pytest


# ── 造库 ──────────────────────────────────────────────────────────

TOPICS = ["睡眠质量", "工作压力", "跑步训练", "饮食记录"]
FILLER = ["今天天气不错", "随手写点东西", "整理一下思路"]


def _bare_store(tmp_path, n=4000, n_users=5):
    """建库并**直接插行**（不经 store.add 的完整管线），用于放大到可观行数。

    ``n_users`` 必须与 ``len(TOPICS)``（4）互质，否则 i%4 与 i%n_users 会锁成
    固定组合，某个用户可能只拿到部分话题 —— 那会让「u3 搜不到睡眠质量」这类
    断言失败在与被测代码无关的地方。


    episodic_fts 由 episodic.py 里的 AFTER INSERT 触发器维护，直插同样会进
    FTS 索引，所以这条路走的是真实检索路径。
    """
    from soma.memory.episodic import EpisodicStore

    store = EpisodicStore(tmp_path, embedder=None, use_vector_search=False)
    rows = [
        (f"m{i}", f"{TOPICS[i % len(TOPICS)]}：{FILLER[i % len(FILLER)]} 第{i}条",
         f"h{i}", time.time() - i, 0.5, 0, "{}", "episodic", f"u{i % n_users}",
         "", "", "", "event")
        for i in range(n)
    ]
    store._conn.executemany(
        "INSERT INTO episodic_memories (id, content, content_hash, timestamp,"
        "importance, access_count, context_json, memory_type, user_id, session_id,"
        "agent_id, shared_group_id, nature) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        rows)
    store._conn.commit()
    return store


def _capture_sql(store, fn):
    """跑一次操作，回收它实际执行过的 SQL（FTS 语句可能有多条，取带 MATCH 的）。"""
    seen = []
    store._conn.set_trace_callback(seen.append)
    try:
        fn()
    finally:
        store._conn.set_trace_callback(None)
    fts = [s for s in seen if "MATCH" in s.upper()]
    assert fts, f"本次操作没有走到 FTS 分支，捕获到的语句：{seen}"
    return fts[-1]


def _sql_body(sql: str) -> str:
    """去掉 SQL 注释后的语句本体。

    被测代码在 SQL 里写了 `-- 不能写成 JOIN ...` 这样的说明注释，注释里带
    "JOIN" 二字；直接对原文做子串判断会被自己的注释误伤。
    """
    return "\n".join(
        ln.split("--")[0] for ln in sql.splitlines())


def _median_ms(fn, reps=7):
    ts = []
    for _ in range(reps):
        t0 = time.perf_counter()
        fn()
        ts.append((time.perf_counter() - t0) * 1000)
    ts.sort()
    return ts[len(ts) // 2]


# ── 1. SQL 形态 ───────────────────────────────────────────────────

class TestSqlShape:
    """生成的 SQL 不得再 JOIN FTS 表 —— 这是修复的全部内容。"""

    def test_keyword_channel_sql_has_no_fts_join(self, tmp_path):
        store = _bare_store(tmp_path)
        sql = _capture_sql(
            store, lambda: store.query_by_keywords(["睡眠质量"], top_k=5,
                                                   user_id="u1"))
        body = _sql_body(sql)
        assert "JOIN" not in body.upper(), (
            "关键词通道又写成了 JOIN FTS 表 —— 这正是「命中为 0 也固定付 38ms」"
            f"的那条慢计划。实际 SQL：\n{sql}")
        assert "rowid IN (" in body, f"应为 rowid 子查询形态，实际：\n{sql}"
        store.close()

    def test_sql_is_semantically_external_content_rowid(self, tmp_path):
        """改写的合法性前提：fts.rowid 与主表 rowid 等价（external-content 表）。

        这条断言在，别人将来把 FTS5 改成 standalone/其它 content_rowid 时，能
        立刻发现「rowid 子查询」的前提没了。
        """
        store = _bare_store(tmp_path, n=50, n_users=5)
        ddl = store._conn.execute(
            "SELECT sql FROM sqlite_master WHERE name='episodic_fts'"
        ).fetchone()[0]
        assert "content='episodic_memories'" in ddl, ddl
        assert "content_rowid='rowid'" in ddl, ddl
        store.close()

    def test_consolidation_sql_has_no_fts_join(self, tmp_path):
        """第二个调用点：consolidation.py 的候选召回。"""
        store = _bare_store(tmp_path)
        c = store._conn
        seen = []
        c.set_trace_callback(seen.append)
        try:
            try:
                from soma.memory.consolidation import ConsolidationEngine
                ConsolidationEngine(store._conn).find_similar(
                    "睡眠质量：今天天气不错", user_id="u1")
            except Exception:
                # embedder 为 None 时后面会早退，但 FTS 语句已经执行过了
                pass
        finally:
            c.set_trace_callback(None)
        fts = [s for s in seen if "MATCH" in s.upper()]
        assert fts, f"未走到 FTS 分支，捕获：{seen}"
        for s in fts:
            body = _sql_body(s)
            assert "JOIN" not in body.upper(), f"consolidation 仍在 JOIN FTS 表：\n{s}"
            assert "rowid IN (" in body, f"应为 rowid 子查询形态：\n{s}"
        store.close()

    def test_semantic_sql_has_no_fts_join(self, tmp_path):
        """第三个调用点：semantic.py 的三元组召回。"""
        from soma.memory.semantic import SemanticStore

        s = SemanticStore(tmp_path / "sem.db")
        seen = []
        s._conn.set_trace_callback(seen.append)
        try:
            try:
                s.query_by_keywords(["睡眠质量"], top_k=5)
            except Exception:
                pass
        finally:
            s._conn.set_trace_callback(None)
        fts = [x for x in seen if "MATCH" in x.upper()]
        assert fts, f"未走到 FTS 分支，捕获：{seen}"
        for x in fts:
            body = _sql_body(x)
            assert "JOIN" not in body.upper(), f"semantic 仍在 JOIN FTS 表：\n{x}"
            assert "rowid IN (" in body, f"应为 rowid 子查询形态：\n{x}"
        s.close()


# ── 2. 执行计划 ───────────────────────────────────────────────────

class TestQueryPlan:
    def test_plan_materializes_fts_hits_as_list_subquery(self, tmp_path):
        """计划里必须出现 LIST SUBQUERY —— 这是「FTS 命中先物化一次」的标志。

        JOIN 写法下计划是 `SEARCH t USING INDEX ...` 紧跟 `SCAN fts VIRTUAL
        TABLE`，即 t 每行探一次虚拟表；物化后虚拟表扫描挂在 LIST SUBQUERY 下，
        只算一次。
        """
        store = _bare_store(tmp_path)
        sql = _capture_sql(
            store, lambda: store.query_by_keywords(["睡眠质量"], top_k=5,
                                                   user_id="u1"))
        plan = [r[-1] for r in
                store._conn.execute("EXPLAIN QUERY PLAN " + sql)]
        joined = "\n".join(plan)
        assert "LIST SUBQUERY" in joined, (
            f"计划疑为逐行探虚拟表的慢计划：\n{joined}")
        store.close()

    def test_plan_uses_user_index_not_full_scan(self, tmp_path):
        """带 user_id 时应当走用户索引，而不是全表扫。"""
        store = _bare_store(tmp_path)
        sql = _capture_sql(
            store, lambda: store.query_by_keywords(["睡眠质量"], top_k=5,
                                                   user_id="u1"))
        plan = "\n".join(r[-1] for r in
                         store._conn.execute("EXPLAIN QUERY PLAN " + sql))
        assert "idx_episodic_user" in plan or "user_id=?" in plan, plan
        assert "SCAN episodic_memories" not in plan, (
            f"退化成全表扫描了：\n{plan}")
        store.close()


# ── 3. 固定开销（DSH 报的就是这个）─────────────────────────────────

class TestFixedCost:
    def test_empty_result_search_does_not_pay_fixed_cost(self, tmp_path):
        """命中为空时不该有明显开销 —— JOIN 写法下这里固定付几十毫秒。

        这几个关键词在本库里**一条都不命中**，所以断言的是纯固定开销：修复后与
        命中数无关地接近 0，而 JOIN 写法要按该用户的行数逐行去探 FTS 虚拟表。

        本测试规模（20000 条 / 101 用户）实测中位数：

            关键词数    子查询写法    JOIN 写法     阈值
            1 个         0.15ms       5.86ms
            3 个         0.20ms      14.08ms
            6 个         0.31ms      27.29ms      5ms  ← 取这一组

        取 30 个关键词那种规模会把差距拉得更大，但没必要：6 个词时阈值两侧各有
        16× / 5.5× 余量，机器慢几倍也不会误判。
        """
        store = _bare_store(tmp_path, n=20000, n_users=101)
        ms = _median_ms(
            lambda: store.query_by_keywords(
                ["面试复盘", "偏头痛发作", "搬家计划",
                 "装修预算", "体检报告", "宠物疫苗"],
                top_k=15, user_id="u1"))
        assert ms < 5.0, (
            f"空结果关键词检索耗时 {ms:.2f}ms —— 疑似又回到了逐行探 FTS 虚拟表"
            " 的慢计划（该写法与命中数无关，每次固定付几十毫秒）")
        store.close()

    def test_search_with_hits_stays_fast(self, tmp_path):
        """有命中的情况同样不能退化。"""
        store = _bare_store(tmp_path, n=20000, n_users=101)
        ms = _median_ms(
            lambda: store.query_by_keywords(["睡眠质量"], top_k=15, user_id="u1"))
        assert ms < 60.0, f"命中 15 条的关键词检索耗时 {ms:.2f}ms，疑似计划退化"
        store.close()


# ── 4. 结果正确性（改写不能改变语义）─────────────────────────────

class TestResultsUnchanged:
    def test_user_isolation_holds(self, tmp_path):
        store = _bare_store(tmp_path, n=600, n_users=5)
        hits = store.query_by_keywords(["睡眠质量"], top_k=20, user_id="u3")
        assert hits, "应能取到 u3 自己的记忆"
        assert all(h.user_id == "u3" for h in hits), \
            f"取到了别人的记忆：{[h.user_id for h in hits]}"
        store.close()

    def test_top_k_respected(self, tmp_path):
        store = _bare_store(tmp_path, n=600, n_users=5)
        for k in (1, 3, 7):
            hits = store.query_by_keywords(["睡眠质量"], top_k=k, user_id="u3")
            assert len(hits) <= k, f"top_k={k} 却返回 {len(hits)} 条"
        store.close()

    def test_no_duplicate_ids(self, tmp_path):
        """一条记忆同时命中多个关键词时不得重复返回。"""
        store = _bare_store(tmp_path, n=600, n_users=5)
        hits = store.query_by_keywords(["睡眠质量", "工作压力", "跑步训练"],
                                       top_k=30, user_id="u3")
        ids = [h.id for h in hits]
        assert len(ids) == len(set(ids)), f"结果里有重复 id：{ids}"
        store.close()

    def test_time_window_applies(self, tmp_path):
        """max_age_days 必须在 SQL 侧生效。"""
        store = _bare_store(tmp_path, n=600, n_users=5)
        # _bare_store 的 timestamp 是 time.time() - i，即越靠后的行越旧
        wide = store.query_by_keywords(["睡眠质量"], top_k=50, user_id="u3",
                                       max_age_days=10000)
        narrow = store.query_by_keywords(["睡眠质量"], top_k=50, user_id="u3",
                                         max_age_days=1)
        assert len(narrow) <= len(wide), "时间窗收窄后结果反而变多了"
        cutoff = time.time() - 1 * 86400
        assert all(h.timestamp >= cutoff for h in narrow), \
            "时间窗外的记忆被返回了"
        store.close()

    def test_results_ordered_newest_first(self, tmp_path):
        store = _bare_store(tmp_path, n=600, n_users=5)
        hits = store.query_by_keywords(["睡眠质量"], top_k=10, user_id="u3")
        ts = [h.timestamp for h in hits]
        assert ts == sorted(ts, reverse=True), f"未按时间倒序：{ts}"
        store.close()

    def test_short_keywords_still_go_to_like_path(self, tmp_path):
        """<3 字关键词仍走 LIKE 兜底 —— 修复不该动这条分支。"""
        store = _bare_store(tmp_path, n=600, n_users=5)
        hits = store.query_by_keywords(["睡"], top_k=5, user_id="u3")
        assert hits, "短关键词应能取到结果（LIKE 分支）"
        assert all(h.user_id == "u3" for h in hits)
        store.close()

    def test_no_fts_keywords_returns_empty_not_crash(self, tmp_path):
        """全是短词时 FTS 分支不该被执行。"""
        store = _bare_store(tmp_path, n=100, n_users=5)
        sql_seen = []
        store._conn.set_trace_callback(sql_seen.append)
        try:
            store.query_by_keywords(["睡"], top_k=5, user_id="u1")
        finally:
            store._conn.set_trace_callback(None)
        assert not [s for s in sql_seen if "MATCH" in s.upper()], \
            "全是短关键词时不该走 FTS5 分支"
        store.close()


class TestPlanStability:
    def test_plan_identical_with_and_without_agent_filter(self, tmp_path):
        """加 agent/group 过滤不改变写法形态（同一段 SQL 模板）。"""
        store = _bare_store(tmp_path, n=400, n_users=5)
        a = _capture_sql(store, lambda: store.query_by_keywords(
            ["睡眠质量"], top_k=5, user_id="u1"))
        b = _capture_sql(store, lambda: store.query_by_keywords(
            ["睡眠质量"], top_k=5, user_id="u1", agent_id="ag1"))
        for sql in (a, b):
            assert "JOIN" not in _sql_body(sql).upper()
            assert "rowid IN (" in _sql_body(sql)
        # 结构差异只应体现在多出来的过滤条件上
        assert "agent_id" in b and "agent_id" not in a
        store.close()


def test_fts_index_actually_populated(tmp_path):
    """前提校验：直插的行确实进了 FTS 索引，上面的对照才有意义。"""
    store = _bare_store(tmp_path, n=200, n_users=5)
    n_match = store._conn.execute(
        "SELECT COUNT(*) FROM episodic_fts WHERE episodic_fts MATCH ?",
        ['"睡眠质量"']).fetchone()[0]
    assert n_match > 0, "FTS 索引没被触发器填充，本文件的前提不成立"
    store.close()
