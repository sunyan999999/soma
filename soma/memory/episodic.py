import hashlib
import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from soma.abc import BaseMemoryStore
from soma.base import MemoryUnit
from soma.db import close_store_connection, open_store_connection
from soma.memory.context_utils import normalize_context, parse_context

_log = logging.getLogger("soma.memory.episodic")
# 单页返回上限 —— 管理页与导出都靠它兜住「一次拉爆内存」
_LIST_MAX_LIMIT = 1000



class EpisodicStore(BaseMemoryStore):
    """情节记忆存储 — SQLite 持久化 + 可选向量语义搜索"""

    def __init__(
        self,
        persist_dir: Path,
        collection_name: str = "episodic",
        embedder=None,
        use_vector_search: bool = False,
        mmap_size: int = 0,
    ):
        persist_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = persist_dir / f"{collection_name}.db"
        self._conn = open_store_connection(self._db_path, mmap_size=mmap_size)
        self._embedder = embedder
        self._use_vector = use_vector_search and embedder is not None
        # v2.0.17: SQLite 内存映射大小（字节），0 = 禁用。见 SOMAConfig.sqlite_mmap_size
        self._mmap_size = max(0, int(mmap_size))

        self._create_table()
        self._vector_index = None

        if self._use_vector:
            from soma.vector_store import NumpyVectorIndex

            dim = embedder.dimension if embedder else 512
            self._vector_index = NumpyVectorIndex(self._db_path, dim)
            self._vector_index.ensure_table(self._conn)
            # 维度迁移：清除嵌入模型变更导致的不兼容旧向量
            stale = self._vector_index.clear_incompatible_vectors(self._conn)
            if stale > 0:
                rebuilt = self.rebuild_vectors()
                if rebuilt > 0:
                    _log.info("向量维度迁移: 清除 %d 条旧向量, 重建 %d 条", stale, rebuilt)

            # v0.9.0: 向量健康检查 — 历史记忆可能缺少向量（向量搜索后启用场景）
            total = self.count()
            indexed = self._vector_index.count_indexed(self._conn)
            if total > 10 and indexed < total * 0.5:
                _log.info("向量健康检查: %d/%d 条记忆缺少向量，开始重建...", total - indexed, total)
                rebuilt = self.rebuild_vectors()
                if rebuilt > 0:
                    _log.info("向量健康检查完成: 已重建 %d 条向量", rebuilt)

    def _create_table(self):
        # WAL 模式 + 性能 PRAGMA
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")       # WAL 下 NORMAL 足够安全
        self._conn.execute("PRAGMA cache_size=-8000")          # 8MB 缓存
        # v2.0.17: 改由 SOMAConfig.sqlite_mmap_size 控制，默认 0（禁用）。
        # 历史默认 256MB 会让每个连接把整个库映射进进程 RSS —— Linux 上多专家
        # 架构一个实例开 4 个连接，同一个 episodic.db 被映射 4 份，实测每实例
        # 因此多占约 811MB（DSH 2026-09-12 定位）。调大可加速随机读，代价是常驻内存。
        self._conn.execute(f"PRAGMA mmap_size={self._mmap_size}")
        self._conn.execute("PRAGMA temp_store=MEMORY")         # 临时表存内存
        self._conn.execute("PRAGMA busy_timeout=15000")        # 15秒忙等待（Windows并发场景）
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS episodic_memories (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                content_hash TEXT NOT NULL DEFAULT '',
                timestamp REAL NOT NULL,
                importance REAL DEFAULT 0.5,
                access_count INTEGER DEFAULT 0,
                context_json TEXT DEFAULT '{}',
                memory_type TEXT DEFAULT 'episodic',
                user_id TEXT NOT NULL DEFAULT '',
                session_id TEXT NOT NULL DEFAULT '',
                agent_id TEXT NOT NULL DEFAULT '',
                shared_group_id TEXT NOT NULL DEFAULT '',
                nature TEXT NOT NULL DEFAULT 'event'
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_timestamp ON episodic_memories(timestamp DESC)"
        )
        # 向后兼容迁移：补齐可能缺失的列
        for col, col_def in [
            ("content_hash", "TEXT NOT NULL DEFAULT ''"),
            ("user_id", "TEXT NOT NULL DEFAULT ''"),
            ("session_id", "TEXT NOT NULL DEFAULT ''"),
            ("agent_id", "TEXT NOT NULL DEFAULT ''"),
            ("shared_group_id", "TEXT NOT NULL DEFAULT ''"),
            ("nature", "TEXT NOT NULL DEFAULT 'event'"),
        ]:
            try:
                self._conn.execute(
                    f"ALTER TABLE episodic_memories ADD COLUMN {col} {col_def}"
                )
            except sqlite3.OperationalError:
                pass  # 列已存在
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_content_hash ON episodic_memories(content_hash)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_episodic_user ON episodic_memories(user_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_episodic_agent ON episodic_memories(agent_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_episodic_group ON episodic_memories(shared_group_id)"
        )
        # v2.0.19: 管理页的「最重要的记忆」按 importance 倒序取 —— 没索引就是
        # 全表排序。SQLite 可以反向扫普通索引，故不必建表达式索引。
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_episodic_importance ON episodic_memories(importance)"
        )
        # v2.0.18.3: (user_id, agent_id) 复合索引。生产 hub 调用恒带这两个条件，
        # 而 SQLite 会放着选择性更好的 idx_episodic_user 不用，去扫
        # idx_episodic_agent（agent_id 近乎覆盖全表）—— 实测 21k 行 / 203 用户下，
        # 只有 3 条记忆的长尾用户也要付 ~70ms（子集 COUNT 35ms + 取向量 35ms），
        # 代价与用户记忆数无关。同一条索引同时修三处拼这个组合的查询：
        #   ① 向量子集检索 _exact_filtered_search（读路径）
        #   ② insert() 的 content_hash 去重（写路径，每次 remember 都付）
        #   ③ 关键词 LIKE 兜底 search_utils 路径2（中文 1~2 字词）
        # 比在 SQL 里写 INDEXED BY 稳：不依赖计划器统计，也没有「索引被删就
        # 直接报错」的硬绑定。（接入方若已手工建过同名索引，IF NOT EXISTS 命中。）
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_episodic_user_agent "
            "ON episodic_memories(user_id, agent_id)"
        )
        # v2.0.18: 轻量 KV —— 存放跨会话元信息（上次会话结束时间、已推进的自主目标等）。
        # 与记忆表同库，避免为几十字节的状态另开一个数据库文件/连接。
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS soma_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )
        self._create_fts5()
        self._conn.commit()

    def _create_fts5(self):
        """创建 FTS5 trigram 全文索引表，用于加速中文关键词搜索"""
        self._conn.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS episodic_fts USING fts5(
                content,
                context_json,
                content='episodic_memories',
                content_rowid='rowid',
                tokenize='trigram'
            )
            """
        )
        # 触发器: INSERT → 同步到 FTS
        self._conn.executescript("""
            CREATE TRIGGER IF NOT EXISTS episodic_fts_ai AFTER INSERT ON episodic_memories BEGIN
                INSERT INTO episodic_fts(rowid, content, context_json)
                VALUES (new.rowid, new.content, new.context_json);
            END;
            CREATE TRIGGER IF NOT EXISTS episodic_fts_ad AFTER DELETE ON episodic_memories BEGIN
                INSERT INTO episodic_fts(episodic_fts, rowid, content, context_json)
                VALUES ('delete', old.rowid, old.content, old.context_json);
            END;
            CREATE TRIGGER IF NOT EXISTS episodic_fts_au AFTER UPDATE ON episodic_memories BEGIN
                INSERT INTO episodic_fts(episodic_fts, rowid, content, context_json)
                VALUES ('delete', old.rowid, old.content, old.context_json);
                INSERT INTO episodic_fts(rowid, content, context_json)
                VALUES (new.rowid, new.content, new.context_json);
            END;
        """)
        # 迁移已有数据到 FTS（幂等：如果 FTS 刚创建且为空）
        populated = self._conn.execute(
            "SELECT COUNT(*) FROM episodic_fts"
        ).fetchone()[0]
        if populated == 0:
            self._conn.execute(
                "INSERT INTO episodic_fts(rowid, content, context_json) "
                "SELECT rowid, content, context_json FROM episodic_memories"
            )

    def _compute_hash(self, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def add(
        self,
        content: str,
        context: Optional[Dict[str, Any]] = None,
        importance: float = 0.5,
        user_id: str = "",
        session_id: str = "",
        agent_id: str = "",
        shared_group_id: str = "",
        nature: str = "event",
    ) -> str:
        content_hash = self._compute_hash(content)

        # 去重检查：同用户 + 同agent + 同内容不重复插入
        existing = self._conn.execute(
            "SELECT id FROM episodic_memories WHERE user_id = ? AND agent_id = ? "
            "AND content_hash = ? LIMIT 1",
            (user_id, agent_id, content_hash),
        ).fetchone()
        if existing:
            return existing["id"]

        if nature not in ("state", "fact", "event"):
            nature = "event"
        memory_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc).timestamp()
        # v2.0.17: 规范化非 dict 入参（调用方误传字符串时 json.dumps 会产出
        # 合法但非对象的 JSON，读回来就是 str），从源头堵住脏数据
        context_json = json.dumps(normalize_context(context), ensure_ascii=False)

        self._conn.execute(
            """
            INSERT INTO episodic_memories (id, content, content_hash, timestamp, importance,
                context_json, user_id, session_id, agent_id, shared_group_id, nature)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (memory_id, content, content_hash, now, importance, context_json,
             user_id, session_id, agent_id, shared_group_id, nature),
        )
        self._conn.commit()

        # 自动生成嵌入向量（拆开 encode 与索引写入，便于定位失败原因）
        if self._use_vector and self._embedder is not None:
            try:
                vec = self._embedder.encode(content)
            except Exception as e:
                _log.warning(
                    "嵌入向量编码失败，memory_id=%s，记忆已存储但无法语义搜索。"
                    "如果首次启动，可能是嵌入模型正在从 HuggingFace 下载（~66MB），"
                    "稍后自动恢复。原因: %s",
                    memory_id, e,
                )
                return memory_id
            try:
                self._vector_index.store_vector(self._conn, memory_id, vec)
            except Exception as e:
                # 索引写入失败：DB 有向量但 faiss 索引缺该条，下次查询会重建补全
                _log.warning(
                    "向量索引写入失败，memory_id=%s，记忆已存储但该条暂缺语义索引"
                    "（下次查询将自动重建索引补全）。原因: %s",
                    memory_id, e,
                )

        return memory_id

    def get_style_samples(self, n: int = 20) -> List[str]:
        """获取高重要性记忆文本作为风格样本（v2.0.9: 补接口，供知识门控风格对齐）。"""
        try:
            rows = self._conn.execute(
                "SELECT content FROM episodic_memories "
                "WHERE length(content) > 50 "
                "ORDER BY importance DESC LIMIT ?",
                (n,),
            ).fetchall()
        except Exception:
            return []
        return [r["content"] for r in rows if r["content"]]

    def query_by_keywords(
        self, keywords: List[str], top_k: int = 5,
        user_id: str = "",
        agent_id: str = "",
        group_id: str = "",
        max_age_days: Optional[float] = None,
    ) -> List[MemoryUnit]:
        if not keywords:
            return []

        from soma.memory.search_utils import fts5_keyword_search

        return fts5_keyword_search(
            self._conn,
            keywords,
            table_name="episodic_memories",
            fts_table="episodic_fts",
            search_cols=["content", "context_json"],
            id_col="id",
            time_col="timestamp",
            importance_col="importance",
            user_col="user_id",
            row_converter=self._row_to_memory,
            top_k=top_k,
            user_id=user_id,
            max_age_days=max_age_days,
            agent_col="agent_id" if agent_id else "",
            agent_id=agent_id,
            group_col="shared_group_id" if group_id else "",
            group_id=group_id,
        )

    def query_by_vector(
        self, query_vec, top_k: int = 5, user_id: str = "",
        agent_id: str = "",
        group_id: str = "",
        max_age_days: Optional[float] = None,
    ) -> List[MemoryUnit]:
        """向量语义搜索（支持 user_id + agent/group 隔离 + 时间窗口过滤）

        v2.0.18.2: 隔离条件**下推**给 similarity_search，在过滤后的子集内取 top-k。

        原先的 ``fetch_k = top_k * 3`` 是「按比例过滤」的粗略补偿：先全局取 3×top_k
        条候选，再逐条按 user_id 剔除。多租户下单个用户的记忆占全库比例很低时，这
        ``3×top_k`` 条候选里往往**一条都不属于**该用户 —— 向量通道对该用户等于失效，
        而它是 RRF 融合的主通道。接入方 27,008 条 / 130 用户的分布下，中位用户 17 条
        （占 0.06%）取 45 条候选，期望命中不足 0.05 条；实测（tmp/probe_user_recall.py）
        长尾用户 top_k=10 只召回 1 条。关键词通道本来就是 SQL 前置过滤，不受影响 ——
        两条通道时机不一致是这个 bug 的根源。

        下面的 Python 侧过滤**保留**，不再是主路径：它是「子集过大退回全局检索」
        （similarity_search 返回的是未过滤候选）时的兜底，也让本方法在
        _vector_index 换成别的实现时依然正确。
        """
        if self._vector_index is None:
            return []

        results = self._vector_index.similarity_search(
            self._conn, query_vec, top_k,
            user_id=user_id, agent_id=agent_id, group_id=group_id,
            max_age_days=max_age_days,
        )
        memories = []
        min_ts = None
        if max_age_days is not None:
            min_ts = datetime.now(timezone.utc).timestamp() - max_age_days * 86400.0
        for mid, score in results:
            mem = self.get(mid)
            if mem is None:
                continue
            # user_id 过滤（空user_id的记忆在指定user_id时被过滤）
            if user_id and mem.user_id != user_id:
                continue
            # agent/group 过滤：agent自己的 + 组共享的（空agent_id的记忆在指定agent_id时被过滤）
            if agent_id and mem.agent_id != agent_id:
                if not (group_id and mem.shared_group_id == group_id):
                    continue
            # 时间窗口过滤
            if min_ts is not None and mem.timestamp < min_ts:
                continue
            # v2.0.17: 兜底防御。context 经 parse_context 后恒为 dict，但 MemoryUnit
            # 也可能由外部直接构造 —— 这里再挡一层，避免单条脏数据把整次全库检索炸掉
            # （历史事故：26,872 条中 1 条 str context 让 query_by_vector 抛 TypeError）
            if isinstance(mem.context, dict):
                mem.context["_vector_score"] = score
            memories.append(mem)
            if len(memories) >= top_k:
                break
        return memories

    def rebuild_vectors(self, batch_size: int = 100) -> int:
        """为缺失向量的记忆批量生成嵌入"""
        if self._embedder is None or self._vector_index is None:
            return 0

        rows = self._conn.execute(
            "SELECT id, content FROM episodic_memories WHERE vector IS NULL"
        ).fetchall()

        count = 0
        for i in range(0, len(rows), batch_size):
            batch = rows[i : i + batch_size]
            ids = [r[0] for r in batch]
            texts = [r[1] for r in batch]
            vecs = self._embedder.encode_batch(texts)
            for j, mid in enumerate(ids):
                self._vector_index.store_vector(self._conn, mid, vecs[j])
                count += 1

        return count

    def prune_stale_vectors(self, background: bool = True) -> dict:
        """清理过期向量（v2.0.18）。

        记忆被删除后（forgetting 直接删行，不经过索引），faiss 索引里会留下对不上
        任何记忆的残留向量。本方法把索引中这部分剔除，**不重新编码** —— 有效向量
        直接从内存索引 reconstruct 出来重建成新索引，代价只有一次索引构造 + 写盘。

        Args:
            background: True（默认）把耗时的索引构造放后台线程；
                        False 同步完成，便于测试与进程收尾。

        Returns:
            {"pruned": 移除条数, "remaining": 剩余条数,
             "rebuilt": 是否已重建, "scheduled": 是否已调度后台重建}
        """
        if self._vector_index is None:
            return {"pruned": 0, "remaining": 0,
                    "rebuilt": False, "scheduled": False}
        return self._vector_index.prune_stale(self._conn, background=background)

    def count_stale_vectors(self) -> int:
        """索引里过期（对应记忆已被删除）的向量条数。"""
        if self._vector_index is None:
            return 0
        return self._vector_index.stale_count(self._conn)

    def reload_index(self) -> int:
        """从 DB 重新加载向量索引（v2.0.15）。

        场景：长驻实例运行时，**外部进程**（CLI / 另一个 Agent / 裸 SQL）往同一个
        记忆库写了数据 —— SQLite 查询能立刻看到新行（WAL 多读者），但内存里的
        faiss 索引还是旧的，语义检索会漏掉新记忆。调本方法把索引按 DB 现状重建。

        Returns:
            重建后的向量条数（索引未启用时返回 0）
        """
        if self._vector_index is None:
            return 0
        ids, vecs = self._vector_index.get_all_vectors(self._conn)
        self._vector_index._build_faiss_index(ids, vecs)
        _log.info("向量索引已重载: %d 条", len(ids))
        return len(ids)

    def get(self, memory_id: str) -> Optional[MemoryUnit]:
        row = self._conn.execute(
            "SELECT * FROM episodic_memories WHERE id = ?", (memory_id,)
        ).fetchone()
        return self._row_to_memory(row) if row else None

    def delete(self, memory_id: str) -> bool:
        cursor = self._conn.execute(
            "DELETE FROM episodic_memories WHERE id = ?", (memory_id,)
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) FROM episodic_memories").fetchone()
        return row[0] if row else 0

    def count_indexed(self) -> int:
        if self._vector_index is None:
            return 0
        return self._vector_index.count_indexed(self._conn)

    # ── v2.0.18: 轻量 KV（跨会话元信息） ────────────────

    def meta_get(self, key: str, default: Any = None) -> Any:
        """读取跨会话元信息，缺失或损坏时返回 default（不抛错）。"""
        try:
            row = self._conn.execute(
                "SELECT value FROM soma_meta WHERE key = ?", (key,)
            ).fetchone()
        except sqlite3.Error:
            _log.debug("meta_get(%s) 读取失败", key, exc_info=True)
            return default
        if row is None:
            return default
        try:
            return json.loads(row["value"])
        except (TypeError, ValueError):
            return default

    def meta_set(self, key: str, value: Any) -> bool:
        """写入跨会话元信息（JSON 序列化），失败返回 False 而不抛错。"""
        try:
            payload = json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError):
            _log.debug("meta_set(%s) 值无法序列化", key, exc_info=True)
            return False
        try:
            self._conn.execute(
                "INSERT INTO soma_meta(key, value, updated_at) VALUES(?,?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, "
                "updated_at=excluded.updated_at",
                (key, payload, datetime.now(timezone.utc).timestamp()),
            )
            self._conn.commit()
            return True
        except sqlite3.Error:
            _log.debug("meta_set(%s) 写入失败", key, exc_info=True)
            return False

    def query_by_context_type(
        self, ctx_type: str, days: float = 0, limit: int = 50, user_id: str = "",
    ) -> List[MemoryUnit]:
        """按 context.type 取最近的记忆（v2.0.18，自主目标来源用）。

        先用 LIKE 粗筛（不依赖 SQLite JSON1 扩展），再用 parse_context 精确比对。
        粗筛刻意放宽，宁可多取几条交给 Python 侧过滤 —— 少取会静默丢目标。
        单条 context 为脏数据时跳过该条，不影响其余结果（沿用 v2.0.17 的防御）。
        """
        sql = "SELECT * FROM episodic_memories WHERE context_json LIKE ? "
        params: List[Any] = [f'%"type"%{ctx_type}%']
        if days > 0:
            sql += "AND timestamp >= ? "
            params.append(datetime.now(timezone.utc).timestamp() - days * 86400)
        if user_id:
            sql += "AND user_id = ? "
            params.append(user_id)
        sql += "ORDER BY timestamp DESC LIMIT ?"
        params.append(int(limit))

        try:
            rows = self._conn.execute(sql, params).fetchall()
        except sqlite3.Error:
            _log.warning("query_by_context_type(%s) 查询失败", ctx_type, exc_info=True)
            return []

        out: List[MemoryUnit] = []
        for row in rows:
            try:
                mem = self._row_to_memory(row)
            except Exception:
                continue
            ctx = mem.context
            if isinstance(ctx, dict) and ctx.get("type") == ctx_type:
                out.append(mem)
        return out

    def query_by_filters(
        self,
        *,
        nature: Optional[str] = None,
        min_importance: Optional[float] = None,
        max_access_count: Optional[int] = None,
        days: float = 0,
        older_than_days: float = 0,
        limit: int = 50,
        user_id: str = "",
    ) -> List[MemoryUnit]:
        """按字段条件取最近的记忆（v2.0.18，自主目标来源用）。

        只开放白名单内的几个筛选维度，不做通用查询构造器 —— 条件全部来自代码内
        固定调用。所有值仍然参数化绑定，不做字符串拼接。

        时间窗有两个方向，按需选用（都不传则不限时间）：
        - ``days``            —— 只取最近 N 天内的（timestamp >= now - N 天）
        - ``older_than_days`` —— 只取早于 N 天前的（timestamp < now - N 天）

        两个方向同时传就是「N 天前到 M 天前」这个区间。

        ``user_id`` 为空串表示**不按用户过滤**（单用户部署的常态）。多租户部署
        必须显式传入 —— 否则会取到其他用户的记忆。
        """
        sql = "SELECT * FROM episodic_memories WHERE 1=1 "
        params: List[Any] = []
        if nature is not None:
            sql += "AND nature = ? "
            params.append(nature)
        if min_importance is not None:
            sql += "AND importance >= ? "
            params.append(float(min_importance))
        if max_access_count is not None:
            sql += "AND access_count <= ? "
            params.append(int(max_access_count))
        if days > 0:
            sql += "AND timestamp >= ? "
            params.append(datetime.now(timezone.utc).timestamp() - days * 86400)
        if older_than_days > 0:
            sql += "AND timestamp < ? "
            params.append(datetime.now(timezone.utc).timestamp() - older_than_days * 86400)
        if user_id:
            sql += "AND user_id = ? "
            params.append(user_id)
        sql += "ORDER BY timestamp DESC LIMIT ?"
        params.append(int(limit))

        try:
            rows = self._conn.execute(sql, params).fetchall()
        except sqlite3.Error:
            _log.warning("query_by_filters 查询失败", exc_info=True)
            return []

        out: List[MemoryUnit] = []
        for row in rows:
            try:
                out.append(self._row_to_memory(row))
            except Exception:
                continue
        return out

    # ── v2.0.19: 用户可见的记忆管理原语（只读列举 / 更新 / 归档删除） ──

    def _ensure_archived_table(self) -> bool:
        """确保归档表存在（表结构唯一定义在 ForgettingEngine，这里只负责触发）。

        新库在第一次遗忘扫描之前没有 episodic_archived —— 直接查会抛
        OperationalError，把「还没有任何东西被归档」误报成查询故障。
        """
        try:
            from soma.memory.forgetting import ForgettingEngine
            ForgettingEngine(self._conn)     # __init__ 里 _ensure_tables()，幂等
            return True
        except Exception:
            _log.warning("归档表初始化失败", exc_info=True)
            return False

    def list_memories(
        self,
        *,
        user_id: str = "",
        agent_id: str = "",
        nature: Optional[str] = None,
        min_importance: Optional[float] = None,
        days: float = 0,
        older_than_days: float = 0,
        after_key: Optional[float] = None,
        after_id: str = "",
        order_by: str = "recent",
        limit: int = 50,
    ) -> List[MemoryUnit]:
        """按条件列举记忆（管理页 / 导出用），键集游标分页。

        与 query_by_filters 的分工：那条服务于代码内的固定调用（自主循环取
        候选），本条服务于「翻给用户看」—— 多一组游标参数，让接入方能连续
        翻页而不漏不重。

        分页用 (timestamp, id) 复合游标而不是 OFFSET：管理页翻到第 20 页时
        若有人新增或删除记忆，OFFSET 会错位（同一条重复出现或整条跳过）。
        传上一页最后一条的 timestamp + id 即可安全续翻。

        order_by: "recent"（默认，按时间倒序）或 "importance"（按重要性倒序，
        管理页的「最重要的记忆」用）。两者都用 (排序键, id) 复合游标，
        after_key 传的就是上一页最后一条的那个排序键。

        user_id 为空串 = 不按用户过滤（单租户常态）；多租户必须显式传，
        否则等于全库可见 —— 与 query_by_filters 同一约定。
        """
        if order_by not in ("recent", "importance"):
            raise ValueError("order_by 只能是 recent / importance，收到 " + repr(order_by))
        sql = "SELECT * FROM episodic_memories WHERE 1=1 "
        params: List[Any] = []
        if user_id:
            sql += "AND user_id = ? "
            params.append(user_id)
        if agent_id:
            sql += "AND agent_id = ? "
            params.append(agent_id)
        if nature:
            sql += "AND nature = ? "
            params.append(nature)
        if min_importance is not None:
            sql += "AND importance >= ? "
            params.append(float(min_importance))
        if days > 0:
            sql += "AND timestamp >= ? "
            params.append(datetime.now(timezone.utc).timestamp() - days * 86400)
        if older_than_days > 0:
            sql += "AND timestamp < ? "
            params.append(datetime.now(timezone.utc).timestamp() - older_than_days * 86400)
        if after_key is not None and after_id:
            # 行值比较的展开写法 —— 兼容不支持 (a,b) < (?,?) 的旧 SQLite
            key = "timestamp" if order_by == "recent" else "importance"
            sql += "AND (" + key + " < ? OR (" + key + " = ? AND id < ?)) "
            params.extend([float(after_key), float(after_key), after_id])
        order = "timestamp" if order_by == "recent" else "importance"
        sql += "ORDER BY " + order + " DESC, id DESC LIMIT ?"
        params.append(max(1, min(int(limit), _LIST_MAX_LIMIT)))

        try:
            rows = self._conn.execute(sql, params).fetchall()
        except sqlite3.Error:
            _log.warning("list_memories 查询失败", exc_info=True)
            return []

        out: List[MemoryUnit] = []
        for row in rows:
            try:
                out.append(self._row_to_memory(row))
            except Exception:
                continue      # 单行坏数据不能拖垮整页（与 query_by_filters 一致）
        return out

    def update(
        self,
        memory_id: str,
        *,
        content: Optional[str] = None,
        importance: Optional[float] = None,
        nature: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """更新一条记忆的字段，并保持一致性（内容变了要重算 hash 与向量）。

        接入方此前只能裸 SQL 改 content —— 那样 content_hash 与向量都留在
        旧值上：去重判断失准，语义搜索还在召回改前的内容。本方法把「改什么、
        连带重算什么」收在一处。

        只更新显式传入的字段（None = 不动该字段）。返回 False 表示该 id 不存在。
        """
        fields: List[str] = []
        params: List[Any] = []

        if content is not None:
            fields.append("content = ?")
            params.append(content)
            fields.append("content_hash = ?")
            params.append(self._compute_hash(content))
        if importance is not None:
            fields.append("importance = ?")
            params.append(max(0.0, min(1.0, float(importance))))
        if nature is not None:
            if nature not in ("state", "fact", "event"):
                raise ValueError("nature 必须是 state/fact/event，收到 " + repr(nature))
            fields.append("nature = ?")
            params.append(nature)
        if context is not None:
            fields.append("context_json = ?")
            params.append(json.dumps(normalize_context(context), ensure_ascii=False))

        if not fields:
            return self.get(memory_id) is not None

        params.append(memory_id)
        try:
            cur = self._conn.execute(
                "UPDATE episodic_memories SET " + ", ".join(fields) + " WHERE id = ?",
                params,
            )
            self._conn.commit()
        except sqlite3.Error:
            _log.warning("update 失败, memory_id=%s", memory_id[:8], exc_info=True)
            return False
        if cur.rowcount == 0:
            return False

        # 内容变了 → 向量必须重算，否则语义搜索仍返回改前内容（FTS5 由触发器自动同步）
        if content is not None:
            self._reindex_vector(memory_id, content)
        return True

    def _reindex_vector(self, memory_id: str, content: str) -> bool:
        """重新编码并写入向量（编码失败只降级索引，不影响内容已更新的事实）。"""
        if not self._use_vector or self._embedder is None:
            return False
        try:
            vec = self._embedder.encode(content)
            self._vector_index.store_vector(self._conn, memory_id, vec)
            return True
        except Exception as e:
            _log.warning(
                "向量重算失败，memory_id=%s，内容已更新但该条暂缺语义索引"
                "（下次查询会自动重建补全）。原因: %s", memory_id[:8], e)
            return False

    def archive_and_delete(
        self, memory_id: str, reason: str = "user_delete"
    ) -> bool:
        """删除一条记忆，但先归档 —— 用户点删除之后还能反悔。

        与 ForgettingEngine 的归档走同一张表（episodic_archived），用
        archive_reason 区分来源。硬删除请走 delete()（遗忘清理用），
        用户侧默认不该硬删。
        """
        row = self._conn.execute(
            "SELECT * FROM episodic_memories WHERE id = ?", (memory_id,)
        ).fetchone()
        if row is None:
            return False

        from soma.memory.forgetting import ForgettingEngine
        engine = ForgettingEngine(self._conn)
        if not engine.archive_row(row, reason=reason):
            return False

        # 行已不在主表 —— 顺手清掉向量，免得 faiss 里留着对不上记忆的幽灵条目
        if self._use_vector and self._vector_index is not None:
            try:
                self._vector_index.delete_vector(self._conn, memory_id)
            except Exception:
                _log.warning("归档后清向量失败, memory_id=%s", memory_id[:8],
                             exc_info=True)
        return True

    def list_archived(
        self, *, user_id: str = "", limit: int = 50
    ) -> List[Dict[str, Any]]:
        """列举归档记忆（供「最近删除 / 可恢复」界面）。

        不复用 ForgettingEngine.recall_archived —— 那里 user_id="" 是**字面**
        条件（只查未指定用户的归档行），而本模块的约定是「空 = 不限」，两者
        语义相反：照抄会让单传 user_id 的调用永远查不到东西。
        """
        if not self._ensure_archived_table():
            return []
        sql = "SELECT * FROM episodic_archived WHERE 1=1 "
        params: List[Any] = []
        if user_id:
            sql += "AND user_id = ? "
            params.append(user_id)
        sql += "ORDER BY archived_at DESC LIMIT ?"
        params.append(max(1, min(int(limit), _LIST_MAX_LIMIT)))
        try:
            rows = self._conn.execute(sql, params).fetchall()
        except sqlite3.Error:
            _log.warning("list_archived 查询失败", exc_info=True)
            return []
        return [dict(r) for r in rows]

    def get_archived(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """按 id 取一条归档记忆（不存在返回 None）。"""
        if not self._ensure_archived_table():
            return None
        try:
            row = self._conn.execute(
                "SELECT * FROM episodic_archived WHERE id = ?", (memory_id,)
            ).fetchone()
        except sqlite3.Error:
            _log.warning("get_archived 查询失败", exc_info=True)
            return None
        return dict(row) if row else None

    def distinct_user_ids(self, limit: int = 500) -> List[str]:
        """库里出现过的非空 user_id，按记忆条数降序（v2.0.18.2）。

        后台自主循环用它做「按用户轮转」时的用户发现（``autonomous_background_
        user_ids="*"``）。空串桶**不返回** —— 它代表「未指定用户」这个命名空间
        本身（单租户部署的常态），不是某个具体用户；需要单租户语义时调用方自己
        传空串。

        带上限（默认 500）且按条数降序：这条查询会被后台循环**定期**调用，不能
        被一个异常库拖成无界扫描；先覆盖记忆多的用户也更符合"优先服务活跃用户"
        的直觉（接入方 130 用户 / 27k 条的分布下 500 完全够用）。
        """
        try:
            rows = self._conn.execute(
                "SELECT user_id, COUNT(*) AS n FROM episodic_memories "
                "WHERE user_id != '' GROUP BY user_id "
                "ORDER BY n DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        except sqlite3.Error:
            _log.warning("distinct_user_ids 查询失败", exc_info=True)
            return []
        return [r["user_id"] for r in rows if r["user_id"]]

    def _row_to_memory(self, row: sqlite3.Row) -> MemoryUnit:
        mem_type = row["memory_type"] if "memory_type" in row.keys() else "episodic"
        return MemoryUnit(
            id=row["id"],
            content=row["content"],
            timestamp=row["timestamp"],
            importance=row["importance"],
            access_count=row["access_count"],
            context=parse_context(row["context_json"]),
            memory_type=mem_type,
            user_id=row["user_id"] if "user_id" in row.keys() else "",
            session_id=row["session_id"] if "session_id" in row.keys() else "",
            agent_id=row["agent_id"] if "agent_id" in row.keys() else "",
            shared_group_id=row["shared_group_id"] if "shared_group_id" in row.keys() else "",
            nature=row["nature"] if "nature" in row.keys() else "event",
        )

    @property
    def use_vector(self) -> bool:
        return self._use_vector

    def increment_access(self, memory_id: str) -> bool:
        """递增记忆的访问计数并持久化"""
        self._conn.execute(
            "UPDATE episodic_memories SET access_count = access_count + 1 WHERE id = ?",
            (memory_id,),
        )
        self._conn.commit()
        return self._conn.total_changes > 0

    # ── v0.7.0 记忆智能 ─────────────────────────────────

    def consolidate(self, user_id: str = "", max_merges: int = 10) -> int:
        """执行一次记忆合并扫描（摘要合并）"""
        from soma.memory.consolidation import ConsolidationEngine
        engine = ConsolidationEngine(self._conn, self._embedder)
        return engine.run_consolidation_pass(user_id=user_id, max_merges=max_merges)

    def forget(self, user_id: str = "", max_archive: int = 50) -> dict:
        """执行一次遗忘扫描（三层遗忘策略）"""
        from soma.memory.forgetting import ForgettingEngine
        engine = ForgettingEngine(self._conn)
        return engine.run_forgetting_pass(user_id=user_id, max_archive=max_archive)

    def recall_archived(self, query: str = "", user_id: str = "", top_k: int = 20):
        """从归档中浏览/恢复记忆"""
        from soma.memory.forgetting import ForgettingEngine
        engine = ForgettingEngine(self._conn)
        return engine.recall_archived(query=query, user_id=user_id, top_k=top_k)

    def restore_archived(self, memory_id: str) -> bool:
        """恢复一条归档记忆（v2.0.19: 连带重建向量）。

        归档时向量随行一起被清掉（delete_vector 置 NULL）—— 只回插主表的话，
        恢复出来的记忆 vector 为空，语义搜索再也召不回它，等于「恢复」只恢复了
        一半。这里补一次重编码。
        """
        from soma.memory.forgetting import ForgettingEngine
        engine = ForgettingEngine(self._conn)
        if not engine.restore(memory_id):
            return False
        row = self._conn.execute(
            "SELECT content FROM episodic_memories WHERE id = ?", (memory_id,)
        ).fetchone()
        if row is not None:
            self._reindex_vector(memory_id, row["content"])
        return True

    def import_knowledge(
        self, source_path: str, user_id: str = "", session_id: str = ""
    ) -> list:
        """从文件导入外部知识"""
        from soma.memory.external import FileSource, ExternalKnowledgeImporter
        source = FileSource(source_path)
        importer = ExternalKnowledgeImporter(self)
        return importer.import_source(source, user_id=user_id, session_id=session_id)

    def close(self):
        close_store_connection(self._conn)
