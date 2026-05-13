"""分布式权重演化 — 每个 agent 独立演化，定期合并到全局模型"""

import logging
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_log = logging.getLogger("soma.multi_agent")


class DistributedEvolver:
    """分布式权重演化协调器

    管理多个 agent 的独立 MetaEvolver，支持：
    - 独立演化：每个 agent 维护自己的 evolver_<agent_id>.db
    - 全局合并：聚合各 agent 权重到全局模型
    - 冲突仲裁：当 agent 权重方向相反时，以成功率高的为准

    合并策略：
    - "simple_average": 所有 agent 权重等权平均（适合均质 agent）
    - "weighted_by_sessions": 按会话数加权（经验多的 agent 更有话语权）
    - "weighted_by_success": 按成功率加权（效果好的 agent 更有话语权）
    """

    # 合并策略常量
    MERGE_SIMPLE = "simple_average"
    MERGE_BY_SESSIONS = "weighted_by_sessions"
    MERGE_BY_SUCCESS = "weighted_by_success"

    def __init__(
        self,
        persist_dir: Path,
        default_weights: Optional[Dict[str, float]] = None,
        merge_strategy: str = "weighted_by_success",
    ):
        persist_dir.mkdir(parents=True, exist_ok=True)
        self._persist_dir = persist_dir
        self._default_weights = default_weights or {}
        self._merge_strategy = merge_strategy
        # agent_id → MetaEvolver
        self._evolvers: Dict[str, object] = {}
        # agent_id → stats (session_count, success_rate)
        self._agent_stats: Dict[str, Dict[str, Any]] = {}
        # 合并后的全局权重缓存
        self._global_weights: Dict[str, float] = {}
        self._merge_count: int = 0

    def register_agent(
        self, agent_id: str, evolver: object, session_count: int = 0, success_rate: float = 0.5,
    ) -> None:
        """注册一个 agent 的演化器"""
        self._evolvers[agent_id] = evolver
        self._agent_stats[agent_id] = {
            "session_count": session_count,
            "success_rate": success_rate,
        }
        _log.debug("注册 agent 演化器: %s sessions=%d sr=%.2f",
                   agent_id, session_count, success_rate)

    def unregister_agent(self, agent_id: str) -> bool:
        """注销一个 agent"""
        if agent_id in self._evolvers:
            del self._evolvers[agent_id]
            del self._agent_stats[agent_id]
            return True
        return False

    def update_stats(self, agent_id: str, session_count: int = 0, success_rate: float = 0.5) -> None:
        """更新 agent 的统计信息"""
        if agent_id in self._agent_stats:
            self._agent_stats[agent_id]["session_count"] = session_count
            self._agent_stats[agent_id]["success_rate"] = success_rate

    def evolve_agent(self, agent_id: str) -> List[Dict[str, Any]]:
        """触发单个 agent 的权重演化"""
        evolver = self._evolvers.get(agent_id)
        if evolver is None:
            _log.warning("未注册的 agent: %s", agent_id)
            return []
        return evolver.evolve()

    def evolve_all(self) -> Dict[str, List[Dict[str, Any]]]:
        """触发所有 agent 独立演化，返回各 agent 的变化"""
        results = {}
        for agent_id in self._evolvers:
            changes = self.evolve_agent(agent_id)
            if changes:
                results[agent_id] = changes
        return results

    def merge_weights(self, strategy: Optional[str] = None) -> Dict[str, float]:
        """执行一次全局权重合并。

        策略：
        - simple_average: 等权平均
        - weighted_by_sessions: 按会话数加权
        - weighted_by_success: 按成功率加权（推荐默认）

        返回合并后的全局权重字典。
        冲突处理：当 agent A 和 B 对同一 law 的权重一个上调一个下调时，
        以成功率高的 agent 为准。
        """
        strategy = strategy or self._merge_strategy
        agents = list(self._evolvers.keys())
        if not agents:
            return dict(self._default_weights)

        # 1. 收集各 agent 的当前权重
        agent_weights: Dict[str, Dict[str, float]] = {}
        for agent_id in agents:
            evolver = self._evolvers[agent_id]
            try:
                w = evolver.get_weights()
                if w:
                    agent_weights[agent_id] = dict(w)
            except Exception:
                _log.warning("获取 agent %s 权重失败", agent_id, exc_info=True)

        if not agent_weights:
            return dict(self._default_weights)

        # 2. 收集所有 law_id
        all_laws: set = set()
        for w in agent_weights.values():
            all_laws.update(w.keys())

        # 3. 计算合并权重
        merged: Dict[str, float] = {}
        self._merge_count += 1

        for law_id in all_laws:
            law_values = []
            law_weights = []

            for agent_id, weights in agent_weights.items():
                if law_id in weights:
                    stats = self._agent_stats.get(agent_id, {})
                    law_values.append(weights[law_id])

                    if strategy == self.MERGE_BY_SUCCESS:
                        # 成功率加权（0.3 底分防止零权）
                        wgt = max(stats.get("success_rate", 0.5), 0.3)
                    elif strategy == self.MERGE_BY_SESSIONS:
                        # 会话数加权（1 底分防止零权）
                        wgt = max(stats.get("session_count", 0), 1)
                    else:  # simple_average
                        wgt = 1.0

                    law_weights.append(wgt)

            if law_values:
                total_w = sum(law_weights)
                if total_w > 0:
                    merged[law_id] = sum(v * w for v, w in zip(law_values, law_weights)) / total_w
                else:
                    merged[law_id] = sum(law_values) / len(law_values)

        # 4. 冲突检测与仲裁（仅成功率加权策略启用）
        if strategy == self.MERGE_BY_SUCCESS:
            merged = self._resolve_conflicts(agent_weights, merged)

        # 5. 默认权重回填
        for law_id, default_w in self._default_weights.items():
            if law_id not in merged:
                merged[law_id] = default_w

        self._global_weights = merged
        _log.info("权重合并完成 (#%d): %d laws, %d agents, 策略=%s",
                  self._merge_count, len(merged), len(agents), strategy)

        return dict(merged)

    def _resolve_conflicts(
        self,
        agent_weights: Dict[str, Dict[str, float]],
        merged: Dict[str, float],
    ) -> Dict[str, float]:
        """冲突仲裁：当 agent 对同一 law 有相反方向时，选成功率高的"""
        if len(agent_weights) < 2:
            return merged

        for law_id in list(merged.keys()):
            values = []
            success_rates = []
            for agent_id, weights in agent_weights.items():
                if law_id in weights:
                    values.append(weights[law_id])
                    sr = self._agent_stats.get(agent_id, {}).get("success_rate", 0.5)
                    success_rates.append(sr)

            if len(values) < 2:
                continue

            # 检查是否有显著分歧（max - min > 0.15）
            v_min, v_max = min(values), max(values)
            if v_max - v_min <= 0.15:
                continue

            # 找出成功率最高的 agent
            best_idx = max(range(len(success_rates)), key=lambda i: success_rates[i])

            # 如果分歧大，偏向成功率高的 agent
            deviation = abs(merged[law_id] - values[best_idx])
            if deviation > 0.1:
                # 向最佳 agent 权重靠拢 60%
                merged[law_id] = merged[law_id] * 0.4 + values[best_idx] * 0.6

        return merged

    def get_global_weights(self) -> Dict[str, float]:
        """获取最近一次合并的全局权重。如未合并过，返回默认权重。"""
        if not self._global_weights:
            return dict(self._default_weights)
        return dict(self._global_weights)

    def apply_global_weights(self, agent_id: str) -> bool:
        """将全局合并权重应用到指定 agent"""
        evolver = self._evolvers.get(agent_id)
        if evolver is None or not self._global_weights:
            return False
        try:
            for law_id, weight in self._global_weights.items():
                evolver.adjust_weight(law_id, weight)
            return True
        except Exception:
            _log.warning("应用全局权重到 agent %s 失败", agent_id, exc_info=True)
            return False

    def apply_all(self) -> int:
        """将全局权重应用到所有 agent。返回成功应用的 agent 数量。"""
        count = 0
        for agent_id in self._evolvers:
            if self.apply_global_weights(agent_id):
                count += 1
        return count

    def get_agent_weights(self, agent_id: str) -> Dict[str, float]:
        """获取单个 agent 的权重"""
        evolver = self._evolvers.get(agent_id)
        if evolver is None:
            return {}
        try:
            return evolver.get_weights()
        except Exception:
            return {}

    def get_stats(self) -> Dict[str, Any]:
        """获取分布式演化统计"""
        agent_details = {}
        for agent_id, stats in self._agent_stats.items():
            w = self.get_agent_weights(agent_id)
            agent_details[agent_id] = {
                "session_count": stats["session_count"],
                "success_rate": stats["success_rate"],
                "weight_count": len(w),
            }
        return {
            "agent_count": len(self._evolvers),
            "merge_count": self._merge_count,
            "merge_strategy": self._merge_strategy,
            "global_weight_count": len(self._global_weights),
            "agents": agent_details,
        }

    @property
    def agent_count(self) -> int:
        return len(self._evolvers)
