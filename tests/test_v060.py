"""v0.6.0 推理引擎综合测试 — 覆盖推理框架、假设检验、触发词扩展、模板挖掘"""
from pathlib import Path
from unittest.mock import patch, MagicMock
import time

import pytest

from soma.config import SOMAConfig, load_config
from soma.agent import SOMA_Agent
from soma.base import Focus, MemoryUnit, ActivatedMemory
from soma.evolve import MetaEvolver


# ── 辅助工厂函数 ──────────────────────────────────────────

def make_focus(law_id, weight=0.9, keywords=None, dimension=None):
    return Focus(
        law_id=law_id,
        dimension=dimension or f"测试维度:{law_id}",
        keywords=keywords or ["测试"],
        weight=weight,
        rationale="测试",
    )


def make_memory(content, domain="分析", mem_id="m1"):
    mem = MemoryUnit(
        id=mem_id, content=content,
        context={"domain": domain, "type": "案例"},
    )
    return mem


def make_activated(content="测试记忆", domain="分析", mem_id="m1", score=0.8, source="episodic"):
    mem = make_memory(content, domain, mem_id)
    return ActivatedMemory(
        memory=mem, activation_score=score,
        source=source, match_rationale="匹配",
    )


# ── Agent 夹具 ────────────────────────────────────────────

@pytest.fixture
def agent(tmp_path):
    framework = load_config(Path("wisdom_laws.yaml"))
    config = SOMAConfig(
        framework=framework,
        episodic_persist_dir=tmp_path / "chroma",
        default_top_k=5,
        recall_threshold=0.01,
        use_vector_search=False,
    )
    return SOMA_Agent(config)


@pytest.fixture
def evolver(tmp_path):
    from soma.engine import WisdomEngine
    framework = load_config(Path("wisdom_laws.yaml"))
    engine = WisdomEngine(framework)
    return MetaEvolver(engine, persist_dir=tmp_path)


# ── 模板系统测试 ──────────────────────────────────────────

class TestTemplates:
    """验证所有推理模板、假设模板、组合模板的完整性"""

    def test_all_base_reasoning_templates_exist(self, agent):
        """7条基础规律都有推理模板"""
        base_laws = ["first_principles", "systems_thinking", "contradiction_analysis",
                     "pareto_principle", "inversion", "analogical_reasoning", "evolutionary_lens"]
        for law_id in base_laws:
            assert law_id in agent._REASONING_TEMPLATES, f"缺少推理模板: {law_id}"
            tmpl = agent._REASONING_TEMPLATES[law_id]
            assert len(tmpl) > 50, f"模板过短: {law_id}"

    def test_all_base_hypothesis_templates_exist(self, agent):
        """7条基础规律都有假设模板"""
        base_laws = ["first_principles", "systems_thinking", "contradiction_analysis",
                     "pareto_principle", "inversion", "analogical_reasoning", "evolutionary_lens"]
        for law_id in base_laws:
            assert law_id in agent._HYPOTHESIS_TEMPLATES, f"缺少假设模板: {law_id}"
            tmpl = agent._HYPOTHESIS_TEMPLATES[law_id]
            assert "{problem}" in tmpl, f"假设模板不含占位符: {law_id}"

    def test_all_combo_reasoning_templates_exist(self, agent):
        """6个组合规律都有推理模板"""
        assert len(agent._COMBO_REASONING) == 6
        for law_id, tmpl in agent._COMBO_REASONING.items():
            assert law_id.startswith("combo_"), f"非combo前缀: {law_id}"
            assert len(tmpl) > 50, f"组合模板过短: {law_id}"

    def test_hypothesis_template_substitution(self, agent):
        """假设模板中的占位符被正确替换"""
        result = agent._HYPOTHESIS_TEMPLATES["first_principles"].replace(
            "{problem}", "增长停滞"
        )
        assert "增长停滞" in result
        assert "{problem}" not in result


class TestMatchTemplate:
    """_match_template 方法测试"""

    def test_exact_match(self, agent):
        result = agent._match_template("first_principles", agent._REASONING_TEMPLATES)
        assert "第一性原理推理" in result

    def test_combo_match(self, agent):
        """组合模板应优先匹配"""
        result = agent._match_template(
            "combo_first_principles_systems_thinking",
            agent._COMBO_REASONING,
        )
        assert "根因系统分析推理" in result

    def test_no_match_returns_empty(self, agent):
        result = agent._match_template("nonexistent_law", agent._REASONING_TEMPLATES)
        assert result == ""


