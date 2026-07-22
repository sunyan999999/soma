"""主动记忆管理 — 让记忆库从"只增不减"升级为"有生命"

三大机制:
1. 艾宾浩斯遗忘曲线 — 不同记忆类型有不同半衰期，访问频次减缓衰减
2. 情节→语义巩固 — 同主题多条情节记忆自动合并为语义摘要
3. 语义冲突检测 — 发现矛盾三元组（同主语+谓语，不同宾语）

用法::

    from soma.memory_manager import MemoryManager

    mgr = MemoryManager(episodic_store, semantic_store, skill_store)
    report = mgr.run_maintenance()  # 触发一轮完整维护
    mgr.prune_stale()               # 仅清理过期记忆
"""

import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


# ═══════════════════════════════════════════════════════════════
# 遗忘曲线参数
# ═══════════════════════════════════════════════════════════════

# 不同记忆类型的半衰期（天）
FORGETTING_HALF_LIFE = {
    "episodic": 7.0,     # 情节记忆: 7天半衰
    "semantic": 30.0,    # 语义知识: 30天半衰
    "skill": 90.0,       # 固化技能: 90天半衰
}

# 访问频次减缓因子 — 每访问一次，等效"时间流逝"减缓比例
ACCESS_DECAY_FACTOR = 0.12  # 每次访问延迟 12% 的衰减

# 记忆修剪阈值：relevance 低于此值的记忆可被清理
PRUNE_THRESHOLD = 0.01

# 巩固阈值：同一主题下情节记忆超过此数量触发摘要合并
CONSOLIDATION_THRESHOLD = 5

# 冲突检测：语义三元组置信度差异超过此值视为冲突
CONFLICT_CONFIDENCE_DELTA = 0.3


@dataclass
class ConflictReport:
    """语义冲突报告"""
    subject: str
    predicate: str
    object_a: str
    object_b: str
    confidence_a: float
    confidence_b: float
    detected_at: float = field(default_factory=time.time)

    @property
    def severity(self) -> str:
        delta = abs(self.confidence_a - self.confidence_b)
        if delta > 0.6:
            return "high"
        elif delta > 0.3:
            return "medium"
        return "low"

    @property
    def description(self) -> str:
        return (
            f"矛盾: [{self.subject}] {self.predicate} "
            f"→ {self.object_a}(置信度{self.confidence_a}) vs "
            f"→ {self.object_b}(置信度{self.confidence_b})"
        )


@dataclass
class MaintenanceReport:
    """一轮记忆维护的报告"""
    pruned_count: int = 0
    consolidated_groups: int = 0
    conflicts_detected: int = 0
    conflicts: List[ConflictReport] = field(default_factory=list)
    memory_stats: Dict[str, int] = field(default_factory=dict)
    duration_ms: float = 0.0


