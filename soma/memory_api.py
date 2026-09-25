"""用户可见的记忆管理接口 —— 列举 / 单条读取 / 编辑 / 删除 / 恢复 / 导出。

为什么要有这个模块：接入方的记忆管理界面此前只能穿透
私有属性拼裸 SQL —— agent.soma._agent.memory.episodic._conn.execute(...)。
三处问题：

1. **越权面**：裸 SQL 没有作用域，云端多用户时会把别人的记忆一起查出来；
2. **锁死演进**：表结构属内部实现，外部一旦依赖它，改列名就是 breaking change；
3. **绕过一致性**：改 content 不重算 content_hash 与向量，去重和语义索引就地失步。

本模块把这些能力收成正式接口。作用域（user_id / agent_id）**在 SQL 层生效**，
不是查完再在 Python 里筛 —— 后者既慢，又容易在改代码时漏掉一处就泄库。

约定：user_id 为空串 = 该维度不限（单租户部署常态）。多租户部署必须显式传。

v2.0.19
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

_log = logging.getLogger("soma.memory_api")

# 导出单次上限默认值（0 = 不限，靠流式写文件扛住）
DEFAULT_PAGE = 50
MAX_PAGE = 1000


def _to_iso(ts: float) -> str:
    """UTC 秒 → ISO 字符串（界面直接显示，省得每处自己转换）。"""
    try:
        return datetime.fromtimestamp(ts, timezone.utc).isoformat()
    except (ValueError, OSError, OverflowError):
        return ""


class MemoryApi:
    """记忆管理的单一出口。

    由 SOMA 门面实例化并持有，接入方经 soma.memories 取用。不自己开连接 ——
    复用 EpisodicStore 既有连接，与 v2.0.18.3 的多专家共享连接策略一致。
    """

    def __init__(self, store, agent=None):
        """store: EpisodicStore；agent: SOMA_Agent（检索要复用它的召回链路）。

        只给 store 也能用全部读写接口，只有 search() 需要 agent —— 检索涉及
        关键词抽取、hub 融合、时间截断，属 agent 层职责，不在这里重抄一遍。
        """
        self._store = store
        self._agent = agent

    # ── 内部 ────────────────────────────────────────────────────

    def _shape(self, mem, *, preview: int = 0) -> Dict[str, Any]:
        """MemoryUnit → 对外 dict。

        显式白名单字段，而不是把整个 dataclass 吐出去 —— 内部字段将来加减
        不该变成对外契约的破坏。
        """
        ctx = getattr(mem, "context", None) or {}
        content = mem.content or ""
        item = {
            "id": mem.id,
            "content": content if not preview else content[:preview],
            "truncated": bool(preview and len(content) > preview),
            "timestamp": mem.timestamp,
            "created_at": _to_iso(mem.timestamp),
            "age_days": mem.age_days() if hasattr(mem, "age_days") else 0.0,
            "importance": mem.importance,
            "access_count": mem.access_count,
            "memory_type": mem.memory_type,
            "nature": getattr(mem, "nature", "event"),
            "is_stale": (mem.is_state_stale()
                         if hasattr(mem, "is_state_stale") else False),
            "user_id": getattr(mem, "user_id", ""),
            "session_id": getattr(mem, "session_id", ""),
            "agent_id": getattr(mem, "agent_id", ""),
            "context": ctx,
        }
        return item

    def _check_owner(self, mem, user_id: str) -> bool:
        """越权兜底：传了 user_id 就必须对上，否则当不存在（不是「无权限」）。

        返回「查不到」而不是「不许看」—— 后者会泄露「这个 id 属于别人」这件事。
        """
        if not user_id:
            return True
        return getattr(mem, "user_id", "") == user_id

    # ── 读 ──────────────────────────────────────────────────────

    def list(
        self,
        *,
        user_id: str = "",
        agent_id: str = "",
        nature: Optional[str] = None,
        min_importance: Optional[float] = None,
        days: float = 0,
        after: str = "",
        order_by: str = "recent",
        limit: int = DEFAULT_PAGE,
        preview: int = 0,
    ) -> Dict[str, Any]:
        """分页列举记忆（管理页用）。

        order_by: "recent"（默认）或 "importance"（「最重要的记忆」列表）。
        after: 上一页返回的 next_cursor（原样传回）。用 (排序键, id) 复合游标
        而不是 OFFSET —— 翻页途中有人新增或删除记忆都不会让页码错位。

        返回 {"items": [...], "next_cursor": str | None, "count": int}
        """
        after_ts: Optional[float] = None
        after_id = ""
        if after:
            want_mode = "t" if order_by == "recent" else "i"
            parts = after.split(":", 2)
            if len(parts) != 3 or parts[0] != want_mode:
                raise ValueError("after 游标格式非法 —— 应原样传回 next_cursor，"
                                 "且不能跨 order_by 复用")
            try:
                after_ts, after_id = float.fromhex(parts[1]), parts[2]
            except (TypeError, ValueError):
                raise ValueError("after 游标已损坏，无法解析排序键")

        mems = self._store.list_memories(
            user_id=user_id, agent_id=agent_id, nature=nature,
            min_importance=min_importance, days=days,
            after_key=after_ts, after_id=after_id,
            order_by=order_by,
            limit=min(max(1, int(limit)), MAX_PAGE))

        items = [self._shape(m, preview=preview) for m in mems]
        next_cursor = None
        if mems and len(mems) >= min(max(1, int(limit)), MAX_PAGE):
            last = mems[-1]
            recent = order_by == "recent"
            key = last.timestamp if recent else last.importance
            next_cursor = "%s:%s:%s" % ("t" if recent else "i",
                                        float(key).hex(), last.id)
        return {"items": items, "next_cursor": next_cursor, "count": len(items)}

    def get(self, memory_id: str, *, user_id: str = "") -> Optional[Dict[str, Any]]:
        """读一条记忆全文。不存在（或不属于该 user_id）返回 None。"""
        mem = self._store.get(memory_id)
        if mem is None or not self._check_owner(mem, user_id):
            return None
        return self._shape(mem)

    def search(
        self, query: str, *, top_k: int = 10, user_id: str = "",
        agent_id: str = "", group_id: str = "", max_age_days: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """语义/关键词检索（管理页搜索框）。走 query_memory 同一召回链路。"""
        if self._agent is None:
            raise RuntimeError(
                "MemoryApi.search 需要 agent —— 请用 soma.memories 取用，"
                "不要自己 new MemoryApi(store)")
        return self._agent.query_memory(
            query, top_k=top_k, user_id=user_id, agent_id=agent_id,
            group_id=group_id, max_age_days=max_age_days)

    # ── 写 ──────────────────────────────────────────────────────

    def update(
        self, memory_id: str, *, user_id: str = "",
        content: Optional[str] = None, importance: Optional[float] = None,
        nature: Optional[str] = None, context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """改一条记忆（用户纠正「它记错了的我」）。内容变了会连带重算 hash 与向量。

        返回 {"ok": bool, "memory": dict | None}
        """
        if content is None and importance is None and nature is None and context is None:
            raise ValueError("至少要传一个要改的字段：content / importance / nature / context")

        mem = self._store.get(memory_id)
        if mem is None or not self._check_owner(mem, user_id):
            return {"ok": False, "memory": None, "reason": "not_found"}

        ok = self._store.update(memory_id, content=content, importance=importance,
                                nature=nature, context=context)
        if not ok:
            return {"ok": False, "memory": None, "reason": "update_failed"}
        return {"ok": True, "memory": self._shape(self._store.get(memory_id))}

    def delete(
        self, memory_id: str, *, user_id: str = "", hard: bool = False,
        reason: str = "user_delete",
    ) -> Dict[str, Any]:
        """删一条记忆。

        默认**归档而非硬删** —— 用户点错还能恢复（restore）。hard=True 才真删，
        给清理脚本用。返回里的 archived 告诉调用方这条还能不能找回。
        """
        mem = self._store.get(memory_id)
        if mem is None or not self._check_owner(mem, user_id):
            return {"ok": False, "reason": "not_found"}

        if hard:
            ok = self._store.delete(memory_id)
            return {"ok": bool(ok), "archived": False}

        ok = self._store.archive_and_delete(memory_id, reason=reason)
        return {"ok": bool(ok), "archived": bool(ok)}

    def archived(self, *, user_id: str = "", limit: int = DEFAULT_PAGE) -> List[Dict[str, Any]]:
        """最近删除（可恢复）的记忆。"""
        rows = self._store.list_archived(user_id=user_id, limit=limit)
        return [
            {"id": r.get("id"), "content": r.get("content"),
             "importance": r.get("importance"),
             "nature": r.get("nature", "event"),
             "archived_at": r.get("archived_at"),
             "archived_at_iso": _to_iso(r.get("archived_at") or 0),
             "archive_reason": r.get("archive_reason"),
             "user_id": r.get("user_id", "")}
            for r in rows
        ]

    def restore(self, memory_id: str, *, user_id: str = "") -> Dict[str, Any]:
        """从归档恢复一条记忆（撤销一次删除）。

        只有真在归档里的才能恢复；不在归档的（比如当初是 hard=True 删的）
        明确返回 not_archived，不要静默失败让界面以为撤销成功了。
        """
        hit = self._store.get_archived(memory_id)
        if hit is None:
            return {"ok": False, "reason": "not_archived"}
        if user_id and hit.get("user_id", "") != user_id:
            return {"ok": False, "reason": "not_found"}
        ok = self._store.restore_archived(memory_id)
        return {"ok": bool(ok)}

    # ── 导出 ────────────────────────────────────────────────────

    def iter_memories(
        self, *, user_id: str = "", agent_id: str = "",
        nature: Optional[str] = None, order_by: str = "recent",
        batch: int = 200,
    ) -> Iterator[Dict[str, Any]]:
        """流式遍历全库（备份、迁移、云端同步用）。

        生成器逐批取 —— 26k 条的库一次性 list() 出来是几百 MB，接入方在
        内存敏感的多实例环境里扛不住（v2.0.16/17 整轮就是在还这笔债）。
        """
        cursor = ""
        while True:
            page = self.list(user_id=user_id, agent_id=agent_id, nature=nature,
                             order_by=order_by, after=cursor, limit=batch)
            for item in page["items"]:
                yield item
            if not page["next_cursor"]:
                return
            cursor = page["next_cursor"]

    def export_memories(
        self, *, user_id: str = "", agent_id: str = "",
        nature: Optional[str] = None, path: str = "",
        order_by: str = "recent", batch: int = 200, limit: int = 0,
    ) -> Dict[str, Any]:
        """导出记忆为 JSON。

        path 为空 → 直接把列表放在返回值的 items 里（小库方便）；
        给了 path → 逐批写文件（NDJSON 语义，一行一条），返回值只带计数和路径，
        不把整库读进内存。
        """
        items: List[Dict[str, Any]] = []
        count = 0
        fobj = None
        out_path: Optional[Path] = None
        try:
            if path:
                out_path = Path(path)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                fobj = out_path.open("w", encoding="utf-8")

            for item in self.iter_memories(user_id=user_id, agent_id=agent_id,
                                           nature=nature, order_by=order_by,
                                           batch=batch):
                if limit and count >= limit:
                    break
                count += 1
                if fobj is not None:
                    fobj.write(json.dumps(item, ensure_ascii=False) + "\n")
                else:
                    items.append(item)
        finally:
            if fobj is not None:
                fobj.close()

        result: Dict[str, Any] = {"count": count, "user_id": user_id,
                                  "format": "ndjson-file" if path else "list"}
        if path:
            result["path"] = str(out_path)
        else:
            result["items"] = items
        return result
