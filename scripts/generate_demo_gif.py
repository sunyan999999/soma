"""
Generate SOMA pipeline demo GIF — terminal-style animated showcase.
Uses Pillow + imageio, no external recording tools needed.
"""
import io
import textwrap
from pathlib import Path
import imageio
from PIL import Image, ImageDraw, ImageFont

# ── config ──────────────────────────────────────────────
W, H = 800, 520
BG = (26, 27, 38)        # dark terminal bg
FG = (192, 202, 245)     # light text
DIM = (86, 95, 137)      # dim text
ACCENT = (127, 207, 250) # cyan accent
GREEN = (158, 206, 106)  # green
YELLOW = (224, 175, 104) # yellow
RED = (247, 118, 142)    # red
PURPLE = (158, 126, 221) # purple
ORANGE = (255, 158, 100) # orange
FPS = 2
FONT_PATH = None

# try to find a monospace font
for candidate in [
    "C:/Windows/Fonts/consola.ttf",
    "C:/Windows/Fonts/Cour.ttf",
    "C:/Windows/Fonts/lucon.ttf",
    "C:/Windows/Fonts/msgothic.ttf",
]:
    if Path(candidate).exists():
        FONT_PATH = candidate
        break


def make_frame(lines, highlight=None, delay=1.0):
    """Render a terminal-style frame with colored text lines."""
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # title bar
    draw.rectangle([(0, 0), (W, 28)], fill=(14, 14, 24))
    try:
        font_sm = ImageFont.truetype(FONT_PATH, 13) if FONT_PATH else ImageFont.load_default()
        font_md = ImageFont.truetype(FONT_PATH, 15) if FONT_PATH else ImageFont.load_default()
        font_lg = ImageFont.truetype(FONT_PATH, 18) if FONT_PATH else ImageFont.load_default()
    except Exception:
        font_sm = font_md = font_lg = ImageFont.load_default()

    draw.text((12, 5), "SOMA  —  Wisdom Pipeline Demo", fill=DIM, font=font_sm)

    y = 42
    for line_info in lines:
        if isinstance(line_info, str):
            text, color = line_info, FG
        else:
            text, color = line_info

        # truncate long lines
        if len(text) > 100:
            text = text[:97] + "..."

        draw.text((24, y), text, fill=color, font=font_md)
        y += 24

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return imageio.v3.imread(buf)


