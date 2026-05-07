# SOMA v0.7.0 发布证据收集 — 协作计划

> 目标：在正式发布 GitHub/PyPI 前，用零熵智库的真实运行数据 + 本地压力测试，
> 充分证明 v0.7.0 的能力、潜力和稳定性。

## 角色分工

| 角色 | 负责人 | 工作内容 |
|------|--------|------|
| **服务器端** | Qoder | 运行诊断脚本，导出数据，提供运行日志 |
| **本地端** | 开发者 | 接收数据，运行验证脚本，编写综合报告 |

---

## 第一阶段：服务器诊断（Qoder 操作，5分钟）

### 步骤1：上传诊断脚本到服务器

将本目录下的 `server_diagnostic.py` 上传到零熵智库服务器：

```bash
# 放在 soma-core/scripts/ 下
scp scripts/server_diagnostic.py user@server:/opt/soma-core/scripts/
```

### 步骤2：运行诊断

```bash
ssh user@server
cd /opt/soma-core
python scripts/server_diagnostic.py
```

输出文件：`soma_data/diagnostic_v070.json`

### 步骤3：导出数据库（干净副本）

```bash
# 先合并 WAL（不必停服务，但建议在低写入时段执行）
cd soma_data   # 或 $SOMA_DATA_DIR 指向的目录
for f in episodic semantic skills evolver analytics; do
    sqlite3 ${f}.db "PRAGMA wal_checkpoint(TRUNCATE)"
done

# 打包
tar czf /tmp/soma_data_v070_$(date +%Y%m%d).tar.gz *.db diagnostic_v070.json
ls -lh /tmp/soma_data_v070_$(date +%Y%m%d).tar.gz
```

### 步骤4：下载到本地

将以下两个文件发送给开发者：
- `/tmp/soma_data_v070_YYYYMMDD.tar.gz`（数据库 + 诊断JSON）
- 最近3天的服务器日志（如有）

---

## 第二阶段：本地验证（开发者操作）

收到文件后：

### 步骤1：导入数据

```bash
# 解压
tar xzf soma_data_v070_YYYYMMDD.tar.gz -C /tmp/server_import/

# 停掉本地 Dash
pkill -f "dash/server"

# 备份当前数据
cp -r C:/SOMA/soma-core/soma_data C:/SOMA/soma-core/soma_data.bak

# 覆盖
cp /tmp/server_import/*.db C:/SOMA/soma-core/soma_data/
```

### 步骤2：运行本地验证

```bash
cd C:/SOMA/soma-core
SOMA_DATA_DIR=C:/SOMA/soma-core/soma_data python scripts/local_v070_validation.py
```

### 步骤3：运行全量测试

```bash
python -m pytest tests/ -q
```

### 步骤4：运行基准测试（3轮）

```bash
python -m soma.benchmarks --full --runs 3
```

### 步骤5：生成综合报告

将以下数据汇总为 `TEST_REPORT_v0.7.0_FINAL.md`：
1. 服务器诊断 JSON
2. 本地验证 JSON
3. 全量测试结果
4. 基准测试结果

---

## 第三阶段：报告编写（开发者操作）

### 报告结构

```
## 1. 版本概要
- v0.7.0 三大能力 + 两项优化
- 341 项测试全通过

## 2. 生产环境验证（零熵智库）
- 运行时长、记忆规模
- 合并引擎：去重率 X%
- 遗忘引擎：归档率 X%
- 进化状态：权重分布、触发词候选
- LLM 重试：成功率 X%

## 3. 本地压力测试
- 真实数据管道耗时
- 探索因子触发情况
- 合并/遗忘引擎功能验证

## 4. 基准测试对比
- v0.6.1 vs v0.7.0 五项指标
- 无性能退化证明

## 5. 结论
- 生产就绪评级
- 发布建议
```

---

## 检查清单

- [ ] Qoder 运行 server_diagnostic.py，产出 diagnostic_v070.json
- [ ] Qoder 导出干净数据库 tar.gz，发给开发者
- [ ] 开发者导入数据，运行 local_v070_validation.py
- [ ] 开发者运行全量测试（341 passed）
- [ ] 开发者运行基准测试（3轮，无退化）
- [ ] 开发者编写 FINAL 报告
- [ ] 发布 GitHub Release + PyPI
