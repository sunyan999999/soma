# SOMA v0.3.1b1 升级说明 / Upgrade Notes

---

## 中文

### 概要

v0.3.1b1 为所有 SQLite 存储库增加了 **FTS5 trigram 全文索引**和 **WAL 日志模式**，大幅提升中文关键词搜索性能。

### 核心变更

| 模块 | 变更 |
|------|------|
| EpisodicStore | 新增 FTS5 trigram 虚拟表，3字及以上关键词走 MATCH 索引（毫秒级），1-2字走 LIKE 兜底 |
| SemanticStore | 新增 FTS5 trigram 索引 + WAL，搜索从 Python 内存遍历改为 SQL 索引查询 |
| SkillStore | 新增 FTS5 trigram 索引 + WAL |
| 全部数据库 | 启用 WAL (Write-Ahead Logging) 模式，读写不再互斥 |

### 兼容性

- **向后兼容**，无需手动迁移
- 首次打开旧数据库时自动创建 FTS 表并回填历史数据
- 不影响现有 API 和记忆数据

### 升级方式

#### 方式一：PyPI（推荐，发布后可用）

```bash
pip install --upgrade soma-wisdom
```

#### 方式二：从 GitHub 安装

```bash
pip install --upgrade git+https://github.com/sunyan999999/soma.git
```

#### 方式三：本地开发安装

```bash
cd /path/to/soma-core
git pull origin master
pip install -e .
```

### 升级后验证

```bash
python -m soma          # 应显示 v0.3.1b1
python -c "from soma import SOMA; s=SOMA(); s.remember('test'); r=s.query_memory('test'); print(f'OK: {len(r)} results')"
```

### 性能提升（预期）

| 指标 | v0.3.0b1 | v0.3.1b1 |
|------|----------|----------|
| 关键词搜索（1万条） | ~100ms | <5ms |
| 关键词搜索（10万条） | ~1000ms | <10ms |
| 并发读写 | 互斥 | 并发 |

### 新增：基准测试 v2（数据量自适应评分）

v0.3.0b1 基准测试固定 top_k=20、延迟阈值 50ms，在大数据量下产生"假降分"。
v0.3.1b1 修复四项设计缺陷：

1. **语义召回 top_k 自适应**：按数据量比例调整（max(20, total×0.15)）
2. **延迟分档阈值**：<500条→30ms, 500-2000→80ms, 2000-10000→150ms, >10000→300ms
3. **合成增益降级**：无消融数据时权重自动重分配，不直接丢 25 分
4. **进化评质量**：最近 30 次反思成功率替代累积总次数

### 新增：SQLite 性能调优

所有存储启用以下 PRAGMA：
- `synchronous=NORMAL` — WAL 模式下安全且更快
- `cache_size=-8000` — 8MB 页面缓存（EpisodicStore）
- `mmap_size=268435456` — 256MB 内存映射（仅 EpisodicStore）
- `busy_timeout=5000` — 5 秒忙等待，减少 SQLITE_BUSY

### 新增：自适应 top_k / recall_threshold

Agent 初始化时根据当前记忆总量自动调整参数，消除小数据集"过度宽松"和大数据集"过度严格"。

---

## English

### Summary

v0.3.1b1 adds **FTS5 trigram full-text indexes** and **WAL journal mode** to all SQLite stores, dramatically improving Chinese keyword search performance.

### Key Changes

| Module | Change |
|--------|--------|
| EpisodicStore | FTS5 trigram virtual table — MATCH index for 3+ char keywords (ms-level), LIKE fallback for 1-2 char |
| SemanticStore | FTS5 trigram index + WAL — search upgraded from Python in-memory scan to SQL indexed query |
| SkillStore | FTS5 trigram index + WAL |
| All databases | WAL (Write-Ahead Logging) mode enabled — concurrent reads no longer blocked by writes |

### Compatibility

- **Backward compatible**, no manual migration required
- Existing databases auto-create FTS tables and backfill on first open
- No changes to public API or existing memory data

### Upgrade

#### Option 1: PyPI (recommended, after release)

```bash
pip install --upgrade soma-wisdom
```

#### Option 2: From GitHub

```bash
pip install --upgrade git+https://github.com/sunyan999999/soma.git
```

#### Option 3: Local dev install

```bash
cd /path/to/soma-core
git pull origin master
pip install -e .
```

### Post-upgrade Verification

```bash
python -m soma          # Should display v0.3.1b1
python -c "from soma import SOMA; s=SOMA(); s.remember('test'); r=s.query_memory('test'); print(f'OK: {len(r)} results')"
```

### Performance Gains (expected)

| Metric | v0.3.0b1 | v0.3.1b1 |
|--------|----------|----------|
| Keyword search (10K records) | ~100ms | <5ms |
| Keyword search (100K records) | ~1000ms | <10ms |
| Concurrent read/write | Mutex-locked | Concurrent |

### New: Benchmark v2 (Data-Scale-Aware Scoring)

v0.3.0b1 benchmark used fixed top_k=20 and 50ms latency threshold, causing unfair score drops at larger data scales. v0.3.1b1 fixes four design flaws:

1. **Semantic recall top_k adaptive**: scales with data count (max(20, total×0.15))
2. **Tiered latency thresholds**: <500→30ms, 500-2000→80ms, 2000-10000→150ms, >10000→300ms
3. **Synthesis gain fallback**: weight redistribution when ablation data is absent (no more automatic 25-point loss)
4. **Evolution quality over quantity**: recent 30-reflection success rate replaces total cumulative count

### New: SQLite Performance Tuning

All stores enable performance PRAGMAs:
- `synchronous=NORMAL` — safe under WAL, faster writes
- `cache_size=-8000` — 8MB page cache (EpisodicStore)
- `mmap_size=268435456` — 256MB memory-mapped I/O (EpisodicStore)
- `busy_timeout=5000` — 5-second busy wait, reduces SQLITE_BUSY errors

### New: Adaptive top_k / recall_threshold

Agent auto-adjusts parameters based on current memory count at init time, eliminating "too loose" at small scale and "too strict" at large scale.

---

## 服务器升级指南 / Server Upgrade Guide

### 零熵智库服务器 (47.94.149.121)

```bash
# 1. SSH 登录
ssh root@47.94.149.121

# 2. 进入项目目录
cd /data/DigitalTwinHub

# 3. 升级 soma-wisdom（PyPI 发布后可用此方式）
pip install --upgrade soma-wisdom

# 或者从源码升级（立即可用）
# pip install --upgrade git+https://github.com/sunyan999999/soma.git

# 4. 验证
python -c "from soma import SOMA; s=SOMA(); print('OK')"

# 5. 重启 SOMA 相关服务
pkill -f "dash/server.py" || true
cd /data/DigitalTwinHub && SOMA_API_KEY=<your-key> nohup python dash/server.py &
```

### 注意事项

- 首次启动时 SOMA 会自动为现有数据库创建 FTS 索引，数据量越大耗时越长（通常秒级完成）
- 数据库文件旁会出现 `.db-wal` 和 `.db-shm` 文件，这是 WAL 模式的正常行为
- 升级不影响正在运行的聊天服务（API 层面无变化）