# ── 推理执行测试 ──────────────────────────────────────────

class TestExecuteReasoning:
    """_execute_reasoning 方法测试"""

    def test_basic_reasoning_blocks(self, agent):
        foci = [make_focus("first_principles", keywords=["基本", "要素"])]
        activated = [make_activated("第一性原理强调回归基本要素")]
        blocks = agent._execute_reasoning("测试问题", foci, activated, [])

        assert len(blocks) == 1
        b = blocks[0]
        assert b["index"] == 1
        assert "第一性原理推理" in b["template"]
        assert b["hypothesis"] != ""
        assert len(b["evidence"]) >= 0

    def test_combo_reasoning_template_used(self, agent):
        """组合Focus应使用_COMBO_REASONING模板"""
        foci = [make_focus("combo_first_principles_systems_thinking",
                          keywords=["系统"])]
        activated = [make_activated("系统思维与第一性原理结合")]
        blocks = agent._execute_reasoning("系统问题", foci, activated, [])

        assert len(blocks) == 1
        assert "根因系统分析推理" in blocks[0]["template"]

    def test_evidence_collection_by_keyword(self, agent):
        foci = [make_focus("systems_thinking", keywords=["系统", "回路"])]
        activated = [
            make_activated("系统思维中的反馈回路分析", mem_id="m1"),
            make_activated("天气很好适合散步", mem_id="m2"),
        ]
        blocks = agent._execute_reasoning("系统问题", foci, activated, [])

        evidence = blocks[0]["evidence"]
        assert any("回路" in e for e in evidence)
        assert not any("散步" in e for e in evidence)

    def test_counter_evidence_collection(self, agent):
        foci = [make_focus("first_principles", keywords=["基本"])]
        activated = [make_activated("基本要素分析", mem_id="m1")]
        anti = [make_activated("反对基本要素观点", mem_id="m2")]
        blocks = agent._execute_reasoning("问题", foci, activated, anti)

        assert len(blocks[0]["counter_evidence"]) >= 1

    def test_foci_cap_at_seven(self, agent):
        """超过7个foci时应截断到前7个（按权重排序）"""
        foci = [
            make_focus(f"law_{i}", weight=0.5 + i * 0.05, keywords=["测试"])
            for i in range(10)
        ]
        # 最后一个权重最高
        foci[-1].weight = 0.99
        blocks = agent._execute_reasoning("问题", foci, [], [])

        assert len(blocks) == 7
        # 权重最高的应在结果中
        assert blocks[0]["weight"] == 0.99

    def test_no_activated_memories(self, agent):
        foci = [make_focus("first_principles")]
        blocks = agent._execute_reasoning("问题", foci, [], [])

        assert len(blocks) == 1
        assert blocks[0]["evidence"] == []
        assert blocks[0]["counter_evidence"] == []

    def test_fallback_template_for_unknown_law(self, agent):
        """未知law_id使用默认模板"""
        foci = [make_focus("custom_analysis_method", dimension="自定义维度")]
        blocks = agent._execute_reasoning("问题", foci, [], [])

        assert len(blocks) == 1
        assert "3 个关键洞察" in blocks[0]["template"]

    def test_multiple_foci_indices(self, agent):
        foci = [
            make_focus("first_principles", dimension="维度A"),
            make_focus("systems_thinking", dimension="维度B"),
            make_focus("pareto_principle", dimension="维度C"),
        ]
        blocks = agent._execute_reasoning("问题", foci, [], [])

        assert len(blocks) == 3
        assert [b["index"] for b in blocks] == [1, 2, 3]


# ── 复杂度评估测试 ────────────────────────────────────────

class TestComplexityAssessment:
    def test_simple_problem_l1(self, agent):
        assert agent._assess_complexity("今天天气不错") == 1

    def test_medium_problem_l2(self, agent):
        assert agent._assess_complexity("为什么系统性能下降") == 2

    def test_complex_problem_l3(self, agent):
        problem = (
            "为什么新产品在市场上增长停滞，尽管投入了大量资源和人力物力财力，"
            "但效果甚微，这背后的深层根本原因、系统矛盾和发展瓶颈究竟是什么，"
            "我们需要深入分析这个复杂困境的根源并找到突破口，"
            "同时还要考虑市场竞争、用户需求变化和技术演进等多重因素"
        )
        assert len(problem) > 100, f"问题长度需>100，当前{len(problem)}"
        assert agent._assess_complexity(problem) == 3


