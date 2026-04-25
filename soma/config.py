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

    framework_path: Path = Path("wisdom_laws.yaml")
    episodic_persist_dir: Path = Path("chroma_data")
    llm_model: str = "deepseek-chat"
    embedding_model: str = "text-embedding-ada-002"
    default_top_k: int = 5
    recall_threshold: float = 0.3

    # Lazily loaded framework config
    framework: Optional[FrameworkConfig] = None


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
