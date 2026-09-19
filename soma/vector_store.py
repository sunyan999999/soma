"""向量索引 — 基于 SQLite BLOB + faiss HNSW 近邻搜索

v1.0.1: 支持持久化 FAISS 索引（磁盘读写），增量更新避免每次全量重建。
"""

import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

_log = logging.getLogger("soma.vector")


class NumpyVectorIndex:
    """将嵌入向量存为 SQLite BLOB，提供 faiss 加速的余弦相似度搜索

    与 EpisodicStore 共用同一数据库和表，通过 BLOB 列存储向量。

    索引策略:
    - <1000 条: IndexFlatIP（精确内积搜索）
    - >=1000 条: IndexHNSWFlat（近似搜索，M=32, efConstruction=200）

    v1.0.1 持久化:
    - FAISS 索引写入 {db_path}.faiss_index 文件
    - ID 映射写入 {db_path}.faiss_id_map.json
    - 重启后优先加载磁盘索引，避免全量重建
    - store_vector 时增量更新 FAISS 索引，积累超过 1000 次增量后全量重建
    """

    _INCREMENTAL_LIMIT = 1000
    _SAVE_BATCH = 50  # v2.0.2: 批量保存，50次增量写一次磁盘
    # v2.0.18: 过期向量清理阈值 —— 索引里已删除记忆的残留向量少于「32 条且不足
    # 索引总量的 5%」时不值得重建（HNSW 全量构造要数秒），留着由搜索侧跳过即可。
    _PRUNE_MIN_STALE = 32
    _PRUNE_STALE_RATIO = 0.05
    # v2.0.18.2: 前置过滤时「按条件取向量 + 精确内积」的扫描上限。取到这么多条还
    # 没命中，说明该用户/分组已经接近全库规模 —— 那时全局候选里的占比也高，
    # post-filter 的召回损失很小，逐条精确扫描反而更贵，于是退回全局检索。
    _MAX_FILTER_SCAN = 10000
    # 退回全局检索时多取的候选倍数 —— 仍要按条件过滤，取太少等于没修
    _DEGRADED_FETCH_FACTOR = 30
    # 过滤子集占全库的比例上限。超过它就不做前置过滤 —— 子集这么大时全局候选里
    # 天然有足够多属于该用户，post-filter 的召回损失可以忽略，而逐条精确扫描
    # （要读全部向量字节）反而比 faiss 慢。单租户部署（一个 user_id 装下全库）
    # 走的就是这条，行为与 v2.0.18.1 完全一致。
    _MAX_FILTER_SHARE = 0.15

    def __init__(self, db_path: Path, vector_dim: int):
        self._db_path = db_path
        self._vector_dim = vector_dim
        self._faiss_index = None
        self._faiss_id_to_mem: dict = {}
        self._mem_to_faiss_id: dict = {}
        self._index_type = "none"
        self._cached_count = -1
        self._incremental_adds = 0
        self._rebuild_busy = False    # v2.0.14: 后台重建进行中标志（防止并发重建）
        # v2.0.18: 保护「索引对象 + 两个 ID 映射」这三件套的一致性。后台重建是逐个
        # 赋值替换它们的，主线程若在中间读，会拿到「旧索引 + 新映射」这类错配组合，
        # 从而把向量认成别的记忆（实测复现过）。持有它的时间都很短——重建侧只覆盖
        # 赋值那几步，磁盘写落在锁外；搜索侧覆盖到结果组装完。
        self._state_lock = threading.RLock()
        self._faiss_index_path = db_path.parent / (db_path.stem + ".faiss_index")
        self._faiss_id_map_path = db_path.parent / (db_path.stem + ".faiss_id_map.json")

    def ensure_table(self, conn):
        """向 episodic_memories 表添加 vector BLOB 列（幂等操作）"""
        try:
            conn.execute(
                f"ALTER TABLE episodic_memories ADD COLUMN vector BLOB"
            )
            conn.commit()
        except Exception:
            pass

    # ── 磁盘持久化 ──────────────────────────────────────────────

    def _save_index_to_disk(self):
        """将 FAISS 索引和 ID 映射原子地写入磁盘（v2.0.18.1）。

        原先直接 ``faiss.write_index(index, 目标路径)``，有两个真实后果：

        - **写一半被打断即留下半成品**：进程退出、磁盘写满，或另一个进程此刻正
          打开该文件读取（Windows 下会直接写失败）。接入方生产上出现过
          ``read error ... 43126570 != 55224480``，即文件被截断，于是每个新进程
          启动都得重建一次索引 —— 代价是每次启动白付一次全量 HNSW 构造。
        - **并发写互相破坏**：``_build_faiss_index`` 的磁盘写在锁外，主线程的
          同步重建与后台剪枝线程（_prune_async）的写盘可以同时发生，两者写同一个
          文件必然写坏。

        现改为：临时文件名带上 pid 与线程 id，并发写各自落在自己的文件上，最后用
        ``os.replace`` 原子替换 —— 读方要么看到完整的旧文件，要么看到完整的新文件，
        不会有中间态。
        """
        import faiss

        if self._faiss_index is None:
            return
        suffix = f".{os.getpid()}.{threading.get_ident()}.tmp"
        idx_tmp = Path(str(self._faiss_index_path) + suffix)
        map_tmp = Path(str(self._faiss_id_map_path) + suffix)
        try:
            faiss.write_index(self._faiss_index, str(idx_tmp))
            with open(map_tmp, "w", encoding="utf-8") as f:
                json.dump({
                    "faiss_to_mem": {str(k): v for k, v in self._faiss_id_to_mem.items()},
                    "mem_to_faiss": self._mem_to_faiss_id,
                    "cached_count": self._cached_count,
                    "incremental_adds": self._incremental_adds,
                }, f)
            # 两个文件无法真正「一起」替换，但 os.replace 只是元数据操作，
            # 中间窗口极小；加载侧另有 index.ntotal 与 id_map 的一致性校验兜底。
            os.replace(idx_tmp, self._faiss_index_path)
            os.replace(map_tmp, self._faiss_id_map_path)
        except Exception as e:
            _log.warning("保存 FAISS 索引到磁盘失败: %s", e)
            for p in (idx_tmp, map_tmp):
                try:
                    if p.exists():
                        p.unlink()
                except Exception:
                    pass

    def _cleanup_stale_tmp(self):
        """清掉崩溃残留的临时索引文件（超过 1 小时未动过的）。

        正常写盘只需数秒，1 小时的宽限足以避开任何正在进行的写入，同时避免
        临时文件在磁盘上越积越多（一份 HNSW 索引可达数十 MB）。
        """
        try:
            cutoff = time.time() - 3600
            parent = self._faiss_index_path.parent
            for name in (self._faiss_index_path.name, self._faiss_id_map_path.name):
                for p in parent.glob(name + ".*.tmp"):
                    try:
                        if p.stat().st_mtime < cutoff:
                            p.unlink()
                    except Exception:
                        pass
        except Exception:
            pass

    def _load_index_from_disk(self) -> bool:
        """从磁盘加载 FAISS 索引和 ID 映射。成功返回 True。

        v2.0.18.1: 加载后校验索引与映射自洽（见下）。失败一律返回 False 交给调用方
        重建 —— 重建后写出的文件是完整的，所以正常只会重建这一次，而不是每次启动
        都重建（截断文件那种情况正是接入方在生产上遇到的）。
        """
        import faiss

        self._cleanup_stale_tmp()
        if not self._faiss_index_path.exists() or not self._faiss_id_map_path.exists():
            return False
        try:
            index = faiss.read_index(str(self._faiss_index_path))
            with open(self._faiss_id_map_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            id_to_mem = {int(k): v for k, v in data["faiss_to_mem"].items()}
            n = index.ntotal

            # 索引里的每个 faiss_id 都必须能在映射里找到落点，且条数对得上。
            # 不校验的话，「索引与映射错配」会一路静默：命中的向量在映射里查不到
            # mem_id 而被丢弃（表现为莫名其妙召回不全），同时两侧计数对不上又被
            # 搜索路径当成「有待剪枝」，反复触发全表 COUNT。
            if (len(id_to_mem) != n
                    or min(id_to_mem, default=0) < 0
                    or max(id_to_mem, default=-1) >= n):
                raise ValueError(
                    f"索引与 ID 映射不一致: index.ntotal={n}, "
                    f"id_map={len(id_to_mem)} 条"
                )

            self._faiss_index = index
            self._faiss_id_to_mem = id_to_mem
            self._mem_to_faiss_id = data.get("mem_to_faiss", {})
            self._cached_count = data.get("cached_count", n)
            self._incremental_adds = data.get("incremental_adds", 0)

            if n < 1000:
                self._index_type = "flat"
            else:
                self._index_type = f"hnsw(n={n})"
            return True
        except Exception as e:
            try:
                size = self._faiss_index_path.stat().st_size
            except Exception:
                size = -1
            _log.warning(
                "从磁盘加载 FAISS 索引失败: %s（文件 %d 字节），将重建",
                e, size,
            )
            self._faiss_index = None
            return False

    # ── 索引构建（持久化） ─────────────────────────────────────

    def _build_faiss_index(self, ids: List[str], vecs: np.ndarray):
        """(重)构建 faiss 索引并写入磁盘

        v2.0.18: 重建可能发生在后台线程（_rebuild_async / _prune_async）。索引构造
        与磁盘写这类耗时步骤留在锁外，只在替换三件套时短暂持锁，让主线程要么看到
        旧的一套、要么看到新的一套，不会读到错配的组合。
        """
        import faiss

        n = len(ids)
        if n == 0:
            with self._state_lock:
                self._faiss_index = None
                self._faiss_id_to_mem = {}
                self._mem_to_faiss_id = {}
                self._index_type = "none"
                self._incremental_adds = 0
            # 清理磁盘文件
            if self._faiss_index_path.exists():
                self._faiss_index_path.unlink()
            if self._faiss_id_map_path.exists():
                self._faiss_id_map_path.unlink()
            return

        if n < 1000:
            index = faiss.IndexFlatIP(self._vector_dim)
            index_type = "flat"
        else:
            index = faiss.IndexHNSWFlat(self._vector_dim, 32)
            index.hnsw.efConstruction = 200
            index.hnsw.efSearch = 64        # v1.1.7-clean: recall提升0.7→0.9
            index_type = f"hnsw(n={n})"

        index.add(vecs.astype(np.float32))
        id_to_mem = {i: mid for i, mid in enumerate(ids)}
        mem_to_id = {mid: i for i, mid in enumerate(ids)}
        with self._state_lock:
            self._faiss_index = index
            self._faiss_id_to_mem = id_to_mem
            self._mem_to_faiss_id = mem_to_id
            self._index_type = index_type
            self._incremental_adds = 0
        self._save_index_to_disk()

    # ── 增量更新 ────────────────────────────────────────────────

    def _incremental_add(self, memory_id: str, vector: np.ndarray):
        """向已有 FAISS 索引增量添加单个向量"""
        if self._faiss_index is None:
            return False

        vec = vector.reshape(1, -1).astype(np.float32)
        with self._state_lock:
            new_id = self._faiss_index.ntotal
            self._faiss_index.add(vec)
            self._faiss_id_to_mem[new_id] = memory_id
            self._mem_to_faiss_id[memory_id] = new_id
            self._cached_count += 1
            self._incremental_adds += 1
        return True

    def _maybe_rebuild(self, conn):
        """增量添加过多 → 后台异步全量重建（插入不阻塞）

        v2.0.14: 原实现同步重建（HNSW 全量 + 磁盘写 ~5s）会阻塞插入。
        现改为：主线程只做轻量快照读取（get_all_vectors，读 DB 快），
        faiss 重建 + 磁盘写放后台线程。重建期间的少量增量仍写 DB，
        由 similarity_search 的一致性检查（失步自愈）兜底补入。
        """
        if self._incremental_adds < self._INCREMENTAL_LIMIT:
            return
        with self._state_lock:
            if self._rebuild_busy:
                return  # 已有后台重建在跑，避免并发重建
            try:
                ids, vecs = self.get_all_vectors(conn)
            except Exception as e:
                _log.warning("后台重建读取向量失败: %s", e)
                return
            if not ids:
                return
            self._cached_count = len(ids)
            self._rebuild_busy = True
        _log.info("增量添加达 %d 次，后台异步全量重建索引 (n=%d)",
                  self._incremental_adds, len(ids))
        threading.Thread(
            target=self._rebuild_async, args=(ids, vecs),
            daemon=True, name="soma-vector-rebuild",
        ).start()

    def _rebuild_async(self, ids: List[str], vecs: np.ndarray):
        """后台线程执行 faiss 全量重建 + 磁盘写入（插入线程不等待）"""
        try:
            self._build_faiss_index(ids, vecs)
        except Exception as e:
            _log.warning("后台全量重建失败: %s", e)
        finally:
            self._rebuild_busy = False

    # ── 公共接口 ────────────────────────────────────────────────

    def store_vector(self, conn, memory_id: str, vector: np.ndarray):
        """存储嵌入向量并增量更新 FAISS 索引

        v2.0.18: 整段持 _state_lock —— 「写库 + 入索引」必须相对搜索侧的重建保持
        原子。否则重建已经把这条读进快照、这里又增量加一次，索引就多出一条重复
        （表现为 ntotal 比 DB 有效数大，且再也对不上）。
        """
        import faiss

        blob = vector.astype(np.float32).tobytes()
        with self._state_lock:
            conn.execute(
                "UPDATE episodic_memories SET vector = ? WHERE id = ?",
                (blob, memory_id),
            )
            conn.commit()

            # 增量添加到 FAISS 索引（v2.0.2: 批量保存，减少磁盘IO）
            if self._faiss_index is not None:
                faiss.normalize_L2(vector.reshape(1, -1))
                if self._incremental_add(memory_id, vector):
                    # v2.0.2: 每 _SAVE_BATCH 次增量才写一次磁盘
                    if self._incremental_adds % self._SAVE_BATCH == 0:
                        self._save_index_to_disk()
                    self._maybe_rebuild(conn)
                    return
            # 索引未构建或增量添加失败 → 下次搜索时重建
            self._cached_count = -1

    def get_all_vectors(
        self, conn
    ) -> Tuple[List[str], np.ndarray]:
        """获取所有已索引的记忆 ID 和向量矩阵 (N, dim)"""
        rows = conn.execute(
            "SELECT id, vector FROM episodic_memories WHERE vector IS NOT NULL"
        ).fetchall()

        if not rows:
            return [], np.empty((0, self._vector_dim), dtype=np.float32)

        ids = []
        vecs = np.empty((len(rows), self._vector_dim), dtype=np.float32)
        for i, row in enumerate(rows):
            ids.append(row[0])
            vecs[i] = np.frombuffer(row[1], dtype=np.float32)
        return ids, vecs

    def _build_filter_clause(
        self, user_id: str, agent_id: str, group_id: str,
        max_age_days: Optional[float],
    ) -> Tuple[str, list]:
        """构造**检索前**的隔离/时间条件，口径与 fts5_keyword_search 对齐。

        - user_id：精确匹配（空串 = 不过滤，单用户部署的常态）
        - agent_id：自己的 OR 组共享的（与关键词通道、与调用方的 post-filter 同义）
        - max_age_days：时间窗口硬截断

        返回 (WHERE 片段, 参数)。片段以 " AND " 开头，便于拼在既有 WHERE 之后。
        """
        conds: List[str] = []
        params: list = []
        if user_id:
            conds.append("user_id = ?")
            params.append(user_id)
        if agent_id and group_id:
            conds.append("(agent_id = ? OR shared_group_id = ?)")
            params.extend([agent_id, group_id])
        elif agent_id:
            conds.append("agent_id = ?")
            params.append(agent_id)
        if max_age_days is not None:
            min_ts = datetime.now(timezone.utc).timestamp() - max_age_days * 86400.0
            conds.append("timestamp >= ?")
            params.append(min_ts)
        return (" AND " + " AND ".join(conds)) if conds else "", params

    def _exact_filtered_search(
        self, conn, query_vec: np.ndarray, top_k: int,
        user_id: str, agent_id: str, group_id: str,
        max_age_days: Optional[float],
    ) -> Tuple[Optional[List[Tuple[str, float]]], int]:
        """在**过滤后的子集**内做精确 top-k（v2.0.18.2）。

        返回 ``(命中列表, 1)``；若判定不该走前置过滤，返回 ``(None, 倍数)`` 让调用
        方退回全局检索 + post-filter —— 倍数是要额外多取多少候选（见 ``_MAX_FILTER_SHARE``
        与 ``_MAX_FILTER_SCAN`` 两处退回原因的区别）。

        为什么必须前置过滤
        ------------------
        原先的做法是先全局取候选、再由调用方 ``mem.user_id != user_id`` 剔除。多租户下
        单个用户的记忆占全库比例很低，候选里几乎没有他的记忆 —— 接入方 27,008 条 /
        130 用户的分布下，中位用户（17 条，占 0.06%）取 45 条候选的期望命中不足
        0.05 条。**向量通道对多数用户等于失效**，而它是 RRF 融合里的主通道（权重 2.0）。
        关键词通道本来就是 SQL 前置过滤（``AND t.user_id = ?``），两条通道此前时机
        不一致。

        为什么不用 faiss 的 IDSelector
        ------------------------------
        实测在 IndexHNSWFlat 上，``IDSelector`` 只过滤「图遍历可达」的点：efSearch
        之内的候选本来就有限，探不到的子集成员直接丢失。400 条的用户实测只命中 1 条
        —— 比不修还差（全局 post-filter 那时也能命中 1 条）。子集内的精确 top-k 只能
        靠穷举该子集，而这恰好很便宜（见下）。

        代价（实测，384 维，≈25k 其他行，k=45，打的是本方法的真实代码路径）
        ----------------------------------------------------------------
        子集 17 条 0.18ms / 500 条 2.3ms / 1000 条 6.5ms / 2137 条 18.7ms。
        接入方最大单用户 2,137 条 → 18.7ms，同一台机器上**同库的无过滤 faiss 路径
        是 46ms**（它每次搜索都要跑一次 25k 行的全表 COUNT）。也就是说这条修复不光
        召回正确，在真实分布下还比 v2.0.18.1 快 —— 所以不加缓存，每次直扫。
        """
        clause, params = self._build_filter_clause(
            user_id, agent_id, group_id, max_age_days)
        if not clause:
            return None, 1

        row = conn.execute(
            f"SELECT COUNT(*) FROM episodic_memories "
            f"WHERE vector IS NOT NULL{clause}", params
        ).fetchone()
        n = int(row[0]) if row else 0
        if n == 0:
            return [], 1
        if n > self._MAX_FILTER_SCAN:
            _log.warning(
                "前置过滤子集 %d 条超过扫描上限 %d，退回全局检索 + post-filter "
                "（该条件下召回可能不足，建议排查是否有超大用户）",
                n, self._MAX_FILTER_SCAN)
            return None, self._DEGRADED_FETCH_FACTOR
        # 子集大到接近全库时前置过滤没有收益（全局候选里本来就有足够多该用户的
        # 记忆），而逐条读向量比 faiss 慢。**这里倍数取 1**：post-filter 在这种
        # 占比下几乎不丢东西，放大候选只会让单用户部署白白多算 —— 它的行为必须与
        # v2.0.18.1 完全一致。分母用索引内的总数，它在内存里，不额外花那次被人
        # 抱怨过的全表 COUNT。
        index_total = self._faiss_index.ntotal if self._faiss_index is not None else 0
        if index_total and n > index_total * self._MAX_FILTER_SHARE:
            return None, 1

        rows = conn.execute(
            f"SELECT id, vector FROM episodic_memories "
            f"WHERE vector IS NOT NULL{clause}", params
        ).fetchall()
        ids: List[str] = []
        vecs: List[np.ndarray] = []
        for r in rows:
            if r[1] is None:
                continue
            v = np.frombuffer(r[1], dtype=np.float32)
            # 维度不符的历史脏数据直接跳过 —— 否则 vstack 会整次炸掉
            if v.shape[0] != self._vector_dim:
                continue
            ids.append(r[0])
            vecs.append(v)
        if not ids:
            return [], 1
        if top_k <= 0:
            return [], 1

        mat = np.vstack(vecs)
        q = np.asarray(query_vec, dtype=np.float32).reshape(-1)
        if q.shape[0] != self._vector_dim:
            return [], 1
        # 两侧都归一化后再内积 = 余弦。faiss 侧入库时做过 normalize_L2（store_vector），
        # 所以分数与全局路径同口径 —— 即使嵌入器没归一化也对得上；不这么做的话
        # |v| 会混进分数，子集内的排序都会变。零向量保持原样（不影响后续 argsort）。
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        np.divide(mat, norms, out=mat, where=norms > 0)
        qn = float(np.linalg.norm(q))
        if qn > 0:
            q = q / qn
        sims = mat @ q
        k = min(top_k, len(ids))
        # argpartition 取前 k，再对前 k 排序 —— 大子集下比全排序快
        order = np.argpartition(-sims, k - 1)[:k] if k < len(ids) else np.arange(len(ids))
        order = order[np.argsort(-sims[order])]
        return [(ids[int(i)], float(sims[int(i)])) for i in order], 1

    def similarity_search(
        self, conn, query_vec: np.ndarray, top_k: int = 5, *,
        user_id: str = "", agent_id: str = "", group_id: str = "",
        max_age_days: Optional[float] = None,
    ) -> List[Tuple[str, float]]:
        """余弦相似度搜索，返回 [(memory_id, score), ...] 按分数降序

        优先使用持久化 FAISS 索引（磁盘加载或增量更新），仅在计数变化且无
        可用缓存时触发全量重建。

        v2.0.18: 整个方法持 _state_lock —— 后台重建会在另一个线程替换「索引 + 两个
        映射」，不持锁的话可能在半途读到错配组合（表现为查到别的记忆）。

        v2.0.18.2: 新增隔离/时间参数。传了 user_id 或 agent_id 时改走
        :meth:`_exact_filtered_search` —— 在过滤后的子集内精确取 top-k，而不是先
        全库取候选再让调用方剔除（后者在多租户下召回趋近于 0）。不传时走原 FAISS
        路径，行为与性能完全不变。

        注意有过滤的路径**不需要 faiss 索引**（直接读库做内积），所以它不经过下面的
        「索引未构建则重建」分支 —— 索引还没热起来时它照样能正确召回。
        """
        with self._state_lock:
            # conn 是 check_same_thread=False 的共享连接（并不线程安全），锁内还会
            # 与后台剪枝/重建线程竞争同一连接，所以过滤分支必须在锁内读库。
            if user_id or agent_id or max_age_days is not None:
                exact, factor = self._exact_filtered_search(
                    conn, query_vec, top_k, user_id, agent_id, group_id,
                    max_age_days)
                if exact is not None:
                    return exact
                # 退回全局检索。只有「子集超过扫描上限」才放大候选（那种占比下
                # post-filter 真的会丢东西）；「子集≈全库」时倍数就是 1，与
                # v2.0.18.1 的行为逐字一致。
                if factor > 1:
                    top_k = max(top_k * factor, top_k + 200)

            current_count = self.count_indexed(conn)
            if current_count == 0:
                return []

            # 尝试从磁盘加载（首次调用或缓存失效后）
            if self._faiss_index is None:
                if not self._load_index_from_disk():
                    ids, vecs = self.get_all_vectors(conn)
                    self._build_faiss_index(ids, vecs)
                    self._cached_count = current_count

            # 缓存一致性：DB 与 faiss 索引不一致时从 DB 全量重建
            # 覆盖两类失步：
            #   current_count > ntotal  新增向量未入索引（增量失败/异常）
            #   current_count < ntotal  删除后的残留向量（faiss 无法精确删除）
            if self._faiss_index is not None and current_count != self._cached_count:
                if current_count == self._faiss_index.ntotal:
                    # 仅计数未同步，更新即可
                    self._cached_count = current_count
                elif current_count > self._faiss_index.ntotal:
                    # DB 比索引多：有向量没进索引，不补齐会漏召回 → 同步重建
                    ids, vecs = self.get_all_vectors(conn)
                    self._build_faiss_index(ids, vecs)
                    self._cached_count = len(ids)
                else:
                    # DB 比索引少：有记忆被删除（forgetting 直接删行，不通知索引），
                    # 索引里留着残留向量。v2.0.18 起不再为此同步全量重建（实测会
                    # 阻塞搜索数秒）：本次搜索已按 stale 补偿取 k（残留条目要么取
                    # 不到 mem_id 被跳过，要么由调用方查库过滤），清理交给后台剪枝。
                    self._cached_count = current_count
                    # v2.0.18.1: 把上面刚算出的差值直接交给剪枝判定 —— 否则
                    # _should_prune 会再跑一次同样的全表 COUNT（P2）。
                    self._schedule_prune(
                        conn, stale=self._faiss_index.ntotal - current_count)

            index = self._faiss_index
            if index is None or index.ntotal == 0:
                return []

            query_vec = query_vec.reshape(1, -1).astype(np.float32)
            # v2.0.18: 索引里可能残留「DB 已删除」的向量。它们会占住 top_k 名额
            # —— 按索引条目数与 DB 有效数之差补偿取 k。
            stale = max(0, index.ntotal - current_count)
            k = min(top_k + stale, index.ntotal)
            distances, indices = index.search(query_vec, k)

            id_map = self._faiss_id_to_mem
            results = []
            for i in range(k):
                faiss_id = int(indices[0][i])
                mem_id = id_map.get(faiss_id)
                if mem_id is not None:
                    score = float(distances[0][i])
                    results.append((mem_id, score))

            return results

    def delete_vector(self, conn, memory_id: str):
        """删除向量（索引里对应条目留待后台清理，不再同步重建）"""
        with self._state_lock:
            conn.execute(
                "UPDATE episodic_memories SET vector = NULL WHERE id = ?",
                (memory_id,),
            )
            conn.commit()
            # 删除后无法从 HNSW 索引中精确移除，标记为过期
            if memory_id in self._mem_to_faiss_id:
                faiss_id = self._mem_to_faiss_id.pop(memory_id)
                # v2.0.18: 反向映射必须同步清理 —— 否则残留向量在搜索时仍能取到
                # mem_id 而占住 top_k 名额（原先只删了正向映射，是个真缺陷）。
                self._faiss_id_to_mem.pop(faiss_id, None)
                self._cached_count = max(0, self._cached_count - 1)

    # ── 过期向量清理（v2.0.18）──────────────────────────────────
    # 记忆被删除时（forgetting 直接 DELETE 行，不经过 index），faiss 索引里会
    # 留下再也对不上任何记忆的残留向量。HNSW 不支持精确删除，全量重建又要数秒；
    # 这里做的是「只清理这部分」：用 reconstruct 把仍然有效的向量从内存索引里
    # 抽出来重建成新索引，不读 DB 取向量、不重新编码。

    def _valid_ids(self, conn) -> set:
        """DB 里仍有向量的记忆 id 集合 —— 也就是索引本该包含的条目。"""
        rows = conn.execute(
            "SELECT id FROM episodic_memories WHERE vector IS NOT NULL"
        ).fetchall()
        return {r[0] for r in rows}

    def stale_count(self, conn) -> int:
        """索引里比 DB 多出来的条目数 —— 即「已删除但尚未清理」的过期向量数。"""
        index = self._faiss_index
        if index is None:
            return 0
        return max(0, index.ntotal - self.count_indexed(conn))

    def _should_prune(self, conn, stale: Optional[int] = None) -> bool:
        """是否有足够多的过期向量值得清理。

        ``stale`` 允许调用方复用已算好的差值（v2.0.18.1）：``stale_count()``
        内部要跑一次全表 COUNT，而搜索热路径在调本方法之前刚算过同一个数
        （``index.ntotal - current_count``），再算一次纯属重复。
        """
        if stale is None:
            stale = self.stale_count(conn)
        if stale <= 0:
            return False
        index = self._faiss_index
        total = index.ntotal if index is not None else 0
        return (stale >= self._PRUNE_MIN_STALE
                or stale >= total * self._PRUNE_STALE_RATIO)

    def _schedule_prune(self, conn, stale: Optional[int] = None) -> bool:
        """按阈值触发一次后台清理；已有重建在跑时跳过。返回是否已调度。"""
        if self._rebuild_busy or not self._should_prune(conn, stale):
            return False
        return bool(self.prune_stale(conn, background=True).get("scheduled"))

    def wait_idle(self, timeout: float = 120.0) -> bool:
        """等待后台重建/清理结束（v2.0.18）。返回是否已空闲。"""
        deadline = time.time() + timeout
        while self._rebuild_busy and time.time() < deadline:
            time.sleep(0.05)
        return not self._rebuild_busy

    def prune_stale(self, conn, background: bool = True) -> dict:
        """清理过期向量：把索引中「DB 已无有效向量」的条目剔除。

        耗时部分（HNSW 构造 + 磁盘写）放后台线程；主线程只做内存拷贝级的快照。
        这个切分是必须的：``reconstruct`` 读的是**正在被主线程使用**的那个索引
        对象，若放后台与主线程的增量 add 并发，faiss 内部数组重分配会让它读到
        已释放内存（段错误），而不是抛一个能捕获的异常。

        返回 ``{pruned, remaining, rebuilt, scheduled}``。

        ``background=False`` 的语义是「清完再返回」：若已有后台任务在跑，先等它
        让位再清。否则会空转返回一个 ``pruned=0``，调用方（运维脚本、自检）很
        容易把它误读成「没有残留」—— 而真相是「还没轮到清」。
        """
        if not background and self._rebuild_busy:
            self.wait_idle()

        with self._state_lock:
            index = self._faiss_index
            if index is None or index.ntotal == 0:
                return {"pruned": 0, "remaining": 0,
                        "rebuilt": False, "scheduled": False}
            if self._rebuild_busy:
                return {"pruned": 0, "remaining": index.ntotal,
                        "rebuilt": False, "scheduled": False, "busy": True}

            id_map = self._faiss_id_to_mem
            valid = self._valid_ids(conn)
            kept = [(i, id_map.get(i)) for i in range(index.ntotal)]
            kept = [(i, mid) for i, mid in kept if mid in valid]
            pruned = index.ntotal - len(kept)
            if pruned <= 0:
                return {"pruned": 0, "remaining": index.ntotal,
                        "rebuilt": False, "scheduled": False}

            ids = [mid for _i, mid in kept]
            if ids:
                vecs = np.empty((len(ids), self._vector_dim), dtype=np.float32)
                for row, (i, _mid) in enumerate(kept):
                    index.reconstruct(int(i), vecs[row])
            else:
                vecs = np.empty((0, self._vector_dim), dtype=np.float32)

            if not background:
                rebuild_now = True
            else:
                # 在锁内占位，避免两次调度同时通过上面的 busy 检查
                self._rebuild_busy = True
                self._cached_count = len(ids)
                rebuild_now = False

        if rebuild_now:
            self._build_faiss_index(ids, vecs)
            self._cached_count = len(ids)
            _log.info("清理过期向量: 移除 %d 条, 剩余 %d 条 (同步)", pruned, len(ids))
            return {"pruned": pruned, "remaining": len(ids),
                    "rebuilt": True, "scheduled": False}

        threading.Thread(
            target=self._prune_async, args=(ids, vecs),
            daemon=True, name="soma-vector-prune",
        ).start()
        _log.info("清理过期向量: 移除 %d 条, 剩余 %d 条 (后台)", pruned, len(ids))
        return {"pruned": pruned, "remaining": len(ids),
                "rebuilt": False, "scheduled": True}

    def _prune_async(self, ids: List[str], vecs: np.ndarray):
        """后台执行清理后的索引重建 + 磁盘写入。"""
        try:
            self._build_faiss_index(ids, vecs)
        except Exception as e:
            _log.warning("后台清理过期向量失败: %s", e)
        finally:
            self._rebuild_busy = False

    def count_indexed(self, conn) -> int:
        row = conn.execute(
            "SELECT COUNT(*) FROM episodic_memories WHERE vector IS NOT NULL"
        ).fetchone()
        return row[0] if row else 0

    def clear_incompatible_vectors(self, conn) -> int:
        """清除维度不匹配的旧向量，返回清除数量"""
        rows = conn.execute(
            "SELECT id, vector FROM episodic_memories WHERE vector IS NOT NULL"
        ).fetchall()
        stale = 0
        for row in rows:
            vec = np.frombuffer(row[1], dtype=np.float32)
            if len(vec) != self._vector_dim:
                conn.execute(
                    "UPDATE episodic_memories SET vector = NULL WHERE id = ?",
                    (row[0],),
                )
                stale += 1
        if stale > 0:
            conn.commit()
            self._cached_count = -1
        return stale
