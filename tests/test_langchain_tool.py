import pytest
from pathlib import Path

from soma.config import SOMAConfig, load_config
from soma.agent import SOMA_Agent
from soma.langchain_tool import create_soma_tool


@pytest.fixture
def soma_agent(tmp_path):
    framework = load_config(Path("wisdom_laws.yaml"))
    config = SOMAConfig(
        framework=framework,
        episodic_persist_dir=tmp_path / "chroma",
        default_top_k=5,
        recall_threshold=0.01,
        use_vector_search=False,
    )
    return SOMA_Agent(config)


class TestLangChainTool:
    def test_create_tool_default_name(self, soma_agent):
        tool = create_soma_tool(soma_agent)
        assert tool.name == "soma_wisdom"
        assert "思维框架" in tool.description

    def test_create_tool_custom_name(self, soma_agent):
        tool = create_soma_tool(soma_agent, name="deep_thinker", description="深度思考引擎")
        assert tool.name == "deep_thinker"
        assert tool.description == "深度思考引擎"

    def test_run_delegates_to_agent(self, soma_agent):
        from unittest.mock import patch

        tool = create_soma_tool(soma_agent)

        with patch("soma.agent.completion") as mock_completion:
            mock_completion.return_value.choices = [
                type("Choice", (), {"message": type("Msg", (), {"content": "思考结果"})()})()
            ]
            result = tool._run("测试问题")

        assert result == "思考结果"

    def test_tool_is_base_tool_subclass(self, soma_agent):
        from langchain_core.tools import BaseTool

        tool = create_soma_tool(soma_agent)
        assert isinstance(tool, BaseTool)