class MemoryManager:
    """主动记忆生命周期管理器

    提供与现有 MemoryStore 接口兼容的记忆健康维护：
    - ebbinghaus_decay(): 计算当前剩余记忆强度
    - consolidate(): 情节记忆合并为语义摘要
    - detect_conflicts(): 语义三元组矛盾检测
    - prune_stale(): 清理低于阈值的记忆
    - run_maintenance(): 一键运行全部维护
    """

    def __init__(self, episodic_store=None, semantic_store=None, skill_store=None):
        self.episodic = episodic_store
        self.semantic = semantic_store
        self.skill = skill_store
        self._last_maintenance: float = 0.0
        self._maintenance_count: int = 0

    # ── 遗忘曲线 ────────────────────────────────────────────────

    def ebbinghaus_strength(
        self,
        memory_timestamp: float,
        memory_type: str = "episodic",
        access_count: int = 0,
        current_time: Optional[float] = None,
    ) -> float:
        """艾宾浩斯遗忘曲线：计算一条记忆的当前保留强度。

        R = e^(-t / S * decay_factor)
        - t: 距创建时间的天数
        - S: 记忆类型对应的半衰期（天）
        - decay_factor: 1 / (1 + access_count * ACCESS_DECAY_FACTOR)

        返回值: 0.0（完全遗忘）~ 1.0（完全保留）
        """
        if current_time is None:
            current_time = datetime.now(timezone.utc).timestamp()
        days = max(current_time - memory_timestamp, 0) / 86400.0
        half_life = FORGETTING_HALF_LIFE.get(memory_type, 7.0)

        # 访问频次减缓衰减
        decay_factor = 1.0 / (1.0 + access_count * ACCESS_DECAY_FACTOR)

        return math.exp(-days / half_life * decay_factor)

    def batch_strength(
        self,
        memories: List[Any],
        current_time: Optional[float] = None,
    ) -> List[float]:
        """批量计算记忆强度"""
        if current_time is None:
            current_time = datetime.now(timezone.utc).timestamp()
        return [
            self.ebbinghaus_strength(
                memory_timestamp=getattr(m, "timestamp", 0),
                memory_type=getattr(m, "memory_type", "episodic"),
                access_count=getattr(m, "access_count", 0),
                current_time=current_time,
            )
            for m in memories
        ]

    def decay_report(self, memories: List[Any]) -> dict:
        """返回记忆衰减统计报告"""
        strengths = self.batch_strength(memories)
        if not strengths:
            return {"count": 0, "avg_strength": 1.0, "weak_count": 0}
        weak = sum(1 for s in strengths if s < 0.1)
        return {
            "count": len(strengths),
            "avg_strength": round(sum(strengths) / len(strengths), 3),
            "min_strength": round(min(strengths), 4),
            "weak_count": weak,  # R < 0.1
            "weak_ratio": round(weak / len(strengths), 3),
        }

    # ── 记忆巩固 ────────────────────────────────────────────────

    def find_consolidation_candidates(
        self,
        min_group_size: int = CONSOLIDATION_THRESHOLD,
    ) -> List[Tuple[str, List[Any]]]:
        """找出可合并的情节记忆组。

        按 context 中的 domain/topic 字段聚类，
        返回超过阈值的记忆组列表。
        """
        if self.episodic is None:
            return []

        all_memories = self._get_all_episodic()
        groups: Dict[str, List[Any]] = defaultdict(list)

        for mem in all_memories:
            ctx = getattr(mem, "context", {}) or {}
            domain = ctx.get("domain", ctx.get("topic", ctx.get("source", "__other__")))
            groups[domain].append(mem)

        # 返回超过阈值的组
        candidates = [
            (domain, mems)
            for domain, mems in groups.items()
            if len(mems) >= min_group_size and domain != "__other__"
        ]
        candidates.sort(key=lambda x: -len(x[1]))
        return candidates

    def consolidate_group(
        self,
        domain: str,
        memories: List[Any],
    ) -> Optional[str]:
        """将一组同主题情节记忆合并为一条语义记忆。

        如果 LLM 可用，生成高质量摘要；否则用模板拼接。
        返回 semantic memory ID 或 None。
        """
        if self.semantic is None or len(memories) < 2:
            return None

        # 提取内容摘要（取每条记忆前150字符 + 去重）
        previews = []
        seen = set()
        for mem in memories:
            content = getattr(mem, "content", str(mem))
            key = content[:60]
            if key not in seen:
                seen.add(key)
                previews.append(content[:200])

        # 生成合并摘要
        summary = self._build_summary(domain, previews, len(memories))

        # 存入语义库
        try:
            sid = self.semantic.add(
                subject=domain,
                predicate="CONSOLIDATED_FROM",
                obj=summary,
                confidence=min(0.8, 0.3 + 0.1 * len(memories)),
                source=f"consolidation:{domain}",
            )
            return sid
        except Exception:
            # 如果语义库不支持 add()，尝试 remember()
            try:
                return self.semantic.remember(
                    f"[记忆巩固] {domain}: {summary}",
                    {"source": "consolidation", "original_count": len(memories)},
                    importance=0.7,
                )
            except Exception:
                return None

    def _build_summary(self, domain: str, previews: List[str], count: int) -> str:
        """构建记忆合并摘要（纯本地，不依赖 LLM）"""
        joined = "；".join(previews[:5])
        if len(joined) > 500:
            joined = joined[:497] + "..."
        return f"主题 [{domain}] 下 {count} 条经历合并: {joined}"

    def _get_all_episodic(self) -> List[Any]:
        """获取所有情节记忆"""
        try:
            # 如果 episodic store 支持 list_all
            return self.episodic.list_all()
        except Exception:
            try:
                # 尝试 stats + search fallback
                stats = self.episodic.stats()
                total = stats.get("episodic", 0) if isinstance(stats, dict) else 0
                if total > 0:
                    return self.episodic.search("", top_k=min(total, 1000))
            except Exception:
                pass
        return []

    # ── 冲突检测 ────────────────────────────────────────────────

    def detect_conflicts(self) -> List[ConflictReport]:
        """检测语义三元组中的矛盾。

        逻辑: 找到相同 (subject, predicate) 但不同 object 的三元组对。
        """
        if self.semantic is None:
            return []

        triples = self._get_all_semantic_triples()
        if len(triples) < 2:
            return []

        # 按 (subject, predicate) 分组
        grouped: Dict[Tuple[str, str], List[dict]] = defaultdict(list)
        for t in triples:
            key = (t.get("subject", ""), t.get("predicate", ""))
            if key[0] and key[1]:
                grouped[key].append(t)

        conflicts = []
        for (subj, pred), entries in grouped.items():
            if len(entries) < 2:
                continue
            # 比较每对不同 object
            objects = {}
            for e in entries:
                obj = e.get("object", e.get("obj", ""))
                if obj and obj not in objects:
                    objects[obj] = e.get("confidence", 0.5)

            obj_list = list(objects.items())
            for i in range(len(obj_list)):
                for j in range(i + 1, len(obj_list)):
                    obj_a, conf_a = obj_list[i]
                    obj_b, conf_b = obj_list[j]
                    if abs(conf_a - conf_b) >= CONFLICT_CONFIDENCE_DELTA:
                        conflicts.append(ConflictReport(
                            subject=subj,
                            predicate=pred,
                            object_a=obj_a,
                            object_b=obj_b,
                            confidence_a=conf_a,
                            confidence_b=conf_b,
                        ))

        conflicts.sort(key=lambda c: -abs(c.confidence_a - c.confidence_b))
        return conflicts

    def _get_all_semantic_triples(self) -> List[dict]:
        """获取所有语义三元组"""
        try:
            return self.semantic.get_all_triples()
        except Exception:
            try:
                stats = self.semantic.stats()
                total = stats.get("semantic", 0) if isinstance(stats, dict) else 0
                if total > 0:
                    return self.semantic.search("", top_k=min(total, 500))
            except Exception:
                pass
        return []

    # ── 记忆修剪 ────────────────────────────────────────────────

    def prune_stale(self, threshold: float = PRUNE_THRESHOLD) -> int:
        """清理 relevance_potential 低于阈值的记忆。返回清理数量。"""
        if self.episodic is None:
            return 0

        all_memories = self._get_all_episodic()
        pruned = 0

        for mem in all_memories:
            try:
                rp = mem.relevance_potential()
            except Exception:
                rp = self.ebbinghaus_strength(
                    memory_timestamp=getattr(mem, "timestamp", 0),
                    memory_type=getattr(mem, "memory_type", "episodic"),
                    access_count=getattr(mem, "access_count", 0),
                )
            if rp < threshold:
                try:
                    mem_id = getattr(mem, "id", None) or getattr(mem, "memory_id", None)
                    if mem_id:
                        self.episodic.delete(mem_id)
                        pruned += 1
                except Exception:
                    pass

        return pruned

    # ── 全量维护 ────────────────────────────────────────────────

    def run_maintenance(
        self,
        prune: bool = True,
        consolidate: bool = True,
        detect: bool = True,
    ) -> MaintenanceReport:
        """运行一轮完整的记忆健康维护。

        顺序：修剪 → 巩固 → 冲突检测
        """
        t0 = time.perf_counter()
        report = MaintenanceReport()

        # 1. 修剪过期记忆
        if prune:
            report.pruned_count = self.prune_stale()

        # 2. 情节→语义巩固
        if consolidate:
            candidates = self.find_consolidation_candidates()
            for domain, memories in candidates:
                sid = self.consolidate_group(domain, memories)
                if sid:
                    report.consolidated_groups += 1

        # 3. 冲突检测
        if detect:
            report.conflicts = self.detect_conflicts()
            report.conflicts_detected = len(report.conflicts)

        # 4. 记忆统计
        report.memory_stats = self._gather_stats()

        report.duration_ms = round((time.perf_counter() - t0) * 1000, 1)
        self._last_maintenance = time.time()
        self._maintenance_count += 1

        return report

    def _gather_stats(self) -> Dict[str, int]:
        """收集记忆统计"""
        stats = {}
        for name, store in [
            ("episodic", self.episodic),
            ("semantic", self.semantic),
            ("skill", self.skill),
        ]:
            if store is None:
                continue
            try:
                s = store.stats()
                if isinstance(s, dict):
                    for k, v in s.items():
                        if isinstance(v, int):
                            stats[f"{name}_{k}"] = v
                    if "total" not in s and name not in str(s):
                        stats[name] = sum(v for v in s.values() if isinstance(v, int))
                elif isinstance(s, int):
                    stats[name] = s
            except Exception:
                pass
        return stats

    # ── 健康报告 ────────────────────────────────────────────────

    def health_report(self) -> dict:
        """返回记忆系统健康摘要"""
        report = {
            "maintenance_count": self._maintenance_count,
            "last_maintenance_ts": self._last_maintenance,
            "memory_counts": self._gather_stats(),
        }

        # 添加衰减统计
        episodic_mems = self._get_all_episodic()
        if episodic_mems:
            report["decay"] = self.decay_report(episodic_mems)

        # 添加冲突统计
        conflicts = self.detect_conflicts()
        report["conflict_count"] = len(conflicts)
        report["high_severity_conflicts"] = sum(
            1 for c in conflicts if c.severity == "high"
        )

        return report
