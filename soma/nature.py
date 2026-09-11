"""记忆业务性质（nature）分类规则 + 批量重分类工具 — v2.0.15

背景
----
v2.0.14 引入 nature（state/fact/event）区分记忆时效强弱，但存量记忆全是默认的
event，接入方需要按业务性质回填。零熵智库（DSH）当时只能裸 SQL UPDATE 硬来 ——
这里把那条路沉淀成内置能力：规则可配、dry_run 先预览、备份可回滚、零 LLM 依赖。

三层时效机制（务必分清，别误判）
--------------------------------
1. **近因衰减**（主防线）：`exp(-days/7)`，半衰期 7 天。记忆超过 ~30 天后权重
   已降到 2% 以下，**根本过不了激活阈值**，压根不会被召回。
2. **max_age_days**（硬截断）：查询时按时间窗口直接过滤，用于「我只要最近的」。
3. **is_stale**（第二道保险）：只对 nature=state 生效。因为 (1) 已经让远期状态
   记不到，"过期状态" 主要出现在 **30 天内但性质已变** 的场景 —— 此时
   explain_activation 返回 is_stale=True，注入层应提示「这是 N 天前的状态，
   可能已变化」。**它不是主防线，别指望它拦住所有远期记忆。**

用法::

    from soma import SOMA
    soma = SOMA()
    # 先预览（默认 dry_run）
    print(soma.reclassify_nature())
    # 确认无误后落盘（自动备份）
    print(soma.reclassify_nature(dry_run=False))
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

NATURE_STATE = "state"
NATURE_FACT = "fact"
NATURE_EVENT = "event"
VALID_NATURES = (NATURE_STATE, NATURE_FACT, NATURE_EVENT)

# 状态类强特征词 —— 时效强：健康状况 / 情绪 / 处境，会随时间变化
# 刻意选具体词，避免误伤（如「会」这种单字不进表）
DEFAULT_STATE_KEYWORDS: tuple = (
    "失眠", "睡不着", "睡不好", "睡眠", "熬夜", "头疼", "头痛", "头晕",
    "焦虑", "心情", "情绪", "压力大", "烦躁", "紧张", "抑郁", "疲惫",
    "疲劳", "没精神", "感冒", "发烧", "咳嗽", "过敏", "血压", "血糖",
    "体重", "胃口", "食欲", "腰疼", "背疼", "身体不适", "状态不好",
    "最近在", "目前在", "这周", "今天",
)

# 事实技能类特征词 —— 长期有效：技能 / 偏好 / 身份 / 知识
DEFAULT_FACT_KEYWORDS: tuple = (
    "用户会", "用户是", "用户喜欢", "用户偏好", "偏好", "擅长", "习惯于",
    "职业是", "从事", "毕业于", "掌握", "熟悉", "精通", "原理", "定义",
    "方法论", "最佳实践", "规范", "架构", "公式", "定理", "定律",
)

# 长文档视为知识（长期有效）—— 零熵智库生产回填验证过的阈值
DEFAULT_FACT_MIN_LEN = 300

# 这些来源的记忆视为知识（长期有效）
DEFAULT_FACT_SOURCES: tuple = ("wiki", "knowledge", "external", "doc", "import")


class NatureClassifier:
    """规则化 nature 分类器（零 LLM 依赖，可完全自定义规则）。"""

    def __init__(
        self,
        state_keywords: Optional[Iterable[str]] = None,
        fact_keywords: Optional[Iterable[str]] = None,
        fact_min_len: int = DEFAULT_FACT_MIN_LEN,
        fact_sources: Optional[Iterable[str]] = None,
    ):
        self.state_keywords = tuple(state_keywords) if state_keywords is not None \
            else DEFAULT_STATE_KEYWORDS
        self.fact_keywords = tuple(fact_keywords) if fact_keywords is not None \
            else DEFAULT_FACT_KEYWORDS
        self.fact_min_len = fact_min_len
        self.fact_sources = tuple(fact_sources) if fact_sources is not None \
            else DEFAULT_FACT_SOURCES

    def classify(self, content: str, context: Optional[dict] = None) -> str:
        """判定一条记忆的 nature。

        优先级：状态词 > 知识来源/长文档 > 事实词 > event。
        状态词优先是因为它最具体 —— 「用户最近在减肥」既是状态也有偏好味道，
        但时效性才是它最要紧的属性。
        """
        text = content or ""
        ctx = context or {}

        # 1. 状态类强特征（时效强，优先）
        for kw in self.state_keywords:
            if kw and kw in text:
                return NATURE_STATE

        # 2. 知识来源 → 事实类
        src = str(ctx.get("source", "") or ctx.get("origin", "")).lower()
        if src and any(s in src for s in self.fact_sources):
            return NATURE_FACT

        # 3. 长文档 → 知识
        if self.fact_min_len and len(text) > self.fact_min_len:
            return NATURE_FACT

        # 4. 事实技能词
        for kw in self.fact_keywords:
            if kw and kw in text:
                return NATURE_FACT

        return NATURE_EVENT

    def describe(self) -> dict:
        """规则概览（便于调用方自查当前规则）"""
        return {
            "state_keywords": list(self.state_keywords),
            "fact_keywords": list(self.fact_keywords),
            "fact_min_len": self.fact_min_len,
            "fact_sources": list(self.fact_sources),
        }


def reclassify_nature(
    store,
    classifier: Optional[NatureClassifier] = None,
    dry_run: bool = True,
    backup_dir: Optional[str] = None,
    user_id: str = "",
    only_nature: str = NATURE_EVENT,
    limit: Optional[int] = None,
    batch_size: int = 500,
) -> Dict[str, Any]:
    """批量重分类存量记忆的 nature。

    安全默认：**dry_run=True 只预览不改**；落盘时自动写备份（可 rollback_nature 回滚）。
    默认只处理 nature='event' 的（不覆盖已分类/人工修正过的记忆）。

    Args:
        store: EpisodicStore（需有 ._conn）
        classifier: 自定义分类器，默认 NatureClassifier()
        dry_run: True 只统计不改库
        backup_dir: 备份目录，默认库同目录下 nature_backups/
        user_id: 只处理某用户（空 = 全部）
        only_nature: 只重分类该性质的历史值（默认 'event'；None = 全部）
        limit: 最多处理多少条（None = 不限）
        batch_size: 每批提交条数

    Returns:
        {dry_run, scanned, changed, by_nature, unchanged, backup_path, elapsed_ms}
    """
    clf = classifier or NatureClassifier()
    conn = getattr(store, "_conn", store)

    sql = "SELECT id, content, context_json, nature FROM episodic_memories WHERE 1=1"
    params: List[Any] = []
    if only_nature:
        sql += " AND nature = ?"
        params.append(only_nature)
    if user_id:
        sql += " AND user_id = ?"
        params.append(user_id)
    sql += " ORDER BY timestamp DESC"
    if limit:
        sql += " LIMIT ?"
        params.append(int(limit))

    rows = conn.execute(sql, params).fetchall()

    changes: List[tuple] = []      # (id, old, new)
    by_nature: Dict[str, int] = {NATURE_STATE: 0, NATURE_FACT: 0, NATURE_EVENT: 0}

    for row in rows:
        mid = row["id"]
        old = row["nature"] if "nature" in row.keys() else NATURE_EVENT
        try:
            ctx = json.loads(row["context_json"] or "{}")
        except (ValueError, TypeError):
            ctx = {}
        new = clf.classify(row["content"] or "", ctx)
        by_nature[new] = by_nature.get(new, 0) + 1
        if new != old:
            changes.append((mid, old, new))

    result: Dict[str, Any] = {
        "dry_run": dry_run,
        "scanned": len(rows),
        "changed": len(changes),
        "unchanged": len(rows) - len(changes),
        "by_nature": by_nature,
        "backup_path": None,
        "elapsed_ms": 0,
    }

    if dry_run or not changes:
        if dry_run and changes:
            # 预览时也给出几条样例，便于人工确认规则是否符合预期
            result["samples"] = [
                {"id": i, "from": o, "to": n} for i, o, n in changes[:5]
            ]
        return result

    t0 = time.time()

    # 备份：id → 原 nature，回滚时按此还原
    if backup_dir:
        bdir = Path(backup_dir)
    else:
        db_path = getattr(store, "_db_path", None) or getattr(store, "persist_dir", None)
        bdir = (Path(db_path).parent if db_path else Path(".")) / "nature_backups"
    try:
        bdir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        bpath = bdir / f"nature_backup_{stamp}.json"
        bpath.write_text(json.dumps(
            {"created": stamp, "changes": [
                {"id": i, "from": o, "to": n} for i, o, n in changes]},
            ensure_ascii=False, indent=1), encoding="utf-8")
        result["backup_path"] = str(bpath)
    except OSError as e:      # 备份失败就不改库——宁可不动，也不留无法回滚的改动
        result["error"] = f"备份写入失败，已中止：{e}"
        return result

    done = 0
    for i, (mid, _old, new) in enumerate(changes):
        conn.execute("UPDATE episodic_memories SET nature=? WHERE id=?", (new, mid))
        done += 1
        if done % batch_size == 0:
            conn.commit()
    conn.commit()

    result["applied"] = done
    result["elapsed_ms"] = int((time.time() - t0) * 1000)
    return result


def rollback_nature(store, backup_path: str) -> Dict[str, Any]:
    """按备份文件回滚一次重分类。"""
    conn = getattr(store, "_conn", store)
    data = json.loads(Path(backup_path).read_text(encoding="utf-8"))
    changes = data.get("changes", [])
    restored = 0
    for c in changes:
        if not c.get("from"):
            continue
        conn.execute("UPDATE episodic_memories SET nature=? WHERE id=?",
                     (c["from"], c["id"]))
        restored += 1
    conn.commit()
    return {"restored": restored, "backup_path": backup_path}
