"""Markdown → 精美PDF转换器 — 使用pandoc转HTML + fpdf2渲染

用法:
    python scripts/md_to_pdf.py docs/SOMA-全面能力介绍.md
    python scripts/md_to_pdf.py docs/SOMA-Capability-Overview-EN.md
    python scripts/md_to_pdf.py docs/SOMA-全面能力介绍.md docs/SOMA-Capability-Overview-EN.md
"""

import os
import re
import subprocess
import sys
from pathlib import Path

from fpdf import FPDF

# ── 颜色方案 ──
CLR = {
    "h1": (25, 60, 120),
    "h2": (41, 128, 185),
    "h3": (30, 30, 30),
    "body": (60, 60, 60),
    "bold": (192, 57, 43),
    "table_head_bg": (41, 128, 185),
    "table_head_fg": (255, 255, 255),
    "table_border": (200, 200, 200),
    "table_row_alt": (245, 248, 252),
    "code_bg": (245, 245, 245),
    "hr": (200, 200, 200),
    "bullet": (41, 128, 185),
    "link": (65, 131, 196),
}

FONT_REG = "C:/Windows/Fonts/msyh.ttc"
FONT_BOLD = "C:/Windows/Fonts/msyhbd.ttc"


class MarkdownToPDF(FPDF):
    def __init__(self, title: str = ""):
        super().__init__("P", "mm", "A4")
        self.add_font("C", "", FONT_REG)
        self.add_font("C", "B", FONT_BOLD)
        self.set_auto_page_break(True, 18)
        self._title = title
        self._in_code = False

    # ── layout helpers ──

    def _para(self, text: str, size: int = 10, bold: bool = False,
              color: tuple = None, align: str = "L", indent: float = 0):
        self.set_font("C", "B" if bold else "", size)
        self.set_text_color(*(color or CLR["body"]))
        self.set_x(self.l_margin + indent)
        self.multi_cell(self.w - self.l_margin - self.r_margin - indent, size * 0.6 + 1, text, align=align)

    def _heading(self, text: str, level: int):
        sizes = {1: 18, 2: 14, 3: 11}
        colors = {1: CLR["h1"], 2: CLR["h2"], 3: CLR["h3"]}
        sz = sizes.get(level, 11)
        self.ln(4 if level == 1 else 2)
        self.set_font("C", "B", sz)
        self.set_text_color(*colors.get(level, CLR["body"]))
        self.multi_cell(0, sz * 0.55 + 2, text.strip(), align="L")
        if level <= 2:
            y = self.get_y()
            self.set_draw_color(*CLR["hr"])
            self.set_line_width(0.2 if level == 2 else 0.4)
            self.line(self.l_margin, y - 1, self.w - self.r_margin, y - 1)
            self.ln(3)

    def _hr(self):
        self.ln(2)
        self.set_draw_color(*CLR["hr"])
        self.set_line_width(0.3)
        y = self.get_y()
        self.line(self.l_margin, y, self.w - self.r_margin, y)
        self.ln(4)

    def _bullet(self, text: str):
        self.set_font("C", "B", 10)
        self.set_text_color(*CLR["bullet"])
        x0 = self.get_x()
        self.cell(6, 5.5, "•", align="C")
        self.set_font("C", "", 10)
        self.set_text_color(*CLR["body"])
        self.multi_cell(self.w - self.l_margin - self.r_margin - 6, 5.5, text)

    def _table(self, header: list, rows: list):
        """渲染表格。rows: list of list of str"""
        if not rows:
            return
        col_w = (self.w - self.l_margin - self.r_margin) / len(header)
        row_h = 7
        self.ln(2)

        # header
        self.set_fill_color(*CLR["table_head_bg"])
        self.set_text_color(*CLR["table_head_fg"])
        self.set_font("C", "B", 9)
        self.set_draw_color(*CLR["table_border"])
        for i, h in enumerate(header):
            self.cell(col_w, row_h, h, border=1, fill=True, align="C")
        self.ln()

        # rows
        self.set_font("C", "", 9)
        for ri, row in enumerate(rows):
            if ri % 2 == 1:
                self.set_fill_color(*CLR["table_row_alt"])
                fill = True
            else:
                fill = False
            self.set_text_color(*CLR["body"])
            for i, cell in enumerate(row):
                # scale font down if cell text is long
                txt = str(cell) if cell else ""
                cw = col_w - 2
                if len(txt) > 30:
                    self.set_font("C", "", 8)
                else:
                    self.set_font("C", "", 9)
                self.cell(col_w, row_h, txt[:80], border=1, fill=fill, align="C" if i > 0 else "L")
            self.ln()
        self.ln(2)


