"""
SOMA 集成指南 — 不破坏原有系统的接入方案

适用场景：数字分身系统，已有一套记忆系统，需要接入 SOMA 做深度分析测试。

三种接入模式，按隔离程度从高到低排列：
  模式A: REST API 旁路    ← 推荐，零风险，两个进程完全独立
  模式B: Python SDK 内嵌   ← 同进程，用独立数据目录隔离
  模式C: LangChain Tool    ← 如果原系统已用 LangChain

══════════════════════════════════════════════════════════════
模式A: REST API 旁路（最安全）
══════════════════════════════════════════════════════════════

SOMA 作为独立服务运行，数字分身通过 HTTP 调用。
两个系统零耦合，SOMA 的崩溃不影响原系统，测试完直接关停。

步骤:
  1. 启动 SOMA 服务（默认端口 8765）
  2. 原系统在"深度分析"场景时调用 SOMA API
  3. 原系统的记忆系统照常工作，互不干扰
"""

import requests  # pip install requests


class SOMAClient:
    """SOMA REST API 客户端 — 嵌入数字分身系统的最小封装"""

    def __init__(self, base_url: str = "http://localhost:8765", api_key: str = ""):
        self.base_url = base_url
        self.headers = {
            "Content-Type": "application/json",
            "X-API-Key": api_key,
        }

    def health(self) -> dict:
        """健康检查"""
        return requests.get(f"{self.base_url}/api/health").json()

    def chat(self, problem: str) -> dict:
        """深度分析 — 返回完整的拆解+激活+回答"""
        resp = requests.post(
            f"{self.base_url}/api/chat",
            headers=self.headers,
            json={"problem": problem},
        )
        return resp.json()

    def chat_stream(self, problem: str):
        """SSE 流式深度分析"""
        resp = requests.post(
            f"{self.base_url}/api/chat/stream",
            headers=self.headers,
            json={"problem": problem},
            stream=True,
        )
        for line in resp.iter_lines():
            if line:
                yield line.decode("utf-8")

    def remember(self, content: str, context: dict = None, importance: float = 0.5) -> dict:
        """注入记忆资粮"""
        resp = requests.post(
            f"{self.base_url}/api/memory/add",
            headers=self.headers,
            json={
                "content": content,
                "domain": (context or {}).get("domain", "通用"),
                "type": (context or {}).get("type", "笔记"),
                "importance": importance,
            },
        )
        return resp.json()

    def search_memory(self, query: str, top_k: int = 10) -> list:
        """搜索 SOMA 记忆库"""
        resp = requests.post(
            f"{self.base_url}/api/memory/search",
            headers=self.headers,
            json={"query": query, "top_k": top_k},
        )
        return resp.json().get("results", [])

    def get_weights(self) -> dict:
        """获取当前思维规律权重"""
        return requests.get(
            f"{self.base_url}/api/framework/weights",
            headers=self.headers,
        ).json()

    def evolve(self) -> dict:
        """触发进化"""
        resp = requests.post(
            f"{self.base_url}/api/framework/evolve",
            headers=self.headers,
        )
        return resp.json()

    def discover_laws(self) -> dict:
        """从高关联记忆簇中自动发现新思维规律。

        返回 {"status": "discovered", "candidate": {...}} 或
             {"status": "no_discovery", "candidate": None}
        建议每 50 次会话调用一次。
        """
        resp = requests.post(
            f"{self.base_url}/api/framework/discover-laws",
            headers=self.headers,
            json={},
        )
        return resp.json()

    def approve_law(self, candidate: dict) -> dict:
        """审批通过一条候选规律，加入思维框架。

        candidate 应为 discover_laws() 返回的 candidate 字典。
        """
        resp = requests.post(
            f"{self.base_url}/api/framework/approve-law",
            headers=self.headers,
            json={"candidate": candidate},
        )
        return resp.json()


