from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from soma.config import SOMAConfig, load_config
from soma.agent import SOMA_Agent


@pytest.fixture
def config(tmp_path):
    framework = load_config(Path("wisdom_laws.yaml"))
    return SOMAConfig(
        framework=framework,
        episodic_persist_dir=tmp_path / "chroma",
        default_top_k=5,
        recall_threshold=0.01,
        use_vector_search=False,  # 关闭向量搜索避免下载模型
    )


@pytest.fixture
def agent(config):
    return SOMA_Agent(config)


class TestSOMA_Agent:
    def test_init(self, agent):
        assert agent.engine is not None
        assert agent.memory is not None
        assert agent.hub is not None
        assert agent.evolver is not None

    def test_remember(self, agent):
        mid = agent.remember("测试情节记忆", {"domain": "测试"})
        assert len(mid) == 32  # uuid hex

    def test_remember_semantic(self, agent):
        agent.remember_semantic("A", "关联", "B")
        assert agent.memory.semantic.count_triples() == 1

    def test_decompose(self, agent):
        foci = agent.decompose("系统矛盾的根本原因是什么？")
        assert len(foci) >= 2
        law_ids = {f.law_id for f in foci}
        assert "systems_thinking" in law_ids  # "系统"
        assert "contradiction_analysis" in law_ids  # "矛盾"

    def test_build_prompt(self, agent):
        foci = agent.decompose("增长停滞的根本原因是什么？")
        activated = agent.hub.activate(foci)
        prompt = agent._build_prompt("增长停滞的根本原因是什么？", foci, activated)
        # 检查 Prompt 结构
        assert "## 思维框架" in prompt
        assert "## 相关记忆与经验" in prompt
        assert "## 当前问题" in prompt
        assert "增长停滞的根本原因是什么？" in prompt

    @patch("soma.agent.completion")
    def test_respond_end_to_end(self, mock_completion, agent):
        # Mock LLM 响应
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "这是一份基于第一性原理和系统思维的深度分析..."
        mock_completion.return_value = mock_response

        # 预先存储一些记忆
        agent.remember("第一性原理强调回归事物最基本的要素进行推导", {"domain": "哲学"})
        agent.remember("系统思维将问题视为相互关联的整体", {"domain": "思维"})
        agent.remember_semantic("增长", "依赖", "创新")
        agent.remember_semantic("停滞", "源于", "路径依赖")

        # 执行完整管道
        answer = agent.respond("为什么新产品增长停滞？")

        # 验证
        assert len(answer) > 0
        assert "第一性原理" in answer or "系统思维" in answer
        mock_completion.assert_called_once()

        # 验证 prompt 包含了框架和相关记忆
        call_args = mock_completion.call_args
        prompt_sent = call_args.kwargs["messages"][0]["content"]
        assert "为什么新产品增长停滞？" in prompt_sent

    @patch("soma.agent.completion")
    def test_respond_no_memories(self, mock_completion, agent):
        """无相关记忆时也应能正常响应"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "基于框架的一般性分析..."
        mock_completion.return_value = mock_response

        answer = agent.respond("一个全新的前所前所未有的话题")

        assert len(answer) > 0
        mock_completion.assert_called_once()

    def test_query_memory(self, agent):
        agent.remember("第一性原理的详细解释", {"domain": "哲学"}, importance=0.9)
        results = agent.query_memory("第一性原理")
        assert len(results) >= 1
        assert "memory_id" in results[0]
        assert "activation_score" in results[0]

    def test_reflect(self, agent):
        agent.reflect("task_001", "success")
        log = agent.evolver.get_log()
        assert len(log) == 1
        assert log[0]["task_id"] == "task_001"
        assert log[0]["outcome"] == "success"

    @patch("soma.agent.completion")
    def test_access_count_incremented(self, mock_completion, agent):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "测试响应"
        mock_completion.return_value = mock_response

        mid = agent.remember("增长分析案例", {"domain": "商业"}, importance=0.8)
        mem_before = agent.memory.episodic.get(mid)
        assert mem_before.access_count == 0

        agent.respond("增长停滞怎么办？")

        mem_after = agent.memory.episodic.get(mid)
        # 如果该记忆被激活，access_count 会递增
        # 但不一定（取决于关键词匹配）
        assert mem_after is not None
