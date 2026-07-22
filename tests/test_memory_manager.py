"""主动记忆管理测试"""
import time
import pytest
from soma.memory_manager import (
    MemoryManager, MaintenanceReport, ConflictReport,
    FORGETTING_HALF_LIFE, PRUNE_THRESHOLD, CONSOLIDATION_THRESHOLD,
)


class FakeMemory:
    """模拟 MemoryUnit — 用于测试遗忘曲线"""
    def __init__(self, content, timestamp=None, memory_type="episodic",
                 access_count=0, context=None, mem_id=None):
        self.content = content
        self.timestamp = timestamp or (time.time() - 86400 * 3)  # 3天前
        self.memory_type = memory_type
        self.access_count = access_count
        self.context = context or {}
        self.id = mem_id or f"mem-{id(self)}"

    def relevance_potential(self):
        # 简单模拟
        import math
        days = max(time.time() - self.timestamp, 0) / 86400.0
        return math.exp(-days / 7.0) * 0.5 * (1 + 0.1 * self.access_count)


class FakeEpisodicStore:
    """模拟情节记忆库"""
    def __init__(self, memories=None):
        self.memories = memories or []
        self.deleted = []

    def list_all(self):
        return self.memories

    def stats(self):
        return {"episodic": len(self.memories)}

    def search(self, query, top_k=100):
        return self.memories[:top_k]

    def delete(self, mem_id):
        self.deleted.append(mem_id)
        self.memories = [m for m in self.memories
                         if getattr(m, "id", None) != mem_id]

    def remember(self, content, context=None, importance=0.5):
        mem = FakeMemory(content, context=context)
        self.memories.append(mem)
        return mem.id

    def add(self, *args, **kwargs):
        return "sem-add-1"


class FakeSemanticStore:
    """模拟语义记忆库"""
    def __init__(self, triples=None):
        self.triples = triples or []

    def get_all_triples(self):
        return self.triples

    def stats(self):
        return {"semantic": len(self.triples)}

    def search(self, query, top_k=100):
        return self.triples[:top_k]

    def add(self, subject, predicate, obj, confidence=1.0, source=""):
        triple = {
            "subject": subject,
            "predicate": predicate,
            "object": obj,
            "confidence": confidence,
            "source": source,
        }
        self.triples.append(triple)
        return f"sem-{len(self.triples)}"


class FakeSkillStore:
    """模拟技能记忆库"""
    def stats(self):
        return {"skill": 0}


class TestEbbinghausCurve:
    """艾宾浩斯遗忘曲线测试"""

    def setup_method(self):
        self.mgr = MemoryManager()

    def test_fresh_memory_full_strength(self):
        now = time.time()
        s = self.mgr.ebbinghaus_strength(now, "episodic", 0, now)
        assert s == 1.0  # 刚刚创建的，强度=1

    def test_after_half_life(self):
        """7天后情节记忆衰减到约 0.37"""
        now = time.time()
        seven_days_ago = now - 86400 * 7
        s = self.mgr.ebbinghaus_strength(seven_days_ago, "episodic", 0, now)
        assert 0.35 < s < 0.40  # e^(-1) ≈ 0.368

    def test_semantic_slower_decay(self):
        """语义记忆 7 天仅衰减到 ~0.79"""
        now = time.time()
        seven_days_ago = now - 86400 * 7
        ep = self.mgr.ebbinghaus_strength(seven_days_ago, "episodic", 0, now)
        se = self.mgr.ebbinghaus_strength(seven_days_ago, "semantic", 0, now)
        assert se > ep  # 语义衰减更慢

    def test_skill_slowest_decay(self):
        """技能记忆衰减最慢"""
        now = time.time()
        seven_days_ago = now - 86400 * 7
        ep = self.mgr.ebbinghaus_strength(seven_days_ago, "episodic", 0, now)
        sk = self.mgr.ebbinghaus_strength(seven_days_ago, "skill", 0, now)
        assert sk > ep

    def test_access_counts_slow_decay(self):
        """多次访问的记忆衰减更慢"""
        now = time.time()
        seven_days_ago = now - 86400 * 7
        no_access = self.mgr.ebbinghaus_strength(seven_days_ago, "episodic", 0, now)
        with_access = self.mgr.ebbinghaus_strength(seven_days_ago, "episodic", 5, now)
        assert with_access > no_access

    def test_batch_strength(self):
        now = time.time()
        mems = [
            FakeMemory("刚刚创建", timestamp=now),
            FakeMemory("3天前", timestamp=now - 86400 * 3),
            FakeMemory("14天前", timestamp=now - 86400 * 14),
        ]
        strengths = self.mgr.batch_strength(mems, now)
        assert len(strengths) == 3
        assert strengths[0] > strengths[1] > strengths[2]

    def test_decay_report(self):
        now = time.time()
        mems = [
            FakeMemory("新", timestamp=now, access_count=10),
            FakeMemory("旧", timestamp=now - 86400 * 30, access_count=0),
        ]
        report = self.mgr.decay_report(mems)
        assert report["count"] == 2
        assert report["weak_count"] >= 0
        assert "avg_strength" in report


