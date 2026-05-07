#!/usr/bin/env python3
"""Generate SOMA Open Graph social preview image (1200x630)."""
from PIL import Image, ImageDraw, ImageFont
import os

W, H = 1200, 630
OUT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _try_font(size, names):
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()

img = Image.new("RGB", (W, H), (13, 17, 23))  # dark bg
draw = ImageDraw.Draw(img)

# accent bar at top
draw.rectangle([0, 0, W, 8], fill=(99, 102, 241))  # indigo

# title
title_font = _try_font(48, ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/segoeui.ttf"])
draw.text((60, 100), "SOMA", fill=(255, 255, 255), font=title_font)

# subtitle
sub_font = _try_font(28, ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/segoeui.ttf"])
draw.text((60, 170), "Somatic Wisdom Architecture", fill=(148, 163, 184), font=sub_font)

# tagline
tag_font = _try_font(32, ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/segoeui.ttf"])
draw.text((60, 280), "Wisdom over Memory — 智慧超越记忆", fill=(99, 102, 241), font=tag_font)

# description
desc_font = _try_font(22, ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/segoeui.ttf"])
draw.text((60, 350), "Framework-First Cognitive Architecture for AI Agents", fill=(203, 213, 225), font=desc_font)

# features
features = [
    "▸  7 Thinking Laws reasoning network",
    "▸  Bidirectional memory activation (vector + keyword RRF)",
    "▸  Meta-evolution: self-optimizing weights",
    "▸  Consolidation + Active forgetting + External knowledge",
    "▸  342 tests · 100% semantic recall · 84.8 overall score",
]
feat_font = _try_font(20, ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/segoeui.ttf"])
y = 420
for feat in features:
    draw.text((60, y), feat, fill=(148, 163, 184), font=feat_font)
    y += 32

# bottom bar
draw.rectangle([0, H - 60, W, H], fill=(30, 41, 59))
url_font = _try_font(20, ["C:/Windows/Fonts/consola.ttf", "C:/Windows/Fonts/segoeui.ttf"])
draw.text((60, H - 44), "github.com/sunyan999999/soma    ·    pypi.org/project/soma-wisdom", fill=(148, 163, 184), font=url_font)

# horizontal rule
draw.line([(60, H - 68), (W - 60, H - 68)], fill=(71, 85, 105), width=1)

out_path = os.path.join(OUT_DIR, "docs", "images", "og-image.png")
img.save(out_path, "PNG")
print(f"OG image saved: {out_path}  ({os.path.getsize(out_path)} bytes)")
