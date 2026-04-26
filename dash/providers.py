"""大模型提供商管理 — 支持 11 个主流模型 + 自定义接口"""
import json
import os
from copy import deepcopy
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, Optional

CONFIG_PATH = Path(__file__).parent / "llm_config.json"

# ── 预定义提供商 ──────────────────────────────────────────────

PRESET_PROVIDERS = {
    "deepseek": {
        "name": "DeepSeek",
        "model": "deepseek/deepseek-chat",
        "api_key_env": "DEEPSEEK_API_KEY",
        "base_url": "",
        "description": "DeepSeek V3/R1 系列",
    },
    "qwen": {
        "name": "通义千问 (Qwen)",
        "model": "openai/qwen-plus",
        "api_key_env": "DASHSCOPE_API_KEY",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "description": "阿里通义千问系列",
    },
    "gemini": {
        "name": "Gemini",
        "model": "gemini/gemini-2.5-pro-exp-03-25",
        "api_key_env": "GEMINI_API_KEY",
        "base_url": "",
        "description": "Google Gemini 2.5 Pro 实验版",
    },
    "claude": {
        "name": "Claude",
        "model": "anthropic/claude-sonnet-4-20250514",
        "api_key_env": "ANTHROPIC_API_KEY",
        "base_url": "",
        "description": "Anthropic Claude Sonnet 4",
    },
    "doubao": {
        "name": "豆包 (Doubao)",
        "model": "openai/doubao-1.5-thinking-pro-250428",
        "api_key_env": "DOUBAO_API_KEY",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "description": "字节豆包 1.5 思考版",
    },
    "gemma": {
        "name": "Gemma",
        "model": "gemini/gemma-3-27b-it",
        "api_key_env": "GEMINI_API_KEY",
        "base_url": "",
        "description": "Google 开源 Gemma 3 27B",
    },
    "openai": {
        "name": "OpenAI",
        "model": "openai/gpt-4o",
        "api_key_env": "OPENAI_API_KEY",
        "base_url": "",
        "description": "GPT-4o 多模态旗舰",
    },
    "zhipu": {
        "name": "智谱 (GLM)",
        "model": "openai/glm-4-plus",
        "api_key_env": "ZHIPU_API_KEY",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "description": "智谱 GLM-4-Plus",
    },
    "minimax": {
        "name": "MiniMax",
        "model": "openai/MiniMax-M1",
        "api_key_env": "MINIMAX_API_KEY",
        "base_url": "https://api.minimax.chat/v1",
        "description": "MiniMax M1 标准版",
    },
    "kimi": {
        "name": "Kimi (月之暗面)",
        "model": "openai/moonshot-v1-128k",
        "api_key_env": "MOONSHOT_API_KEY",
        "base_url": "https://api.moonshot.cn/v1",
        "description": "Kimi/Moonshot 128K 长文本版",
    },
    "custom": {
        "name": "自定义",
        "model": "",
        "api_key_env": "",
        "base_url": "",
        "description": "任何兼容 OpenAI API 的服务",
    },
}


# ── 配置管理器 ────────────────────────────────────────────────

class ProviderManager:
    """提供商配置管理器，持久化到 JSON 文件"""

    def __init__(self):
        self._config = self._load()

    def _load(self) -> dict:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
        else:
            saved = {}

        # 合并预设 + 已保存配置
        config = {
            "current_provider": saved.get("current_provider", "deepseek"),
            "providers": {},
        }

        for pid, preset in PRESET_PROVIDERS.items():
            saved_p = saved.get("providers", {}).get(pid, {})
            # API key 优先级: 保存的 > 环境变量
            saved_api_key = saved_p.get("api_key", "")
            env_key = os.environ.get(preset["api_key_env"], "") if preset["api_key_env"] else ""
            config["providers"][pid] = {
                **deepcopy(preset),
                "api_key": saved_api_key if saved_api_key else env_key,
                "model": saved_p.get("model", preset["model"]),
                "base_url": saved_p.get("base_url", preset["base_url"]),
            }

        return config

    def save(self):
        """持久化（仅保存非敏感的配置，API key 仅保留用户显式填写的）"""
        out = {"current_provider": self._config["current_provider"], "providers": {}}
        for pid, p in self._config["providers"].items():
            preset = PRESET_PROVIDERS[pid]
            saved = {}
            if p["model"] != preset["model"]:
                saved["model"] = p["model"]
            if p["api_key"] and p["api_key"] != os.environ.get(preset["api_key_env"], ""):
                saved["api_key"] = p["api_key"]
            if p["base_url"] != preset["base_url"]:
                saved["base_url"] = p["base_url"]
            out["providers"][pid] = saved
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)

    def get_current(self) -> dict:
        return self._config["providers"][self._config["current_provider"]]

    def get_providers(self) -> dict:
        """返回所有提供商列表（API key 脱敏）"""
        result = {"current_provider": self._config["current_provider"], "providers": {}}
        for pid, p in self._config["providers"].items():
            masked = {**p}
            if masked["api_key"]:
                key = masked["api_key"]
                if len(key) > 8:
                    masked["api_key"] = key[:4] + "****" + key[-4:]
                else:
                    masked["api_key"] = "****"
            masked.pop("api_key_env", None)
            result["providers"][pid] = masked
        return result

    def switch_provider(self, provider_id: str) -> bool:
        if provider_id not in self._config["providers"]:
            return False
        self._config["current_provider"] = provider_id
        self.save()
        return True

    def update_provider(self, provider_id: str, api_key: Optional[str] = None,
                        model: Optional[str] = None, base_url: Optional[str] = None) -> bool:
        if provider_id not in self._config["providers"]:
            return False
        p = self._config["providers"][provider_id]
        if api_key is not None:
            p["api_key"] = api_key
        if model is not None and model.strip():
            p["model"] = model.strip()
        if base_url is not None:
            p["base_url"] = base_url.strip()
        self.save()
        return True

    @property
    def current_provider_id(self) -> str:
        return self._config["current_provider"]


# ── 全局单例 ──────────────────────────────────────────────────

_manager: Optional[ProviderManager] = None


def get_provider_manager() -> ProviderManager:
    global _manager
    if _manager is None:
        _manager = ProviderManager()
    return _manager
