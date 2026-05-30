# SOMA v1.1.3 中道引擎深化 — 零熵智库测试说明

> 版本：v1.1.3-dev（基于 v1.1.2 的 A1-A4 升级）
> 测试目标：验证中道引擎参数可配置化、仪表盘可视化、多Agent趋同检测、持久化日志四项新功能在生产环境的表现
> 安装方式：本地 wheel 一键安装

---

## 一、升级概览

v1.1.2 引入了中道引擎（会话内实时规律使用偏差检测），但存在四个局限：
1. 阈值(40%)、降权(20%)、提权(15%)、采样数(5)全部硬编码，无法按场景调优
2. 校正过程完全黑盒，运维只能翻日志
3. 多Agent各做各的中道校正，可能出现群体思维盲区
4. 校正记录用完即丢，无法跨会话分析趋势

v1.1.3 一次性解决这四个问题：

| 编号 | 功能 | 一句话说明 |
|------|------|-----------|
| A1 | 参数可配置化 | `SOMA(enable_zhongdao=True, zhongdao_threshold_ratio=0.30)` — 4个参数全可调 |
| A2 | Dash 可视化 | 侧边栏新增 ☯️ 中道引擎视图 — 规律热力图 + 校正时间线 |
| A3 | 多Agent趋同检测 | ≥2个Agent陷入同一规律时自动标记，共识回答附带脚注提醒 |
| A4 | 持久化日志 | 每次校正写入 `analytics.db` → `zhongdao_corrections` 表，API可查 |

---

## 二、文件清单

```
soma_wisdom-1.1.2-py3-none-any.whl    # 本地安装包
install.bat                             # Windows 一键安装脚本
install.sh                              # Linux/macOS 一键安装脚本
verify_install.py                       # 安装后验证脚本
SOMA_v1.1.3_测试说明.md                # 本文件
```

---

## 三、安装步骤

### Windows
```cmd
install.bat
```

### Linux / macOS
```bash
bash install.sh
```

### 手动安装
```bash
pip install soma_wisdom-1.1.2-py3-none-any.whl --force-reinstall
python verify_install.py
```

---

## 四、验证测试

安装后运行验证脚本，应看到 4 项全部 PASS：
```
$ python verify_install.py
A1(a): 默认参数启用 ... PASS
A1(b): 自定义参数启用 ... PASS
A2: Dash API 中道端点 ... PASS
A3: 跨Agent趋同检测  ... PASS
A4: 持久化校正日志  ... PASS
结果: 4/4 通过
```

---

## 五、功能测试指南

### 5.1 A1 — 参数可配置化

```python
from soma import SOMA

# 场景1: 快速响应（3次采样就触发，阈值30%）
soma = SOMA(enable_zhongdao=True, zhongdao_min_samples=3,
            zhongdao_threshold_ratio=0.30, llm="deepseek-chat")

# 场景2: 保守校正（阈值60%才触发，降权仅10%）
soma = SOMA(enable_zhongdao=True, zhongdao_threshold_ratio=0.60,
            zhongdao_penalty_factor=0.10, llm="deepseek-chat")

# 场景3: 激进纠偏（提权30%，适合头脑风暴）
soma = SOMA(enable_zhongdao=True, zhongdao_boost_factor=0.30,
            zhongdao_penalty_factor=0.30, llm="deepseek-chat")
```

**测试要点**：
- 不同 `zhongdao_threshold_ratio` 值下，触发校正的灵敏度是否如预期
- 极端值（0.0 / 1.0）不会崩溃
- `zhongdao_min_samples=1` 也能正常工作

### 5.2 A2 — Dash 仪表盘可视化

启动 Dash 后访问 `http://localhost:8765`，左侧导航栏出现 ☯️ **中道引擎** 入口。

**测试要点**：
- 未启用中道时显示 "未启用" 提示
- 启用后，开始对话，刷新页面能看到规律使用分布条形图
- 橙色高亮条 = 超过阈值的规律
- 校正记录区显示降权（橙色）/ 提权（绿色）历史
- 点击"重置会话"按钮清空当前统计

