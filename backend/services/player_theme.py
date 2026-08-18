"""Resolve per-company colors used by the traditional course player."""
from __future__ import annotations

import re
from typing import Any, Dict


DEFAULTS = {
    "canvas": "#0f0f1a",
    "header": "#101827",
    "navigation": "#16213e",
    "accent": "#0f3460",
    "sidebar": "#16213e",
    "sidebarHeader": "#0f3460",
    "sidebarItem": "#0f3460",
    "sidebarActive": "#312e81",
}


def _safe_hex(value: Any, fallback: str) -> str:
    raw = str(value or "").strip()
    if re.fullmatch(r"#[0-9a-fA-F]{6}", raw):
        return raw.lower()
    if re.fullmatch(r"#[0-9a-fA-F]{3}", raw):
        return "#" + "".join(char * 2 for char in raw[1:]).lower()
    return fallback


def _text_color(background: str) -> str:
    value = background.lstrip("#")
    red, green, blue = (int(value[i:i + 2], 16) for i in (0, 2, 4))
    luminance = (0.299 * red + 0.587 * green + 0.114 * blue) / 255
    return "#0f172a" if luminance > 0.62 else "#f8fafc"


def resolve_player_theme(project: Dict[str, Any] | None) -> Dict[str, str]:
    """Return safe player colors, preserving the legacy theme by default."""
    project = project or {}
    kit = project.get("brandKit") or {}
    canvas = _safe_hex(kit.get("playerCanvasColor"), DEFAULTS["canvas"])
    header = _safe_hex(kit.get("playerHeaderColor"), DEFAULTS["header"])
    navigation = _safe_hex(kit.get("playerNavigationColor"), DEFAULTS["navigation"])
    # Player chrome is opt-in. Do not reuse the slide accent automatically,
    # otherwise existing companies would see their navigation change merely
    # by having an older Brand Kit configured.
    accent = _safe_hex(kit.get("playerAccentColor"), DEFAULTS["accent"])
    sidebar = _safe_hex(kit.get("playerSidebarColor"), DEFAULTS["sidebar"])
    sidebar_header = _safe_hex(kit.get("playerSidebarHeaderColor"), DEFAULTS["sidebarHeader"])
    sidebar_item = _safe_hex(kit.get("playerSidebarItemColor"), DEFAULTS["sidebarItem"])
    sidebar_active = _safe_hex(kit.get("playerSidebarActiveColor"), DEFAULTS["sidebarActive"])
    return {
        "canvas": canvas,
        "header": header,
        "navigation": navigation,
        "accent": accent,
        "headerText": _text_color(header),
        "navigationText": _text_color(navigation),
        "accentText": _text_color(accent),
        "sidebar": sidebar,
        "sidebarHeader": sidebar_header,
        "sidebarItem": sidebar_item,
        "sidebarActive": sidebar_active,
        "sidebarText": _text_color(sidebar),
        "sidebarHeaderText": _text_color(sidebar_header),
        "sidebarItemText": _text_color(sidebar_item),
        "sidebarActiveText": _text_color(sidebar_active),
    }
