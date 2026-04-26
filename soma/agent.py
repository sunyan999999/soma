from typing import Any, Dict, List, Optional

from litellm import completion

from soma.base import ActivatedMemory, Focus
from soma.config import SOMAConfig, load_config
from soma.embedder import SOMAEmbedder
from soma.engine import WisdomEngine
from soma.evolve import MetaEvolver
from soma.hub import ActivationHub
from soma.memory.core import MemoryCore


class SOMA_Agent:
    """顶层统一对话接口 — 编排完整智者思维管道"""

    def __init__(self, config: SOMAConfig):
        self.config = config

        # 加载思维框架
        framework = config.framework or load_config(config.framework_path)
        self.engine = WisdomEngine(framework)

        # 嵌入器（Alpha 新增）
        self.embedder = None
        if config.use_vector_search:
            self.embedder = SOMAEmbedder(config)

        # 记忆核心
        self.memory = MemoryCore(config, embedder=self.embedder)

        # 双向激活调度器
        self.hub = ActivationHub(
            self.memory,
            top_k=config.default_top_k,
            threshold=config.recall_threshold,
        )

        # 元认知进化器（持久化到 dashboard_data）
        self.evolver = MetaEvolver(self.engine, memory_core=self.memory,
                                   persist_dir=config.episodic_persist_dir)

    def respond(self, problem: str) -> str:
        """完整管道：拆解 → 双向激活 → 合成 → 应答"""
        # Step 1: 问题拆解
        foci = self.engine.decompose(problem)

        # Step 2: 双向激活记忆
        activated = self.hub.activate(foci)

        # Step 3: 合成 Prompt
        prompt = self._build_prompt(problem, foci, activated)

        # Step 4: 调用 LLM
        answer = self._call_llm(prompt)

        # Step 5: 更新访问计数
        for am in activated:
            am.memory.access_count += 1

        # Step 6: 写入进化器上下文（Alpha 新增）
        self.evolver.set_current_context(foci, activated)

        return answer

    def _build_prompt(
        self,
        problem: str,
        foci: List[Focus],
        memories: List[ActivatedMemory],
    ) -> str:
        """构建 LLM Prompt：框架上下文 + 相关记忆 + 问题"""
        # 框架上下文
        foci_text = "\n".join(
            f"### {i+1}. {f.dimension}\n*触发原因*: {f.rationale}"
            for i, f in enumerate(foci)
        )

        # 记忆参考
        if memories:
            memory_text = "\n\n".join(
                f"**[参考 {i+1}]** (来源: {am.source}, 关联度: {am.activation_score:.3f})\n"
                f"{am.memory.content}"
                for i, am in enumerate(memories)
            )
        else:
            memory_text = "（暂无直接相关的参考信息）"

        prompt = f"""你是一位**智者**，运用系统性的思维框架来分析和回答问题。

## 思维框架
以下是你用来拆解当前问题的思维规律和分析维度：

{foci_text}

## 相关记忆与经验
以下是你过往积累的相关记忆片段和知识：

{memory_text}

## 当前问题
{problem}

---
请综合运用思维框架和相关经验，给出有深度、有洞见的回答。
在回答中：
1. 可以自然融入框架思维，但不必逐条罗列
2. 结合你的经验和知识给出分析
3. 给出综合性的解答与建议"""

        return prompt

    def _call_llm(self, prompt: str) -> str:
        """通过 LiteLLM 统一接口调用大模型"""
        response = completion(
            model=self.config.llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        return response.choices[0].message.content

    def remember(
        self,
        content: str,
        context: Optional[Dict[str, Any]] = None,
        importance: float = 0.5,
    ) -> str:
        """存储情节记忆"""
        return self.memory.remember(content, context, importance)

    def remember_semantic(
        self,
        subject: str,
        predicate: str,
        object_: str,
        confidence: float = 1.0,
    ) -> None:
        """存储语义三元组"""
        self.memory.remember_semantic(subject, predicate, object_, confidence)

    def query_memory(self, query: str, top_k: int = 5) -> List[Dict]:
        """直接查询记忆（绕过框架拆解）"""
        from soma.engine import _extract_keywords

        keywords = _extract_keywords(query, max_keywords=10)
        focus = Focus(
            law_id="direct_query",
            dimension=f"直接查询: {query}",
            keywords=keywords,
            weight=1.0,
            rationale="用户直接查询",
        )
        original_top_k = self.hub.top_k
        self.hub.top_k = top_k
        try:
            activated = self.hub.activate([focus])
        finally:
            self.hub.top_k = original_top_k
        return [self.hub.explain_activation(am) for am in activated]

    def decompose(self, problem: str) -> List[Focus]:
        """暴露思维拆解结果（供可视化和调试）"""
        return self.engine.decompose(problem)

    def reflect(self, task_id: str, outcome: str) -> None:
        """元认知反思"""
        self.evolver.reflect(task_id, outcome)
