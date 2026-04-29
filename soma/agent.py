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

        # 保存最近一次构建的 prompt（供仪表盘可视化）
        self._last_prompt: str = ""

    def respond(self, problem: str) -> str:
        """完整管道：拆解 → 双向激活 → 合成 → 应答"""
        import time

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

        # Step 6: 写入进化器上下文
        self.evolver.set_current_context(foci, activated)

        # Step 7: 录制 session（供仪表盘消费）
        self.record_session(problem, answer, foci, activated)

        return answer

    def record_session(
        self, problem: str, answer: str,
        foci: List[Focus], activated: List[ActivatedMemory],
    ) -> None:
        """录制一次对话会话到 AnalyticsStore。

        供所有调用路径（respond / chat / 外部流式）统一使用。
        接入方在流式收集完 answer 后调用此方法即可。
        """
        import sys, time
        try:
            from soma.analytics import AnalyticsStore
            store = AnalyticsStore(self.config.episodic_persist_dir)
            store.record_session({
                "id": f"session_{int(time.time())}",
                "problem": problem,
                "mock_mode": False,
                "provider_used": self.config.llm_model or "unknown",
                "response_time_ms": 0,
                "foci": [{"law_id": f.law_id, "dimension": f.dimension,
                          "keywords": f.keywords[:8], "weight": f.weight,
                          "rationale": f.rationale} for f in foci],
                "activated_memories": [self.hub.explain_activation(am) for am in activated],
                "answer": answer,
                "prompt": getattr(self, '_last_prompt', ''),
                "memory_stats": self.memory.stats(),
                "weights": self.evolver.get_weights(),
            })
        except Exception as e:
            print(f"[soma] 录制会话失败 (dir={self.config.episodic_persist_dir}): {e}",
                  file=sys.stderr)

    def _build_prompt(
        self,
        problem: str,
        foci: List[Focus],
        memories: List[ActivatedMemory],
    ) -> str:
        """构建 LLM Prompt：思考角度 + 相关记忆 + 问题"""
        # 思考角度 — 剥离规律名称，只保留思考方向描述
        angles = []
        for i, f in enumerate(foci):
            clean = f.dimension
            # 去掉 "从「规律名」出发：" 或 "从「规律名」视角审视：" 前缀
            if "出发：" in clean:
                clean = clean.split("出发：", 1)[1]
            elif "视角审视：" in clean:
                clean = clean.split("视角审视：", 1)[1]
            # 去掉尾部 "应用于问题：「...」"
            if "。应用于问题：" in clean:
                clean = clean.split("。应用于问题：")[0]
            angles.append(f"{i+1}. {clean}")
        foci_text = "\n".join(angles)

        # 记忆参考
        if memories:
            memory_text = "\n\n".join(
                f"**[参考 {i+1}]** (来源: {am.source}, 关联度: {am.activation_score:.3f})\n"
                f"{am.memory.content}"
                for i, am in enumerate(memories)
            )
        else:
            memory_text = "（暂无直接相关的参考信息）"

        prompt = f"""你是一位**智者**，善于从多个角度深入思考问题。

## 思考角度
针对当前问题，可以从以下角度切入分析：

{foci_text}

## 相关记忆与经验
以下是你过往积累的相关记忆片段和知识：

{memory_text}

## 当前问题
{problem}

---
请综合以上思考角度和相关经验，给出有深度、有洞见的回答。
重要：
1. **不要在回答中提及任何规律、理论或框架的名称**，将思考方式自然融入分析
2. 用日常交流的语言表达，像一位智者在自然交谈
3. 给出综合性的解答与建议"""

        self._last_prompt = prompt
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
