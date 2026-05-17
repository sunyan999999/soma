"""Markdown → 精美HTML → 浏览器打印PDF

用法:
    python scripts/md_to_html.py docs/SOMA-全面能力介绍.md
    python scripts/md_to_html.py docs/SOMA-Capability-Overview-EN.md
"""

import os
import sys
from pathlib import Path

CSS = """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;700&display=swap');

  * { margin: 0; padding: 0; box-sizing: border-box; }

  body {
    font-family: "Noto Sans SC", "Microsoft YaHei", "Segoe UI", sans-serif;
    font-size: 14px;
    line-height: 1.8;
    color: #3a3a3a;
    max-width: 800px;
    margin: 0 auto;
    padding: 50px 40px;
    background: #fff;
  }

  h1 {
    font-size: 28px;
    color: #193c78;
    border-bottom: 3px solid #2980b9;
    padding-bottom: 12px;
    margin: 20px 0 16px;
  }

  h2 {
    font-size: 20px;
    color: #2980b9;
    margin: 32px 0 12px;
    padding-bottom: 6px;
    border-bottom: 1px solid #d5e8f6;
  }

  h3 {
    font-size: 16px;
    color: #2c3e50;
    margin: 24px 0 8px;
  }

  p { margin: 10px 0; }

  blockquote {
    border-left: 4px solid #2980b9;
    padding: 8px 16px;
    margin: 16px 0;
    background: #f0f6fb;
    color: #555;
    font-style: italic;
  }

  strong { color: #c0392b; }

  table {
    width: 100%;
    border-collapse: collapse;
    margin: 16px 0;
    font-size: 13px;
  }

  thead { background: #2980b9; color: #fff; }

  th {
    padding: 10px 12px;
    text-align: left;
    font-weight: 700;
  }

  td {
    padding: 8px 12px;
    border-bottom: 1px solid #e0e0e0;
  }

  tr:nth-child(even) td { background: #f5f8fc; }

  ul, ol { margin: 10px 0 10px 24px; }
  li { margin: 4px 0; }

  code {
    background: #f0f0f0;
    padding: 2px 6px;
    border-radius: 3px;
    font-family: "Cascadia Code", "Fira Code", "Consolas", monospace;
    font-size: 13px;
  }

  pre {
    background: #f7f7f7;
    padding: 16px;
    border-radius: 6px;
    overflow-x: auto;
    margin: 12px 0;
    border: 1px solid #e5e5e5;
  }

  pre code { background: none; padding: 0; }

  hr {
    border: none;
    border-top: 1px solid #ddd;
    margin: 28px 0;
  }

  a { color: #2980b9; text-decoration: none; }
  a:hover { text-decoration: underline; }

  @media print {
    body { padding: 20px 30px; font-size: 13px; }
    h1 { font-size: 24px; }
    h2 { font-size: 18px; }
    @page { margin: 1.5cm; }
  }
</style>
"""

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<title>{title}</title>
{CSS}
</head>
<body>
{body}
</body>
</html>
"""


def md_to_html(md_path: str) -> str:
    """Convert markdown to a self-contained HTML file"""
    import subprocess

    md_text = Path(md_path).read_text(encoding="utf-8")

    # Detect language
    lang = "zh-CN" if any("一" <= c <= "鿿" for c in md_text[:200]) else "en"

    # Use pandoc to convert markdown to HTML body
    result = subprocess.run(
        ["pandoc", md_path, "-f", "markdown", "-t", "html", "--no-highlight"],
        capture_output=True, text=True,
    )
    body_html = result.stdout

    # Extract title from first h1
    import re
    title_match = re.search(r"<h1[^>]*>(.+?)</h1>", body_html)
    title = title_match.group(1) if title_match else Path(md_path).stem

    html = HTML_TEMPLATE.format(
        lang=lang,
        title=title,
        CSS=CSS,
        body=body_html,
    )

    out_path = str(Path(md_path).with_suffix(".html"))
    Path(out_path).write_text(html, encoding="utf-8")
    return out_path


def main():
    if len(sys.argv) < 2:
        print("用法: python scripts/md_to_html.py <markdown文件> [更多...]")
        sys.exit(1)

    for path in sys.argv[1:]:
        if not os.path.exists(path):
            print(f"  ✗ 文件不存在: {path}")
            continue
        print(f"  处理: {path}")
        out = md_to_html(path)
        print(f"  ✓ {Path(out).name}")

    print(f"\n在浏览器中打开 HTML 文件，然后 Ctrl+P → 另存为 PDF 即可。")


if __name__ == "__main__":
    main()
