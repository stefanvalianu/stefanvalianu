#!/usr/bin/env python3
"""Generate ASCII art profile headers as SVG.

Fetches a seeded photo from Picsum and converts it to colored ASCII art
with a limited 216-color palette (6 levels per channel).  Produces both
light- and dark-themed variants for GitHub's prefers-color-scheme switching.

An optional titlecard (assets/TITLECARD.md) is rendered on a translucent
backdrop at the bottom center of the image, preserving basic markdown
formatting (bold, italic, headers).

Dependencies: Pillow (pip install Pillow)

Usage:
    python generate_header.py [seed]

    seed    String seed for generation (default: random)
"""

import colorsys
import os
import random
import re
import sys
import urllib.request
from io import BytesIO

from PIL import Image, ImageEnhance

# ── Canvas & SVG ────────────────────────────────────────────────────────

COLS = 100
ROWS = 24
FONT_SIZE = 13
CHAR_W = 7.8
LINE_H = 16
PAD = 14
SVG_W = int(COLS * CHAR_W + 2 * PAD)
SVG_H = int(ROWS * LINE_H + 2 * PAD)

# ASCII character ramp sorted by visual density (light → dark).
CHARS = " .',:;+*oO#@"

# Color quantization: 6 levels per channel = 216 colors (web-safe style).
COLOR_LEVELS = 6

# ── Themes ──────────────────────────────────────────────────────────────

THEMES = {
    "dark": {
        "bg": "#0d1117",
        "border": "#30363d",
        "text_color": "#e6edf3",
    },
    "light": {
        "bg": "#ffffff",
        "border": "#d0d7de",
        "text_color": "#1f2328",
    },
}

# ── Color mapping ──────────────────────────────────────────────────────

# Precompute a mapping from each dark-mode quantized color to a darker,
# more saturated variant suitable for a white background.  We reduce
# brightness in HSV space while boosting saturation so that hue
# differences survive the coarse 6-level quantization.
_LIGHT_COLOR_MAP = {}


def _dark_variant(hex_color):
    """Return a darker, vivid quantized color for light-mode rendering."""
    if hex_color in _LIGHT_COLOR_MAP:
        return _LIGHT_COLOR_MAP[hex_color]
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    v *= 0.6
    s = min(1.0, s * 2.0)
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    L = COLOR_LEVELS
    step = 255 // (L - 1)  # 51
    r = round(r * 255 / step) * step
    g = round(g * 255 / step) * step
    b = round(b * 255 / step) * step
    result = f"#{r:02x}{g:02x}{b:02x}"
    _LIGHT_COLOR_MAP[hex_color] = result
    return result


# ── Titlecard (Markdown) ──────────────────────────────────────────────

_INLINE_RE = re.compile(
    r"\*\*\*(.+?)\*\*\*"  # ***bold italic***
    r"|\*\*(.+?)\*\*"     # **bold**
    r"|\*(.+?)\*"          # *italic*
    r"|([^*]+)"            # plain text
)


def parse_md_line(line):
    """Parse a markdown line into (text, bold, italic) segments."""
    bold_all = False
    m = re.match(r"^(#{1,6})\s+", line)
    if m:
        line = line[m.end():]
        bold_all = True

    segments = []
    for m in _INLINE_RE.finditer(line):
        if m.group(1):      # ***bold italic***
            segments.append((m.group(1), True, True))
        elif m.group(2):    # **bold**
            segments.append((m.group(2), True, False))
        elif m.group(3):    # *italic*
            segments.append((m.group(3), bold_all, True))
        elif m.group(4):    # plain
            segments.append((m.group(4), bold_all, False))

    return segments


def load_titlecard():
    """Load assets/TITLECARD.md and return its lines, or None."""
    path = os.path.join(os.path.dirname(__file__), "..", "assets", "TITLECARD.md")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
    # Strip trailing blank lines
    while lines and not lines[-1].strip():
        lines.pop()
    return lines if lines else None


# ── Image fetch ─────────────────────────────────────────────────────────


def fetch_image(seed_str):
    """Fetch a deterministic photo from Picsum.

    Dimensions match our character grid's effective aspect ratio so the
    ASCII art isn't distorted.
    """
    w = 800
    h = int(w * ROWS * LINE_H / (COLS * CHAR_W))
    url = f"https://picsum.photos/seed/{seed_str}/{w}/{h}?blur=2"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return Image.open(BytesIO(resp.read()))


# ── Image → ASCII grid ──────────────────────────────────────────────────


