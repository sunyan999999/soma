"""自动化知识图谱构建器 — 从记忆中自动提取三元组和关联边

三路自动构建：
  1. 模式匹配: 中文因果/归属/依赖关系 → 语义三元组
  2. 会话共现: 同会话记忆 → 关联边
  3. 关键词重叠: Jaccard > 阈值 → 相似边

周期性触发（每次 memory_maintenance 或 evolve 时自动运行），
无需手动喂养，图谱自我生长。

用法::

    from soma.graph_builder import AutoGraphBuilder

    builder = AutoGraphBuilder(episodic_store, semantic_store)
    report = builder.build()  # 运行一轮自动构建
    print(f"新增三元组: {report['new_triples']}, 边: {report['new_edges']}")
"""

import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from itertools import combinations
from typing import Any, Dict, List, Optional, Set, Tuple


# ═══════════════════════════════════════════════════════════════
# 中文关系提取模式
# ═══════════════════════════════════════════════════════════════

# (模式正则, 谓语, 主体组索引, 客体组索引)
EXTRACTION_PATTERNS = [
    # 因果关系
    (r"([^\s，,。；;]{2,20})[的之]?(?:直接)?导致[了]?([^\s，,。；;]{2,30})", "CAUSES", 1, 2),
    (r"([^\s，,。；;]{2,20})[的之]?(?:直接)?引起[了]?([^\s，,。；;]{2,30})", "CAUSES", 1, 2),
    (r"([^\s，,。；;]{2,20})[的之]?造成[了]?([^\s，,。；;]{2,30})", "CAUSES", 1, 2),
    (r"因为([^\s，,。；;]{2,20})[，,]?所以([^\s，,。；;]{2,30})", "CAUSES", 1, 2),
    (r"由于([^\s，,。；;]{2,20})[，,]?([^\s，,。；;]{2,30})", "CAUSES", 1, 2),
    # 归属关系
    (r"([^\s，,。；;]{2,20})属于([^\s，,。；;]{2,20})(?:的)?(?:一种|范畴|类型)", "IS_A", 1, 2),
    (r"([^\s，,。；;]{2,20})是([^\s，,。；;]{2,20})(?:的)?(?:一种|子类|子集)", "IS_A", 1, 2),
    # 包含关系
    (r"([^\s，,。；;]{2,20})包含[了]?([^\s，,。；;]{2,30})", "CONTAINS", 1, 2),
    (r"([^\s，,。；;]{2,20})包括[了]?([^\s，,。；;]{2,30})", "CONTAINS", 1, 2),
    (r"([^\s，,。；;]{2,20})由([^\s，,。；;]{2,20})(?:组成|构成|构建)", "CONTAINS", 1, 2),
    # 依赖关系
    (r"([^\s，,。；;]{2,20})依赖[于]?([^\s，,。；;]{2,30})", "DEPENDS_ON", 1, 2),
    (r"([^\s，,。；;]{2,20})需要([^\s，,。；;]{2,20})(?:的)?(?:支持|配合|辅助)", "DEPENDS_ON", 1, 2),
    (r"([^\s，,。；;]{2,20})基于([^\s，,。；;]{2,30})", "DEPENDS_ON", 1, 2),
    # 相似关系
    (r"([^\s，,。；;]{2,20})(?:类似|类似[于]|好比|如同|相当于)([^\s，,。；;]{2,30})", "SIMILAR_TO", 1, 2),
    (r"([^\s，,。；;]{2,20})(?:与|和|跟)([^\s，,。；;]{2,20})(?:相似|类似|相近|类同)", "SIMILAR_TO", 1, 2),
    # 关联关系
    (r"([^\s，,。；;]{2,20})(?:与|和|跟)([^\s，,。；;]{2,20})(?:相关|有关|关联|相连)", "RELATED_TO", 1, 2),
    # 时序关系
    (r"([^\s，,。；;]{2,20})(?:先于|早于|之前)([^\s，,。；;]{2,30})", "PRECEDES", 1, 2),
    (r"([^\s，,。；;]{2,20})(?:后于|晚于|之后)([^\s，,。；;]{2,30})", "PRECEDES", 2, 1),  # 主客体交换
    # 对立关系
    (r"([^\s，,。；;]{2,20})(?:与|和|跟)([^\s，,。；;]{2,20})(?:相反|对立|矛盾|冲突)", "OPPOSES", 1, 2),
]


@dataclass
class GraphBuildReport:
    """一轮图谱构建的报告"""
    new_triples: int = 0
    new_session_edges: int = 0
    new_keyword_edges: int = 0
    total_semantic_after: int = 0
    duration_ms: float = 0.0
    sample_triples: List[Tuple[str, str, str]] = field(default_factory=list)


