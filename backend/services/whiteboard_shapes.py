"""Shape rendering primitives for the Whiteboard renderer.

Adds animated "pen-traces-the-outline" support for the 4 most common
emphasis shapes used in didactic whiteboards:

  - circle      → traces along the circumference (CCW from top)
  - rectangle   → traces 4 sides clockwise from top-left
  - arrow       → traces shaft, then the V-shaped arrowhead
  - underline   → straight stroke left→right

Each shape exposes the same two-function contract so the renderer can
animate them uniformly:

  path(spec) -> list[(x, y)]
      Returns the ordered sequence of pen positions. The renderer
      advances along this sequence one substep per frame.

  draw_partial(img, path, progress, *, color, width)
      Renders the visible portion of the stroke onto `img` (an RGBA
      PIL Image) given current progress in [0.0, 1.0]. Uses anti-aliased
      polylines so the result blends naturally with the text layer.

Coordinates assume the same 1920x1080 canvas the rest of the renderer
operates on.
"""
from __future__ import annotations

import math
from typing import Iterable, Optional, Sequence

from PIL import Image, ImageDraw


# Number of pen positions per shape. Higher → smoother stroke and more
# animation substeps but proportionally slower. 120 strikes the right
# balance for our 1920×1080 canvas: ~5px between adjacent points.
DEFAULT_POINTS_PER_SHAPE = 120

Point = tuple[float, float]


# ── path generators ──────────────────────────────────────────────────


def circle_path(
    cx: float,
    cy: float,
    rx: float,
    ry: Optional[float] = None,
    n: int = DEFAULT_POINTS_PER_SHAPE,
) -> list[Point]:
    """Counter-clockwise path tracing an ellipse starting at the TOP
    (12 o'clock). Starting at the top feels natural for hand-drawn
    emphasis circles around words."""
    if ry is None:
        ry = rx
    pts: list[Point] = []
    for i in range(n + 1):
        t = i / n
        # Start at -π/2 (top) and go counter-clockwise → angle decreases.
        angle = -math.pi / 2 - 2 * math.pi * t
        pts.append((cx + rx * math.cos(angle), cy + ry * math.sin(angle)))
    return pts


def rectangle_path(
    x: float, y: float, w: float, h: float,
    n: int = DEFAULT_POINTS_PER_SHAPE,
) -> list[Point]:
    """Clockwise rectangle starting at the top-left corner.

    Allocates the N points proportionally to side length so each segment
    has the same pen speed (avoids the eraser-style "fast on short side"
    look)."""
    perimeter = 2 * (w + h)
    if perimeter <= 0:
        return [(x, y)]
    # Cumulative segment lengths around the rectangle.
    segs = [
        ((x, y), (x + w, y), w),            # top  L→R
        ((x + w, y), (x + w, y + h), h),    # right T→B
        ((x + w, y + h), (x, y + h), w),    # bottom R→L
        ((x, y + h), (x, y), h),            # left B→T
    ]
    pts: list[Point] = []
    for (p0, p1, length) in segs:
        seg_n = max(2, int(round(n * length / perimeter)))
        for i in range(seg_n):
            t = i / seg_n
            pts.append((
                p0[0] + (p1[0] - p0[0]) * t,
                p0[1] + (p1[1] - p0[1]) * t,
            ))
    # Close the path back to the starting corner so the stroke joins.
    pts.append(segs[0][0])
    return pts


def arrow_path(
    x1: float, y1: float, x2: float, y2: float,
    head_len: float = 35.0,
    head_spread: float = 22.0,
    n: int = DEFAULT_POINTS_PER_SHAPE,
) -> list[Point]:
    """Straight arrow from (x1,y1) → (x2,y2) with a V-shaped arrowhead.

    Pen traces the shaft first then the two arrowhead wings. The wings
    are drawn as two short strokes that emanate from the tip — visually
    indistinguishable from a "<" or ">" handwritten head."""
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    if length <= 0:
        return [(x1, y1)]
    # Direction & perpendicular unit vectors.
    ux, uy = dx / length, dy / length
    nx, ny = -uy, ux
    pts: list[Point] = []
    # Reserve ~70% of substeps for the shaft, ~15% per wing.
    shaft_n = max(4, int(n * 0.7))
    wing_n = max(2, int(n * 0.15))
    for i in range(shaft_n + 1):
        t = i / shaft_n
        pts.append((x1 + dx * t, y1 + dy * t))
    # Wing 1: from tip back-left
    w1_end = (
        x2 - ux * head_len + nx * head_spread,
        y2 - uy * head_len + ny * head_spread,
    )
    for i in range(1, wing_n + 1):
        t = i / wing_n
        pts.append((
            x2 + (w1_end[0] - x2) * t,
            y2 + (w1_end[1] - y2) * t,
        ))
    # Pen "jumps" back to the tip — emulated by repeating the tip so
    # draw_partial() sees an inflection point and starts wing 2 fresh.
    pts.append((x2, y2))
    w2_end = (
        x2 - ux * head_len - nx * head_spread,
        y2 - uy * head_len - ny * head_spread,
    )
    for i in range(1, wing_n + 1):
        t = i / wing_n
        pts.append((
            x2 + (w2_end[0] - x2) * t,
            y2 + (w2_end[1] - y2) * t,
        ))
    return pts