def demo_mode_a():
    """
    模式A 演示：REST API 旁路

    前提：先启动 SOMA 服务
      pip install soma-core
      python -m soma                    # 验证安装
      SOMA_API_KEY=test python dash/server.py   # 启动 API 服务

    然后在数字分身项目中：
    """

    # 1. 创建 SOMA 客户端（数字分身项目中只需这几行）
    soma = SOMAClient(base_url="http://localhost:8765")

    # 2. 健康检查 — 确认 SOMA 服务在线
    try:
        status = soma.health()
        print(f"SOMA 服务状态: {status['status']}, 版本: {status['version']}")
    except Exception:
        print("SOMA 服务未启动，请先运行: python dash/server.py")
        return

    # 3. 给 SOMA 注入数字分身的"核心记忆"
    #    这些可以是从原系统迁移过来的关键知识
    soma.remember(
        "用户的职业经历：2015年进入互联网行业，先后在字节跳动和腾讯担任产品经理，"
        "2022年创业做AI教育产品，积累了丰富的产品设计和用户增长经验。",
        context={"domain": "用户画像", "type": "职业背景"},
        importance=0.95,
    )
    soma.remember(
        "用户的思维偏好：习惯从第一性原理出发分析问题，重视数据驱动决策，"
        "对商业模式有敏锐的洞察力。在面对重大抉择时，倾向于列出所有选项后"
        "逐一排除。",
        context={"domain": "用户画像", "type": "思维模式"},
        importance=0.9,
    )
    soma.remember(
        "用户的价值观：认为教育的本质是唤醒而非灌输，技术应该服务于人的成长。"
        "最欣赏的企业家是Elon Musk，因为他敢于挑战不可能。",
        context={"domain": "用户画像", "type": "价值观"},
        importance=0.85,
    )
    print("已注入3条核心记忆到SOMA")

    # 4. 原系统保持自己的记忆逻辑，只在"深度分析"场景调用 SOMA
    #    这是关键：SOMA 和原系统各司其职

    # 模拟：数字分身收到一个需要深度分析的问题
    deep_question = "用户正在考虑是否应该放弃独立创业、加入一家AI大厂，如何帮他系统地分析这个抉择？"

    print(f"\n深度分析问题: {deep_question}")

    result = soma.chat(deep_question)

    # 展示 SOMA 返回的结构化结果
    print(f"\n拆解维度 ({len(result.get('foci', []))} 个):")
    for f in result.get("foci", []):
        print(f"  - [{f['law_id']}] {f['dimension'][:80]}... (权重: {f['weight']:.2f})")

    print(f"\n激活记忆 ({len(result.get('activated_memories', []))} 条):")
    for am in result.get("activated_memories", []):
        print(f"  - [{am.get('source', '')}] 分数: {am.get('activation_score', 0):.3f}")

    print(f"\n智者回答:\n{result.get('answer', '')[:500]}...")

    # 5. 定期运行规律发现（如每 50 次会话）
    discovery = soma.discover_laws()
    if discovery.get("status") == "discovered":
        cand = discovery["candidate"]
        print(f"\n发现候选规律: {cand.get('name', cand.get('id', '?'))}")
        # 人工审核后：
        # soma.approve_law(cand)
    else:
        print("\n当前无新规律发现条件")


# ═════════════════════════════════════════════════════════════
# 模式B: Python SDK 内嵌（同进程，独立数据目录）
# ═════════════════════════════════════════════════════════════
"""
适合场景：不想额外启动一个服务进程，且原系统是用 Python 写的。

安全隔离措施：
  1. SOMA 用独立的 persist_dir（不与原系统共用数据目录）
  2. 在原系统中新建一个独立模块封装 SOMA 调用
  3. 原系统的记忆系统完全不受影响
"""

def demo_mode_b():
    from pathlib import Path
    from soma import SOMA

    # 关键：指定独立的数据目录，不与原系统混用
    soma = SOMA(
        persist_dir="soma_test_data",   # ← SOMA 独立数据目录
        llm="deepseek-chat",            # 或 "mock" 先测试管道
        top_k=5,
    )

    # 以下和模式A的使用方式类似，但通过 Python API 调用
    soma.remember(
        "用户的核心记忆内容...",
        context={"domain": "用户画像", "type": "背景"},
        importance=0.9,
    )

    result = soma.chat("需要深度分析的问题")
    return result


# ═════════════════════════════════════════════════════════════
# 模式C: LangChain Tool（如果原系统已用 LangChain）
# ═════════════════════════════════════════════════════════════
"""
适合场景：原系统基于 LangChain 构建，希望 SOMA 作为一个 Tool 被 Agent 调用。
"""

