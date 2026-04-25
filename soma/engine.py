import re
from typing import List

from soma.base import Focus
from soma.config import FrameworkConfig, WisdomLaw

# 中英文停用词
_STOP_WORDS = {
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一",
    "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着",
    "没有", "看", "好", "自己", "这", "他", "她", "它", "们", "那", "个",
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "shall", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "through", "during",
    "before", "after", "above", "below", "between", "under", "again",
    "further", "then", "once", "here", "there", "when", "where", "why",
    "how", "all", "both", "each", "few", "more", "most", "other", "some",
    "such", "no", "nor", "not", "only", "own", "same", "so", "than",
    "too", "very", "just", "because", "but", "and", "or", "if", "while",
    "although", "though", "even", "also", "it", "its", "that", "this",
    "these", "those", "what", "which", "who", "whom",
}


def _extract_keywords(text: str, max_keywords: int = 10) -> List[str]:
    """从文本中提取关键词 — MVP 简单分词 + 停用词过滤"""
    # 按中英文标点、空格、引号分割
    tokens = re.split(
        r"[，。！？、\s,.!?;:；：\-+()（）\[\]【】/\\"
        + "\""
        + "'"
        + r"“”‘’]+",
        text,
    )
    keywords = []
    for token in tokens:
        token = token.strip().lower()
        if token and token not in _STOP_WORDS and len(token) >= 2:
            keywords.append(token)
    # 去重保持顺序
    seen = set()
    unique = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            unique.append(kw)
    return unique[:max_keywords]


class WisdomEngine:
    """思维框架引擎 — 基于规律图谱拆解问题为分析焦点"""

    def __init__(self, framework: FrameworkConfig):
        self.laws: List[WisdomLaw] = framework.laws
        # 按权重降序排列
        self.laws.sort(key=lambda law: law.weight, reverse=True)

    def decompose(self, problem: str) -> List[Focus]:
        """
        将问题按思维规律拆解为分析焦点。

        MVP 策略：关键词匹配。
        对每条规律检查其 triggers 是否出现在问题中，
        匹配则生成一个 Focus。
        无匹配时返回最高权重规律作为默认透镜。
        """
        foci: List[Focus] = []
        problem_lower = problem.lower()

        for law in self.laws:
            matched_triggers = [
                t for t in law.triggers if t.lower() in problem_lower
            ]
            if matched_triggers:
                dimension = f"从「{law.name}」出发：{law.description}。应用于问题：「{problem}」"
                keywords = list(set(law.triggers + _extract_keywords(problem)))
                focus = Focus(
                    law_id=law.id,
                    dimension=dimension,
                    keywords=keywords,
                    weight=law.weight,
                    rationale=f"问题中出现触发词：{', '.join(matched_triggers)}",
                )
                foci.append(focus)

        # 兜底：无匹配时使用最高权重规律
        if not foci:
            top_law = self.laws[0]
            dimension = f"从「{top_law.name}」视角审视：{top_law.description}。应用于问题：「{problem}」"
            keywords = _extract_keywords(problem) + top_law.triggers
            foci.append(
                Focus(
                    law_id=top_law.id,
                    dimension=dimension,
                    keywords=keywords,
                    weight=top_law.weight,
                    rationale="无特定规律匹配，默认应用最高权重思维规律",
                )
            )

        # 按 weight 降序排列
        foci.sort(key=lambda f: f.weight, reverse=True)
        return foci
