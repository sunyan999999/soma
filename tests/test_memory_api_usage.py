# -*- coding: utf-8 -*-
"""用户可见记忆管理接口 + 真实 token 用量（v2.0.19）。

背景（架构规划 §4.1「现在必须定」）：接入方要一个稳定的只读记忆接口和一个
能编辑/删除的入口 —— 此前只能穿透 soma._agent.memory.episodic._conn 拼裸 SQL。
三条理由：裸 SQL 没有作用域（多用户互相可见）、把表结构变成对外契约、
改内容不重算 hash 与向量。

覆盖：
- 作用域在 SQL 生效：跨用户读写一律「查不到」
- 键集游标分页不漏不重；跨排序维度复用游标被拒
- update 连带重算 content_hash 与向量；nature 非法值报错
- delete 走归档、可 restore；恢复后 nature 与向量都回来
- 归档表不存在（新库）时返回空而不是报错
- export 的列表 / NDJSON 文件两种模式
- usage：provider 真实值原样记账；缺 usage 时估算兜底并标 estimated
- 缓存命中不重复计费；并发调用按 user 归属不串
"""
import json
import threading

import numpy as np
import pytest

from soma import SOMA
from soma.usage import TokenUsage, UsageRecorder, estimate_tokens, extract_usage


class FakeEmbedder:
    """确定性假嵌入器 —— 让向量路径可在测试里跑，不下载 66MB 模型。"""

    def __init__(self, dim: int = 16):
        self.dim = dim
        self.calls = 0

    @property
    def dimension(self):
        return self.dim

    def encode(self, text):
        self.calls += 1
        v = np.zeros(self.dim, dtype=np.float32)
        v[hash(text) % self.dim] = 1.0
        return v

    def encode_batch(self, texts):
        return np.vstack([self.encode(t) for t in texts])


@pytest.fixture
def soma(tmp_path):
    s = SOMA(persist_dir=str(tmp_path / "data"), use_vector_search=False,
             recall_threshold=0.01)
    yield s
    s.close()


@pytest.fixture
def soma_vec(tmp_path):
    """开向量检索的实例（注入假 embedder）。"""
    emb = FakeEmbedder()
    s = SOMA(persist_dir=str(tmp_path / "vec"), use_vector_search=True,
             embedder=emb, recall_threshold=0.01)
    s._fake_embedder = emb
    yield s
    s.close()


def _seed(soma):
    """两个用户各几条记忆，返回 id 字典"""
    return {
        "u1_state": soma.remember("用户长期失眠，入睡困难", importance=0.9,
                                   user_id="u1", nature="state"),
        "u1_fact": soma.remember("用户会写 Python", importance=0.6,
                                  user_id="u1", nature="fact"),
        "u2": soma.remember("另一个用户的秘密", importance=0.5, user_id="u2"),
    }


class TestScope:
    """作用域必须落在 SQL 层，而不是查完再筛"""

    def test_list_scoped_to_user(self, soma):
        _seed(soma)
        items = soma.memories.list(user_id="u1", limit=10)["items"]
        assert {i["user_id"] for i in items} == {"u1"}
        assert len(items) == 2

    def test_empty_user_id_means_all(self, soma):
        """单租户常态：不传 user_id = 不限（与 query_by_filters 同一约定）"""
        _seed(soma)
        assert soma.memories.list(limit=10)["count"] == 3

    def test_get_other_user_hidden(self, soma):
        ids = _seed(soma)
        assert soma.memories.get(ids["u1_state"], user_id="u2") is None

    def test_update_other_user_not_found(self, soma):
        """越权改写返回 not_found（不是 forbidden —— 不泄露 id 归属）"""
        ids = _seed(soma)
        out = soma.memories.update(ids["u1_state"], user_id="u2",
                                   content="恶意改写")
        assert out["ok"] is False and out["reason"] == "not_found"
        assert "长期失眠" in soma.memories.get(ids["u1_state"])["content"]

    def test_delete_other_user_not_found(self, soma):
        ids = _seed(soma)
        assert soma.memories.delete(ids["u1_state"], user_id="u2")["reason"] == "not_found"

    def test_export_scoped(self, soma):
        _seed(soma)
        assert soma.memories.export_memories(user_id="u2")["count"] == 1
        assert soma.memories.export_memories(user_id="u1")["count"] == 2


