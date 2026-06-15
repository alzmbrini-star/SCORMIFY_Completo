"""Whiteboard / Hand-writer video renderer.

Self-hosted MVP for generating "Doodly/VideoScribe-style" explainer
videos where a pen progressively writes text on a white canvas. No
external API dependency — uses Pillow for frame composition +
imageio-ffmpeg for MP4 encoding.

Writing motion:
-----------------
Instead of revealing whole characters at once, each character is
written column-by-column from left to right. For every column, the
pen tip sits at the **vertical centroid of the ink** in that column,
so for a cursive font (Caveat) the tip naturally rides along the
stroke "river" — visually indistinguishable from real penwork at
this distance and resolution.

Pipeline:
1. Layout the script text on a 1920x1080 white canvas with a
   handwriting font (Caveat). Layout is precomputed.
2. For each unique character, render a small glyph mask offscreen
   and compute its **trace**: for every column index, the (x, y)
   offset where the pen tip should sit when that column has just
   been revealed.
3. Frame schedule: each character gets N **sub-steps**; the pen
   advances one column at a time, revealing the corresponding
   slice of the glyph and moving to the next trace point.
4. Encode the frame stream as H.264 MP4 via imageio-ffmpeg.

Output MP4 is saved to /app/backend/storage/whiteboard/<id>.mp4 and
served as a static asset. Slides reference it as `videoUrl`."""
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
import imageio_ffmpeg  # noqa: F401  # ensures binary is bundled

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

# Canvas dimensions — 1920x1080 matches SCORM export aspect ratio so
# the whiteboard slide drops in without letterboxing.
CANVAS_W, CANVAS_H = 1920, 1080
MARGIN_X, MARGIN_Y = 140, 140
FONT_SIZE_DEFAULT = 84
LINE_SPACING = 1.25  # multiplier of font size
FPS = 30
# Pen asset has its writing tip at the asset's (0, 0). These nudges
# fine-tune so the tip visually rides the ink instead of floating
# above it.
HAND_OFFSET_X = -2
HAND_OFFSET_Y = -4


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
    """Return (font, characters) where each character is (char, x, y).
    The character list is the temporal sequence the pen will follow."""
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


def _build_glyph_cache(chars: list[tuple[str, int, int]], font: ImageFont.FreeTypeFont):
    """For each unique non-whitespace character compute:

        (glyph_rgba, trace, left, top)

    where `glyph_rgba` is the standalone rendered glyph (RGBA, sized
    to its bbox), `trace[i]` is the (dx, dy) offset relative to the
    character's draw origin where the pen tip should rest when
    column `i` has just been written, and (left, top) are the
    glyph's bbox offsets so we know where to paste the partial
    reveal back onto the canvas.

    Whitespace characters and zero-width chars map to None.
    """
    cache: dict[str, Optional[tuple[Image.Image, list[tuple[int, int]], int, int]]] = {}
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
        gd = ImageDraw.Draw(glyph)
        # Draw at (-left, -top) so the visible ink lands inside (0..w, 0..h).
        gd.text((-left, -top), ch, font=font, fill=(20, 20, 20, 255))
        alpha = np.asarray(glyph)[..., 3]
        trace: list[tuple[int, int]] = []
        last_y = h // 2
        for col in range(w):
            rows = np.where(alpha[:, col] > 32)[0]
            if rows.size > 0:
                y_center = int(rows.mean())
                last_y = y_center
            else:
                y_center = last_y  # carry over for gaps / antialias edges
            # Convert back to "offset from character draw origin": the
            # canvas paste origin will be (cx + left, cy + top), so the
            # ink pixel at (col, y_center) of the glyph lives at
            # (cx + left + col, cy + top + y_center).
            trace.append((left + col, top + y_center))
        cache[ch] = (glyph, trace, left, top)
    return cache


