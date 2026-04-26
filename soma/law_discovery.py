"""新规律自主归纳 — 从高关联记忆聚类中发现候选思维规律

基于 DBSCAN 聚类 + TF-IDF 关键词提取 + LLM 审核提示。
"""

import math
import time
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from soma.base import MemoryUnit


class LawDiscovery:
    """从记忆聚类中自动发现新的思维规律。

    使用方式::

        discovery = LawDiscovery(memory_core, embedder, llm_model="deepseek-chat")
        candidate = discovery.discover()
        if candidate:
            # 展示给开发者审核
            approved = discovery.approve(candidate)
    """

    # 安全限制
    MAX_TOTAL_LAWS = 15          # 框架内规律总数上限
    MAX_CANDIDATES_PER_RUN = 1   # 单次最多生成 1 条候选
    MIN_CLUSTER_SIZE = 5         # 聚类最小记忆数
    MIN_IMPORTANCE = 0.5         # 参与聚类的记忆最低重要性
    MIN_ACCESS_COUNT = 2         # 参与聚类的记忆最低访问次数

    def __init__(self, memory_core, embedder, llm_model: Optional[str] = None):
        """
        Args:
            memory_core: MemoryCore 实例
            embedder: SOMAEmbedder 实例
            llm_model: LiteLLM 模型名，为 None 则使用启发式生成
        """
        self._memory = memory_core
        self._embedder = embedder
        self._llm_model = llm_model

    # ── 主流程 ────────────────────────────────────────────────

    def discover(self, current_law_count: int = 7) -> Optional[Dict[str, Any]]:
        """从记忆中尝试发现一条候选新规律。

        返回 None 表示无符合条件的聚类。
        返回 dict 包含候选规律的 name/description/triggers/confidence。
        """
        if current_law_count >= self.MAX_TOTAL_LAWS:
            return None

        # 1. 获取候选记忆
        memories = self._get_candidate_memories()
        if len(memories) < self.MIN_CLUSTER_SIZE:
            return None

        # 2. 嵌入
        texts = [m.content for m in memories]
        vectors = self._embedder.encode_batch(texts)

        # 3. 聚类
        clusters = self._cluster(vectors, memories)
        if not clusters:
            return None

        # 4. 选择最佳聚类并提取关键词
        best_cluster = self._select_best_cluster(clusters)
        keywords = self._extract_keywords(best_cluster)

        # 5. 生成候选规律
        candidate = self._generate_law(best_cluster, keywords)
        candidate["confidence"] = self._compute_confidence(best_cluster)

        return candidate

    def approve(self, candidate: Dict[str, Any], engine) -> bool:
        """将候选规律添加到思维框架。返回是否成功。"""
        from soma.config import WisdomLaw

        law = WisdomLaw(
            id=candidate["id"],
            name=candidate["name"],
            description=candidate["description"],
            weight=0.60,  # 新规律的起始权重设为中等
            triggers=candidate["triggers"],
            relations=candidate.get("relations", []),
        )
        engine.laws.append(law)
        engine.laws.sort(key=lambda l: l.weight, reverse=True)
        return True

    # ── 内部步骤 ──────────────────────────────────────────────

    def _get_candidate_memories(self) -> List[MemoryUnit]:
        """获取高重要性、高访问频次的记忆"""
        all_memories = self._memory.episodic.query_by_keywords([], top_k=500)
        candidates = [
            m for m in all_memories
            if m.importance >= self.MIN_IMPORTANCE
            and m.access_count >= self.MIN_ACCESS_COUNT
        ]
        return candidates

    def _cluster(
        self, vectors: np.ndarray, memories: List[MemoryUnit]
    ) -> List[Dict[str, Any]]:
        """对向量进行 DBSCAN 聚类，返回聚类列表"""
        from sklearn.cluster import DBSCAN

        if len(vectors) < self.MIN_CLUSTER_SIZE:
            return []

        # 归一化
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1.0, norms)
        normalized = vectors / norms

        # DBSCAN 聚类
        eps = 0.3  # 余弦距离阈值
        clustering = DBSCAN(eps=eps, min_samples=3, metric="cosine").fit(normalized)

        labels = clustering.labels_
        clusters: Dict[int, List[MemoryUnit]] = {}
        for i, label in enumerate(labels):
            if label == -1:  # 噪声点
                continue
            clusters.setdefault(label, []).append(memories[i])

        # 过滤掉太小的聚类
        result = []
        for label, mems in clusters.items():
            if len(mems) >= self.MIN_CLUSTER_SIZE:
                result.append({
                    "label": label,
                    "memories": mems,
                    "size": len(mems),
                })
        return result

    def _select_best_cluster(self, clusters: List[Dict]) -> Dict:
        """选择最佳聚类：大小 × 平均重要性的乘积最大"""
        best = None
        best_score = -1.0
        for c in clusters:
            avg_imp = np.mean([m.importance for m in c["memories"]])
            score = c["size"] * avg_imp
            if score > best_score:
                best_score = score
                best = c
        return best

    def _extract_keywords(self, cluster: Dict) -> List[str]:
        """从聚类记忆中提取关键词（TF-IDF + 词频混合）"""
        from sklearn.feature_extraction.text import TfidfVectorizer

        texts = [m.content for m in cluster["memories"]]
        if len(texts) < 2:
            return _simple_keyword_extract(texts[0] if texts else "")

        try:
            vectorizer = TfidfVectorizer(max_features=20, stop_words=None)
            vectorizer.fit_transform(texts)
            # 按 TF-IDF 均值排序取 top 12
            feature_names = vectorizer.get_feature_names_out()
            scores = vectorizer.idf_
            indexed = sorted(
                enumerate(scores),
                key=lambda x: x[1],
                reverse=True,
            )
            keywords = [feature_names[i] for i, _ in indexed[:12]]
            return keywords
        except Exception:
            combined = " ".join(texts)
            return _simple_keyword_extract(combined)

    def _generate_law(
        self, cluster: Dict, keywords: List[str]
    ) -> Dict[str, Any]:
        """生成候选规律。有 LLM 则用 LLM 审核，否则启发式生成。"""
        # 提取领域信息
        domains = Counter()
        for m in cluster["memories"]:
            domain = m.context.get("domain", "通用")
            domains[domain] += 1
        top_domain = domains.most_common(1)[0][0] if domains else "通用"

        # 提取记忆片段摘要
        snippets = [m.content[:200] for m in cluster["memories"][:5]]

        if self._llm_model:
            return self._llm_generate_law(snippets, keywords, top_domain)
        return self._heuristic_generate_law(snippets, keywords, top_domain)

    def _llm_generate_law(
        self, snippets: List[str], keywords: List[str], domain: str
    ) -> Dict[str, Any]:
        """通过 LLM 审核生成规律"""
        from litellm import completion

        prompt = f"""你是一位认知科学专家。分析以下高关联记忆聚类，提取其中隐含的思维规律。

## 聚类领域
{domain}

## 关键主题词
{', '.join(keywords[:10])}

## 记忆片段
{chr(10).join(f'{i+1}. {s}' for i, s in enumerate(snippets))}

## 任务
从以上记忆中归纳出一条新的思维规律。输出 JSON 格式：

```json
{{
  "id": "规律ID（英文 snake_case）",
  "name": "规律名称（中文，4-6字）",
  "description": "规律描述（一句话说明这个思维规律的核心思想）",
  "triggers": ["触发词1", "触发词2", ..., "触发词10"],
  "relations": ["关联的已有规律ID"]
}}
```

注意：
- id 必须唯一，不要使用 first_principles/systems_thinking/contradiction_analysis/pareto_principle/inversion/analogical_reasoning/evolutionary_lens
- description 体现此聚类中记忆共性的核心思维模式
- triggers 提取10个最能激活此规律的关键词
- relations 从已有规律中选择1-2个最相关的"""

        try:
            response = completion(
                model=self._llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
            )
            text = response.choices[0].message.content
            # 提取 JSON
            import re
            json_match = re.search(r'\{[\s\S]*\}', text)
            if json_match:
                import json
                return json.loads(json_match.group())
        except Exception:
            pass

        return self._heuristic_generate_law(snippets, keywords, domain)

    def _heuristic_generate_law(
        self, snippets: List[str], keywords: List[str], domain: str
    ) -> Dict[str, Any]:
        """启发式生成候选规律（无需 LLM）"""
        import uuid

        # 用前两个最显著的关键词构建名称
        name_keywords = keywords[:3] if len(keywords) >= 3 else keywords
        law_name = f"{domain}·{'·'.join(name_keywords[:2])}思维"

        return {
            "id": f"discovered_{uuid.uuid4().hex[:8]}",
            "name": law_name[:12],
            "description": f"从{domain}领域的{len(snippets)}条高关联记忆中归纳的思维模式，"
                          f"聚焦于{'、'.join(keywords[:4])}等关键要素的内在联系。",
            "triggers": keywords[:10],
            "relations": [],
        }

    def _compute_confidence(self, cluster: Dict) -> float:
        """计算候选规律的置信度（0-1）"""
        size_score = min(cluster["size"] / (self.MIN_CLUSTER_SIZE * 3), 1.0)
        avg_imp = np.mean([m.importance for m in cluster["memories"]])
        imp_score = (avg_imp - self.MIN_IMPORTANCE) / (1.0 - self.MIN_IMPORTANCE)
        return round(0.5 * size_score + 0.5 * max(imp_score, 0), 3)


def _simple_keyword_extract(text: str, top_k: int = 12) -> List[str]:
    """简单关键词提取（无 sklearn 时兜底）"""
    import re

    # 中文：按常见停用词切分
    stop_chars = set("，。！？；：、（）""''【】《》的了吗是在有和就不人都一很到说要去看好")
    # 英文：取长度 >= 3 的词
    words = re.findall(r'[一-鿿]{2,}|[a-zA-Z]{3,}', text)
    filtered = [w for w in words if w not in stop_chars]
    counter = Counter(filtered)
    return [w for w, _ in counter.most_common(top_k)]
