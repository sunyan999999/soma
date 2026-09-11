"""门面透传测试（v2.0.15）

背景（DSH 协作反馈，2026-08-29）：SOMA 的记忆时间感知能力只打通到 agent 层，
顶层门面 SOMA 没跟上 —— 接入方按文档写 `get_soma().query_memory(q, max_age_days=30)`
会直接 TypeError；`SOMA.remember` 也没有 nature 参数，接入方只能绕过门面。

修复：门面补齐两处透传，四层（门面→agent→memory→episodic）彻底打通。

覆盖：
- SOMA.query_memory(max_age_days=) 不抛 TypeError 且真截断远期记忆
- SOMA.remember(nature=) 存入后查询返回同一 nature
- remember_code 默认 nature=fact（代码/技能长期有效）
- remember_image / remember_table 接受 nature
"""
import time
from pathlib import Path

import pytest

from soma import SOMA


@pytest.fixture
def soma(tmp_path):
    """轻量门面实例：关向量检索，避免加载嵌入模型"""
    s = SOMA(persist_dir=str(tmp_path / "soma_data"),
             use_vector_search=False, recall_threshold=0.01)
    yield s
    s.close()


def _backdate(soma, keyword, days: float):
    """把最近一条匹配记忆的时间改到 days 天前"""
    ep = soma._agent.memory.episodic
    mems = ep.query_by_keywords([keyword], top_k=10)
    if not mems:
        return
    ep._conn.execute("UPDATE episodic_memories SET timestamp=? WHERE id=?",
                     (time.time() - days * 86400, mems[0].id))
    ep._conn.commit()


class TestFacadeMaxAgeDays:
    def test_query_memory_accepts_max_age_days(self, soma):
        """DSH 生产调用形式不抛 TypeError（修复前必现）"""
        soma.remember("用户最近睡眠不错", {"domain": "健康"})
        results = soma.query_memory("睡眠", top_k=5, max_age_days=30)
        assert results, "应召回记忆"
        for item in results:
            assert item["age_days"] <= 30

    def test_max_age_days_truncates_end_to_end(self, soma):
        """门面层 max_age_days 真的硬截断远期记忆"""
        soma.remember("用户睡眠不好经常失眠", {"domain": "健康"})
        soma.remember("用户最近睡眠不错", {"domain": "健康"})
        _backdate(soma, "失眠", 40)
        results = soma.query_memory("睡眠", top_k=5, max_age_days=30)
        assert results
        for item in results:
            assert item["age_days"] <= 30, \
                f"含远期记忆: {item['content_preview'][:20]}"

    def test_default_no_window(self, soma):
        """不传 max_age_days 时行为不变（向后兼容）"""
        soma.remember("用户最近睡眠不错", {"domain": "健康"})
        results = soma.query_memory("睡眠", top_k=5)
        assert results
        assert "age_days" in results[0]


class TestFacadeNature:
    def test_remember_nature_roundtrip(self, soma):
        """门面 remember(nature) 存入 → 查询返回同一 nature"""
        soma.remember("用户最近睡眠不错", {"domain": "健康"}, nature="state")
        r = soma.query_memory("睡眠", top_k=3)
        assert r
        assert all(x["nature"] == "state" for x in r), f"nature 应为 state: {r}"

    def test_remember_default_event(self, soma):
        """不带 nature 默认 event（向后兼容）"""
        soma.remember("用户昨天开会", {"domain": "工作"})
        r = soma.query_memory("开会", top_k=3)
        assert r and r[0]["nature"] == "event"
        assert "is_stale" in r[0]

    def test_remember_code_defaults_fact(self, soma):
        """remember_code 默认 nature=fact（代码技能长期有效，不随时间过时）"""
        soma.remember_code("def add(a, b):\n    return a + b",
                           file_path="calc.py")
        r = soma.query_memory("add", top_k=3)
        assert r
        assert all(x["nature"] == "fact" for x in r), \
            f"代码记忆应为 fact: {[x['nature'] for x in r]}"

    def test_remember_code_nature_overridable(self, soma):
        """remember_code 的 nature 可显式覆盖"""
        soma.remember_code("def render_report(data):\n    return str(data)",
                           file_path="report.py", nature="event")
        r = soma.query_memory("render_report", top_k=3)
        assert r and r[0]["nature"] == "event"

    def test_remember_image_accepts_nature(self, soma):
        """remember_image 透传 nature"""
        out = soma.remember_image(description="一张白板照片，写着排期",
                                  use_ocr=False, nature="fact")
        assert out["memory_id"]
        r = soma.query_memory("白板", top_k=3)
        assert r and r[0]["nature"] == "fact"

    def test_remember_table_accepts_nature(self, soma):
        """remember_table 透传 nature"""
        out = soma.remember_table(markdown_table="| 月份 | 收入 |\n|---|---|\n| 1月 | 100 |",
                                  title="季度收入", nature="fact")
        assert out["memory_id"]
        r = soma.query_memory("收入", top_k=3)
        assert r and r[0]["nature"] == "fact"
