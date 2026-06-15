"""Whiteboard / Hand-writer video renderer.

Self-hosted MVP for generating "Doodly/VideoScribe-style" explainer
videos where a hand-with-marker progressively writes text on a white
canvas. No external API dependency — uses Pillow for frame composition
+ imageio-ffmpeg for MP4 encoding.

Pipeline:
1. Layout the script text on a 1920x1080 white canvas with handwriting
   font (Caveat). Layout is precomputed so we know each character's
   pixel position and bounding box.
2. For each frame, render a mask that REVEALS characters left-to-right
   based on the writing progress (0 → 1).
3. Overlay the hand+marker PNG with its writing tip aligned to the
   current "pen position" (next unrevealed character's left edge).
4. Encode the resulting frame stream as H.264 MP4 via imageio-ffmpeg.

The output MP4 is saved to /app/backend/storage/whiteboard/<id>.mp4 and
served as a static asset. Slides can reference it as `videoUrl` in the
SCORM export.
"""
from __future__ import annotations

import os
import uuid
import asyncio
import logging
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont
import imageio
import imageio_ffmpeg  # noqa: F401  # ensures binary is bundled

logger = logging.getLogger("server.whiteboard")

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets" / "whiteboard"
FONT_PATH = ASSETS_DIR / "Caveat-Regular.ttf"
HAND_PATH = ASSETS_DIR / "hand.png"
OUTPUT_DIR = Path(os.environ.get("STORAGE_DIR", "/app/backend/storage")) / "whiteboard"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Canvas dimensions — 1920x1080 matches SCORM export aspect ratio so the
# whiteboard slide drops in without letterboxing.
CANVAS_W, CANVAS_H = 1920, 1080
MARGIN_X, MARGIN_Y = 140, 140
FONT_SIZE_DEFAULT = 84
LINE_SPACING = 1.25  # multiplier of font size
FRAMES_PER_CHAR = 1.6  # at 30fps this is ~19 chars/sec — natural pen speed
FPS = 30
HAND_OFFSET_X = -10  # writing tip horizontal nudge so it touches char start
HAND_OFFSET_Y = -20  # vertical nudge so the tip aligns with char baseline


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Greedy word-wrap that respects explicit `\n` line breaks."""
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
    The character list IS the temporal sequence the pen will follow."""
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


def _render_frame(
    chars_visible: int, total_chars: int,
    chars: list[tuple[str, int, int]],
    font: ImageFont.FreeTypeFont,
    hand_img: Image.Image,
    title: Optional[str] = None,
    title_font: Optional[ImageFont.FreeTypeFont] = None,
) -> Image.Image:
    """Render a single MP4 frame at the given character reveal progress."""
    img = Image.new("RGB", (CANVAS_W, CANVAS_H), (255, 255, 255))
    d = ImageDraw.Draw(img)

    # Optional title (rendered upfront, never animated — context for the
    # body text the hand is about to write).
    if title and title_font:
        bb = title_font.getbbox(title)
        tw = bb[2] - bb[0]
        d.text(((CANVAS_W - tw) // 2, 40), title, font=title_font, fill=(40, 60, 140))
        d.line([(MARGIN_X, 130), (CANVAS_W - MARGIN_X, 130)], fill=(120, 140, 200), width=3)

    # Draw the already-written characters at fixed positions.
    for ch, x, y in chars[:chars_visible]:
        d.text((x, y), ch, font=font, fill=(20, 20, 20))

    # Hand at the position of the NEXT char (or last char if done).
    if chars:
        if chars_visible < total_chars:
            _, hx, hy = chars[chars_visible]
        else:
            _, hx, hy = chars[-1]
            hx += int(font.getlength(chars[-1][0]))  # past the last char
        # Paste hand so its tip (0,0 in the asset) lands at (hx, hy).
        tip_x = hx + HAND_OFFSET_X
        tip_y = hy + HAND_OFFSET_Y
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

    Returns (relative_url, info_dict). The video is encoded H.264 yuv420p
    so it plays in every SCORM viewer (including Articulate, Moodle,
    Cornerstone)."""
    if not text or not text.strip():
        raise ValueError("text must not be empty")

    # Layout precomputation — this is fast (<10ms even for long scripts).
    font, chars = _layout(text, font_size)
    total = len(chars)
    if total == 0:
        raise ValueError("layout produced 0 characters (only whitespace?)")

    title_font = None
    if title:
        title_font = ImageFont.truetype(str(FONT_PATH), int(font_size * 0.9))

    hand_img = Image.open(HAND_PATH).convert("RGBA")
    # Scale hand proportionally to font size so it never looks oversized
    # on small fonts or tiny on huge ones.
    hand_target_h = int(font_size * 3.0)
    hand_scale = hand_target_h / hand_img.height
    hand_img = hand_img.resize(
        (int(hand_img.width * hand_scale), hand_target_h),
        Image.LANCZOS,
    )

    # Frame schedule: how many chars are revealed at each frame.
    # frames_per_char accounts for the requested chars_per_second.
    frames_per_char = max(1, int(FPS / chars_per_second))
    total_anim_frames = total * frames_per_char
    dwell_frames = int(FPS * dwell_end_seconds)
    total_frames = total_anim_frames + dwell_frames

    video_id = f"wb_{uuid.uuid4().hex[:12]}"
    out_path = OUTPUT_DIR / f"{video_id}.mp4"

    # Encode via imageio (uses bundled ffmpeg binary). yuv420p for
    # universal LMS player compatibility.
    writer = imageio.get_writer(
        str(out_path), format="FFMPEG",
        mode="I", fps=FPS,
        codec="libx264", pixelformat="yuv420p",
        macro_block_size=None,  # 1920x1080 already divisible
        ffmpeg_log_level="error",
        output_params=["-movflags", "+faststart"],
    )
    try:
        await asyncio.to_thread(
            _write_all_frames,
            writer, total_frames, total_anim_frames, total,
            frames_per_char, chars, font, hand_img, title, title_font,
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
    writer, total_frames: int, total_anim_frames: int, total_chars: int,
    frames_per_char: int, chars, font, hand_img,
    title: Optional[str], title_font,
) -> None:
    """Hot loop kept out of the async function to keep the to_thread
    handoff minimal. CPU-bound — we run inside a worker thread."""
    for f in range(total_frames):
        if f < total_anim_frames:
            chars_visible = min(total_chars, f // frames_per_char)
        else:
            chars_visible = total_chars
        frame = _render_frame(
            chars_visible, total_chars, chars, font, hand_img,
            title=title, title_font=title_font,
        )
        writer.append_data(_pil_to_array(frame))


def _pil_to_array(img: Image.Image):
    """PIL Image -> numpy array for imageio.append_data."""
    import numpy as np
    return np.asarray(img)
