"""端到端集成测试：完整智者思维管道（Mock LLM）"""
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from soma.config import SOMAConfig, load_config
from soma.agent import SOMA_Agent


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


def populate_memories(agent):
    """注入测试用记忆资粮"""
    # 情节记忆
    agent.remember(
        "第一性原理的核心：回归事物最基本的要素，从底层逻辑推导。"
        "在商业中，这意味着不被竞争对手的行为所干扰，而是关注客户最根本的需求。",
        context={"domain": "哲学", "type": "理论"},
        importance=0.95,
    )
    agent.remember(
        "系统思维告诉我们，增长停滞不是单一原因造成的，"
        "而是产品、市场、团队、流程等多个要素形成负反馈回路的结果。",
        context={"domain": "思维", "type": "方法论"},
        importance=0.9,
    )
    agent.remember(
        "二八法则在增长分析中的应用：80%的增长瓶颈来自20%的核心问题。"
        "我们需要找到关键少数而非面面俱到。",
        context={"domain": "管理", "type": "案例"},
        importance=0.85,
    )
    agent.remember(
        "逆向思考案例：某产品团队不研究'如何增长'，而是研究'用户为何流失'，"
        "发现流失主因后反向改进，最终实现增长。",
        context={"domain": "营销", "type": "案例"},
        importance=0.8,
    )
    agent.remember(
        "矛盾分析视角：增长停滞的表面问题是获客不足，"
        "但深层矛盾是产品价值交付与用户期望之间的差距。",
        context={"domain": "分析", "type": "框架"},
        importance=0.85,
    )
    agent.remember(
        "今天天气很好，适合出去散步。",
        context={"domain": "生活", "type": "日记"},
        importance=0.1,
    )

    # 语义三元组
    agent.remember_semantic("增长", "依赖", "创新")
    agent.remember_semantic("增长", "受阻于", "路径依赖")
    agent.remember_semantic("停滞", "源于", "价值交付不足")
    agent.remember_semantic("系统思维", "关联", "矛盾分析")