class TestPagination:
    def test_cursor_no_dup_no_skip(self, soma):
        _seed(soma)
        for i in range(3):
            soma.remember("补充记忆 %d 号" % i, user_id="u1")
        seen, cursor = [], None
        for _ in range(20):
            page = soma.memories.list(user_id="u1", limit=2, after=cursor or "")
            seen.extend(i["id"] for i in page["items"])
            cursor = page["next_cursor"]
            if not cursor:
                break
        assert len(seen) == len(set(seen)), "翻页出现重复"
        assert len(seen) == 5, "翻页条数不对: %d" % len(seen)

    def test_order_by_importance(self, soma):
        _seed(soma)
        page = soma.memories.list(user_id="u1", order_by="importance", limit=2)
        assert [i["importance"] for i in page["items"]] == [0.9, 0.6]

    def test_cursor_not_reusable_across_orders(self, soma):
        _seed(soma)
        page = soma.memories.list(user_id="u1", order_by="importance", limit=1)
        assert page["next_cursor"]
        with pytest.raises(ValueError):
            soma.memories.list(user_id="u1", limit=1, after=page["next_cursor"])

    def test_garbage_cursor_raises(self, soma):
        _seed(soma)
        with pytest.raises(ValueError):
            soma.memories.list(limit=1, after="not-a-cursor")

    def test_limit_capped(self, soma):
        """超上限不报错，收敛到 MAX_PAGE"""
        _seed(soma)
        page = soma.memories.list(limit=10 ** 6)
        assert page["count"] <= 1000


class TestUpdate:
    def test_content_rehashes(self, soma):
        """内容变了 content_hash 必须跟着变 —— 否则去重判断失准"""
        ids = _seed(soma)
        ep = soma._agent.memory.episodic
        before = ep.get(ids["u1_state"]).content
        row0 = ep._conn.execute(
            "SELECT content_hash FROM episodic_memories WHERE id=?",
            (ids["u1_state"],)).fetchone()["content_hash"]
        out = soma.memories.update(ids["u1_state"], content="用户最近睡眠改善了")
        assert out["ok"] and out["memory"]["content"] == "用户最近睡眠改善了"
        row1 = ep._conn.execute(
            "SELECT content_hash FROM episodic_memories WHERE id=?",
            (ids["u1_state"],)).fetchone()["content_hash"]
        assert row0 != row1, "content_hash 没重算"
        assert before != out["memory"]["content"]

    def test_update_reindexes_vector(self, soma_vec):
        """裸 SQL 改内容最容易漏的就是这步：向量必须重算，否则语义搜索还返回旧内容"""
        mid = soma_vec.remember("用户长期失眠", user_id="u1", importance=0.9)
        ep = soma_vec._agent.memory.episodic
        calls_before = soma_vec._fake_embedder.calls
        assert ep.count_indexed() == 1
        soma_vec.memories.update(mid, content="用户最近睡眠很好")
        assert soma_vec._fake_embedder.calls > calls_before, "没有重新编码"
        assert ep.count_indexed() == 1

    def test_importance_clamped(self, soma):
        ids = _seed(soma)
        soma.memories.update(ids["u1_fact"], importance=5.0)
        assert soma.memories.get(ids["u1_fact"])["importance"] == 1.0

    def test_nature_validated(self, soma):
        ids = _seed(soma)
        with pytest.raises(ValueError):
            soma.memories.update(ids["u1_fact"], nature="nonsense")

    def test_empty_update_rejected(self, soma):
        ids = _seed(soma)
        with pytest.raises(ValueError):
            soma.memories.update(ids["u1_fact"])

    def test_update_nature_and_context(self, soma):
        ids = _seed(soma)
        out = soma.memories.update(ids["u1_state"], nature="fact",
                                   context={"domain": "健康"})
        assert out["memory"]["nature"] == "fact"
        assert out["memory"]["context"]["domain"] == "健康"

    def test_update_missing_id(self, soma):
        assert soma.memories.update("nope", content="x")["reason"] == "not_found"