class AutoGraphBuilder:
    """自动知识图谱构建器

    三路构建 + 去重 + 置信度管理。
    纯本地计算，零 LLM 依赖。
    """

    # 关键词 Jaccard 相似度阈值
    KEYWORD_SIMILARITY_THRESHOLD = 0.3
    # 每轮最多新建三元组数（防止爆炸）
    MAX_TRIPLES_PER_RUN = 100
    # 每轮最多新建边数
    MAX_EDGES_PER_RUN = 200

    def __init__(self, episodic_store=None, semantic_store=None):
        self.episodic = episodic_store
        self.semantic = semantic_store
        self._existing_triples: Set[Tuple[str, str, str]] = set()

    # ═══════════════════════════════════════════════════════════
    # 主入口
    # ═══════════════════════════════════════════════════════════

    def build(self, max_memories: int = 200) -> GraphBuildReport:
        """运行一轮完整的图谱构建。

        Args:
            max_memories: 最多处理多少条近期记忆

        Returns:
            GraphBuildReport 构建统计
        """
        t0 = time.perf_counter()
        report = GraphBuildReport()

        # 加载已有三元组（去重用）
        self._load_existing_triples()

        # 获取近期记忆
        memories = self._get_recent_memories(max_memories)
        if not memories:
            report.duration_ms = round((time.perf_counter() - t0) * 1000, 1)
            report.total_semantic_after = len(self._existing_triples)
            return report

        # ── 路径1: 模式匹配提取三元组 ──
        new_triples = self._extract_triples_from_memories(memories)
        stored = self._store_triples(new_triples)
        report.new_triples = stored
        report.sample_triples = new_triples[:5]

        # ── 路径2: 会话共现边 ──
        session_edges = self._build_session_cooccurrence_edges(memories)
        stored_edges = self._store_edges(session_edges, "CO_OCCURS")
        report.new_session_edges = stored_edges

        # ── 路径3: 关键词重叠边 ──
        keyword_edges = self._build_keyword_overlap_edges(memories)
        stored_kw = self._store_edges(keyword_edges, "KEYWORD_OVERLAP")
        report.new_keyword_edges = stored_kw

        report.total_semantic_after = len(self._existing_triples) + stored + stored_edges + stored_kw
        report.duration_ms = round((time.perf_counter() - t0) * 1000, 1)
        return report

    # ═══════════════════════════════════════════════════════════
    # 路径1: 模式匹配
    # ═══════════════════════════════════════════════════════════

    def _extract_triples_from_memories(
        self, memories: List[Any]
    ) -> List[Tuple[str, str, str]]:
        """从记忆文本中提取中文语义三元组"""
        triples = []
        seen = set()

        for mem in memories:
            content = getattr(mem, "content", str(mem))
            extracted = self._extract_from_text(content)
            for triple in extracted:
                key = (triple[0][:30], triple[1], triple[2][:30])
                if key not in seen and key not in self._existing_triples:
                    seen.add(key)
                    triples.append(key)

            if len(triples) >= self.MAX_TRIPLES_PER_RUN:
                break

        return triples

    def _extract_from_text(self, text: str) -> List[Tuple[str, str, str]]:
        """从单段文本提取三元组"""
        triples = []
        for pattern, predicate, subj_idx, obj_idx in EXTRACTION_PATTERNS:
            for match in re.finditer(pattern, text):
                subj = match.group(subj_idx).strip()
                obj = match.group(obj_idx).strip()
                # 过滤太短或太长的实体
                if 1 < len(subj) <= 30 and 1 < len(obj) <= 30:
                    # 过滤纯标点/数字
                    if not subj.isdigit() and not obj.isdigit():
                        triples.append((subj, predicate, obj))
        return triples

    # ═══════════════════════════════════════════════════════════
    # 路径2: 会话共现
    # ═══════════════════════════════════════════════════════════

    def _build_session_cooccurrence_edges(
        self, memories: List[Any]
    ) -> List[Tuple[str, str]]:
        """同会话内出现的记忆对→关联边"""
        session_groups: Dict[str, List[str]] = defaultdict(list)

        for mem in memories:
            sid = getattr(mem, "session_id", "")
            content = getattr(mem, "content", str(mem))
            # 提取记忆的关键短语作为节点名
            node = self._extract_node_name(content)
            if sid and node:
                session_groups[sid].append(node)

        edges = []
        seen = set()
        for sid, nodes in session_groups.items():
            if len(nodes) < 2:
                continue
            for a, b in combinations(nodes[:10], 2):  # 每组最多 10 个节点
                key = (a, b) if a < b else (b, a)
                if key not in seen:
                    seen.add(key)
                    edges.append((a, b))
                    if len(edges) >= self.MAX_EDGES_PER_RUN:
                        return edges
        return edges

    # ═══════════════════════════════════════════════════════════
    # 路径3: 关键词重叠
    # ═══════════════════════════════════════════════════════════

    def _build_keyword_overlap_edges(
        self, memories: List[Any]
    ) -> List[Tuple[str, str]]:
        """基于 Jaccard 关键词相似度构建边"""
        # 提取每条记忆的关键词
        mem_keywords: List[Tuple[str, Set[str]]] = []
        for mem in memories:
            content = getattr(mem, "content", str(mem))
            node = self._extract_node_name(content)
            keywords = self._tokenize_keywords(content)
            if node and len(keywords) >= 2:
                mem_keywords.append((node, keywords))

        edges = []
        seen = set()
        for i in range(len(mem_keywords)):
            for j in range(i + 1, len(mem_keywords)):
                node_a, kws_a = mem_keywords[i]
                node_b, kws_b = mem_keywords[j]
                if node_a == node_b:
                    continue
                # Jaccard
                intersection = kws_a & kws_b
                union = kws_a | kws_b
                if not union:
                    continue
                jaccard = len(intersection) / len(union)
                if jaccard >= self.KEYWORD_SIMILARITY_THRESHOLD:
                    key = (node_a, node_b) if node_a < node_b else (node_b, node_a)
                    if key not in seen:
                        seen.add(key)
                        edges.append((node_a, node_b))

                if len(edges) >= self.MAX_EDGES_PER_RUN:
                    return edges
        return edges

    # ═══════════════════════════════════════════════════════════
    # 存储
    # ═══════════════════════════════════════════════════════════

    def _store_triples(self, triples: List[Tuple[str, str, str]]) -> int:
        """将三元组存入语义库，返回成功数量"""
        if self.semantic is None:
            return 0
        count = 0
        for subj, pred, obj in triples:
            try:
                if hasattr(self.semantic, "add"):
                    self.semantic.add(
                        subject=subj, predicate=pred, object_=obj,
                        confidence=0.5, source="auto_graph",
                    )
                else:
                    self.semantic.remember(
                        f"[自动图谱] {subj} {pred} {obj}",
                        {"source": "auto_graph", "subject": subj,
                         "predicate": pred, "object": obj},
                        importance=0.4,
                    )
                self._existing_triples.add((subj, pred, obj))
                count += 1
            except Exception:
                pass
        return count

    def _store_edges(self, edges: List[Tuple[str, str]], edge_type: str) -> int:
        """将边作为 RELATED_TO 三元组存入"""
        if self.semantic is None:
            return 0
        count = 0
        for a, b in edges:
            key = (a, "RELATED_TO", b)
            if key in self._existing_triples:
                continue
            try:
                if hasattr(self.semantic, "add"):
                    self.semantic.add(
                        subject=a, predicate="RELATED_TO", object_=b,
                        confidence=0.4, source=f"auto_graph:{edge_type}",
                    )
                else:
                    self.semantic.remember(
                        f"[自动边:{edge_type}] {a} ↔ {b}",
                        {"source": f"auto_graph:{edge_type}", "subject": a,
                         "predicate": "RELATED_TO", "object": b},
                        importance=0.3,
                    )
                self._existing_triples.add(key)
                count += 1
            except Exception:
                pass
        return count

    # ═══════════════════════════════════════════════════════════
    # 工具函数
    # ═══════════════════════════════════════════════════════════

    def _get_recent_memories(self, max_count: int) -> List[Any]:
        """获取近期情节记忆"""
        if self.episodic is None:
            return []
        try:
            return self.episodic.search("", top_k=max_count)
        except Exception:
            try:
                return self.episodic.list_all()[:max_count]
            except Exception:
                return []

    def _load_existing_triples(self):
        """加载已有三元组用于去重"""
        if self.semantic is None:
            return
        try:
            triples = self.semantic.get_all_triples()
            for t in triples:
                subj = t.get("subject", "")[:30]
                pred = t.get("predicate", "")[:30]
                obj = t.get("object", "")[:30]
                if subj and pred and obj:
                    self._existing_triples.add((subj, pred, obj))
        except Exception:
            pass

    def _extract_node_name(self, text: str) -> str:
        """从文本提取节点名（前20个有意义的字符）"""
        # 去除常见噪音前缀
        cleaned = re.sub(r"^\[[^\]]+\]\s*", "", text)
        # 提取第一个短语
        match = re.match(r"([^\s，,。；;：:！!\?？]{2,25})", cleaned)
        if match:
            return match.group(1).strip()
        return cleaned[:20].strip()

    def _tokenize_keywords(self, text: str) -> Set[str]:
        """从文本提取关键词集合（纯本地分词）"""
        # 简单 2-4 字片段作为关键词
        kw = set()
        text_clean = re.sub(r"[^一-鿿\w]", " ", text.lower())
        words = text_clean.split()
        for w in words:
            if 2 <= len(w) <= 8 and not w.isdigit():
                kw.add(w)
        return kw
