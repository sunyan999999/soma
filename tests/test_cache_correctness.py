# -*- coding: utf-8 -*-
"""两处性能缓存的正确性 —— 缓存可以慢一点，但不能读到陈旧值。

## 背景（2026-11-24，下游生产 32k 条实测）

两个真实热点：

**① `count_indexed()` 每次搜索全表扫描**

```sql
SELECT COUNT(*) FROM episodic_memories WHERE vector IS NOT NULL
```

`vector IS NOT NULL` 走不了索引。32,233 行实测 **100ms**（下游是 65ms），
而 `similarity_search` 每次调用都查一次做 DB/faiss 一致性检查 ——
一次激活 4~6 次 → 300~600ms 的纯重复劳动，占激活耗时 40%+。

修：缓存 + 双探针
  · `PRAGMA data_version` —— 其他连接提交后变化
  · `conn.total_changes`  —— 本连接累计写入数（零成本属性）

**② `episodic.get()` 的 N+1**

`query_by_vector` 对每个候选都调 `get(mid)`，同一条记忆在一次激活里被
hydration 多次（下游 SQL 抓取：2 次 activate 共 3,122 条 SQL，同一 id 重复 10 次）。

修：LRU + 2 秒 TTL，写路径主动失效。

实测（3 万条）：count_indexed 100ms → 0.006ms；get 0.019ms → 0.000ms。

## 为什么只测正确性不测速度

速度判据依赖机器、依赖数据量，放进 CI 只会变成 flaky。
速度用一次性脚本测（已记录在 CHANGELOG），CI 里只钉「不能读到旧值」。

## 注入自证

  · count_indexed 去掉 total_changes 探针 → TestCountIndexedCache 红
  · get 去掉写路径失效                  → TestGetCache 红
  · increment_access 不更新缓存对象      → TestAccessCount 红
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from soma.memory.episodic import EpisodicStore  # noqa: E402
from soma.vector_store import NumpyVectorIndex  # noqa: E402


def _store(tmp_path, vector=False):
    return EpisodicStore(tmp_path, use_vector_search=vector)


class TestCountIndexedCache:
    """★ count_indexed 缓存必须在任何写入后失效。"""

    def _setup(self, tmp_path):
        store = _store(tmp_path)
        idx = NumpyVectorIndex(tmp_path / "episodic.db", 512)
        idx.ensure_table(store._conn)
        return store, idx

    def _insert(self, store, n, vector=None):
        import time, uuid
        blob = vector if vector is not None else np.zeros(512, dtype=np.float32).tobytes()
        store._conn.executemany(
            "INSERT INTO episodic_memories(id,content,content_hash,timestamp,"
            "importance,access_count,context_json,memory_type,user_id,"
            "session_id,agent_id,shared_group_id,nature,vector) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [(uuid.uuid4().hex, f"c{i}", "h", time.time(), 0.5, 0, "{}",
              "episodic", "u1", "", "", "", "event", blob) for i in range(n)],
        )
        store._conn.commit()

    def test_same_connection_write_invalidates(self, tmp_path):
        """★ 本连接写入必须让缓存失效。

        只靠 `data_version` 会漏掉这种 —— 它只反映**其他连接**的提交。
        第一版就是这么翻车的：self-heal 判据读到了陈旧的 0。
        """
        store, idx = self._setup(tmp_path)
        try:
            assert idx.count_indexed(store._conn) == 0
            self._insert(store, 5)
            assert idx.count_indexed(store._conn) == 5, (
                "同一连接插入后仍读到旧值 —— 缓存没有失效")
        finally:
            store.close()

    def test_other_connection_write_invalidates(self, tmp_path):
        """另一个连接提交后（data_version 变化）也必须失效。"""
        store, idx = self._setup(tmp_path)
        other = _store(tmp_path)          # 模拟另一个进程/实例
        try:
            assert idx.count_indexed(store._conn) == 0
            import time, uuid
            other._conn.execute(
                "INSERT INTO episodic_memories(id,content,content_hash,timestamp,"
                "importance,access_count,context_json,memory_type,user_id,"
                "session_id,agent_id,shared_group_id,nature,vector) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (uuid.uuid4().hex, "x", "h", time.time(), 0.5, 0, "{}",
                 "episodic", "u1", "", "", "", "event",
                 np.zeros(512, dtype=np.float32).tobytes()),
            )
            other._conn.commit()
            assert idx.count_indexed(store._conn) == 1, (
                "其他连接提交后仍读到旧值 —— data_version 探针失效了")
        finally:
            store.close()
            other.close()

    def test_delete_vector_invalidates(self, tmp_path):
        store, idx = self._setup(tmp_path)
        try:
            self._insert(store, 3)
            assert idx.count_indexed(store._conn) == 3
            mid = store._conn.execute(
                "SELECT id FROM episodic_memories LIMIT 1").fetchone()[0]
            idx.delete_vector(store._conn, mid)
            store._conn.commit()
            assert idx.count_indexed(store._conn) == 2, (
                "删向量后仍读到旧计数")
        finally:
            store.close()


class TestGetCache:
    """★ get() 缓存：写路径必须失效。"""

    def test_update_visible(self, tmp_path):
        store = _store(tmp_path)
        try:
            mid = store.add("原始内容", user_id="u1")
            assert store.get(mid).content == "原始内容"
            store.update(mid, content="改过的内容")
            assert store.get(mid).content == "改过的内容", (
                "update 之后 get 还是旧内容 —— 缓存没失效")
        finally:
            store.close()

    def test_delete_returns_none(self, tmp_path):
        store = _store(tmp_path)
        try:
            mid = store.add("会被删掉", user_id="u1")
            assert store.get(mid) is not None
            store.delete(mid)
            assert store.get(mid) is None, "删除后 get 还能拿到对象"
        finally:
            store.close()

    def test_new_object_each_store(self, tmp_path):
        """不同实例各自缓存，互不干扰。"""
        a = _store(tmp_path)
        mid = a.add("共享内容", user_id="u1")
        b = _store(tmp_path)
        try:
            assert a.get(mid).content == "共享内容"
            assert b.get(mid).content == "共享内容"
        finally:
            a.close()
            b.close()


class TestAccessCount:
    """★ increment_access 后缓存对象要同步 —— 否则召回排序读到旧值。"""

    def test_increment_visible_through_cache(self, tmp_path):
        store = _store(tmp_path)
        try:
            mid = store.add("计数测试", user_id="u1")
            first = store.get(mid)
            assert first.access_count == 0
            assert store.increment_access(mid) is True
            again = store.get(mid)
            assert again.access_count == 1, (
                f"increment 之后 get 还是 {again.access_count} —— "
                f"缓存对象没同步（access_count 影响 relevance_potential）")
        finally:
            store.close()

    def test_increment_returns_false_for_missing(self, tmp_path):
        """原来的返回值用 conn.total_changes（连接累计），永远为真 —— 已修。"""
        store = _store(tmp_path)
        try:
            store.add("随便一条", user_id="u1")   # 让 total_changes > 0
            assert store.increment_access("not-a-real-id") is False, (
                "对不存在的 id 递增，返回值却是 True —— "
                "还在用 conn.total_changes 判断")
        finally:
            store.close()

    def test_increment_persists(self, tmp_path):
        """跨实例读到的也必须是新值（DB 真的写了）。"""
        a = _store(tmp_path)
        mid = a.add("持久化", user_id="u1")
        a.increment_access(mid)
        b = _store(tmp_path)
        try:
            assert b.get(mid).access_count == 1
        finally:
            a.close()
            b.close()