class TestDeleteRestore:
    def test_delete_archives_by_default(self, soma):
        ids = _seed(soma)
        out = soma.memories.delete(ids["u1_state"], user_id="u1")
        assert out == {"ok": True, "archived": True}
        assert soma.memories.get(ids["u1_state"]) is None
        arc = soma.memories.archived(user_id="u1")
        assert len(arc) == 1 and arc[0]["archive_reason"] == "user_delete"

    def test_restore_brings_back_nature(self, soma):
        """回归：归档表早期没有 nature 列，恢复后 state 会退化成 event，
        时效窗口就此失效"""
        ids = _seed(soma)
        soma.memories.delete(ids["u1_state"], user_id="u1")
        assert soma.memories.restore(ids["u1_state"], user_id="u1")["ok"]
        back = soma.memories.get(ids["u1_state"])
        assert back and back["nature"] == "state"

    def test_restore_reindexes_vector(self, soma_vec):
        """回归：删除时清了向量，恢复若只回插主表 —— 这条记忆再也召不回"""
        mid = soma_vec.remember("用户长期失眠", user_id="u1")
        ep = soma_vec._agent.memory.episodic
        soma_vec.memories.delete(mid, user_id="u1")
        assert ep.count_indexed() == 0
        assert soma_vec.memories.restore(mid, user_id="u1")["ok"]
        assert ep.count_indexed() == 1
        row = ep._conn.execute("SELECT vector IS NULL AS v FROM episodic_memories WHERE id=?",
                                (mid,)).fetchone()
        assert row and not row["v"]

    def test_hard_delete_not_restorable(self, soma):
        ids = _seed(soma)
        out = soma.memories.delete(ids["u1_fact"], hard=True)
        assert out == {"ok": True, "archived": False}
        assert soma.memories.restore(ids["u1_fact"])["reason"] == "not_archived"

    def test_archived_on_fresh_store_returns_empty(self, soma):
        """回归：新库还没跑过遗忘时归档表不存在，应返回空而不是报错"""
        assert soma.memories.archived() == []
        assert soma.memories.restore("whatever")["reason"] == "not_archived"

    def test_restore_other_user_denied(self, soma):
        ids = _seed(soma)
        soma.memories.delete(ids["u1_state"], user_id="u1")
        assert soma.memories.restore(ids["u1_state"], user_id="u2")["reason"] == "not_found"


class TestExport:
    def test_export_as_list(self, soma):
        _seed(soma)
        out = soma.memories.export_memories(user_id="u1")
        assert out["format"] == "list" and out["count"] == 2
        assert len(out["items"]) == 2

    def test_export_ndjson_file(self, soma, tmp_path):
        _seed(soma)
        target = tmp_path / "dump.jsonl"
        out = soma.memories.export_memories(user_id="u1", path=str(target))
        assert out["format"] == "ndjson-file" and out["count"] == 2
        lines = target.read_text(encoding="utf-8").strip().split(chr(10))
        assert len(lines) == 2
        for line in lines:
            rec = json.loads(line)
            assert rec["user_id"] == "u1"
            assert "content" in rec and "timestamp" in rec

    def test_export_respects_limit(self, soma):
        _seed(soma)
        assert soma.memories.export_memories(limit=1)["count"] == 1

    def test_iter_memories_lazy(self, soma):
        """生成器分页 —— 不能一次性把整库读进内存"""
        _seed(soma)
        got = [i["id"] for i in soma.memories.iter_memories(batch=1)]
        assert len(got) == 3 and len(set(got)) == 3


class TestUsageHelpers:
    def test_extract_from_object(self):
        resp = type("R", (), {})()
        resp.model = "glm-4"
        resp.usage = type("U", (), {"prompt_tokens": 10,
                                     "completion_tokens": 5,
                                     "total_tokens": 15})()
        u = extract_usage(resp)
        assert (u.prompt_tokens, u.completion_tokens, u.total_tokens,
                u.model, u.estimated) == (10, 5, 15, "glm-4", False)

    def test_extract_from_dict(self):
        resp = {"model": "x", "usage": {"prompt_tokens": 3,
                                         "completion_tokens": 2,
                                         "total_tokens": 5}}
        assert extract_usage(resp).total_tokens == 5

    def test_missing_usage_returns_none(self):
        resp = type("R", (), {"usage": None, "model": ""})()
        assert extract_usage(resp) is None

    def test_all_zero_treated_as_missing(self):
        """provider 回全 0 不等于「这次没花钱」，应交给估算兜底并标注"""
        resp = {"model": "x", "usage": {"prompt_tokens": 0,
                                         "completion_tokens": 0,
                                         "total_tokens": 0}}
        assert extract_usage(resp) is None
        assert extract_usage(None) is None

    def test_estimate_tokens_cjk_and_ascii(self):
        assert estimate_tokens("") == 0
        assert estimate_tokens("失眠很严重") == 5
        assert estimate_tokens("a" * 40) == 10

    def test_to_dict_roundtrip(self):
        d = TokenUsage(prompt_tokens=1, completion_tokens=2, total_tokens=3,
                        model="m", user_id="u", purpose="respond",
                        estimated=True).to_dict()
        assert d["estimated"] is True and d["model"] == "m"
        assert {"prompt_tokens", "completion_tokens", "user_id"} <= set(d)


