"""v2.0.37: 语义三元组的 kind（fact / relation）。

## 核心不变量

`kind` 只影响**知识注入**，不影响**图扩展**：

    图扩展  expand_query_terms   → 内存 NetworkX，只用节点名，不看 kind
    知识注入 query_by_keywords   → SQL，按 kind 过滤

下游踩过的坑：1.5 万条 wiki 关联图落在 namespace='' 里，include_global
一开就把用户情节记忆挤出 70%，而分数面板看不出来。kind 让它在结构上可过滤。

## 注入自证

  · 去掉 kind 列 / 写入不落 kind        → TestKindRoundtrip 红
  · 注入过滤去掉                        → TestInjectFilter 红
  · 给图扩展也加 kind 过滤              → TestGraphExpansionIgnoresKind 红
  · reclassify 的 dry_run 改动库        → TestReclassify 红
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from soma.base import Focus
from soma.config import SOMAConfig
from soma.memory.core import MemoryCore
from soma.memory.semantic import SemanticStore
from soma.semantic_kind import (
    KIND_FACT,
    KIND_RELATION,
    reclassify_semantic_kind,
    rollback_semantic_kind,
)


@pytest.fixture
def store(tmp_path):
    s = SemanticStore(tmp_path / "sem")
    yield s
    s.close()


@pytest.fixture
def core(tmp_path):
    cfg = SOMAConfig(episodic_persist_dir=tmp_path / "core")
    mc = MemoryCore(cfg)
    yield mc
    mc.close()


def _focus(keywords):
    return Focus(law_id="t", dimension="系统思维", keywords=keywords,
                 weight=1.0, rationale="r")


# ── 1. 往返 ──────────────────────────────────────────────────

class TestKindRoundtrip:
    def test_relation_kind_survives_roundtrip(self, store):
        store.add_triple("文章甲", "关联概念", "经络", kind=KIND_RELATION)

        rows = store.get_all_triples()
        assert len(rows) == 1
        assert rows[0]["kind"] == KIND_RELATION

    def test_default_kind_is_fact(self, store):
        """旧调用不传 kind —— 必须还是 fact（向后兼容）。"""
        store.add_triple("第一性原理", "核心是", "回归本质")

        assert store.get_all_triples()[0]["kind"] == KIND_FACT

    def test_kind_shows_in_query_context(self, store):
        store.add_triple("文章甲", "关联概念", "经络", kind=KIND_RELATION)

        units = store.query_by_keywords(["文章甲"], top_k=5)
        assert units, "没查到"
        assert units[0].context["kind"] == KIND_RELATION


# ── 2. 注入过滤 ──────────────────────────────────────────────

class TestInjectFilter:
    def test_include_kinds_filters_relation(self, store):
        store.add_triple("第一性原理", "核心是", "回归本质", kind=KIND_FACT)
        store.add_triple("系统思维", "关联概念", "整体性", kind=KIND_RELATION)

        facts = store.query_by_keywords(
            ["第一性原理", "系统思维"], top_k=10, include_kinds=("fact",))

        ids = [u.id for u in facts]
        assert any("第一性原理" in i for i in ids), "fact 被误过滤"
        assert not any("系统思维" in i for i in ids), (
            f"relation 边进了注入结果：{ids}")

    def test_include_kinds_none_does_not_filter(self, store):
        """store 层默认不过滤 —— 直接调它的下游行为不变。"""
        store.add_triple("系统思维", "关联概念", "整体性", kind=KIND_RELATION)

        units = store.query_by_keywords(["系统思维"], top_k=10)
        assert len(units) == 1

    def test_empty_kinds_means_no_filter(self, store):
        """空集合不应被理解成「什么都不要」——那是 top_k=0 的语义。"""
        store.add_triple("系统思维", "关联概念", "整体性", kind=KIND_RELATION)

        units = store.query_by_keywords(["系统思维"], top_k=10, include_kinds=())
        assert len(units) == 1


# ── 3. ★ 核心不变量：图扩展不看 kind ─────────────────────────

class TestGraphExpansionIgnoresKind:
    def test_relation_edges_still_expand(self, store):
        """★ relation 边必须继续参与图扩展。

        如果哪天有人为了「更干净」给扩展也加了 kind 过滤，wiki 的关联概念
        就不再参与召回扩展，下游会直接看到召回下降 —— 这条判据盯着它。
        """
        store.add_triple("系统思维", "关联概念", "整体性", kind=KIND_RELATION)

        terms = store.expand_query_terms(["系统思维"], depth=1, max_terms=5)
        assert "整体性" in terms, (
            f"relation 边没参与图扩展，扩展结果：{terms}")

    def test_mixed_kinds_both_expand(self, store):
        store.add_triple("第一性原理", "核心是", "回归本质", kind=KIND_FACT)
        store.add_triple("系统思维", "关联概念", "整体性", kind=KIND_RELATION)

        terms = set(store.expand_query_terms(["第一性原理", "系统思维"],
                                             depth=1, max_terms=10))
        assert "回归本质" in terms
        assert "整体性" in terms


# ── 4. MemoryCore 注入默认只取 fact ──────────────────────────

class TestMemoryCoreInjection:
    def test_query_injects_only_facts(self, core):
        core.remember_semantic("第一性原理", "核心是", "回归本质", kind=KIND_FACT)
        core.remember_semantic("系统思维", "关联概念", "整体性", kind=KIND_RELATION)

        acts = core.query(_focus(["第一性原理", "系统思维"]), top_k=10)
        ids = [a.memory.id for a in acts]

        assert any("第一性原理" in i for i in ids), "fact 没被注入"
        assert not any("系统思维" in i for i in ids), (
            f"relation 边被注入 prompt 了：{ids}")

    def test_facade_passes_semantic_inject_kinds(self, tmp_path):
        """★ SOMA() 门面必须能透传这个配置。

        装包冒烟抓到过一次：配置项加进了 SOMAConfig，但门面构造函数
        没列参数，用户传 `SOMA(semantic_inject_kinds=None)` 直接 TypeError。
        判据锁住门面这一层，避免只测 MemoryCore。
        """
        from soma import SOMA

        s = SOMA(llm="mock", persist_dir=str(tmp_path / "facade"),
                 semantic_inject_kinds=None)
        try:
            assert s._config.semantic_inject_kinds is None
        finally:
            s.close()

        s2 = SOMA(llm="mock", persist_dir=str(tmp_path / "facade2"))
        try:
            assert s2._config.semantic_inject_kinds == ("fact",), (
                "门面默认值没有跟随 SOMAConfig")
        finally:
            s2.close()

    def test_config_none_restores_old_behaviour(self, tmp_path):
        """semantic_inject_kinds=None → 回到 2.0.36（不过滤）。"""
        cfg = SOMAConfig(episodic_persist_dir=tmp_path / "c2",
                         semantic_inject_kinds=None)
        mc = MemoryCore(cfg)
        try:
            mc.remember_semantic("系统思维", "关联概念", "整体性", kind=KIND_RELATION)
            acts = mc.query(_focus(["系统思维"]), top_k=10)
            assert any("系统思维" in a.memory.id for a in acts), (
                "配置为 None 时 relation 仍被过滤了")
        finally:
            mc.close()


# ── 5. 批量重分类 ────────────────────────────────────────────

class TestReclassify:
    @pytest.fixture
    def seeded(self, tmp_path):
        s = SemanticStore(tmp_path / "rc")
        s.add_triple("数字分身", "基于", "命理八字", namespace="")          # 事实
        s.add_triple("文章甲", "关联概念", "经络", namespace="wiki_graph")  # 导航
        s.add_triple("文章乙", "关联人物", "孙岩", namespace="wiki_graph")  # 导航
        yield s
        s.close()

    def test_dry_run_does_not_touch_db(self, seeded):
        out = reclassify_semantic_kind(seeded, dry_run=True)

        assert out["changed"] == 2
        assert out["scanned"] == 3
        # 库没变
        kinds = {r["subject"]: r["kind"] for r in seeded.get_all_triples()}
        assert kinds["文章甲"] == KIND_FACT, "dry_run 改动了库"

    def test_apply_marks_graph_namespace(self, seeded):
        out = reclassify_semantic_kind(seeded, dry_run=False)

        assert out["applied"] == 2
        assert out["backup_path"] and Path(out["backup_path"]).exists()

        kinds = {r["subject"]: r["kind"] for r in seeded.get_all_triples()}
        assert kinds["文章甲"] == KIND_RELATION
        assert kinds["文章乙"] == KIND_RELATION
        assert kinds["数字分身"] == KIND_FACT, "非 graph namespace 被误改"

    def test_rollback_restores(self, seeded):
        out = reclassify_semantic_kind(seeded, dry_run=False)
        rollback_semantic_kind(seeded, out["backup_path"])

        kinds = {r["subject"]: r["kind"] for r in seeded.get_all_triples()}
        assert kinds["文章甲"] == KIND_FACT
        assert kinds["文章乙"] == KIND_FACT

    def test_predicate_rule_cleans_global_nav_edges(self, tmp_path):
        """`''` 里混进的导航边，靠 predicate 规则清理。"""
        s = SemanticStore(tmp_path / "rc2")
        try:
            s.add_triple("文章甲", "关联概念", "经络", namespace="")
            s.add_triple("数字分身", "基于", "命理八字", namespace="")

            out = reclassify_semantic_kind(
                s, dry_run=False, predicate_relation=["关联"])

            assert out["applied"] == 1
            kinds = {r["subject"]: r["kind"] for r in s.get_all_triples()}
            assert kinds["文章甲"] == KIND_RELATION
            assert kinds["数字分身"] == KIND_FACT
        finally:
            s.close()

    def test_backup_failure_aborts(self, seeded, tmp_path):
        """备份写不进去时不能继续改库。"""
        blocker = tmp_path / "blocked"
        blocker.write_text("not a dir", encoding="utf-8")

        out = reclassify_semantic_kind(seeded, dry_run=False,
                                       backup_dir=str(blocker))

        assert "error" in out
        kinds = {r["subject"]: r["kind"] for r in seeded.get_all_triples()}
        assert kinds["文章甲"] == KIND_FACT, "备份失败却改了库"
