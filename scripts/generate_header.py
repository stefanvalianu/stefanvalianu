#!/usr/bin/env python3
"""Generate ASCII art profile headers as SVG.

Fetches a seeded photo from Picsum and converts it to colored ASCII art
with a limited 216-color palette (6 levels per channel).  Produces both
light- and dark-themed variants for GitHub's prefers-color-scheme switching.

An optional label is rendered as bitmap-font ASCII art on a gradient
backdrop, placed in the emptiest region of the image.

Dependencies: Pillow (pip install Pillow)

Usage:
    python generate_header.py [seed] [label]

    seed    String seed for generation (default: random)
    label   Text to overlay on the image (default: Stefan Valianu)
"""

import colorsys
import os
import random
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


# ── Bitmap font (5 rows tall, variable width) ──────────────────────────

GLYPH = {
    'A': (" ## ", "#  #", "####", "#  #", "#  #"),
    'B': ("### ", "#  #", "### ", "#  #", "### "),
    'C': (" ## ", "#   ", "#   ", "#   ", " ## "),
    'D': ("### ", "#  #", "#  #", "#  #", "### "),
    'E': ("####", "#   ", "### ", "#   ", "####"),
    'F': ("####", "#   ", "### ", "#   ", "#   "),
    'G': (" ## ", "#   ", "# ##", "#  #", " ## "),
    'H': ("#  #", "#  #", "####", "#  #", "#  #"),
    'I': ("###", " # ", " # ", " # ", "###"),
    'J': (" ###", "   #", "   #", "#  #", " ## "),
    'K': ("#  #", "# # ", "##  ", "# # ", "#  #"),
    'L': ("#   ", "#   ", "#   ", "#   ", "####"),
    'M': ("#   #", "## ##", "# # #", "#   #", "#   #"),
    'N': ("#  #", "## #", "# ##", "#  #", "#  #"),
    'O': (" ## ", "#  #", "#  #", "#  #", " ## "),
    'P': ("### ", "#  #", "### ", "#   ", "#   "),
    'Q': (" ## ", "#  #", "#  #", " ## ", "  # "),
    'R': ("### ", "#  #", "### ", "# # ", "#  #"),
    'S': (" ###", "#   ", " ## ", "   #", "### "),
    'T': ("#####", "  #  ", "  #  ", "  #  ", "  #  "),
    'U': ("#  #", "#  #", "#  #", "#  #", " ## "),
    'V': ("#   #", "#   #", " # # ", " # # ", "  #  "),
    'W': ("#   #", "#   #", "# # #", "# # #", " # # "),
    'X': ("#   #", " # # ", "  #  ", " # # ", "#   #"),
    'Y': ("#   #", " # # ", "  #  ", "  #  ", "  #  "),
    'Z': ("#####", "   # ", "  #  ", " #   ", "#####"),
    '0': (" ## ", "#  #", "#  #", "#  #", " ## "),
    '1': (" #  ", "##  ", " #  ", " #  ", "####"),
    '2': (" ## ", "#  #", "  # ", " #  ", "####"),
    '3': ("### ", "   #", " ## ", "   #", "### "),
    '4': ("#  #", "#  #", "####", "   #", "   #"),
    '5': ("####", "#   ", "### ", "   #", "### "),
    '6': (" ## ", "#   ", "### ", "#  #", " ## "),
    '7': ("####", "   #", "  # ", " #  ", "#   "),
    '8': (" ## ", "#  #", " ## ", "#  #", " ## "),
    '9': (" ## ", "#  #", " ###", "   #", " ## "),
    ' ': ("   ", "   ", "   ", "   ", "   "),
    '.': (" ", " ", " ", " ", "#"),
    '-': ("    ", "    ", "####", "    ", "    "),
    '_': ("    ", "    ", "    ", "    ", "####"),
}
GLYPH_H = 5


def render_text(text):
    """Render text as a 5-row ASCII art block using the bitmap font.

    Returns a list of 5 equal-length strings.
    """
    text = text.upper()
    rows = [""] * GLYPH_H
    for i, ch in enumerate(text):
        glyph = GLYPH.get(ch, GLYPH[' '])
        if i > 0:
            for r in range(GLYPH_H):
                rows[r] += " "
        for r in range(GLYPH_H):
            rows[r] += glyph[r]
    return rows


