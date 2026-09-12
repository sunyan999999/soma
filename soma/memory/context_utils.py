"""context 字段的类型安全处理（v2.0.17）。

背景：``context_json`` 列历史上可能存入非 JSON 对象的裸值 —— 调用方把字符串
直接传给 ``remember(context=...)`` 时，``json.dumps("文本")`` 产出的是**合法
但非对象**的 JSON，读回来就是一个 str。检索热路径上的
``mem.context["_vector_score"] = score`` 一旦拿到 str 就抛 TypeError，
**全库两万多条里只要有 1 条脏数据，整次全库检索就会崩**
（DSH 2026-09-12 在官方基准上撞到，26,872 条里 1 条 str 导致 query_by_vector 崩溃）。

本模块提供读写双向规范化：读出来的 context 恒为 dict，写进去的也恒为 JSON 对象，
且原始数据不丢弃 —— 规范化不了的值收进 ``_raw`` 键保留原文。
"""

import json
import logging
from typing import Any, Dict

_log = logging.getLogger("soma.memory.context")


def parse_context(raw: Any) -> Dict[str, Any]:
    """把数据库里的 context_json 安全解析为 dict（v2.0.17）。

    任何异常输入都不会抛错，最差情况返回 ``{"_raw": <原值>}``：

    - None / 空串            → {}
    - dict                   → 原样返回
    - 合法 JSON 对象文本     → 解析后的 dict
    - 合法 JSON 但非对象     → {"_raw": <解析结果>}   （字符串/数组/数字）
    - 非法 JSON 文本         → {"_raw": <原文本>}     （裸字符串脏数据）
    """
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, (bytes, bytearray, memoryview)):
        raw = bytes(raw).decode("utf-8", errors="replace")

    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return {}
        try:
            value = json.loads(text)
        except (ValueError, TypeError):
            _log.warning(
                "context_json 不是合法 JSON，按原文本收进 _raw 保留: %r", raw[:200]
            )
            return {"_raw": raw}
    else:
        value = raw

    if isinstance(value, dict):
        return value

    _log.warning(
        "context 解析结果不是对象（%s），收进 _raw 保留: %r",
        type(value).__name__,
        value,
    )
    return {"_raw": value}


def normalize_context(ctx: Any) -> Dict[str, Any]:
    """把待写入的 context 规范化为 dict（v2.0.17）。

    非 dict（典型是调用方误传字符串）会被包成 ``{"_raw": <原值>}`` 并告警，
    保证入库的一定是 JSON 对象，从源头堵住脏数据。
    """
    if ctx is None:
        return {}
    if isinstance(ctx, dict):
        return ctx

    _log.warning(
        "remember(context=...) 收到非 dict（%s），已包成 {'_raw': ...} 存入。"
        "请改传 dict（如 {'source': '...'}）。原值: %r",
        type(ctx).__name__,
        ctx,
    )
    return {"_raw": ctx}
