from pathlib import Path
from typing import List, Optional

import yaml
from pydantic import BaseModel, Field


class WisdomLaw(BaseModel):
    """单条思维规律"""

    id: str
    name: str
    description: str
    weight: float = Field(ge=0.0, le=1.0)
    triggers: List[str] = Field(default_factory=list)
    relations: List[str] = Field(default_factory=list)


class FrameworkConfig(BaseModel):
    """思维框架配置"""

    name: str
    version: str
    laws: List[WisdomLaw]


class SOMAConfig(BaseModel):
    """SOMA 顶层配置"""

    framework_path: Optional[Path] = None
    episodic_persist_dir: Path = Path("chroma_data")
    llm_model: str = "deepseek-chat"
    default_top_k: int = 5
    recall_threshold: float = 0.3

    # 自适应参数开关（v0.3.2+）
    adaptive_params: bool = True  # 根据数据量自动调整 top_k/threshold

    # 嵌入模型配置（Alpha 新增）
    embedding_model_name: str = "BAAI/bge-small-zh-v1.5"
    use_vector_search: bool = True
    vector_dim: int = 512
    embedder_device: str = "cpu"  # "cpu" | "cuda"

    # Lazily loaded framework config
    framework: Optional[FrameworkConfig] = None


def adaptive_top_k(data_count: int) -> int:
    """根据记忆总量自适应调整 top_k

    原则：数据量越大，top_k 越大以捕获更多候选；
    但上限为 10，避免噪声过多。
    """
    if data_count < 500:
        return 3
    elif data_count < 2000:
        return 5
    elif data_count < 10000:
        return 8
    else:
        return 10


def adaptive_recall_threshold(data_count: int) -> float:
    """根据记忆总量自适应调整 recall_threshold

    原则：数据量越大，阈值越低以放宽召回；
    数据量小则严格过滤避免不相关记忆。
    """
    if data_count < 500:
        return 0.05
    elif data_count < 2000:
        return 0.02
    elif data_count < 10000:
        return 0.01
    else:
        return 0.005


def load_config(yaml_path: Path) -> FrameworkConfig:
    """从 YAML 文件加载思维框架配置"""
    if not yaml_path.exists():
        raise FileNotFoundError(f"思维框架配置文件不存在: {yaml_path}")

    with open(yaml_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    framework_data = raw.get("framework")
    if framework_data is None:
        raise ValueError("YAML 缺少顶层 'framework' 键")

    return FrameworkConfig(**framework_data)