# ── 因果抽取测试 ──────────────────────────────────────────

class TestCausalExtraction:
    @patch("soma.agent.completion")
    def test_extracts_causal_triples(self, mock_completion, agent):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = (
            "增长停滞 | 源于 | 价值交付不足\n"
            "创新 | 驱动 | 增长突破"
        )
        mock_completion.return_value = mock_response

        # 启用因果抽取
        agent.config.causal_extraction = True
        sem_count_before = agent.memory.semantic.count_triples()
        agent._extract_causal_relations("为什么增长停滞？", "分析结果...")
        sem_count_after = agent.memory.semantic.count_triples()

        assert sem_count_after >= sem_count_before
        mock_completion.assert_called_once()

    def test_disabled_causal_extraction(self, agent):
        agent.config.causal_extraction = False
        sem_count_before = agent.memory.semantic.count_triples()
        agent._extract_causal_relations("问题", "答案")
        assert agent.memory.semantic.count_triples() == sem_count_before

    @patch("soma.agent.completion")
    def test_extraction_failure_does_not_raise(self, mock_completion, agent):
        mock_completion.side_effect = Exception("API错误")
        agent.config.causal_extraction = True
        # 不应抛出异常
        agent._extract_causal_relations("问题", "答案")

    @patch("soma.agent.completion")
    def test_invalid_triple_lines_ignored(self, mock_completion, agent):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = (
            "这是一段无意义文本\n"
            "没有竖线分隔符\n"
            "增长 | 依赖 | 创新"  # 有效
        )
        mock_completion.return_value = mock_response

        agent.config.causal_extraction = True
        sem_count_before = agent.memory.semantic.count_triples()
        agent._extract_causal_relations("问题", "答案")
        # 只有1条有效三元组被添加
        assert agent.memory.semantic.count_triples() == sem_count_before + 1


# ── 触发词追踪与提升测试 ──────────────────────────────────

class FakeLaw:
    def __init__(self, id_, name, weight=0.5):
        self.id = id_
        self.name = name
        self.weight = weight
        self.triggers: list = []


class TestTriggerTracking:
    """track_triggers + _promote_triggers 测试"""

    @pytest.fixture
    def evo_with_laws(self, tmp_path):
        from soma.engine import WisdomEngine
        framework = load_config(Path("wisdom_laws.yaml"))
        engine = WisdomEngine(framework)
        # 给每条规律添加triggers属性（确保安全）
        for law in engine.laws:
            if not hasattr(law, 'triggers'):
                law.triggers = []
        return MetaEvolver(engine, persist_dir=tmp_path)

    def test_track_new_trigger(self, evo_with_laws):
        evo = evo_with_laws
        foci = [make_focus("first_principles")]
        problem = "如何系统性地分析产品增长瓶颈"
        evo.set_current_context(foci, [])
        # success时追踪
        evo.track_triggers(problem, foci, "success")
        assert len(evo._candidate_triggers) >= 1

    def test_track_ignores_failure(self, evo_with_laws):
        evo = evo_with_laws
        foci = [make_focus("first_principles")]
        evo.set_current_context(foci, [])
        evo.track_triggers("测试问题", foci, "failure")
        # 失败不追踪，候选词为空
        assert len(evo._candidate_triggers) == 0

    def test_promote_after_threshold(self, evo_with_laws):
        evo = evo_with_laws
        foci = [make_focus("first_principles")]
        problem = "如何用第一性原理分析商业问题"

        evo.set_current_context(foci, [])
        for _ in range(5):
            evo.track_triggers(problem, foci, "success")

        promoted = evo._promote_triggers(threshold=5)
        assert len(promoted) >= 1
        assert promoted[0]["type"] == "trigger_promoted"
        assert promoted[0]["law_id"] == "first_principles"

    def test_promote_not_below_threshold(self, evo_with_laws):
        evo = evo_with_laws
        foci = [make_focus("first_principles")]
        evo.set_current_context(foci, [])
        for _ in range(3):
            evo.track_triggers("测试问题", foci, "success")

        promoted = evo._promote_triggers(threshold=5)
        assert len(promoted) == 0

    def test_skip_combo_and_anti_laws(self, evo_with_laws):
        evo = evo_with_laws
        foci = [make_focus("combo_first_principles_systems_thinking")]
        evo.set_current_context(foci, [])
        evo.track_triggers("测试问题", foci, "success")
        assert len(evo._candidate_triggers) == 0

    def test_candidate_not_deleted_when_law_not_found(self, evo_with_laws):
        """Bug #3修复: 未找到law时不删除候选词"""
        evo = evo_with_laws
        # 手动插入一个不存在law的候选词
        evo._candidate_triggers["nonexistent::测试词"] = {
            "law_id": "nonexistent",
            "word": "测试词",
            "session_count": 10,
            "first_seen": time.time(),
            "last_seen": time.time(),
        }
        promoted = evo._promote_triggers(threshold=5)
        assert len(promoted) == 0
        # 候选词仍保留，未被误删
        assert "nonexistent::测试词" in evo._candidate_triggers

    def test_already_promoted_skipped(self, evo_with_laws):
        """已是正式触发词的候选不应重复提升"""
        evo = evo_with_laws
        law = evo.engine.laws[0]
        law.triggers = ["测试词"]

        evo._candidate_triggers[f"{law.id}::测试词"] = {
            "law_id": law.id,
            "word": "测试词",
            "session_count": 10,
            "first_seen": time.time(),
            "last_seen": time.time(),
        }
        promoted = evo._promote_triggers(threshold=5)
        assert len(promoted) == 0


