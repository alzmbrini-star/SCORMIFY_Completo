"""Whiteboard / Hand-writer video renderer.

Self-hosted MVP for generating "Doodly/VideoScribe-style" explainer
videos where a pen progressively writes text on a white canvas.
No external API dependency — Pillow + numpy for image work,
imageio-ffmpeg for MP4 encoding.

Writing motion (skeleton-traced):
---------------------------------
Each glyph is rendered offscreen, then **skeletonized** (Zhang-Suen
thinning) into a 1-pixel-wide centerline. We walk the skeleton in
writing order (top-left endpoint → forward-biased neighbor chase) to
produce a sequence of "pen positions". During rendering, each pen
position **reveals a disk of ink** of approximately one stroke-width
in radius — so the visible letter grows naturally outward from the
pen tip, exactly like wet ink flowing from a nib.

This handles multi-stroke letters (H, T, F, t, i) by chasing each
connected component of the skeleton in turn, jumping between them
without leaving phantom ink in between.

Pipeline:
1. Layout text on 1920x1080 canvas with Caveat handwriting font.
2. For every unique character: render glyph → thin → order skeleton
   path → precompute incremental "reveal masks" at each sub-step.
3. Frame schedule: chars × sub_steps_per_char gives the animation
   timeline. Pen tip follows the path; current letter's reveal mask
   is composited; previous letters stay fully drawn.
4. Encode H.264 / yuv420p MP4 via imageio-ffmpeg.
"""
from __future__ import annotations

import os
import re
import uuid
import asyncio
import logging
from pathlib import Path
from typing import Optional

from PIL import Image, ImageChops, ImageDraw, ImageFont
import numpy as np
import imageio
import imageio_ffmpeg  # noqa: F401

logger = logging.getLogger("server.whiteboard")


def _resolve_ffmpeg_binary() -> str:
    """Locate an ffmpeg binary the encoder can call.

    Resolution order:
      1. imageio-ffmpeg bundled/cached binary (production happy path).
      2. System ffmpeg on $PATH (operator-installed via apt).
    """
    try:
        path = imageio_ffmpeg.get_ffmpeg_exe()
        if path and Path(path).exists():
            return path
    except Exception as e:  # noqa: BLE001
        logger.warning("imageio_ffmpeg.get_ffmpeg_exe() failed: %s", e)
    import shutil
    sys_ffmpeg = shutil.which("ffmpeg")
    if sys_ffmpeg:
        logger.info("whiteboard: using system ffmpeg at %s", sys_ffmpeg)
        return sys_ffmpeg
    raise RuntimeError(
        "No ffmpeg binary found. Install imageio-ffmpeg, or `apt-get "
        "install ffmpeg` in the deployment image."
    )


ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets" / "whiteboard"
FONTS_DIR = ASSETS_DIR / "fonts"
# Legacy single-font location (kept for fallback compat).
LEGACY_FONT_PATH = ASSETS_DIR / "Caveat-Regular.ttf"
HAND_PATH = ASSETS_DIR / "hand.png"
OUTPUT_DIR = Path(os.environ.get("STORAGE_DIR", "/app/backend/storage")) / "whiteboard"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# =====================================================================
# Font catalog — bundled handwriting / marker fonts.
# =====================================================================
# Each entry: id (used as font_family param) -> (filename, display name,
# style hint). The "hand_friendly" flag tells the UI which fonts work
# well with the pen animation (handwriting fonts) vs print fonts that
# would still animate but look less natural.

FONT_CATALOG: dict[str, dict] = {
    "caveat": {
        "file": "Caveat.ttf",
        "label": "Caveat (manuscrita)",
        "style": "handwriting",
    },
    "architects_daughter": {
        "file": "ArchitectsDaughter.ttf",
        "label": "Architects Daughter (arquiteto)",
        "style": "handwriting",
    },
    "indie_flower": {
        "file": "IndieFlower.ttf",
        "label": "Indie Flower (arredondada)",
        "style": "handwriting",
    },
    "patrick_hand": {
        "file": "PatrickHand.ttf",
        "label": "Patrick Hand (limpa)",
        "style": "handwriting",
    },
    "permanent_marker": {
        "file": "PermanentMarker.ttf",
        "label": "Permanent Marker (marcador)",
        "style": "marker",
    },
    "shadows_into_light": {
        "file": "ShadowsIntoLight.ttf",
        "label": "Shadows Into Light (fina)",
        "style": "handwriting",
    },
    "kalam": {
        "file": "Kalam.ttf",
        "label": "Kalam (caligráfica)",
        "style": "handwriting",
    },
}


def _resolve_font_path(font_family: Optional[str]) -> Path:
    """Map a `font_family` id to a TTF on disk. Falls back to Caveat."""
    if font_family and font_family in FONT_CATALOG:
        candidate = FONTS_DIR / FONT_CATALOG[font_family]["file"]
        if candidate.exists():
            return candidate
    # Default: Caveat in the new fonts dir, else legacy location.
    new_caveat = FONTS_DIR / "Caveat.ttf"
    if new_caveat.exists():
        return new_caveat
    return LEGACY_FONT_PATH


def list_available_fonts() -> list[dict]:
    """Return the catalog filtered to fonts physically present on disk."""
    out = []
    for fid, meta in FONT_CATALOG.items():
        if (FONTS_DIR / meta["file"]).exists():
            out.append({"id": fid, "label": meta["label"], "style": meta["style"]})
    return out

# Canvas dimensions — 1920x1080 matches SCORM export aspect ratio.
CANVAS_W, CANVAS_H = 1920, 1080
MARGIN_X, MARGIN_Y = 140, 140
FONT_SIZE_DEFAULT = 84
LINE_SPACING = 1.25  # multiplier of font size
FPS = 30
# Pen asset tip is at (0, 0). These nudges fine-tune so the tip
# sits ON the ink rather than slightly above.
HAND_OFFSET_X = -2
HAND_OFFSET_Y = -4


# =====================================================================
# Skeleton extraction (Zhang-Suen thinning)
# =====================================================================

