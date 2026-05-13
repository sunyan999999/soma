"""共识形成协议 — 多 agent 对同一问题协调形成共识"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Callable

from soma.base import ActivatedMemory, Focus

_log = logging.getLogger("soma.multi_agent")


@dataclass
class AgentOpinion:
    """单个 agent 对问题的观点"""
    agent_id: str
    answer: str  # agent 的完整回答
    confidence: float = 0.5  # agent 对自身回答的置信度（0-1）
    foci: List[Focus] = field(default_factory=list)  # 使用的思维焦点
    key_points: List[str] = field(default_factory=list)  # 核心论点
    supporting_memories: int = 0  # 支持此观点的记忆数量

    def summary(self) -> str:
        """观点摘要"""
        points = "; ".join(self.key_points[:3]) if self.key_points else "无核心论点"
        return f"[{self.agent_id}] (置信度={self.confidence:.2f}) {points}"


@dataclass
class ConsensusResult:
    """共识形成结果"""
    question: str
    consensus_answer: str  # 最终共识回答
    agreement_level: float  # 共识度（0-1，1=完全一致）
    agent_opinions: List[AgentOpinion]
    strategy_used: str  # "voting" / "llm_arbitration" / "dialectical_synthesis"
    disagreements: List[Dict[str, Any]] = field(default_factory=list)  # 分歧点列表
    minority_view: Optional[str] = None  # 少数派观点（如有）
    synthesis_notes: str = ""  # 综合说明

    @property
    def is_strong_consensus(self) -> bool:
        return self.agreement_level >= 0.8

    @property
    def agent_count(self) -> int:
        return len(self.agent_opinions)


class ConsensusProtocol:
    """多 agent 共识形成协议

    三级共识策略：
    - L1 "voting": 加权多数投票（快速，适合简单问题）
    - L2 "llm_arbitration": LLM 仲裁分歧（适合中等分歧）
    - L3 "dialectical_synthesis": 辩证综合正反合（适合深层哲学问题）
    """

    def __init__(self, llm_call: Optional[Callable] = None):
        """llm_call: 可选的 LLM 调用函数，签名 (prompt) -> str"""
        self._llm_call = llm_call
        self.session_count: int = 0

    def form_consensus(
        self,
        question: str,
        opinions: List[AgentOpinion],
        strategy: str = "voting",
    ) -> ConsensusResult:
        """从多个 agent 的观点中形成共识。

        Args:
            question: 原始问题
            opinions: 各 agent 的观点列表（至少1个）
            strategy: "voting" / "llm_arbitration" / "dialectical_synthesis"

        Returns:
            ConsensusResult: 包含共识回答、共识度、分歧点等
        """
        self.session_count += 1

        if not opinions:
            raise ValueError("至少需要一个 agent 观点才能形成共识")

        if len(opinions) == 1:
            # 单 agent：无需共识，直接返回
            return ConsensusResult(
                question=question,
                consensus_answer=opinions[0].answer,
                agreement_level=1.0,
                agent_opinions=opinions,
                strategy_used="single_agent",
            )

        if strategy == "llm_arbitration" and self._llm_call is not None:
            return self._llm_arbitration(question, opinions)
        elif strategy == "dialectical_synthesis" and self._llm_call is not None:
            return self._dialectical_synthesis(question, opinions)
        else:
            return self._weighted_voting(question, opinions)

    def _weighted_voting(
        self, question: str, opinions: List[AgentOpinion],
    ) -> ConsensusResult:
        """L1: 加权多数投票

        按 (confidence × 记忆支持数) 加权。
        检测分歧点，标记少数派观点。
        """
        # 计算每个 agent 的投票权重
        weights = []
        for op in opinions:
            memory_bonus = min(op.supporting_memories / 5.0, 1.0)  # 最多翻倍
            w = op.confidence * (1.0 + 0.3 * memory_bonus)
            weights.append(max(w, 0.1))

        total_w = sum(weights)

        # 检测观点分歧
        disagreements = self._detect_disagreements(opinions)
        agreement_level = self._compute_agreement(opinions, disagreements)

        # 选择权重最高的观点作为主要回答
        best_idx = max(range(len(weights)), key=lambda i: weights[i])
        consensus_answer = opinions[best_idx].answer

        # 如果有显著分歧，综合多个观点
        if agreement_level < 0.6 and len(opinions) >= 2:
            # 按权重取前两名综合
            ranked = sorted(
                range(len(weights)), key=lambda i: weights[i], reverse=True,
            )
            top2 = [opinions[ranked[0]], opinions[ranked[1]]]
            consensus_answer = (
                f"**多数观点** (置信度 {top2[0].confidence:.2f}):\n{top2[0].answer}\n\n"
                f"**补充视角** (置信度 {top2[1].confidence:.2f}):\n{top2[1].answer}\n\n"
                f"**共识度**: {agreement_level:.1%} | 策略: 加权投票"
            )

        # 少数派观点
        minority_view = None
        if agreement_level < 0.8 and len(opinions) >= 3:
            worst_idx = min(range(len(weights)), key=lambda i: weights[i])
            minority_view = (
                f"[{opinions[worst_idx].agent_id}] "
                f"{opinions[worst_idx].answer[:300]}"
            )

        return ConsensusResult(
            question=question,
            consensus_answer=consensus_answer,
            agreement_level=agreement_level,
            agent_opinions=opinions,
            strategy_used="voting",
            disagreements=disagreements,
            minority_view=minority_view,
        )

    def _llm_arbitration(
        self, question: str, opinions: List[AgentOpinion],
    ) -> ConsensusResult:
        """L2: LLM 仲裁 — 将分歧提交 LLM 综合判断"""
        opinions_text = "\n\n".join(
            f"### Agent {op.agent_id} (置信度: {op.confidence:.2f})\n{op.answer[:800]}"
            for op in opinions
        )

        prompt = f"""你是仲裁者。以下是 {len(opinions)} 个 AI Agent 对同一问题的回答。