def parse_markdown_sections(html: str) -> list:
    """Parse markdown content into a list of blocks: (type, data)"""
    blocks = []
    lines = html.split("\n")

    i = 0
    while i < len(lines):
        line = lines[i]

        # skip empty
        if not line.strip():
            i += 1
            continue

        # headings
        m = re.match(r"^(#{1,3})\s+(.+?)(?:\s*\{.*\})?\s*$", line)
        if m:
            level = len(m.group(1))
            text = re.sub(r"<[^>]+>", "", m.group(2)).strip()
            blocks.append(("heading", (level, text)))
            i += 1
            continue

        # horizontal rule
        if re.match(r"^[-*_]{3,}\s*$", line):
            blocks.append(("hr", None))
            i += 1
            continue

        # table header
        m = re.match(r"^\|(.+)\|\s*$", line)
        if m and i + 1 < len(lines) and re.match(r"^\|[\s\-:|]+\|\s*$", lines[i + 1]):
            headers = [c.strip() for c in m.group(1).split("|")]
            headers = [h for h in headers if h]
            i += 2  # skip header + separator
            rows = []
            while i < len(lines):
                rm = re.match(r"^\|(.+)\|\s*$", lines[i])
                if not rm:
                    break
                cells = [c.strip() for c in rm.group(1).split("|")]
                cells = [c for c in cells if c or True]  # keep all
                # filter leading/trailing empty from split
                cells_clean = []
                for c in cells:
                    cells_clean.append(c.strip())
                # remove first/last empty from pipe split
                if cells_clean and cells_clean[0] == "":
                    cells_clean = cells_clean[1:]
                if cells_clean and cells_clean[-1] == "":
                    cells_clean = cells_clean[:-1]
                rows.append(cells_clean)
                i += 1
            blocks.append(("table", (headers, rows)))
            continue

        # code block
        if line.strip().startswith("```"):
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1  # skip closing ```
            blocks.append(("code", "\n".join(code_lines)))
            continue

        # bullet list item
        if re.match(r"^[-*]\s+", line.strip()):
            bullets = []
            while i < len(lines) and re.match(r"^[-*]\s+", lines[i].strip()):
                text = re.sub(r"^[-*]\s+", "", lines[i].strip())
                text = re.sub(r"<[^>]+>", "", text)
                bullets.append(text)
                i += 1
            blocks.append(("bullets", bullets))
            continue

        # numbered list
        if re.match(r"^\d+\.\s+", line.strip()):
            items = []
            while i < len(lines) and re.match(r"^\d+\.\s+", lines[i].strip()):
                text = re.sub(r"^\d+\.\s+", "", lines[i].strip())
                text = re.sub(r"<[^>]+>", "", text)
                items.append(text)
                i += 1
            blocks.append(("numbered", items))
            continue

        # regular paragraph (collect consecutive text lines)
        para_lines = []
        while i < len(lines) and lines[i].strip() and not re.match(r"^(#{1,3}\s|\||```|[-*]\s|\d+\.\s|[-*_]{3,})", lines[i]):
            para_lines.append(lines[i].strip())
            i += 1
        text = " ".join(para_lines)
        text = re.sub(r"<[^>]+>", "", text)
        if text.strip():
            blocks.append(("para", text))

    return blocks


def render_text_with_bold(pdf, text: str, size: int = 10, color: tuple = None, indent: float = 0):
    """Render a paragraph with **bold** inline spans"""
    parts = re.split(r"(\*\*(.+?)\*\*)", text)
    # parts: even indices = plain, odd indices (1,3,5,...) = full **...** match, odd+1 = content

    pdf.set_x(pdf.l_margin + indent)
    x_start = pdf.l_margin + indent
    max_w = pdf.w - pdf.l_margin - pdf.r_margin - indent
    x = x_start
    y = pdf.get_y()

    for idx, part in enumerate(parts):
        if not part:
            continue
        if idx % 2 == 1:
            # this is the full **text** match including markers → skip, content is at idx+1
            continue
        # check if previous part was a ** marker
        is_bold = (idx > 0 and parts[idx - 1].startswith("**"))

        pdf.set_font("C", "B" if is_bold else "", size)
        if is_bold:
            pdf.set_text_color(*CLR["bold"])
        else:
            pdf.set_text_color(*(color or CLR["body"]))

        # rough word-wrap
        words = part.split(" ")
        for wi, word in enumerate(words):
            word_w = pdf.get_string_width(word + (" " if wi < len(words) - 1 else ""))
            if x + word_w > x_start + max_w and x > x_start:
                pdf.set_xy(x_start, y)
                pdf.cell(0, size * 0.6 + 1, "", new_x="LMARGIN", new_y="NEXT")
                y = pdf.get_y()
                x = x_start
            pdf.set_xy(x, y)
            pdf.cell(word_w, size * 0.6 + 1, word + (" " if wi < len(words) - 1 else ""))
            x += word_w
        y = pdf.get_y()
        pdf.set_xy(x_start, y)
        pdf.cell(0, size * 0.6 + 1, "", new_x="LMARGIN", new_y="NEXT")