def find_placement(grid, tw, th, margin=3):
    """Find the grid position with the most empty space for a text block.

    Scans every valid position and picks the one whose bounding box
    (including margin) contains the most space characters.  Falls back
    to center-bottom if no position is at least 50 % empty.
    """
    pw = tw + margin * 2
    ph = th + margin * 2
    best_x, best_y, best_score = 0, 0, -1

    for y in range(max(1, ROWS - ph + 1)):
        for x in range(max(1, COLS - pw + 1)):
            score = sum(
                1
                for dy in range(ph)
                for dx in range(pw)
                if grid[y + dy][x + dx][0] == " "
            )
            if score > best_score:
                best_score = score
                best_x = x + margin
                best_y = y + margin

    if best_score < pw * ph * 0.5:
        best_x = max(0, (COLS - tw) // 2)
        best_y = max(0, ROWS - th - margin)

    return best_x, best_y


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


def to_svg(grid, theme, text_rows=None, text_pos=None):
    """Render the character grid as an SVG document."""
    bg = theme["bg"]
    border = theme["border"]
    text_color = theme["text_color"]
    is_light = bg == "#ffffff"

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{SVG_W}" height="{SVG_H}" '
        f'viewBox="0 0 {SVG_W} {SVG_H}">',
    ]

    # Gradient definition for text backdrop
    if text_rows and text_pos:
        lines.append("  <defs>")
        lines.append(
            '    <linearGradient id="tbg" x1="0" y1="0" x2="0" y2="1">'
        )
        lines.append(
            f'      <stop offset="0%" stop-color="{bg}" stop-opacity="0"/>'
        )
        lines.append(
            f'      <stop offset="20%" stop-color="{bg}" stop-opacity="0.9"/>'
        )
        lines.append(
            f'      <stop offset="80%" stop-color="{bg}" stop-opacity="0.9"/>'
        )
        lines.append(
            f'      <stop offset="100%" stop-color="{bg}" stop-opacity="0"/>'
        )
        lines.append("    </linearGradient>")
        lines.append("  </defs>")

    lines.extend([
        f'  <rect width="100%" height="100%" fill="{bg}" rx="6"/>',
        f'  <rect x=".5" y=".5" width="{SVG_W - 1}" height="{SVG_H - 1}" '
        f'fill="none" stroke="{border}" stroke-width="1" rx="6"/>',
        f"  <g font-family=\"'SFMono-Regular',Consolas,'Liberation Mono',"
        f'Menlo,monospace" font-size="{FONT_SIZE}">',
    ])

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

    # ── Text overlay with gradient backdrop ──
    if text_rows and text_pos:
        tx, ty = text_pos
        tw = len(text_rows[0])
        margin = 3

        # Gradient backdrop rect
        gx = PAD + max(0, tx - margin) * CHAR_W
        gy = PAD + max(0, ty - margin) * LINE_H
        gw = (tw + margin * 2) * CHAR_W
        gh = (GLYPH_H + margin * 2) * LINE_H
        lines.append(
            f'    <rect x="{gx:.1f}" y="{gy:.1f}" '
            f'width="{gw:.1f}" height="{gh:.1f}" '
            f'fill="url(#tbg)" rx="6"/>'
        )

        # Overlay text characters
        for r, row_str in enumerate(text_rows):
            y = PAD + (ty + r + 1) * LINE_H
            x = PAD + tx * CHAR_W
            lines.append(
                f'    <text x="{x:.1f}" y="{y:.0f}" '
                f'fill="{text_color}" xml:space="preserve">'
                f"{_xml(row_str)}</text>"
            )

    lines.append("  </g>")
    lines.append("</svg>")
    return "\n".join(lines)


# ── Main ────────────────────────────────────────────────────────────────


def main():
    seed_str = sys.argv[1] if len(sys.argv) > 1 else str(random.randint(1, 1_000_000_000))
    label = sys.argv[2] if len(sys.argv) > 2 else "Stefan Valianu"
    out_dir = os.path.join(os.path.dirname(__file__), "..", "assets")
    os.makedirs(out_dir, exist_ok=True)

    img = fetch_image(seed_str)
    grid = image_to_grid(img)

    text_rows = render_text(label) if label else None
    text_pos = None
    if text_rows:
        tw = len(text_rows[0])
        text_pos = find_placement(grid, tw, GLYPH_H)

    for name, theme in THEMES.items():
        svg = to_svg(grid, theme, text_rows, text_pos)
        path = os.path.join(out_dir, f"header-{name}.svg")
        with open(path, "w", encoding="utf-8") as f:
            f.write(svg)
        print(f"Generated {path} (seed: {seed_str})")


if __name__ == "__main__":
    main()
