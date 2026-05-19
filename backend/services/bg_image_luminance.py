"""Per-region luminance analysis for slide backgroundImages.

Used by the Aesthetic Analyzer to decide proper text contrast color when
an element sits over a `backgroundImage` whose lightness varies across
the canvas. Without this, the analyzer was only looking at the SOLID
`slide.background` color and producing wrong recommendations (e.g.,
suggesting white text on a slide whose decorative image has a giant
white shape in the center of the canvas, leaving most of the text
invisible).

Returns a dict per element:
  {
    "luminance": float,     # 0..1, mean perceived luminance
    "stddev": float,        # 0..1, variability in the region
    "tone": "light"|"dark"|"mixed",
    "recommendedTextColor": "#0f172a"|"#f8fafc",  # what to use
    "isMixed": bool,        # True when region has both light AND dark pixels
  }

The result is cached by (image_path, x, y, w, h, canvas_w, canvas_h)
inside an LRU cache.
"""
from __future__ import annotations

import logging
import re
from functools import lru_cache
from io import BytesIO
from typing import Optional, Tuple

logger = logging.getLogger("server")

# WCAG fallbacks — exposed here too so callers don't reach into wcag.py.
LIGHT_TEXT = "#f8fafc"
DARK_TEXT = "#0f172a"


def _luminance_of_rgb(pixels) -> Tuple[float, float]:
    """Return (mean, stddev) of relative luminance for an iterable of RGB
    triples. Both values in 0..1.
    Standard W3C coefficients: 0.2126*R + 0.7152*G + 0.0722*B
    """
    total = 0.0
    sq_total = 0.0
    n = 0
    for r, g, b in pixels:
        lum = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0
        total += lum
        sq_total += lum * lum
        n += 1
    if n == 0:
        return 0.5, 0.0
    mean = total / n
    var = max(0.0, (sq_total / n) - mean * mean)
    return mean, var ** 0.5


def _classify(mean: float, stddev: float) -> Tuple[str, str, bool]:
    """Pick a tone bucket and recommended text color from a region's stats."""
    # When the region has BOTH bright and dark pixels (high stddev),
    # neither pure white nor pure black guarantees contrast.
    is_mixed = stddev > 0.18
    if mean >= 0.55:
        return ("light", DARK_TEXT, is_mixed)
    if mean <= 0.35:
        return ("dark", LIGHT_TEXT, is_mixed)
    # Mid-tone — bias toward the side that has more contrast.
    if mean >= 0.5:
        return ("mixed" if is_mixed else "light", DARK_TEXT, is_mixed)
    return ("mixed" if is_mixed else "dark", LIGHT_TEXT, is_mixed)


def analyze_region(
    image_bytes: bytes,
    x_pct: float,
    y_pct: float,
    w_pct: float,
    h_pct: float,
) -> Optional[dict]:
    """Compute luminance stats for a sub-region of an image.

    All `*_pct` args are fractions of the image width/height (0..1).
    Coords are clamped to [0,1] and the box is enlarged a touch to give
    PIL a usable crop even for tiny elements.
    """
    try:
        from PIL import Image  # type: ignore
    except ImportError:
        logger.warning("Pillow not available — skipping region luminance")
        return None

    try:
        img = Image.open(BytesIO(image_bytes)).convert("RGB")
    except Exception as exc:
        logger.warning(f"PIL failed to decode bgImage: {exc}")
        return None

    W, H = img.size
    if W == 0 or H == 0:
        return None

    # Clamp & enforce a minimum crop so very thin elements still produce
    # meaningful stats.
    x = max(0.0, min(1.0, x_pct))
    y = max(0.0, min(1.0, y_pct))
    x2 = max(0.0, min(1.0, x_pct + w_pct))
    y2 = max(0.0, min(1.0, y_pct + h_pct))
    if x2 - x < 0.02:
        x2 = min(1.0, x + 0.02)
    if y2 - y < 0.02:
        y2 = min(1.0, y + 0.02)

    box = (int(x * W), int(y * H), int(x2 * W), int(y2 * H))
    region = img.crop(box)
    # Downsample for speed — 64x64 is plenty for luminance.
    region.thumbnail((64, 64))
    mean, stddev = _luminance_of_rgb(region.getdata())
    tone, rec_color, is_mixed = _classify(mean, stddev)
    return {
        "luminance": round(mean, 3),
        "stddev": round(stddev, 3),
        "tone": tone,
        "recommendedTextColor": rec_color,
        "isMixed": is_mixed,
    }


# ----- bgImage URL → bytes resolution -----------------------------------

_ASSET_URL_RE = re.compile(
    r"^/api/companies/(?P<company_id>[^/]+)/assets/(?P<asset_id>[^/]+)/file/?$"
)


async def fetch_bg_image_bytes(db, bg_image_url: Optional[str]) -> Optional[bytes]:
    """Resolve a slide `backgroundImage` URL/path to raw bytes.

    Currently supports the `/api/companies/{cid}/assets/{aid}/file` form
    that is produced by the Brand Library. Other formats (external URLs,
    inlined data URIs) return None — the caller falls back to the solid
    `slide.background` color in that case.
    """
    if not bg_image_url or not isinstance(bg_image_url, str):
        return None

    # Strip query string if present.
    clean = bg_image_url.split("?", 1)[0].split("#", 1)[0]
    m = _ASSET_URL_RE.match(clean)
    if not m:
        return None

    company_id = m.group("company_id")
    asset_id = m.group("asset_id")
    try:
        from services.asset_store import retrieve_company_asset_async
    except ImportError:
        # Fallback for older codebases that kept this helper inline
        from routes.company_assets import retrieve_company_asset_async  # type: ignore
    try:
        data, _ct = await retrieve_company_asset_async(db, company_id, asset_id)
        return data
    except Exception as exc:
        logger.warning(f"fetch_bg_image_bytes({asset_id}) failed: {exc}")
        return None


# ----- LRU cache shim ---------------------------------------------------
# Each call to `analyze_region` rescales/recrops, so we cache the FINAL
# `dict` keyed by (image hash short, normalized coords).

_REGION_CACHE: dict = {}
_REGION_CACHE_MAX = 256


def _cache_key(asset_id: str, x: float, y: float, w: float, h: float) -> str:
    # Bucket coords to 0.01 precision so near-identical regions share cache.
    return f"{asset_id}:{round(x, 2)}:{round(y, 2)}:{round(w, 2)}:{round(h, 2)}"


def get_cached(asset_id: str, x: float, y: float, w: float, h: float):
    return _REGION_CACHE.get(_cache_key(asset_id, x, y, w, h))


def set_cached(asset_id: str, x: float, y: float, w: float, h: float, value: dict):
    if len(_REGION_CACHE) >= _REGION_CACHE_MAX:
        # Evict a stale entry (FIFO-ish).
        try:
            _REGION_CACHE.pop(next(iter(_REGION_CACHE)))
        except StopIteration:
            pass
    _REGION_CACHE[_cache_key(asset_id, x, y, w, h)] = value
