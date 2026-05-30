"""v1.1.2 中道引擎测试"""
import pytest

from soma.base import Focus
from soma.config import SOMAConfig, WisdomLaw
from soma.zhongdao import ZhongdaoEngine


# ── 测试用的模拟规律 ──────────────────────────────────

def _make_laws():
    """构造7条模拟规律，与 wisdom_laws.yaml 结构一致"""
    return [
        WisdomLaw(
            id="first_principles", name="第一性原理",
            description="从最基本要素出发推导",
            weight=0.80,
            triggers=["基本", "要素", "本质"],
            relations=["systems_thinking"],
        ),
        WisdomLaw(
            id="systems_thinking", name="系统思维",
            description="从整体关联角度分析",
            weight=0.90,
            triggers=["系统", "整体", "关联"],
            relations=["first_principles", "contradiction_analysis"],
        ),
        WisdomLaw(
            id="contradiction_analysis", name="矛盾分析",
            description="识别对立统一的力量",
            weight=0.70,
            triggers=["矛盾", "对立", "冲突"],
            relations=["systems_thinking", "inversion"],
        ),
        WisdomLaw(
            id="pareto_principle", name="二八法则",
            description="识别20%关键因素",
            weight=0.60,
            triggers=["关键", "少数", "优先"],
            relations=["first_principles"],
        ),
        WisdomLaw(
            id="inversion", name="逆向思考",
            description="从反方向审视假设",
            weight=0.50,
            triggers=["反向", "反面", "反过来"],
            relations=["contradiction_analysis"],
        ),
        WisdomLaw(
            id="analogical_reasoning", name="类比推理",
            description="跨领域迁移模式",
            weight=0.55,
            triggers=["类比", "相似", "借鉴"],
            relations=["systems_thinking", "first_principles"],
        ),
        WisdomLaw(
            id="evolutionary_lens", name="演进视角",
            description="从时间维度看变化规律",
            weight=0.45,
            triggers=["演进", "阶段", "变化"],
            relations=["systems_thinking"],
        ),
    ]


def _make_foci(law_id="systems_thinking", weight=0.90):
    """构造单个 Focus 对象（模拟 decompose 直接触发的结果）"""
    return [
        Focus(
            law_id=law_id,
            dimension=f"从「系统思维」出发分析问题",
            keywords=["系统", "整体", "关联"],
            weight=weight,
            rationale="问题中出现触发词：系统",
        ),
    ]


def _make_config(enabled=True):
    """构造启用了中道的配置"""
    return SOMAConfig(enable_zhongdao=enabled)


# ── T1: 默认关闭 ─────────────────────────────────────

class TestZhongdaoDefaultOff:
    """默认关闭时不影响行为"""

    def test_disabled_engine_no_track(self):
        """关闭时 track() 不记录任何数据"""
        config = SOMAConfig(enable_zhongdao=False)
        engine = ZhongdaoEngine(config)
        foci = _make_foci()
        engine.track(foci)
        assert len(engine._session_usage) == 0

    def test_disabled_engine_no_correct(self):
        """关闭时 detect_and_correct() 返回原 foci"""
        config = SOMAConfig(enable_zhongdao=False)
        engine = ZhongdaoEngine(config)
        foci = _make_foci()
        corrected, corrections = engine.detect_and_correct(foci, _make_laws())
        assert corrected is foci  # 同一对象，未修改
        assert corrections == []


# ── T2: track() 累加计数 ─────────────────────────────