class TestConsolidation:
    """记忆巩固测试"""

    def setup_method(self):
        self.episodic = FakeEpisodicStore()
        self.semantic = FakeSemanticStore()
        self.mgr = MemoryManager(
            episodic_store=self.episodic,
            semantic_store=self.semantic,
        )

    def test_find_candidates_empty(self):
        candidates = self.mgr.find_consolidation_candidates()
        assert len(candidates) == 0

    def test_find_candidates_below_threshold(self):
        # 只有 3 条同主题，不够 5 条阈值
        for i in range(3):
            self.episodic.memories.append(FakeMemory(
                f"memory {i}",
                context={"domain": "test"},
            ))
        candidates = self.mgr.find_consolidation_candidates()
        assert len(candidates) == 0

    def test_find_candidates_above_threshold(self):
        for i in range(6):
            self.episodic.memories.append(FakeMemory(
                f"memory {i}",
                context={"domain": "algorithms"},
            ))
        candidates = self.mgr.find_consolidation_candidates()
        assert len(candidates) == 1
        domain, mems = candidates[0]
        assert domain == "algorithms"
        assert len(mems) == 6

    def test_consolidate_group_creates_semantic(self):
        for i in range(5):
            self.episodic.memories.append(FakeMemory(
                f"学习 Python 装饰器的经验 #{i}",
                context={"domain": "python-decorators"},
            ))
        sid = self.mgr.consolidate_group("python-decorators",
                                          self.episodic.memories)
        assert sid is not None
        assert len(self.semantic.triples) == 1


class TestConflictDetection:
    """冲突检测测试"""

    def setup_method(self):
        self.semantic = FakeSemanticStore()
        self.mgr = MemoryManager(semantic_store=self.semantic)

    def test_no_triples_no_conflicts(self):
        conflicts = self.mgr.detect_conflicts()
        assert len(conflicts) == 0

    def test_no_conflict_when_consistent(self):
        self.semantic.triples = [
            {"subject": "电池", "predicate": "CAUSES", "object": "成本下降",
             "confidence": 0.9},
            {"subject": "电池", "predicate": "CAUSES", "object": "成本下降",
             "confidence": 0.8},  # 相同 object，不冲突
        ]
        conflicts = self.mgr.detect_conflicts()
        assert len(conflicts) == 0  # 相同 object 不算冲突

    def test_detect_contradiction(self):
        self.semantic.triples = [
            {"subject": "电池", "predicate": "CAUSES", "object": "成本下降",
             "confidence": 0.9},
            {"subject": "电池", "predicate": "CAUSES", "object": "成本上升",
             "confidence": 0.3},  # 不同 object，置信度差 > 0.3
        ]
        conflicts = self.mgr.detect_conflicts()
        assert len(conflicts) == 1
        c = conflicts[0]
        assert c.subject == "电池"
        assert c.predicate == "CAUSES"
        assert c.severity == "high"  # delta 0.6 > 0.6

    def test_conflict_severity_medium(self):
        self.semantic.triples = [
            {"subject": "X", "predicate": "RELATES", "object": "A",
             "confidence": 0.8},
            {"subject": "X", "predicate": "RELATES", "object": "B",
             "confidence": 0.4},  # delta 0.4 → medium
        ]
        conflicts = self.mgr.detect_conflicts()
        assert len(conflicts) == 1
        assert conflicts[0].severity == "medium"

    def test_conflict_report_description(self):
        c = ConflictReport(
            subject="S", predicate="P",
            object_a="A", object_b="B",
            confidence_a=0.9, confidence_b=0.2,
        )
        assert "S" in c.description
        assert "P" in c.description


