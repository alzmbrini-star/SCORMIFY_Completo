"""Render plan executor for the Whiteboard.

Given a plan from `whiteboard_ai_plan` (list of text + shape ops),
produces a video/APNG where the pen sequentially:

  1. Writes each glyph with the same traced masks as the normal text renderer
  2. Traces each shape op along its path

Text retains glyph-by-glyph motion at arbitrary positions. Closed shapes
and closed icon regions can be progressively colored after their outlines.

The encoding stage is shared with `whiteboard_renderer` (ffmpeg APNG
or MP4 with yuva420p).
"""
from __future__ import annotations

import asyncio
import gc as _gc
import logging
import math
import subprocess
import uuid
from pathlib import Path
from typing import Optional

from PIL import Image, ImageChops, ImageDraw, ImageFont
import numpy as np
import imageio

from .whiteboard_renderer import (
    CANVAS_W, CANVAS_H, OUT_W, OUT_H, FPS,
    OUTPUT_DIR, _resolve_tool, _to_output,
    _resolve_ffmpeg_binary, _resolve_font_path,
    _build_glyph_cache, _make_glyph_image,
)
from . import whiteboard_shapes as ws

logger = logging.getLogger("server.whiteboard_plan")

HOLD_FRAMES_BETWEEN_OPS = 6   # tiny pause so the eye can land on the new op


async def render_whiteboard_plan(
    plan: dict,
    *,
    font_family: Optional[str] = None,
    transparent: bool = False,
    tool: Optional[str] = None,
    chars_per_second: float = 6,
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

    # Deterministic geometry cleanup — also fixes previously-saved plans
    # (texts centered inside their shapes, arrows stopping at borders).
    from .whiteboard_ai_plan import prepare_render_plan
    plan = prepare_render_plan(plan)
    ops = plan.get("ops") or []

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
        spec = _prepare_op(op, font_path, chars_per_second)
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
        "resolution": f"{OUT_W}x{OUT_H}",
        "duration": duration,
        "frames": total_frames,
        "fileSize": file_size,
        "transparent": transparent,
        "format": info_format,
        "planOps": len(op_specs),
        "engine": "plan",
    }


# ── op preparation ──────────────────────────────────────────────────


