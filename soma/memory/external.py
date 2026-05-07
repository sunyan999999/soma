"""外部知识集成 — 多源知识接入，与内部记忆混合检索

设计参考：
- Mem0 add_document(): 从文本提取事实作为独立记忆
- RAG 标准模式: chunk → embed → store → retrieve
- Letta: 外部文件作为记忆块，LLM自主管理

SOMA 方案：KnowledgeSource 抽象接口 + FileSource/URLSource 首批实现。
外部知识以 memory_type="external" 存入，混合检索时内部记忆权重略高。
"""
import logging
import re
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

_log = logging.getLogger("soma.memory.external")


class KnowledgeSource(ABC):
    """外部知识源抽象基类"""

    @abstractmethod
    def name(self) -> str:
        """知识源名称"""

    @abstractmethod
    def extract(self) -> List[Dict]:
        """提取知识单元。

        Returns:
            [{"content": "文本", "context": {...}}, ...]
        """

    @property
    def default_importance(self) -> float:
        return 0.6

    @property
    def default_expiry_days(self) -> int:
        return 30


class FileSource(KnowledgeSource):
    """文件知识源 — 支持 .md / .txt / .json"""

    SUPPORTED_SUFFIXES = {".md", ".txt", ".json", ".jsonl", ".yaml", ".yml"}

    def __init__(self, file_path: str, chunk_size: int = 500):
        self._path = Path(file_path)
        self._chunk_size = chunk_size
        if not self._path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")
        if self._path.suffix not in self.SUPPORTED_SUFFIXES:
            raise ValueError(
                f"不支持的文件类型: {self._path.suffix}，支持: {self.SUPPORTED_SUFFIXES}"
            )

    def name(self) -> str:
        return f"文件:{self._path.name}"

    def extract(self) -> List[Dict]:
        content = self._path.read_text(encoding="utf-8")
        suffix = self._path.suffix.lower()

        if suffix == ".json":
            return self._extract_json(content)
        elif suffix == ".jsonl":
            return self._extract_jsonl(content)
        else:
            return self._extract_text(content)

    def _extract_text(self, content: str) -> List[Dict]:
        """分块长文本，保持段落边界"""
        paragraphs = re.split(r'\n\n+', content)
        chunks = []
        current = ""
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            if len(current) + len(para) > self._chunk_size and current:
                chunks.append(current)
                current = para
            else:
                current = f"{current}\n\n{para}" if current else para
        if current:
            chunks.append(current)

        return [
            {
                "content": chunk,
                "context": {"source": str(self._path), "chunk_index": i},
            }
            for i, chunk in enumerate(chunks)
        ]

    def _extract_json(self, content: str) -> List[Dict]:
        import json
        data = json.loads(content)
        if isinstance(data, list):
            return [
                {
                    "content": item.get("text") or item.get("content") or json.dumps(item, ensure_ascii=False),
                    "context": {"source": str(self._path), "index": i},
                }
                for i, item in enumerate(data) if item
            ]
        else:
            return [
                {
                    "content": json.dumps(item, ensure_ascii=False),
                    "context": {"source": str(self._path), "key": k},
                }
                for k, item in data.items() if item
            ]

    def _extract_jsonl(self, content: str) -> List[Dict]:
        import json
        results = []
        for i, line in enumerate(content.strip().split("\n")):
            try:
                obj = json.loads(line.strip())
                text = obj.get("text") or obj.get("content") or json.dumps(obj, ensure_ascii=False)
                results.append({
                    "content": text,
                    "context": {"source": str(self._path), "line": i + 1},
                })
            except json.JSONDecodeError:
                continue
        return results


class URLSource(KnowledgeSource):
    """URL 知识源 — 抓取网页文本导入"""

    def __init__(self, url: str, max_length: int = 5000):
        self._url = url
        self._max_length = max_length
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"不支持的URL协议: {parsed.scheme}")

    def name(self) -> str:
        return f"URL:{urlparse(self._url).netloc}"

    def extract(self) -> List[Dict]:
        import urllib.request
        import urllib.error

        try:
            req = urllib.request.Request(
                self._url,
                headers={"User-Agent": "SOMA-ExternalKnowledge/0.7"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                content = resp.read().decode("utf-8", errors="replace")
        except urllib.error.URLError as e:
            _log.warning("URL知识源抓取失败: %s — %s", self._url, e)
            return []

        # 简单 HTML 文本提取（去除标签）
        text = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()

        if len(text) > self._max_length:
            text = text[:self._max_length] + "..."

        return [{
            "content": text,
            "context": {"source": self._url},
        }]


class ExternalKnowledgeImporter:
    """外部知识导入器 — 将知识源内容存入 EpisodicStore"""

    def __init__(self, episodic_store):
        self._store = episodic_store

    def import_source(
        self, source: KnowledgeSource, user_id: str = "", session_id: str = ""
    ) -> List[str]:
        """导入知识源的所有知识单元"""
        memory_ids = []
        items = source.extract()
        for item in items:
            ctx = item.get("context", {})
            ctx["_external"] = True
            ctx["_source_name"] = source.name()
            ctx["_expires_in_days"] = source.default_expiry_days

            mid = self._store.add(
                content=item["content"],
                context=ctx,
                importance=source.default_importance,
                user_id=user_id,
                session_id=session_id,
            )
            if mid:
                memory_ids.append(mid)

        # 标记为 external 类型
        for mid in memory_ids:
            try:
                self._store._conn.execute(
                    "UPDATE episodic_memories SET memory_type = 'external' WHERE id = ?",
                    (mid,),
                )
            except Exception:
                pass
        if self._store._conn:
            self._store._conn.commit()

        _log.info(
            "外部知识导入: %s → %d 条记忆", source.name(), len(memory_ids)
        )
        return memory_ids

    def check_expired(self, user_id: str = "") -> int:
        """检查并标记过期外部知识（超过 expiry 天数的降至 importance=0）"""
        now = datetime.now(timezone.utc).timestamp()
        expired_count = 0

        rows = self._store._conn.execute(
            """SELECT id, timestamp, context_json FROM episodic_memories
               WHERE memory_type = 'external' AND importance > 0 AND user_id = ?""",
            (user_id,),
        ).fetchall()

        for row in rows:
            import json
            ctx = json.loads(row["context_json"] or "{}")
            expires_in = ctx.get("_expires_in_days", 30)
            age_days = (now - row["timestamp"]) / 86400.0
            if age_days > expires_in:
                self._store._conn.execute(
                    "UPDATE episodic_memories SET importance = 0 WHERE id = ?",
                    (row["id"],),
                )
                expired_count += 1

        if expired_count:
            self._store._conn.commit()
            _log.info("外部知识过期: %d 条", expired_count)
        return expired_count