class TestUsageRecorder:
    def test_accumulates_and_groups_by_model(self):
        rec = UsageRecorder()
        rec.record(TokenUsage(prompt_tokens=10, completion_tokens=5, model="a"))
        rec.record(TokenUsage(prompt_tokens=1, completion_tokens=1, model="b",
                              estimated=True))
        snap = rec.snapshot()
        assert snap["calls"] == 2
        assert snap["total_tokens"] == 17
        assert set(snap["by_model"]) == {"a", "b"}
        assert snap["estimated_calls"] == 1

    def test_total_backfilled_from_parts(self):
        rec = UsageRecorder()
        rec.record(TokenUsage(prompt_tokens=7, completion_tokens=3))
        assert rec.snapshot()["total_tokens"] == 10

    def test_recent_order_and_limit(self):
        rec = UsageRecorder()
        for i in range(5):
            rec.record(TokenUsage(prompt_tokens=i, model="m"))
        recent = rec.recent(3)
        assert len(recent) == 3
        assert recent[0]["prompt_tokens"] == 4, "应最新在前"

    def test_recent_buffer_bounded(self):
        rec = UsageRecorder()
        for i in range(rec.RECENT_LIMIT + 50):
            rec.record(TokenUsage(prompt_tokens=i, model="m"))
        assert len(rec.recent(10 ** 4)) == rec.RECENT_LIMIT
        assert rec.snapshot()["calls"] == rec.RECENT_LIMIT + 50, "累计不应被截断"

    def test_callback_receives_usage(self):
        rec = UsageRecorder()
        got = []
        rec.on_usage(lambda u: got.append((u.user_id, u.total_tokens)))
        rec.record(TokenUsage(prompt_tokens=2, completion_tokens=3, user_id="zed"))
        assert got == [("zed", 5)]

    def test_bad_callback_does_not_break_recording(self):
        rec = UsageRecorder()
        def boom(u):
            raise RuntimeError("接入方回调炸了")
        rec.on_usage(boom)
        rec.record(TokenUsage(prompt_tokens=1, model="m"))
        assert rec.snapshot()["calls"] == 1

    def test_reset(self):
        rec = UsageRecorder()
        rec.record(TokenUsage(prompt_tokens=9, model="m"))
        rec.reset()
        assert rec.snapshot()["calls"] == 0 and rec.recent(5) == []

    def test_threadsafe_concurrent_records(self):
        """多专家编排下 LLM 调用来自多线程，计数不能丢"""
        rec = UsageRecorder()
        def worker():
            for _ in range(20):
                rec.record(TokenUsage(prompt_tokens=1, completion_tokens=1,
                                      model="m"))
        ts = [threading.Thread(target=worker) for _ in range(8)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        assert rec.snapshot()["calls"] == 160
        assert rec.snapshot()["total_tokens"] == 320


class TestFacadeUsage:
    """门面 → 真实 provider usage 的端到端"""

    def _fake_completion(self, usage=None, model="gptest", text="回答"):
        def _call(**kwargs):
            resp = type("R", (), {})()
            resp.model = model
            resp.usage = (type("U", (), usage)() if usage else None)
            resp.choices = [type("C", (), {
                "message": type("M", (), {"content": text})()})()]
            return resp
        return _call

    def test_provider_usage_recorded(self, soma, monkeypatch):
        import soma.agent as agent_mod
        monkeypatch.setattr(agent_mod, "completion", self._fake_completion(
            {"prompt_tokens": 111, "completion_tokens": 22, "total_tokens": 133}))
        soma._agent.config.llm_model = "gptest"
        soma._agent._call_llm("请分析这个问题", user_id="alice")
        snap = soma.token_usage
        assert snap["calls"] == 1 and snap["total_tokens"] == 133
        assert snap["estimated_calls"] == 0
        rec = soma.recent_usage(1)[0]
        assert rec["user_id"] == "alice" and rec["model"] == "gptest"
        assert rec["purpose"] == "respond" and rec["estimated"] is False

    def test_cache_hit_not_billed_twice(self, soma, monkeypatch):
        """命中缓存 = 没有真实请求 = 不产生 token"""
        import soma.agent as agent_mod
        calls = []
        def counting(**kwargs):
            calls.append(1)
            return self._fake_completion(
                {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10}
            )(**kwargs)
        monkeypatch.setattr(agent_mod, "completion", counting)
        soma._agent.config.llm_model = "gptest"
        soma._agent._call_llm("同一个问题", user_id="alice")
        soma._agent._call_llm("同一个问题", user_id="alice")   # 命中缓存
        assert len(calls) == 1
        assert soma.token_usage["calls"] == 1

    def test_missing_usage_falls_back_to_estimate(self, soma, monkeypatch):
        """provider 不给 usage 也要有数，但必须标 estimated=True（不能拿去计费）"""
        import soma.agent as agent_mod
        monkeypatch.setattr(agent_mod, "completion",
                            self._fake_completion(None, text="x" * 400))
        soma._agent.config.llm_model = "gptest"
        soma._agent._call_llm("问题", user_id="bob")
        snap = soma.token_usage
        assert snap["calls"] == 1 and snap["estimated_calls"] == 1
        rec = soma.recent_usage(1)[0]
        assert rec["estimated"] is True and rec["user_id"] == "bob"

    def test_user_attributed_per_thread(self, soma, monkeypatch):
        """并发下用量不能记到别人账上（thread-local 上下文）"""
        import soma.agent as agent_mod
        monkeypatch.setattr(agent_mod, "completion", self._fake_completion(
            {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}))
        soma._agent.config.llm_model = "gptest"
        soma._agent.config.llm_cache_ttl = 0      # 关缓存，确保每次都真调
        def worker(i):
            soma._agent._call_llm("并发问题 %d" % i, user_id="user%d" % i)
        ts = [threading.Thread(target=worker, args=(i,)) for i in range(6)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        users = {r["user_id"] for r in soma.recent_usage(20)}
        assert users == {"user%d" % i for i in range(6)}

    def test_on_usage_via_facade(self, soma, monkeypatch):
        import soma.agent as agent_mod
        monkeypatch.setattr(agent_mod, "completion", self._fake_completion(
            {"prompt_tokens": 4, "completion_tokens": 6, "total_tokens": 10}))
        soma._agent.config.llm_model = "gptest"
        got = []
        soma.usage.on_usage(lambda u: got.append(u.to_dict()))
        soma._agent._call_llm("问题", user_id="q")
        assert len(got) == 1 and got[0]["total_tokens"] == 10

    def test_snapshot_shape_on_fresh_instance(self, soma):
        snap = soma.token_usage
        assert snap["calls"] == 0 and snap["by_model"] == {}
        assert "estimated_calls" in snap


class TestCliWiring:
    """子命令注册与参数解析（不建实例，照 test_cli.py 的路子）"""

    def test_commands_registered(self):
        from soma import cli
        p = cli.build_parser()
        for cmd in ("memories", "forget", "export", "usage"):
            assert cmd in p.parse_args.__self__._subparsers._group_actions[0].choices

    def test_memories_args_parse(self):
        from soma import cli
        p = cli.build_parser()
        args = p.parse_args(["memories", "--project", "SOMA", "--user-id", "u1",
                             "--order", "importance", "-n", "5"])
        assert args.project == "SOMA" and args.user_id == "u1"
        assert args.order == "importance" and args.limit == 5

    def test_forget_args_parse(self):
        from soma import cli
        p = cli.build_parser()
        args = p.parse_args(["forget", "abc123", "--hard", "--user-id", "u1"])
        assert args.id == "abc123" and args.hard is True
        args2 = p.parse_args(["forget", "--restore", "abc123"])
        assert args2.restore == "abc123" and args2.id == ""

    def test_export_and_usage_args_parse(self):
        from soma import cli
        p = cli.build_parser()
        args = p.parse_args(["export", "--user-id", "u1", "-o", "d.jsonl", "-n", "10"])
        assert args.output == "d.jsonl" and args.limit == 10
        args2 = p.parse_args(["usage", "--recent", "5"])
        assert args2.recent == 5
