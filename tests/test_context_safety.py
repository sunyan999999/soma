"""v2.0.17 — context 字段类型安全（读写双向）+ SQLite mmap 可配置。

对应 DSH 2026-09-12 报告：26,872 条记忆中 1 条 str 类型的 context 让全库检索
抛 TypeError —— 崩溃点是 episodic.query_by_vector 里的
``mem.context["_vector_score"] = score``。本文件锁死修复后的行为：

1. 读取：任何形状的 context_json 读出来都是 dict（脏值收进 ``_raw``，不丢数据）
2. 写入：非 dict 入参被规范化，从源头不再产生脏数据
3. 检索：全库向量检索遇到存量脏数据不崩
4. 自愈：repair_context 能扫出并修复存量脏数据，且可回滚
5. mmap：sqlite_mmap_size 可配置，默认 0（历史硬编码 256MB）
"""

import json

import numpy as np
import pytest

from soma.config import SOMAConfig
from soma.memory.context_utils import normalize_context, parse_context
from soma.memory.core import MemoryCore
from soma.memory.episodic import EpisodicStore
from soma.memory.skill import SkillStore
from soma.repair import repair_context, rollback_context


class FakeEmbedder:
    """最小契约实现 —— 只含 BaseEmbedder 的 encode / encode_batch / dimension。"""

    dimension = 8

    def encode(self, text):
        v = np.zeros(self.dimension, dtype=np.float32)
        v[abs(hash(text)) % self.dimension] = 1.0
        return v

    def encode_batch(self, texts):
        return np.stack([self.encode(t) for t in texts])


@pytest.fixture
def embedder():
    return FakeEmbedder()


@pytest.fixture
def store(tmp_path, embedder):
    return EpisodicStore(tmp_path, embedder=embedder, use_vector_search=True)


def _inject_dirty(store, memory_id, raw_json_text):
    """绕过写入侧防御，直接把脏值塞进库 —— 模拟历史存量数据。"""
    store._conn.execute(
        "UPDATE episodic_memories SET context_json=? WHERE id=?", (raw_json_text, memory_id)
    )
    store._conn.commit()


# ══════════════════════════════════════════════════════════════
# 1. parse_context — 读取侧
# ══════════════════════════════════════════════════════════════


class TestParseContext:
    @pytest.mark.parametrize("raw", [None, "", "   "])
    def test_empty_inputs_become_empty_dict(self, raw):
        assert parse_context(raw) == {}

    def test_dict_passthrough(self):
        ctx = {"a": 1, "b": [2]}
        assert parse_context(ctx) is ctx

    def test_valid_json_object(self):
        assert parse_context('{"source": "x", "n": 3}') == {"source": "x", "n": 3}

    def test_bare_json_string_goes_to_raw(self):
        """DSH 那条脏数据的形状：合法 JSON，但解析出来是 str。"""
        got = parse_context('"部署验证/分身健康检查"')
        assert got == {"_raw": "部署验证/分身健康检查"}
        assert isinstance(got, dict)

    def test_invalid_json_text_goes_to_raw(self):
        got = parse_context("裸文本不是JSON")
        assert got == {"_raw": "裸文本不是JSON"}

    @pytest.mark.parametrize("raw,expect", [
        ('[1, 2]', [1, 2]),
        ('123', 123),
        ('true', True),
        ('null', None),
    ])
    def test_non_object_json_goes_to_raw(self, raw, expect):
        assert parse_context(raw) == {"_raw": expect}

    def test_bytes_input(self):
        assert parse_context(b'{"k": "v"}') == {"k": "v"}

    def test_never_raises_on_arbitrary_input(self):
        """读取路径永不抛错 —— 这是"一条脏数据毁掉全库查询"的根治点。"""
        for weird in [object(), 3.14, [], {"already": "dict"}]:
            assert isinstance(parse_context(weird), dict)


# ══════════════════════════════════════════════════════════════
# 2. normalize_context — 写入侧
# ══════════════════════════════════════════════════════════════


class TestNormalizeContext:
    def test_none_becomes_empty_dict(self):
        assert normalize_context(None) == {}

    def test_dict_passthrough(self):
        ctx = {"a": 1}
        assert normalize_context(ctx) is ctx

    def test_string_wrapped(self):
        assert normalize_context("字符串") == {"_raw": "字符串"}

    def test_list_wrapped(self):
        assert normalize_context([1, 2]) == {"_raw": [1, 2]}


# ══════════════════════════════════════════════════════════════
# 3. 存储层读取安全
# ══════════════════════════════════════════════════════════════