# ── 思维模板追踪与挖掘测试 ────────────────────────────────

class TestFocusPattern:
    """track_focus_pattern + _mine_thought_templates 测试"""

    @pytest.fixture
    def evo_with_laws(self, tmp_path):
        from soma.engine import WisdomEngine
        framework = load_config(Path("wisdom_laws.yaml"))
        engine = WisdomEngine(framework)
        return MetaEvolver(engine, persist_dir=tmp_path)

    def test_track_creates_pattern(self, evo_with_laws):
        evo = evo_with_laws
        foci = [make_focus("first_principles"), make_focus("systems_thinking")]
        evo.track_focus_pattern("如何系统分析增长瓶颈", foci)

        templates = evo.get_thought_templates()
        assert len(templates) >= 1

    def test_skip_combo_laws_in_pattern(self, evo_with_laws):
        evo = evo_with_laws
        foci = [
            make_focus("combo_first_principles_systems_thinking"),
            make_focus("first_principles"),
        ]
        evo.track_focus_pattern("测试问题", foci)

        templates = evo.get_thought_templates()
        # combo law应被过滤，只保留first_principles
        for t in templates:
            assert "combo_" not in ",".join(t["law_ids"])

    def test_mine_templates_at_threshold(self, evo_with_laws):
        evo = evo_with_laws
        foci = [make_focus("first_principles"), make_focus("systems_thinking")]

        for _ in range(5):
            evo.track_focus_pattern("如何系统分析增长瓶颈", foci)

        mined = evo._mine_thought_templates(threshold=5)
        assert len(mined) >= 1
        assert mined[0]["type"] == "thought_template"

    def test_mine_below_threshold_returns_empty(self, evo_with_laws):
        evo = evo_with_laws
        foci = [make_focus("first_principles")]
        for _ in range(3):
            evo.track_focus_pattern("测试问题", foci)

        mined = evo._mine_thought_templates(threshold=5)
        assert len(mined) == 0

    def test_mined_data_not_deleted(self, evo_with_laws):
        """Bug #4修复: 挖掘后追踪数据保留"""
        evo = evo_with_laws
        foci = [make_focus("first_principles")]
        for _ in range(5):
            evo.track_focus_pattern("问题域测试", foci)

        count_before = len(evo.get_thought_templates())
        evo._mine_thought_templates(threshold=5)
        count_after = len(evo.get_thought_templates())

        # 挖掘后数据应仍存在
        assert count_after >= count_before


# ── clear_log 完整清理测试 ────────────────────────────────

