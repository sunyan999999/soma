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
    episodic_persist_dir: Path = Path("soma_data")
    llm_model: str = "deepseek-chat"
    llm_api_key: str = ""          # v0.9.2: LLM API Key
    llm_base_url: str = ""         # v0.9.2: LLM 自定义 base_url
    default_top_k: int = 5
    recall_threshold: float = 0.3

    # 自适应参数开关（v0.3.2+）
    adaptive_params: bool = True  # 根据数据量自动调整 top_k/threshold

    # LLM 调用缓存（v0.5.0+）
    llm_cache_ttl: int = 600  # 缓存有效期（秒），默认10分钟
    llm_cache_max_size: int = 50  # 最大缓存条目数

    # 因果抽取（v0.6.0+）
    causal_extraction: bool = False  # 是否在回答后自动抽取因果三元组
    causal_extraction_complexity: int = 3  # 最低复杂度阈值（1-3），仅 >= 此值时触发

    # 嵌入模型配置（Alpha 新增）
    embedding_model_name: str = "BAAI/bge-small-zh-v1.5"
    use_vector_search: bool = True
    vector_dim: int = 512  # BAAI/bge-small-zh-v1.5 实际输出512维
    embedder_device: str = "cpu"  # "cpu" | "cuda"

    # 框架锚定检测（v0.9.1+）
    enable_frame_detection: bool = False
    frame_detection_window: int = 5

    # 多Agent编排（v0.9.2+）
    orchestration_mode: str = "single"      # "single" | "multi"
    orchestration_top_k: int = 3            # 多Agent下最多参与专家数
    orchestration_consensus: str = "voting" # "voting" | "llm_arbitration" | "dialectical_synthesis"

    # ═══ v0.10.0: 记忆分层（L2 Scene + L3 Profile） ═══
    # L2 场景块 — 从多条情节记忆中提取的主题聚合
    scene_extraction_enabled: bool = False          # 是否启用自动场景提取
    scene_extraction_warmup: int = 5                # warmup 稳定阈值：N条新记忆后触发
    scene_extraction_warmup_enabled: bool = True    # 是否启用 warmup 递增（1→2→4→N）
    scene_extraction_min_interval: int = 300        # 两次捕获最小间隔（秒）
    scene_extraction_max_interval: int = 3600       # 最大间隔（秒），保底触发
    scene_extraction_idle_timeout: int = 600        # 无新记忆后空闲超时（秒）

    # L3 用户画像 — 从多个场景块中提取稳定用户特征
    profile_extraction_enabled: bool = False        # 是否启用自动画像提取
    profile_extraction_scene_interval: int = 10     # 每N个新场景触发一次画像更新

    # 检索权重 — Scene/Profile 参与 MemoryCore 检索时的 RRF 权重
    scene_retrieval_weight: float = 0.3             # 场景块检索权重
    profile_retrieval_weight: float = 0.5           # 画像条目检索权重

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