**启动Dash**：
```bash
python -m soma.dash.server
# 或
python -c "from soma.dash.server import app; import uvicorn; uvicorn.run(app, host='0.0.0.0', port=8765)"
```

**API 端点**：
```bash
curl http://localhost:8765/api/zhongdao/status     # 当前状态
curl http://localhost:8765/api/zhongdao/history    # 校正历史
curl -X POST http://localhost:8765/api/zhongdao/reset  # 重置会话
```

### 5.3 A3 — 多Agent趋同检测

```python
from soma import SOMA

soma = SOMA(enable_zhongdao=True, orchestration_mode="multi", llm="deepseek-chat")

# 创建多个专家
soma.create_experts([
    {"agent_id": "analyst", "expertise": ["商业分析"], "description": "分析师"},
    {"agent_id": "strategist", "expertise": ["战略规划"], "description": "策略师"},
])

# 连续问同一视角的问题
for i in range(5):
    soma.respond("用系统思维分析市场趋势")

# 预期：第5轮后两个Agent的中道引擎触发降权，
# 且共识回答末尾出现 "中道协调提示" 脚注
result = soma.respond("继续分析")
print(result)  # 检查是否包含 "中道协调提示"
```

**测试要点**：
- 只有 1 个 Agent 过度使用时，不触发趋同告警
- ≥2 个 Agent 对同一规律过度使用 >40%，触发趋同告警
- 告警以 blockquote 脚注形式出现在回答末尾（低干扰）

### 5.4 A4 — 持久化日志

```python
from soma.analytics import AnalyticsStore

store = AnalyticsStore("soma_data")
history = store.get_zhongdao_history(limit=20)
summary = store.get_zhongdao_summary()

print(f"总校正次数: {summary['total_corrections']}")
print(f"降权: {summary['by_type'].get('overuse_penalty', 0)} 次")
print(f"提权: {summary['by_type'].get('neglect_boost', 0)} 次")
print(f"各规律: {summary['by_law']}")

# 按规律过滤
system_thinking = store.get_zhongdao_history(limit=10, law_id="systems_thinking")
print(f"系统思维被校正: {len(system_thinking)} 次")
```

**数据库表结构**：
```sql
SELECT * FROM zhongdao_corrections ORDER BY timestamp DESC LIMIT 5;
-- 字段: id, timestamp, session_id, agent_id, type, law_id, law_name,
--        usage_ratio, old_weight, new_weight, details_json
```

---

## 六、基准对比建议

建议 Qoder 参照上次 v1.1.2 的测试方法（Run#38 vs #39），做一组 v1.1.3 ON vs OFF 的对比：

```python
# OFF 基准
soma_off = SOMA(enable_zhongdao=False, llm="deepseek-chat")
# 跑 30 轮多样化问题，记录各项指标

# ON 测试
soma_on = SOMA(enable_zhongdao=True, llm="deepseek-chat")
# 同样的 30 轮，对比：
# - 基尼系数（规律使用均衡度）
# - 智慧评分变化
# - 校正触发频率和幅度
# - Dashboard 可视化是否准确反映实际状态
```

---

## 七、注意事项

1. **本次为本地测试包，未推送 GitHub/PyPI**。测试通过后再正式发布
2. 中道引擎默认关闭，不影响现有生产管道
3. Dash 新增的 ☯️ 视图在移动端可能需要横向滚动
4. `zhongdao_corrections` 表会随使用增长，建议定期清理 90 天前的记录
5. 多Agent模式下每个 Agent 有独立的中道引擎实例，会话统计互不干扰

---

## 八、反馈模板

测试后请回复以下信息：

```
### v1.1.3 测试报告
- 测试环境: [零熵智库 / 本地]
- 测试轮数: [N 轮]
- A1(参数配置): [正常/异常] — [备注]
- A2(Dash可视化): [正常/异常] — [备注]
- A3(多Agent趋同): [正常/异常] — [备注]
- A4(持久化日志): [正常/异常] — [备注]
- 全量测试: [X/Y 通过]
- 性能影响: [有/无 明显回归]
- 建议:
```