def generate_pdf(md_path: str):
    """Convert a markdown file to a beautiful PDF"""
    md_text = Path(md_path).read_text(encoding="utf-8")

    # extract title from first h1 or filename
    title_match = re.search(r"^#\s+(.+)$", md_text, re.MULTILINE)
    doc_title = title_match.group(1) if title_match else Path(md_path).stem

    pdf = MarkdownToPDF(doc_title)
    pdf.set_left_margin(22)
    pdf.set_right_margin(22)

    # Parse blocks from raw markdown (simpler than HTML parsing)
    blocks = parse_markdown_blocks(md_text)

    pdf.add_page()

    for block_type, data in blocks:
        if block_type == "heading":
            level, text = data
            pdf._heading(text, level)

        elif block_type == "hr":
            pdf._hr()

        elif block_type == "para":
            render_text_with_bold(pdf, data)

        elif block_type == "bullets":
            for b in data:
                # strip bold markers for bullet rendering
                clean = re.sub(r"\*\*", "", b)
                pdf._bullet(clean)

        elif block_type == "numbered":
            for ni, item in enumerate(data, 1):
                clean = re.sub(r"\*\*", "", item)
                pdf.set_font("C", "", 10)
                pdf.set_text_color(*CLR["body"])
                pdf.cell(8, 5.5, f"{ni}.", align="R")
                pdf.multi_cell(pdf.w - pdf.l_margin - pdf.r_margin - 8, 5.5, clean)

        elif block_type == "table":
            pdf._table(*data)

        elif block_type == "code":
            pdf.set_fill_color(*CLR["code_bg"])
            pdf.set_font("C", "", 8)
            pdf.set_text_color(100, 100, 100)
            for cl in data.split("\n")[:30]:  # limit code lines
                pdf.cell(0, 4.5, cl[:120], fill=True, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)

    # ── output ──
    out_path = str(Path(md_path).with_suffix(".pdf"))
    pdf.output(out_path)
    size_kb = os.path.getsize(out_path) / 1024
    print(f"  ✓ {Path(out_path).name} ({size_kb:.0f} KB)")


def parse_markdown_blocks(text: str) -> list:
    """Parse raw markdown text into blocks"""
    lines = text.split("\n")
    blocks = []
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        # heading
        m = re.match(r"^(#{1,3})\s+(.+)$", stripped)
        if m:
            blocks.append(("heading", (len(m.group(1)), m.group(2).strip())))
            i += 1
            continue

        # horizontal rule
        if re.match(r"^[-*_]{3,}\s*$", stripped):
            blocks.append(("hr", None))
            i += 1
            continue

        # table
        m = re.match(r"^\|(.+)\|\s*$", stripped)
        if m and i + 1 < len(lines) and re.match(r"^\|[\s\-:|]+\|\s*$", lines[i + 1].strip()):
            headers = [c.strip() for c in m.group(1).split("|")]
            headers = [h for h in headers if h]
            i += 2
            rows = []
            while i < len(lines):
                rm = re.match(r"^\|(.+)\|\s*$", lines[i].strip())
                if not rm:
                    break
                cells = [c.strip() for c in rm.group(1).split("|")]
                cells = [c for c in cells if c]
                rows.append(cells)
                i += 1
            blocks.append(("table", (headers, rows)))
            continue

        # code block
        if stripped.startswith("```"):
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1
            blocks.append(("code", "\n".join(code_lines)))
            continue

        # bullet list
        if re.match(r"^[-*]\s+", stripped):
            bullets = []
            while i < len(lines) and re.match(r"^[-*]\s+", lines[i].strip()):
                bullets.append(re.sub(r"^[-*]\s+", "", lines[i].strip()))
                i += 1
            blocks.append(("bullets", bullets))
            continue

        # numbered list
        if re.match(r"^\d+\.\s+", stripped):
            items = []
            while i < len(lines) and re.match(r"^\d+\.\s+", lines[i].strip()):
                items.append(re.sub(r"^\d+\.\s+", "", lines[i].strip()))
                i += 1
            blocks.append(("numbered", items))
            continue

        # paragraph
        para_lines = []
        while i < len(lines) and lines[i].strip() and not re.match(
            r"^(#{1,3}\s|\||```|[-*]\s|\d+\.\s|[-*_]{3,})", lines[i]
        ):
            para_lines.append(lines[i].strip())
            i += 1
        blocks.append(("para", " ".join(para_lines)))

    return blocks


# ═══════════════════════════════════

def main():
    if len(sys.argv) < 2:
        print("用法: python scripts/md_to_pdf.py <markdown文件> [更多文件...]")
        sys.exit(1)

    for path in sys.argv[1:]:
        if not os.path.exists(path):
            print(f"  ✗ 文件不存在: {path}")
            continue
        print(f"  处理: {path}")
        try:
            generate_pdf(path)
        except Exception as e:
            print(f"  ✗ 失败: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
