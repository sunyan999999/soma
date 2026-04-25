import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from soma.base import MemoryUnit


class SkillStore:
    """技能模式存储 — MVP 最小实现，Alpha 阶段完整实现技能抽取"""

    def __init__(self):
        self._skills: Dict[str, Dict[str, Any]] = {}

    def add_skill(self, name: str, pattern: str, context: Optional[Dict] = None) -> str:
        skill_id = uuid.uuid4().hex
        self._skills[skill_id] = {
            "name": name,
            "pattern": pattern,
            "context": context or {},
            "created_at": datetime.now(timezone.utc).timestamp(),
        }
        return skill_id

    def query_by_keywords(self, keywords: List[str], top_k: int = 3) -> List[MemoryUnit]:
        results = []
        for sid, skill in self._skills.items():
            text = f"{skill['name']} {skill['pattern']}"
            matched = [kw for kw in keywords if kw.lower() in text.lower()]
            if matched:
                results.append(
                    MemoryUnit(
                        id=sid,
                        content=f"技能: {skill['name']} — {skill['pattern']}",
                        context=skill["context"],
                        memory_type="skill",
                        importance=0.8,
                    )
                )
        return results[:top_k]

    def count(self) -> int:
        return len(self._skills)
