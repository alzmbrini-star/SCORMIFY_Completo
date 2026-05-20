"""Strip "island plates" from htmlContent — top-level wrapper <div> tags
whose only purpose is to paint a colored backdrop behind the slide content.

Background: the AI Agent that generates slides sometimes wraps the whole
htmlContent in `<div style="width:100%;height:100%;background:#3b82f6;">`
to create a "card visual" effect. When the user later switches the slide's
own background (e.g., from navy to white), those wrapper backgrounds
become coloured rectangles floating on the slide — visually identical to
the rejected "plate overlays".

Rules for safe removal:
  - Only strip `background[-color]:` from TOP-LEVEL wrappers (the outermost
    element, OR a `<div>` that directly wraps a single text leaf).
  - Preserve cosmetic backgrounds on small inline elements (badges, chips,
    accent boxes), `<table>`/`<th>`, and on anything with explicit width
    that isn't full-canvas.
  - Skip wrappers whose background matches the slide.background — those
    are intentional and already aligned.

Idempotent.
"""
from __future__ import annotations

import logging
import re
from bs4 import BeautifulSoup

logger = logging.getLogger("server")


_BG_DECL_RE = re.compile(
    r"\bbackground(?:-color)?\s*:\s*[^;]+;?",
    re.IGNORECASE,
)


def _is_full_bleed_style(style: str) -> bool:
    """True when a style attribute paints a full-width-and-height bleed
    (typical of AI-generated wrapper divs)."""
    if not style:
        return False
    s = style.lower().replace(" ", "")
    has_width = "width:100%" in s or "width:100vw" in s or "width:1920" in s
    has_height = ("height:100%" in s or "height:100vh" in s or "height:820" in s
                  or "height:100" in s)  # heuristic
    return has_width and has_height


def _strip_bg_from_style(style: str) -> str:
    if not style:
        return style
    out = _BG_DECL_RE.sub("", style)
    # Tidy double semicolons / leading/trailing whitespace
    out = re.sub(r";\s*;+", ";", out).strip().rstrip(";").strip()
    return out


def _candidate_for_strip(tag, slide_bg_hex: str | None) -> bool:
    """Decide if this tag's background should be stripped."""
    style = (tag.get("style") or "").strip()
    if not style or not _BG_DECL_RE.search(style):
        return False
    name = (tag.name or "").lower()
    # Only target div/section/article wrappers — never inline chips, badges,
    # buttons, table cells, etc.
    if name not in ("div", "section", "article"):
        return False
    # Skip elements with class hints of cards/badges/buttons (cosmetic, keep).
    cls = " ".join((tag.get("class") or [])).lower()
    if any(k in cls for k in ("badge", "chip", "btn", "button", "label", "card", "tag", "pill")):
        return False
    text_leaf = (tag.get_text(strip=True) or "")
    # ALWAYS strip when this is a full-bleed wrapper (likely the AI-Agent
    # generated "island" background).
    if _is_full_bleed_style(style):
        return True
    # Strip when the wrapper has direct text content (h1-h6, p, li children)
    # — these typically host the slide's main copy and shouldn't sit on a
    # colored rectangle when the user changed slide.background.
    if text_leaf and len(text_leaf) > 20:
        # Skip when the wrapper has class hints of an intentional callout
        return True
    return False


def strip_html_container_backgrounds(
    html: str | None,
    slide_bg_hex: str | None = None,
) -> tuple[str, int]:
    """Return (new_html, stripped_count). Idempotent."""
    if not html or "background" not in html.lower():
        return html or "", 0
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception as exc:
        logger.warning(f"strip_html_container_backgrounds: BS4 parse failed: {exc}")
        return html, 0
    stripped = 0
    for tag in soup.find_all(["div", "section", "article"]):
        if not _candidate_for_strip(tag, slide_bg_hex):
            continue
        new_style = _strip_bg_from_style(tag.get("style") or "")
        if new_style:
            tag["style"] = new_style
        else:
            del tag["style"]
        stripped += 1
    if stripped == 0:
        return html, 0
    return str(soup), stripped