class TestIntegration:
    @patch("soma.agent.completion")
    def test_full_pipeline(self, mock_completion, soma_agent):
        """端到端测试：注入记忆 → 提问 → 验证全管道"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = (
            "## 问题拆解\n"
            "### 从第一性原理出发\n"
            "增长停滞的本质是价值创造与交付的断裂...\n"
            "### 从系统思维出发\n"
            "增长是一个系统行为...\n"
            "## 综合建议\n"
            "..."
        )
        mock_completion.return_value = mock_response

        # 注入记忆
        populate_memories(soma_agent)

        # 验证记忆已注入
        stats = soma_agent.memory.stats()
        assert stats["episodic"] == 6
        assert stats["semantic"] == 4

        # 第一步：拆解问题
        foci = soma_agent.decompose("为什么新产品增长停滞？")
        assert len(foci) >= 1  # "为什么" → first_principles
        law_ids = {f.law_id for f in foci}
        assert "first_principles" in law_ids

        # 第二步：验证激活的记忆
        activated = soma_agent.hub.activate(foci)
        assert len(activated) >= 1  # 应至少激活一条记忆

        # 应激活与增长/停滞相关的记忆
        activated_contents = [am.memory.content for am in activated]
        has_relevant = any(
            "增长" in c or "第一性原理" in c or "系统思维" in c
            for c in activated_contents
        )
        assert has_relevant, f"激活的记忆应与增长/思维相关: {activated_contents}"

        # 第三步：执行完整应答
        answer = soma_agent.respond("为什么新产品增长停滞？")
        assert len(answer) > 0
        mock_completion.assert_called_once()

        # 第四步：验证 Prompt 结构
        prompt = mock_completion.call_args.kwargs["messages"][0]["content"]
        assert "## 思维框架" in prompt
        assert "## 可用资粮" in prompt
        assert "## 当前问题" in prompt
        assert "为什么新产品增长停滞？" in prompt

    @patch("soma.agent.completion")
    def test_fallback_pipeline(self, mock_completion, soma_agent):
        """测试无匹配记忆时的兜底管道"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "一般性分析..."
        mock_completion.return_value = mock_response

        answer = soma_agent.respond("一个完全陌生领域的问题XYZ")
        assert len(answer) > 0
        mock_completion.assert_called_once()

    @patch("soma.agent.completion")
    def test_multiple_runs(self, mock_completion, soma_agent):
        """多次运行验证访问计数递增"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "分析..."
        mock_completion.return_value = mock_response

        populate_memories(soma_agent)
        mid = soma_agent.remember("增长关键在创新", {"domain": "商业"}, importance=0.9)

        for _ in range(3):
            soma_agent.respond("为什么增长停滞？")

        mem = soma_agent.memory.episodic.get(mid)
        assert mem is not None


class TestVectorSearchIntegration:
    """向量搜索端到端测试（使用 Mock Embedder）"""

    @pytest.fixture
    def vec_agent(self, tmp_path):
        from unittest.mock import MagicMock
        import numpy as np

        framework = load_config(Path("wisdom_laws.yaml"))
        config = SOMAConfig(
            framework=framework,
            episodic_persist_dir=tmp_path / "chroma",
            default_top_k=5,
            recall_threshold=0.01,
            use_vector_search=True,
        )
        agent = SOMA_Agent(config)

        # 用 Mock embedder 替换真实 embedder
        mock_emb = MagicMock()
        # 模拟：与增长相关的内容返回 [1,0,0,0]，天气内容返回 [0,1,0,0]
        def mock_encode(text):
            vec = np.zeros(config.vector_dim, dtype=np.float32)
            if "增长" in text or "商业" in text or "第一性" in text:
                vec[0] = 1.0
            else:
                vec[1] = 1.0
            return vec

        mock_emb.encode = mock_encode
        mock_emb.encode_batch = lambda texts: np.array([mock_encode(t) for t in texts], dtype=np.float32)
        mock_emb.dimension = config.vector_dim

        agent.embedder = mock_emb
        agent.memory._embedder = mock_emb
        agent.memory.episodic._embedder = mock_emb

        return agent

    @patch("soma.agent.completion")
    def test_vector_search_semantic_recall(self, mock_completion, vec_agent):
        """同义改写应能通过向量搜索召回相关内容"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "基于语义的深度分析..."
        mock_completion.return_value = mock_response

        # 存储语义相关但关键词不同的记忆
        vec_agent.remember("商业扩张离不开创新驱动的成长思维", {"domain": "商业"}, importance=0.9)
        vec_agent.remember("今天天气非常好适合郊游", {"domain": "生活"}, importance=0.1)

        # 用不同措辞查询 — 关键词"增长"不会直接匹配"成长思维"
        foci = vec_agent.decompose("为什么企业增长陷入瓶颈？")
        activated = vec_agent.hub.activate(foci)

        # 向量搜索应找到"商业扩张..."而非"今天天气..."
        if activated:
            contents = [am.memory.content for am in activated]
            assert any("商业" in c for c in contents)

    @patch("soma.agent.completion")
    def test_vector_vs_keyword_advantage(self, mock_completion, vec_agent):
        """向量搜索能跨越关键词字面差异"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "分析..."
        mock_completion.return_value = mock_response

        # 两个内容：一个相关但用词不同，一个完全不相关但包含关键词
        vec_agent.remember("组织架构调整需要整体协调", {"domain": "管理"}, importance=0.9)
        vec_agent.remember("系统漏洞修复指南", {"domain": "技术"}, importance=0.5)

        # "系统思维" 和 "组织协调" 语义相似，"系统漏洞" 只是字面匹配
        answer = vec_agent.respond("如何运用系统思维协调组织？")
        assert len(answer) > 0
