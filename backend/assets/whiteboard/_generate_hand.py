"""One-shot script to generate the marker/pen + hand PNG asset used in
whiteboard renders. Runs once during build; the output PNG ships in
/app/backend/assets/whiteboard/hand.png.

Drawing: a stylized marker held by a simplified hand silhouette, with
the pen tip at the (0,0) coordinate (top-left of the canvas) so the
renderer can directly translate the asset to the writing tip position.
"""
from PIL import Image, ImageDraw
from pathlib import Path

W, H = 220, 280
img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# --- Marker body (vertical, tip at top-left around 18,18) ---
# Cap (dark blue)
d.polygon([(8, 14), (32, 22), (28, 60), (12, 56)], fill=(30, 60, 140, 255), outline=(20, 40, 100, 255))
# Pen barrel (white with red trim)
d.polygon([(12, 56), (28, 60), (60, 180), (44, 184)], fill=(245, 245, 245, 255), outline=(80, 80, 80, 255))
# Red ring
d.polygon([(20, 100), (32, 104), (33, 115), (21, 111)], fill=(200, 30, 30, 255))
# Tip — black triangle at the very top-left, this is the WRITING POINT.
d.polygon([(0, 18), (18, 12), (8, 28)], fill=(20, 20, 20, 255))

# --- Hand (skin-tone silhouette grasping the marker) ---
skin = (230, 190, 160, 255)
skin_outline = (170, 120, 90, 255)
# Palm
d.ellipse([(60, 160), (180, 270)], fill=skin, outline=skin_outline, width=2)
# Thumb wrapped around marker
d.polygon([(50, 175), (72, 165), (78, 195), (60, 210)], fill=skin, outline=skin_outline)
# Index finger pointing toward tip
d.polygon([(55, 180), (35, 110), (50, 105), (70, 175)], fill=skin, outline=skin_outline)
# Sleeve cuff
d.rectangle([(120, 260), (210, 280)], fill=(60, 100, 180, 255))

out = Path(__file__).resolve().parent / "hand.png"
img.save(out, "PNG")
print(f"saved: {out} ({W}x{H})")
