"""One-shot script to generate the stylized "hand holding a pen" asset
used by the whiteboard renderer when the author picks the `hand`
drawing tool (the default `pen` tool uses `hand.png` — kept for
backward compatibility despite the misleading filename, see
`_generate_hand.py`).

Design: a stylized right-handed forearm extending diagonally from the
bottom-right, with fingers wrapping around the existing minimalist
pen. The pen tip is anchored at coordinate (0, 0) so the renderer can
reuse the same translate-by-tip contract regardless of which tool the
author chose.

Output: /app/backend/assets/whiteboard/hand_holding_pen.png
"""
from PIL import Image, ImageDraw, ImageFilter
from pathlib import Path
import math

# Final asset canvas size (anything past this gets cropped).
W, H = 360, 380
buf = Image.new("RGBA", (W + 60, H + 60), (0, 0, 0, 0))
d = ImageDraw.Draw(buf)

# The pen axis runs from the tip (logical (0,0)) toward the back of the
# pen. The tip will land at OFFSET on the buffer; we crop later so it
# is at (0,0) of the final PNG (same contract as the pen asset).
OFFSET = (50, 50)

ANGLE = math.radians(48)   # matches pen.png so the styles align visually
ax = math.cos(ANGLE)
ay = math.sin(ANGLE)
px = -ay                   # perpendicular (rotated +90°)
py = ax


def atb(dist: float, side: float = 0.0) -> tuple[int, int]:
    """Point at `dist` along pen axis, offset by `side` perpendicular."""
    x = ax * dist + px * side + OFFSET[0]
    y = ay * dist + py * side + OFFSET[1]
    return (int(round(x)), int(round(y)))


# Colors — keep restrained and printable.
SKIN = (243, 211, 184, 255)
SKIN_SHADOW = (210, 175, 145, 255)
SKIN_OUTLINE = (130, 95, 70, 255)
KNUCKLE = (228, 188, 158, 255)
NAIL = (252, 232, 218, 255)

# Pen palette (same as _generate_hand.py for visual continuity).
NIB_DARK = (35, 35, 40, 255)
NIB_LIGHT = (170, 175, 185, 255)
SECTION = (25, 25, 30, 255)
BARREL = (18, 20, 28, 255)
BARREL_HI = (55, 60, 75, 255)
CLIP = (190, 195, 205, 255)
CLIP_DARK = (130, 135, 145, 255)
END_CAP = (12, 14, 20, 255)


# ── 1) Forearm + wrist ────────────────────────────────────────────────
# Wide rounded blob that extends from the bottom-right edge toward the
# pen grip. Drawn FIRST so fingers + pen overlap it cleanly.
FOREARM_W = 70
FOREARM_START = 130     # at hand junction
FOREARM_END = 320       # off-canvas to suggest it continues
forearm_poly = [
    atb(FOREARM_START, FOREARM_W - 8),
    atb(FOREARM_START + 25, FOREARM_W),
    atb(FOREARM_END,    FOREARM_W + 10),
    atb(FOREARM_END,   -FOREARM_W - 6),
    atb(FOREARM_START + 25, -FOREARM_W + 4),
    atb(FOREARM_START, -(FOREARM_W - 12)),
]
d.polygon(forearm_poly, fill=SKIN, outline=SKIN_OUTLINE)
# Subtle inner shadow on the bottom side.
d.polygon([
    atb(FOREARM_START + 10, FOREARM_W - 4),
    atb(FOREARM_END,        FOREARM_W + 6),
    atb(FOREARM_END,        FOREARM_W - 10),
    atb(FOREARM_START + 20, FOREARM_W - 18),
], fill=SKIN_SHADOW)


# ── 2) Palm / back of the hand ───────────────────────────────────────
# Egg-shaped blob centered around the grip. The pen passes diagonally
# through the lower half of this blob; fingers (drawn next) overlay it
# from the front.
PALM_CENTER = atb(90, 0)
PALM_W = 78
PALM_H = 95
palm_bbox = (
    PALM_CENTER[0] - PALM_W,
    PALM_CENTER[1] - PALM_H,
    PALM_CENTER[0] + PALM_W,
    PALM_CENTER[1] + PALM_H,
)
d.ellipse(palm_bbox, fill=SKIN, outline=SKIN_OUTLINE)
# Inner shadow on the lower-left of the palm.
d.ellipse(
    (palm_bbox[0] + 8, palm_bbox[1] + 30,
     palm_bbox[2] - 30, palm_bbox[3] - 6),
    fill=SKIN_SHADOW,
)


# ── 3) Pen barrel (drawn ON TOP of forearm/palm, BELOW the fingers) ──
NIB_LEN = 28
NIB_BASE_W = 7
SEC_START = NIB_LEN
SEC_END = NIB_LEN + 18
SEC_W = 9
RING_W = SEC_W + 1
BAR_START = SEC_END + 3
BAR_END = BAR_START + 145
BAR_W = 10
CLIP_START = BAR_START + 22
CLIP_END = BAR_START + 78
CAP_START = BAR_END
CAP_END = BAR_END + 14
CAP_W = BAR_W + 1

