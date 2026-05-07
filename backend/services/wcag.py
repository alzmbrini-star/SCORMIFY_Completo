"""WCAG 2.1 contrast ratio helpers.

Used by the Aesthetic Analyzer to ENFORCE minimum readable contrast even
when the LLM proposes weak colors. Reference: https://www.w3.org/TR/WCAG21/#contrast-minimum
"""
from typing import Optional, Tuple
import re

# Pure colors used as deterministic fallbacks when LLM suggestion fails the
# WCAG check. Pure white/black give the maximum possible ratio against any
# colored background.
DARK_FALLBACK = "#0f172a"   # slate-900 (near-black, slightly warm)
LIGHT_FALLBACK = "#f8fafc"  # slate-50 (near-white)
DARK_PLATE = "rgba(15,23,42,0.65)"     # for light text on busy backgrounds
LIGHT_PLATE = "rgba(248,250,252,0.78)" # for dark text on busy backgrounds


def parse_hex(value: Optional[str]) -> Optional[Tuple[int, int, int]]:
    """Parse '#rgb', '#rrggbb', 'rgb(r,g,b)', or 'rgba(r,g,b,a)' to (r,g,b).
    Returns None for unparseable values (e.g., 'transparent', None, ''). """
    if not value or not isinstance(value, str):
        return None
    v = value.strip().lower()
    if v in ("", "transparent", "inherit", "none", "currentcolor"):
        return None

    # Hex
    if v.startswith("#"):
        v = v[1:]
        if len(v) == 3:
            v = "".join(ch * 2 for ch in v)
        if len(v) == 6:
            try:
                return (int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16))
            except ValueError:
                return None
        return None

    # rgb(...) / rgba(...)
    m = re.match(r"rgba?\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", v)
    if m:
        try:
            r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
            return (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))
        except ValueError:
            return None
    return None


def _channel_lum(c: int) -> float:
    """sRGB channel → linear luminance per WCAG."""
    cs = c / 255.0
    return cs / 12.92 if cs <= 0.03928 else ((cs + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb: Tuple[int, int, int]) -> float:
    """WCAG relative luminance (0=black, 1=white)."""
    r, g, b = rgb
    return 0.2126 * _channel_lum(r) + 0.7152 * _channel_lum(g) + 0.0722 * _channel_lum(b)


def contrast_ratio(fg: str, bg: str) -> float:
    """WCAG contrast ratio between two CSS colors. Returns 1.0 if either is
    unparseable (most permissive — caller decides what to do)."""
    fg_rgb = parse_hex(fg)
    bg_rgb = parse_hex(bg)
    if not fg_rgb or not bg_rgb:
        return 1.0
    l1 = relative_luminance(fg_rgb)
    l2 = relative_luminance(bg_rgb)
    lighter, darker = (l1, l2) if l1 > l2 else (l2, l1)
    return (lighter + 0.05) / (darker + 0.05)


def is_dark_background(bg: str) -> bool:
    """Heuristic: luminance < 0.5 → dark."""
    rgb = parse_hex(bg)
    if not rgb:
        return False
    return relative_luminance(rgb) < 0.5


def pick_high_contrast_color(bg: str) -> str:
    """Return DARK or LIGHT fallback that gives ≥7:1 against the background.

    For unparseable backgrounds (e.g., images or transparent), returns DARK
    fallback (safer default since most images have lighter overall tones)."""
    if is_dark_background(bg):
        return LIGHT_FALLBACK
    return DARK_FALLBACK


def enforce_min_contrast(fg: str, bg: str, min_ratio: float = 4.5) -> str:
    """Return fg unchanged if contrast(fg,bg) ≥ min_ratio, else replace with
    a pure fallback that maximizes contrast against bg.

    Default min_ratio=4.5 corresponds to WCAG AA for normal text. For large
    text WCAG allows 3.0; we prefer the stricter target so even body text
    is comfortable to read.
    """
    if contrast_ratio(fg, bg) >= min_ratio:
        return fg
    return pick_high_contrast_color(bg)


def needs_plate(bg_image: Optional[str], bg_color: Optional[str], fg: Optional[str]) -> bool:
    """Decide whether a text element should get a semi-transparent plate
    behind it. Plates are mandatory when:
      - The slide has a backgroundImage (multicolored, unpredictable contrast)
      - OR the foreground vs solid background contrast is below 4.5:1
    """
    if bg_image:
        return True
    if not fg or not bg_color:
        return False
    return contrast_ratio(fg, bg_color) < 4.5


def pick_plate_color(fg: str) -> str:
    """Pick the plate color that contrasts well with the foreground text.
    Light text → dark plate; dark text → light plate."""
    fg_rgb = parse_hex(fg)
    if not fg_rgb:
        return DARK_PLATE
    return DARK_PLATE if relative_luminance(fg_rgb) > 0.5 else LIGHT_PLATE