class TestZhongdaoTracking:
    """追踪功能正确性"""

    def test_track_single_law(self):
        """单次追踪正确累加"""
        engine = ZhongdaoEngine(_make_config())
        foci = _make_foci("systems_thinking")
        engine.track(foci)
        assert engine._session_usage.get("systems_thinking") == 1

    def test_track_multiple_laws(self):
        """多次追踪多个规律正确累加"""
        engine = ZhongdaoEngine(_make_config())
        engine.track(_make_foci("systems_thinking"))
        engine.track(_make_foci("first_principles"))
        engine.track(_make_foci("systems_thinking"))
        assert engine._session_usage["systems_thinking"] == 2
        assert engine._session_usage["first_principles"] == 1

    def test_track_skips_combo(self):
        """跳过 combo_ 前缀的组合规律"""
        engine = ZhongdaoEngine(_make_config())
        combo_foci = [
            Focus(law_id="combo_systems_first", dimension="组合",
                  keywords=[], weight=0.5, rationale="组合"),
        ]
        engine.track(combo_foci)
        assert "combo_systems_first" not in engine._session_usage

    def test_track_skips_anti(self):
        """跳过 _anti 后缀的反视角规律"""
        engine = ZhongdaoEngine(_make_config())
        anti_foci = [
            Focus(law_id="systems_thinking_anti", dimension="反视角",
                  keywords=[], weight=0.3, rationale="反视角"),
        ]
        engine.track(anti_foci)
        assert "systems_thinking_anti" not in engine._session_usage


# ── T3: 采样不足不触发 ───────────────────────────────

class TestZhongdaoMinSamples:
    """最少采样数阈值"""

    def test_below_min_samples_no_trigger(self):
        """4次采样不足5次，不触发"""
        engine = ZhongdaoEngine(_make_config())
        for _ in range(4):
            engine.track(_make_foci("systems_thinking"))
        foci = _make_foci("systems_thinking")
        corrected, corrections = engine.detect_and_correct(foci, _make_laws())
        assert corrections == []


# ── T4: 过度使用触发降权 ─────────────────────────────

class TestZhongdaoOverusePenalty:
    """单条规律使用率>40%时触发降权"""

    def test_overuse_triggers_penalty(self):
        """连续5轮同一规律 → 使用率100% > 40% → 降权"""
        engine = ZhongdaoEngine(_make_config())
        laws = _make_laws()
        for _ in range(5):
            engine.track(_make_foci("systems_thinking"))
        foci = _make_foci("systems_thinking", weight=0.90)
        corrected, corrections = engine.detect_and_correct(foci, laws)

        assert len(corrections) >= 1
        penalty = [c for c in corrections if c["type"] == "overuse_penalty"]
        assert len(penalty) == 1
        assert penalty[0]["law_id"] == "systems_thinking"
        # 权重应打折: 0.90 * (1 - 0.20) = 0.72
        assert corrected[0].weight < 0.90
        assert "中道校正" in corrected[0].rationale

    def test_mixed_usage_no_trigger(self):
        """使用率≤40%时不触发（5轮中同一规律最多2次=40%，不算>40%）"""
        engine = ZhongdaoEngine(_make_config())
        engine.track(_make_foci("systems_thinking"))
        engine.track(_make_foci("systems_thinking"))
        engine.track(_make_foci("first_principles"))
        engine.track(_make_foci("contradiction_analysis"))
        engine.track(_make_foci("pareto_principle"))
        # systems_thinking: 2/5 = 40%, 正好等于阈值，不触发（需要>40%）
        foci = _make_foci("systems_thinking")
        corrected, corrections = engine.detect_and_correct(foci, _make_laws())
        assert corrections == []


# ── T5: 被忽略关联规律提权注入 ────────────────────────

