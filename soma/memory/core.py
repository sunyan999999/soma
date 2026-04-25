from typing import Any, Dict, List, Optional

from soma.base import ActivatedMemory, Focus, MemoryUnit
from soma.config import SOMAConfig
from soma.memory.episodic import EpisodicStore
from soma.memory.semantic import SemanticStore
from soma.memory.skill import SkillStore


class MemoryCore:
    """统一记忆存储门面"""

    def __init__(self, config: SOMAConfig):
        self.episodic = EpisodicStore(config.episodic_persist_dir)
        self.semantic = SemanticStore()
        self.skill = SkillStore()

    def remember(
        self,
        content: str,
        context: Optional[Dict[str, Any]] = None,
        importance: float = 0.5,
    ) -> str:
        """存储情节记忆"""
        return self.episodic.add(content, context, importance)

    def remember_semantic(
        self,
        subject: str,
        predicate: str,
        object_: str,
        confidence: float = 1.0,
    ) -> None:
        """存储语义三元组"""
        self.semantic.add_triple(subject, predicate, object_, confidence)

    def query(self, focus: Focus, top_k: int = 5) -> List[ActivatedMemory]:
        """对单个 Focus 跨三个子库查询，返回 ActivatedMemory 列表"""
        activated: List[ActivatedMemory] = []
        keywords = focus.keywords

        # 查询情节记忆
        episodic_results = self.episodic.query_by_keywords(keywords, top_k)
        for mem in episodic_results:
            matched = [kw for kw in keywords if kw.lower() in mem.content.lower()]
            activated.append(
                ActivatedMemory(
                    memory=mem,
                    activation_score=0.0,  # 由 ActivationHub 最终计算
                    source="episodic",
                    match_rationale=f"关键词匹配: {', '.join(matched[:3])}",
                )
            )

        # 查询语义记忆
        semantic_results = self.semantic.query_by_keywords(keywords, top_k)
        for mem in semantic_results:
            matched = [kw for kw in keywords if kw.lower() in mem.content.lower()]
            activated.append(
                ActivatedMemory(
                    memory=mem,
                    activation_score=0.0,
                    source="semantic",
                    match_rationale=f"图谱匹配: {', '.join(matched[:3])}",
                )
            )

        # 查询技能记忆
        skill_results = self.skill.query_by_keywords(keywords, top_k)
        for mem in skill_results:
            activated.append(
                ActivatedMemory(
                    memory=mem,
                    activation_score=0.0,
                    source="skill",
                    match_rationale="技能模式匹配",
                )
            )

        return activated

    def stats(self) -> Dict[str, int]:
        return {
            "episodic": self.episodic.count(),
            "semantic": self.semantic.count_triples(),
            "skill": self.skill.count(),
        }
