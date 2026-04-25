from soma.config import SOMAConfig, load_config
from soma.base import MemoryUnit, Focus, ActivatedMemory
from soma.agent import SOMA_Agent

__all__ = ["SOMA", "SOMAConfig", "load_config", "MemoryUnit", "Focus", "ActivatedMemory"]


class SOMA:
    """SOMA 顶层门面，匹配需求文档 9.1 节 API 设计"""

    def __init__(
        self,
        framework_config: str = "wisdom_laws.yaml",
        vector_store: str = "chromadb",
        graph_store: str = "networkx",
        llm: str = "deepseek-chat",
        embedding: str = "openai",
    ):
        self._config = SOMAConfig(
            framework_path=framework_config,
            llm_model=llm,
            embedding_model=embedding,
        )
        self._agent = SOMA_Agent(self._config)

    def respond(self, problem: str) -> str:
        """智慧式应答"""
        return self._agent.respond(problem)

    def remember(
        self, content: str, context: dict = None, importance: float = 0.5
    ) -> str:
        """存储情节记忆"""
        return self._agent.remember(content, context, importance)

    def remember_semantic(
        self, subject: str, predicate: str, object_: str, confidence: float = 1.0
    ) -> None:
        """存储语义三元组"""
        self._agent.remember_semantic(subject, predicate, object_, confidence)

    def query_memory(self, query: str, top_k: int = 5) -> list:
        """查询记忆资粮"""
        return self._agent.query_memory(query, top_k)

    def decompose(self, problem: str) -> list:
        """暴露思维拆解结果"""
        return self._agent.decompose(problem)

    def reflect(self, task_id: str, outcome: str) -> None:
        """元认知反思"""
        self._agent.reflect(task_id, outcome)