class TestStoreReadSafety:
    def test_episodic_dirty_row_reads_as_dict(self, store):
        mid = store.add("记忆", {"ok": 1}, user_id="u1")
        _inject_dirty(store, mid, '"裸字符串context"')

        mem = store.get(mid)
        assert isinstance(mem.context, dict)
        assert mem.context["_raw"] == "裸字符串context"

    def test_episodic_invalid_json_row_reads_as_dict(self, store):
        mid = store.add("记忆2", {"ok": 1}, user_id="u1")
        _inject_dirty(store, mid, "完全不是JSON")

        mem = store.get(mid)
        assert isinstance(mem.context, dict)
        assert mem.context["_raw"] == "完全不是JSON"

    def test_skill_dirty_row_reads_as_dict(self, tmp_path):
        sk = SkillStore(tmp_path)
        sid = sk.add_skill("技能名", "模式", {"k": "v"})
        sk._conn.execute(
            "UPDATE skills SET context_json=? WHERE id=?", ('"裸技能context"', sid)
        )
        sk._conn.commit()

        mem = sk.get(sid) if hasattr(sk, "get") else sk._row_to_memory(
            sk._conn.execute("SELECT * FROM skills WHERE id=?", (sid,)).fetchone()
        )
        assert isinstance(mem.context, dict)
        assert mem.context["_raw"] == "裸技能context"

    def test_write_side_never_persists_bare_string(self, store):
        """写入侧规范化后，库里存的一定是 JSON 对象。"""
        mid = store.add("写入侧", "我是字符串", user_id="u1")
        raw = store._conn.execute(
            "SELECT context_json FROM episodic_memories WHERE id=?", (mid,)
        ).fetchone()[0]
        assert isinstance(json.loads(raw), dict)
        assert store.get(mid).context == {"_raw": "我是字符串"}


# ══════════════════════════════════════════════════════════════
# 4. 检索路径不崩（DSH 的复现用例）
# ══════════════════════════════════════════════════════════════


class TestVectorSearchNotCrash:
    def test_query_by_vector_with_dirty_context(self, store, embedder):
        """改造前：这里抛 TypeError: 'str' object does not support item assignment"""
        for i in range(3):
            store.add(f"正常记忆 {i}", {"src": f"s{i}"}, user_id="u1")
        dirty_id = store.add("脏记忆", {"ok": 1}, user_id="u1")
        _inject_dirty(store, dirty_id, '"部署验证/分身健康检查"')

        results = store.query_by_vector(embedder.encode("正常记忆"), top_k=5, user_id="")
        assert len(results) >= 1  # 全库检索（不带 user_id）不再崩

    def test_query_by_keywords_with_dirty_context(self, store):
        """关键词检索走同一个 _row_to_memory，同样必须安全。"""
        mid = store.add("关键词命中测试", {"ok": 1}, user_id="u1")
        _inject_dirty(store, mid, '"脏"')

        results = store.query_by_keywords(["关键词"], top_k=5, user_id="")
        for m in results:
            assert isinstance(m.context, dict)


# ══════════════════════════════════════════════════════════════
# 5. repair_context 自愈工具
# ══════════════════════════════════════════════════════════════


