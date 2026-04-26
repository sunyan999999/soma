import time
from pathlib import Path

from soma.config import SOMAConfig, load_config
from soma.base import MemoryUnit, Focus, ActivatedMemory
from soma.agent import SOMA_Agent
from soma.evolve import MetaEvolver
from soma.law_discovery import LawDiscovery
from soma.embedder import SOMAEmbedder
from soma.langchain_tool import create_soma_tool

# 包内置默认思维框架 — 确保 pip install 后在任何目录都能找到
_PACKAGE_DIR = Path(__file__).parent
_DEFAULT_FRAMEWORK = _PACKAGE_DIR / "wisdom_laws.yaml"

__all__ = [
    "SOMA",
    "SOMA_Agent",
    "SOMAConfig",
    "SOMAEmbedder",
    "MetaEvolver",
    "LawDiscovery",
    "load_config",
    "create_soma_tool",
    "MemoryUnit",
    "Focus",
    "ActivatedMemory",
]


class SOMA:
    """SOMA 顶层门面 — 供外部 Agent / 应用直接调用

    使用示例::

        from soma import SOMA

        soma = SOMA()
        soma.remember("第一性原理：从最基本要素出发推导...")
        answer = soma.respond("如何系统性地分析公司增长瓶颈？")

    五分钟接入，让你的 Agent 学会智者思维。
    """

    def __init__(
        self,
        framework_config: str = None,
        llm: str = "deepseek-chat",
        use_vector_search: bool = True,
        persist_dir: str = "soma_data",
        recall_threshold: float = 0.01,
        top_k: int = 5,
    ):
        if framework_config is None:
            framework_config = str(_DEFAULT_FRAMEWORK)
        framework_path = Path(framework_config)
        # 兜底：如果指定的文件不存在，尝试包内置 YAML
        if not framework_path.exists():
            framework_path = _DEFAULT_FRAMEWORK

        self._config = SOMAConfig(
            framework_path=framework_path,
            episodic_persist_dir=Path(persist_dir),
            llm_model=llm,
            use_vector_search=use_vector_search,
            recall_threshold=recall_threshold,
            default_top_k=top_k,
        )
        self._agent = SOMA_Agent(self._config)
        self._session_count = 0

    def respond(self, problem: str) -> str:
        """完整智者管道：拆解→激活→合成→反思→进化检测"""
        try:
            answer = self._agent.respond(problem)
        except Exception:
            answer = self._mock_respond(problem)
        self._session_count += 1
        self._agent.reflect(f"soma_{self._session_count}", "success")
        if self._session_count > 0 and self._session_count % 10 == 0:
            self._agent.evolver.evolve()
        return answer

    def chat(self, problem: str) -> dict:
        """完整对话接口，返回结构化结果（供 API / Agent 使用）"""
        foci = self._agent.decompose(problem)
        activated = self._agent.hub.activate(foci)

        try:
            answer = self._agent._call_llm(
                self._agent._build_prompt(problem, foci, activated)
            )
        except Exception:
            answer = self._mock_respond(problem, foci, activated)

        for am in activated:
            am.memory.access_count += 1
        self._agent.evolver.set_current_context(foci, activated)
        self._session_count += 1
        self._agent.reflect(f"soma_{self._session_count}", "success")
        if self._session_count > 0 and self._session_count % 10 == 0:
            self._agent.evolver.evolve()

        result = {
            "problem": problem,
            "answer": answer,
            "foci": [
                {
                    "law_id": f.law_id,
                    "dimension": f.dimension,
                    "keywords": f.keywords[:8],
                    "weight": f.weight,
                    "rationale": f.rationale,
                }
                for f in foci
            ],
            "activated_memories": [
                self._agent.hub.explain_activation(am) for am in activated
            ],
            "memory_stats": self._agent.memory.stats(),
            "weights": self._agent.evolver.get_weights(),
        }

        self._agent.record_session(problem, answer, foci, activated)
        return result

    def _mock_respond(self, problem, foci=None, activated=None):
        """无 LLM 时的 mock 响应"""
        if foci is None:
            foci = self._agent.decompose(problem)
        if activated is None:
            activated = self._agent.hub.activate(foci)
        parts = [f"## 问题拆解\n从 {len(foci)} 个维度分析「{problem}」："]
        for f in foci:
            parts.append(f"- **{f.law_id}**（权重 {f.weight:.2f}）：{f.dimension[:120]}")
        if activated:
            parts.append(f"\n## 激活的相关记忆（{len(activated)} 条）")
            for am in activated[:5]:
                snippet = am.memory.content[:100]
                parts.append(f"- [{am.source}] {snippet}...")
        parts.append(f"\n> 未配置 LLM，此为 Mock 模式。设置 llm 参数连接真实模型。")
        return "\n".join(parts)

    def remember(
        self, content: str, context: dict = None, importance: float = 0.5
    ) -> str:
        return self._agent.remember(content, context, importance)

    def remember_semantic(
        self, subject: str, predicate: str, object_: str, confidence: float = 1.0
    ) -> None:
        self._agent.remember_semantic(subject, predicate, object_, confidence)

    def query_memory(self, query: str, top_k: int = 5) -> list:
        return self._agent.query_memory(query, top_k)

    def decompose(self, problem: str) -> list:
        return self._agent.decompose(problem)

    def reflect(self, task_id: str, outcome: str) -> None:
        self._agent.reflect(task_id, outcome)

    def evolve(self) -> list:
        """执行自动进化"""
        return self._agent.evolver.evolve()

    def get_weights(self) -> dict:
        return self._agent.evolver.get_weights()

    def adjust_weight(self, law_id: str, new_weight: float) -> bool:
        return self._agent.evolver.adjust_weight(law_id, new_weight)

    def discover_laws(self) -> dict | None:
        """尝试从高关联记忆中自动发现新的思维规律。

        返回候选规律字典（供人工审核），或 None 表示当前无条件生成。
        建议每 50 次会话调用一次。需要 LLM 时设置 llm 参数。
        """
        return self._agent.evolver.discover_laws(
            embedder=self._agent.embedder,
            llm_model=self._config.llm_model if self._config.llm_model != "mock" else None,
        )

    def approve_law(self, candidate: dict) -> bool:
        """审批通过一条候选规律，加入思维框架。返回是否成功。"""
        return self._agent.evolver.approve_law(
            candidate, embedder=self._agent.embedder,
        )

    @property
    def stats(self) -> dict:
        return self._agent.memory.stats()
