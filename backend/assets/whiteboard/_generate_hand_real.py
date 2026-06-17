"""Convert the user-supplied photo of a hand holding a marker into a
transparent-background PNG asset for the Whiteboard renderer.

Pipeline:
  1. Load the source image (483×690, hand + marker on a whiteboard
     background with a faint purple text "o de me…" and a gray desk
     strip at the bottom).
  2. Remove the white whiteboard background (alpha = 0 wherever the
     pixel is nearly white).
  3. Remove the bluish desk strip at the bottom (low saturation, mid
     brightness, B > R).
  4. Remove the small "o de me" text fragment in the upper-left (dark
     purple / blue ink — looks like it was written by another marker
     in the original photo) by masking the rectangular text area.
  5. Locate the marker tip — the visually leftmost ink in the marker
     body. After visual inspection of this specific source image the
     tip sits at roughly (108, 47). We refine it programmatically by
     finding the topmost dark pixel inside a small region around that
     coordinate, then crop the final PNG so the tip ends up at (0, 0)
     — same contract as the other tool assets.
  6. Save to `assets/whiteboard/hand_real.png`.

Run once at build time. The script is idempotent.
"""
from pathlib import Path

from PIL import Image
import numpy as np

SRC = Path("/tmp/hand_real_src.png")
DST = Path(__file__).resolve().parent / "hand_real.png"


def main():
    img = Image.open(SRC).convert("RGBA")
    arr = np.array(img)
    h, w, _ = arr.shape
    print(f"src: {w}x{h}")

    r, g, b, a = arr[..., 0], arr[..., 1], arr[..., 2], arr[..., 3]

    # ── 1) Background: pure-white whiteboard ────────────────────────
    white_mask = (r > 230) & (g > 230) & (b > 230)

    # ── 2) Desk strip + whiteboard frame line at the bottom ─────────
    # The original image has TWO horizontal bands below the hand:
    # (a) a thin medium-gray frame line (~rgb 170,170,170, almost no
    #     saturation), and (b) a muted blue desk surface (B > R).
    # Anything BELOW the hand (y > 60% of height) that is NOT skin
    # (skin tones have R > G > B and R > 150) gets removed. This is a
    # bit aggressive but the cropped output is much cleaner and we
    # avoid leaving a stray gray dash floating under the hand.
    desk_band = (np.arange(h)[:, None] > h * 0.62) & np.ones((1, w), dtype=bool)
    is_skin = (r > 150) & (r >= g) & (g >= b) & (r.astype(int) - b.astype(int) > 18)
    desk_mask = desk_band & ~is_skin

    # ── 3) "o de me" purple text in the upper-left corner ───────────
    # Restrict to a rectangle so we don't accidentally erase the dark
    # plastic body of the marker (which also has B > R locally due to
    # JPEG colour bleed). Anything in this corner area that is purple-
    # ish (B > R + 8, low brightness) gets removed.
    text_corner = (np.arange(w)[None, :] < 140) & (np.arange(h)[:, None] < 65)
    text_color = (
        (b.astype(int) - r.astype(int) > 8)
        & (r < 180) & (g < 180)
    )
    text_mask = text_corner & text_color

    drop_mask = white_mask | desk_mask | text_mask
    arr[..., 3] = np.where(drop_mask, 0, 255)

    # Re-build an Image for further processing.
    cleaned = Image.fromarray(arr, mode="RGBA")

    # ── 4) Locate the marker tip ────────────────────────────────────
    # The marker is the darkest large region in the upper-left of the
    # cleaned image. We pick the topmost non-transparent pixel whose
    # luminosity is below 80 — that is the very tip of the marker.
    op = arr[..., 3] > 0
    lum = (0.299 * r + 0.587 * g + 0.114 * b).astype(int)
    candidate = op & (lum < 80)
    ys, xs = np.where(candidate)
    if len(xs) == 0:
        raise RuntimeError("could not locate marker tip — drop_mask too aggressive?")
    # Topmost-leftmost dark pixel.
    top_y = int(ys.min())
    # Among rows close to the topmost, pick the leftmost.
    near_top = (ys < top_y + 8)
    tip_x = int(xs[near_top].min())
    tip_y = int(ys[near_top & (xs == tip_x)].min())
    print(f"tip detected at ({tip_x}, {tip_y})")

    # ── 5) Crop so the tip ends up at (0, 0) of the final PNG ───────
    # We need everything to the right and below the tip; anything to
    # the LEFT or ABOVE the tip is discarded (the contract).
    bbox = cleaned.getbbox()  # (l, t, r, b) of opaque pixels
    if bbox is None:
        raise RuntimeError("nothing opaque after cleanup")
    print(f"opaque bbox: {bbox}")
    crop_left = tip_x
    crop_top = tip_y
    crop_right = bbox[2]
    crop_bottom = bbox[3]
    final = cleaned.crop((crop_left, crop_top, crop_right, crop_bottom))

    final.save(DST, "PNG")
    print(f"saved: {DST} ({final.width}x{final.height})")


if __name__ == "__main__":
    main()