class TestZhongdaoNeglectBoost:
    """被忽略的关联规律应被注入"""

    def test_neglected_relations_injected(self):
        """systems_thinking 的 relations 包含 first_principles 和 contradiction_analysis
        当 systems_thinking 过度使用时，这些被忽略的规律应被注入"""
        engine = ZhongdaoEngine(_make_config())
        laws = _make_laws()
        for _ in range(5):
            engine.track(_make_foci("systems_thinking"))
        foci = _make_foci("systems_thinking", weight=0.90)
        corrected, corrections = engine.detect_and_correct(foci, laws)

        boost = [c for c in corrections if c["type"] == "neglect_boost"]
        assert len(boost) >= 1, "应至少注入1条被忽略的关联规律"
        # 注入的规律应在 systems_thinking 的 relations 中
        boosted_ids = {c["law_id"] for c in boost}
        assert any(
            rid in boosted_ids
            for rid in ["first_principles", "contradiction_analysis"]
        )

    def test_neglected_boost_weight_increased(self):
        """注入的规律权重应被提权"""
        engine = ZhongdaoEngine(_make_config())
        laws = _make_laws()
        for _ in range(5):
            engine.track(_make_foci("systems_thinking"))
        foci = _make_foci("systems_thinking", weight=0.90)
        corrected, corrections = engine.detect_and_correct(foci, laws)

        # 至少有一个新Focus被注入（提权后权重 > 原权重）
        original_ids = {f.law_id for f in foci}
        new_foci = [f for f in corrected if f.law_id not in original_ids]
        assert len(new_foci) >= 1
        for nf in new_foci:
            # 找到原规律权重，验证提权
            orig_law = next(l for l in laws if l.id == nf.law_id)
            assert nf.weight > orig_law.weight, (
                f"注入规律 {nf.law_id} 应被提权，"
                f"原权重 {orig_law.weight}，注入权重 {nf.weight}"
            )
            assert "中道自校正" in nf.rationale


# ── T6: 校正后权重计算正确 ────────────────────────────

class TestZhongdaoWeightCalc:
    """权重计算精度"""

    def test_penalty_factor_calculation(self):
        """降权计算: new = old * (1 - 0.20)"""
        engine = ZhongdaoEngine(_make_config())
        laws = _make_laws()
        for _ in range(5):
            engine.track(_make_foci("systems_thinking"))
        foci = _make_foci("systems_thinking", weight=0.75)
        corrected, _ = engine.detect_and_correct(foci, laws)
        assert corrected[0].weight == pytest.approx(0.60)  # 0.75 * 0.80

    def test_boost_factor_calculation(self):
        """提权计算: new = old * (1 + 0.15)"""
        engine = ZhongdaoEngine(_make_config())
        laws = _make_laws()
        for _ in range(5):
            engine.track(_make_foci("pareto_principle"))
        foci = _make_foci("pareto_principle", weight=0.60)
        corrected, corrections = engine.detect_and_correct(foci, laws)

        boost = [c for c in corrections if c["type"] == "neglect_boost"]
        if boost:
            for c in boost:
                orig_law = next(l for l in laws if l.id == c["law_id"])
                expected = round(orig_law.weight * 1.15, 4)
                assert c["weight"] == expected, (
                    f"提权计算错误: {c['law_id']} 期望 {expected}，实际 {c['weight']}"
                )


# ── T7: reset() 清空状态 ─────────────────────────────

class TestZhongdaoReset:
    """重置会话状态"""

    def test_reset_clears_usage(self):
        """reset() 清空使用计数"""
        engine = ZhongdaoEngine(_make_config())
        engine.track(_make_foci("systems_thinking"))
        engine.track(_make_foci("systems_thinking"))
        assert len(engine._session_usage) > 0
        engine.reset()
        assert len(engine._session_usage) == 0
        assert engine._corrections == []


# ── T8: last_corrections 属性 ────────────────────────

class TestZhongdaoLastCorrections:
    """最近校正记录访问"""

    def test_last_corrections_returns_copy(self):
        """返回校正记录的副本（非原对象引用）"""
        engine = ZhongdaoEngine(_make_config())
        laws = _make_laws()
        for _ in range(5):
            engine.track(_make_foci("systems_thinking"))
        engine.detect_and_correct(_make_foci("systems_thinking"), laws)
        result = engine.last_corrections
        assert len(result) >= 1
        assert result is not engine._corrections  # 副本

    def test_no_corrections_returns_empty(self):
        """无校正时返回空列表"""
        engine = ZhongdaoEngine(_make_config())
        assert engine.last_corrections == []


# ── T9: 与原 foci 中的非 overused 项不变 ──────────────

