# SOMA v0.6.1 基准测试报告

| 项目 | 数值 |
|------|------|
| 版本 | 0.6.1 |
| 测试轮次 | 3 轮独立运行 |
| 数据规模 | small |
| 总耗时 | 11.3s |

## 综合评分

| 维度 | 均值 | 标准差 | 95%置信区间 | CV% | 稳定性 | 范围 |
|------|------|--------|-------------|-----|--------|------|
| overall | 64.8 | ±0.1 | [64.69, 64.91] | 0.15% | ● stable | [64.7, 64.9] |
| memory | 95.2 | ±0.17 | [95.0, 95.4] | 0.18% | ● stable | [95.1, 95.4] |
| wisdom | 75.0 | ±0.17 | [74.8, 75.2] | 0.23% | ● stable | [74.8, 75.1] |
| evolution | 17.5 | ±0.0 | [17.5, 17.5] | 0.0% | ● stable | [17.5, 17.5] |
| scalability | -1.0 | ±0.0 | [-1.0, -1.0] | -0.0% | ● stable | [-1.0, -1.0] |

## 波动较大的细分指标

| 指标 | 均值 | 标准差 | CV% | 稳定性 |
|------|------|--------|-----|--------|
| scalability/query_1k_ms | 7.39 | ±1.53 | 20.74% | ○ unstable |
| scalability/search_throughput_per_s | 138.93 | ±25.83 | 18.59% | ○ unstable |
| scalability/insert_throughput_per_s | 202.5 | ±18.57 | 9.17% | ◐ acceptable |
| wisdom/avg_activate_time_ms | 45.4 | ±3.32 | 7.3% | ◐ acceptable |
| memory/avg_insert_latency_ms | 6.01 | ±0.31 | 5.18% | ◐ acceptable |
| memory/capacity_1k_latency_ms | 6.85 | ±0.31 | 4.46% | ◐ acceptable |
| memory/capacity_10k_latency_ms | 13.69 | ±0.61 | 4.46% | ◐ acceptable |
| wisdom/avg_decompose_time_ms | 19.5 | ±0.79 | 4.07% | ◐ acceptable |
| memory/avg_query_latency_ms | 5.75 | ±0.18 | 3.21% | ◐ acceptable |

## 版本回归检测

> 与上一版本的对比将在有历史数据后自动生成。

---

*报告由多轮基准测试自动生成。轮次: 3, 每轮独立数据库。*