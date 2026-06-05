"""专家路由器 — 将问题自动分配给最匹配的专家 agent"""

import logging
from typing import List, Optional, Tuple

from soma.multi_agent.registry import AgentRegistry

_log = logging.getLogger("soma.multi_agent")

# 领域→关键词映射表，用于快速路由（无需 LLM）
# v1.1.4: 双语关键词支持，新增哲学/心理/传统文化领域，匹配已注册专家
_DOMAIN_KEYWORDS: dict = {
    # ── 原有通用领域（中英双语）──
    "法律": ["法律", "合同", "诉讼", "法规", "合规", "知识产权", "版权", "专利", "仲裁",
             "law", "legal", "contract", "lawsuit", "compliance", "patent", "arbitration"],
    "技术": ["代码", "架构", "API", "数据库", "部署", "算法", "性能", "bug", "编程",
             "code", "architecture", "database", "deploy", "algorithm", "programming", "debug"],
    "金融": ["投资", "股票", "基金", "财务", "预算", "成本", "收入", "利润", "税务",
             "invest", "stock", "fund", "finance", "budget", "profit", "tax"],
    "管理": ["团队", "管理", "领导", "组织", "战略", "流程", "考核", "招聘", "文化",
             "team", "management", "leadership", "strategy", "process", "recruit"],
    "产品": ["用户", "需求", "体验", "设计", "功能", "迭代", "增长", "留存", "转化",
             "user", "requirement", "UX", "feature", "iteration", "retention", "conversion"],
    "科学": ["实验", "假设", "数据", "统计", "变量", "控制组", "显著性", "相关性",
             "experiment", "hypothesis", "statistics", "variable", "correlation"],
    "教育": ["学习", "教学", "课程", "培训", "知识", "技能", "考试", "毕业",
             "learn", "teach", "course", "training", "exam", "graduate"],
    "医疗": ["诊断", "治疗", "药物", "手术", "患者", "临床", "病理", "预防",
             "diagnosis", "treatment", "medicine", "surgery", "patient", "clinical"],
    # ── 新增：匹配已注册专家 ──
    "哲学": ["哲学", "人生", "意义", "命运", "存在", "价值", "思维", "思考", "世界观",
             "生死", "自由", "选择", "本质", "真理", "道", "悟", "觉悟",
             "philosophy", "meaning", "destiny", "existence", "truth", "freedom", "wisdom"],
    "心理": ["心理", "情绪", "压力", "焦虑", "抑郁", "情感", "关系", "失眠", "疏导",
             "调节", "安全感", "内耗", "自我", "疗愈", "共情", "边界", "沟通",
             "psychology", "emotion", "stress", "anxiety", "depression", "therapy", "healing"],
    "传统文化": ["易经", "国学", "儒释道", "老子", "孔子", "道德经", "论语", "佛经",
               "阴阳", "五行", "太极", "八卦", "典故", "经典", "古训", "传统",
               "周易", "易经", "自强不息", "厚德载物", "中庸", "仁义",
               "culture", "traditional", "I-Ching", "Confucius", "Taoism", "Buddhism"],
}


def _extract_domain_keywords(problem: str) -> dict:
    """从问题中提取领域信号，返回 {领域: 命中次数}"""
    scores = {}
    problem_lower = problem.lower()
    for domain, keywords in _DOMAIN_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw.lower() in problem_lower)
        if hits > 0:
            scores[domain] = hits
    return scores