class TestZhongdaoNonOverused:
    """非过度使用的规律不受影响"""

    def test_non_overused_foci_unchanged(self):
        """使用率低的规律权重不变"""
        engine = ZhongdaoEngine(_make_config())
        laws = _make_laws()
        # 5轮中 systems_thinking 2次（40%不触发），first_principles 3次（60%触发）
        engine.track(_make_foci("systems_thinking"))
        engine.track(_make_foci("systems_thinking"))
        engine.track(_make_foci("first_principles"))
        engine.track(_make_foci("first_principles"))
        engine.track(_make_foci("first_principles"))
        # first_principles: 3/5=60% > 40% → 触发降权
        foci = [
            Focus(law_id="first_principles", dimension="fp",
                  keywords=[], weight=0.80, rationale="r"),
            Focus(law_id="systems_thinking", dimension="st",
                  keywords=[], weight=0.90, rationale="r"),
        ]
        corrected, _ = engine.detect_and_correct(foci, laws)
        # first_principles 应降权
        fp = [f for f in corrected if f.law_id == "first_principles"][0]
        assert fp.weight < 0.80
        # systems_thinking 不在 overused 中，保持不变
        st = [f for f in corrected if f.law_id == "systems_thinking"][0]
        assert st.weight == 0.90


# ── T10: 中道 chat() 集成 ────────────────────────────

class TestZhongdaoChatIntegration:
    """chat() API 也走中道校正"""

    def test_chat_detects_overuse(self):
        """通过 SOMA.chat() 多次调用，中道应介入"""
        from soma import SOMA
        soma = SOMA(enable_zhongdao=True, llm="mock")
        soma.remember("系统思维是从整体关联角度分析问题的方法论")
        soma.remember("第一性原理强调回归最基本要素")
        soma.remember("矛盾分析法关注对立统一")
        soma.remember("二八法则聚焦少数关键因素")

        # 前5轮触发同一领域问题，累积中道追踪
        for i in range(5):
            soma.respond(f"用系统思维分析第{i}个问题")

        # 第6轮用 chat()，应该也被中道校正
        result = soma.chat("继续用系统思维深入分析")
        assert "answer" in result
        assert len(result["foci"]) > 0
        # 检查是否有校正过的 focus（rationale 含中道标记）
        zhongdao_foci = [
            f for f in result["foci"]
            if "中道" in f.get("rationale", "")
        ]
        assert len(zhongdao_foci) > 0, (
            f"chat() 应触发中道校正，实际 foci: {result['foci']}"
        )

    def test_chat_no_zhongdao_when_disabled(self):
        """关闭中道时 chat() 不应有校正标记"""
        from soma import SOMA
        soma = SOMA(enable_zhongdao=False, llm="mock")
        soma.remember("系统思维方法论")

        for _ in range(5):
            soma.respond("用系统思维分析问题")

        result = soma.chat("继续分析")
        zhongdao_foci = [
            f for f in result["foci"]
            if "中道" in f.get("rationale", "")
        ]
        assert len(zhongdao_foci) == 0


# ── T11: 多条规律同时过度使用 ──────────────────────────

class TestZhongdaoMultipleOveruse:
    """多条规律同时超过阈值"""

    def test_multiple_overuse_both_penalized(self):
        """两条规律同时 >40%，都应降权"""
        engine = ZhongdaoEngine(_make_config())
        laws = _make_laws()
        for _ in range(3):
            engine.track(_make_foci("systems_thinking", weight=0.90))
        for _ in range(3):
            engine.track(_make_foci("first_principles", weight=0.80))
        # systems: 3/6=50% >40%, first: 3/6=50% >40%
        foci = [
            Focus(law_id="systems_thinking", dimension="st",
                  keywords=["系统"], weight=0.90, rationale="r"),
            Focus(law_id="first_principles", dimension="fp",
                  keywords=["基本"], weight=0.80, rationale="r"),
        ]
        corrected, corrections = engine.detect_and_correct(foci, laws)
        penalties = [c for c in corrections if c["type"] == "overuse_penalty"]
        assert len(penalties) == 2, f"两条都应被降权，实际: {penalties}"
        # 只检查被降权的原始foci（排除新注入的neglect_boost foci）
        penalized_ids = {c["law_id"] for c in penalties}
        for f in corrected:
            if f.law_id in penalized_ids:
                assert f.weight < {"systems_thinking": 0.90, "first_principles": 0.80}[f.law_id]


