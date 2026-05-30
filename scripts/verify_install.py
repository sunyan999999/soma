"""SOMA v1.1.3 安装后验证脚本 — 零熵智库部署测试"""
import sys
import tempfile
import shutil

PASS = 0
FAIL = 0

def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  {name} ... PASS {detail}")
    else:
        FAIL += 1
        print(f"  {name} ... FAIL {detail}")

print("SOMA v1.1.3 安装验证")
print("=" * 50)

# ── 模块导入 ──
print("\n[0] 核心模块导入")
try:
    from soma import SOMA, __version__
    check("SOMA 导入", True, f"v{__version__}")
except Exception as e:
    check("SOMA 导入", False, str(e))

try:
    from soma.zhongdao import ZhongdaoEngine
    check("中道引擎", True)
except Exception as e:
    check("中道引擎", False, str(e))

try:
    from soma.analytics import AnalyticsStore
    check("分析存储", True)
except Exception as e:
    check("分析存储", False, str(e))

try:
    from soma.multi_agent.orchestrator import SOMAOrchestrator
    check("多Agent编排", True)
except Exception as e:
    check("多Agent编排", False, str(e))

# ── A1: 参数可配置化 ──
print("\n[1] A1: 参数可配置化")
try:
    # 默认参数
    s1 = SOMA(enable_zhongdao=True, llm="mock")
    z1 = s1._agent.zhongdao
    check("A1(a) 默认参数",
          z1 is not None and z1.threshold_ratio == 0.40 and
          z1.penalty_factor == 0.20 and z1.min_samples == 5)

    # 自定义参数
    s2 = SOMA(enable_zhongdao=True, zhongdao_threshold_ratio=0.30,
              zhongdao_penalty_factor=0.10, zhongdao_boost_factor=0.25,
              zhongdao_min_samples=3, llm="mock")
    z2 = s2._agent.zhongdao
    check("A1(b) 自定义参数",
          z2.threshold_ratio == 0.30 and z2.penalty_factor == 0.10 and
          z2.boost_factor == 0.25 and z2.min_samples == 3)

    # 关闭状态
    s3 = SOMA(enable_zhongdao=False, llm="mock")
    check("A1(c) 默认关闭", s3._agent.zhongdao is None)
except Exception as e:
    check("A1 异常", False, str(e))

# ── A2: Dash API ──
print("\n[2] A2: Dash API 中道端点")
try:
    from soma.config import SOMAConfig
    cfg = SOMAConfig(enable_zhongdao=True)
    assert hasattr(cfg, 'zhongdao_threshold_ratio')
    assert hasattr(cfg, 'zhongdao_penalty_factor')
    assert hasattr(cfg, 'zhongdao_boost_factor')
    assert hasattr(cfg, 'zhongdao_min_samples')
    check("A2(a) 配置字段完整", True)

    z = s1._agent.zhongdao
    status = {
        "enabled": z.enabled,
        "config": {
            "threshold_ratio": z.threshold_ratio,
            "penalty_factor": z.penalty_factor,
            "boost_factor": z.boost_factor,
            "min_samples": z.min_samples,
        },
        "session_usage": z._session_usage,
        "total_samples": sum(z._session_usage.values()),
        "last_corrections": z.last_corrections,
    }
    check("A2(b) 状态数据结构", status["enabled"] and "config" in status)
except Exception as e:
    check("A2 异常", False, str(e))

# ── A3: 跨Agent趋同 ──
print("\n[3] A3: 多Agent趋同检测")
try:
    from soma.multi_agent.consensus import AgentOpinion
    config = SOMAConfig(enable_zhongdao=True, orchestration_evolution_enabled=False)
    orch = SOMAOrchestrator(config)
    orch.create_agents([
        {"agent_id": "a1", "expertise": ["分析"], "description": "分析师"},
        {"agent_id": "a2", "expertise": ["战略"], "description": "策略师"},
    ])

    # 验证每个子Agent都有中道引擎
    check("A3(a) 子Agent中道启用",
          orch._agents["a1"].zhongdao is not None and
          orch._agents["a2"].zhongdao is not None)

    # 模拟两个Agent都过度使用同一规律
    for aid in ["a1", "a2"]:
        for _ in range(6):
            orch._agents[aid].zhongdao._session_usage["systems_thinking"] = \
                orch._agents[aid].zhongdao._session_usage.get("systems_thinking", 0) + 1

    ops = [AgentOpinion(agent_id=aid, answer="x", confidence=0.8) for aid in ["a1", "a2"]]
    result = orch._detect_cross_agent_convergence(ops)
    check("A3(b) 趋同检测触发", result is not None and len(result["agents"]) >= 2)

    # 分散使用时不应触发
    orch2 = SOMAOrchestrator(config)
    orch2.create_agents([
        {"agent_id": "b1", "expertise": ["分析"], "description": "分析师"},
        {"agent_id": "b2", "expertise": ["创意"], "description": "创意师"},
    ])
    # b1 偏系统思维，b2 偏第一性原理
    for _ in range(6):
        orch2._agents["b1"].zhongdao._session_usage["systems_thinking"] = \
            orch2._agents["b1"].zhongdao._session_usage.get("systems_thinking", 0) + 1
        orch2._agents["b2"].zhongdao._session_usage["first_principles"] = \
            orch2._agents["b2"].zhongdao._session_usage.get("first_principles", 0) + 1
    ops2 = [AgentOpinion(agent_id="b1", answer="x", confidence=0.8),
            AgentOpinion(agent_id="b2", answer="y", confidence=0.7)]
    result2 = orch2._detect_cross_agent_convergence(ops2)
    check("A3(c) 分散不触发", result2 is None)
except Exception as e:
    check("A3 异常", False, str(e))

# ── A4: 持久化日志 ──
print("\n[4] A4: 持久化校正日志")
try:
    tmp = tempfile.mkdtemp()
    store = AnalyticsStore(tmp)

    # 写入测试数据
    store.record_zhongdao_correction(
        {"type": "overuse_penalty", "law_id": "systems_thinking",
         "law_name": "系统思维", "usage_ratio": 0.60,
         "old_weight": 0.90, "new_weight": 0.72},
        session_id="test_verify", agent_id="agent_1")

    store.record_zhongdao_correction(
        {"type": "neglect_boost", "law_id": "first_principles",
         "law_name": "第一性原理", "weight": 0.92},
        session_id="test_verify", agent_id="agent_1")

    # 查询验证
    history = store.get_zhongdao_history(limit=10)
    check("A4(a) 历史查询", len(history) == 2)

    summary = store.get_zhongdao_summary()
    check("A4(b) 汇总统计",
          summary["total_corrections"] == 2 and
          "overuse_penalty" in summary["by_type"] and
          "neglect_boost" in summary["by_type"])

    # 类型过滤
    penalties = store.get_zhongdao_history(limit=10, correction_type="overuse_penalty")
    check("A4(c) 类型过滤", len(penalties) == 1)

    # 幂等建表
    store._create_zhongdao_tables()
    store._create_zhongdao_tables()
    check("A4(d) 幂等建表", True)

    shutil.rmtree(tmp, ignore_errors=True)
except Exception as e:
    check("A4 异常", False, str(e))

# ── 总结 ──
print("\n" + "=" * 50)
print(f"结果: {PASS}/{PASS+FAIL} 通过")
if FAIL == 0:
    print("状态: 全部通过，可以开始零熵智库测试")
    sys.exit(0)
else:
    print(f"状态: {FAIL} 项失败，请检查上方输出")
    sys.exit(1)