def _thin_zhang_suen(binary: np.ndarray) -> np.ndarray:
    """Zhang-Suen thinning. Input is a bool 2-D array, True = ink.
    Returns a 1-pixel-thick skeleton as a bool array of the same shape.

    Vectorized: each iteration runs ~10-50 µs on typical glyph masks.
    """
    img = binary.copy()
    h, w = img.shape
    if h < 3 or w < 3:
        return img

    while True:
        changed = False
        # Run two sub-iterations per Zhang-Suen step. We pack both into
        # one pass for clarity.
        for sub in (0, 1):
            padded = np.pad(img, 1, constant_values=False)
            # 8-neighborhood (P2..P9 in clockwise order from north).
            P2 = padded[0:h,   1:w+1]   # N
            P3 = padded[0:h,   2:w+2]   # NE
            P4 = padded[1:h+1, 2:w+2]   # E
            P5 = padded[2:h+2, 2:w+2]   # SE
            P6 = padded[2:h+2, 1:w+1]   # S
            P7 = padded[2:h+2, 0:w]     # SW
            P8 = padded[1:h+1, 0:w]     # W
            P9 = padded[0:h,   0:w]     # NW

            B = (P2.astype(np.int8) + P3 + P4 + P5 + P6 + P7 + P8 + P9)
            seq = [P2, P3, P4, P5, P6, P7, P8, P9, P2]
            A = np.zeros_like(B)
            for i in range(8):
                A += ((~seq[i]) & seq[i + 1]).astype(np.int8)

            cond = img & (B >= 2) & (B <= 6) & (A == 1)
            if sub == 0:
                cond &= ~(P2 & P4 & P6)
                cond &= ~(P4 & P6 & P8)
            else:
                cond &= ~(P2 & P4 & P8)
                cond &= ~(P2 & P6 & P8)

            if cond.any():
                img &= ~cond
                changed = True
        if not changed:
            break
    return img


# =====================================================================
# Skeleton ordering — produce a "writing path" through the skeleton.
# =====================================================================

def _order_skeleton_path(skel: np.ndarray) -> list[tuple[int, int]]:
    """Walk skeleton pixels in writing order. Returns a flat list of
    (x, y) tuples spanning ALL connected components, chained left-to-
    right by component leftmost endpoint.

    Within a component:
      - Start at the topmost-leftmost endpoint (pixel with one
        neighbor). If no endpoint (closed loop), start at the
        topmost-leftmost pixel.
      - At each step, prefer the unvisited neighbor most aligned with
        the last movement direction (smooth continuous writing).
      - When no unvisited neighbor exists, the component is done.

    The resulting path is what the pen tip traces.
    """
    ys, xs = np.where(skel)
    if len(ys) == 0:
        return []

    point_set = set(zip(xs.tolist(), ys.tolist()))
    visited: set[tuple[int, int]] = set()
    full_path: list[tuple[int, int]] = []

    NEIGH_OFFSETS = [(-1, -1), (0, -1), (1, -1),
                     (-1,  0),          (1,  0),
                     (-1,  1), (0,  1), (1,  1)]

    def neighbors_of(p):
        x, y = p
        return [(x + dx, y + dy) for dx, dy in NEIGH_OFFSETS
                if (x + dx, y + dy) in point_set]

    # Pre-find endpoints (1-neighbor pixels) for fast component starts.
    endpoints_set = {p for p in point_set if len(neighbors_of(p)) == 1}

    # Find connected components via BFS.
    def find_component(seed):
        comp = set()
        stack = [seed]
        while stack:
            p = stack.pop()
            if p in comp:
                continue
            comp.add(p)
            for n in neighbors_of(p):
                if n not in comp:
                    stack.append(n)
        return comp

    remaining = set(point_set)
    components: list[set] = []
    while remaining:
        seed = next(iter(remaining))
        c = find_component(seed)
        components.append(c)
        remaining -= c

    # Order components by leftmost-then-topmost pixel — mimics LTR writing.
    def comp_key(c):
        xs_c = [p[0] for p in c]
        ys_c = [p[1] for p in c]
        return (min(xs_c), min(ys_c))
    components.sort(key=comp_key)

    for comp in components:
        comp_endpoints = sorted(
            [p for p in comp if p in endpoints_set],
            key=lambda p: (p[1], p[0]),   # topmost, then leftmost
        )
        if comp_endpoints:
            start = comp_endpoints[0]
        else:
            start = min(comp, key=lambda p: (p[1], p[0]))

        current = start
        last_dir = (1, 0)
        comp_visited: set[tuple[int, int]] = set()
        while True:
            full_path.append(current)
            visited.add(current)
            comp_visited.add(current)
            cands = [n for n in neighbors_of(current)
                     if n in comp and n not in comp_visited]
            if not cands:
                break
            def alignment(n):
                dx = n[0] - current[0]
                dy = n[1] - current[1]
                return dx * last_dir[0] + dy * last_dir[1]
            cands.sort(key=alignment, reverse=True)
            chosen = cands[0]
            last_dir = (chosen[0] - current[0], chosen[1] - current[1])
            current = chosen

    return full_path


# =====================================================================
# Layout (unchanged) + glyph cache with skeleton path & reveal frames.
# =====================================================================