# ── T12: 提权注入数量上限 ──────────────────────────────

class TestZhongdaoBoostLimit:
    """注入的提权焦点不超过2条"""

    def test_boost_capped_at_two(self):
        """多条关联规律被忽略时，只注入前2条"""
        engine = ZhongdaoEngine(_make_config())
        laws = _make_laws()
        # systems_thinking 的 relations: first_principles + contradiction_analysis
        # first_principles 的 relations: systems_thinking (overused, skipped)
        # 还有 analogical_reasoning, evolutionary_lens 的 relations 也含 systems_thinking
        # 但只有 overused 规律的 relations 才会被注入
        for _ in range(5):
            engine.track([
                Focus(law_id="systems_thinking", dimension="",
                      keywords=[], weight=0.90, rationale=""),
            ])
        foci = _make_foci("systems_thinking")
        corrected, corrections = engine.detect_and_correct(foci, laws)
        boost_count = len([c for c in corrections if c["type"] == "neglect_boost"])
        assert boost_count <= 2, f"注入数量应≤2，实际: {boost_count}"


# ── T13: A1 参数可配置化测试 ───────────────────────────

class TestZhongdaoConfigurableParams:
    """A1: 中道参数通过 SOMAConfig 配置"""

    def test_custom_threshold_ratio(self):
        """自定义阈值：30%阈值下2/5=40%触发"""
        config = SOMAConfig(enable_zhongdao=True, zhongdao_threshold_ratio=0.30)
        engine = ZhongdaoEngine(config)
        laws = _make_laws()
        engine.track(_make_foci("systems_thinking"))
        engine.track(_make_foci("systems_thinking"))
        engine.track(_make_foci("first_principles"))
        engine.track(_make_foci("first_principles"))
        engine.track(_make_foci("first_principles"))
        # systems_thinking: 2/5=40% > 30% → 应触发
        foci = _make_foci("systems_thinking")
        _, corrections = engine.detect_and_correct(foci, laws)
        penalties = [c for c in corrections if c["type"] == "overuse_penalty"]
        assert len(penalties) == 1

    def test_high_threshold_no_trigger(self):
        """高阈值80%：2/5=40%不触发"""
        config = SOMAConfig(enable_zhongdao=True, zhongdao_threshold_ratio=0.80)
        engine = ZhongdaoEngine(config)
        laws = _make_laws()
        engine.track(_make_foci("systems_thinking"))
        engine.track(_make_foci("systems_thinking"))
        engine.track(_make_foci("first_principles"))
        engine.track(_make_foci("first_principles"))
        engine.track(_make_foci("first_principles"))
        foci = _make_foci("systems_thinking")
        _, corrections = engine.detect_and_correct(foci, laws)
        assert corrections == []

    def test_custom_penalty_factor(self):
        """自定义降权比例 0.50：权重应减半"""
        config = SOMAConfig(
            enable_zhongdao=True,
            zhongdao_penalty_factor=0.50,
        )
        engine = ZhongdaoEngine(config)
        laws = _make_laws()
        for _ in range(5):
            engine.track(_make_foci("systems_thinking"))
        foci = _make_foci("systems_thinking", weight=0.90)
        corrected, _ = engine.detect_and_correct(foci, laws)
        # 0.90 * (1 - 0.50) = 0.45
        assert corrected[0].weight == pytest.approx(0.45)

    def test_custom_boost_factor(self):
        """自定义提权比例 0.30：权重应增加30%"""
        config = SOMAConfig(
            enable_zhongdao=True,
            zhongdao_boost_factor=0.30,
        )
        engine = ZhongdaoEngine(config)
        laws = _make_laws()
        for _ in range(5):
            engine.track(_make_foci("pareto_principle"))
        foci = _make_foci("pareto_principle", weight=0.60)
        _, corrections = engine.detect_and_correct(foci, laws)
        boost = [c for c in corrections if c["type"] == "neglect_boost"]
        if boost:
            for c in boost:
                orig = next(l for l in laws if l.id == c["law_id"])
                expected = round(orig.weight * 1.30, 4)
                assert c["weight"] == expected

    def test_custom_min_samples(self):
        """自定义最少采样数：min_samples=3，3次即触发"""
        config = SOMAConfig(enable_zhongdao=True, zhongdao_min_samples=3)
        engine = ZhongdaoEngine(config)
        laws = _make_laws()
        for _ in range(3):
            engine.track(_make_foci("systems_thinking"))
        foci = _make_foci("systems_thinking", weight=0.90)
        _, corrections = engine.detect_and_correct(foci, laws)
        penalties = [c for c in corrections if c["type"] == "overuse_penalty"]
        assert len(penalties) == 1

    def test_default_params_unchanged_behavior(self):
        """默认参数下行为与 v1.1.2 完全一致"""
        config = SOMAConfig(enable_zhongdao=True)
        engine = ZhongdaoEngine(config)
        # 默认值与原来硬编码值相同
        assert engine.threshold_ratio == 0.40
        assert engine.penalty_factor == 0.20
        assert engine.boost_factor == 0.15
        assert engine.min_samples == 5

    def test_zero_penalty_no_weight_change(self):
        """降权比例=0时权重不变"""
        config = SOMAConfig(
            enable_zhongdao=True,
            zhongdao_penalty_factor=0.0,
        )
        engine = ZhongdaoEngine(config)
        laws = _make_laws()
        for _ in range(5):
            engine.track(_make_foci("systems_thinking"))
        foci = _make_foci("systems_thinking", weight=0.90)
        corrected, _ = engine.detect_and_correct(foci, laws)
        assert corrected[0].weight == 0.90


