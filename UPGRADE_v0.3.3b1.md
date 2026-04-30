# SOMA v0.3.3b1 升级说明 / Upgrade Notes

---

## 中文

### 概要

v0.3.3b1 补全基准测试伸缩性维度持久化、新增五维评分趋势折线图，并完成 SOMA ↔ Glaude 零侵入集成。

### 核心变更

| 模块 | 变更 |
|------|------|
| BenchmarkView | CSS 条形图 → ECharts 五线折线图（总分+四维度），hover 看数值，中英文图例 |
| AnalyticsStore | `benchmark_runs` 表新增 `score_scalability` + `scalability_json` 列，自动迁移兼容旧库 |
| `/api/benchmarks/*` | latest/history/run 响应补全 scalability 分数和数据 |
| SOMA Go Client | 新增 `cmd/soma-hook`（Glaude Hook CLI 桥接），修正所有 API 路径 |
| Glaude 集成 | 3 个 Hook 事件 + 2 个 Skill，自动记录工具执行/召回开发经验 |

### 升级方式

```bash
pip install --upgrade soma-wisdom
```

### 验证

```bash
python -m soma          # 应显示 v0.3.3b1
python -c "from soma import SOMA; s=SOMA(); print('OK')"
```

---

## English

### Summary

v0.3.3b1 adds scalability dimension persistence to benchmarks, a five-line ECharts trend chart, and SOMA↔Glaude zero-intrusion integration.

### Key Changes

| Module | Change |
|--------|--------|
| BenchmarkView | CSS bar chart → ECharts 5-line trend (overall + 4 dims), hover tooltips, i18n legend |
| AnalyticsStore | New columns `score_scalability`/`scalability_json` in `benchmark_runs`, auto-migration |
| `/api/benchmarks/*` | latest/history/run responses now include scalability scores and data |
| SOMA Go Client | New `cmd/soma-hook` (Glaude Hook CLI bridge), all API paths corrected |
| Glaude Integration | 3 Hook events + 2 Skills — auto-record tool executions, recall dev experience |

### Upgrade

```bash
pip install --upgrade soma-wisdom
```

### Verification

```bash
python -m soma          # Should display v0.3.3b1
python -c "from soma import SOMA; s=SOMA(); print('OK')"
```