def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Greedy word-wrap that respects explicit `\\n` line breaks."""
    out: list[str] = []
    for raw_line in (text or "").split("\n"):
        if not raw_line.strip():
            out.append("")
            continue
        words = raw_line.split(" ")
        line = ""
        for w in words:
            cand = f"{line} {w}".strip() if line else w
            bbox = font.getbbox(cand)
            if bbox[2] - bbox[0] <= max_width:
                line = cand
            else:
                if line:
                    out.append(line)
                line = w
        if line:
            out.append(line)
    return out


DEFAULT_INK_COLOR = (20, 20, 20)


def _parse_color(value: str) -> Optional[tuple[int, int, int]]:
    """Parse '#RRGGBB', '#RGB' or 'rgb(r,g,b)' into an (R, G, B) tuple."""
    if not value:
        return None
    value = value.strip().lower()
    if value.startswith("#"):
        hex_str = value[1:]
        if len(hex_str) == 3:
            hex_str = "".join(c * 2 for c in hex_str)
        if len(hex_str) == 6:
            try:
                return (int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16))
            except ValueError:
                return None
    m = re.match(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", value)
    if m:
        return tuple(min(255, max(0, int(m.group(i)))) for i in (1, 2, 3))
    return None


def _parse_html_to_runs(
    html: str, default_color: tuple[int, int, int],
) -> list[dict]:
    """Parse simple HTML into a flat list of char dicts:
        {ch, color, bold, underline, align}
    where `align` is "left"|"center"|"right" inherited from the
    nearest block ancestor (default "left"). Newlines have `ch="\\n"`
    and carry the alignment of the line being closed.

    Supported markup:
      Color: `<span style="color:#XXX">`, `<font color="#XXX">`
      Bold:  `<b>`, `<strong>`, `style="font-weight: bold"`
      Underline: `<u>`, `style="text-decoration: underline"`
      Breaks: `<br>`, `<div>`, `<p>` (line breaks)
      Lists: `<ul><li>...</li></ul>` — each li becomes a "• ..." line
      Alignment: `style="text-align: left|center|right"` on the
        nearest block element.
    """
    from html.parser import HTMLParser
    from html import unescape

    runs: list[dict] = []
    color_stack: list[tuple[int, int, int]] = [default_color]
    bold_stack: list[bool] = [False]
    underline_stack: list[bool] = [False]
    align_stack: list[str] = ["left"]

    BLOCK_TAGS = {"div", "p", "li"}

    def _current_attrs():
        return {
            "color": color_stack[-1],
            "bold": bold_stack[-1],
            "underline": underline_stack[-1],
            "align": align_stack[-1],
        }

    def _emit_newline():
        # Only emit if the last emitted char wasn't already a newline
        # — avoids double breaks from nested block tags.
        if runs and runs[-1]["ch"] != "\n":
            runs.append({"ch": "\n", **_current_attrs()})

    class _P(HTMLParser):
        def handle_starttag(self, tag, attrs):
            attrs_d = dict(attrs)
            style = (attrs_d.get("style", "") or "").lower()
            # Color.
            new_color = None
            m = re.search(r"color\s*:\s*([^;]+)", style)
            if m:
                new_color = _parse_color(m.group(1))
            if not new_color and tag == "font":
                new_color = _parse_color(attrs_d.get("color", "") or "")
            color_stack.append(new_color if new_color else color_stack[-1])
            # Bold.
            is_bold = bold_stack[-1]
            if tag in ("b", "strong"):
                is_bold = True
            elif re.search(r"font-weight\s*:\s*(bold|[6-9]\d\d)", style):
                is_bold = True
            bold_stack.append(is_bold)
            # Underline.
            is_under = underline_stack[-1]
            if tag == "u":
                is_under = True
            elif "underline" in style and "text-decoration" in style:
                is_under = True
            underline_stack.append(is_under)
            # Alignment (block-level scope).
            new_align = align_stack[-1]
            m = re.search(r"text-align\s*:\s*(left|center|right)", style)
            if m:
                new_align = m.group(1)
            align_stack.append(new_align)
            # Structural breaks.
            if tag == "br":
                _emit_newline()
            elif tag in BLOCK_TAGS:
                _emit_newline()
            if tag == "li":
                # Prepend bullet glyph to the line. Bullets inherit
                # color but ignore bold/underline for visual consistency.
                for ch in "•  ":
                    runs.append({
                        "ch": ch,
                        "color": color_stack[-1],
                        "bold": False,
                        "underline": False,
                        "align": align_stack[-1],
                    })

        def handle_startendtag(self, tag, attrs):
            self.handle_starttag(tag, attrs)
            self.handle_endtag(tag)

        def handle_endtag(self, tag):
            for stk in (color_stack, bold_stack, underline_stack, align_stack):
                if len(stk) > 1:
                    stk.pop()

        def handle_data(self, data):
            decoded = unescape(data)
            for ch in decoded:
                runs.append({"ch": ch, **_current_attrs()})

    parser = _P()
    parser.feed(html)
    return runs


def _layout(
    text: Optional[str],
    font_size: int,
    font_path: Path,
    default_color: tuple[int, int, int] = DEFAULT_INK_COLOR,
    text_html: Optional[str] = None,
) -> tuple[ImageFont.FreeTypeFont, list[dict]]:
    """Lay out either plain `text` or rich `text_html` into positioned
    characters. Per-line alignment is honored (left/center/right)
    based on the alignment of each line's first char.

    Returns (font, list[dict]) where each dict has:
        ch, x, y, color, bold, underline.
    """
    font = ImageFont.truetype(str(font_path), font_size)
    max_w = CANVAS_W - 2 * MARGIN_X

    if text_html:
        char_runs = _parse_html_to_runs(text_html, default_color)
    else:
        char_runs = [{
            "ch": c, "color": default_color, "bold": False,
            "underline": False, "align": "left",
        } for c in (text or "")]

    # Group char_runs into "input lines" by explicit \n characters.
    # Each input line knows its alignment from its first non-newline
    # char (or carries the newline char's alignment if empty).
    input_lines: list[list[dict]] = [[]]
    for r in char_runs:
        if r["ch"] == "\n":
            input_lines.append([])
        else:
            input_lines[-1].append(r)
    # Drop trailing empty lines from typical trailing block tags.
    while len(input_lines) > 1 and not input_lines[-1]:
        input_lines.pop()

    chars: list[dict] = []
    line_h = int(font_size * LINE_SPACING)
    y = MARGIN_Y

    for input_line in input_lines:
        if not input_line:
            # Blank line — preserve as vertical spacing.
            y += line_h
            continue
        # Build the line's text for wrap calc, and apply word-wrap.
        line_text = "".join(r["ch"] for r in input_line)
        wrapped = _wrap_text(line_text, font, max_w) or [""]
        # Alignment from the first char of this paragraph.
        align = input_line[0].get("align", "left")
        # Walk the wrapped sublines, mapping each char back to its
        # source attribute dict by index in `input_line`.
        flat_idx = 0
        for sub in wrapped:
            sub_w = int(font.getlength(sub))
            if align == "center":
                line_x = MARGIN_X + max(0, (max_w - sub_w) // 2)
            elif align == "right":
                line_x = MARGIN_X + max(0, max_w - sub_w)
            else:
                line_x = MARGIN_X
            x = line_x
            for ch in sub:
                # Advance flat_idx through any chars dropped by wrap
                # (e.g., separator spaces between wrapped words).
                while (flat_idx < len(input_line)
                       and input_line[flat_idx]["ch"] != ch):
                    flat_idx += 1
                attrs = input_line[flat_idx] if flat_idx < len(input_line) else {
                    "color": default_color, "bold": False, "underline": False,
                }
                chars.append({
                    "ch": ch, "x": x, "y": y,
                    "color": attrs.get("color", default_color),
                    "bold": bool(attrs.get("bold")),
                    "underline": bool(attrs.get("underline")),
                })
                adv = font.getlength(ch)
                x += int(adv)
                flat_idx += 1
            y += line_h
    return font, chars


def _disk_mask(radius: int) -> np.ndarray:
    """Return a (2r+1, 2r+1) bool disk mask."""
    r = max(1, radius)
    yy, xx = np.ogrid[-r:r + 1, -r:r + 1]
    return (xx * xx + yy * yy) <= r * r


def _build_glyph_cache(
    chars: list[dict],
    font: ImageFont.FreeTypeFont,
    sub_steps: int,
):
    """Per-unique-glyph precompute everything the frame loop needs.

    Cache is keyed on the character alone — color and bold/underline are
    applied at composite time so we never duplicate cache entries.
    """
    cache: dict[str, Optional[dict]] = {}
    for entry in chars:
        ch = entry["ch"]
        if ch in cache:
            continue
        if not ch.strip():
            cache[ch] = None
            continue
        bbox = font.getbbox(ch)
        if not bbox:
            cache[ch] = None
            continue
        left, top, right, bottom = bbox
        w = max(1, right - left)
        h = max(1, bottom - top)

        glyph = Image.new("RGBA", (w, h), (255, 255, 255, 0))
        ImageDraw.Draw(glyph).text(
            (-left, -top), ch, font=font, fill=(20, 20, 20, 255),
        )
        alpha = np.asarray(glyph)[..., 3]
        ink = alpha > 32
        if not ink.any():
            cache[ch] = None
            continue

        # Skeletonize.
        skel = _thin_zhang_suen(ink)
        if not skel.any():
            # Degenerate (single pixel). Fall back to the ink mask itself.
            skel = ink.copy()
        path = _order_skeleton_path(skel)
        if not path:
            cache[ch] = None
            continue

        # Estimate stroke radius. ink_area / path_length ≈ stroke width.
        ink_area = int(ink.sum())
        stroke_w = max(2.0, ink_area / max(1, len(path)))
        reveal_radius = max(2, int(round(stroke_w * 0.9)))
        # Slightly larger "trail" radius behind the pen so the reveal
        # convincingly fills the stroke even at antialiased edges.

        disk = _disk_mask(reveal_radius)
        dr = reveal_radius

        # Precompute cumulative reveal masks at `sub_steps` checkpoints.
        # We stamp a disk centered at each path point; checkpoints
        # divide the path into roughly equal segments.
        reveal_masks: list[np.ndarray] = []
        pen_positions: list[tuple[int, int]] = []

        cur_mask = np.zeros((h, w), dtype=bool)
        n_pts = len(path)
        last_painted_idx = -1
        for s in range(sub_steps):
            target_idx = int(round((s + 1) / sub_steps * n_pts)) - 1
            target_idx = max(0, min(n_pts - 1, target_idx))
            # Stamp disks from last_painted_idx + 1 through target_idx.
            for i in range(last_painted_idx + 1, target_idx + 1):
                px, py = path[i]
                # Compute paste rect clamped to the glyph bounds.
                x0 = max(0, px - dr)
                x1 = min(w, px + dr + 1)
                y0 = max(0, py - dr)
                y1 = min(h, py + dr + 1)
                dx0 = x0 - (px - dr)
                dx1 = dx0 + (x1 - x0)
                dy0 = y0 - (py - dr)
                dy1 = dy0 + (y1 - y0)
                cur_mask[y0:y1, x0:x1] |= disk[dy0:dy1, dx0:dx1]
            last_painted_idx = target_idx
            # Snapshot is intersected with original ink — disks should
            # only show where there's actual letter ink, never on
            # background.
            reveal_masks.append((cur_mask & ink).copy())
            pen_positions.append(path[target_idx])

        # After all sub-steps, ensure the FULL letter is shown
        # (in case the skeleton didn't cover every ink pixel —
        # e.g., disconnected antialias pixels). The last mask must
        # equal the full ink mask for visual cleanliness.
        reveal_masks[-1] = ink.copy()

        cache[ch] = {
            "glyph": glyph,
            "ink": ink,
            "reveal_masks": reveal_masks,
            "left": left,
            "top": top,
            "width": w,
            "height": h,
            "pen_positions": pen_positions,
        }
    return cache


# =====================================================================
# Frame rendering
# =====================================================================

def _dilate_alpha(alpha: np.ndarray) -> np.ndarray:
    """1-pixel 4-connected dilation of an alpha plane. Used to "fatten"
    glyph strokes for bold-style emphasis since handwriting fonts don't
    have native bold weights."""
    out = alpha.copy()
    out[1:] = np.maximum(out[1:], alpha[:-1])
    out[:-1] = np.maximum(out[:-1], alpha[1:])
    out[:, 1:] = np.maximum(out[:, 1:], out[:, :-1].copy())
    out[:, :-1] = np.maximum(out[:, :-1], out[:, 1:].copy())
    return out


def _make_glyph_image(
    entry: dict, reveal_idx: int,
    color: tuple[int, int, int] = DEFAULT_INK_COLOR,
    bold: bool = False,
) -> Image.Image:
    """Apply the cumulative reveal mask of the given sub-step to the
    glyph and recolor the ink with `color`. Pixels not yet 'written'
    are made transparent.

    When `bold=True` the alpha plane is dilated by 1 pixel before
    composition — produces a thicker-stroke effect that reads as bold
    on handwriting fonts (which lack native bold variants)."""
    glyph = entry["glyph"]
    mask = entry["reveal_masks"][reveal_idx]
    arr = np.array(glyph)  # writable RGBA copy
    masked_alpha = np.where(mask, arr[..., 3], 0).astype(np.uint8)
    if bold:
        masked_alpha = _dilate_alpha(masked_alpha)
    # Recolor: overwrite RGB channels with the desired ink color while
    # keeping the (possibly dilated) alpha.
    arr[..., 0] = color[0]
    arr[..., 1] = color[1]
    arr[..., 2] = color[2]
    arr[..., 3] = masked_alpha
    return Image.fromarray(arr, "RGBA")


def _render_frame_writing(
    step_idx: int,
    chars: list[tuple[str, int, int]],
    glyph_cache: dict,
    char_substeps: list[int],
    char_step_starts: list[int],
    hand_img: Image.Image,
    title: Optional[str],
    title_font: Optional[ImageFont.FreeTypeFont],
    transparent: bool = False,
) -> Image.Image:
    """Render a single MP4/WebM frame at the given **sub-step** index.

    When `transparent` is True the background is an empty alpha channel
    (RGBA, alpha=0) so the resulting video can be overlaid on any slide
    background. Title and underline are still drawn — they're part of
    the artwork that should be visible."""
    if transparent:
        img = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    else:
        img = Image.new("RGB", (CANVAS_W, CANVAS_H), (255, 255, 255))
    d = ImageDraw.Draw(img)

    if title and title_font:
        bb = title_font.getbbox(title)
        tw = bb[2] - bb[0]
        d.text(((CANVAS_W - tw) // 2, 40), title, font=title_font, fill=(40, 60, 140))
        d.line([(MARGIN_X, 130), (CANVAS_W - MARGIN_X, 130)], fill=(120, 140, 200), width=3)

    total = len(chars)
    cur_idx = total - 1
    for i, start in enumerate(char_step_starts):
        if step_idx < start + char_substeps[i]:
            cur_idx = i
            break

    # Track underline segments we need to draw — one per consecutive run
    # of underlined chars that have been at least partially revealed.
    underline_segs: list[tuple[int, int, int, tuple[int, int, int]]] = []  # (x0, x1, y, color)
    cur_underline: Optional[dict] = None

    def _commit_underline():
        nonlocal cur_underline
        if cur_underline:
            underline_segs.append((
                cur_underline["x0"], cur_underline["x1"],
                cur_underline["y"], cur_underline["color"],
            ))
            cur_underline = None

    # 1) Fully drawn characters before the current one.
    for i in range(cur_idx):
        c = chars[i]
        ch, cx, cy = c["ch"], c["x"], c["y"]
        color = c.get("color", DEFAULT_INK_COLOR)
        bold = c.get("bold", False)
        underline = c.get("underline", False)
        entry = glyph_cache.get(ch)
        char_w = int(entry["width"] + entry["left"]) if entry else 0
        if entry is not None:
            full = _make_glyph_image(entry, len(entry["reveal_masks"]) - 1, color, bold)
            img.paste(full, (cx + entry["left"], cy + entry["top"]), full)
        # Underline tracking — extend or commit segments based on the
        # contiguity of underlined chars on the SAME baseline.
        if underline:
            char_right = cx + (char_w if entry else 0) + (1 if bold else 0)
            if (cur_underline
                    and cur_underline["y"] == cy
                    and cur_underline["color"] == color
                    and cur_underline["x1"] >= cx - 4):
                cur_underline["x1"] = char_right
            else:
                _commit_underline()
                cur_underline = {
                    "x0": cx, "x1": char_right, "y": cy, "color": color,
                }
        else:
            _commit_underline()

    # 2) Partial current character.
    c = chars[cur_idx]
    ch, cx, cy = c["ch"], c["x"], c["y"]
    color = c.get("color", DEFAULT_INK_COLOR)
    bold = c.get("bold", False)
    underline_cur = c.get("underline", False)
    entry = glyph_cache.get(ch)
    pen_x: Optional[int] = None
    pen_y: Optional[int] = None
    if entry is None:
        pen_x = cx
        pen_y = cy + int(0.55 * (chars[0]["y"] if False else 60))
    else:
        sub_in_char = step_idx - char_step_starts[cur_idx]
        substeps = char_substeps[cur_idx]
        sub_in_char = max(0, min(substeps - 1, sub_in_char))
        partial = _make_glyph_image(entry, sub_in_char, color, bold)
        img.paste(partial, (cx + entry["left"], cy + entry["top"]), partial)

        pen_local = entry["pen_positions"][sub_in_char]
        pen_x = cx + entry["left"] + pen_local[0]
        pen_y = cy + entry["top"] + pen_local[1]

        if underline_cur:
            # Progressive underline for the char being drawn: extend
            # `x1` to the current pen X to keep the line under the
            # already-written portion.
            char_right = max(cx + 2, pen_x)
            if (cur_underline
                    and cur_underline["y"] == cy
                    and cur_underline["color"] == color
                    and cur_underline["x1"] >= cx - 4):
                cur_underline["x1"] = char_right
            else:
                _commit_underline()
                cur_underline = {
                    "x0": cx, "x1": char_right, "y": cy, "color": color,
                }
    _commit_underline()

    # 3) Draw collected underline segments. Place the line just under
    # the baseline of the glyph (cy + font_metric * 0.95) and use a
    # thickness that scales with the font size we inferred from the
    # first cached glyph (height proxy).
    if underline_segs and glyph_cache:
        sample = next((v for v in glyph_cache.values() if v is not None), None)
        if sample is not None:
            base_h = sample["height"]
            line_y_off = int(base_h * 0.92)
            line_thick = max(2, base_h // 28)
            for x0, x1, y, col in underline_segs:
                d.line(
                    [(x0, y + line_y_off), (x1, y + line_y_off)],
                    fill=col, width=line_thick,
                )

    # 3) Pen overlay.
    if pen_x is not None and pen_y is not None:
        tip_x = pen_x + HAND_OFFSET_X
        tip_y = pen_y + HAND_OFFSET_Y
        img.paste(hand_img, (tip_x, tip_y), hand_img)

    return img


# ---------------------------------------------------------------------------
# Eraser-at-end animation
# ---------------------------------------------------------------------------
#
# Goal: simulate a classroom-style felt eraser sweeping the text away in
# horizontal stripes (left → right, top → bottom). This is appended AFTER
# the writing + dwell phases when `erase_at_end=True`. The result is a
# self-contained "write → pause → erase" clip the author can chain on the
# Timeline with multiple Whiteboard videos without seeing the prior text.

ERASER_COLOR = (110, 110, 115)       # dark gray "felt" body
ERASER_HIGHLIGHT = (170, 170, 175)   # subtle top edge highlight


def _compute_text_band(chars: list, font_size: int) -> tuple[int, int]:
    """Return (y_top, y_bottom) of the text area to erase, in canvas coords."""
    if not chars:
        return MARGIN_Y, MARGIN_Y + int(font_size * 1.2)
    y_top = min(int(c["y"]) for c in chars)
    line_h = int(font_size * 1.2)
    y_bottom = max(int(c["y"]) + line_h for c in chars)
    # Add a bit of padding for ascenders/descenders.
    return max(0, y_top - 8), min(CANVAS_H, y_bottom + 8)


def _render_final_text_layer(
    chars: list,
    glyph_cache: dict,
    transparent: bool,
) -> Image.Image:
    """Render the "all chars fully drawn" image WITHOUT title/underline/hand.
    Used as a baseline that the erase animation progressively masks away."""
    img = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    for c in chars:
        ch, cx, cy = c["ch"], c["x"], c["y"]
        color = c.get("color", DEFAULT_INK_COLOR)
        bold = c.get("bold", False)
        underline = c.get("underline", False)
        entry = glyph_cache.get(ch)
        if entry is None:
            continue
        full = _make_glyph_image(entry, len(entry["reveal_masks"]) - 1, color, bold)
        img.paste(full, (cx + entry["left"], cy + entry["top"]), full)
        if underline:
            char_w = int(entry["width"] + entry["left"]) + (1 if bold else 0)
            thickness = max(2, int(font_size_from_entry(entry) / 28))
            uy = cy + int(font_size_from_entry(entry) * 0.92)
            d = ImageDraw.Draw(img)
            d.line([(cx, uy), (cx + char_w, uy)], fill=color, width=thickness)
    return img


def font_size_from_entry(entry: dict) -> int:
    """Best-effort font-size estimate from a glyph entry (its mask height)."""
    # `reveal_masks[-1]` is the final-shape glyph; its height ≈ font size.
    masks = entry.get("reveal_masks") or []
    if masks:
        return masks[-1].height
    return 80  # safe default


def _build_erase_schedule(
    text_band: tuple[int, int],
    font_size: int,
    chars_per_second: float,
    has_title: bool = False,
) -> tuple[list[tuple[int, int]], int, int, int]:
    """Compute the eraser geometry and per-stripe frame count.

    Returns:
      stripe_bounds: list of (y_top, y_bottom) for each stripe (top→bottom)
      eraser_w: width in px of the eraser block
      eraser_h: height in px of the eraser block (= stripe height)
      frames_per_stripe: how many animation frames per horizontal pass

    When `has_title` is True a "title stripe" covering y=(20, 140) is
    prepended so the eraser wipes the title in a natural top→bottom
    motion BEFORE moving on to the text. Without this the previous
    whiteboard's title remains visible on the last erase frame, which
    leaks into the next clip when chaining Whiteboards on the Timeline.
    """
    y_top, y_bottom = text_band
    band_h = max(1, y_bottom - y_top)
    eraser_h = max(60, int(font_size * 1.05))
    num_stripes = max(1, (band_h + eraser_h - 1) // eraser_h)
    # Distribute stripes evenly inside the band so the last one doesn't overshoot.
    stripe_h = band_h // num_stripes
    stripe_bounds: list[tuple[int, int]] = []
    for i in range(num_stripes):
        y0 = y_top + i * stripe_h
        y1 = y_top + (i + 1) * stripe_h if i < num_stripes - 1 else y_bottom
        stripe_bounds.append((y0, y1))
    if has_title:
        # Title stripe sits at the top (y=20..140 captures title + underline).
        stripe_bounds.insert(0, (20, 140))
    eraser_w = max(140, int(font_size * 2.4))
    # Speed: ~2.5x faster than writing. For a 1920px sweep we want ~0.5s
    # per stripe at typical writing speeds, clamped to a usable range.
    erase_cps = max(2.0, chars_per_second * 2.5)
    # Approximate "chars" per stripe to keep timing intuitive.
    chars_per_stripe = max(8, int((CANVAS_W - 2 * MARGIN_X) / max(1, font_size * 0.6)))
    stripe_seconds = max(0.35, min(1.2, chars_per_stripe / erase_cps))
    frames_per_stripe = max(8, int(round(stripe_seconds * FPS)))
    return stripe_bounds, eraser_w, eraser_h, frames_per_stripe


def _render_frame_erasing(
    erase_step: int,
    total_erase_steps_per_stripe: int,
    stripe_bounds: list[tuple[int, int]],
    eraser_w: int,
    final_text_layer: Image.Image,
    title: Optional[str],
    title_font,
    transparent: bool,
    erase_style: str = "horizontal",
) -> Image.Image:
    """Render a single erase-phase frame at `erase_step` (global step index
    across all stripes).

    `erase_style`:
      - "horizontal" (default): every stripe sweeps left→right.
      - "zigzag": alternating stripes reverse direction (L→R, R→L, L→R, …),
        producing a continuous serpentine eraser path — feels more like a
        teacher quickly wiping the board than a robotic raster scan.

    Title and text are composited into a single "content" layer and then
    masked together — this way the eraser also wipes the title when its
    stripe is included in `stripe_bounds` (built via
    `_build_erase_schedule(has_title=True)`). On the very last erase
    frame the eraser block itself is omitted so the clip ends on a fully
    clean canvas (no leftover gray block visible when chained on the
    Timeline)."""
    if transparent:
        img = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    else:
        img = Image.new("RGB", (CANVAS_W, CANVAS_H), (255, 255, 255))

    stripe_idx = min(len(stripe_bounds) - 1, erase_step // total_erase_steps_per_stripe)
    step_in_stripe = erase_step - stripe_idx * total_erase_steps_per_stripe
    sweep = step_in_stripe / max(1, total_erase_steps_per_stripe - 1)
    sweep = min(1.0, max(0.0, sweep))

    # Direction for the current stripe. Zig-zag flips every other stripe
    # so the eraser doesn't teleport back to the left edge between rows.
    reverse = (erase_style == "zigzag") and (stripe_idx % 2 == 1)

    # Build a mask of where content is STILL visible.
    # Mask == 255 keeps pixels, 0 hides them.
    mask = Image.new("L", (CANVAS_W, CANVAS_H), 255)
    md = ImageDraw.Draw(mask)
    # Past stripes — fully erased.
    for i in range(stripe_idx):
        y0, y1 = stripe_bounds[i]
        md.rectangle([(0, y0), (CANVAS_W, y1)], fill=0)
    # Current stripe — erase progressively from one edge to the other.
    y0, y1 = stripe_bounds[stripe_idx]
    left_bound = MARGIN_X
    right_bound = CANVAS_W - MARGIN_X
    if reverse:
        # Right-to-left: erase from the right edge inward.
        sweep_x_left = int(right_bound - sweep * (right_bound - left_bound))
        if sweep_x_left < CANVAS_W:
            md.rectangle([(sweep_x_left, y0), (CANVAS_W, y1)], fill=0)
        # Eraser block at the leading edge (its left face is the wipe front).
        ex_right = min(right_bound, sweep_x_left + eraser_w // 2)
        ex_left = max(left_bound, ex_right - eraser_w)
    else:
        # Left-to-right (default).
        sweep_x_right = int(left_bound + sweep * (right_bound - left_bound))
        if sweep_x_right > 0:
            md.rectangle([(0, y0), (sweep_x_right, y1)], fill=0)
        ex_left = max(left_bound, sweep_x_right - eraser_w // 2)
        ex_right = min(right_bound, ex_left + eraser_w)

    # Build a combined content layer (title + final text) so a single mask
    # wipes both. The title used to be drawn directly on the frame which
    # meant the eraser couldn't touch it — now the title stripe (when
    # present in stripe_bounds) properly erases it.
    content = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    if title and title_font:
        td = ImageDraw.Draw(content)
        bb = title_font.getbbox(title)
        tw = bb[2] - bb[0]
        td.text(((CANVAS_W - tw) // 2, 40), title, font=title_font, fill=(40, 60, 140))
        td.line(
            [(MARGIN_X, 130), (CANVAS_W - MARGIN_X, 130)],
            fill=(120, 140, 200), width=3,
        )
    if final_text_layer is not None:
        content.alpha_composite(final_text_layer)

    # Composite the masked content onto our background.
    if transparent:
        alpha = content.split()[3]
        new_alpha = ImageChops.multiply(alpha, mask)
        content.putalpha(new_alpha)
        img = Image.alpha_composite(img, content)
    else:
        # On white BG: flatten content first, then paste using mask.
        flat = Image.new("RGB", (CANVAS_W, CANVAS_H), (255, 255, 255))
        flat.paste(content, (0, 0), content)
        img.paste(flat, (0, 0), mask)
    d = ImageDraw.Draw(img)

    # Draw the eraser block — UNLESS this is the final frame of the final
    # stripe. Keeping the block on the last frame leaves a gray rectangle
    # on screen that visually contaminates the next clip when chained.
    is_last_frame = (
        stripe_idx == len(stripe_bounds) - 1
        and step_in_stripe >= total_erase_steps_per_stripe - 1
    )
    if not is_last_frame:
        d.rounded_rectangle(
            [(ex_left, y0), (ex_right, y1)],
            radius=8, fill=ERASER_COLOR,
        )
        # Thin highlight along the top of the eraser for a subtle 3D feel.
        d.rectangle(
            [(ex_left + 4, y0 + 4), (ex_right - 4, y0 + 10)],
            fill=ERASER_HIGHLIGHT,
        )
    return img


async def render_whiteboard_video(
    text: str,
    title: Optional[str] = None,
    font_size: int = FONT_SIZE_DEFAULT,
    chars_per_second: float = 19.0,
    dwell_end_seconds: float = 1.5,
    font_family: Optional[str] = None,
    transparent: bool = False,
    ink_color: Optional[tuple[int, int, int]] = None,
    text_html: Optional[str] = None,
    erase_at_end: bool = False,
    erase_style: str = "horizontal",
) -> tuple[str, dict]:
    """Synthesize a whiteboard video from `text` (or rich `text_html`).

    When `text_html` is provided, inline `<span style="color:#XXX">` and
    `<font color="#XXX">` segments are honored — each character is drawn
    in its segment's color. Otherwise the global `ink_color` (default
    near-black) is applied to the whole text.
    """
    if not (text and text.strip()) and not (text_html and text_html.strip()):
        raise ValueError("text must not be empty")

    font_path = _resolve_font_path(font_family)
    default_color = ink_color if ink_color else DEFAULT_INK_COLOR
    font, chars = _layout(
        text, font_size, font_path,
        default_color=default_color,
        text_html=text_html,
    )
    total = len(chars)
    if total == 0:
        raise ValueError("layout produced 0 characters (only whitespace?)")

    title_font = None
    if title:
        title_font = ImageFont.truetype(str(font_path), int(font_size * 0.9))

    hand_img = Image.open(HAND_PATH).convert("RGBA")
    hand_target_h = int(font_size * 2.2)
    hand_scale = hand_target_h / hand_img.height
    hand_img = hand_img.resize(
        (int(hand_img.width * hand_scale), hand_target_h),
        Image.LANCZOS,
    )

    # Sub-steps per character control how many distinct pen positions
    # are visible per letter. To FEEL like writing motion the pen has
    # to land on a different point in many consecutive frames, so we
    # tie sub-steps to the **frames per character** budget instead of
    # using a fixed default:
    #   frames_per_char = FPS / chars_per_second
    #   sub_default     ≈ frames_per_char (1 substep per frame)
    # This is then clamped to [6, 24]; the lower bound guarantees a
    # visible trace even at very high cps (we *slow down* the overall
    # animation if needed to keep ≥6 frames per char — see duration
    # calculation below).
    frames_per_char = FPS / max(0.1, chars_per_second)
    sub_default = max(6, min(24, int(round(frames_per_char))))

    glyph_cache = _build_glyph_cache(chars, font, sub_default)

    char_substeps: list[int] = []
    for entry in chars:
        ch = entry["ch"]
        if glyph_cache.get(ch) is None:
            char_substeps.append(2)
        else:
            char_substeps.append(sub_default)

    total_substeps = sum(char_substeps)
    char_step_starts: list[int] = []
    acc = 0
    for s in char_substeps:
        char_step_starts.append(acc)
        acc += s

    # Duration: requested by user as total_chars/cps, BUT we also
    # enforce a minimum of 1 frame per substep so every pen position
    # is actually visible. Whichever is longer wins. For cps > ~5 the
    # min-substep constraint kicks in and slightly slows down playback
    # — a worthwhile tradeoff for a visible writing motion.
    requested_duration_sec = total / max(0.1, chars_per_second)
    min_duration_sec = total_substeps / FPS
    duration_sec = max(requested_duration_sec, min_duration_sec)
    total_anim_frames = max(1, int(round(duration_sec * FPS)))
    dwell_frames = int(FPS * dwell_end_seconds)
    total_frames = total_anim_frames + dwell_frames

    # Optional erase-at-end phase: append frames where a felt-eraser
    # block sweeps the text away in horizontal stripes. Pre-render the
    # final text layer once so the erase frames just composite a masked
    # version of it.
    erase_meta: dict = {}
    final_text_layer = None
    stripe_bounds: list[tuple[int, int]] = []
    eraser_w = 0
    frames_per_stripe = 0
    total_erase_frames = 0
    if erase_at_end:
        text_band = _compute_text_band(chars, font_size)
        stripe_bounds, eraser_w, _eraser_h, frames_per_stripe = _build_erase_schedule(
            text_band, font_size, chars_per_second,
            has_title=bool(title),
        )
        total_erase_frames = len(stripe_bounds) * frames_per_stripe
        # Build the final image to be masked. We render it without title /
        # underline / hand — those are redrawn each erase frame.
        final_text_layer = _render_final_text_layer(chars, glyph_cache, transparent)
        erase_meta = {
            "eraseStripes": len(stripe_bounds),
            "eraseFrames": total_erase_frames,
            "eraseDuration": total_erase_frames / FPS,
        }
    total_frames_with_erase = total_frames + total_erase_frames

    video_id = f"wb_{uuid.uuid4().hex[:12]}"
    if transparent:
        # Transparent output: animated PNG. VP9-alpha and VP8-alpha
        # WebM encoders in our bundled ffmpeg silently strip the alpha
        # channel during encode (verified), so APNG is the most reliable
        # format. Modern browsers (Chrome/Firefox/Safari/Edge) play it
        # natively in <img> tags with full alpha. Larger files than VP9
        # but acceptable for short animations.
        ext = "png"  # APNG uses .png extension
        out_path = OUTPUT_DIR / f"{video_id}.{ext}"
        ffmpeg_bin = _resolve_ffmpeg_binary()
        await asyncio.to_thread(
            _write_apng_via_ffmpeg,
            ffmpeg_bin, out_path, CANVAS_W, CANVAS_H, FPS,
            total_frames, total_anim_frames, total_substeps,
            chars, glyph_cache, char_substeps, char_step_starts,
            hand_img, title, title_font,
            final_text_layer, stripe_bounds, eraser_w, frames_per_stripe,
            erase_style,
        )
        info_format = "apng"
    else:
        # H.264 MP4 on white canvas — broad LMS compatibility.
        ext = "mp4"
        out_path = OUTPUT_DIR / f"{video_id}.{ext}"
        os.environ["IMAGEIO_FFMPEG_EXE"] = _resolve_ffmpeg_binary()
        writer = imageio.get_writer(
            str(out_path), format="FFMPEG",
            mode="I", fps=FPS,
            codec="libx264", pixelformat="yuv420p",
            macro_block_size=None,
            ffmpeg_log_level="error",
            output_params=["-movflags", "+faststart"],
        )
        try:
            await asyncio.to_thread(
                _write_all_frames,
                writer, total_frames, total_anim_frames, total_substeps,
                chars, glyph_cache, char_substeps, char_step_starts,
                hand_img, title, title_font, False,
                final_text_layer, stripe_bounds, eraser_w, frames_per_stripe,
                erase_style,
            )
        finally:
            writer.close()
        info_format = "mp4"

    file_size = out_path.stat().st_size
    logger.info(
        "whiteboard: rendered %s.%s (%d frames write+dwell, %d erase, %.1fs total, %.1f KB, transparent=%s)",
        video_id, ext, total_frames, total_erase_frames,
        total_frames_with_erase / FPS, file_size / 1024, transparent,
    )
    # Release heavy intermediate buffers and force a GC pass before
    # returning. Each render holds ~50–100MB of glyph cache + the
    # final_text_layer; on memory-tight production containers we want
    # them gone before the next job starts (or before the API process
    # services unrelated requests). The explicit `gc.collect()` is
    # needed because PIL Images often live in cyclic references.
    try:
        glyph_cache.clear()
    except Exception:
        pass
    final_text_layer = None  # noqa: F841 — break ref for GC
    import gc as _gc
    _gc.collect()
    return f"/api/whiteboard/file/{video_id}.{ext}", {
        "videoId": video_id,
        "duration": total_frames_with_erase / FPS,
        "frames": total_frames_with_erase,
        "totalChars": total,
        "fileSize": file_size,
        "transparent": transparent,
        "format": info_format,
        "eraseAtEnd": bool(erase_at_end),
        "eraseStyle": erase_style if erase_at_end else None,
        **erase_meta,
    }


def _write_apng_via_ffmpeg(
    ffmpeg_bin: str, out_path: Path, width: int, height: int, fps: int,
    total_frames: int, total_anim_frames: int, total_substeps: int,
    chars, glyph_cache, char_substeps, char_step_starts,
    hand_img, title: Optional[str], title_font,
    final_text_layer: Optional[Image.Image] = None,
    stripe_bounds: Optional[list] = None,
    eraser_w: int = 0,
    frames_per_stripe: int = 0,
    erase_style: str = "horizontal",
) -> None:
    """Encode an animated PNG by piping raw RGBA frames into ffmpeg's
    APNG encoder. APNG preserves the alpha channel losslessly — the only
    format we can reliably produce with transparency in this env.

    When `final_text_layer` + `stripe_bounds` are provided, an erase
    animation is appended after the write+dwell phase."""
    import subprocess
    total_erase_frames = (
        len(stripe_bounds) * frames_per_stripe if stripe_bounds else 0
    )
    grand_total = total_frames + total_erase_frames
    proc = subprocess.Popen(
        [ffmpeg_bin, "-y", "-loglevel", "error",
         "-f", "rawvideo", "-pix_fmt", "rgba",
         "-s", f"{width}x{height}", "-r", str(fps),
         "-i", "-",
         "-c:v", "apng", "-f", "apng", "-plays", "1",
         "-pred", "mixed",  # better compression for APNG
         str(out_path)],
        stdin=subprocess.PIPE,
    )
    try:
        for f in range(grand_total):
            if f < total_frames:
                # Write + dwell phase
                if f < total_anim_frames:
                    step_idx = min(
                        total_substeps - 1,
                        int(f * total_substeps / max(1, total_anim_frames)),
                    )
                else:
                    step_idx = total_substeps - 1
                frame = _render_frame_writing(
                    step_idx, chars, glyph_cache,
                    char_substeps, char_step_starts, hand_img,
                    title=title, title_font=title_font,
                    transparent=True,
                )
            else:
                # Erase phase
                erase_step = f - total_frames
                frame = _render_frame_erasing(
                    erase_step, frames_per_stripe, stripe_bounds, eraser_w,
                    final_text_layer, title, title_font, transparent=True,
                    erase_style=erase_style,
                )
            arr = np.asarray(frame, dtype=np.uint8)
            # Ensure 4-channel RGBA.
            if arr.shape[-1] == 3:
                alpha = np.full((arr.shape[0], arr.shape[1], 1), 255, dtype=np.uint8)
                arr = np.concatenate([arr, alpha], axis=-1)
            proc.stdin.write(arr.tobytes())
            # Free per-frame PIL Image and numpy array eagerly. Without
            # this Python's GC waits longer and peak RSS climbs ~2× —
            # critical in production where container memory limits are
            # tight and a single OOM kill makes the whole job 502.
            del frame, arr
    finally:
        try:
            proc.stdin.close()
        except Exception:  # noqa: BLE001
            pass
        proc.wait(timeout=60)
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg APNG encode failed (rc={proc.returncode})")


def _write_all_frames(
    writer, total_frames: int, total_anim_frames: int, total_substeps: int,
    chars, glyph_cache, char_substeps, char_step_starts,
    hand_img, title: Optional[str], title_font, transparent: bool = False,
    final_text_layer: Optional[Image.Image] = None,
    stripe_bounds: Optional[list] = None,
    eraser_w: int = 0,
    frames_per_stripe: int = 0,
    erase_style: str = "horizontal",
) -> None:
    """Synchronous hot loop, offloaded via asyncio.to_thread.

    When `final_text_layer` + `stripe_bounds` are provided, the loop also
    emits an erase animation after the writing+dwell phase."""
    total_erase_frames = (
        len(stripe_bounds) * frames_per_stripe if stripe_bounds else 0
    )
    grand_total = total_frames + total_erase_frames
    for f in range(grand_total):
        if f < total_frames:
            if f < total_anim_frames:
                step_idx = min(
                    total_substeps - 1,
                    int(f * total_substeps / max(1, total_anim_frames)),
                )
            else:
                step_idx = total_substeps - 1
            frame = _render_frame_writing(
                step_idx, chars, glyph_cache,
                char_substeps, char_step_starts, hand_img,
                title=title, title_font=title_font,
                transparent=transparent,
            )
        else:
            erase_step = f - total_frames
            frame = _render_frame_erasing(
                erase_step, frames_per_stripe, stripe_bounds, eraser_w,
                final_text_layer, title, title_font, transparent=transparent,
                erase_style=erase_style,
            )
        # imageio's FFMPEG writer accepts both RGB and RGBA arrays —
        # when yuva420p is the pixel format, RGBA arrays carry the
        # alpha plane through to the encoder.
        writer.append_data(np.asarray(frame))
        # Eagerly release the per-frame Image to bound peak RSS.
        del frame
