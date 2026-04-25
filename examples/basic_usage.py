"""
SOMA 基础使用示例

演示完整的智者思维管道：
1. 初始化 SOMA
2. 存储情节记忆和语义三元组
3. 智慧式问答
4. 查看思维拆解过程
5. 查询记忆资粮
6. 元认知反思

运行方式：
    python examples/basic_usage.py

注意：需要设置 LLM API 密钥环境变量（如 DEEPSEEK_API_KEY 等）。
如果不需要实际调用 LLM，可以设置 SOMAConfig(llm_model="mock") 并 mock LiteLLM。
"""

import os
from pathlib import Path

# 添加项目根目录到路径
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from soma.config import SOMAConfig, load_config
from soma.agent import SOMA_Agent


def demo_with_mock_llm():
    """使用 Mock LLM 演示管道流程（不需要 API 密钥）"""
    from unittest.mock import patch, MagicMock

    print("=" * 60)
    print("SOMA 智者思维演示（Mock LLM 模式）")
    print("=" * 60)

    # 初始化
    import tempfile
    tmp_dir = Path(tempfile.mkdtemp())
    framework = load_config(Path("wisdom_laws.yaml"))
    config = SOMAConfig(
        framework=framework,
        episodic_persist_dir=tmp_dir / "chroma",
        default_top_k=5,
        recall_threshold=0.01,
    )
    agent = SOMA_Agent(config)

    # 存储情节记忆
    print("\n[注入记忆资粮]")
    agent.remember(
        "第一性原理：回归事物最基本的要素，从底层逻辑出发进行推导。"
        "在商业中，关注客户的根本需求而非竞争对手的行为。",
        context={"domain": "哲学", "type": "理论"},
        importance=0.95,
    )
    print("  ✓ 存储: 第一性原理理论")

    agent.remember(
        "系统思维应用：增长是一个系统行为，涉及产品、市场、团队、"
        "流程等多个要素的相互作用。增长停滞往往是系统出现负反馈回路。",
        context={"domain": "思维", "type": "方法论"},
        importance=0.9,
    )
    print("  ✓ 存储: 系统思维方法论")

    agent.remember(
        "逆向思考案例：与其研究'如何增长'，不如先研究'用户为何流失'。"
        "某SaaS产品通过分析流失用户的共性，反向优化留存策略，最终实现增长。",
        context={"domain": "营销", "type": "案例"},
        importance=0.85,
    )
    print("  ✓ 存储: 逆向思考案例")

    agent.remember(
        "二八法则实践：80%的增长瓶颈来自20%的核心问题。"
        "找到关键少数杠杆点，避免面面俱到。",
        context={"domain": "管理", "type": "实践"},
        importance=0.8,
    )
    print("  ✓ 存储: 二八法则实践")

    # 存储语义三元组
    agent.remember_semantic("增长", "依赖", "创新")
    agent.remember_semantic("增长", "受阻于", "路径依赖")
    agent.remember_semantic("停滞", "源于", "价值交付不足")
    agent.remember_semantic("系统思维", "关联", "矛盾分析")
    print("  ✓ 存储: 4条语义三元组")

    # 查看记忆库状态
    stats = agent.memory.stats()
    print(f"\n[记忆库状态] 情节记忆: {stats['episodic']}, "
          f"语义三元组: {stats['semantic']}, 技能: {stats['skill']}")

    # 拆解问题
    problem = "为什么新产品增长停滞？"
    print(f"\n[问题] {problem}")

    print("\n[思维拆解]")
    foci = agent.decompose(problem)
    for i, f in enumerate(foci, 1):
        print(f"  {i}. [{f.law_id}] (权重: {f.weight})")
        print(f"     维度: {f.dimension}")
        print(f"     触发: {f.rationale}")
        print(f"     检索关键词: {', '.join(f.keywords[:5])}...")

    # 激活记忆
    print("\n[激活的记忆资粮]")
    activated = agent.hub.activate(foci)
    for i, am in enumerate(activated, 1):
        preview = am.memory.content[:80].replace("\n", " ")
        print(f"  {i}. [{am.source}] 分数: {am.activation_score:.4f}")
        print(f"     内容预览: {preview}...")

    # 模拟 LLM 应答
    with patch("soma.agent.completion") as mock_llm:
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = (
            "## 智者分析\n\n"
            "### 从第一性原理出发\n"
            "增长停滞的本质应从最底层拆解：客户为何不再选择我们？"
            "回归到'为客户创造价值'这一最根本的要素...\n\n"
            "### 从系统思维出发\n"
            "增长不是孤立的获客问题，而是产品、市场、渠道的相互作用。"
            "需要找到负反馈回路的杠杆点...\n\n"
            "### 综合建议\n"
            "1. 先逆向分析流失用户，找到根本原因\n"
            "2. 用二八法则聚焦关键20%的问题\n"
            "3. 从第一性原理重新定义价值主张"
        )
        mock_llm.return_value = mock_response

        answer = agent.respond(problem)
        print(f"\n[最终答案]\n{answer}")

    # 元认知反思
    agent.reflect("task_001", "success")
    print("\n[元认知] 已记录反思日志 ✓")

    print("\n" + "=" * 60)
    print("演示完成！")

    # 清理临时目录
    import shutil
    shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    demo_with_mock_llm()
