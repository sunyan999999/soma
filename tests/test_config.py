import tempfile
from pathlib import Path

import pytest
import yaml

from soma.config import SOMAConfig, WisdomLaw, FrameworkConfig, load_config


class TestSOMAConfig:
    def test_default_values(self):
        config = SOMAConfig()
        assert config.framework_path is None  # 默认 None，由 SOMA facade 赋予包内置路径
        assert config.default_top_k == 5
        assert config.recall_threshold == 0.3
        assert config.llm_model == "deepseek-chat"

    def test_custom_values(self):
        config = SOMAConfig(
            llm_model="gpt-4",
            default_top_k=10,
            recall_threshold=0.5,
        )
        assert config.llm_model == "gpt-4"
        assert config.default_top_k == 10
        assert config.recall_threshold == 0.5


class TestWisdomLaw:
    def test_valid_law(self):
        law = WisdomLaw(
            id="first_principles",
            name="第一性原理",
            description="回归事物最基本的要素",
            weight=0.9,
            triggers=["为什么", "本质"],
            relations=["systems_thinking"],
        )
        assert law.id == "first_principles"
        assert law.weight == 0.9

    def test_weight_bounds(self):
        with pytest.raises(ValueError):
            WisdomLaw(id="test", name="test", description="test", weight=1.5)

        with pytest.raises(ValueError):
            WisdomLaw(id="test", name="test", description="test", weight=-0.1)


class TestLoadConfig:
    def test_load_valid(self):
        """从默认 wisdom_laws.yaml 加载"""
        config = load_config(Path("wisdom_laws.yaml"))
        assert config.name == "默认智者思维框架"
        assert config.version == "0.1.0"
        assert len(config.laws) == 7
        assert config.laws[0].id == "first_principles"

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_config(Path("nonexistent.yaml"))

    def test_missing_framework_key(self, tmp_path):
        yaml_path = tmp_path / "bad.yaml"
        yaml_path.write_text("other: data", encoding="utf-8")
        with pytest.raises(ValueError, match="framework"):
            load_config(yaml_path)

    def test_custom_yaml(self, tmp_path):
        data = {
            "framework": {
                "name": "自定义框架",
                "version": "1.0.0",
                "laws": [
                    {
                        "id": "custom_law",
                        "name": "自定义规律",
                        "description": "测试用",
                        "weight": 0.5,
                        "triggers": ["测试"],
                        "relations": [],
                    }
                ],
            }
        }
        yaml_path = tmp_path / "custom.yaml"
        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True)

        config = load_config(yaml_path)
        assert config.name == "自定义框架"
        assert len(config.laws) == 1
        assert config.laws[0].id == "custom_law"
