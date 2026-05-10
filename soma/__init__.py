import logging
import os
import time
import traceback
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

_log = logging.getLogger("soma")


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
        persist_dir: str = None,
        recall_threshold: float = 0.01,
        top_k: int = 5,
    ):
        if persist_dir is None:
            persist_dir = os.environ.get("SOMA_DATA_DIR", "soma_data")
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

    def __getattr__(self, name):
        """将未定义的公开属性委托给内部 SOMA_Agent 实例。

        这样外部代码（如 dash/server.py）可以直接访问 agent.hub、
        agent.memory、agent.evolver 等属性，无需绕过 SOMA 包装类。
        """
        if name.startswith('_'):
            raise AttributeError(
                f"'{type(self).__name__}' object has no attribute '{name}'"
            )
        return getattr(self._agent, name)

    def respond(self, problem: str, user_id: str = "") -> str:
        """完整智者管道：拆解→激活→合成→反思→进化检测"""
        mock_fallback = False
        try:
            answer = self._agent.respond(problem, user_id=user_id)
        except Exception:
            _log.error(
                "SOMA.respond() LLM调用失败，回退到mock响应:\n%s",
                traceback.format_exc(),
            )
            answer = self._mock_respond(problem)
            mock_fallback = True
        self._session_count += 1
        outcome = "failure" if mock_fallback else "success"
        self._agent.reflect(f"soma_{self._session_count}", outcome)
        if self._session_count > 0 and self._session_count % 5 == 0:
            self._agent.evolver.evolve()
        return answer

    def chat(self, problem: str, user_id: str = "") -> dict:
        """完整对话接口，返回结构化结果（供 API / Agent 使用）"""
        complexity = self._agent._assess_complexity(problem)
        foci = self._agent.decompose(problem)
        if complexity == 1 and len(foci) > 2:
            foci = foci[:2]

        original_top_k = self._agent.hub.top_k
        if complexity == 3:
            self._agent.hub.top_k = min(original_top_k * 2, 15)
        elif complexity == 1:
            self._agent.hub.top_k = max(original_top_k // 2, 2)
        try:
            activated = self._agent.hub.activate(
                foci, user_id=user_id, laws=self._agent.engine.laws,
            )
        finally:
            self._agent.hub.top_k = original_top_k

        # v0.8.0: 收集记忆建议的焦点，合并进推理框架
        suggested_foci = []
        for am in activated:
            if am.suggested_focus and am.suggested_focus.weight >= 0.1:
                suggested_foci.append(am.suggested_focus)
        if suggested_foci:
            foci = foci + suggested_foci

        # 确认偏误检测
        if complexity >= 2:
            self._agent._last_anti_memories = self._agent.hub.anti_confirmation_search(
                foci, user_id=user_id,
            )
        else:
            self._agent._last_anti_memories = []

        # v0.6.0: 构建推理框架
        self._agent._last_reasoning = self._agent._execute_reasoning(
            problem, foci, activated, self._agent._last_anti_memories,
        )

        mock_fallback = False

        try:
            answer = self._agent._call_llm(
                self._agent._build_prompt(problem, foci, activated),
                user_id,
            )
        except Exception:
            _log.error(
                "SOMA.chat() LLM调用失败，回退到mock响应:\n%s",
                traceback.format_exc(),
            )
            answer = self._mock_respond(problem, foci, activated)
            mock_fallback = True

        # v0.6.0: 因果抽取
        if complexity >= self._agent.config.causal_extraction_complexity:
            self._agent._extract_causal_relations(problem, answer)

        # v0.8.0: 反思质量自评
        quality = self._agent.quality_evaluator.evaluate(
            answer=answer,
            memory_contents=[am.memory.content for am in activated],
            conflict_count=len(getattr(self._agent.hub, 'last_conflicts', [])),
        )
        if quality["needs_reflection"]:
            self._agent._last_quality_note = (
                f"[质量反馈] 综合分 {quality['overall']:.2f} ({quality['grade']}) — "
                f"一致性 {quality['consistency']:.2f} "
                f"连贯性 {quality['coherence']:.2f} "
                f"可操作性 {quality['actionability']:.2f}"
            )
        else:
            self._agent._last_quality_note = ""

        for am in activated:
            am.memory.access_count += 1
            if am.source == "episodic":
                self._agent.memory.episodic.increment_access(am.memory.id)
        self._agent.evolver.set_current_context(foci, activated, problem)
        self._session_count += 1
        outcome = "failure" if mock_fallback else "success"
        self._agent.reflect(f"soma_{self._session_count}", outcome)
        if self._session_count > 0 and self._session_count % 5 == 0:
            self._agent.evolver.evolve()

        result = {
            "problem": problem,
            "answer": answer,
            "prompt": getattr(self._agent, '_last_prompt', ''),
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
            "reasoning": getattr(self._agent, '_last_reasoning', []),
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
        self, content: str, context: dict = None, importance: float = 0.5,
        user_id: str = "", session_id: str = "",
    ) -> str:
        return self._agent.remember(content, context, importance,
                                    user_id=user_id, session_id=session_id)

    def remember_semantic(
        self, subject: str, predicate: str, object_: str, confidence: float = 1.0,
        namespace: str = "",
    ) -> None:
        self._agent.remember_semantic(subject, predicate, object_, confidence,
                                      namespace=namespace)

    def query_memory(self, query: str, top_k: int = 5, user_id: str = "") -> list:
        return self._agent.query_memory(query, top_k, user_id=user_id)

    def decompose(self, problem: str) -> list:
        return self._agent.decompose(problem)

    def reflect(self, task_id: str, outcome: str) -> None:
        self._agent.reflect(task_id, outcome)

    def evolve(self) -> list:
        """执行自动进化（权重调整 + 记忆合并 + 遗忘清理）"""
        changes = self._agent.evolver.evolve()

        # v0.7.0: 记忆合并 — 相似记忆自动归并
        try:
            merged = self._agent.memory.episodic.consolidate(max_merges=10)
            if merged:
                changes.append({
                    "type": "memory_consolidation",
                    "merged_count": merged,
                })
        except Exception:
            pass

        # v0.7.0: 主动遗忘 — 低价值记忆归档
        try:
            forgotten = self._agent.memory.episodic.forget(max_archive=50)
            if any(forgotten.values()):
                changes.append({
                    "type": "memory_forgetting",
                    "details": forgotten,
                })
        except Exception:
            pass

        return changes

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

    def get_thought_templates(self) -> list:
        """获取已挖掘的思维模板（v0.6.0）"""
        return self._agent.evolver.get_thought_templates()

    def close(self) -> None:
        """关闭底层 agent 及所有子组件连接"""
        self._agent.close()

    def __enter__(self) -> "SOMA":
        return self

    def __exit__(self, *args) -> None:
        self.close()

    @property
    def stats(self) -> dict:
        return self._agent.memory.stats()
