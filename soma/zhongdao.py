"""v1.1.2 中道引擎 — 会话内实时规律使用偏差检测与自校正。

原理：
1. 追踪每次 respond() 调用中各规律(law_id)的使用次数
2. 当某规律在会话内占比超过阈值(默认40%)，自动临时降权
3. 同时从该规律的 relations 中找被忽略的关联规律，临时提权注入
4. 校正仅在当前 respond() 调用内生效，不持久化（与 MetaEvolver 互补）

设计约束：
- 零 LLM 依赖（纯规则匹配），满足 G3 降级
- 零外部依赖
- 不修改 law.weight 源值，只修改 Focus.weight（foci 中的副本）
"""
from __future__ import annotations

from typing import Dict, List, Tuple

from soma.base import Focus
from soma.config import SOMAConfig, WisdomLaw


class ZhongdaoEngine:
    """中道引擎 — 会话内实时规律使用偏差检测与自校正。

    与 MetaEvolver 互补：中道做会话内临时微调（不持久化），
    MetaEvolver 做跨会话趋势校正（持久化到 SQLite）。
    """

    def __init__(self, config: SOMAConfig):
        self.enabled = config.enable_zhongdao
        self.threshold_ratio = 0.40    # 单条规律使用率超过此值触发校正
        self.penalty_factor = 0.20     # 过度使用规律的临时降权比例
        self.boost_factor = 0.15       # 被忽略规律的临时提权比例
        self.min_samples = 5           # 最少采样数才触发
        self._session_usage: Dict[str, int] = {}
        self._corrections: List[dict] = []

    # ── 追踪 ──────────────────────────────────────────────

    def track(self, foci: List[Focus]) -> None:
        """记录本轮使用的规律（仅计数直接触发的焦点，排除链传播/探索/组合）。

        链传播和探索因子是系统自动添加的平衡视角，若一并计数会稀释
        直接触发规律的占比，导致偏差检测失效。
        """
        if not self.enabled:
            return
        for f in foci:
            lid = f.law_id
            if lid.startswith("combo_") or lid.endswith("_anti"):
                continue
            # 只计数直接触发的焦点（rationale 以 "问题中出现触发词" 开头）
            if "触发词" in f.rationale and "问题中出现" in f.rationale[:30]:
                self._session_usage[lid] = self._session_usage.get(lid, 0) + 1

    # ── 检测与校正 ────────────────────────────────────────

    def detect_and_correct(
        self, foci: List[Focus], laws: List[WisdomLaw],
    ) -> Tuple[List[Focus], List[dict]]:
        """检测偏差并返回校正后的 foci + 校正记录。

        Args:
            foci: 当前轮次拆解出的焦点列表
            laws: 所有思维规律列表（含 relations 字段）

        Returns:
            (corrected_foci, corrections_log)
            未触发校正时返回原 foci 和空列表。
        """
        if not self.enabled:
            return foci, []

        total = sum(self._session_usage.values())
        if total < self.min_samples:
            return foci, []

        # Step 1: 检测过度使用的规律
        overused: Dict[str, float] = {}
        for law_id, count in self._session_usage.items():
            ratio = count / total
            if ratio > self.threshold_ratio:
                overused[law_id] = ratio

        if not overused:
            return foci, []

        corrections: List[dict] = []
        law_map = {l.id: l for l in laws}

        # Step 2: 对当前 foci 中 overused 规律降权
        corrected: List[Focus] = []
        for f in foci:
            if f.law_id in overused:
                new_w = round(f.weight * (1 - self.penalty_factor), 4)
                law_name = law_map[f.law_id].name if f.law_id in law_map else f.law_id
                corrected.append(Focus(
                    law_id=f.law_id,
                    dimension=f.dimension,
                    keywords=list(f.keywords),
                    weight=new_w,
                    rationale=(
                        f"{f.rationale} "
                        f"[中道校正: 「{law_name}」会话内使用率 "
                        f"{overused[f.law_id]:.0%}，临时降权 {self.penalty_factor:.0%}]"
                    ),
                ))
                corrections.append({
                    "type": "overuse_penalty",
                    "law_id": f.law_id,
                    "law_name": law_name,
                    "usage_ratio": round(overused[f.law_id], 3),
                    "old_weight": round(f.weight, 4),
                    "new_weight": new_w,
                })
            else:
                corrected.append(f)

        # Step 3: 找被忽略但相关的规律，注入提权焦点
        used_ids = {f.law_id for f in foci}
        neglected: List[WisdomLaw] = []
        for ou_id in overused:
            ou_law = law_map.get(ou_id)
            if ou_law is None:
                continue
            for related_id in ou_law.relations:
                if related_id not in used_ids and related_id not in overused:
                    rlaw = law_map.get(related_id)
                    if rlaw is not None:
                        neglected.append(rlaw)

        # 去重（按 id 降权排序取前2条）
        seen = set()
        unique_neglected = []
        for law in neglected:
            if law.id not in seen:
                seen.add(law.id)
                unique_neglected.append(law)
        unique_neglected.sort(key=lambda l: l.weight, reverse=True)

        for law in unique_neglected[:2]:
            boost_w = round(law.weight * (1 + self.boost_factor), 4)
            corrected.append(Focus(
                law_id=law.id,
                dimension=(
                    f"从「{law.name}」出发（中道平衡视角）："
                    f"{law.description}"
                ),
                keywords=list(law.triggers),
                weight=boost_w,
                rationale=(
                    f"中道自校正：会话内「{law.name}」被抑制，"
                    f"临时提权 {self.boost_factor:.0%} 以平衡思维维度"
                ),
            ))
            corrections.append({
                "type": "neglect_boost",
                "law_id": law.id,
                "law_name": law.name,
                "weight": boost_w,
            })

        self._corrections = corrections
        return corrected, corrections

    # ── 生命周期 ──────────────────────────────────────────

    def reset(self) -> None:
        """重置会话统计（新会话开始时调用）。"""
        self._session_usage.clear()
        self._corrections.clear()

    @property
    def last_corrections(self) -> List[dict]:
        """最近一次校正记录。"""
        return list(self._corrections)