class ExpertRouter:
    """专家路由器 — 分析问题并将请求路由到最匹配的专家 agent

    三层路由策略：
    L1: 关键词快速匹配（零延迟，适合明确领域的问题）
    L2: 语义相似度匹配（需要embedder，适合模糊领域的问题）
    L3: 回退到默认 agent（无匹配时）
    """

    def __init__(self, registry: AgentRegistry, embedder=None):
        self.registry = registry
        self._embedder = embedder
        # 路由统计
        self.route_count: int = 0
        self.l1_hits: int = 0
        self.l2_hits: int = 0
        self.fallbacks: int = 0

    def route(
        self,
        problem: str,
        min_confidence: float = 0.3,
        allow_fallback: bool = True,
    ) -> Tuple[object, float, str]:
        """将问题路由到最匹配的专家 agent。

        返回 (agent, confidence, strategy)，strategy 为 "l1"/"l2"/"fallback"。
        """
        self.route_count += 1

        # L1: 关键词快速匹配
        agent, confidence = self._route_l1(problem, min_confidence)
        if agent is not None:
            self.l1_hits += 1
            return agent, confidence, "l1"

        # L2: 语义相似度匹配（需要 embedder）
        if self._embedder is not None:
            agent, confidence = self._route_l2(problem, min_confidence)
            if agent is not None:
                self.l2_hits += 1
                return agent, confidence, "l2"

        # L3: 回退到默认 agent
        if allow_fallback:
            default = self.registry.get_default()
            if default is not None:
                self.fallbacks += 1
                return default, 0.1, "fallback"

        # 无可用 agent
        raise RuntimeError(
            "没有可用的 agent 处理此问题。请先注册至少一个 agent 或设置默认 agent。"
        )

    def route_multi(
        self, problem: str, top_k: int = 3, min_confidence: float = 0.2,
    ) -> List[Tuple[object, float, str]]:
        """返回前 K 个匹配的专家 agent（用于多角度分析）"""
        self.route_count += 1
        results = []

        # L1: 关键词快速匹配
        domain_scores = _extract_domain_keywords(problem)
        for domain, hits in domain_scores.items():
            experts = self.registry.find_experts(domain, min_score=min_confidence)
            for agent, score in experts:
                results.append((agent, score * min(hits / 3, 1.0), "l1"))
        if results:
            self.l1_hits += 1  # v1.1.4: 修复 route_multi 未计入 l1_hits

        # L2: 语义相似度匹配
        if self._embedder is not None and (not results or len(results) < top_k):
            for info in self.registry.list_agents():
                if not info.expertise:
                    continue
                # 用 embedder 计算问题与专长描述的语义相似度
                try:
                    expertise_text = " ".join(info.expertise) + " " + info.description
                    sim = self._semantic_similarity(problem, expertise_text)
                    if sim >= min_confidence:
                        agent = self.registry.get(info.agent_id)
                        if agent is not None:
                            results.append((agent, sim, "l2"))
                except Exception:
                    pass
            if any(s == "l2" for _, _, s in results):
                self.l2_hits += 1  # v1.1.4: 修复 route_multi 未计入 l2_hits

        # 去重 + 排序
        seen = set()
        deduped = []
        for agent, score, strategy in sorted(results, key=lambda x: -x[1]):
            aid = getattr(agent, 'agent_id', id(agent))
            if aid not in seen:
                seen.add(aid)
                deduped.append((agent, score, strategy))

        if not deduped:
            default = self.registry.get_default()
            if default is not None:
                deduped.append((default, 0.1, "fallback"))
                self.fallbacks += 1  # v1.1.4: 修复 route_multi 未计入 fallbacks

        return deduped[:top_k]

    def _route_l1(
        self, problem: str, min_confidence: float,
    ) -> Tuple[Optional[object], float]:
        """L1: 关键词→领域快速路由"""
        domain_scores = _extract_domain_keywords(problem)
        if not domain_scores:
            return None, 0.0

        # 取命中最多的领域
        best_domain = max(domain_scores, key=domain_scores.get)
        hits = domain_scores[best_domain]
        confidence = min(hits / 3.0, 1.0)  # 3个关键词命中 = 满分

        if confidence < min_confidence:
            return None, 0.0

        experts = self.registry.find_experts(best_domain)
        if experts:
            return experts[0][0], confidence * experts[0][1]

        return None, 0.0

    def _route_l2(
        self, problem: str, min_confidence: float,
    ) -> Tuple[Optional[object], float]:
        """L2: 语义相似度匹配"""
        if self._embedder is None:
            return None, 0.0

        best_agent = None
        best_score = 0.0

        for info in self.registry.list_agents():
            if not info.expertise:
                continue
            try:
                expertise_text = " ".join(info.expertise) + " " + info.description
                sim = self._semantic_similarity(problem, expertise_text)
                if sim > best_score:
                    best_score = sim
                    best_agent = self.registry.get(info.agent_id)
            except Exception:
                _log.debug("L2路由语义计算失败: agent=%s", info.agent_id, exc_info=True)

        if best_agent is not None and best_score >= min_confidence:
            return best_agent, best_score
        return None, 0.0

    def _semantic_similarity(self, text1: str, text2: str) -> float:
        """计算两段文本的语义相似度（余弦相似度）"""
        import numpy as np

        if self._embedder is None:
            return 0.0
        try:
            v1 = np.asarray(self._embedder.encode(text1), dtype=np.float32)
            v2 = np.asarray(self._embedder.encode(text2), dtype=np.float32)
            dot = float(np.dot(v1, v2))
            n1 = float(np.linalg.norm(v1))
            n2 = float(np.linalg.norm(v2))
            if n1 == 0 or n2 == 0:
                return 0.0
            return dot / (n1 * n2)
        except Exception:
            return 0.0

    @property
    def stats(self) -> dict:
        """路由统计信息"""
        total = max(self.route_count, 1)
        return {
            "route_count": self.route_count,
            "l1_hit_rate": self.l1_hits / total,
            "l2_hit_rate": self.l2_hits / total,
            "fallback_rate": self.fallbacks / total,
        }