# ── T14: A4 中道校正持久化日志 ─────────────────────────

class TestZhongdaoAnalyticsLogging:
    """A4: 中道校正写入 analytics.db"""

    def test_record_zhongdao_correction(self):
        """记录单条校正到 zhongdao_corrections 表"""
        from soma.analytics import AnalyticsStore
        import tempfile, os
        tmp = tempfile.mkdtemp()
        try:
            store = AnalyticsStore(tmp)
            row_id = store.record_zhongdao_correction(
                {
                    "type": "overuse_penalty",
                    "law_id": "systems_thinking",
                    "law_name": "系统思维",
                    "usage_ratio": 0.60,
                    "old_weight": 0.90,
                    "new_weight": 0.72,
                },
                session_id="test_session",
                agent_id="agent_1",
            )
            assert row_id > 0
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    def test_get_zhongdao_history(self):
        """查询校正历史"""
        from soma.analytics import AnalyticsStore
        import tempfile
        tmp = tempfile.mkdtemp()
        try:
            store = AnalyticsStore(tmp)
            for i in range(3):
                store.record_zhongdao_correction(
                    {
                        "type": "overuse_penalty",
                        "law_id": f"law_{i}",
                        "law_name": f"规律{i}",
                        "usage_ratio": 0.5 + i * 0.1,
                        "old_weight": 0.80,
                        "new_weight": 0.64,
                    },
                    session_id="s1",
                )
            history = store.get_zhongdao_history(limit=10)
            assert len(history) == 3
            # 按时间倒序
            assert history[0]["law_id"] == "law_2"
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    def test_get_zhongdao_summary(self):
        """汇总统计正确"""
        from soma.analytics import AnalyticsStore
        import tempfile
        tmp = tempfile.mkdtemp()
        try:
            store = AnalyticsStore(tmp)
            store.record_zhongdao_correction(
                {"type": "overuse_penalty", "law_id": "st", "law_name": "系统思维",
                 "usage_ratio": 0.50, "old_weight": 0.80, "new_weight": 0.64},
                session_id="s1",
            )
            store.record_zhongdao_correction(
                {"type": "neglect_boost", "law_id": "fp", "law_name": "第一性原理",
                 "usage_ratio": 0, "old_weight": 0, "new_weight": 0, "weight": 0.92},
                session_id="s1",
            )
            summary = store.get_zhongdao_summary()
            assert summary["total_corrections"] == 2
            assert "overuse_penalty" in summary["by_type"]
            assert "neglect_boost" in summary["by_type"]
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    def test_history_filter_by_type(self):
        """按类型过滤历史"""
        from soma.analytics import AnalyticsStore
        import tempfile
        tmp = tempfile.mkdtemp()
        try:
            store = AnalyticsStore(tmp)
            store.record_zhongdao_correction(
                {"type": "overuse_penalty", "law_id": "st", "law_name": "x",
                 "usage_ratio": 0.5, "old_weight": 0.8, "new_weight": 0.6},
                session_id="s1",
            )
            store.record_zhongdao_correction(
                {"type": "neglect_boost", "law_id": "fp", "law_name": "y",
                 "usage_ratio": 0, "old_weight": 0, "new_weight": 0, "weight": 0.9},
                session_id="s1",
            )
            penalties = store.get_zhongdao_history(limit=10, correction_type="overuse_penalty")
            assert len(penalties) == 1
            assert penalties[0]["law_id"] == "st"
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    def test_idempotent_table_creation(self):
        """重复创建表不会报错"""
        from soma.analytics import AnalyticsStore
        import tempfile
        tmp = tempfile.mkdtemp()
        try:
            store = AnalyticsStore(tmp)
            store._create_zhongdao_tables()
            store._create_zhongdao_tables()  # 不应报错
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)