def underline_path(
    x1: float, y1: float, x2: float, y2: Optional[float] = None,
    n: int = 30,
) -> list[Point]:
    """Simple straight underline (or generic line) L→R.

    Shorter point count than other shapes because there's no curvature
    to interpolate; the animation feels snappier this way (matches how
    a real instructor underlines for emphasis)."""
    if y2 is None:
        y2 = y1
    pts: list[Point] = []
    for i in range(n + 1):
        t = i / n
        pts.append((x1 + (x2 - x1) * t, y1 + (y2 - y1) * t))
    return pts


# ── stroke renderer ─────────────────────────────────────────────────


def draw_partial(
    img: Image.Image,
    path: Sequence[Point],
    progress: float,
    *,
    color: tuple[int, int, int] = (0, 0, 0),
    width: int = 6,
) -> tuple[float, float]:
    """Draw the portion of `path` from index 0 up to (progress * len(path))
    onto `img` in-place. Returns the pen-tip (x, y) — used by the caller
    to place the hand sprite at the leading edge.

    Strokes are rendered as anti-aliased polylines so they blend with
    the text layer the same way the text reveals do."""
    if not path:
        return (0.0, 0.0)
    progress = max(0.0, min(1.0, progress))
    cut = max(2, int(progress * len(path)))
    sub = list(path[:cut])
    if len(sub) < 2:
        return sub[0] if sub else (0.0, 0.0)
    draw = ImageDraw.Draw(img)
    # PIL.line takes a flat list of tuples; alpha encoded via RGBA tuple.
    rgba = (color[0], color[1], color[2], 255)
    draw.line(sub, fill=rgba, width=width, joint="curve")
    # Cap the ends with circles so the stroke looks smooth at start/end.
    r = max(2, width // 2)
    for end in (sub[0], sub[-1]):
        draw.ellipse(
            [(end[0] - r, end[1] - r), (end[0] + r, end[1] + r)],
            fill=rgba,
        )
    return sub[-1]


# ── plan helpers ────────────────────────────────────────────────────


def draw_partial_multi(
    img: Image.Image,
    strokes: Sequence[Sequence[Point]],
    progress: float,
    *,
    color: tuple[int, int, int] = (0, 0, 0),
    width: int = 5,
) -> tuple[float, float]:
    """Multi-stroke variant of draw_partial for icon drawings: strokes
    are independent polylines (pen lifts between them). Progress spans
    the TOTAL point count so the pen speed stays uniform. Returns the
    current pen tip."""
    total = sum(len(s) for s in strokes)
    if total == 0:
        return (0.0, 0.0)
    progress = max(0.0, min(1.0, progress))
    cut = max(1, int(progress * total))
    draw = ImageDraw.Draw(img)
    rgba = (color[0], color[1], color[2], 255)
    r = max(1, width // 2)
    tip: tuple[float, float] = strokes[0][0]
    acc = 0
    for s in strokes:
        if acc >= cut:
            break
        take = min(len(s), cut - acc)
        if take >= 2:
            sub = list(s[:take])
            draw.line(sub, fill=rgba, width=width, joint="curve")
            for end in (sub[0], sub[-1]):
                draw.ellipse(
                    [(end[0] - r, end[1] - r), (end[0] + r, end[1] + r)],
                    fill=rgba,
                )
            tip = sub[-1]
        elif take == 1:
            tip = s[0]
        acc += len(s)
    return tip


def shape_substeps(shape_type: str) -> int:
    """How many animation substeps a shape consumes. Longer paths get
    more substeps so the pen speed stays roughly constant across shapes.

    The renderer's outer scheduler converts substeps to frames at FPS."""
    return {
        "circle": 90,
        "rectangle": 100,
        "arrow": 70,
        "underline": 35,
    }.get(shape_type, 80)


def parse_color(value: Optional[str], fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    """Permissive hex color parser. Accepts '#RGB', '#RRGGBB', 'RRGGBB',
    and named CSS-ish basics so the LLM-generated plan can use either."""
    if not value:
        return fallback
    v = value.strip().lstrip("#").lower()
    named = {
        "black": (0, 0, 0), "white": (255, 255, 255),
        "red": (220, 38, 38), "blue": (37, 99, 235),
        "green": (22, 163, 74), "yellow": (234, 179, 8),
        "orange": (234, 88, 12), "purple": (147, 51, 234),
        "pink": (236, 72, 153), "teal": (13, 148, 136),
    }
    if v in named:
        return named[v]
    try:
        if len(v) == 3:
            v = "".join(c * 2 for c in v)
        if len(v) == 6:
            return (int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16))
    except ValueError:
        pass
    return fallback


def path_for_op(op: dict, default_n: int = DEFAULT_POINTS_PER_SHAPE) -> list[Point]:
    """Build the pen path for a single render-plan operation. Returns
    an empty list if the op type is unsupported — caller should skip."""
    t = (op.get("type") or "").lower()
    if t == "circle":
        return circle_path(
            float(op["cx"]), float(op["cy"]),
            float(op["rx"]), float(op.get("ry") or op["rx"]),
            n=default_n,
        )
    if t == "rectangle":
        return rectangle_path(
            float(op["x"]), float(op["y"]),
            float(op["w"]), float(op["h"]),
            n=default_n,
        )
    if t == "arrow":
        return arrow_path(
            float(op["x1"]), float(op["y1"]),
            float(op["x2"]), float(op["y2"]),
            head_len=float(op.get("head_len", 35)),
            head_spread=float(op.get("head_spread", 22)),
            n=default_n,
        )
    if t == "underline":
        return underline_path(
            float(op["x1"]), float(op["y1"]),
            float(op["x2"]), float(op.get("y2", op["y1"])),
        )
    return []
