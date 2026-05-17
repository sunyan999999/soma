"""用Playwright将HTML渲染为PDF"""
import os
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright


def render(html_path: str, pdf_path: str):
    abs_html = Path(html_path).resolve().as_uri()
    abs_pdf = str(Path(pdf_path).resolve())

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(abs_html, wait_until="networkidle")
        page.pdf(
            path=abs_pdf,
            format="A4",
            margin={"top": "15mm", "bottom": "15mm", "left": "12mm", "right": "12mm"},
            print_background=True,
        )
        browser.close()

    size_kb = os.path.getsize(abs_pdf) / 1024
    print(f"  ✓ {Path(pdf_path).name} ({size_kb:.0f} KB)")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: python scripts/render_pdf.py <input.html> <output.pdf>")
        sys.exit(1)
    render(sys.argv[1], sys.argv[2])
