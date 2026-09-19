"""进程内 SQLite 连接复用（v2.0.18）。

背景
----
SOMA 的记忆层由多个独立 store 组成（episodic / semantic / profile / scene /
skill / evolver / audit / analytics），历史上每个 store 在自己的 ``__init__``
里各开一条 ``sqlite3.connect``。**单实例下这些连接指向不同的文件**，并不重复；
但多专家架构下（同一进程内多个 agent 各建一套记忆层、或多个 SOMA 实例指向同一
persist_dir），同一个 db 文件会被反复打开 —— 文件句柄数与 WAL 写锁竞争随之线性
增长。本模块提供进程级的连接复用。

复用粒度：**每个 db 文件、每个线程一条**
----------------------------------------
"共享一条连接给所有线程" 看着省得更多，但那是错的。CPython 的 ``sqlite3`` 在
``check_same_thread=False`` 下只解除线程归属检查，**并不保证线程安全**：并发使用
同一条连接时，包装层会复用/重置同一条底层语句，实测（v2.0.18 冒烟）表现为
``InterfaceError: bad parameter or other API misuse`` 与 ``SystemError``，
4 线程 × 25 次写入只落库 31 条 —— 静默丢数据。

因此本模块按 ``(归一化路径, 线程 id)`` 复用：**同一线程内多个 store 复用一条，
不同线程各持一条**。同线程内不存在并发，天然安全；跨线程既不共享连接，也就不共享
语句状态。多专家顺序调用（同一线程）能拿到全部复用收益；并行调用（多线程）至少
不会随实例数再翻倍，且不会有数据风险。

用法
----
store 侧只需两行::

    from soma.db import open_store_connection, close_store_connection

    self._conn = open_store_connection(self._db_path, mmap_size=0)

    def close(self):
        close_store_connection(self._conn)

``shared_sqlite_connection`` 为 False（默认）时，本模块退化为对
``sqlite3.connect`` / ``Connection.close`` 的直通包装，行为与历史完全一致。

**开关只能通过构造参数打开**：``SOMA(..., shared_sqlite_connection=True)``。
构造时会用该参数同步进程级开关，所以「先 ``set_shared_enabled(True)`` 再建实例」
会被构造参数的默认值 False 覆盖回去，现象是「设了没生效」（接入方实测反馈）。
开关是进程级的，多个实例共存时以最后构造者为准 —— 需要它在整个进程内生效时，
就给每个实例都传 ``shared_sqlite_connection=True``。

事务语义
--------
sqlite3 的事务是**连接级**的：同一线程内复用一条连接后，一处 ``commit()`` 会连带
提交另一处尚未提交的写。因此：

- 单条 ``execute`` 后立刻 ``commit`` 的写路径**不受影响**（最终状态一致）；
- 需要「多条语句要么全成、要么全不成」的写路径**必须**用 :func:`transaction`
  包起来 —— 它在持锁期间独占该连接，并自动 commit / 异常回滚。

当前代码库中所有写路径都属于前者（全库没有任何 SQL 级 ``rollback``），
故开启共享对现有语义是无损的；:func:`transaction` 供后续需要原子性的写路径使用。

线程与关闭
----------
连接由**创建它的线程**持有。跨线程关闭（A 线程建、B 线程关）在本模块中是允许的
—— 按连接对象反查注册表，引用计数归零即关闭；但那会让原线程的后续使用命中已关闭
连接并明确报错，属于调用方的用法问题，不静默兜底。

后台线程（如 ``autonomous_background``）首次访问 store 时会为自己建立一份连接，
主线程 ``close()`` 不会代为释放；这类连接随进程结束回收，或用 :func:`reset`
显式清理。

全局状态
--------
"是否启用共享" 是**进程级**开关（它管理的本就是进程级资源）。多个 SOMA 实例同时
存在时，最后构造的那个生效；已建立的连接不受影响，各自按建立时的状态关闭。
"""
import logging
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Tuple

_log = logging.getLogger("soma.db")

# (归一化路径, 线程 id) → 共享条目
_registry: Dict[Tuple[str, int], "_SharedConnection"] = {}
_registry_lock = threading.RLock()

# 进程级开关（由 SOMA 构造时按配置设置）
_enabled = False

# 共享连接的 cache_size 取各 store 中最大的一档（8MB）：对数据量小的库只是
# 多占一点内存，不会更慢。PRAGMA 是连接级的，共享后只能保留一份设置。
_SHARED_CACHE_SIZE_KB = -8000

# 共享关闭时 transaction() 用的空锁，保证调用方无需关心开关
_null_lock = threading.RLock()


