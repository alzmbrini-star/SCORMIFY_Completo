"""Branded loading-overlay resolver shared by the HTML and SCORM exporters.

Decides what the initial "Carregando curso…" overlay should say and
which accent color it should use. Priorities:

  1. Per-course override on `project["course"]["loader"]`:
       { "title": "Carregando: Treinamento X…",
         "color": "#ff8800",
         "accentColor": "#ffaa44" }
  2. Brand kit `primaryColor` (and `accentColor` if present).
  3. Falls back to a neutral blue palette + the course's own title.

The helper is intentionally tolerant of malformed input — every step
is wrapped in defensive guards so a typo in the course payload never
breaks the export pipeline.
"""
from __future__ import annotations

import html
import re
from typing import Any, Optional


_HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}){1,2}$")

# Conservative fallbacks — match what the unbranded loader used before
# we added customization.
DEFAULT_TITLE = "Carregando curso…"
DEFAULT_PRIMARY = "#3b82f6"
DEFAULT_ACCENT = "#60a5fa"


def _safe_hex(value: Any, fallback: str) -> str:
    """Return `value` if it's a valid `#RGB`/`#RRGGBB`, else `fallback`."""
    if isinstance(value, str) and _HEX_RE.match(value.strip()):
        return value.strip()
    return fallback


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _lighten(hex_color: str, amount: float = 0.25) -> str:
    """Lighten a hex color toward white by `amount` (0..1). Used to
    derive a soft accent from the primary when no explicit accent is
    set in the brand kit."""
    r, g, b = _hex_to_rgb(hex_color)
    r = int(r + (255 - r) * amount)
    g = int(g + (255 - g) * amount)
    b = int(b + (255 - b) * amount)
    return f"#{r:02x}{g:02x}{b:02x}"


def resolve_loader_config(project: Optional[dict]) -> dict:
    """Return `{title_html, primary, accent}` ready to substitute into
    the HTML template (the title is already HTML-escaped)."""
    project = project or {}
    course = (project.get("course") or {}) if isinstance(project, dict) else {}
    metadata = course.get("metadata") or {}
    loader = course.get("loader") or {}
    brand_kit = project.get("brandKit") or {}

    # ── Title ────────────────────────────────────────────────────────
    raw_title = loader.get("title")
    if not isinstance(raw_title, str) or not raw_title.strip():
        course_title = metadata.get("title") or project.get("name") or ""
        if isinstance(course_title, str) and course_title.strip():
            raw_title = f"Carregando: {course_title.strip()}…"
        else:
            raw_title = DEFAULT_TITLE
    # Cap length so the overlay never breaks the layout on long titles.
    if len(raw_title) > 80:
        raw_title = raw_title[:77].rstrip() + "…"
    title_html = html.escape(raw_title, quote=True)

    # ── Colors ───────────────────────────────────────────────────────
    primary = _safe_hex(loader.get("color"), "")
    if not primary:
        primary = _safe_hex(brand_kit.get("primaryColor"), DEFAULT_PRIMARY)

    accent = _safe_hex(loader.get("accentColor"), "")
    if not accent:
        accent = _safe_hex(brand_kit.get("accentColor"), "")
    if not accent:
        accent = _lighten(primary, 0.25)

    return {
        "title_html": title_html,
        "primary": primary,
        "accent": accent,
    }