def build_gif(output_path: str):
    frames = []

    # ── Frame 1: Problem input ──
    frames.append(make_frame([
        ("", FG),
        ("╭──────────────────────────────────────────────╮", DIM),
        ("│  🧠 SOMA Wisdom Pipeline                      │", ACCENT),
        ("╰──────────────────────────────────────────────╯", DIM),
        ("", FG),
        ("  >>>", ACCENT),
        ("", FG),
        ("  User asks:", DIM),
        ('  "如何突破我们产品的增长瓶颈？"', FG),
        ("", FG),
        ("  [等待 SOMA 拆解问题...]", DIM),
        ("", FG),
        ("  ⏳ decompose → activate → synthesize → evolve", DIM),
    ]))

    # ── Frame 2: Decomposition ──
    frames.append(make_frame([
        ("", FG),
        ("  ═══ STAGE 1: DECOMPOSE (问题拆解) ═══", ACCENT),
        ("", FG),
        ("  识别到 5 个思维维度:", GREEN),
        ("", FG),
        ("  📌 第一性原理  ·  增长 = f(获客,转化,留存,传播)", PURPLE),
        ("  📌 二八法则    ·  哪个 20% 渠道贡献 80% 增长?", YELLOW),
        ("  📌 系统思维    ·  获客↑ 但留存↓ → 漏桶效应", ORANGE),
        ("  📌 逆向思考    ·  如果增长停滞,最可能哪里先断裂?", RED),
        ("  📌 类比推理    ·  参考 Dropbox 推荐裂变模式", GREEN),
        ("", FG),
        ("  ✓ 拆解完成, 激活权重: [0.90, 0.85, 0.80, 0.75, 0.70]", GREEN),
    ]))

    # ── Frame 3: Memory Activation ──
    frames.append(make_frame([
        ("", FG),
        ("  ═══ STAGE 2: ACTIVATE (记忆激活) ═══", YELLOW),
        ("", FG),
        ("  🔍 检索跨会话记忆 (hybrid RRF)...", DIM),
        ("", FG),
        ("  唤起 7 条相关记忆:", GREEN),
        ("", FG),
        ('  ▸ "获客成本从 $12 降到 $4 的 SEO 重构"', PURPLE),
        ("      来源: 情节记忆  |  相关度: 0.89  |  ⬆ 激活", DIM),
        ('  ▸ "产品增长飞轮模型 (AARRR → RARRA)"', YELLOW),
        ("      来源: 语义记忆  |  相关度: 0.87  |  ⬆ 激活", DIM),
        ('  ▸ "SaaS 定价心理学: 锚定效应"', GREEN),
        ("      来源: 技能记忆  |  相关度: 0.81  |  ↑ 激活", DIM),
        ("", FG),
        ("  ✓ 双向激活完成, 7 条记忆注入上下文", GREEN),
    ]))

    # ── Frame 4: LLM Synthesis ──
    frames.append(make_frame([
        ("", FG),
        ("  ═══ STAGE 3: SYNTHESIZE (智慧合成) ═══", PURPLE),
        ("", FG),
        ("  📤 构造 Prompt → LLM 推理 ...", DIM),
        ("", FG),
        ("  Prompt 结构:", FG),
        ('  ┌─ ## 思考角度 (5 个维度)', DIM),
        ('  ├─ ## 相关记忆与经验 (7 条)', DIM),
        ('  └─ ## 当前问题', DIM),
        ("", FG),
        ("  LLM 流式响应中...", ACCENT),
        ("", FG),
        ("  ┌──────────────────────────────────────────┐", DIM),
        ("  │ 增长瓶颈应从获客效率与留存裂变两个       │", FG),
        ("  │ 维度同时切入。依据二八法则,建议先       │", FG),
        ("  │ 锁定转化率最高的 3 个渠道深度优化,       │", FG),
        ("  │ 同时引入推荐裂变机制解决获客天花板...    │", FG),
        ("  └──────────────────────────────────────────┘", DIM),
    ]))

    # ── Frame 5: Evolution record ──
    frames.append(make_frame([
        ("", FG),
        ("  ═══ STAGE 4: EVOLVE (自我进化) ═══", GREEN),
        ("", FG),
        ("  📊 记录本次推理结果...", DIM),
        ("", FG),
        ("  规律表现评估:", FG),
        ("  ✅ 第一性原理       +2%  权重 0.90 → 0.92", GREEN),
        ("  ✅ 二八法则         +2%  权重 0.85 → 0.87", GREEN),
        ("  ⬜ 系统思维           ±0  权重 0.80", DIM),
        ("  ✅ 逆向思考         +2%  权重 0.75 → 0.77", GREEN),
        ("  ⬜ 类比推理           ±0  权重 0.65", DIM),
        ("", FG),
        ("  ⏳ 累计 10 次会话后自动 evolve()", YELLOW),
        ("", FG),
        ("  ┌──────────────────────────────────────────┐", DIM),
        ("  │  ✓ 管线完成  |  总耗时 15.6s              │", GREEN),
        ("  │  记忆激活: 7条 | 思考维度: 5个 | 权重更新: 3项  │", DIM),
        ("  └──────────────────────────────────────────┘", DIM),
    ]))

    # ── Frame 6: Summary / CTA ──
    frames.append(make_frame([
        ("", FG),
        ("", FG),
        ("", FG),
        ("        ╔══════════════════════════════════╗", ACCENT),
        ("        ║  🧠  Wisdom Over Memory          ║", ACCENT),
        ("        ║                                  ║", ACCENT),
        ("        ║  pip install soma-wisdom         ║", GREEN),
        ("        ║  python -m soma                  ║", GREEN),
        ("        ║                                  ║", ACCENT),
        ("        ║  框架优先 · 双向激活 · 自我进化  ║", PURPLE),
        ("        ╚══════════════════════════════════╝", ACCENT),
        ("", FG),
        ("", FG),
        ("        ⭐  github.com/sunyan999999/soma", YELLOW),
    ]))

    # duplicate last frame for pause
    frames.append(frames[-1])
    frames.append(frames[-1])

    # ── write GIF ──
    imageio.mimsave(
        output_path,
        frames,
        duration=[1.2, 2.0, 2.2, 2.2, 2.2, 1.5, 1.5, 1.5],
        loop=0,
    )
    print(f"✓ GIF saved: {output_path}")
    print(f"  Frames: {len(frames)}, Size: {Path(output_path).stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    out = Path(__file__).resolve().parent.parent / "docs" / "images" / "demo-pipeline.gif"
    out.parent.mkdir(parents=True, exist_ok=True)
    build_gif(str(out))
