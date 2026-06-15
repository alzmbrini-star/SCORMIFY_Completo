"""One-shot script to generate the minimalist pen PNG asset used in
whiteboard renders. Runs once during build; the output PNG ships in
/app/backend/assets/whiteboard/hand.png (filename kept for backward
compatibility with the renderer that imports it).

Design: a sleek, minimalist fountain/fineliner pen pointing toward
the top-left. The pen tip is anchored at coordinate (0, 0) so the
renderer can directly translate the asset to the current writing tip
position (same contract as the previous hand asset).

The pen is rendered along a 45° diagonal — body extends from the tip
in the bottom-right direction — so it visually mimics the natural
angle a right-handed author would hold a pen at while writing.
"""
from PIL import Image, ImageDraw
from pathlib import Path
import math

# Canvas — tall+narrow enough to hold the diagonal pen without clipping
# but small enough that the asset stays light.
W, H = 220, 240
img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# --- Geometry: pen along a 45° axis from the tip at (0,0) -----------
# We define the pen by walking along an axis vector and laying down
# polygons with a perpendicular width that varies by segment.
ANGLE = math.radians(48)  # slight tilt away from pure 45° for elegance
ax = math.cos(ANGLE)
ay = math.sin(ANGLE)
# Perpendicular (rotated +90°) for offsetting polygon edges sideways.
px = -ay
py = ax


def at(dist: float, side: float = 0.0) -> tuple[int, int]:
    """Point at `dist` along the pen axis, offset by `side` perpendicular."""
    x = ax * dist + px * side
    y = ay * dist + py * side
    return (int(round(x)), int(round(y)))


# Colors — restrained, minimalist palette
NIB_DARK = (35, 35, 40, 255)       # graphite nib tip
NIB_LIGHT = (170, 175, 185, 255)   # nib upper edge highlight
SECTION = (25, 25, 30, 255)        # gripping section (matte black)
BARREL = (18, 20, 28, 255)         # main body (near-black, subtle blue cast)
BARREL_HI = (55, 60, 75, 255)      # highlight stripe along the body
CLIP = (190, 195, 205, 255)        # brushed-metal clip
CLIP_DARK = (130, 135, 145, 255)
END_CAP = (12, 14, 20, 255)

# --- 1) Nib (the writing point sits at (0,0)) -----------------------
# Triangular nib that tapers from tip → section. Tip is razor-sharp.
NIB_LEN = 28
NIB_BASE_W = 7
nib_outline = [
    at(0, 0),
    at(NIB_LEN, NIB_BASE_W),
    at(NIB_LEN, -NIB_BASE_W),
]
d.polygon(nib_outline, fill=NIB_DARK)
# Subtle highlight on the upper edge of the nib (one side only) so it
# reads as metallic rather than a flat triangle.
d.polygon([
    at(2, -1),
    at(NIB_LEN, -NIB_BASE_W),
    at(NIB_LEN, -NIB_BASE_W + 2),
], fill=NIB_LIGHT)

# --- 2) Section (grip) ----------------------------------------------
SEC_START = NIB_LEN
SEC_END = NIB_LEN + 18
SEC_W = 9
d.polygon([
    at(SEC_START, SEC_W - 2),
    at(SEC_END, SEC_W),
    at(SEC_END, -SEC_W),
    at(SEC_START, -(SEC_W - 2)),
], fill=SECTION)

# Thin ring between section and barrel (visual break).
RING_W = SEC_W + 1
d.polygon([
    at(SEC_END - 1, RING_W),
    at(SEC_END + 3, RING_W),
    at(SEC_END + 3, -RING_W),
    at(SEC_END - 1, -RING_W),
], fill=CLIP)

# --- 3) Barrel (main body) ------------------------------------------
BAR_START = SEC_END + 3
BAR_END = BAR_START + 145
BAR_W = 10
d.polygon([
    at(BAR_START, BAR_W),
    at(BAR_END, BAR_W),
    at(BAR_END, -BAR_W),
    at(BAR_START, -BAR_W),
], fill=BARREL)
# Highlight stripe — single thin band along the upper side conveys a
# glossy cylindrical body without overdoing the gradient.
d.polygon([
    at(BAR_START + 4, -BAR_W + 1),
    at(BAR_END - 6, -BAR_W + 1),
    at(BAR_END - 6, -BAR_W + 4),
    at(BAR_START + 4, -BAR_W + 4),
], fill=BARREL_HI)

# --- 4) Pocket clip --------------------------------------------------
# Sleek metal clip on the upper side of the barrel.
CLIP_START = BAR_START + 22
CLIP_END = BAR_START + 78
d.polygon([
    at(CLIP_START, -BAR_W),
    at(CLIP_END, -BAR_W),
    at(CLIP_END - 4, -BAR_W - 5),
    at(CLIP_START + 2, -BAR_W - 5),
], fill=CLIP)
# Dark inner shadow on the clip for depth.
d.polygon([
    at(CLIP_START + 3, -BAR_W - 1),
    at(CLIP_END - 3, -BAR_W - 1),
    at(CLIP_END - 5, -BAR_W - 3),
    at(CLIP_START + 4, -BAR_W - 3),
], fill=CLIP_DARK)

