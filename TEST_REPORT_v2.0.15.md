# SOMA v2.0.15 测试报告

## 版本
- **soma-wisdom 2.0.15**（接入方收尾：门面透传补齐 + nature 批量重分类 + reload）
- 2026-09-11

## 本次变更

### 1. 门面透传补齐（修复 DSH 反馈的接入缺口）
- `SOMA.remember` / `remember_code` / `remember_image` / `remember_table` 增加 `nature` 参数
- `SOMA.query_memory` 增加 `max_age_days` 参数
- 四层打通：门面 `SOMA` → `SOMA_Agent` → `MemoryCore` → `EpisodicStore`
- 修复前 `SOMA(...).query_memory(..., max_age_days=30)` 抛 `TypeError: unexpected keyword argument`

### 2. 内置 nature 批量重分类（新增 `soma/nature.py`）
- `reclassify_nature()`：默认 `dry_run=True` 只预览；落盘前自动写备份 JSON，**备份失败则中止不改库**
- 内置精度规则（把 DSH 裸 SQL 回填的经验沉淀为默认值）：
  - 状态词（失眠/头痛/焦虑/感冒…）→ `state`
  - 知识来源（wiki/knowledge/external/doc/import）→ `fact`
  - 长文档（>300 字）不归 `state`
  - 默认只处理 `nature='event'` 的存量行，不覆盖已分类数据
- `rollback_nature()`：按备份文件还原
- CLI：`soma reclassify`（默认预览）/ `--apply` / `--rollback`

### 3. `reload()` 向量索引重载
- 外部进程直改 DB 后，已加载实例可主动重载内存 faiss 索引
- 覆盖「删一条 + 加一条（总数不变）」的计数自愈盲区

### 4. 文档
- 新增 `docs/guides/memory-recency.md` + `_zh.md`：写清三层机制分工
  - **近因衰减 `exp(-days/7)` 是主防线**（30 天后权重 <2%，过不了激活阈值）
  - `max_age_days` 是查询期硬截断
  - `is_stale`（仅 `nature=state`）是兜底，覆盖 10–30 天区间
- README / README_zh 增加 Time awareness 小节；mkdocs nav 与 docs/index 索引同步

## 新增测试（+26）

| 文件 | 数量 | 覆盖 |
|------|------|------|
| `tests/test_facade_passthrough.py` | 9 | 门面 remember/remember_code/remember_image/remember_table/query_memory 的 nature 与 max_age_days 透传；含 DSH 生产调用形式回归 |
| `tests/test_nature_reclassify.py` | 17 | NatureClassifier 分类优先级 7 项；reclassify dry_run/落盘/备份/回滚/规则覆盖 8 项；reload 2 项 |

## 全量测试

```
893 passed in 157.13s
```

- 原有 867 用例 + 新增 26 用例，**零回归**（`EXIT=0`）

## 验证亮点

- **门面透传**：`SOMA.query_memory(..., max_age_days=30)` 生产调用形式通过（修复前必现 TypeError）；`nature` 同样四层打通
- **reclassify 真实 CLI 全链路**：写入样本 → `soma reclassify` 预览 → `--apply` 落盘（自动生成备份）→ `--rollback` 还原，DB 层确认分类全对（失眠→state、会写 Python→fact、评审会→event）
- **reload**：外部删一条加一条（总数不变）时，计数自愈会漏，`reload_index()` 兜住

## 环境说明（排查记录）

测试机首次运行时卡在 `test_autonomous.py` 无输出。经 `faulthandler` 抓栈定位：

```
fastembed/model_management.py → huggingface_hub.model_info → socket.create_connection
```

根因：**fastembed 默认把模型缓存放在系统 Temp 目录**（`%LOCALAPPDATA%\Temp\fastembed_cache`），该目录被清理后缓存为空，embedder 每次都要联网下载 `BAAI/bge-small-zh-v1.5`，网络不可达导致挂起。

- **与 2.0.15 代码无关**：`git stash` 后跑基线版本同样复现
- 处理：模型下载到持久路径并设置 `FASTEMBED_CACHE_PATH=C:/Users/suny/.cache/fastembed`
- 设置该变量后全量测试 157s 正常跑完

## wheel

- `dist/soma_wisdom-2.0.15-py3-none-any.whl`
- 已确认不含 `soma-agent` 任何内容（`git ls-files | grep -c 'soma-agent|soma_agent'` = 0）
