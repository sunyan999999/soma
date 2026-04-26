"""抽象基类 — 定义 SOMA 核心组件的契约接口"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import numpy as np


class BaseMemoryStore(ABC):
    """记忆存储的抽象契约"""

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
