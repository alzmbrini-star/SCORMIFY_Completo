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
import uuid
import asyncio
import logging
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont
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
FONT_PATH = ASSETS_DIR / "Caveat-Regular.ttf"
HAND_PATH = ASSETS_DIR / "hand.png"
OUTPUT_DIR = Path(os.environ.get("STORAGE_DIR", "/app/backend/storage")) / "whiteboard"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

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


def _layout(text: str, font_size: int) -> tuple[ImageFont.FreeTypeFont, list[tuple[str, int, int]]]:
    """Return (font, characters) where each character is (char, x, y)."""
    font = ImageFont.truetype(str(FONT_PATH), font_size)
    max_w = CANVAS_W - 2 * MARGIN_X
    lines = _wrap_text(text, font, max_w)
    line_h = int(font_size * LINE_SPACING)
    chars: list[tuple[str, int, int]] = []
    y = MARGIN_Y
    for line in lines:
        x = MARGIN_X
        for ch in line:
            chars.append((ch, x, y))
            adv = font.getlength(ch)
            x += int(adv)
        y += line_h
    return font, chars


def _disk_mask(radius: int) -> np.ndarray:
    """Return a (2r+1, 2r+1) bool disk mask."""
    r = max(1, radius)
    yy, xx = np.ogrid[-r:r + 1, -r:r + 1]
    return (xx * xx + yy * yy) <= r * r


def _build_glyph_cache(
    chars: list[tuple[str, int, int]],
    font: ImageFont.FreeTypeFont,
    sub_steps: int,
):
    """Per-unique-glyph precompute everything the frame loop needs.

    For each character we cache:
      - glyph_rgba: full Pillow RGBA of the rendered glyph.
      - reveal_masks: list of bool arrays (len = sub_steps), each a
        progressively-larger mask of the glyph "visible" at that step.
      - path: list of (x, y) skeleton points in writing order.
      - left, top: bbox offsets so the renderer can paste the glyph
        back at the right canvas coordinates.
      - pen_positions: per sub-step the pen tip (x, y) **relative to
        the glyph image origin (0,0)**.

    Whitespace and zero-width chars map to None.
    """
    cache: dict[str, Optional[dict]] = {}
    for ch, _, _ in chars:
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

def _make_glyph_image(entry: dict, reveal_idx: int) -> Image.Image:
    """Apply the cumulative reveal mask of the given sub-step to the
    glyph's RGBA copy, producing a partial glyph image. The mask zeroes
    out pixels not yet 'written'."""
    glyph = entry["glyph"]
    mask = entry["reveal_masks"][reveal_idx]
    arr = np.array(glyph)  # writable copy
    arr[..., 3] = np.where(mask, arr[..., 3], 0)
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
) -> Image.Image:
    """Render a single MP4 frame at the given **sub-step** index."""
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

    # 1) Fully drawn characters before the current one.
    for i in range(cur_idx):
        ch, cx, cy = chars[i]
        entry = glyph_cache.get(ch)
        if entry is None:
            continue
        full = _make_glyph_image(entry, len(entry["reveal_masks"]) - 1)
        img.paste(full, (cx + entry["left"], cy + entry["top"]), full)

    # 2) Partial current character.
    ch, cx, cy = chars[cur_idx]
    entry = glyph_cache.get(ch)
    pen_x: Optional[int] = None
    pen_y: Optional[int] = None
    if entry is None:
        # Whitespace: idle pen at character X position, baseline-ish y.
        pen_x = cx
        pen_y = cy + int(0.55 * (chars[0][2] if False else 60))
    else:
        sub_in_char = step_idx - char_step_starts[cur_idx]
        substeps = char_substeps[cur_idx]
        sub_in_char = max(0, min(substeps - 1, sub_in_char))
        partial = _make_glyph_image(entry, sub_in_char)
        img.paste(partial, (cx + entry["left"], cy + entry["top"]), partial)

        pen_local = entry["pen_positions"][sub_in_char]
        pen_x = cx + entry["left"] + pen_local[0]
        pen_y = cy + entry["top"] + pen_local[1]

    # 3) Pen overlay.
    if pen_x is not None and pen_y is not None:
        tip_x = pen_x + HAND_OFFSET_X
        tip_y = pen_y + HAND_OFFSET_Y
        img.paste(hand_img, (tip_x, tip_y), hand_img)

    return img


async def render_whiteboard_video(
    text: str,
    title: Optional[str] = None,
    font_size: int = FONT_SIZE_DEFAULT,
    chars_per_second: float = 19.0,
    dwell_end_seconds: float = 1.5,
) -> tuple[str, dict]:
    """Synthesize a whiteboard MP4 from `text`."""
    if not text or not text.strip():
        raise ValueError("text must not be empty")

    font, chars = _layout(text, font_size)
    total = len(chars)
    if total == 0:
        raise ValueError("layout produced 0 characters (only whitespace?)")

    title_font = None
    if title:
        title_font = ImageFont.truetype(str(FONT_PATH), int(font_size * 0.9))

    hand_img = Image.open(HAND_PATH).convert("RGBA")
    hand_target_h = int(font_size * 2.2)
    hand_scale = hand_target_h / hand_img.height
    hand_img = hand_img.resize(
        (int(hand_img.width * hand_scale), hand_target_h),
        Image.LANCZOS,
    )

    # Sub-steps per character — controls smoothness of the pen
    # animation. Higher = more frames per letter = smoother but
    # heavier file. ~font_size/8 with clamp gives good defaults.
    sub_default = max(8, min(20, font_size // 6))

    glyph_cache = _build_glyph_cache(chars, font, sub_default)

    char_substeps: list[int] = []
    for ch, _, _ in chars:
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

    duration_sec = total / max(0.1, chars_per_second)
    total_anim_frames = max(1, int(round(duration_sec * FPS)))
    dwell_frames = int(FPS * dwell_end_seconds)
    total_frames = total_anim_frames + dwell_frames

    video_id = f"wb_{uuid.uuid4().hex[:12]}"
    out_path = OUTPUT_DIR / f"{video_id}.mp4"

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
            hand_img, title, title_font,
        )
    finally:
        writer.close()

    file_size = out_path.stat().st_size
    logger.info(
        "whiteboard: rendered %s (%d frames, %.1fs, %.1f KB)",
        video_id, total_frames, total_frames / FPS, file_size / 1024,
    )
    return f"/api/whiteboard/file/{video_id}.mp4", {
        "videoId": video_id,
        "duration": total_frames / FPS,
        "frames": total_frames,
        "totalChars": total,
        "fileSize": file_size,
    }


def _write_all_frames(
    writer, total_frames: int, total_anim_frames: int, total_substeps: int,
    chars, glyph_cache, char_substeps, char_step_starts,
    hand_img, title: Optional[str], title_font,
) -> None:
    """Synchronous hot loop, offloaded via asyncio.to_thread."""
    for f in range(total_frames):
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
        )
        writer.append_data(np.asarray(frame))
