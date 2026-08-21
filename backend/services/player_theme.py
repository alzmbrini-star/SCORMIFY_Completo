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

TUTOR_DEFAULTS = {
    "header": "#6366f1",
    "panel": "#1e1e2e",
    "accent": "#6366f1",
    "message": "#2a2a3e",
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


def resolve_tutor_theme(project: Dict[str, Any] | None) -> Dict[str, Any]:
    """Resolve Tutor colors from the company kit with safe player fallbacks.

    Dedicated Tutor colors take precedence. When they are empty, companies
    that already customized the player automatically receive a matching Tutor.
    Legacy courses without a Brand Kit keep the original purple/dark palette.
    """
    project = project or {}
    kit = project.get("brandKit") or {}
    header_fallback = kit.get("playerAccentColor") or kit.get("primaryColor") or TUTOR_DEFAULTS["header"]
    panel_fallback = kit.get("playerNavigationColor") or TUTOR_DEFAULTS["panel"]
    accent_fallback = kit.get("accentColor") or kit.get("playerAccentColor") or TUTOR_DEFAULTS["accent"]
    message_fallback = kit.get("playerSidebarItemColor") or TUTOR_DEFAULTS["message"]
    header = _safe_hex(kit.get("tutorHeaderColor"), _safe_hex(header_fallback, TUTOR_DEFAULTS["header"]))
    panel = _safe_hex(kit.get("tutorPanelColor"), _safe_hex(panel_fallback, TUTOR_DEFAULTS["panel"]))
    accent = _safe_hex(kit.get("tutorAccentColor"), _safe_hex(accent_fallback, TUTOR_DEFAULTS["accent"]))
    message = _safe_hex(kit.get("tutorMessageColor"), _safe_hex(message_fallback, TUTOR_DEFAULTS["message"]))
    customized = any(kit.get(key) for key in (
        "tutorHeaderColor", "tutorPanelColor", "tutorAccentColor", "tutorMessageColor",
        "playerAccentColor", "playerNavigationColor", "playerSidebarItemColor",
        "primaryColor", "accentColor",
    ))
    return {
        "customized": customized,
        "header": header,
        "panel": panel,
        "accent": accent,
        "message": message,
        "headerText": _text_color(header),
        "panelText": _text_color(panel),
        "accentText": _text_color(accent),
        "messageText": _text_color(message),
    }


def build_tutor_theme_css(theme: Dict[str, Any] | None) -> str:
    """Build scoped CSS overrides without weakening accessibility modes."""
    if theme and theme.get("customized") is False:
        return ""
    theme = theme or TUTOR_DEFAULTS
    header = _safe_hex(theme.get("header"), TUTOR_DEFAULTS["header"])
    panel = _safe_hex(theme.get("panel"), TUTOR_DEFAULTS["panel"])
    accent = _safe_hex(theme.get("accent"), TUTOR_DEFAULTS["accent"])
    message = _safe_hex(theme.get("message"), TUTOR_DEFAULTS["message"])
    header_text = _safe_hex(theme.get("headerText"), _text_color(header))
    panel_text = _safe_hex(theme.get("panelText"), _text_color(panel))
    accent_text = _safe_hex(theme.get("accentText"), _text_color(accent))
    message_text = _safe_hex(theme.get("messageText"), _text_color(message))
    normal = ".tutor-panel:not(.tutor-contrast-light):not(.tutor-contrast-high)"
    return f"""
/* Company Tutor theme. Light/high-contrast accessibility modes stay sovereign. */
.tutor-fab {{ background: {accent}; color: {accent_text}; box-shadow: 0 4px 20px {accent}66; }}
.tutor-fab:hover {{ box-shadow: 0 6px 28px {accent}80; }}
{normal} {{ background: {panel}; color: {panel_text}; }}
{normal} .tutor-header {{ background: {header}; color: {header_text}; }}
{normal} .tutor-header button {{ color: {header_text}; }}
{normal} .tutor-slide-indicator {{ background: {message}; color: {message_text}; border-color: {accent}66; }}
{normal} .tutor-suggestions {{ border-color: {accent}55; }}
{normal} .tutor-suggestion-btn {{ border-color: {accent}; color: {panel_text}; }}
{normal} .tutor-suggestion-btn:hover,
{normal} .tutor-msg.user,
{normal} .tutor-send {{ background: {accent}; color: {accent_text}; border-color: {accent}; }}
{normal} .tutor-msg.assistant,
{normal} .tutor-typing,
{normal} .tutor-input {{ background: {message}; color: {message_text}; }}
{normal} .tutor-msg.assistant strong {{ color: {accent}; }}
{normal} .tutor-typing span {{ background: {accent}; }}
{normal} .tutor-input-area,
{normal} .tutor-counter {{ background: {panel}; color: {panel_text}; border-color: {accent}55; }}
{normal} .tutor-input {{ border-color: {accent}99; }}
{normal} .tutor-input:focus {{ border-color: {accent}; }}
{normal} .tutor-a11y-bar {{ border-color: {accent}55; }}
""".strip()


def build_single_page_player_theme_css(theme: Dict[str, Any] | None) -> str:
    """Map the company player palette to standalone/single-page classes."""
    theme = theme or DEFAULTS
    canvas = _safe_hex(theme.get("canvas"), DEFAULTS["canvas"])
    header = _safe_hex(theme.get("header"), DEFAULTS["header"])
    navigation = _safe_hex(theme.get("navigation"), DEFAULTS["navigation"])
    accent = _safe_hex(theme.get("accent"), DEFAULTS["accent"])
    sidebar = _safe_hex(theme.get("sidebar"), DEFAULTS["sidebar"])
    sidebar_item = _safe_hex(theme.get("sidebarItem"), DEFAULTS["sidebarItem"])
    sidebar_active = _safe_hex(theme.get("sidebarActive"), DEFAULTS["sidebarActive"])
    header_text = _safe_hex(theme.get("headerText"), _text_color(header))
    navigation_text = _safe_hex(theme.get("navigationText"), _text_color(navigation))
    accent_text = _safe_hex(theme.get("accentText"), _text_color(accent))
    sidebar_text = _safe_hex(theme.get("sidebarText"), _text_color(sidebar))
    sidebar_item_text = _safe_hex(theme.get("sidebarItemText"), _text_color(sidebar_item))
    sidebar_active_text = _safe_hex(theme.get("sidebarActiveText"), _text_color(sidebar_active))
    return f"""
/* Company player theme - standalone HTML parity with SCORM. */
html, body {{ background: {canvas}; }}
.sp-bg-image, .sp-bg-pattern {{ background-color: {canvas}; }}
.sp-bg-pattern {{ background: {canvas}; }}
.sp-header {{ background: {header}; color: {header_text}; }}
.sp-header .sp-title, .sp-header .sp-menu-btn,
.sp-header .sp-fullscreen-btn, .sp-header .sp-bg-music-toggle {{ color: {header_text}; }}
.sp-progress {{ background: {navigation}; }}
.sp-progress-fill {{ background: {accent}; }}
.sp-drawer {{ background: {sidebar}; color: {sidebar_text}; border-color: {accent}; }}
.sp-drawer-list li {{ background: {sidebar_item}; color: {sidebar_item_text}; }}
.sp-drawer-list li.unlocked:hover,
.sp-drawer-list li.active {{ background: {sidebar_active}; color: {sidebar_active_text}; border-color: {accent}; }}
.sp-drawer-list li.completed::before,
.sp-drawer-list li.unlocked:not(.completed):not(.locked)::before {{ color: {accent}; }}
.sp-next-btn, .sp-btn-primary {{ background: {accent}; color: {accent_text}; }}
.sp-next-btn:hover, .sp-btn-primary:hover {{ background: {accent}; filter: brightness(1.08); }}
.sp-next-btn::before {{ border-color: {accent}80; }}
.sp-narration-controls {{ background: {navigation}; color: {navigation_text}; }}
.sp-narration-btn {{ color: {navigation_text}; }}
""".strip()