# Nib
d.polygon([atb(0, 0), atb(NIB_LEN, NIB_BASE_W), atb(NIB_LEN, -NIB_BASE_W)],
          fill=NIB_DARK)
d.polygon([
    atb(2, -1),
    atb(NIB_LEN, -NIB_BASE_W),
    atb(NIB_LEN, -NIB_BASE_W + 2),
], fill=NIB_LIGHT)
# Section
d.polygon([
    atb(SEC_START, SEC_W - 2), atb(SEC_END, SEC_W),
    atb(SEC_END, -SEC_W),     atb(SEC_START, -(SEC_W - 2)),
], fill=SECTION)
# Ring
d.polygon([
    atb(SEC_END - 1, RING_W), atb(SEC_END + 3, RING_W),
    atb(SEC_END + 3, -RING_W), atb(SEC_END - 1, -RING_W),
], fill=CLIP)
# Barrel
d.polygon([
    atb(BAR_START, BAR_W), atb(BAR_END, BAR_W),
    atb(BAR_END, -BAR_W),  atb(BAR_START, -BAR_W),
], fill=BARREL)
d.polygon([
    atb(BAR_START + 4, -BAR_W + 1), atb(BAR_END - 6, -BAR_W + 1),
    atb(BAR_END - 6, -BAR_W + 4),   atb(BAR_START + 4, -BAR_W + 4),
], fill=BARREL_HI)
# Pocket clip
d.polygon([
    atb(CLIP_START, -BAR_W),     atb(CLIP_END, -BAR_W),
    atb(CLIP_END - 4, -BAR_W - 5), atb(CLIP_START + 2, -BAR_W - 5),
], fill=CLIP)
d.polygon([
    atb(CLIP_START + 3, -BAR_W - 1), atb(CLIP_END - 3, -BAR_W - 1),
    atb(CLIP_END - 5, -BAR_W - 3),   atb(CLIP_START + 4, -BAR_W - 3),
], fill=CLIP_DARK)
# End cap
d.polygon([
    atb(CAP_START, CAP_W), atb(CAP_END - 4, CAP_W - 2),
    atb(CAP_END, 0),
    atb(CAP_END - 4, -(CAP_W - 2)), atb(CAP_START, -CAP_W),
], fill=END_CAP)


# ── 4) Fingers wrapping the pen (drawn LAST so they sit on top) ──────
# Thumb on the upper side near the section, index/middle finger pads
# pressing against the barrel from the lower side. Each finger is a
# small filled ellipse rotated to follow the pen axis.

def finger_blob(dist_along: float, side: float, length: int, width: int,
                shadow=False):
    """Draw a finger pad centered at (dist_along, side) on the pen axis.

    Uses two ellipses for a soft pad shape — first a darker shadow
    underneath, then the skin on top — to suggest depth without
    needing real shading."""
    cx, cy = atb(dist_along, side)
    # Outer skin ellipse (rotated bbox approximation by drawing a
    # rounded rectangle aligned to canvas; the visual rotation is
    # implied by the position alone, which is enough for this style).
    bbox = (cx - length // 2, cy - width // 2,
            cx + length // 2, cy + width // 2)
    if shadow:
        sh_bbox = (bbox[0] + 2, bbox[1] + 3, bbox[2] + 2, bbox[3] + 3)
        d.ellipse(sh_bbox, fill=SKIN_SHADOW)
    d.ellipse(bbox, fill=SKIN, outline=SKIN_OUTLINE)
    # Fingertip highlight (tiny lighter ellipse).
    hi_bbox = (bbox[0] + length // 6, bbox[1] + width // 6,
               bbox[2] - length // 2, bbox[3] - width // 2)
    d.ellipse(hi_bbox, fill=NAIL)


# Thumb — placed UPPER side (negative `side`), near the grip section.
finger_blob(dist_along=42, side=-22, length=58, width=34, shadow=True)
# Index finger — pad pressing barrel from the LOWER side.
finger_blob(dist_along=60, side=26, length=64, width=30, shadow=True)
# Middle finger — slightly further along + slightly more curl.
finger_blob(dist_along=92, side=30, length=66, width=28, shadow=True)
# Ring + pinky combined as one soft blob behind the others.
finger_blob(dist_along=120, side=44, length=70, width=24, shadow=True)


# ── 5) Soft blur on shadows so the rasterised polygons don't look harsh
#       (only on the alpha — keeps edges crisp where needed).
# We composite a 1-pixel inflated outline to smooth the silhouette.
silhouette = buf.copy()
silhouette = silhouette.filter(ImageFilter.GaussianBlur(radius=0.6))
buf = Image.alpha_composite(silhouette, buf)


# ── 6) Crop so the pen tip ends up at (0, 0) of the final PNG ────────
bbox = buf.getbbox()
if bbox is None:
    raise RuntimeError("nothing drawn")

crop_left = OFFSET[0]
crop_top = OFFSET[1]
crop_right = bbox[2]
crop_bottom = bbox[3]
final = buf.crop((crop_left, crop_top, crop_right, crop_bottom))

out = Path(__file__).resolve().parent / "hand_holding_pen.png"
final.save(out, "PNG")
print(f"saved: {out} ({final.width}x{final.height})")