def demo_mode_c():
    from soma.config import SOMAConfig, load_config
    from soma.agent import SOMA_Agent
    from soma.langchain_tool import create_soma_tool

    config = SOMAConfig(
        framework_path="wisdom_laws.yaml",
        episodic_persist_dir="soma_langchain_data",
    )
    agent = SOMA_Agent(config)

    # 注入记忆
    agent.remember("...", context={"domain": "..."}, importance=0.9)

    # 创建 Tool — 可注册到 LangChain Agent 中
    tool = create_soma_tool(
        agent,
        name="soma_deep_analysis",
        description="当需要多维度深度分析时使用此工具。输入问题，返回智者分析。",
    )

    # 在原 LangChain Agent 中注册此 Tool
    # agent = initialize_agent([...existing_tools, tool], llm, ...)

    return tool


# ═════════════════════════════════════════════════════════════
# 集成决策树
# ═════════════════════════════════════════════════════════════
"""
                    你的数字分身系统
                          │
              ┌───────────┼───────────┐
              │           │           │
         需要深度分析?  普通对话?   记忆存储?
              │           │           │
              ▼           ▼           ▼
         调用 SOMA    使用原系统   使用原系统
         (API/SDK)   (已有逻辑)   (已有存储)
              │
              ▼
         SOMA 返回
      结构化分析结果
      (拆解+激活+回答+进化)

关键原则:
  1. SOMA 只负责"深度分析"场景 — 不替代原系统的日常对话和记忆
  2. SOMA 的记忆库独立管理 — 可以注入原系统的关键知识作为"资粮"
  3. 原系统保持完全不变 — SOMA 作为可选增强，随时可开关
  4. 测试阶段建议用模式A (REST API) — 隔离最彻底


═══════════════════════════════════════════════════════════════
能力覆盖对照表
═══════════════════════════════════════════════════════════════

┌──────────────────────────────┬──────────┬──────────┬──────────┐
│        能力项                  │ 模式A   │ 模式B   │ 模式C   │
│                              │ REST API │ Python  │LangChain│
├──────────────────────────────┼──────────┼──────────┼──────────┤
│ 问题拆解 (decompose)          │   ✅     │   ✅     │   ✅    │
│ 记忆激活 (activate)           │   ✅     │   ✅     │   ✅    │
│ 智者合成 (synthesize)         │   ✅     │   ✅     │   ✅    │
│ SSE 流式输出                  │   ✅     │   ✅     │   ✅    │
│ 注入情境记忆 (remember)       │   ✅     │   ✅     │   ✅    │
│ 注入语义记忆 (remember_sem)   │   ✅     │   ✅     │   ✅    │
│ 记忆搜索 (search)             │   ✅     │   ✅     │   ✅    │
│ 查询/调整权重                  │   ✅     │   ✅     │   ✅    │
│ 手动触发进化 (evolve)         │   ✅     │   ✅     │   ✅    │
│ 自动进化 (每10次会话)          │   ✅     │   ✅     │   ✅    │
│ 反思记录 (reflect)            │ 自动     │   ✅     │   ✅    │
│ 规律发现 (discover_laws) ★    │   ✅     │   ✅     │   ✅    │
│ 审批新规律 (approve_law) ★    │   ✅     │   ✅     │   ✅    │
│ 分析数据看板                   │   ✅     │   —      │   —     │
│ 基准测试                       │   ✅     │   —      │   —     │
│ 独立数据目录隔离               │   ✅     │   ✅     │   ✅    │
│ 原系统零代码改动               │   ✅     │   ❌     │   ❌    │
└──────────────────────────────┴──────────┴──────────┴──────────┘

★ 规律发现与审批是 SOMA 的进阶能力：
  1. discover_laws() — 分析高关联记忆簇，尝试从中提取通用思维模式
  2. approve_law()   — 人工审核通过后，将新规律正式加入7律框架
  建议每 50 次深度分析后调用一次 discover_laws()，
  产生的候选规律经人工审核确认后调用 approve_law()。

  注意：规律发现需要 LLM 支持（Mock 模式下无法使用），
  且记忆库中需要有足够数量的高关联记忆作为"原料"。

  模式C (LangChain Tool) 也有完整访问权限，
  因为 SOMA_Agent 实例直接暴露了所有 API。
"""

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "a":
        demo_mode_a()
    elif len(sys.argv) > 1 and sys.argv[1] == "b":
        demo_mode_b()
    elif len(sys.argv) > 1 and sys.argv[1] == "c":
        demo_mode_c()
    else:
        print(__doc__)
        print("\n用法: python integration_guide.py [a|b|c]")
        print("  a = REST API 旁路模式（推荐）")
        print("  b = Python SDK 内嵌模式")
        print("  c = LangChain Tool 模式")
        print("\n模式A需要先启动 SOMA API 服务: python dash/server.py")
