# -*- coding: utf-8 -*-
"""多专家共享 SQLite 连接测试（v2.0.18）

覆盖：
- 开关语义（默认关闭时逐字退化为历史行为）
- 复用粒度：同线程同路径复用、不同路径 / 不同线程各自独立
- 引用计数关闭语义
- transaction() 的原子性（回滚 / 提交）
- SOMA 集成：同一 persist_dir 的两个实例共享连接，关闭互不误伤
"""
import sqlite3
import threading

import pytest

from soma import SOMA
from soma import db as somadb
from soma.db import (
    close_store_connection,
    is_shared_enabled,
    open_store_connection,
    reset,
    set_shared_enabled,
    stats,
    transaction,
)


@pytest.fixture(autouse=True)
def _isolate_registry():
    """每个测试前后都清干净注册表与开关，避免进程级状态互相污染。"""
    prev = is_shared_enabled()
    reset()
    yield
    reset()
    set_shared_enabled(prev)


def _soma(persist_dir, **kw) -> SOMA:
    """轻量实例：关掉向量检索，避免测试里去加载嵌入模型。"""
    return SOMA(persist_dir=str(persist_dir), llm="mock",
                use_vector_search=False, **kw)


# ── 开关语义 ────────────────────────────────────────────


class TestSwitch:
    def test_disabled_by_default_is_passthrough(self, tmp_path):
        """默认关闭：不产生任何注册表条目，连接行为与历史一致。"""
        assert is_shared_enabled() is False
        conn = open_store_connection(tmp_path / "x.db")
        assert stats()["count"] == 0, "关闭时不该有任何共享条目"

        conn.execute("CREATE TABLE t (a INTEGER)")
        conn.execute("INSERT INTO t VALUES (1)")
        conn.commit()
        assert conn.execute("SELECT a FROM t").fetchone()[0] == 1

        assert close_store_connection(conn) is True
        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")          # 确实关掉了

    def test_row_factory_set_in_both_modes(self, tmp_path):
        """共享与否都要能按列名取值（sqlite3.Row）。"""
        for flag in (False, True):
            reset()
            set_shared_enabled(flag)
            conn = open_store_connection(tmp_path / f"rf{int(flag)}.db")
            conn.execute("CREATE TABLE t (a INTEGER, b TEXT)")
            conn.execute("INSERT INTO t VALUES (7, 'x')")
            conn.commit()
            row = conn.execute("SELECT a, b FROM t").fetchone()
            assert row["a"] == 7 and row["b"] == "x"
            close_store_connection(conn)

    def test_reset_closes_everything(self, tmp_path):
        set_shared_enabled(True)
        a = open_store_connection(tmp_path / "a.db")
        b = open_store_connection(tmp_path / "b.db")
        assert stats()["count"] == 2
        reset()
        assert stats()["count"] == 0
        for conn in (a, b):
            with pytest.raises(sqlite3.ProgrammingError):
                conn.execute("SELECT 1")


# ── 复用粒度 ────────────────────────────────────────────


class TestReuseScope:
    def test_same_thread_same_path_reuses(self, tmp_path):
        set_shared_enabled(True)
        p = tmp_path / "y.db"
        c1 = open_store_connection(p)
        c2 = open_store_connection(p)
        assert c1 is c2, "同一线程内同一路径应复用同一条连接"
        assert stats()["count"] == 1
        assert stats()["connections"][0]["refs"] == 2

    def test_relative_and_absolute_path_are_same_key(self, tmp_path, monkeypatch):
        """a.db 与 ./a.db 必须归一到同一个键，否则复用形同虚设。"""
        set_shared_enabled(True)
        monkeypatch.chdir(tmp_path)
        c1 = open_store_connection(tmp_path / "a.db")
        c2 = open_store_connection("a.db")
        assert c1 is c2

    def test_different_paths_are_independent(self, tmp_path):
        set_shared_enabled(True)
        c1 = open_store_connection(tmp_path / "a.db")
        c2 = open_store_connection(tmp_path / "b.db")
        assert c1 is not c2
        assert stats()["count"] == 2

    def test_each_thread_gets_own_connection(self, tmp_path):
        """跨线程不共享连接 —— CPython sqlite3 并发用同一条连接会静默丢数据。"""
        set_shared_enabled(True)
        p = tmp_path / "t.db"
        main_conn = open_store_connection(p)
        seen = {}

        def worker():
            seen["conn"] = open_store_connection(p)
            seen["same"] = seen["conn"] is main_conn

        th = threading.Thread(target=worker)
        th.start()
        th.join()

        assert seen["same"] is False, "不同线程不该共用同一条连接"
        assert stats()["count"] == 2
        assert stats()["threads"] == 2
        # 主线程再取仍然是它自己那条
        assert open_store_connection(p) is main_conn


# ── 引用计数关闭语义 ────────────────────────────────────


class TestRefCounting:
    def test_close_only_frees_on_last_holder(self, tmp_path):
        set_shared_enabled(True)
        p = tmp_path / "r.db"
        c1 = open_store_connection(p)
        c2 = open_store_connection(p)
        assert c1 is c2

        assert close_store_connection(c1) is False, "还有持有者，不该真关"
        assert stats()["count"] == 1
        assert c2.execute("SELECT 1").fetchone()[0] == 1

        assert close_store_connection(c2) is True, "最后一个持有者应真关"
        assert stats()["count"] == 0

    def test_close_of_unregistered_connection(self, tmp_path):
        """不在注册表里的连接（共享关闭时建的那些）走直接关闭。"""
        conn = open_store_connection(tmp_path / "solo.db")
        assert close_store_connection(conn) is True

    def test_close_none_is_noop(self):
        assert close_store_connection(None) is False

    def test_release_after_reset_does_not_raise(self, tmp_path):
        """reset() 之后再关一次，不该抛错（注册表已空，按独立连接处理）。"""
        set_shared_enabled(True)
        conn = open_store_connection(tmp_path / "z.db")
        reset()
        close_store_connection(conn)