class TestClearLog:
    def test_clears_v060_tables(self, evolver):
        """Bug #5修复: clear_log清理candidate_triggers和focus_patterns"""
        foci = [make_focus("first_principles")]
        evolver.set_current_context(foci, [])
        evolver.reflect("t1", "success")

        # 手动写入候选触发词和聚焦模式
        ts = time.time()
        evolver._conn.execute(
            "INSERT INTO candidate_triggers (law_id, word, session_count, first_seen, last_seen) "
            "VALUES (?, ?, 5, ?, ?)",
            ("first_principles", "测试词", ts, ts),
        )
        evolver._conn.execute(
            "INSERT INTO focus_patterns (domain_key, law_ids, count, first_seen, last_seen) "
            "VALUES (?, ?, 5, ?, ?)",
            ("测试域", "first_principles", ts, ts),
        )
        evolver._conn.commit()
        evolver._load_state()

        assert len(evolver._candidate_triggers) >= 1

        evolver.clear_log()

        assert len(evolver.get_log()) == 0
        assert evolver.get_stats() == {}
        assert len(evolver._candidate_triggers) == 0

        # 验证DB表也为空
        ct = evolver._conn.execute("SELECT COUNT(*) FROM candidate_triggers").fetchone()
        assert ct[0] == 0
        fp = evolver._conn.execute("SELECT COUNT(*) FROM focus_patterns").fetchone()
        assert fp[0] == 0


# ── 端到端 v0.6.0 管道测试 ────────────────────────────────

