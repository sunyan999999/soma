"""抽象基类 — 定义 SOMA 核心组件的契约接口"""

from abc import ABC, abstractmethod
from typing import Any, Iterator, List, Optional

import numpy as np


class BaseMemoryStore(ABC):
    """记忆存储的抽象契约 — 继承实现以接入新的数据库后端"""

    def store(self, content: str, context: Optional[dict] = None,
              importance: float = 0.5) -> str:
        """存储一条记忆，返回 memory_id（默认未实现）"""
        raise NotImplementedError(f"{type(self).__name__}.store() 未实现")

    def query(self, query_text: str, top_k: int = 10) -> List[Any]:
        """检索与查询文本最相关的 top_k 条记忆（默认未实现）"""
        raise NotImplementedError(f"{type(self).__name__}.query() 未实现")

    def delete(self, memory_id: str) -> bool:
        """删除指定记忆，返回是否成功（默认未实现）"""
        raise NotImplementedError(f"{type(self).__name__}.delete() 未实现")

    @abstractmethod
    def count(self) -> int:
        """返回存储条目数"""
        ...


class BaseEmbedder(ABC):
    """文本嵌入器的抽象契约"""

    @abstractmethod
    def encode(self, text: str) -> np.ndarray:
        """编码单条文本为向量"""
        ...

    @abstractmethod
    def encode_batch(self, texts: List[str]) -> np.ndarray:
        """批量编码文本为向量"""
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        """返回嵌入向量维度"""
        ...


class BaseFrameworkEngine(ABC):
    """思维框架引擎的抽象契约"""

    @abstractmethod
    def decompose(self, problem: str) -> List[Any]:
        """将问题拆解为分析焦点列表"""
        ...


class BaseLLM(ABC):
    """大语言模型调用的抽象契约 — 继承实现以接入新的 LLM 后端"""

    @abstractmethod
    def complete(self, prompt: str) -> str:
        """发送 prompt，返回完整响应文本"""
        ...

    @abstractmethod
    def complete_stream(self, prompt: str) -> Iterator[str]:
        """发送 prompt，返回增量 token 迭代器"""
        ...
