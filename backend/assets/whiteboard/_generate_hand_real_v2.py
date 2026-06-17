"""Process the user-supplied high-resolution vector illustration of a
hand holding a marker into the `hand_real.png` asset.

The source PNG (`Mao.png`) already has a transparent background and
much sharper artwork than the previous photo, so the pipeline is
minimal:

  1. Locate the marker tip — the upper-left-most dark/opaque pixel
     (luminosity < 80, alpha > 200). This is the very point of the
     marker nib in the illustration.
  2. Crop so the tip sits at (0, 0) of the saved PNG — same contract
     as the other tool assets.
  3. Upscale 1.5× with LANCZOS to push the asset above 900 px tall
     (so it stays crisp when rendered at large `font_size` values on
     1920×1080 canvases without source-pixel blur).
  4. Save to `assets/whiteboard/hand_real.png`.
"""
from pathlib import Path

from PIL import Image
import numpy as np

SRC = Path("/tmp/Mao.png")
DST = Path(__file__).resolve().parent / "hand_real.png"

UPSCALE = 1.5  # pushes 575 px → ~860 px tall — fits any reasonable font_size


def main():
    img = Image.open(SRC).convert("RGBA")
    arr = np.array(img)
    r, g, b, a = arr[..., 0], arr[..., 1], arr[..., 2], arr[..., 3]

    # 1) Locate marker tip.
    op = a > 200
    lum = (0.299 * r + 0.587 * g + 0.114 * b).astype(int)
    candidate = op & (lum < 80)
    ys, xs = np.where(candidate)
    if len(xs) == 0:
        raise RuntimeError("could not locate marker tip in source")
    top_y = int(ys.min())
    near_top = ys < top_y + 12
    tip_x = int(xs[near_top].min())
    tip_y = int(ys[near_top & (xs == tip_x)].min())
    print(f"tip detected at ({tip_x}, {tip_y}) of {img.size}")

    # 2) Crop so the tip ends up at (0, 0) of the final PNG.
    bbox = img.getbbox()
    if bbox is None:
        raise RuntimeError("nothing opaque in source")
    final = img.crop((tip_x, tip_y, bbox[2], bbox[3]))
    print(f"cropped to {final.size} (tip → origin)")

    # 3) Upscale for crisper render at high font_size values.
    new_w = int(final.width * UPSCALE)
    new_h = int(final.height * UPSCALE)
    final = final.resize((new_w, new_h), Image.LANCZOS)
    print(f"upscaled to {final.size}")

    final.save(DST, "PNG", optimize=True)
    print(f"saved: {DST} ({final.width}×{final.height}, {DST.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
