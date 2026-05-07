"""记忆摘要合并引擎 — 相似记忆自动归并，减少冗余

设计参考：
- Mem0 的 ADD/UPDATE/DELETE/NOOP 四操作分类（LLM判决）
- Letta 的 Memory Blocks 自编辑机制
- SleepGate 的周期性合并扫描（而非实时检查）

SOMA 方案：新记忆插入时做轻量相似检测，evolve() 时做深度合并扫描。
"""
import json
import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

_log = logging.getLogger("soma.memory.consolidation")


class ConsolidationEngine:
    """记忆合并引擎 — 检测并合并冗余记忆"""

    def __init__(self, conn, embedder=None, similarity_threshold: float = 0.85):
        self._conn = conn
        self._embedder = embedder
        self._threshold = similarity_threshold
        self._ensure_tables()

    def _ensure_tables(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS memory_merges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                primary_id TEXT NOT NULL,
                secondary_id TEXT NOT NULL,
                merged_content TEXT NOT NULL,
                primary_importance REAL,
                secondary_importance REAL,
                similarity_score REAL,
                timestamp REAL NOT NULL,
                user_id TEXT NOT NULL DEFAULT ''
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_merges_user ON memory_merges(user_id)"
        )
        self._conn.commit()

    def find_similar(
        self, content: str, user_id: str = "", top_k: int = 5
    ) -> List[Tuple[str, float]]:
        """查找与给定内容相似的已有记忆。

        两阶段检测：
        1. FTS5 关键词粗筛（快速，候选池）
        2. Embedding 余弦相似度精排（精确）

        Returns:
            [(memory_id, similarity_score), ...] 按相似度降序
        """
        # Phase 1: FTS5 关键词粗筛
        import jieba
        keywords = list(jieba.cut(content))[:20]
        keyword_filter = " OR ".join(f'"{kw}"' for kw in keywords if len(kw) >= 2)
        if not keyword_filter:
            return []

        try:
            rows = self._conn.execute(
                f"""
                SELECT m.id, m.content, m.importance
                FROM episodic_memories m
                JOIN episodic_fts f ON m.rowid = f.rowid
                WHERE episodic_fts MATCH ?
                  AND m.user_id = ?
                LIMIT {top_k * 5}
                """,
                (keyword_filter, user_id),
            ).fetchall()
        except Exception:
            return []

        if not rows or self._embedder is None:
            return []

        # Phase 2: Embedding 余弦相似度精排
        try:
            query_vec = self._embedder.encode(content)
        except Exception:
            return []

        candidates = []
        for row in rows:
            try:
                cand_vec = self._embedder.encode(row["content"])
                sim = _cosine_similarity(query_vec, cand_vec)
                if sim >= self._threshold:
                    candidates.append((row["id"], sim, row["importance"]))
            except Exception:
                continue

        candidates.sort(key=lambda x: x[1], reverse=True)
        return [(cid, sim) for cid, sim, _ in candidates[:top_k]]

    def merge(self, primary_id: str, secondary_id: str, user_id: str = "") -> Optional[str]:
        """合并两条相似记忆。

        策略：
        - 保留重要性高的为主体
        - 重要性低的独特信息追加为"补充："段
        - 合并后重新计算重要性（max + 0.1 奖励）
        - 低重要性记忆标记为待归档
        """
        primary = self._conn.execute(
            "SELECT content, importance, context_json FROM episodic_memories WHERE id = ?",
            (primary_id,),
        ).fetchone()
        secondary = self._conn.execute(
            "SELECT content, importance, context_json FROM episodic_memories WHERE id = ?",
            (secondary_id,),
        ).fetchone()
        if not primary or not secondary:
            return None

        p_content = primary["content"]
        s_content = secondary["content"]
        p_importance = primary["importance"]
        s_importance = secondary["importance"]

        # 确保 primary 是重要性高的（否则交换）
        if s_importance > p_importance:
            primary_id, secondary_id = secondary_id, primary_id
            p_content, s_content = s_content, p_content
            p_importance, s_importance = s_importance, p_importance

        # 提取低重要性记忆中不重复的信息
        unique_info = _extract_unique_info(p_content, s_content)
        if unique_info:
            merged_content = f"{p_content}\n补充：{unique_info}"
        else:
            merged_content = p_content

        merged_importance = min(p_importance + 0.1, 1.0)  # 合并奖励

        # 更新主体记忆
        similarity = _text_overlap(p_content, s_content)
        now = datetime.now(timezone.utc).timestamp()
        self._conn.execute(
            "UPDATE episodic_memories SET content = ?, importance = ? WHERE id = ?",
            (merged_content, merged_importance, primary_id),
        )

        # 标记次要记忆为待归档（14天宽限期后自动删除）
        self._conn.execute(
            "UPDATE episodic_memories SET importance = -0.1 WHERE id = ?",
            (secondary_id,),
        )

        # 记录合并日志
        self._conn.execute(
            """INSERT INTO memory_merges
               (primary_id, secondary_id, merged_content, primary_importance,
                secondary_importance, similarity_score, timestamp, user_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (primary_id, secondary_id, merged_content, p_importance,
             s_importance, similarity, now, user_id),
        )
        self._conn.commit()

        _log.info("记忆合并: %s ← %s (相似度=%.3f)", primary_id[:8], secondary_id[:8], similarity)
        return primary_id

    def run_consolidation_pass(self, user_id: str = "", max_merges: int = 10) -> int:
        """执行一次合并扫描（由 evolve() 触发）。

        扫描所有高相似度记忆对，合并前 max_merges 对。
        """
        import jieba

        # 获取最近30天、未归档的所有记忆
        cutoff = datetime.now(timezone.utc).timestamp() - 30 * 86400
        rows = self._conn.execute(
            """SELECT id, content, importance FROM episodic_memories
               WHERE timestamp > ? AND importance > 0 AND user_id = ?
               ORDER BY importance DESC LIMIT 500""",
            (cutoff, user_id),
        ).fetchall()

        if len(rows) < 2:
            return 0

        merges_done = 0
        seen = set()

        for i in range(len(rows)):
            if merges_done >= max_merges:
                break
            if rows[i]["id"] in seen:
                continue

            for j in range(i + 1, len(rows)):
                if merges_done >= max_merges:
                    break
                if rows[j]["id"] in seen:
                    continue

                overlap = _text_overlap(rows[i]["content"], rows[j]["content"])
                if overlap >= self._threshold:
                    merged_id = self.merge(rows[i]["id"], rows[j]["id"], user_id)
                    if merged_id:
                        seen.add(rows[i]["id"])
                        seen.add(rows[j]["id"])
                        merges_done += 1

        return merges_done

    def stats(self, user_id: str = "") -> Dict:
        """合并统计"""
        if user_id:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM memory_merges WHERE user_id = ?", (user_id,)
            ).fetchone()
        else:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM memory_merges"
            ).fetchone()
        return {"total_merges": row[0] if row else 0}


def _cosine_similarity(a, b) -> float:
    import numpy as np
    a, b = np.asarray(a), np.asarray(b)
    norm_a, norm_b = np.linalg.norm(a), np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def _text_overlap(text_a: str, text_b: str) -> float:
    """计算两段文本的Jaccard词重叠度（使用jieba中文分词）"""
    import jieba
    tokens_a = set(w for w in jieba.cut(text_a) if len(w.strip()) >= 1)
    tokens_b = set(w for w in jieba.cut(text_b) if len(w.strip()) >= 1)
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


def _extract_unique_info(primary: str, secondary: str) -> str:
    """从次要记忆提取主要记忆中没有的独特句子"""
    import re
    import jieba
    primary_tokens = set(w for w in jieba.cut(primary) if len(w.strip()) >= 1)
    sec_sentences = re.split(r'[。！？；\n]', secondary)
    unique_parts = []
    for sent in sec_sentences:
        sent = sent.strip()
        if not sent:
            continue
        tokens = set(w for w in jieba.cut(sent) if len(w.strip()) >= 1)
        if tokens and len(tokens - primary_tokens) / len(tokens) > 0.3:
            unique_parts.append(sent)
    return "；".join(unique_parts[:3])  # 最多保留3个独特句子
