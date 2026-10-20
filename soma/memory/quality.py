# -*- coding: utf-8 -*-
"""记忆写入的质量门控（2026-10-20）。

## 为什么需要

`remember()` 之前是**什么都记**：'你好'、'好的'、'嗯'、用户重复说的话，
全进库。后果不是"存不下"（库很大），而是**检索时噪音压倒信号** ——
真正重要的事（"用户叫孙岩"）和"好的"在同一个池子里竞争 top_k。

「越用越懂」的前提是**池子里装的是值得记的东西**。

## 门控不是"少记"，是"记对的"

三类过滤，全部**极保守**：

| 类型 | 判据 | 例子 |
|---|---|---|
| 无实质内容 | 去掉标点空白后 < 2 字 | `。。。` / `嗯` / ` ` |
| 纯寒暄 | **精确**匹配白名单 | `你好` / `谢谢` / `好的` |
| 重复 | 和最近的记忆**归一化后相同** | 用户把同一句话说两遍 |

## 三条设计约束（都是踩过的）

1. **不按长度挡** —— "用户叫孙岩"只有 6 个字，比 200 字的寒暄重要得多。
2. **寒暄用精确匹配，不做模糊** —— 模糊匹配会把"你好，我叫孙岩"当成寒暄杀掉。
3. **重复只做归一化全等，不做相似度** —— 相似度阈值低一点就会误杀
   （"用户喜欢 Python" / "用户不喜欢 Java" 很像，但都是真信息）。

## 可关闭

配置 `memory_quality_gate=False` 时不挡（有些接入方要存全量日志）。
**默认开** —— 因为默认不挡的代价（噪音压倒信号）比默认挡（漏记一两句寒暄）大得多。
"""
from __future__ import annotations

import re
from typing import Iterable, Optional, Tuple

#: 纯寒暄 —— **精确**匹配（归一化后）。不做包含匹配。
_GREETINGS = {
    "你好", "您好", "在吗", "在不在", "在么",
    "谢谢", "多谢", "感谢", "谢谢啦", "谢谢你",
    "好的", "好", "行", "可以", "嗯", "嗯嗯", "哦", "噢",
    "收到", "明白", "知道了", "了解",
    "hi", "hello", "hey", "ok", "okay", "thanks", "thankyou",
    "早", "早安", "晚安", "拜拜", "再见",
}

#: 归一化时丢掉的字符：空白 + 各类标点符号
_PUNCT_RE = re.compile(r"[\s\W_]+", re.UNICODE)


def normalize(content: str) -> str:
    """归一化：去空白和标点，转小写。

    用于「是不是寒暄」和「是不是重复」两个判断 —— **两处必须用同一个归一化**，
    否则 '你好！' 和 '你好' 一个被挡一个漏过。
    """
    return _PUNCT_RE.sub("", str(content or "")).lower()


def check(content: str) -> Tuple[bool, str]:
    """这条内容值不值得写入记忆。返回 `(是否丢弃, 原因)`。

    原因会进日志 —— **被挡掉的东西要能查**，否则用户问"我刚才说的你怎么没记住"
    时无从回答。
    """
    raw = str(content or "")
    core = normalize(raw)

    # ① 无实质内容：'。。。' / '嗯' / 空白
    if len(core) < 2:
        return True, "无实质内容"

    # ② 纯寒暄：**精确**匹配（归一化后全等）
    if core in _GREETINGS:
        return True, "纯寒暄"

    return False, ""


def is_duplicate(content: str, recent: Iterable[str]) -> bool:
    """和最近的记忆是否**归一化后完全相同**。

    ⚠️ **只做全等，不做相似度**：
      · "用户喜欢 Python" 和 "用户不喜欢 Java" 字面很像，但都是真信息；
      · 相似度阈值只要松一点，就会把后者当成前者的重复丢掉。

    真正的"重复"是用户把同一句话说了两遍 —— 那种归一化后**一模一样**。
    """
    target = normalize(content)
    if not target:
        return False
    return any(normalize(r) == target for r in (recent or ()))


def should_store(content: str, recent: Optional[Iterable[str]] = None,
                 enabled: bool = True) -> Tuple[bool, str]:
    """对外唯一的入口：要不要把这条写进记忆。

    返回 `(要不要写, 原因)` —— 原因非空时表示**被挡掉了**。
    """
    if not enabled:
        return True, ""
    drop, why = check(content)
    if drop:
        return False, why
    if recent is not None and is_duplicate(content, recent):
        return False, "与最近记忆重复"
    return True, ""


__all__ = ["normalize", "check", "is_duplicate", "should_store"]