def image_to_grid(img):
    """Convert a PIL Image to limited-palette ASCII art.

    Character density encodes brightness.  Each pixel's actual color is
    quantized to COLOR_LEVELS per channel (216 colors at 6 levels),
    preserving the image's real hues with a subtle retro posterization.

    Returns list[list[(char, color | None)]].
    """
    img = img.convert("RGB")
    img = ImageEnhance.Contrast(img).enhance(1.3)
    img = img.resize((COLS, ROWS), Image.LANCZOS)

    n = len(CHARS)
    L = COLOR_LEVELS
    gamma = 0.85  # lift shadows for dark-bg legibility
    grid = []

    for y in range(ROWS):
        row = []
        for x in range(COLS):
            r, g, b = img.getpixel((x, y))
            lum = 0.299 * r + 0.587 * g + 0.114 * b

            if lum < 8:
                row.append((" ", None))
                continue

            # Gamma correction
            r = int(255 * (r / 255) ** gamma)
            g = int(255 * (g / 255) ** gamma)
            b = int(255 * (b / 255) ** gamma)

            # Quantize to L levels per channel
            r = round(r / 255 * (L - 1)) * (255 // (L - 1))
            g = round(g / 255 * (L - 1)) * (255 // (L - 1))
            b = round(b / 255 * (L - 1)) * (255 // (L - 1))

            # Character from post-gamma brightness
            lum2 = 0.299 * r + 0.587 * g + 0.114 * b
            idx = min(int(lum2 / 256 * n), n - 1)
            ch = CHARS[idx]
            if ch == " ":
                row.append((" ", None))
                continue

            row.append((ch, f"#{r:02x}{g:02x}{b:02x}"))
        grid.append(row)

    return grid


# ── SVG output ──────────────────────────────────────────────────────────


def _xml(s):
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def to_svg(grid, theme, titlecard=None):
    """Render the character grid as an SVG document."""
    bg = theme["bg"]
    border = theme["border"]
    text_color = theme["text_color"]
    is_light = bg == "#ffffff"

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{SVG_W}" height="{SVG_H}" '
        f'viewBox="0 0 {SVG_W} {SVG_H}">',
        f'  <rect width="100%" height="100%" fill="{bg}" rx="6"/>',
        f'  <rect x=".5" y=".5" width="{SVG_W - 1}" height="{SVG_H - 1}" '
        f'fill="none" stroke="{border}" stroke-width="1" rx="6"/>',
        f"  <g font-family=\"'SFMono-Regular',Consolas,'Liberation Mono',"
        f'Menlo,monospace" font-size="{FONT_SIZE}">',
    ]

    # ── Base grid ──
    for r, row in enumerate(grid):
        y = PAD + (r + 1) * LINE_H

        spans = []
        cur_color = None
        cur_chars = []
        for ch, color in row:
            if color is None:
                c = bg
            elif is_light:
                c = _dark_variant(color)
            else:
                c = color
            if c == cur_color:
                cur_chars.append(ch)
            else:
                if cur_chars:
                    spans.append(("".join(cur_chars), cur_color))
                cur_color = c
                cur_chars = [ch]
        if cur_chars:
            spans.append(("".join(cur_chars), cur_color))

        parts = "".join(
            f'<tspan fill="{c}">{_xml(t)}</tspan>' for t, c in spans
        )
        lines.append(
            f'    <text x="{PAD}" y="{y:.0f}" '
            f'xml:space="preserve">{parts}</text>'
        )

    # ── Titlecard overlay ──
    if titlecard:
        pad_px = 3 * CHAR_W  # uniform padding on all sides (~23px)
        parsed = [parse_md_line(line) for line in titlecard]
        widths = [sum(len(t) for t, _, _ in segs) for segs in parsed]
        max_w = max(widths) if widths else 0
        num_lines = len(titlecard)

        card_pw = max_w * CHAR_W + pad_px * 2
        card_ph = num_lines * LINE_H + pad_px * 2

        # Bottom center
        card_x = (SVG_W - card_pw) / 2
        card_y = SVG_H - PAD - card_ph

        # Translucent backdrop with border
        lines.append(
            f'    <rect x="{card_x:.1f}" y="{card_y:.1f}" '
            f'width="{card_pw:.1f}" height="{card_ph:.1f}" '
            f'fill="{bg}" fill-opacity="0.85" rx="6"/>'
        )
        lines.append(
            f'    <rect x="{card_x:.1f}" y="{card_y:.1f}" '
            f'width="{card_pw:.1f}" height="{card_ph:.1f}" '
            f'fill="none" stroke="{border}" stroke-opacity="0.5" '
            f'stroke-width="1" rx="6"/>'
        )

        # Render each line
        text_x = card_x + pad_px
        for i, segs in enumerate(parsed):
            text_y = card_y + pad_px + i * LINE_H + LINE_H

            if not segs:
                continue  # blank line — vertical spacing preserved via index

            tspans = []
            for text, bold, italic in segs:
                attrs = f'fill="{text_color}"'
                if bold:
                    attrs += ' font-weight="bold"'
                if italic:
                    attrs += ' font-style="italic"'
                tspans.append(f"<tspan {attrs}>{_xml(text)}</tspan>")

            lines.append(
                f'    <text x="{text_x:.1f}" y="{text_y:.1f}" '
                f'xml:space="preserve">{"".join(tspans)}</text>'
            )

    lines.append("  </g>")
    lines.append("</svg>")
    return "\n".join(lines)


# ── Main ────────────────────────────────────────────────────────────────


def main():
    seed_str = sys.argv[1] if len(sys.argv) > 1 else str(random.randint(1, 1_000_000_000))
    out_dir = os.path.join(os.path.dirname(__file__), "..", "assets")
    os.makedirs(out_dir, exist_ok=True)

    img = fetch_image(seed_str)
    grid = image_to_grid(img)
    titlecard = load_titlecard()

    for name, theme in THEMES.items():
        svg = to_svg(grid, theme, titlecard)
        path = os.path.join(out_dir, f"header-{name}.svg")
        with open(path, "w", encoding="utf-8") as f:
            f.write(svg)
        print(f"Generated {path} (seed: {seed_str})")


if __name__ == "__main__":
    main()
