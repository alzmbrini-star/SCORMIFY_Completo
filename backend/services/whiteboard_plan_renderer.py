"""Render plan executor for the Whiteboard.

Given a plan from `whiteboard_ai_plan` (list of text + shape ops),
produces a video/APNG where the pen sequentially:

  1. Writes each text op left-to-right with a sweep reveal
  2. Traces each shape op along its path

This is intentionally a SIMPLER text renderer than `whiteboard_renderer`
(which does skeleton-traced glyph reveals) — the plan renderer trades
the glyph-by-glyph realism for the flexibility of placing text + shapes
at arbitrary positions, with independent colors per op.

The encoding stage is shared with `whiteboard_renderer` (ffmpeg APNG
or MP4 with yuva420p).
"""
from __future__ import annotations

import asyncio
import gc as _gc
import logging
import subprocess
import uuid
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont
import numpy as np
import imageio

from .whiteboard_renderer import (
    CANVAS_W, CANVAS_H, FPS,
    OUTPUT_DIR, _resolve_tool,
    _resolve_ffmpeg_binary, _resolve_font_path,
)
from . import whiteboard_shapes as ws

logger = logging.getLogger("server.whiteboard_plan")

# Substeps for the text sweep. ~6 chars/sec at FPS=30 ⇒ each char takes
# 5 frames; we keep it simple by using a fixed total substeps per text
# op proportional to the text length.
TEXT_FRAMES_PER_CHAR = 4
HOLD_FRAMES_BETWEEN_OPS = 6   # tiny pause so the eye can land on the new op


async def render_whiteboard_plan(
    plan: dict,
    *,
    font_family: Optional[str] = None,
    transparent: bool = False,
    tool: Optional[str] = None,
) -> tuple[str, dict]:
    """Render the plan and return (relative URL, metadata dict).

    Mirrors the contract of `render_whiteboard_video` so the route
    layer can swap between the two transparently.

    `tool` picks the drawing implement: "pen" (default minimalist pen),
    "hand" (cartoon hand holding a pen) or "hand_real" (photo of a
    real hand in HD). Falls back to "pen" if the requested asset is
    missing on disk.
    """
    ops = plan.get("ops") or []
    if not ops:
        raise ValueError("plan has no operations")

    video_id = f"wb_plan_{uuid.uuid4().hex[:12]}"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Pre-cache hand sprite and font (font reused per text op).
    # Honor the user-selected tool (pen / hand / hand_real). Falls
    # back silently to the default if the asset is missing on disk.
    tool_profile = _resolve_tool(tool)
    hand_img = Image.open(tool_profile["path"]).convert("RGBA")
    hand_target_h = 130
    hand_scale = hand_target_h / hand_img.height
    hand_img = hand_img.resize(
        (int(hand_img.width * hand_scale), hand_target_h),
        Image.Resampling.LANCZOS,
    )
    hand_offset_x = tool_profile["offset_x"]
    hand_offset_y = tool_profile["offset_y"]

    font_path = _resolve_font_path(font_family)

    # Build per-op execution timeline.
    op_specs = []
    total_frames = 0
    for op in ops:
        spec = _prepare_op(op, font_path)
        op_specs.append(spec)
        total_frames += spec["frames"] + HOLD_FRAMES_BETWEEN_OPS

    # Accumulated visible content (drawn ON the canvas for each frame).
    accumulator = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))

    # Encode to APNG or MP4 depending on transparency. We use the `.png`
    # extension for APNG outputs (same convention as the text renderer)
    # so the existing `/api/whiteboard/file/{name}` serving + name
    # validation works without changes.
    if transparent:
        ext = "png"
        info_format = "apng"
    else:
        ext = "mp4"
        info_format = "mp4"
    out_path = OUTPUT_DIR / f"{video_id}.{ext}"

    if transparent:
        await asyncio.to_thread(
            _write_apng_plan,
            out_path, op_specs, accumulator, hand_img,
            hand_offset_x, hand_offset_y,
        )
    else:
        await asyncio.to_thread(
            _write_mp4_plan,
            out_path, op_specs, accumulator, hand_img,
            hand_offset_x, hand_offset_y,
        )

    file_size = out_path.stat().st_size if out_path.exists() else 0
    duration = total_frames / FPS
    logger.info(
        "whiteboard-plan: rendered %s.%s (%d ops, %d frames, %.1fs, %.1f KB)",
        video_id, ext, len(op_specs), total_frames, duration, file_size / 1024,
    )

    # Free buffers before returning (same hygiene as the text renderer).
    accumulator.close()
    hand_img.close()
    _gc.collect()

    return f"/api/whiteboard/file/{video_id}.{ext}", {
        "videoId": video_id,
        "duration": duration,
        "frames": total_frames,
        "fileSize": file_size,
        "transparent": transparent,
        "format": info_format,
        "planOps": len(op_specs),
        "engine": "plan",
    }


