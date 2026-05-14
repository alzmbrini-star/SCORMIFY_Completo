"""Apply a company's BrandKit (colors + font) on top of the design template
palette used by the AI Agent slide builder.

The Agent's `_build_*_slide` functions read everything from a `palette` dict
with keys: primary, accent, accentLight, contentBg, text, fontHeading,
fontBody, headerStyle, cornerRadius. By mutating that dict ONCE — at the
top of `generate_course_from_storyboard` — we get brand-aware slides without
touching the ~30 builder call-sites individually.

Resolution rules:
  - brandKit.primaryColor   → palette.primary   (slide chrome / header bg)
  - brandKit.accentColor    → palette.accent    (dividers / pills / callouts)
                             + a lighter version → palette.accentLight (tints)
  - brandKit.secondaryColor → palette.text      (body copy color)
  - brandKit.fontFamily     → palette.fontHeading + palette.fontBody

Missing/empty brandKit fields fall through to whatever the design template
provided. So a company can override just the primary color and keep the
designer-chosen accent if they want.
"""
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


def _is_hex_color(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    v = value.strip()
    if not v.startswith("#"):
        return False
    # 3, 4, 6, 8-digit hex codes are all valid CSS colors
    rest = v[1:]
    if len(rest) not in (3, 4, 6, 8):
        return False
    return all(c in "0123456789abcdefABCDEF" for c in rest)


def _lighten_hex(hex_str: str, factor: float = 0.85) -> str:
    """Return a lighter version of a hex color (factor 0..1, higher = lighter).

    Used to derive `accentLight` from `accentColor` so the agent's "pill" and
    "callout" backgrounds stay legible against light slide backgrounds.
    """
    if not _is_hex_color(hex_str):
        return hex_str
    h = hex_str.strip().lstrip("#")
    # Expand 3-digit shorthand
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    elif len(h) == 4:
        h = "".join(c * 2 for c in h[:3])  # drop alpha
    elif len(h) == 8:
        h = h[:6]  # drop alpha
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        return hex_str
    r = round(r + (255 - r) * factor)
    g = round(g + (255 - g) * factor)
    b = round(b + (255 - b) * factor)
    return f"#{r:02x}{g:02x}{b:02x}"


def apply_brand_kit_to_palette(palette: Dict[str, Any], brand_kit: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Return a NEW palette dict with brand kit overrides applied.

    Args:
        palette: the design-template palette (mutated copy is returned).
        brand_kit: the company's BrandKit (or None / empty dict).

    Returns:
        A new palette dict. Original palette is not mutated so the caller
        can still log/serialize the design-template version for debugging.
    """
    out = dict(palette or {})
    if not brand_kit or not isinstance(brand_kit, dict):
        return out

    primary = brand_kit.get("primaryColor")
    secondary = brand_kit.get("secondaryColor")
    accent = brand_kit.get("accentColor")
    font_family = brand_kit.get("fontFamily")

    if _is_hex_color(primary):
        out["primary"] = primary
    if _is_hex_color(secondary):
        out["text"] = secondary
    if _is_hex_color(accent):
        out["accent"] = accent
        # Always derive a fresh accentLight so the two stay coherent.
        out["accentLight"] = _lighten_hex(accent, 0.82)

    if isinstance(font_family, str) and font_family.strip():
        ff = font_family.strip()
        # If the user already wrote a full stack like "Inter, sans-serif",
        # pass it through verbatim. Otherwise wrap multi-word names in
        # quotes and append a generic fallback so CSS stays valid when the
        # font isn't loaded.
        if "," not in ff:
            if " " in ff and not ff.startswith(("'", '"')):
                ff = f"'{ff}'"
            ff = f"{ff}, sans-serif"
        out["fontHeading"] = ff
        out["fontBody"] = ff

    return out


async def fetch_brand_kit(db, company_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a company's BrandKit. Returns None when no kit exists or company
    is missing — callers treat None as a no-op (palette stays as-is)."""
    if not company_id or db is None:
        return None
    try:
        doc = await db.companies.find_one(
            {"id": company_id},
            {"_id": 0, "brandKit": 1},
        )
        if not doc:
            return None
        kit = doc.get("brandKit") or None
        if not kit:
            return None
        return kit
    except Exception as e:
        logger.warning(f"fetch_brand_kit failed for {company_id}: {e}")
        return None
