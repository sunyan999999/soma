"""v0.9.1 空性偏差检测 — 检测用户是否过度锁定在单一认知框架中。

原理：
1. 统计最近 N 轮对话中每个认知框架维度的关键词出现频率
2. 若同一框架占比超过阈值（≥60%），触发觉察提示
3. 同一框架冷却时间内不重复提示（去重）

设计约束：
- 零 LLM 依赖（纯规则匹配），满足 G3（非 LLM 降级）
- 零嵌入器依赖，满足 G2（无嵌入器降级）
"""
from __future__ import annotations

import time
from typing import Dict, List, Optional, Tuple


class FrameAnchoringDetector:
    """框架锚定检测器 — 检测是否过度锁定单一认知维度。

    检测结果用于生成温和的觉察提示，而非强制改变用户思维方式。
    """

    # 8 对认知框架维度：每个框架有关键词列表 + 对立框架的关键词列表
    FRAME_PAIRS: Dict[str, Tuple[List[str], List[str]]] = {
        "技术视角": (
            ["代码", "架构", "性能", "接口", "系统", "模块", "算法", "数据"],
            ["市场", "用户", "收入", "竞争", "增长", "商业", "运营", "品牌"],
        ),
        "商业视角": (
            ["市场", "用户", "收入", "竞争", "增长", "商业", "运营", "品牌"],
            ["代码", "架构", "性能", "接口", "系统", "模块", "算法", "数据"],
        ),
        "管理视角": (
            ["团队", "流程", "沟通", "激励", "组织", "管理", "协调", "领导"],
            ["代码", "架构", "性能", "数据", "算法", "系统"],
        ),
        "法律视角": (
            ["合规", "合同", "风险", "条款", "知识产权", "法规", "诉讼", "版权"],
            ["创新", "试验", "突破", "自由", "快速"],
        ),
        "短期导向": (
            ["快速", "立即", "本周", "紧急", "马上", "短期内", "眼下", "当前"],
            ["战略", "规划", "未来", "长期", "愿景", "长远", "持久", "根本"],
        ),
        "长期导向": (
            ["战略", "规划", "未来", "长期", "愿景", "长远", "持久", "根本"],
            ["快速", "立即", "本周", "紧急", "马上", "短期内", "眼下", "当前"],
        ),
        "内求视角": (
            ["反思", "自身", "成长", "觉察", "内在", "自省", "内观", "修行"],
            ["环境", "他人", "外部", "市场", "机会", "外部因素", "客观", "外在"],
        ),
        "外求视角": (
            ["环境", "他人", "外部", "市场", "机会", "外部因素", "客观", "外在"],
            ["反思", "自身", "成长", "觉察", "内在", "自省", "内观", "修行"],
        ),
    }

    def __init__(
        self,
        window: int = 5,
        threshold_ratio: float = 0.6,
        cooldown_seconds: int = 3600,
    ):
        self.window = window
        self.threshold_ratio = threshold_ratio
        self.cooldown_seconds = cooldown_seconds
        self._last_trigger: Dict[str, float] = {}

    def detect(self, recent_turns: List[str]) -> Optional[dict]:
        """分析最近 N 轮对话，检测框架锁定。

        Args:
            recent_turns: 最近 N 轮用户输入的文本列表（最新的在末尾）

        Returns:
            None 表示未检测到锁定，或 dict:
            {
                "dominant_frame": str,
                "ratio": float,
                "matched_turns": int,
                "neglected_frames": [str],
                "reflection": str,
            }
        """
        if len(recent_turns) < self.window:
            return None

        recent = recent_turns[-self.window:]
        frame_counts = self._count_frame_usage(recent)

        if not frame_counts:
            return None

        dominant = max(frame_counts, key=frame_counts.get)
        dominant_count = frame_counts[dominant]
        ratio = dominant_count / len(recent)

        if ratio < self.threshold_ratio:
            return None

        # 去重：同一框架在冷却时间内不重复提示
        now = time.time()
        last_time = self._last_trigger.get(dominant, 0.0)
        if now - last_time < self.cooldown_seconds:
            return None

        self._last_trigger[dominant] = now

        # 查找被忽略的对立框架
        _, opposite_kw = self.FRAME_PAIRS.get(dominant, ([], []))
        neglected = []
        for frame_name, (keywords, _) in self.FRAME_PAIRS.items():
            if frame_name == dominant:
                continue
            if any(kw in " ".join(recent).lower() for kw in opposite_kw):
                if frame_name not in neglected:
                    neglected.append(frame_name)

        neglected_suggestion = ""
        if neglected:
            neglected_suggestion = "「" + "」「".join(neglected[:2]) + "」"

        reflection = (
            f"觉察提示：您已连续 {dominant_count}/{len(recent)} 轮从「{dominant}」"
            f"角度分析问题。建议尝试从"
            f"{neglected_suggestion or '其他维度'}"
            f"视角重新审视，以获得更完整的认知图景。"
        )

        return {
            "dominant_frame": dominant,
            "ratio": round(ratio, 2),
            "matched_turns": dominant_count,
            "neglected_frames": neglected[:3],
            "reflection": reflection,
        }

    def _count_frame_usage(self, turns: List[str]) -> Dict[str, int]:
        """统计每轮对话使用的框架。

        每轮对话可能匹配多个框架（关键词重叠），每个命中框架独立计数。
        """
        counts: Dict[str, int] = {}
        for turn in turns:
            text_lower = turn.lower()
            for frame_name, (keywords, _) in self.FRAME_PAIRS.items():
                if any(kw.lower() in text_lower for kw in keywords):
                    counts[frame_name] = counts.get(frame_name, 0) + 1
        return counts