# ── op preparation ──────────────────────────────────────────────────


def _prepare_op(op: dict, font_path: Path) -> dict:
    """Resolve everything we'll need at frame-time: rendered text layer,
    path points, frame counts, color. Done once per op so each frame is
    a cheap composite."""
    t = op["type"]
    color = ws.parse_color(op.get("color"), (31, 41, 55))  # default ink: #1f2937
    if t == "text":
        text = op["text"]
        font_size = int(op.get("font_size") or 80)
        font = ImageFont.truetype(str(font_path), font_size)
        # Render the text once into a layer at its target position.
        layer = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.text((op["x"], op["y"]), text, font=font, fill=(*color, 255))
        # Bounding box of the rendered text (so sweep mask is tight).
        bbox = font.getbbox(text)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        # Substep / frame counts derived from char count.
        chars = max(1, len(text))
        frames = chars * TEXT_FRAMES_PER_CHAR
        return {
            "kind": "text",
            "frames": frames,
            "layer": layer,
            "bbox": (op["x"], op["y"], op["x"] + text_w, op["y"] + text_h + 10),
            "color": color,
        }
    # Shapes
    path = ws.path_for_op(op)
    substeps = ws.shape_substeps(t)
    # Roughly 1 frame per 2 substeps for smooth playback.
    frames = max(20, len(path) // 2)
    width = int(op.get("width") or 6)
    return {
        "kind": "shape",
        "frames": frames,
        "path": path,
        "color": color,
        "stroke_width": width,
    }


# ── frame rendering ─────────────────────────────────────────────────


def _compose_frame(
    accumulator: Image.Image,
    op_spec: dict,
    progress: float,
    hand_img: Image.Image,
    hand_offset_x: int,
    hand_offset_y: int,
) -> Image.Image:
    """Build a single frame: background + already-completed ops (from
    accumulator) + the partial current op + hand sprite."""
    frame = accumulator.copy()
    pen_tip: tuple[float, float] | None = None

    if op_spec["kind"] == "text":
        x0, y0, x1, y1 = op_spec["bbox"]
        # Sweep mask reveals text up to x = x0 + progress*(x1-x0).
        sweep_x = x0 + progress * (x1 - x0)
        mask = Image.new("L", (CANVAS_W, CANVAS_H), 0)
        md = ImageDraw.Draw(mask)
        md.rectangle(
            [(x0, y0 - 5), (sweep_x, y1)],
            fill=255,
        )
        partial_text = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
        partial_text.paste(op_spec["layer"], (0, 0), mask)
        frame.alpha_composite(partial_text)
        partial_text.close()
        mask.close()
        # Pen tip rides the sweep front, centered vertically on the text.
        pen_tip = (sweep_x, (y0 + y1) / 2)

    else:  # shape
        # Draw partial path onto a transient layer to avoid mutating accumulator.
        shape_layer = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
        tip = ws.draw_partial(
            shape_layer,
            op_spec["path"],
            progress,
            color=op_spec["color"],
            width=op_spec["stroke_width"],
        )
        frame.alpha_composite(shape_layer)
        shape_layer.close()
        pen_tip = tip

    # Place hand at pen tip.
    if pen_tip is not None:
        tip_x = int(pen_tip[0]) + hand_offset_x
        tip_y = int(pen_tip[1]) + hand_offset_y
        frame.paste(hand_img, (tip_x, tip_y), hand_img)

    return frame


def _commit_op(accumulator: Image.Image, op_spec: dict) -> None:
    """Push the fully-rendered op into the accumulator so subsequent
    frames keep showing it."""
    if op_spec["kind"] == "text":
        accumulator.alpha_composite(op_spec["layer"])
    else:
        ws.draw_partial(
            accumulator, op_spec["path"], 1.0,
            color=op_spec["color"], width=op_spec["stroke_width"],
        )


# ── encoders ────────────────────────────────────────────────────────


def _frame_iter(
    op_specs: list,
    accumulator: Image.Image,
    hand_img: Image.Image,
    hand_offset_x: int,
    hand_offset_y: int,
):
    """Yield every frame of the entire plan in chronological order.

    Implemented as a generator so we never hold more than one frame in
    memory at a time (critical on memory-tight production containers)."""
    for spec in op_specs:
        n = max(1, spec["frames"])
        for i in range(n):
            progress = (i + 1) / n
            yield _compose_frame(
                accumulator, spec, progress, hand_img,
                hand_offset_x, hand_offset_y,
            )
        # Finalize this op into the accumulator before moving on.
        _commit_op(accumulator, spec)
        # Hold a few frames showing the completed state.
        if HOLD_FRAMES_BETWEEN_OPS:
            held = accumulator.copy()
            for _ in range(HOLD_FRAMES_BETWEEN_OPS):
                yield held.copy()
            held.close()


def _write_apng_plan(
    out_path: Path,
    op_specs: list,
    accumulator: Image.Image,
    hand_img: Image.Image,
    hand_offset_x: int,
    hand_offset_y: int,
) -> None:
    ffmpeg_bin = _resolve_ffmpeg_binary()
    # `-c:v apng -f apng` forces ffmpeg to use the APNG muxer regardless
    # of the file extension. Without `-f apng` ffmpeg picks the image2
    # muxer (one file per frame) based on the `.png` extension and the
    # write fails with "Error muxing a packet"/Broken pipe.
    proc = subprocess.Popen(
        [
            ffmpeg_bin, "-y", "-loglevel", "error",
            "-f", "rawvideo", "-pix_fmt", "rgba",
            "-s", f"{CANVAS_W}x{CANVAS_H}", "-r", str(FPS),
            "-i", "-",
            "-c:v", "apng", "-f", "apng", "-plays", "1",
            "-pred", "mixed",
            str(out_path),
        ],
        stdin=subprocess.PIPE,
    )
    try:
        for frame in _frame_iter(op_specs, accumulator, hand_img, hand_offset_x, hand_offset_y):
            arr = np.asarray(frame, dtype=np.uint8)
            if arr.shape[-1] == 3:
                alpha = np.full((arr.shape[0], arr.shape[1], 1), 255, dtype=np.uint8)
                arr = np.concatenate([arr, alpha], axis=-1)
            proc.stdin.write(arr.tobytes())
            del frame, arr
    finally:
        proc.stdin.close()
        proc.wait()


def _write_mp4_plan(
    out_path: Path,
    op_specs: list,
    accumulator: Image.Image,
    hand_img: Image.Image,
    hand_offset_x: int,
    hand_offset_y: int,
) -> None:
    # MP4 path uses imageio's ffmpeg writer (matches whiteboard_renderer
    # for the non-transparent case — no alpha channel).
    writer = imageio.get_writer(
        str(out_path),
        fps=FPS, codec="libx264", quality=8, pixelformat="yuv420p",
        macro_block_size=1,
    )
    try:
        for frame in _frame_iter(op_specs, accumulator, hand_img, hand_offset_x, hand_offset_y):
            # Flatten alpha against white background for MP4 output.
            bg = Image.new("RGB", (CANVAS_W, CANVAS_H), (255, 255, 255))
            bg.paste(frame, (0, 0), frame)
            writer.append_data(np.asarray(bg, dtype=np.uint8))
            del frame, bg
    finally:
        writer.close()