def _render_frame_writing(
    step_idx: int,
    chars: list[tuple[str, int, int]],
    glyph_cache: dict,
    char_substeps: list[int],
    char_step_starts: list[int],
    hand_img: Image.Image,
    title: Optional[str] = None,
    title_font: Optional[ImageFont.FreeTypeFont] = None,
) -> Image.Image:
    """Render a single MP4 frame at the given **sub-step** index.

    `char_substeps[i]` is how many sub-steps character `i` consumes.
    `char_step_starts[i]` is the cumulative sub-step where char `i`
    begins. The frame shows:
      - all characters before the current one fully drawn,
      - the current character partially drawn (left-to-right column
        reveal),
      - pen tip riding the ink centroid of the last revealed column.
    """
    img = Image.new("RGB", (CANVAS_W, CANVAS_H), (255, 255, 255))
    d = ImageDraw.Draw(img)

    if title and title_font:
        bb = title_font.getbbox(title)
        tw = bb[2] - bb[0]
        d.text(((CANVAS_W - tw) // 2, 40), title, font=title_font, fill=(40, 60, 140))
        d.line([(MARGIN_X, 130), (CANVAS_W - MARGIN_X, 130)], fill=(120, 140, 200), width=3)

    # Locate the current character index from the cumulative schedule.
    total = len(chars)
    cur_idx = total - 1
    for i, start in enumerate(char_step_starts):
        if step_idx < start + char_substeps[i]:
            cur_idx = i
            break

    # Paste fully completed characters.
    for i in range(cur_idx):
        ch, cx, cy = chars[i]
        entry = glyph_cache.get(ch)
        if entry is None:
            continue
        glyph, _, left, top = entry
        img.paste(glyph, (cx + left, cy + top), glyph)

    # Partial reveal for the current character.
    ch, cx, cy = chars[cur_idx]
    entry = glyph_cache.get(ch)
    pen_x: Optional[int] = None
    pen_y: Optional[int] = None

    if entry is None:
        # Whitespace: no ink to reveal — pen idles slightly to the
        # right of the previous char (or stays where it was).
        # Use the next non-whitespace start (if any) or the char x.
        pen_x = cx
        # Y baseline approximation: middle of line height.
        pen_y = cy + chars[cur_idx][2] - chars[cur_idx][2] + int(0.55 * (chars[cur_idx][2] + 0)) or cy
        pen_y = cy + int(0.7 * (chars[0][2] if False else 0)) + cy  # noqa: F841 -- replaced below
        pen_y = cy + 40  # neutral mid-line placement
    else:
        glyph, trace, left, top = entry
        sub_in_char = step_idx - char_step_starts[cur_idx]
        substeps = char_substeps[cur_idx]
        # Map sub_in_char (0..substeps-1) -> col (0..glyph.width-1).
        progress = (sub_in_char + 1) / substeps
        max_col = max(1, min(glyph.width, int(round(progress * glyph.width))))

        # Crop the glyph to the revealed columns and paste.
        revealed = glyph.crop((0, 0, max_col, glyph.height))
        img.paste(revealed, (cx + left, cy + top), revealed)

        # Pen position: trace of the last revealed column.
        tx, ty = trace[max_col - 1]
        pen_x = cx + tx
        pen_y = cy + ty

    # Compose the pen so its tip (0, 0 in the asset) lands at (pen_x, pen_y).
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
    """Synthesize a whiteboard MP4 from `text`.

    Returns (relative_url, info_dict). The video is encoded H.264
    yuv420p so it plays in every SCORM viewer."""
    if not text or not text.strip():
        raise ValueError("text must not be empty")

    font, chars = _layout(text, font_size)
    total = len(chars)
    if total == 0:
        raise ValueError("layout produced 0 characters (only whitespace?)")

    title_font = None
    if title:
        title_font = ImageFont.truetype(str(FONT_PATH), int(font_size * 0.9))

    # Pen asset — scaled relative to font size for visual balance.
    hand_img = Image.open(HAND_PATH).convert("RGBA")
    hand_target_h = int(font_size * 2.2)
    hand_scale = hand_target_h / hand_img.height
    hand_img = hand_img.resize(
        (int(hand_img.width * hand_scale), hand_target_h),
        Image.LANCZOS,
    )

    # Glyph cache + per-char substep count.
    glyph_cache = _build_glyph_cache(chars, font)
    # Substeps per character: ~ font_size / 10, clamped to [4, 16].
    sub_default = max(4, min(16, font_size // 10))
    char_substeps: list[int] = []
    for ch, _, _ in chars:
        if glyph_cache.get(ch) is None:
            # Whitespace consumes 2 sub-steps so the timing stays
            # roughly proportional to characters-per-second.
            char_substeps.append(2)
        else:
            char_substeps.append(sub_default)

    total_substeps = sum(char_substeps)
    char_step_starts: list[int] = []
    acc = 0
    for s in char_substeps:
        char_step_starts.append(acc)
        acc += s

    # Total animation time follows the requested chars_per_second
    # regardless of how many sub-steps each character actually uses.
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
    """Hot loop kept synchronous so we can offload via asyncio.to_thread."""
    for f in range(total_frames):
        if f < total_anim_frames:
            # Map frame index -> sub-step index linearly.
            step_idx = min(total_substeps - 1, int(f * total_substeps / max(1, total_anim_frames)))
        else:
            step_idx = total_substeps - 1
        frame = _render_frame_writing(
            step_idx, chars, glyph_cache,
            char_substeps, char_step_starts, hand_img,
            title=title, title_font=title_font,
        )
        writer.append_data(np.asarray(frame))
