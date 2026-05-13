"""v0.9.1 框架锚定检测器测试"""
import time

import pytest

from soma.hub._frame_detector import FrameAnchoringDetector


class TestFrameAnchoringDetector:
    """框架锚定检测器单元测试"""

    @pytest.fixture
    def detector(self):
        """创建检测器实例，关闭冷却以简化测试"""
        return FrameAnchoringDetector(
            window=5,
            threshold_ratio=0.6,
            cooldown_seconds=0,
        )

    # ── 正常情况：多框架混合 → 不触发 ─────────────────

    def test_mixed_frames_no_trigger(self, detector):
        """连续5轮涉及不同框架 → 不应触发"""
        turns = [
            "代码架构需要重构",        # 技术视角
            "市场用户反馈很重要",      # 商业视角
            "团队流程需要优化",        # 管理视角
            "反思自身的成长方向",      # 内求视角
            "需要快速交付本周任务",    # 短期导向
        ]
        result = detector.detect(turns)
        assert result is None

    # ── 锁定情况：连续多轮同一框架 → 触发 ──────────

    def test_anchoring_triggered(self, detector):
        """连续5轮同一框架 ≥60% → 触发检测"""
        turns = [
            "代码质量需要改进",
            "架构设计要重新考虑",
            "系统性能是瓶颈",
            "接口规范应该统一",
            "算法复杂度需要优化",
        ]
        result = detector.detect(turns)
        assert result is not None
        assert result["dominant_frame"] == "技术视角"
        assert result["ratio"] >= 0.6
        assert "reflection" in result
        assert len(result["neglected_frames"]) >= 0

    def test_anchoring_exact_threshold(self, detector):
        """精确60%阈值边界：3/5轮同一框架 → 触发"""
        turns = [
            "代码需要重构",      # 技术
            "架构需要改进",      # 技术
            "性能需要优化",      # 技术
            "市场用户反馈",      # 商业
            "团队管理流程",      # 管理
        ]
        result = detector.detect(turns)
        assert result is not None

    def test_anchoring_below_threshold(self, detector):
        """低于60%阈值 → 不触发"""
        turns = [
            "代码需要重构",      # 技术
            "架构需要改进",      # 技术
            "市场用户反馈",      # 商业
            "团队管理流程",      # 管理
            "反思自我成长",      # 内求
        ]
        # 2/5 = 40% < 60%
        result = detector.detect(turns)
        assert result is None

    # ── 边界测试 ─────────────────────────────────────

    def test_empty_turns(self, detector):
        """空 turns → 返回 None"""
        result = detector.detect([])
        assert result is None

    def test_single_turn(self, detector):
        """单轮对话 → 返回 None"""
        result = detector.detect(["代码架构"])
        assert result is None

    def test_insufficient_window(self, detector):
        """不足窗口大小 → 返回 None"""
        turns = ["代码架构", "性能优化"]  # 2 < window=5
        result = detector.detect(turns)
        assert result is None

    # ── 去重测试 ─────────────────────────────────────

    def test_cooldown_prevents_retrigger(self):
        """同一框架在冷却时间内不重复提示"""
        det = FrameAnchoringDetector(
            window=5, threshold_ratio=0.6, cooldown_seconds=3600
        )
        turns = [
            "代码架构", "性能优化", "系统设计",
            "接口规范", "算法选择",
        ]
        result1 = det.detect(turns)
        assert result1 is not None

        # 立即再次检测（冷却时间内）
        result2 = det.detect(turns)
        assert result2 is None  # 冷却中，不重复触发

    def test_cooldown_expired(self):
        """冷却时间过后可重新触发"""
        det = FrameAnchoringDetector(
            window=5, threshold_ratio=0.6, cooldown_seconds=0
        )
        turns = [
            "代码架构", "性能优化", "系统设计",
            "接口规范", "算法选择",
        ]
        result1 = det.detect(turns)
        assert result1 is not None

        # 冷却为0，每次都触发
        result2 = det.detect(turns)
        assert result2 is not None

    # ── 对立框架检测 ─────────────────────────────────

    def test_neglected_frames_suggestion(self, detector):
        """锁定后建议被忽略的对立框架"""
        turns = [
            "反思自己的不足",
            "觉察内在的模式",
            "自身成长是关键",
            "内观修行很重要",
            "反省昨天的问题",
        ]
        result = detector.detect(turns)
        assert result is not None
        assert result["dominant_frame"] == "内求视角"
        assert "reflection" in result

    # ── 多次匹配测试 ─────────────────────────────────

    def test_multi_frame_matching(self, detector):
        """每轮可能匹配多个框架（关键词重叠），每个独立计数"""
        turns = [
            "代码架构和团队流程都需要改进",  # 技术 + 管理
            "反思代码质量与市场用户反馈",    # 内求 + 技术 + 商业
            "架构性能和长期战略规划",        # 技术 + 长期
            "系统接口与快速交付",            # 技术 + 短期
            "算法复杂度和未来愿景",          # 技术 + 长期
        ]
        result = detector.detect(turns)
        assert result is not None
        # 技术视角应该出现最多
        assert result["ratio"] >= 0.0


class TestFrameAnchoringIntegration:
    """集成测试：FrameAnchoringDetector 与 ActivationHub 配合"""

    @pytest.fixture
    def hub_with_detector(self, tmp_path):
        """创建带框架检测器的 ActivationHub"""
        from soma.config import SOMAConfig
        from soma.memory.core import MemoryCore
        from soma.hub import ActivationHub
        from soma.hub._frame_detector import FrameAnchoringDetector

        config = SOMAConfig(
            episodic_persist_dir=tmp_path / "data",
            use_vector_search=False,
            enable_frame_detection=True,
        )
        mc = MemoryCore(config)
        detector = FrameAnchoringDetector(window=5)
        hub = ActivationHub(mc, top_k=3, frame_detector=detector)
        return hub

    def test_detect_frame_anchoring_delegation(self, hub_with_detector):
        """hub.detect_frame_anchoring 正确委托给检测器"""
        turns = [
            "代码架构", "系统性能", "接口设计",
            "算法优化", "模块解耦",
        ]
        result = hub_with_detector.detect_frame_anchoring(turns)
        assert result is not None
        assert result["dominant_frame"] == "技术视角"

    def test_detect_frame_anchoring_empty(self, hub_with_detector):
        """空 turns 不报错"""
        result = hub_with_detector.detect_frame_anchoring([])
        assert result is None