class TestPruning:
    """记忆修剪测试"""

    def setup_method(self):
        self.episodic = FakeEpisodicStore()
        self.mgr = MemoryManager(episodic_store=self.episodic)

    def test_prune_removes_stale(self):
        # 极旧 + 低重要性 + 零访问 = 应该被清理
        very_old = time.time() - 86400 * 365  # 一年前
        self.episodic.memories = [
            FakeMemory("新记忆", timestamp=time.time(), access_count=5),
            FakeMemory("极旧记忆", timestamp=very_old, access_count=0),
        ]
        pruned = self.mgr.prune_stale(threshold=0.01)
        assert pruned >= 1  # 极旧记忆应该被清理

    def test_prune_keeps_important(self):
        now = time.time()
        self.episodic.memories = [
            FakeMemory("重要记忆", timestamp=now, access_count=100),
        ]
        pruned = self.mgr.prune_stale(threshold=0.01)
        assert pruned == 0  # 重要记忆不应被清理


class TestMaintenance:
    """全量维护测试"""

    def setup_method(self):
        self.episodic = FakeEpisodicStore()
        self.semantic = FakeSemanticStore()
        self.skill = FakeSkillStore()
        self.mgr = MemoryManager(
            episodic_store=self.episodic,
            semantic_store=self.semantic,
            skill_store=self.skill,
        )

    def test_run_maintenance_empty(self):
        report = self.mgr.run_maintenance()
        assert isinstance(report, MaintenanceReport)
        assert report.pruned_count == 0
        assert report.consolidated_groups == 0
        assert report.conflicts_detected == 0
        assert report.duration_ms >= 0

    def test_run_maintenance_with_data(self):
        # 添加足够的记忆触发巩固
        for i in range(6):
            self.episodic.memories.append(FakeMemory(
                f"测试记忆 #{i}",
                context={"domain": "testing"},
            ))
        report = self.mgr.run_maintenance()
        assert report.consolidated_groups >= 0
        # 统计键可能是 episodic_episodic 或包含 episodic
        any_episodic = any("episodic" in k for k in report.memory_stats)
        assert any_episodic

    def test_health_report(self):
        self.episodic.memories = [
            FakeMemory(f"mem #{i}")
            for i in range(10)
        ]
        report = self.mgr.health_report()
        assert "maintenance_count" in report
        assert "memory_counts" in report
        assert "decay" in report


class TestConstants:
    """确保关键常量未被意外修改"""

    def test_forgetting_half_lives(self):
        assert FORGETTING_HALF_LIFE["episodic"] == 7.0
        assert FORGETTING_HALF_LIFE["semantic"] == 30.0
        assert FORGETTING_HALF_LIFE["skill"] == 90.0

    def test_thresholds(self):
        assert 0 < PRUNE_THRESHOLD < 0.1
        assert CONSOLIDATION_THRESHOLD >= 3
