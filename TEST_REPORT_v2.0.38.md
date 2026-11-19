# SOMA v2.0.38 测试报告

## 版本
- **soma-wisdom 2.0.38**（迁移类 CLI 的库路径显式参数）
- 2026-11-20

## 本次变更

下游在生产执行 `soma semantic-kind` dry-run，输出 `scanned: 0`。
CLI 解析的是 `~/.soma/<project>`，而生产库在 `SOMA_DATA_DIR`。

「扫描 0 条」看起来像「库里没有要处理的数据」——运维会跳过迁移，而实际
有 15,299 条图边没被标记。`reclassify` 有同样问题。

### 修复

`semantic-kind` / `reclassify` 增加：

```
--data-dir DIR   直接指定记忆库目录（覆盖 --project）
--db FILE        直接指定 .db 文件（取所在目录，优先于 --data-dir）
```

帮助文本明示：**默认读 `~/.soma/<project>`，不读 `SOMA_DATA_DIR`**。

## 新增测试（+9）

| 文件 | 数量 | 覆盖 |
|------|------|------|
| `tests/test_cli_data_dir.py` | 9 | `--db` 优先级；`--data-dir` 决定 persist_dir；两个命令都接受两个参数；帮助文本必须包含 `SOMA_DATA_DIR` |

### 注入验证

```
_get_soma 忽略 data_dir（改回 _persist_dir(project)）
  → test_persist_dir_follows_data_dir 红
  （实际 persist_dir 落到 ~/.soma/shared）
```

最后一条判据（帮助文本含 SOMA_DATA_DIR）是防复发的：只要帮助不提，
运维看到「扫描 0 条」仍会误读。

## 全量测试（3 轮）

```
1406 passed in 164.59s
1406 passed in 169.11s
1406 passed in 169.59s
```

原有 1397 + 新增 9 = 1406，**三轮零回归**。

## 下游 2.0.37 验证结果

- kind 迁移 15,299 条，与 namespace 规则收敛到同一答案
- 注入只留 fact，图扩展逐位一致
- 稳定性 16/16 全绿，预热 4,662ms PASS，召回不变
- **附带收益**：FTS/LIKE 兜底减少 → wisdom 极差 2.1→0.3、overall 1.2→0.1

## 待下游验证

1. `soma semantic-kind --data-dir <生产库>` 应能扫到 15,312 行
   （已迁移的会显示 changed=0）
2. `soma reclassify --data-dir <生产库>` 同样对齐
