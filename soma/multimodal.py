"""多模态记忆 — 图片与表格的结构化记忆（v2.0.10）

在零外部依赖原则下，为图片/表格提供「结构化描述 + 引用」的记忆形式：
  - ImageMemory: 图片路径/引用 + 用户描述（可选 OCR，有库则增强）
  - TableMemory: 结构化数据 → 提取要点 → 记忆条目

设计原则：
  - 纯本地：OCR/视觉均为可选增强（检测到库才启用），基础功能零依赖
  - 复用现有记忆通道：remember() 存为文本记忆 + context 标记 memory_type
  - 与 remember_code 同模式：结构化数据 + 摘要 + 记忆条目
"""
import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ═══════════════════════════════════════════════════════════════
# 图片记忆
# ═══════════════════════════════════════════════════════════════

class ImageMemory:
    """图片记忆 — 存图片引用 + 结构化描述"""

    # 支持的图片扩展名
    SUPPORTED_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}

    def __init__(self, image_path: str = "", description: str = "",
                 use_ocr: bool = True):
        self.image_path = image_path
        self.description = description.strip()
        self._use_ocr = use_ocr

    def analyze(self) -> Dict[str, Any]:
        """分析图片，返回结构化元数据。

        - 基础：文件信息（路径/大小/扩展名）
        - OCR：可选，若安装了 pytesseract/PIL 且 use_ocr=True，提取文字
        """
        meta: Dict[str, Any] = {
            "content_type": "image",
            "image_path": self.image_path,
            "description": self.description,
        }

        if self.image_path and os.path.exists(self.image_path):
            meta["file_size_bytes"] = os.path.getsize(self.image_path)
            ext = os.path.splitext(self.image_path)[1].lower()
            meta["extension"] = ext

            if self._use_ocr and ext in self.SUPPORTED_EXTS:
                ocr_text = self._try_ocr(self.image_path)
                if ocr_text:
                    meta["ocr_text"] = ocr_text[:1000]

        return meta

    def _try_ocr(self, image_path: str) -> str:
        """可选 OCR 增强：检测到 pytesseract 才启用，失败静默返回空。"""
        try:
            from PIL import Image
            import pytesseract  # noqa: F401

            img = Image.open(image_path)
            return pytesseract.image_to_string(img, lang="chi_sim+eng").strip()
        except Exception:
            return ""

    def to_memory_content(self, meta: Dict[str, Any]) -> str:
        """构造记忆文本内容"""
        parts = []
        if self.description:
            parts.append(f"[图片] {self.description}")
        else:
            parts.append("[图片] 未提供描述")
        if meta.get("ocr_text"):
            parts.append(f"图片文字: {meta['ocr_text'][:200]}")
        if meta.get("image_path"):
            # 用 Markdown 引用，保留图片引用而非二进制
            parts.append(f"图片: {self.image_path}")
        return "\n".join(parts)


# ═══════════════════════════════════════════════════════════════
# 表格记忆
# ═══════════════════════════════════════════════════════════════

@dataclass
class TableMemory:
    """表格记忆 — 结构化数据提取要点"""

    title: str = ""
    data: List[Dict[str, Any]] = field(default_factory=list)
    # 可选：从 markdown 表格或 CSV 字符串解析
    markdown_table: str = ""
    csv_text: str = ""

    def __post_init__(self):
        # 支持从 markdown 或 CSV 解析
        if not self.data and self.markdown_table:
            self.data = self._parse_markdown_table(self.markdown_table)
        elif not self.data and self.csv_text:
            self.data = self._parse_csv(self.csv_text)

    def analyze(self) -> Dict[str, Any]:
        """提取表格结构化信息"""
        rows = self.data
        if not rows:
            return {
                "content_type": "table",
                "title": self.title,
                "row_count": 0,
                "columns": [],
                "summary": "空表格",
            }

        # 列名
        first = rows[0]
        columns = list(first.keys()) if isinstance(first, dict) else []
        # 汇总：每列的非空值数量（反映数据密度）
        column_stats = {}
        for col in columns:
            vals = [str(r.get(col, "")) for r in rows if isinstance(r, dict)]
            non_empty = sum(1 for v in vals if v.strip())
            column_stats[col] = {
                "non_empty": non_empty,
                "total": len(rows),
            }

        return {
            "content_type": "table",
            "title": self.title,
            "row_count": len(rows),
            "columns": columns,
            "column_stats": column_stats,
            "summary": self._summarize(rows, columns),
        }

    def to_memory_content(self, meta: Dict[str, Any]) -> str:
        """构造记忆文本内容"""
        parts = [f"[表格] {self.title or '未命名表格'}"]
        parts.append(f"行数: {meta['row_count']}, 列: {', '.join(meta['columns'])}")
        if meta.get("summary"):
            parts.append(f"内容: {meta['summary']}")
        return "\n".join(parts)

    @staticmethod
    def _parse_markdown_table(md: str) -> List[Dict[str, Any]]:
        """解析 markdown 表格为 dict 列表"""
        lines = [l.strip() for l in md.strip().splitlines() if l.strip()]
        if not lines:
            return []
        header = [c.strip() for c in lines[0].strip("|").split("|")]
        # 跳过分隔行（|---|）
        data_lines = [l for l in lines[1:] if not set(l.replace("|", "").replace("-", "").replace(":", "")).issubset({""})]
        rows = []
        for line in data_lines:
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) == len(header):
                rows.append(dict(zip(header, cells)))
        return rows

    @staticmethod
    def _parse_csv(csv_text: str) -> List[Dict[str, Any]]:
        """解析 CSV 字符串为 dict 列表"""
        import csv
        import io

        reader = csv.DictReader(io.StringIO(csv_text))
        return list(reader)

    def _summarize(self, rows: List[Dict], columns: List[str]) -> str:
        """生成简短摘要（取前几行的关键字段）"""
        if not columns:
            return ""
        summary_rows = []
        for r in rows[:3]:
            if isinstance(r, dict):
                cells = [f"{k}:{str(r.get(k, ''))[:20]}" for k in columns[:4]]
                summary_rows.append("；".join(cells))
        return " / ".join(summary_rows)[:300]