class _SharedConnection:
    """一条被同一线程内多处共享的连接 + 它的引用计数。

    只有最后一个持有者归还时才真正 ``close()``。
    """

    __slots__ = ("key", "path", "thread_id", "conn", "refs", "lock")

    def __init__(self, key: Tuple[str, int], path: str, mmap_size: int = 0):
        self.key = key
        self.path = path
        self.thread_id = key[1]
        self.refs = 0
        # 事务边界锁：transaction() 持锁期间独占该连接（同线程可重入）
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._apply_pragmas(int(mmap_size))

    def _apply_pragmas(self, mmap_size: int) -> None:
        """设一套「对全部使用者都安全且够用」的 PRAGMA。

        各 store 自己在 ``_create_table()`` 里的 PRAGMA 仍会照常执行，所以最终
        cache_size 由最晚初始化的 store 决定 —— 那是纯性能差异，不影响正确性。
        """
        try:
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA synchronous=NORMAL")
            self.conn.execute(f"PRAGMA cache_size={_SHARED_CACHE_SIZE_KB}")
            self.conn.execute("PRAGMA busy_timeout=15000")
            self.conn.execute(f"PRAGMA mmap_size={max(0, mmap_size)}")
            self.conn.execute("PRAGMA temp_store=MEMORY")
        except sqlite3.Error:
            _log.debug("共享连接 PRAGMA 设置失败（不影响可用性）", exc_info=True)

    # 下面两个方法都假定调用方持有 _registry_lock（RLock，可重入）

    def acquire(self) -> sqlite3.Connection:
        self.refs += 1
        return self.conn

    def release(self) -> bool:
        """归还一次引用；归零时关闭连接。返回是否真的关闭了底层连接。"""
        with _registry_lock:
            self.refs -= 1
            if self.refs > 0:
                return False
            try:
                self.conn.close()
            except sqlite3.Error:
                _log.debug("共享连接关闭失败", exc_info=True)
            return True


# ── 开关 ────────────────────────────────────────────────


def set_shared_enabled(flag: bool) -> None:
    """设置进程级共享开关。只影响之后新开的连接。

    通常不需要直接调用 —— ``SOMA(...)`` 构造时会用 ``shared_sqlite_connection``
    参数同步这个开关，所以手动设的值很可能在下一个实例构造时被覆盖回去。
    要打开共享连接，请传 ``SOMA(..., shared_sqlite_connection=True)``。
    """
    global _enabled
    _enabled = bool(flag)


def is_shared_enabled() -> bool:
    return _enabled


# ── 连接生命周期 ────────────────────────────────────────


def _key_for(db_path) -> Tuple[str, int]:
    """复用键 = (归一化路径, 当前线程)。"""
    try:
        path = str(Path(db_path).resolve())
    except OSError:
        path = str(db_path)
    return (path, threading.get_ident())


def open_store_connection(db_path, *, mmap_size: int = 0) -> sqlite3.Connection:
    """打开（或复用）一条 store 连接。

    共享关闭时等价于 ``sqlite3.connect(str(db_path), check_same_thread=False)``
    加 ``row_factory = sqlite3.Row``，与历史行为逐字一致。
    """
    if not _enabled:
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    key = _key_for(db_path)
    with _registry_lock:
        entry = _registry.get(key)
        if entry is None:
            entry = _SharedConnection(key, str(db_path), mmap_size=mmap_size)
            _registry[key] = entry
            _log.debug("新建共享连接 %s (thread=%d)", key[0], key[1])
        return entry.acquire()


def _entry_for_conn(conn):
    if conn is None:
        return None
    with _registry_lock:
        for entry in _registry.values():
            if entry.conn is conn:
                return entry
    return None


def close_store_connection(conn) -> bool:
    """关闭一条 store 连接。共享连接走引用计数，归零才真关。

    判据是「这条连接是否在共享注册表里」，而不是当前的开关状态 —— 否则开关中途
    变化会让引用计数错乱。返回是否真的关闭了底层连接。
    """
    if conn is None:
        return False

    with _registry_lock:
        for key, entry in list(_registry.items()):
            if entry.conn is conn:
                closed = entry.release()
                if closed:
                    _registry.pop(key, None)
                    _log.debug("共享连接已关闭并摘除 %s (thread=%d)", key[0], key[1])
                return closed

    # 不在注册表里 → 独立连接（共享关闭时创建的那些）
    try:
        conn.close()
    except sqlite3.Error:
        _log.debug("连接关闭失败", exc_info=True)
    return True


@contextmanager
def transaction(conn):
    """以事务方式独占一条连接。

    进入时取得该连接的事务锁，正常退出时 ``commit()``，发生异常则 ``rollback()``
    后重新抛出。共享模式下这是**唯一**能保证「多条语句原子生效」的方式；共享关闭
    时它就是普通的 commit / rollback 包装，调用方无需分支。

    用法::

        with transaction(store._conn):
            store._conn.execute(...)
            store._conn.execute(...)
    """
    entry = _entry_for_conn(conn)
    lock = entry.lock if entry is not None else _null_lock
    with lock:
        try:
            yield conn
        except Exception:
            try:
                conn.rollback()
            except sqlite3.Error:
                _log.debug("事务回滚失败", exc_info=True)
            raise
        else:
            conn.commit()


# ── 诊断 ────────────────────────────────────────────────


def stats() -> Dict[str, Any]:
    """当前进程内的共享连接情况（供诊断与测试）。

    ``count`` 是连接条目数，``threads`` 是涉及的后台/主线程数 —— 后者大于 1
    说明有多个线程各持一份连接，属预期行为。
    """
    with _registry_lock:
        entries = [
            {"db_path": e.path, "refs": e.refs, "thread": e.thread_id}
            for e in _registry.values()
        ]
    return {
        "enabled": _enabled,
        "count": len(entries),
        "threads": len({e["thread"] for e in entries}),
        "connections": entries,
    }


def reset() -> None:
    """关闭全部共享连接并清空注册表（测试与进程收尾用）。"""
    with _registry_lock:
        for entry in _registry.values():
            try:
                entry.conn.close()
            except sqlite3.Error:
                pass
        _registry.clear()