# ── transaction ─────────────────────────────────────────


class TestTransaction:
    def test_rollback_on_exception(self, tmp_path):
        set_shared_enabled(True)
        conn = open_store_connection(tmp_path / "tx.db")
        conn.execute("CREATE TABLE t (v TEXT)")
        conn.commit()

        with pytest.raises(RuntimeError):
            with transaction(conn):
                conn.execute("INSERT INTO t VALUES ('bad')")
                raise RuntimeError("故意失败")

        assert conn.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 0

    def test_commit_on_success(self, tmp_path):
        set_shared_enabled(True)
        conn = open_store_connection(tmp_path / "tx2.db")
        conn.execute("CREATE TABLE t (v TEXT)")
        conn.commit()

        with transaction(conn):
            conn.execute("INSERT INTO t VALUES ('good')")

        assert conn.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 1

    def test_usable_when_shared_disabled(self, tmp_path):
        """共享关闭时 transaction() 仍是可用的 commit/rollback 包装。"""
        conn = open_store_connection(tmp_path / "tx3.db")
        conn.execute("CREATE TABLE t (v TEXT)")
        conn.commit()

        with transaction(conn):
            conn.execute("INSERT INTO t VALUES ('a')")
        assert conn.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 1

        with pytest.raises(ValueError):
            with transaction(conn):
                conn.execute("INSERT INTO t VALUES ('b')")
                raise ValueError("nope")
        assert conn.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 1


# ── SOMA 集成 ───────────────────────────────────────────


class TestSomaIntegration:
    def test_second_instance_shares_connections(self, tmp_path):
        """同一 persist_dir 的第二个实例复用主线程已有连接。"""
        main = threading.get_ident()

        def main_entries():
            return [c for c in stats()["connections"] if c["thread"] == main]

        s1 = _soma(tmp_path, shared_sqlite_connection=True)
        try:
            n1 = len(main_entries())
            assert n1 > 0, "开启共享后应建立共享连接"

            s2 = _soma(tmp_path, shared_sqlite_connection=True)
            try:
                assert len(main_entries()) == n1, "第二个实例不该新建连接"
                assert all(c["refs"] >= 2 for c in main_entries())
            finally:
                s2.close()
        finally:
            s1.close()

    def test_close_one_keeps_other_working(self, tmp_path):
        s1 = _soma(tmp_path, shared_sqlite_connection=True)
        s2 = _soma(tmp_path, shared_sqlite_connection=True)
        s1.remember("实例1 的记忆")
        s2.remember("实例2 的记忆")
        s1.close()

        conn = s2._agent.memory.episodic._conn
        n = conn.execute(
            "SELECT COUNT(*) FROM episodic_memories WHERE content=?",
            ("实例1 的记忆",),
        ).fetchone()[0]
        assert n == 1, "s1 关闭后 s2 应仍读得到数据"
        s2.close()

    def test_disabled_by_default_keeps_instances_independent(self, tmp_path):
        s1 = _soma(tmp_path)
        s2 = _soma(tmp_path)
        try:
            assert stats()["count"] == 0
            assert s1._agent.memory.episodic._conn is not \
                s2._agent.memory.episodic._conn
        finally:
            s1.close()
            s2.close()

    def test_flag_exposed_on_config(self, tmp_path):
        s = _soma(tmp_path, shared_sqlite_connection=True)
        try:
            assert s._config.shared_sqlite_connection is True
            assert is_shared_enabled() is True
        finally:
            s.close()
        # 回退：关掉开关后不再产生共享连接
        reset()
        s2 = _soma(tmp_path, shared_sqlite_connection=False)
        try:
            assert is_shared_enabled() is False
            assert stats()["count"] == 0
            s2.remember("回退后的记忆")
            n = s2._agent.memory.episodic._conn.execute(
                "SELECT COUNT(*) FROM episodic_memories WHERE content=?",
                ("回退后的记忆",),
            ).fetchone()[0]
            assert n == 1
        finally:
            s2.close()


# ── 多专家并发（每线程一个实例） ────────────────────────


class TestMultiExpertConcurrency:
    @pytest.mark.parametrize("shared", [False, True])
    def test_no_lost_writes_with_instance_per_thread(self, tmp_path, shared):
        """多专家形态：每个线程自己建一个实例写自己的库，一条都不能丢。"""
        n_threads, per_thread = 3, 12
        errors = []
        counts = []

        def worker(tid):
            try:
                s = _soma(tmp_path / f"exp{tid}", shared_sqlite_connection=shared)
                try:
                    for i in range(per_thread):
                        s.remember(f"专家{tid}记忆{i}")
                    counts.append(s._agent.memory.episodic._conn.execute(
                        "SELECT COUNT(*) FROM episodic_memories WHERE content LIKE ?",
                        (f"专家{tid}记忆%",),
                    ).fetchone()[0])
                finally:
                    s.close()
            except Exception as exc:                   # noqa: BLE001
                errors.append(f"t{tid}: {type(exc).__name__}: {exc}")

        threads = [threading.Thread(target=worker, args=(t,))
                   for t in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"并发写报错：{errors}"
        assert sum(counts) == n_threads * per_thread, (
            f"丢数据：期望 {n_threads * per_thread}，实到 {sum(counts)}"
        )