def _prepare_op(op: dict, font_path: Path, chars_per_second: float = 6) -> dict:
    """Resolve everything we'll need at frame-time: rendered text layer,
    path points, frame counts, color. Done once per op so each frame is
    a cheap composite."""
    t = op["type"]
    color = ws.parse_color(op.get("color"), (31, 41, 55))  # default ink: #1f2937
    if t == "text":
        text = op["text"]
        font_size = int(op.get("font_size") or 80)
        font = ImageFont.truetype(str(font_path), font_size)
        substeps = max(6, min(24, int(round(FPS / max(.1, chars_per_second)))))
        chars, starts, cursor, step = [], [], float(op['x']), 0
        y = float(op['y'])
        for ch in text:
            chars.append({'ch': ch, 'x': int(round(cursor)), 'y': int(round(y))})
            starts.append(step)
            step += substeps if ch.strip() else 2
            if ch == '\n':
                cursor = float(op['x']); y += font_size * 1.35
            else:
                cursor += font.getlength(ch)
        # Masks are built lazily, one operation at a time, then freed on commit.
        return {'kind': 'text', 'frames': max(1, step), 'chars': chars,
                'starts': starts, 'font': font, 'substeps': substeps, 'color': color}
    # Icon drawings: multi-stroke line-art traced by the pen.
    if t == "icon":
        from .whiteboard_icons import icon_strokes
        strokes = icon_strokes(op["name"], float(op["x"]), float(op["y"]), float(op.get("size") or 220))
        total_pts = sum(len(s) for s in strokes)
        if total_pts < 2:
            # Unknown/empty icon — render nothing but keep timing sane.
            return {"kind": "icon", "frames": 1, "strokes": [], "color": color, "stroke_width": 5}
        frames = max(30, min(150, total_pts // 4))
        return {
            "kind": "icon",
            "frames": frames,
            "strokes": strokes,
            "color": color,
            "stroke_width": int(op.get("width") or 5),
            "fill": op.get('fill'), "fill_opacity": op.get('fill_opacity', 85),
        }

    # Shapes
    path = ws.path_for_op(op)
    substeps = ws.shape_substeps(t)
    # Roughly 1 frame per 2 substeps for smooth playback.
    frames = max(20, min(180, len(path) // 2))
    width = int(op.get("width") or 6)
    return {
        "kind": "shape",
        "frames": frames,
        "path": path,
        "color": color,
        "stroke_width": width,
        "fill": op.get('fill'), "fill_opacity": op.get('fill_opacity', 85),
        "closed": t in {'circle', 'rectangle', 'polygon'},
    }


def _draw_plan_text(frame, spec, progress):
    if not spec['chars']:
        return None
    if 'cache' not in spec:
        spec['cache'] = _build_glyph_cache(spec['chars'], spec['font'], spec['substeps'])
        spec['ink_layer'] = Image.new('RGBA', frame.size, (0, 0, 0, 0))
        spec['done'] = 0
    step = min(spec['frames']-1, max(0, int(math.ceil(progress*spec['frames']))-1))
    index = max(i for i, start in enumerate(spec['starts']) if start <= step)
    if index < spec['done']:
        spec['ink_layer'].paste((0, 0, 0, 0), (0, 0, *frame.size)); spec['done'] = 0
    def draw_char(target, char, substep):
        entry = spec['cache'].get(char['ch'])
        if entry is None:
            return None
        glyph = _make_glyph_image(entry, substep, spec['color'])
        target.alpha_composite(glyph, (char['x']+entry['left'], char['y']+entry['top']))
        glyph.close()
        px, py = entry['pen_positions'][substep]
        return char['x']+entry['left']+px, char['y']+entry['top']+py
    for i in range(spec['done'], index):
        draw_char(spec['ink_layer'], spec['chars'][i], -1)
    spec['done'] = index
    frame.alpha_composite(spec['ink_layer'])
    return draw_char(frame, spec['chars'][index], min(spec['substeps']-1, step-spec['starts'][index]))


def _fill_paths(spec):
    if not spec.get('fill'):
        return []
    if spec.get('closed'):
        return [spec['path']]
    return [s for s in spec.get('strokes', []) if len(s)>3 and math.dist(s[0], s[-1])<.1]


def _underpaint(frame, spec, progress):
    """Reveal closed fills with a serpentine coloring pass, below existing ink."""
    paths = _fill_paths(spec)
    if not paths or progress <= 0:
        return frame, None
    mask = Image.new('L', frame.size, 0)
    draw = ImageDraw.Draw(mask)
    for path in paths:
        draw.polygon(path, fill=255)
    box = mask.getbbox()
    if not box:
        mask.close(); return frame, None
    x0, y0, x1, y1 = box
    row_height = 12
    rows = max(1, math.ceil((y1-y0)/row_height))
    amount = min(1, progress)*rows
    row = min(rows-1, int(amount))
    frac = 1 if progress >= 1 else amount-row
    reverse = row % 2 == 1
    x = x1-frac*(x1-x0) if reverse else x0+frac*(x1-x0)
    reveal = Image.new('L', frame.size, 0); rd = ImageDraw.Draw(reveal)
    if row:
        rd.rectangle((x0, y0, x1, y0+row*row_height-1), fill=255)
    rd.rectangle((x if reverse else x0, y0+row*row_height, x1 if reverse else x, min(y1,y0+(row+1)*row_height)), fill=255)
    visible = ImageChops.multiply(mask, reveal)
    opacity = max(10, min(100, int(spec.get('fill_opacity', 85))))
    alpha = visible.point(lambda v: int(v*opacity/100))
    layer = Image.new('RGBA', frame.size, (*ws.parse_color(spec['fill'], (219,234,254)), 0))
    layer.putalpha(alpha); layer.alpha_composite(frame)
    tip_y = min(y1-1, int(y0+(row+.5)*row_height))
    band = mask.crop((x0, tip_y, x1, tip_y+1)); row_box = band.getbbox(); band.close()
    if row_box:
        x = max(x0+row_box[0], min(x0+row_box[2]-1, x))
    mask.close(); reveal.close(); visible.close(); alpha.close(); frame.close()
    return layer, (x, tip_y)


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
    filling = bool(_fill_paths(op_spec))
    outline_progress = min(1, progress/.7) if filling else progress
    fill_tip = None
    if filling:
        frame, fill_tip = _underpaint(frame, op_spec, max(0, (progress-.7)/.3))

    if op_spec["kind"] == "text":
        pen_tip = _draw_plan_text(frame, op_spec, progress)

    elif op_spec["kind"] == "icon":
        if op_spec["strokes"]:
            icon_layer = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
            tip = ws.draw_partial_multi(
                icon_layer,
                op_spec["strokes"],
                outline_progress,
                color=op_spec["color"],
                width=op_spec["stroke_width"],
            )
            frame.alpha_composite(icon_layer)
            icon_layer.close()
            pen_tip = tip

    else:  # shape
        # Draw partial path onto a transient layer to avoid mutating accumulator.
        shape_layer = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
        tip = ws.draw_partial(
            shape_layer,
            op_spec["path"],
            outline_progress,
            color=op_spec["color"],
            width=op_spec["stroke_width"],
        )
        frame.alpha_composite(shape_layer)
        shape_layer.close()
        pen_tip = tip

    pen_tip = fill_tip or pen_tip
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
        if not op_spec['chars']:
            return
        _draw_plan_text(accumulator, op_spec, 1)
        op_spec['ink_layer'].close()
        for glyph in op_spec['cache'].values():
            if glyph: glyph['glyph'].close()
        for key in ('cache', 'ink_layer', 'done'): op_spec.pop(key, None)
    elif op_spec["kind"] == "icon":
        filled, _ = _underpaint(accumulator.copy(), op_spec, 1)
        accumulator.paste(filled); filled.close()
        if op_spec["strokes"]:
            ws.draw_partial_multi(
                accumulator, op_spec["strokes"], 1.0,
                color=op_spec["color"], width=op_spec["stroke_width"],
            )
    else:
        filled, _ = _underpaint(accumulator.copy(), op_spec, 1)
        accumulator.paste(filled); filled.close()
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
            "-s", f"{OUT_W}x{OUT_H}", "-r", str(FPS),
            "-i", "-",
            "-c:v", "apng", "-f", "apng", "-plays", "1",
            "-pred", "mixed",
            str(out_path),
        ],
        stdin=subprocess.PIPE,
    )
    try:
        for frame in _frame_iter(op_specs, accumulator, hand_img, hand_offset_x, hand_offset_y):
            out_frame = _to_output(frame)
            arr = np.asarray(out_frame, dtype=np.uint8)
            if arr.shape[-1] == 3:
                alpha = np.full((arr.shape[0], arr.shape[1], 1), 255, dtype=np.uint8)
                arr = np.concatenate([arr, alpha], axis=-1)
            proc.stdin.write(arr.tobytes())
            del frame, out_frame, arr
    finally:
        try:
            proc.stdin.close()
        except Exception:  # noqa: BLE001
            pass
        proc.wait(timeout=60)
        if proc.returncode != 0:
            out_path.unlink(missing_ok=True)
            raise RuntimeError(
                f"ffmpeg APNG encode failed (rc={proc.returncode})"
            )


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
        output_params=["-preset", "veryfast", "-threads", "2"],
    )
    try:
        for frame in _frame_iter(op_specs, accumulator, hand_img, hand_offset_x, hand_offset_y):
            # Flatten alpha against white background for MP4 output.
            bg = Image.new("RGB", (CANVAS_W, CANVAS_H), (255, 255, 255))
            bg.paste(frame, (0, 0), frame)
            writer.append_data(np.asarray(_to_output(bg), dtype=np.uint8))
            del frame, bg
    finally:
        writer.close()