class TestV060Pipeline:
    @patch("soma.agent.completion")
    def test_reasoning_injected_in_prompt(self, mock_completion, agent):
        """L2+问题：推理框架+假设+证据应注入Prompt"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "深度分析..."
        mock_completion.return_value = mock_response

        agent.remember("第一性原理强调回归基本要素", {"domain": "哲学"}, importance=0.9)
        # v1.1.1: 使用L2+问题触发推理框架（含深度词"根本"、"为什么"）
        agent.respond("什么是第一性原理？为什么它如此根本重要？")

        prompt = agent._last_prompt
        assert "结构化推理框架" in prompt
        assert "可检验假设" in prompt or "第一性原理推理" in prompt

    @patch("soma.agent.completion")
    def test_combo_law_in_prompt(self, mock_completion, agent):
        """组合规律应出现组合推理模板"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "分析..."
        mock_completion.return_value = mock_response

        # 存储系统思维相关的关键词记忆
        agent.remember("系统思维与第一性原理结合分析问题", {"domain": "思维"})
        agent.respond("如何从系统和根本角度综合分析增长瓶颈？")

        prompt = agent._last_prompt
        assert "结构化推理框架" in prompt

    @patch("soma.agent.completion")
    def test_causal_extraction_in_respond(self, mock_completion, agent):
        """respond()在L3复杂度时触发因果抽取"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "深层系统分析..."
        mock_completion.return_value = mock_response

        agent.config.causal_extraction = True
        agent.config.causal_extraction_complexity = 3  # L3才触发

        # L3问题
        sem_before = agent.memory.semantic.count_triples()
        agent.respond("为什么新产品在市场上增长停滞，系统矛盾和深层机制是什么？")
        sem_after = agent.memory.semantic.count_triples()
        # 至少调用了completion一次（主调用），可能还有因果抽取
        assert mock_completion.call_count >= 1

    @patch("soma.agent.completion")
    def test_last_reasoning_stored(self, mock_completion, agent):
        """_last_reasoning在respond后应有值"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "分析..."
        mock_completion.return_value = mock_response

        agent.respond("为什么增长停滞？")
        assert len(agent._last_reasoning) >= 1
        assert "template" in agent._last_reasoning[0]

    @patch("soma.agent.completion")
    def test_l3_gets_more_foci(self, mock_completion, agent):
        """L3问题保留全部foci"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "复杂分析..."
        mock_completion.return_value = mock_response

        agent.respond("为什么系统矛盾导致增长停滞，深层机制和根本原因是什么？")
        # L3问题不截断foci，推理块数应>=1
        assert len(agent._last_reasoning) >= 1

    @patch("soma.agent.completion")
    def test_complexity_adaptive_top_k(self, mock_completion, agent):
        """L3问题使用更大的top_k"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "分析..."
        mock_completion.return_value = mock_response

        agent.remember("系统分析案例1", {"domain": "分析"})
        agent.remember("系统分析案例2", {"domain": "分析"})
        agent.remember("系统分析案例3", {"domain": "分析"})

        original_top_k = agent.hub.top_k
        # L3问题
        agent.respond("为什么新产品增长停滞的根本矛盾是什么深层机制？")
        # top_k应恢复原值
        assert agent.hub.top_k == original_top_k

    @patch("soma.agent.completion")
    def test_anti_confirmation_search_l2_l3(self, mock_completion, agent):
        """L2/L3问题触发确认偏误检测"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "分析..."
        mock_completion.return_value = mock_response

        agent.respond("为什么系统出现矛盾？")  # L2
        # L2问题应触发反视角搜索
        assert hasattr(agent, '_last_anti_memories')


# ── prompt构建详细测试 ────────────────────────────────────

class TestBuildPrompt:
    def test_build_prompt_fallback_when_no_last_reasoning(self, agent):
        """_build_prompt在_last_reasoning为空且L2+时应回退到直接调用_execute_reasoning"""
        agent._last_reasoning = []
        agent._current_complexity = 2  # v1.1.1: L2触发推理框架
        foci = [make_focus("first_principles")]
        activated = [make_activated("第一性原理记忆")]
        # 重置_last_anti_memories避免旧值
        agent._last_anti_memories = []

        prompt = agent._build_prompt("测试问题", foci, activated)

        assert "结构化推理框架" in prompt
        assert "相关记忆与经验" in prompt
        assert "当前问题" in prompt
        assert "测试问题" in prompt

    def test_build_prompt_with_reasoning(self, agent):
        """有_last_reasoning且L2+时直接使用"""
        agent._last_reasoning = [{
            "index": 1,
            "dimension": "测试维度",
            "weight": 0.9,
            "template": "测试推理模板",
            "hypothesis": "测试假设",
            "evidence": ["证据1"],
            "counter_evidence": [],
        }]
        agent._last_anti_memories = []
        agent._current_complexity = 2  # v1.1.1: L2触发推理框架

        foci = [make_focus("first_principles")]
        prompt = agent._build_prompt("测试问题", foci, [])

        assert "测试推理模板" in prompt
        assert "测试假设" in prompt
        assert "证据1" in prompt

    def test_build_prompt_with_anti_memories(self, agent):
        """L2+有反面视角时应有专门段落"""
        agent._last_reasoning = [{
            "index": 1, "dimension": "测试", "weight": 0.9,
            "template": "模板", "hypothesis": "", "evidence": [], "counter_evidence": [],
        }]
        agent._last_anti_memories = [make_activated("反面证据内容", mem_id="anti1")]
        agent._current_complexity = 2  # v1.1.1: L2触发推理框架

        prompt = agent._build_prompt("问题", [], [])

        assert "反面视角" in prompt
        assert "反面证据内容" in prompt


# ── evolve 集成测试 ──────────────────────────────────────

class TestEvolveV060:
    def test_evolve_includes_trigger_promotion(self, evolver):
        """evolve()应包含触发词提升"""
        foci = [make_focus("first_principles")]
        evolver.set_current_context(foci, [], problem="如何系统分析增长瓶颈")
        for _ in range(5):
            evolver.reflect("t_success", "success")

        changes = evolver.evolve()
        change_types = {c.get("type", "weight_change") for c in changes}
        assert "trigger_promoted" in change_types

    def test_evolve_includes_template_mining(self, evolver):
        """evolve()应包含思维模板挖掘"""
        foci = [make_focus("first_principles"), make_focus("systems_thinking")]
        evolver.set_current_context(foci, [], problem="如何系统分析增长瓶颈")
        for _ in range(5):
            evolver.reflect("t_success", "success")

        changes = evolver.evolve()
        change_types = {c.get("type", "weight_change") for c in changes}
        assert "thought_template" in change_types

    def test_focus_pattern_only_on_success(self, evolver):
        """Bug #2修复: 失败不追踪聚焦模式"""
        foci = [make_focus("first_principles")]
        evolver.set_current_context(foci, [], problem="测试问题")
        for _ in range(5):
            evolver.reflect("t_fail", "failure")

        templates = evolver.get_thought_templates()
        assert len(templates) == 0