class TestRepairContext:
    def _seed(self, store, n_dirty=1, n_clean=3):
        for i in range(n_clean):
            store.add(f"干净 {i}", {"src": f"s{i}"}, user_id="u1")
        ids = []
        for i in range(n_dirty):
            mid = store.add(f"脏 {i}", {"ok": 1}, user_id="u1")
            _inject_dirty(store, mid, f'"脏context{i}"')
            ids.append(mid)
        return ids

    def test_dry_run_does_not_modify(self, store):
        ids = self._seed(store)
        res = repair_context(store, dry_run=True)

        assert res["dry_run"] is True
        assert res["dirty"] == 1
        assert res["repaired"] == 0
        assert res["backup_path"] is None
        # 库里还是脏的
        raw = store._conn.execute(
            "SELECT context_json FROM episodic_memories WHERE id=?", (ids[0],)
        ).fetchone()[0]
        assert raw == '"脏context0"'

    def test_apply_repairs_and_backs_up(self, store):
        ids = self._seed(store)
        res = repair_context(store, dry_run=False)

        assert res["dirty"] == 1
        assert res["repaired"] == 1
        assert res["by_table"] == {"episodic_memories": 1}
        assert res["backup_path"] is not None
        assert repair_context(store)["dirty"] == 0

        ctx = store.get(ids[0]).context
        assert ctx["_raw"] == "脏context0"
        assert "_repaired_at" in ctx

    def test_repaired_content_is_recoverable(self, store):
        """修复不丢数据：原值完整保留在 _raw。"""
        ids = self._seed(store)
        repair_context(store, dry_run=False)
        assert store.get(ids[0]).context["_raw"] == "脏context0"

    def test_rollback_restores_raw_value(self, store):
        ids = self._seed(store)
        res = repair_context(store, dry_run=False)
        assert repair_context(store)["dirty"] == 0

        rb = rollback_context(store, res["backup_path"])
        assert rb["restored"] == 1
        assert repair_context(store)["dirty"] == 1
        raw = store._conn.execute(
            "SELECT context_json FROM episodic_memories WHERE id=?", (ids[0],)
        ).fetchone()[0]
        assert raw == '"脏context0"'

    def test_clean_db_reports_nothing(self, store):
        self._seed(store, n_dirty=0)
        res = repair_context(store, dry_run=False)
        assert res["dirty"] == 0
        assert res["repaired"] == 0
        assert res["backup_path"] is None  # 无改动不写备份

    def test_user_id_filter(self, store):
        mid = store.add("u1 的脏数据", {"ok": 1}, user_id="u1")
        _inject_dirty(store, mid, '"脏"')
        mid2 = store.add("u2 的脏数据", {"ok": 1}, user_id="u2")
        _inject_dirty(store, mid2, '"也脏"')

        res = repair_context(store, dry_run=False, user_id="u1")
        assert res["repaired"] == 1
        # u2 的那条没被动
        assert repair_context(store)["dirty"] == 1

    def test_limit(self, store):
        self._seed(store, n_dirty=3)
        res = repair_context(store, dry_run=False, limit=1)
        assert res["repaired"] == 1
        assert repair_context(store)["dirty"] == 2

    def test_scan_covers_skill_store(self, tmp_path, store):
        sk = SkillStore(tmp_path)
        sid = sk.add_skill("技能", "模式", {"k": "v"})
        sk._conn.execute("UPDATE skills SET context_json=? WHERE id=?", ('"脏技能"', sid))
        sk._conn.commit()

        # repair_context 只认 EpisodicStore 的连接，这里直接传 skill 的连接
        res = repair_context(sk, dry_run=True)
        assert res["by_table"].get("skills") == 1

    def test_samples_preview(self, store):
        self._seed(store)
        res = repair_context(store, dry_run=True)
        assert res["samples"]
        assert res["samples"][0]["table"] == "episodic_memories"
        assert "脏context0" in res["samples"][0]["raw"]


# ══════════════════════════════════════════════════════════════
# 6. SQLite mmap 可配置（v2.0.17，DSH 定位的 Linux RSS 大头）
# ══════════════════════════════════════════════════════════════


def _actual_mmap(store) -> int:
    return store._conn.execute("PRAGMA mmap_size").fetchone()[0]


class TestMmapConfig:
    def test_config_default_is_zero(self):
        """历史硬编码 256MB → 默认 0（Linux 每实例 811MB 映射的根因）。"""
        assert SOMAConfig().sqlite_mmap_size == 0

    def test_default_store_disables_mmap(self, tmp_path, embedder):
        st = EpisodicStore(tmp_path, embedder=embedder, use_vector_search=True)
        assert _actual_mmap(st) == 0

    @pytest.mark.parametrize("size", [0, 33554432, 268435456])
    def test_configurable(self, tmp_path, embedder, size):
        st = EpisodicStore(
            tmp_path, embedder=embedder, use_vector_search=True, mmap_size=size
        )
        assert _actual_mmap(st) == size

    def test_negative_clamped_to_zero(self, tmp_path, embedder):
        st = EpisodicStore(
            tmp_path, embedder=embedder, use_vector_search=True, mmap_size=-5
        )
        assert _actual_mmap(st) == 0

    def test_memory_core_passes_config_through(self, tmp_path, embedder):
        cfg = SOMAConfig(episodic_persist_dir=tmp_path, sqlite_mmap_size=33554432)
        core = MemoryCore(cfg, embedder=embedder)
        assert _actual_mmap(core.episodic) == 33554432
        core.close() if hasattr(core, "close") else None

    def test_memory_core_default_is_zero(self, tmp_path, embedder):
        cfg = SOMAConfig(episodic_persist_dir=tmp_path)
        core = MemoryCore(cfg, embedder=embedder)
        assert _actual_mmap(core.episodic) == 0