请综合分析，给出公正的仲裁结论。

## 原始问题
{question}

## 各 Agent 回答
{opinions_text}

## 请完成以下任务
1. 识别各 agent 回答中的共同点和分歧点
2. 判断哪个观点最有说服力，说明理由
3. 给出综合结论（3-5 句话）
4. 评估总体共识度（0-1 的数字）

请按以下格式回答：
共识度: [0-1数字]
仲裁结论: [综合结论]
分歧点: [简要列出]"""

        try:
            arbitration = self._llm_call(prompt)
        except Exception:
            _log.warning("LLM 仲裁失败，回退到投票策略")
            return self._weighted_voting(question, opinions)

        # 解析 LLM 输出
        agreement_level = 0.5
        consensus_answer = ""
        disagreements = []

        for line in arbitration.split("\n"):
            line = line.strip()
            if line.startswith("共识度:") or line.startswith("共识度："):
                try:
                    # 提取数字
                    nums = ''.join(c for c in line if c.isdigit() or c == '.')
                    agreement_level = min(max(float(nums), 0.0), 1.0) if nums else 0.5
                except ValueError:
                    pass
            elif line.startswith("仲裁结论:") or line.startswith("仲裁结论："):
                consensus_answer = line.split(":", 1)[-1].split("：", 1)[-1].strip()
            elif "分歧" in line and ":" in line:
                disagreements.append({"description": line.split(":", 1)[-1].strip()})

        if not consensus_answer:
            # 解析失败，取 LLM 输出的后 500 字符
            consensus_answer = arbitration[-500:].strip()

        return ConsensusResult(
            question=question,
            consensus_answer=consensus_answer or arbitration[:500],
            agreement_level=agreement_level,
            agent_opinions=opinions,
            strategy_used="llm_arbitration",
            disagreements=disagreements,
        )

    def _dialectical_synthesis(
        self, question: str, opinions: List[AgentOpinion],
    ) -> ConsensusResult:
        """L3: 辩证综合 — 正反合方法论"""
        # 仅取前3个最有信心的观点
        ranked = sorted(opinions, key=lambda o: o.confidence, reverse=True)[:3]

        opinions_text = "\n\n".join(
            f"### Agent {op.agent_id} (置信度: {op.confidence:.2f})\n{op.answer[:600]}"
            for op in ranked
        )

        prompt = f"""你是辩证思考者。请用正反合（thesis-antithesis-synthesis）方法综合以下观点。

## 问题
{question}

## 各方观点
{opinions_text}

## 请按正反合结构回答
**正题 (Thesis)**: 各方观点的核心共识是什么？
**反题 (Antithesis)**: 各方观点的核心分歧/对立在哪里？
**合题 (Synthesis)**: 超越分歧的更高层次综合——不是折中，而是能包容各方合理性的框架。

请用中文回答，300-500字。"""

        try:
            synthesis = self._llm_call(prompt)
        except Exception:
            _log.warning("辩证综合失败，回退到LLM仲裁")
            return self._llm_arbitration(question, opinions)

        return ConsensusResult(
            question=question,
            consensus_answer=synthesis,
            agreement_level=0.6,  # 辩证综合默认中等共识度
            agent_opinions=opinions,
            strategy_used="dialectical_synthesis",
            synthesis_notes="采用正反合方法论，综合各方观点形成更高层次框架",
        )

    def _detect_disagreements(
        self, opinions: List[AgentOpinion],
    ) -> List[Dict[str, Any]]:
        """检测 agent 观点之间的分歧"""
        disagreements = []
        if len(opinions) < 2:
            return disagreements

        for i in range(len(opinions)):
            for j in range(i + 1, len(opinions)):
                a, b = opinions[i], opinions[j]
                # 置信度差异大 = 可能分歧
                conf_diff = abs(a.confidence - b.confidence)
                if conf_diff > 0.3:
                    # 检查关键论点是否差异大
                    a_set = set(p.lower()[:30] for p in a.key_points)
                    b_set = set(p.lower()[:30] for p in b.key_points)
                    overlap = len(a_set & b_set)
                    total = len(a_set | b_set)
                    if total > 0 and overlap / total < 0.3:
                        disagreements.append({
                            "agents": [a.agent_id, b.agent_id],
                            "confidence_gap": round(conf_diff, 2),
                            "a_points": a.key_points[:3],
                            "b_points": b.key_points[:3],
                        })

        return disagreements

    def _compute_agreement(
        self,
        opinions: List[AgentOpinion],
        disagreements: List[Dict[str, Any]],
    ) -> float:
        """基于分歧数量和严重程度计算共识度"""
        if not opinions:
            return 1.0

        n = len(opinions)
        # 基础：无分歧=1.0，有分歧=按数量和严重程度扣分
        if not disagreements:
            # 检查置信度方差
            confs = [op.confidence for op in opinions]
            if len(confs) > 1:
                mean_c = sum(confs) / len(confs)
                variance = sum((c - mean_c) ** 2 for c in confs) / len(confs)
                return max(0.5, 1.0 - variance * 2)
            return 1.0

        # 有分歧：每个分歧点扣 0.15，最大间隔扣 0.1
        max_gap = max((d["confidence_gap"] for d in disagreements), default=0)
        penalty = min(len(disagreements) * 0.15 + max_gap * 0.1, 0.7)
        return max(0.3, 1.0 - penalty)