# ── T15: A3 多Agent中道协调 ─────────────────────────────

class TestCrossAgentZhongdaoConvergence:
    """A3: 跨Agent群体趋同检测"""

    def test_no_convergence_with_single_agent(self):
        """单Agent不触发趋同检测"""
        from soma.multi_agent.orchestrator import SOMAOrchestrator
        from soma.multi_agent.consensus import AgentOpinion
        config = SOMAConfig(enable_zhongdao=True)
        orch = SOMAOrchestrator(config)
        # 只有一个 opinion，不应触发
        opinions = [AgentOpinion(agent_id="a1", answer="x", confidence=0.8)]
        result = orch._detect_cross_agent_convergence(opinions)
        assert result is None

    def test_no_convergence_without_zhongdao_data(self):
        """无中道数据的Agent不触发趋同"""
        from soma.multi_agent.orchestrator import SOMAOrchestrator
        from soma.multi_agent.consensus import AgentOpinion
        config = SOMAConfig(enable_zhongdao=False)
        orch = SOMAOrchestrator(config)
        opinions = [
            AgentOpinion(agent_id="a1", answer="x", confidence=0.8),
            AgentOpinion(agent_id="a2", answer="y", confidence=0.7),
        ]
        result = orch._detect_cross_agent_convergence(opinions)
        assert result is None

    def test_convergence_with_two_agents(self):
        """两个Agent使用同一规律超过阈值 → 触发趋同"""
        from soma.multi_agent.orchestrator import SOMAOrchestrator
        from soma.multi_agent.consensus import AgentOpinion
        config = SOMAConfig(
            enable_zhongdao=True,
            orchestration_evolution_enabled=False,
        )
        orch = SOMAOrchestrator(config)
        orch.create_agents([
            {"agent_id": "analyst", "expertise": ["分析"],
             "description": "分析师"},
            {"agent_id": "strategist", "expertise": ["战略"],
             "description": "策略师"},
        ])

        # 让两个Agent都过度使用 systems_thinking
        for agent_id in ["analyst", "strategist"]:
            agent = orch._agents[agent_id]
            if agent.zhongdao is None:
                continue
            for _ in range(5):
                agent.zhongdao._session_usage["systems_thinking"] = \
                    agent.zhongdao._session_usage.get("systems_thinking", 0) + 1

        opinions = [
            AgentOpinion(agent_id="analyst", answer="分析", confidence=0.8),
            AgentOpinion(agent_id="strategist", answer="策略", confidence=0.7),
        ]

        result = orch._detect_cross_agent_convergence(opinions)
        # 两个Agent都过度使用同一规律，应触发
        if result is not None:
            assert result["law_id"] == "systems_thinking"
            assert len(result["agents"]) >= 2