# --- 5) End cap (back of pen) ---------------------------------------
CAP_START = BAR_END
CAP_END = BAR_END + 14
CAP_W = BAR_W + 1
d.polygon([
    at(CAP_START, CAP_W),
    at(CAP_END - 4, CAP_W - 2),
    at(CAP_END, 0),
    at(CAP_END - 4, -(CAP_W - 2)),
    at(CAP_START, -CAP_W),
], fill=END_CAP)

# --- Composition: the canvas origin (0,0) is the writing tip --------
# Shift everything so it fits in our positive-coordinate PNG, then
# remember the offset so the renderer can translate back.
# (We'll instead just create a translated image by drawing into a
# larger canvas with a positive translation, then crop tightly so the
# tip ends up at the asset's (0,0) again.)
# Simpler approach: draw at a translated origin and rely on the
# renderer's HAND_OFFSET_X/Y for fine alignment.

# We need to move the drawing so it fits inside (0..W, 0..H). All the
# pen-side coordinates we used can be negative (perpendicular offsets
# point up-left). Composite into a larger buffer and find the bounding
# box of opaque pixels, then translate so the tip (currently at the
# drawing's logical origin) ends up at (0, 0) of the final PNG.
# Easiest: redo the drawing inside a translated buffer.

# Rebuild with translation so coordinates are non-negative.
OFFSET = (40, 40)  # logical (0,0) tip will land here in the buffer

buf = Image.new("RGBA", (W + OFFSET[0], H + OFFSET[1]), (0, 0, 0, 0))
bd = ImageDraw.Draw(buf)


def atb(dist: float, side: float = 0.0) -> tuple[int, int]:
    x = ax * dist + px * side + OFFSET[0]
    y = ay * dist + py * side + OFFSET[1]
    return (int(round(x)), int(round(y)))


# Re-emit all polygons using `atb` instead of `at`.
bd.polygon([atb(0, 0), atb(NIB_LEN, NIB_BASE_W), atb(NIB_LEN, -NIB_BASE_W)], fill=NIB_DARK)
bd.polygon([
    atb(2, -1),
    atb(NIB_LEN, -NIB_BASE_W),
    atb(NIB_LEN, -NIB_BASE_W + 2),
], fill=NIB_LIGHT)
bd.polygon([
    atb(SEC_START, SEC_W - 2),
    atb(SEC_END, SEC_W),
    atb(SEC_END, -SEC_W),
    atb(SEC_START, -(SEC_W - 2)),
], fill=SECTION)
bd.polygon([
    atb(SEC_END - 1, RING_W),
    atb(SEC_END + 3, RING_W),
    atb(SEC_END + 3, -RING_W),
    atb(SEC_END - 1, -RING_W),
], fill=CLIP)
bd.polygon([
    atb(BAR_START, BAR_W),
    atb(BAR_END, BAR_W),
    atb(BAR_END, -BAR_W),
    atb(BAR_START, -BAR_W),
], fill=BARREL)
bd.polygon([
    atb(BAR_START + 4, -BAR_W + 1),
    atb(BAR_END - 6, -BAR_W + 1),
    atb(BAR_END - 6, -BAR_W + 4),
    atb(BAR_START + 4, -BAR_W + 4),
], fill=BARREL_HI)
bd.polygon([
    atb(CLIP_START, -BAR_W),
    atb(CLIP_END, -BAR_W),
    atb(CLIP_END - 4, -BAR_W - 5),
    atb(CLIP_START + 2, -BAR_W - 5),
], fill=CLIP)
bd.polygon([
    atb(CLIP_START + 3, -BAR_W - 1),
    atb(CLIP_END - 3, -BAR_W - 1),
    atb(CLIP_END - 5, -BAR_W - 3),
    atb(CLIP_START + 4, -BAR_W - 3),
], fill=CLIP_DARK)
bd.polygon([
    atb(CAP_START, CAP_W),
    atb(CAP_END - 4, CAP_W - 2),
    atb(CAP_END, 0),
    atb(CAP_END - 4, -(CAP_W - 2)),
    atb(CAP_START, -CAP_W),
], fill=END_CAP)

# Crop with a tight bounding box, then translate so the tip lands at
# (0, 0) of the final saved PNG. The tip's location in `buf` is OFFSET.
bbox = buf.getbbox()  # (left, top, right, bottom) of opaque pixels
if bbox is None:
    raise RuntimeError("Drew nothing — bbox is empty")

# Pad so the tip stays at (0, 0): the tip is at OFFSET in `buf`, so we
# crop starting at OFFSET (not at bbox[0..1]) and width/height extend
# to bbox[2..3]. Anything to the left/above the tip is intentionally
# discarded — the renderer assumes the tip is at the asset's (0, 0).
crop_left = OFFSET[0]
crop_top = OFFSET[1]
crop_right = bbox[2]
crop_bottom = bbox[3]
final = buf.crop((crop_left, crop_top, crop_right, crop_bottom))

out = Path(__file__).resolve().parent / "hand.png"
final.save(out, "PNG")
print(f"saved: {out} ({final.width}x{final.height})")
