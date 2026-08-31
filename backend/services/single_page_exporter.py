"""Single Page (vertical scroll / scrollytelling) HTML exporter.

Renders ALL course slides stacked vertically as 'sections' in one HTML page.
Navigation: a single down-chevron button at bottom-right that ONLY appears
when the user has clicked every interactive element of the current section.
A hamburger menu drawer lets the student jump back to already-unlocked
sections (linear strict — locked sections cannot be opened).

Tracked interactives per section:
  - <audio> / <video> elements (must press play at least once)
  - elements with class "sp-clickable" or [data-clickable="true"] (must click)
  - quiz blocks (must finish quiz)
  - scenario / simulator blocks (must open / start)

A thin progress bar at the top reflects (sectionsUnlocked / totalSections).

When all sections are unlocked AND all required quizzes were answered,
the exporter dispatches a 'sp:course-completed' event that SCORM and
LMS integrations can listen to (used in fase 2 for cmi.completion_status).
"""
from __future__ import annotations

import base64
import html
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


# --------------------------------------------------------------------------- helpers


def _b64_data_uri(file_path: str) -> Optional[str]:
    """Read a local asset and return a data URI for inlining into the HTML."""
    try:
        p = Path(file_path)
        if not p.exists() or not p.is_file():
            return None
        ext = p.suffix.lower().lstrip(".")
        mime_map = {
            "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
            "gif": "image/gif", "webp": "image/webp", "svg": "image/svg+xml",
            "mp3": "audio/mpeg", "wav": "audio/wav", "ogg": "audio/ogg",
            "mp4": "video/mp4", "webm": "video/webm", "pdf": "application/pdf",
        }
        mime = mime_map.get(ext, "application/octet-stream")
        data = base64.b64encode(p.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{data}"
    except Exception:
        return None


def _resolve_asset_url(url: str, project_id: str, assets_dir: str, base_url: str = "") -> str:
    """Convert a /api/projects/<id>/assets/<file> URL to an inlined data URI
    when the file exists on disk. Also supports /api/companies/<cid>/assets/<aid>/file
    when the file has been pre-extracted via `prepare_company_assets_for_export`
    into `assets_dir/_companies/<aid>.<ext>`.

    Also resolves /api/whiteboard/file/wb_*.{mp4,png} URLs from the
    Whiteboard renderer (transparent APNG / opaque MP4 outputs) by
    reading from `backend/storage/whiteboard/`.

    Falls back to absolute base_url + path when neither local resolution works.
    """
    if not url:
        return url
    if url.startswith("data:") or url.startswith("blob:"):
        return url
    # Match Whiteboard renderer output (MP4 or APNG). These live in a
    # global storage dir, not the per-project assets dir.
    m_wb = re.match(r"^/api/whiteboard/file/([^/?#]+)$", url)
    if m_wb:
        wb_name = m_wb.group(1)
        wb_path = Path(__file__).parent.parent / "storage" / "whiteboard" / wb_name
        data_uri = _b64_data_uri(str(wb_path))
        if data_uri:
            return data_uri
        if base_url:
            return f"{base_url.rstrip('/')}{url}"
    # Match local project asset path
    m = re.match(r"^/api/projects/[^/]+/assets/(.+)$", url)
    if m:
        fname = m.group(1)
        local_path = Path(assets_dir) / fname
        data_uri = _b64_data_uri(str(local_path))
        if data_uri:
            return data_uri
        if base_url:
            return f"{base_url.rstrip('/')}{url}"
    # Match company asset path (brand kit images, logos, watermarks, etc.)
    # Format: /api/companies/<company_id>/assets/<asset_id>/file
    # These need to have been pre-extracted by `prepare_company_assets_for_export`
    # into assets_dir/_companies/<asset_id>.<ext>. Without that pre-step, the
    # SCORM/HTML export would leave the URL untouched and the brand image
    # would be broken offline.
    m2 = re.match(r"^/api/companies/[^/]+/assets/([^/]+)/file/?$", url)
    if m2:
        asset_id = m2.group(1)
        # Try every common extension we may have written.
        for ext in ("png", "jpg", "jpeg", "gif", "webp", "svg", "mp4", "mp3", "ogg", "bin"):
            local_path = Path(assets_dir) / "_companies" / f"{asset_id}.{ext}"
            data_uri = _b64_data_uri(str(local_path))
            if data_uri:
                return data_uri
        if base_url:
            return f"{base_url.rstrip('/')}{url}"
    if url.startswith("/") and base_url:
        return f"{base_url.rstrip('/')}{url}"
    return url


def _is_dark_color(hex_color: str) -> bool:
    """Return True if the given #RRGGBB color is dark enough to need light text."""
    if not hex_color or not hex_color.startswith("#"):
        return False
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        return False
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        return False
    # Perceived luminance (WCAG-ish formula)
    lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return lum < 0.5


def _esc(s: Any) -> str:
    if s is None:
        return ""
    return html.escape(str(s), quote=True)


def _inline_assets_in_html(html_str: str, project_id: str, assets_dir: str, base_url: str) -> str:
    """Replace asset URLs inside an htmlContent fragment with data URIs.

    Covers BOTH `/api/projects/<id>/assets/...` (per-project files on disk)
    AND `/api/companies/<cid>/assets/<aid>/file` (brand-kit images) so the
    SCORM/HTML package is fully self-contained offline.
    """
    if not html_str:
        return ""

    def repl(match: re.Match) -> str:
        full = match.group(0)
        url = match.group(1)
        new_url = _resolve_asset_url(url, project_id, assets_dir, base_url)
        return full.replace(url, new_url)

    pattern = re.compile(
        r'(?:src|href)\s*=\s*"((?:/api/projects/[^"]+|/api/companies/[^"]+/assets/[^"]+/file))"'
    )
    html_str = pattern.sub(repl, html_str)

    # Also inline CSS-level `url(...)` references in style attributes/blocks.
    css_pattern = re.compile(
        r'url\(\s*[\'"]?((?:/api/projects/[^\'")]+|/api/companies/[^\'")]+/assets/[^\'")]+/file))[\'"]?\s*\)'
    )

    def css_repl(match: re.Match) -> str:
        url = match.group(1)
        new_url = _resolve_asset_url(url, project_id, assets_dir, base_url)
        return f'url("{new_url}")'

    return css_pattern.sub(css_repl, html_str)


def _kebab(name: str) -> str:
    return re.sub(r"([A-Z])", r"-\1", name).lower()


def _safe_text_html(s: str) -> str:
    """Allow line breaks but escape everything else for safety."""
    if s is None:
        return ""
    return re.sub(r"\r?\n", "<br>", _esc(s))


# --------------------------------------------------------------------------- element renderers



def _render_element(el: dict, project_id: str, assets_dir: str, base_url: str,
                     slide_idx: int, el_idx: int, questions_lookup: Dict[str, dict]) -> str:
    """Render a single element as a flow-block (no absolute positioning).
    Each element type has its own max-width to avoid videos/avatars taking
    over the entire card."""
    etype = (el.get("type") or "text").lower()
    if etype == "text":
        rendered = _render_text_element_inner(el)
    elif etype == "image":
        rendered = _render_image_element_inner(el, project_id, assets_dir, base_url)
    elif etype == "audio":
        rendered = _render_audio_element_inner(el, project_id, assets_dir, base_url, el_idx)
    elif etype == "video":
        rendered = _render_video_element_inner(el, project_id, assets_dir, base_url, el_idx)
    elif etype == "avatar":
        rendered = _render_avatar_element_inner(el, project_id, assets_dir, base_url, el_idx)
    elif etype == "html":
        rendered = _render_html_element_inner(el, project_id, assets_dir, base_url, slide_idx, el_idx)
    elif etype == "quiz":
        rendered = _render_quiz_element_inner(el, slide_idx, el_idx, questions_lookup)
    elif etype == "scenario":
        rendered = _render_scenario_element_inner(el, slide_idx, el_idx)
    elif etype == "simulator":
        rendered = _render_simulator_element_inner(el, project_id, assets_dir, base_url, slide_idx, el_idx)
    elif etype == "button":
        rendered = _render_button_element_inner(el, slide_idx, el_idx)
    elif etype == "shape":
        rendered = _render_shape_element_inner(el)
    elif etype == "flipbook":
        rendered = _render_flipbook_element_inner(el, project_id, assets_dir, base_url, slide_idx, el_idx)
    else:
        return ""
    return _maybe_wrap_with_timeline(rendered, el)


def _render_flipbook_element_inner(el: dict, project_id: str, assets_dir: str, base_url: str,
                                   slide_idx: int, el_idx: int) -> str:
    """Render a flipbook element. PDFs are embedded as base64 and loaded via a
    blob URL at runtime so the single-page export works fully offline."""
    ftype = (el.get("flipbookType") or "external").lower()
    url = el.get("flipbookUrl") or ""
    if ftype == "pdf":
        display = (el.get("pdfDisplay") or "full").lower()
        # Pages-only mode: pre-converted page images, clean visual
        if display == "pages" and el.get("pdfPages"):
            imgs = "".join(
                f'<img src="{_esc(_resolve_asset_url(p, project_id, assets_dir, base_url))}" loading="lazy" '
                f'style="max-width:100%;height:auto;border-radius:8px;margin-bottom:8px;display:block;'
                f'box-shadow:0 4px 14px rgba(0,0,0,.12)" />'
                for p in el["pdfPages"] if p
            )
            return f'<div class="sp-pdf-pages">{imgs}</div>' if imgs else ""
        if url:
            clean_suffix = '#toolbar=0&navpanes=0&scrollbar=0' if display == "clean" else ''
            resolved = _resolve_asset_url(url, project_id, assets_dir, base_url)
            if resolved.startswith("data:application/pdf"):
                b64 = resolved.split(",", 1)[1]
                iframe_id = f"sp-pdf-{slide_idx}-{el_idx}"
                return (
                    f'<div class="sp-pdf" style="margin:0 0 8px 0">'
                    f'<iframe id="{iframe_id}" title="Documento PDF" '
                    f'style="width:100%;height:640px;border:0;border-radius:12px;background:#fff;box-shadow:0 6px 20px rgba(0,0,0,.18)"></iframe>'
                    f'<script>(function(){{var b="{b64}";var bin=atob(b);var u=new Uint8Array(bin.length);'
                    f'for(var i=0;i<bin.length;i++)u[i]=bin.charCodeAt(i);'
                    f'document.getElementById("{iframe_id}").src=URL.createObjectURL(new Blob([u],{{type:"application/pdf"}}))+"{clean_suffix}";}})();</scr'
                    f'ipt></div>'
                )
            if resolved:
                return (
                    f'<iframe src="{_esc(resolved + clean_suffix)}" title="Documento PDF" '
                    f'style="width:100%;height:640px;border:0;border-radius:12px;background:#fff"></iframe>'
                )
        return ""
    if ftype == "external" and url:
        return (
            f'<iframe src="{_esc(url)}" title="Flipbook" allow="fullscreen" '
            f'style="width:100%;height:640px;border:0;border-radius:12px;background:#fff"></iframe>'
        )
    if ftype == "images":
        pages = el.get("flipbookPages") or []
        imgs = "".join(
            f'<img src="{_esc(_resolve_asset_url(p, project_id, assets_dir, base_url))}" loading="lazy" '
            f'style="max-width:100%;height:auto;border-radius:8px;margin-bottom:8px" />'
            for p in pages if p
        )
        return f'<div class="sp-flipbook-images">{imgs}</div>' if imgs else ""
    return ""


def _render_button_element_inner(el: dict, slide_idx: int, el_idx: int) -> str:
    """Render a button element. Buttons typically link to external resources
    (PDFs, downloads, websites). When `buttonUrl` is set we render an <a> tag;
    otherwise a passive <button>. The button is treated as an interactive
    that gates section progression — clicking marks it as completed."""
    text = _esc(el.get("buttonText") or el.get("content") or "Botão")
    url = el.get("buttonUrl") or ""
    new_tab = ' target="_blank" rel="noopener noreferrer"' if el.get("openInNewTab", True) else ""
    style_palette = el.get("buttonStyle") or "primary"
    palette_map = {
        "primary": "background:#2563eb;color:#fff;border:0",
        "secondary": "background:#6b7280;color:#fff;border:0",
        "outline": "background:transparent;color:#2563eb;border:2px solid #2563eb",
        "ghost": "background:transparent;color:#2563eb;border:0",
        "destructive": "background:#dc2626;color:#fff;border:0",
        "success": "background:#16a34a;color:#fff;border:0",
    }
    palette = palette_map.get(style_palette, palette_map["primary"])
    style_obj = el.get("style") or {}
    extra_style = []
    fs = style_obj.get("fontSize")
    if fs:
        extra_style.append(f"font-size:{fs}px" if isinstance(fs, (int, float)) else f"font-size:{fs}")
    fw = style_obj.get("fontWeight")
    if fw:
        extra_style.append(f"font-weight:{fw}")
    br = style_obj.get("borderRadius")
    if br is not None:
        extra_style.append(f"border-radius:{br}px" if isinstance(br, (int, float)) else f"border-radius:{br}")
    extra = ";".join(extra_style)
    common_style = (
        "display:inline-flex;align-items:center;justify-content:center;gap:8px;"
        f"padding:12px 24px;{palette};{extra};"
        "cursor:pointer;text-decoration:none;font-weight:600;"
        "transition:transform .15s ease,box-shadow .15s ease;"
        "box-shadow:0 2px 6px rgba(0,0,0,.1)"
    )
    interactive_attrs = (
        f'class="sp-button sp-interactive" data-interactive="button" '
        f'data-required="true" data-interactive-id="button-{slide_idx}-{el_idx}"'
    )
    if url:
        return (
            f'<div {interactive_attrs} style="display:flex;justify-content:center;padding:8px">'
            f'<a href="{_esc(url)}"{new_tab} '
            f'onclick="window.SP&&SP.markClicked(this.closest(\'.sp-interactive\'))" '
            f'style="{common_style}">{text}</a>'
            f'</div>'
        )
    return (
        f'<div {interactive_attrs} style="display:flex;justify-content:center;padding:8px">'
        f'<button type="button" '
        f'onclick="window.SP&&SP.markClicked(this.closest(\'.sp-interactive\'))" '
        f'style="{common_style}">{text}</button>'
        f'</div>'
    )


def _render_shape_element_inner(el: dict) -> str:
    """Render a basic shape element (rectangle/circle/arrow). Decorative —
    no required interactive."""
    style_obj = el.get("style") or {}
    fill = style_obj.get("fill") or "#94a3b8"
    stroke = style_obj.get("stroke")
    stroke_width = style_obj.get("strokeWidth") or 0
    border = f"border:{stroke_width}px solid {stroke}" if stroke and stroke_width else "border:0"
    shape_type = (el.get("shapeType") or "rectangle").lower()
    radius = "border-radius:50%" if shape_type == "circle" else "border-radius:8px"
    width = el.get("width") or 100
    height = el.get("height") or 60
    try:
        w_str = f"{int(float(width))}px"
        h_str = f"{int(float(height))}px"
    except (TypeError, ValueError):
        w_str = "100px"
        h_str = "60px"
    return (
        f'<div class="sp-shape" style="display:flex;justify-content:center;padding:4px">'
        f'<div style="width:{w_str};height:{h_str};background:{fill};{border};{radius}"></div>'
        f'</div>'
    )


def _maybe_wrap_with_timeline(rendered_html: str, el: dict) -> str:
    """If the element has a startTime > 0 or endTime > 0 timeline, wrap it in
    a `.sp-element-timed` div that the JS runtime will reveal/hide on schedule.
    Without wrapping, all elements render simultaneously (legacy behavior)."""
    if not rendered_html:
        return rendered_html
    try:
        start = float(el.get("startTime") or 0)
    except (TypeError, ValueError):
        start = 0.0
    try:
        end_raw = el.get("endTime")
        end = float(end_raw) if end_raw is not None else 0.0
    except (TypeError, ValueError):
        end = 0.0
    if start <= 0 and end <= 0:
        return rendered_html
    attrs = []
    if start > 0:
        attrs.append(f'data-start-time="{start}"')
    if end > 0:
        attrs.append(f'data-end-time="{end}"')
    return f'<div class="sp-element-timed" {" ".join(attrs)}>{rendered_html}</div>'


# --------------------------------------------------------------------------- inner renderers

# Style-key → CSS-property mappings. Without this, _kebab() turned legacy
# editor keys into invalid CSS that browsers silently dropped — so e.g.
# `fontColor: '#fff'` rendered as `font-color:#fff` and the text kept its
# default color. Map them to the canonical CSS property names instead.
_STYLE_KEY_MAP = {
    "fontColor": "color",
    "color": "color",
    "fontSize": "font-size",
    "fontFamily": "font-family",
    "fontWeight": "font-weight",
    "fontStyle": "font-style",
    "textAlign": "text-align",
    "textDecoration": "text-decoration",
    "lineHeight": "line-height",
    "letterSpacing": "letter-spacing",
    "backgroundColor": "background-color",
    "textBackgroundColor": "background-color",   # plate alias
    "borderRadius": "border-radius",
    "borderColor": "border-color",
    "borderWidth": "border-width",
    "borderStyle": "border-style",
    "border": "border",
    "padding": "padding",
    "margin": "margin",
    "boxShadow": "box-shadow",
    "textShadow": "text-shadow",
    "opacity": "opacity",
    "fill": "color",  # legacy alias
}

_STYLE_NUMERIC_PX_KEYS = {"fontSize", "borderRadius", "padding", "margin", "borderWidth", "lineHeight"}


def _format_style_value(key: str, value) -> str:
    """Format a style value, adding 'px' for numeric values on size keys."""
    # line-height is special — unitless is preferred
    if key == "lineHeight":
        return _esc(value)
    if isinstance(value, (int, float)) and key in _STYLE_NUMERIC_PX_KEYS:
        return f"{value}px"
    return _esc(value)


def _style_dict_to_css(style: dict) -> str:
    """Convert an editor style dict into CSS declarations. Maps known keys
    to canonical CSS properties and skips invalid/unknown ones to avoid
    polluting the inline style attribute with garbage like `font-color:`."""
    if not style:
        return ""
    parts = []
    for k, v in style.items():
        if v in (None, ""):
            continue
        if k in ("position", "top", "left", "right", "bottom"):
            continue
        css_key = _STYLE_KEY_MAP.get(k)
        if not css_key:
            # Skip unknown keys silently — better than emitting invalid CSS
            continue
        parts.append(f"{css_key}:{_format_style_value(k, v)}")
    return ";".join(parts)


def _render_text_element_inner(el: dict) -> str:
    content = el.get("content") or ""
    style = el.get("style") or {}
    style_attr = _style_dict_to_css(style)
    return f'<div class="sp-text" style="{style_attr}">{_safe_text_html(content)}</div>'


def _render_image_element_inner(el: dict, project_id: str, assets_dir: str, base_url: str) -> str:
    # Support both `src` (canonical) and `imageUrl` (legacy from the
    # brand-kit applier which writes logos with imageUrl). Falling back to
    # `content` last for ancient slides that stored the URL there.
    src = el.get("src") or el.get("imageUrl") or el.get("content") or ""
    src = _resolve_asset_url(src, project_id, assets_dir, base_url)
    alt = _esc(el.get("alt", ""))
    style = el.get("style") or {}
    radius = style.get("borderRadius", "8px")
    if el.get("journeyInteractive"):
        evidence = el.get("visualEvidence") or []
        if not isinstance(evidence, list):
            evidence = [str(evidence)]
        evidence = [str(item).strip() for item in evidence if str(item).strip()][:3]
        while len(evidence) < 3:
            evidence.append(("Observe o contexto", "Identifique o indício", "Relacione com a decisão")[len(evidence)])
        prompt = _esc(el.get("observationPrompt") or "Explore os pontos da cena.")
        pins = "".join(
            f'<button type="button" class="sp-evidence-pin sp-evidence-pin-{idx + 1}" '
            f'aria-label="Revelar evidência {idx + 1}" onclick="this.parentNode.classList.add(\'is-explored\');'
            f'this.parentNode.querySelector(\'[data-evidence=\'{idx}\']\').classList.toggle(\'is-visible\')">{idx + 1}</button>'
            for idx in range(3)
        )
        cards = "".join(
            f'<div class="sp-evidence-card" data-evidence="{idx}"><b>{idx + 1}</b><span>{_esc(item)}</span></div>'
            for idx, item in enumerate(evidence)
        )
        return (
            f'<figure class="sp-image sp-evidence-scene" style="margin:0">'
            f'<div class="sp-evidence-prompt">🔎 {prompt}</div>'
            f'<div class="sp-evidence-media"><img src="{_esc(src)}" alt="{alt}" loading="lazy" />{pins}</div>'
            f'<figcaption class="sp-evidence-cards">{cards}</figcaption>'
            f'</figure>'
        )
    return (
        f'<figure class="sp-image" style="margin:0;display:flex;justify-content:center">'
        f'<img src="{_esc(src)}" alt="{alt}" loading="lazy" '
        f'style="max-width:100%;height:auto;border-radius:{_esc(radius)};box-shadow:0 6px 20px rgba(0,0,0,.18)" />'
        f'</figure>'
    )


def _render_audio_element_inner(el: dict, project_id: str, assets_dir: str, base_url: str, idx: int) -> str:
    src = el.get("src") or el.get("audioUrl") or el.get("content") or ""
    src = _resolve_asset_url(src, project_id, assets_dir, base_url)
    title = _esc(el.get("title", "Áudio"))
    return (
        f'<div class="sp-audio sp-interactive" data-interactive="audio" data-required="true" '
        f'data-interactive-id="audio-{idx}">'
        f'<div class="sp-audio-label">🎧 {title}</div>'
        f'<audio controls preload="metadata" src="{_esc(src)}" '
        f'onplay="window.SP&&SP.markPlayed(this.closest(\'.sp-interactive\'))" style="width:100%"></audio>'
        f'<div class="sp-audio-hint">▶ Reproduza para liberar a próxima seção</div>'
        f'</div>'
    )


def _render_slide_narration(slide: dict, slide_idx: int, project_id: str, assets_dir: str, base_url: str) -> str:
    """Render slide-level narration audio (uploaded via TTS / ElevenLabs).

    Reads `slide.audio[]` (populated by /projects/{pid}/slides/{sid}/audio
    upload — the same path used by the Editor's ElevenLabs TTS dialog and
    the Agent's narration pipeline). Renders ONE compact player per
    narration entry. The narration auto-plays when the section becomes
    active (handled in JS) and is NON-BLOCKING (does not require play to
    unlock next section), since narration is supportive content.
    """
    audios = slide.get("audio") or []
    if not isinstance(audios, list) or not audios:
        return ""
    # Filter to narration only (skip sfx / background-music for now — those
    # would have type="sfx" or "background")
    narrations = [a for a in audios if isinstance(a, dict)
                  and (a.get("type", "narration") == "narration")
                  and (a.get("src") or a.get("audioUrl") or a.get("content"))]
    if not narrations:
        return ""
    # Build narration block — one <audio> per entry, with a minimal player UI.
    parts: List[str] = []
    parts.append(
        f'<div class="sp-narration" data-narration-section="{slide_idx}" '
        f'data-testid="sp-narration-{slide_idx}">'
    )
    for n_idx, n in enumerate(narrations):
        src_raw = n.get("src") or n.get("audioUrl") or n.get("content") or ""
        src = _resolve_asset_url(src_raw, project_id, assets_dir, base_url)
        try:
            volume = float(n.get("volume", 1.0) or 1.0)
        except (TypeError, ValueError):
            volume = 1.0
        volume = max(0.0, min(1.0, volume))
        parts.append(
            f'<audio class="sp-narration-audio" preload="metadata" '
            f'src="{_esc(src)}" data-volume="{volume}" '
            f'data-narration-id="narr-{slide_idx}-{n_idx}" '
            f'data-testid="sp-narration-audio-{slide_idx}-{n_idx}"></audio>'
        )
    # Compact controls: play/pause + mute (per section). Global mute lives in the
    # top progress bar (rendered by _BUILD_PAGE).
    parts.append(
        f'<div class="sp-narration-controls" role="group" aria-label="Controles de narração">'
        f'<button type="button" class="sp-narration-btn" data-narration-action="toggle" '
        f'data-testid="sp-narration-toggle-{slide_idx}" aria-label="Reproduzir/pausar narração">'
        f'<span class="sp-narration-icon-play">▶</span>'
        f'<span class="sp-narration-icon-pause">⏸</span>'
        f'</button>'
        f'<button type="button" class="sp-narration-btn" data-narration-action="restart" '
        f'data-testid="sp-narration-restart-{slide_idx}" aria-label="Reiniciar narração">↻</button>'
        f'<span class="sp-narration-label">🎧 Narração</span>'
        f'</div>'
        f'</div>'
    )
    return "".join(parts)


def _is_heygen_avatar_url(url: str) -> bool:
    """HeyGen avatar videos têm URL contendo 'heygen' (heygen.ai, resourceN.heygen.ai etc.)
    e são entregues como WebM com canal alpha (fundo transparente).
    Quando detectamos esse padrão, renderizamos sem o card amarelo .sp-interactive
    e sem `background:#000` no <video>, para que o avatar se misture com o background
    da slide."""
    if not url:
        return False
    return "heygen" in url.lower()


def _render_video_element_inner(el: dict, project_id: str, assets_dir: str, base_url: str, idx: int) -> str:
    embed_url = (el.get("embedUrl") or "").strip()
    if embed_url:
        # Bunny and other hosted players must remain iframes. In particular,
        # Bunny's token/expires query pair is security-sensitive and must be
        # preserved exactly rather than converted to a <video> source.
        return (
            f'<div class="sp-video sp-interactive" data-interactive="video" data-required="true" '
            f'data-interactive-id="video-{idx}">'
            f'<iframe src="{_esc(embed_url)}" title="Vídeo" loading="lazy" '
            f'allow="accelerometer; gyroscope; autoplay; encrypted-media; picture-in-picture; fullscreen" '
            f'allowfullscreen referrerpolicy="strict-origin-when-cross-origin" '
            f'style="width:100%;height:min(68vh,540px);border:0;display:block" '
            f'onload="window.SP&&SP.markPlayed(this.closest(\'.sp-interactive\'))"></iframe>'
            f'<div class="sp-video-hint">▶ Reproduza o vídeo para continuar</div>'
            f'</div>'
        )

    src = el.get("src") or el.get("videoUrl") or el.get("content") or ""
    src = _resolve_asset_url(src, project_id, assets_dir, base_url)
    # Avatar HeyGen detectado via URL → fundo transparente, sem card amarelo
    if _is_heygen_avatar_url(src):
        return (
            f'<div class="sp-avatar-wrap" data-interactive="video" data-required="true" '
            f'data-interactive-id="video-{idx}" '
            f'style="display:flex;flex-direction:column;align-items:center;gap:8px;background:transparent;border:0;padding:0;max-width:480px;margin:0 auto">'
            f'<video controls preload="metadata" src="{_esc(src)}" '
            f'onplay="window.SP&&SP.markPlayed(this.closest(\'.sp-avatar-wrap\'))" '
            f'style="width:100%;max-width:480px;max-height:540px;background:transparent;border:0;border-radius:8px;display:block" '
            f'playsinline></video>'
            f'<div class="sp-avatar-hint" style="font-size:11px;color:inherit;opacity:.7;font-style:italic">▶ Avatar — reproduza para liberar próxima seção</div>'
            f'</div>'
        )
    poster = el.get("poster", "")
    if poster:
        poster = _resolve_asset_url(poster, project_id, assets_dir, base_url)
    poster_attr = f' poster="{_esc(poster)}"' if poster else ""
    return (
        f'<div class="sp-video sp-interactive" data-interactive="video" data-required="true" '
        f'data-interactive-id="video-{idx}">'
        f'<video controls preload="metadata" src="{_esc(src)}"{poster_attr} '
        f'onplay="window.SP&&SP.markPlayed(this.closest(\'.sp-interactive\'))"></video>'
        f'<div class="sp-video-hint">▶ Assista para liberar a próxima seção</div>'
        f'</div>'
    )


def _render_avatar_element_inner(el: dict, project_id: str, assets_dir: str, base_url: str, idx: int) -> str:
    """Avatar = video player com fundo TRANSPARENTE (avatares HeyGen .webm têm alpha
    channel; ao remover bg do container, o avatar se mistura com o cenário/slide background.
    Sem yellow border do .sp-interactive — apenas tracking 'video required' sutil."""
    video_url = el.get("videoUrl") or el.get("avatarVideoUrl") or ""
    image_url = el.get("avatarImage") or el.get("imageUrl") or el.get("src") or ""
    if video_url:
        video_url = _resolve_asset_url(video_url, project_id, assets_dir, base_url)
        return (
            f'<div class="sp-avatar-wrap" data-interactive="video" data-required="true" '
            f'data-interactive-id="avatar-{idx}" '
            f'style="display:flex;flex-direction:column;align-items:center;gap:8px;background:transparent;border:0;padding:0;max-width:480px;margin:0 auto">'
            f'<video controls preload="metadata" src="{_esc(video_url)}" '
            f'onplay="window.SP&&SP.markPlayed(this.closest(\'.sp-avatar-wrap\'))" '
            f'style="width:100%;max-width:480px;max-height:540px;background:transparent;border:0;border-radius:8px;display:block" '
            f'playsinline></video>'
            f'<div class="sp-avatar-hint" style="font-size:11px;color:inherit;opacity:.7;font-style:italic">▶ Avatar — reproduza para liberar próxima seção</div>'
            f'</div>'
        )
    if image_url:
        image_url = _resolve_asset_url(image_url, project_id, assets_dir, base_url)
        return (
            f'<figure class="sp-avatar-img" style="margin:0;display:flex;justify-content:center;background:transparent">'
            f'<img src="{_esc(image_url)}" alt="Avatar" loading="lazy" '
            f'style="max-width:320px;max-height:480px;height:auto;background:transparent;display:block" />'
            f'</figure>'
        )
    return ''


def _smart_avatar_position(scene_image_path: str) -> Optional[Dict[str, float]]:
    """Analyze the bottom third of a scene image and pick the quadrant with
    the DARKEST pixels (most likely to be floor/desk/shadow area where the
    avatar can "sit" naturally without occluding important subjects).

    Returns percentage-based placement {left, top, width, height} or None if
    the analysis fails (PIL unavailable, image can't be opened, etc.).

    Heuristic:
    - Sample the bottom 40% of the image.
    - Split into 3 columns (left/center/right) and compute mean brightness.
    - Pick the darkest column → avatar goes there.
    - Avatar size is 32% of image width × 55% of image height (balanced
      visual weight — not too big, not tiny).
    """
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        with Image.open(scene_image_path) as img:
            # Convert to grayscale for brightness analysis (faster, same result)
            gray = img.convert("L")
            w, h = gray.size
            if w == 0 or h == 0:
                return None
            # Sample only the bottom 40% (ground / lower torso area)
            top_y = int(h * 0.60)
            band = gray.crop((0, top_y, w, h))
            bw, bh = band.size
            col_w = bw // 3
            # Compute mean brightness of each column
            means = []
            for col in range(3):
                left = col * col_w
                right = left + col_w if col < 2 else bw
                region = band.crop((left, 0, right, bh))
                # PIL histogram gives a list of 256 counts
                total, count = 0, 0
                for i, c in enumerate(region.histogram()):
                    total += i * c
                    count += c
                mean = total / count if count > 0 else 128
                means.append((mean, col))
            # Darkest column wins (lower mean = darker = more likely "ground")
            _, chosen_col = min(means, key=lambda t: t[0])
            col_left_pct = (chosen_col * col_w) / bw * 100.0
            col_width_pct = (col_w / bw) * 100.0
            # Avatar occupies ~32% × 55% centered within the chosen column's
            # horizontal range, anchored to the bottom of the image.
            avatar_w_pct = 32.0
            avatar_h_pct = 55.0
            # Center the avatar horizontally within its column
            left_pct = col_left_pct + (col_width_pct - avatar_w_pct) / 2.0
            left_pct = max(0.0, min(100.0 - avatar_w_pct, left_pct))
            # Anchor to bottom
            top_pct = max(0.0, 100.0 - avatar_h_pct)
            return {
                "left": round(left_pct, 2),
                "top": round(top_pct, 2),
                "width": avatar_w_pct,
                "height": avatar_h_pct,
                "column": chosen_col,  # 0=left, 1=center, 2=right (for debug)
            }
    except Exception:
        return None


def _is_heygen_or_transparent_avatar(el: dict) -> bool:
    """Returns True if `el` is a HeyGen avatar (transparent .webm) — the only
    case where we should overlay it on the slide's scene image."""
    etype = (el.get("type") or "").lower()
    if etype not in ("video", "avatar"):
        return False
    src = (el.get("src") or el.get("videoUrl")
           or el.get("avatarVideoUrl") or el.get("content") or "")
    return _is_heygen_avatar_url(src)


def _looks_like_scene_image(el: dict, slide_w: int) -> bool:
    """Heuristic: an image element is a "scene/background image" when it
    occupies most of the slide width (>=55%). The Editor positions the
    cenário-fundo as a large image, while logos/icons stay small (<40%)."""
    if (el.get("type") or "").lower() != "image":
        return False
    try:
        w = float(el.get("width") or 0)
    except (TypeError, ValueError):
        return False
    if slide_w <= 0:
        return False
    return (w / slide_w) >= 0.55


def _find_avatar_scene_pair(elements: List[dict], slide_w: int) -> Optional[Dict[str, Any]]:
    """Locate the HeyGen avatar + scene-image pair on the same slide. Returns
    a dict {avatar_idx, scene_idx, avatar_el, scene_el} or None.

    Picks the FIRST avatar and the LARGEST scene image (in case the slide
    has multiple images — pickin one stops accidental overlay onto a logo)."""
    avatar_idx = None
    avatar_el = None
    for i, el in enumerate(elements):
        if _is_heygen_or_transparent_avatar(el):
            avatar_idx = i
            avatar_el = el
            break
    if avatar_idx is None:
        return None
    scene_idx = None
    scene_el = None
    best_w = 0.0
    for i, el in enumerate(elements):
        if i == avatar_idx:
            continue
        if not _looks_like_scene_image(el, slide_w):
            continue
        try:
            w = float(el.get("width") or 0)
        except (TypeError, ValueError):
            w = 0
        if w > best_w:
            best_w = w
            scene_idx = i
            scene_el = el
    if scene_idx is None:
        return None
    return {"avatar_idx": avatar_idx, "scene_idx": scene_idx,
            "avatar_el": avatar_el, "scene_el": scene_el}


def _render_avatar_stage(scene_el: dict, avatar_el: dict, project_id: str,
                          assets_dir: str, base_url: str, slide_idx: int) -> str:
    """Compose a single block where the avatar (transparent video) is
    absolutely positioned over the scene image. The avatar's editor x/y/width
    are translated to percentages of the scene image, so the layout the user
    set in the Editor is honored.

    Falls back to centered-bottom positioning when the avatar element has no
    coordinates (e.g. legacy slides)."""
    scene_src = scene_el.get("src") or scene_el.get("content") or ""
    scene_src = _resolve_asset_url(scene_src, project_id, assets_dir, base_url)
    avatar_src = (avatar_el.get("src") or avatar_el.get("videoUrl")
                  or avatar_el.get("avatarVideoUrl") or "")
    avatar_src = _resolve_asset_url(avatar_src, project_id, assets_dir, base_url)
    if not scene_src or not avatar_src:
        return ""

    # Compute overlay positioning as percentages relative to the scene image's
    # editor coordinates. Editor canvas defaults to slide.width / slide.height.
    try:
        sx = float(scene_el.get("x") or 0)
        sy = float(scene_el.get("y") or 0)
        sw = float(scene_el.get("width") or 0)
        sh = float(scene_el.get("height") or 0)
        ax = float(avatar_el.get("x") or 0)
        ay = float(avatar_el.get("y") or 0)
        aw = float(avatar_el.get("width") or 0)
        ah = float(avatar_el.get("height") or 0)
    except (TypeError, ValueError):
        sx = sy = sw = sh = ax = ay = aw = ah = 0

    if sw > 0 and sh > 0 and aw > 0 and ah > 0:
        left_pct = max(0.0, min(100.0, ((ax - sx) / sw) * 100.0))
        top_pct = max(0.0, min(100.0, ((ay - sy) / sh) * 100.0))
        width_pct = max(5.0, min(100.0, (aw / sw) * 100.0))
        height_pct = max(5.0, min(100.0, (ah / sh) * 100.0))
        overlay_style = (
            f"position:absolute;left:{left_pct:.2f}%;top:{top_pct:.2f}%;"
            f"width:{width_pct:.2f}%;height:{height_pct:.2f}%;"
            f"display:flex;align-items:center;justify-content:center;"
            f"background:transparent"
        )
    else:
        # Fallback: bottom-center, ~40% width, intrinsic height
        overlay_style = (
            "position:absolute;left:50%;bottom:0;transform:translateX(-50%);"
            "width:40%;display:flex;align-items:flex-end;justify-content:center;"
            "background:transparent"
        )

    alt = _esc(scene_el.get("alt") or "Cenário")
    return (
        f'<div class="sp-avatar-stage" data-testid="sp-avatar-stage-{slide_idx}" '
        f'style="position:relative;width:100%;max-width:1024px;margin:0 auto;'
        f'aspect-ratio:{int(sw) if sw > 0 else 16}/{int(sh) if sh > 0 else 9};'
        f'border-radius:12px;overflow:hidden;box-shadow:0 8px 28px rgba(0,0,0,.22);background:#000">'
        f'<img src="{_esc(scene_src)}" alt="{alt}" loading="lazy" '
        f'style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;display:block"/>'
        f'<div class="sp-avatar-overlay sp-avatar-wrap" data-interactive="video" data-required="true" '
        f'data-interactive-id="avatar-stage-{slide_idx}" style="{overlay_style}">'
        f'<video controls preload="metadata" src="{_esc(avatar_src)}" '
        f'onplay="window.SP&&SP.markPlayed(this.closest(\'.sp-avatar-wrap\'))" '
        f'playsinline '
        f'style="width:100%;height:100%;object-fit:contain;background:transparent;border:0;display:block"></video>'
        f'</div>'
        f'<div class="sp-avatar-stage-hint">▶ Avatar — reproduza para liberar próxima seção</div>'
        f'</div>'
    )


def _find_avatar_for_bg_scene(elements: List[dict]) -> Optional[Dict[str, Any]]:
    """Find a HeyGen avatar element on a slide whose scene comes from
    `slide.backgroundImage` (PPT-imported or aspect-locked slides). Returns
    {avatar_idx, avatar_el} or None.
    """
    for i, el in enumerate(elements):
        if _is_heygen_or_transparent_avatar(el):
            return {"avatar_idx": i, "avatar_el": el}
    return None


def _render_avatar_overlay_for_bg(avatar_el: dict, slide: dict, project_id: str,
                                    assets_dir: str, base_url: str, slide_idx: int) -> str:
    """Render JUST the avatar as an absolute overlay positioned relative to
    the slide's frame (slide.width × slide.height). Designed to be appended
    INSIDE the section-inner card (which already has the slide bg-image and
    aspect-ratio locked) — the avatar floats over the bg.

    Smart positioning kicks in when EITHER:
      1. `slide.smartAvatar` is True (explicit opt-in from the Editor), OR
      2. The avatar has no meaningful editor coordinates (all zero / missing)

    The smart positioner analyzes the scene image's bottom third to find the
    darkest column (likely a floor/desk area) and places the avatar there.
    """
    avatar_src = (avatar_el.get("src") or avatar_el.get("videoUrl")
                  or avatar_el.get("avatarVideoUrl") or avatar_el.get("content") or "")
    avatar_src = _resolve_asset_url(avatar_src, project_id, assets_dir, base_url)
    if not avatar_src:
        return ""
    try:
        slide_w = float(slide.get("width") or 0)
        slide_h = float(slide.get("height") or 0)
        ax = float(avatar_el.get("x") or 0)
        ay = float(avatar_el.get("y") or 0)
        aw = float(avatar_el.get("width") or 0)
        ah = float(avatar_el.get("height") or 0)
    except (TypeError, ValueError):
        slide_w = slide_h = ax = ay = aw = ah = 0

    smart_requested = bool(slide.get("smartAvatar"))
    has_editor_coords = (slide_w > 0 and slide_h > 0 and aw > 0 and ah > 0
                         and not (ax == 0 and ay == 0))
    use_smart = smart_requested or not has_editor_coords
    smart_debug_attr = ""
    overlay_style = ""

    if use_smart:
        # Try smart positioning — analyze the scene image
        bg_raw = slide.get("backgroundImage") or ""
        scene_fs_path = None
        if bg_raw:
            # Convert "/api/projects/{id}/assets/{file}" → actual disk path
            m = re.search(r"/assets/([^?#]+)$", bg_raw)
            if m:
                candidate = Path(assets_dir) / m.group(1)
                if candidate.exists():
                    scene_fs_path = str(candidate)
        smart = _smart_avatar_position(scene_fs_path) if scene_fs_path else None
        if smart:
            overlay_style = (
                f"position:absolute;left:{smart['left']:.2f}%;top:{smart['top']:.2f}%;"
                f"width:{smart['width']:.2f}%;height:{smart['height']:.2f}%;"
                f"display:flex;align-items:center;justify-content:center;background:transparent;z-index:4"
            )
            smart_debug_attr = f' data-smart-column="{smart["column"]}"'

    if not overlay_style:
        if slide_w > 0 and slide_h > 0 and aw > 0 and ah > 0:
            left_pct = max(0.0, min(100.0, (ax / slide_w) * 100.0))
            top_pct = max(0.0, min(100.0, (ay / slide_h) * 100.0))
            width_pct = max(5.0, min(100.0, (aw / slide_w) * 100.0))
            height_pct = max(5.0, min(100.0, (ah / slide_h) * 100.0))
            overlay_style = (
                f"position:absolute;left:{left_pct:.2f}%;top:{top_pct:.2f}%;"
                f"width:{width_pct:.2f}%;height:{height_pct:.2f}%;"
                f"display:flex;align-items:center;justify-content:center;background:transparent;z-index:4"
            )
        else:
            overlay_style = (
                "position:absolute;left:50%;bottom:0;transform:translateX(-50%);"
                "width:38%;height:75%;display:flex;align-items:flex-end;justify-content:center;"
                "background:transparent;z-index:4"
            )

    return (
        f'<div class="sp-avatar-overlay sp-avatar-wrap" data-interactive="video" data-required="true" '
        f'data-interactive-id="avatar-bg-{slide_idx}"{smart_debug_attr} '
        f'data-testid="sp-avatar-overlay-{slide_idx}" style="{overlay_style}">'
        f'<video controls preload="metadata" src="{_esc(avatar_src)}" '
        f'onplay="window.SP&&SP.markPlayed(this.closest(\'.sp-avatar-wrap\'))" '
        f'playsinline '
        f'style="width:100%;height:100%;object-fit:contain;background:transparent;border:0;display:block"></video>'
        f'</div>'
    )


def _render_slide_sfx(slide: dict, slide_idx: int, project_id: str,
                       assets_dir: str, base_url: str) -> str:
    """Render slide-level SFX (sound effects) as hidden <audio> tags that
    auto-play ONCE when the section becomes active. `slide.audio[]` entries
    with `type="sfx"` are treated as fire-and-forget one-shots (no UI, no
    controls, no gating of progression).
    """
    audios = slide.get("audio") or []
    if not isinstance(audios, list) or not audios:
        return ""
    sfx_entries = [a for a in audios if isinstance(a, dict)
                   and a.get("type") == "sfx"
                   and (a.get("src") or a.get("audioUrl") or a.get("content"))]
    if not sfx_entries:
        return ""
    parts: List[str] = []
    parts.append(
        f'<div class="sp-sfx" data-sfx-section="{slide_idx}" '
        f'data-testid="sp-sfx-{slide_idx}" aria-hidden="true" style="display:none">'
    )
    for s_i, s in enumerate(sfx_entries):
        src_raw = s.get("src") or s.get("audioUrl") or s.get("content") or ""
        src = _resolve_asset_url(src_raw, project_id, assets_dir, base_url)
        try:
            volume = float(s.get("volume", 0.6) or 0.6)
        except (TypeError, ValueError):
            volume = 0.6
        volume = max(0.0, min(1.0, volume))
        parts.append(
            f'<audio class="sp-sfx-audio" preload="auto" '
            f'src="{_esc(src)}" data-volume="{volume}" '
            f'data-testid="sp-sfx-audio-{slide_idx}-{s_i}"></audio>'
        )
    parts.append("</div>")
    return "".join(parts)


def _find_background_music(course: dict, project_id: str, assets_dir: str, base_url: str) -> Optional[Dict[str, Any]]:
    """Look for a course-level background music track. The FIRST `type="background"`
    audio found across all slides becomes the course's ambient loop. Users typically
    set this on slide 0 (the "course intro").
    """
    slides = (course or {}).get("slides") or []
    for s in slides:
        audios = s.get("audio") or []
        for a in audios if isinstance(audios, list) else []:
            if not isinstance(a, dict):
                continue
            if a.get("type") != "background":
                continue
            src_raw = a.get("src") or a.get("audioUrl") or a.get("content")
            if not src_raw:
                continue
            try:
                volume = float(a.get("volume", 0.2) or 0.2)
            except (TypeError, ValueError):
                volume = 0.2
            volume = max(0.0, min(1.0, volume))
            return {
                "src": _resolve_asset_url(src_raw, project_id, assets_dir, base_url),
                "volume": volume,
            }
    return None


def _looks_like_header_bar(html: str) -> bool:
    """Heuristic: returns True if the HTML content is structurally a "thin header
    bar" (gradient or solid background, short text, single flex row) regardless
    of the author-set height.

    We use this to override the authored height for elements where the CONTENT
    is a header even though the author oversized the element (e.g. h=700) to
    cover the full slide canvas in the editor. In Single Page, that would
    render a giant near-empty colored block.

    Heuristic checks (must satisfy all):
      1. Plain text length < 200 chars (after stripping tags) — header bars are short
      2. Has flex layout with `align-items:center` (typical header pattern)
      3. NO hierarchical content tags: h1-h6, p, ul, ol, li, table
    """
    if not html:
        return False
    text = re.sub(r"<[^>]+>", "", html).strip()
    if len(text) > 200:
        return False
    if not re.search(r"align-items\s*:\s*center", html, re.IGNORECASE):
        return False
    if re.search(r"<\s*(h[1-6]|ul|ol|li|p|table)\b", html, re.IGNORECASE):
        return False
    return True


def _inject_fixed_game_stage_fit(raw: str) -> str:
    """Fit generated 960x540 games without scanning hidden game screens.

    The generic legacy scanner measures every hidden/transformed actor and can
    incorrectly shrink a game inside an already large iframe. Generated games
    have a known 960x540 stage, so use those dimensions deterministically.
    """
    if not raw or "__scormify_game_fit_v7" in raw:
        return raw
    looks_like_game = (
        "QuestionEngine" in raw
        and bool(re.search(r'class=["\'][^"\']*\b(?:game|app)\b', raw, re.IGNORECASE))
        and bool(re.search(r'\b(?:hud|chips|xp|coins|lives|combo)\b', raw, re.IGNORECASE))
    )
    if not looks_like_game:
        return raw
    snippet = r'''<style id="__scormify_game_fit_v7">
html,body{margin:0!important;padding:0!important;width:100%!important;height:100%!important;overflow:hidden!important}
#__stage{width:960px!important;height:540px!important;min-width:960px!important;min-height:540px!important;max-width:none!important;max-height:none!important;transform-origin:0 0!important}
</style><script>(function(){function gameFit(){var st=document.getElementById('__stage')||document.querySelector('main.app,main.game,.app,.game');if(!st)return;var p=4;
var s=Math.max(.1,Math.min((window.innerWidth-p*2)/960,(window.innerHeight-p*2)/540));
var x=(window.innerWidth-960*s)/2,y=(window.innerHeight-540*s)/2;
st.style.setProperty('width','960px','important');st.style.setProperty('height','540px','important');
st.style.setProperty('transform-origin','0 0','important');
st.style.setProperty('transform','translate('+x+'px,'+y+'px) scale('+s+')','important');}
window.addEventListener('resize',gameFit);[0,80,360,1100,1900].forEach(function(ms){setTimeout(gameFit,ms)});})();</script>'''
    idx = raw.lower().rfind("</body>")
    return raw[:idx] + snippet + raw[idx:] if idx >= 0 else raw + snippet


def _render_html_element_inner(el: dict, project_id: str, assets_dir: str, base_url: str,
                                 slide_idx: int, el_idx: int) -> str:
    raw = el.get("htmlContent") or el.get("content") or ""
    # Upgrade legacy interactive slides whose fit script prohibited upscaling.
    # This keeps existing games readable in the modern wide player without
    # forcing administrators to regenerate the course.
    if "__scormify_fit_v3" in raw:
        raw = raw.replace(
            "(innerHeight-pad*2)/ch,1);s=Math.max(.1,s);",
            "(innerHeight-pad*2)/ch,1.35);s=Math.max(.1,s);",
        )
    raw = _inject_fixed_game_stage_fit(raw)
    raw = _inline_assets_in_html(raw, project_id, assets_dir, base_url)
    # Element-level text-shadow — captured here so each branch below (iframe
    # / inline interactive / direct-inline) can apply it in the correct scope.
    shadow_value = ((el.get("style") or {}).get("textShadow") or "").strip()
    if shadow_value == "none":
        shadow_value = ""
    has_global_styles = bool(re.search(r"<\s*(style|script|body|html|head)\b", raw, re.IGNORECASE))
    # Respect the element's authored height when available — keeps thin headers
    # (e.g. 60px gradient bars) from ballooning to 540px in Single Page export.
    # Falls back to 540px when height is missing/zero/too small to be meaningful.
    raw_h = el.get("height")
    try:
        h = float(raw_h) if raw_h is not None else 0
    except (TypeError, ValueError):
        h = 0
    # Override: structurally-detected header bars get capped at 60px regardless
    # of authored height (handles authors who sized header HTML at h=700 to
    # "fill the slide" — which renders as a giant near-empty block in Single Page).
    if _looks_like_header_bar(raw):
        h = 60
    # Clamp to sensible bounds: 60px minimum (visible), 720px maximum (avoids giant scrolls)
    if h <= 0:
        iframe_height_css = "min-height:540px"
    elif h < 60:
        # Author's height is tiny (header bar) — honor it but ensure at least 60px so it remains clickable/visible
        iframe_height_css = f"height:{int(max(h, 60))}px"
    else:
        iframe_height_css = f"height:{int(min(h, 720))}px"
    if has_global_styles:
        # Reset body margin + hide overflow so the iframe doesn't show scrollbars
        # when the authored content fills exactly the iframe height (e.g. 60px header bar).
        # The default body margin:8px would push content past the iframe edges and
        # force a vertical scrollbar that bleeds into a horizontal one too.
        reset_css = (
            '<style>'
            "@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Lato:wght@300;400;700&family=Merriweather:wght@300;400;700&family=Montserrat:wght@300;400;500;600;700&family=Nunito:wght@300;400;600;700&family=Oswald:wght@300;400;500;600;700&family=Playfair+Display:wght@400;500;600;700&family=Poppins:wght@300;400;500;600;700&family=Raleway:wght@300;400;500;600;700&family=Outfit:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&family=Manrope:wght@400;600;700;800&family=Sora:wght@400;600;700&family=Fraunces:wght@400;600;700&family=Source+Serif+4:wght@400;600&family=IBM+Plex+Sans:wght@400;600&family=Archivo:wght@400;600;700&display=swap');"
            'html,body{margin:0 !important;padding:0 !important;'
            'height:100%;overflow:hidden;box-sizing:border-box}'
            '*{box-sizing:border-box}</style>'
        )
        # For thin headers (< 100px) authors often use `margin-left:auto` to push text
        # to the right edge of the slide. In Single Page the iframe is narrower than
        # the original slide canvas, so right-aligned text gets clipped at the edge.
        # Force everything to flex-start / left-align to keep the full text visible.
        if 0 < h < 100:
            reset_css += (
                '<style>'
                'body>div,body{justify-content:flex-start !important;text-align:left !important}'
                '[style*="margin-left:auto"],[style*="margin-left: auto"]{margin-left:0 !important}'
                'span,div,p{white-space:nowrap;overflow:visible}'
                '</style>'
            )
        # Iframe scope — safe to use body,body * because it's self-contained.
        if shadow_value:
            reset_css += (
                '<style>body,body *{text-shadow:' + shadow_value + ' !important;}</style>'
            )
        if "<meta" not in raw.lower() and "charset" not in raw.lower():
            raw_with_meta = '<meta charset="utf-8">\n' + reset_css + raw
        else:
            raw_with_meta = reset_css + raw
        b64 = base64.b64encode(raw_with_meta.encode("utf-8")).decode("ascii")
        return (
            f'<div class="sp-html sp-interactive" data-interactive="html" data-required="true">'
            f'<iframe sandbox="allow-scripts allow-same-origin allow-forms" loading="lazy" '
            f'src="data:text/html;charset=utf-8;base64,{b64}" '
            f'style="width:100%;{iframe_height_css};border:0;border-radius:8px;background:#fff;display:block"></iframe>'
            f'<button type="button" class="sp-btn sp-btn-primary sp-iframe-done" '
            f'onclick="window.SP&&SP.markClicked(this.closest(\'.sp-interactive\'))" '
            f'style="margin-top:12px;width:100%">'
            f'✓ Concluí a interação acima — liberar próxima seção'
            f'</button>'
            f'</div>'
        )
    is_interactive = bool(re.search(r"<button|<details|onclick=", raw, re.IGNORECASE))
    # Inline branches (no iframe) — apply shadow as an inline style on the
    # wrapper div. This scopes the effect to just this HTML block, avoiding
    # any leak to sibling elements in the parent single-page document.
    inline_style = f' style="text-shadow:{shadow_value};"' if shadow_value else ''
    if is_interactive:
        return (
            f'<div class="sp-html sp-interactive" data-interactive="html" data-required="true" '
            f'onclick="window.SP&&SP.markClicked(this)"{inline_style}>'
            f'{raw}'
            f'<div class="sp-html-hint">👆 Clique aqui para liberar a próxima seção</div>'
            f'</div>'
        )
    return f'<div class="sp-html"{inline_style}>{raw}</div>'


def _render_quiz_element_inner(el: dict, slide_idx: int, el_idx: int, questions_lookup: Dict[str, dict]) -> str:
    cfg = el.get("quizConfig") or {}
    qids = cfg.get("questionIds") or []
    title = _esc(cfg.get("title", "Quiz"))
    questions = []
    for qid in qids:
        q = questions_lookup.get(qid)
        if not q:
            continue
        alts = q.get("alternatives") or q.get("options") or []
        normalized_options = []
        for a in alts:
            if isinstance(a, str):
                normalized_options.append({"text": a, "correct": False})
            elif isinstance(a, dict):
                normalized_options.append({
                    "text": a.get("text") or a.get("label") or a.get("answer") or "",
                    "correct": bool(a.get("isCorrect") or a.get("correct") or a.get("right")),
                })
        questions.append({
            "id": q.get("id"),
            "text": q.get("text") or q.get("question") or "",
            "explanation": q.get("explanation") or "",
            "options": normalized_options,
        })
    qjson = json.dumps(questions, ensure_ascii=False).replace("</", "<\\/")
    qjson_attr = html.escape(qjson, quote=True)
    is_transparent = bool(cfg.get("transparentBackground"))
    quiz_classes = "sp-quiz sp-quiz-autostart sp-interactive"
    if is_transparent:
        quiz_classes += " sp-quiz-transparent"
    return (
        f'<div class="{quiz_classes}" data-interactive="quiz" data-required="true" data-autostart="true" '
        f'data-interactive-id="quiz-{slide_idx}-{el_idx}" '
        f'data-questions="{qjson_attr}">'
        f'<div class="sp-quiz-icon">📝</div>'
        f'<h3 class="sp-quiz-title">{title}</h3>'
        f'<p class="sp-quiz-meta">{len(questions)} questões</p>'
        f'<button type="button" class="sp-btn sp-btn-primary" '
        f'onclick="window.SP&&SP.startQuiz(this.closest(\'.sp-quiz\'))">Iniciar Quiz</button>'
        f'<div class="sp-quiz-body" hidden></div>'
        f'</div>'
    )


def _render_scenario_element_inner(el: dict, slide_idx: int, el_idx: int) -> str:
    sd = el.get("scenarioData") or {}
    title = _esc(sd.get("title", "Cenário interativo"))
    desc = _esc(sd.get("description", ""))
    context = _esc(sd.get("context", ""))
    characters = sd.get("characters", []) or []
    nodes = sd.get("nodes", []) or []

    # Serialize the scenario state for the JS runtime
    scenario_payload = {
        "characters": [
            {"name": c.get("name", ""), "role": c.get("role", "")}
            for c in characters
        ],
        "nodes": [
            {
                "id": n.get("id", ""),
                "title": n.get("title", ""),
                "narrative": n.get("narrative", ""),
                "character_speaking": n.get("character_speaking", ""),
                "is_ending": bool(n.get("is_ending", False)),
                "ending_type": n.get("ending_type"),
                "score": n.get("score"),
                "choices": [
                    {
                        "id": ch.get("id", ""),
                        "text": ch.get("text", ""),
                        "next_node_id": ch.get("next_node_id"),
                        "feedback": ch.get("feedback", ""),
                        "is_optimal": bool(ch.get("is_optimal", False)),
                        "points": ch.get("points", 0),
                    }
                    for ch in (n.get("choices") or [])
                ],
            }
            for n in nodes
        ],
    }
    scenario_json = json.dumps(scenario_payload, ensure_ascii=False).replace("</", "<\\/")
    scenario_attr = html.escape(scenario_json, quote=True)

    chars_html = ""
    if characters:
        chars_html = '<div class="sp-scenario-chars" style="display:flex;flex-wrap:wrap;gap:8px;margin:14px 0;justify-content:center">'
        for ch in characters[:4]:
            ch_name = _esc(ch.get("name", ""))
            ch_role = _esc(ch.get("role", ""))
            chars_html += (
                f'<div style="background:rgba(0,0,0,.25);border-radius:8px;padding:8px 12px;font-size:12px;text-align:center;min-width:120px">'
                f'<div style="font-weight:700">{ch_name}</div>'
                f'<div style="opacity:.85;font-size:11px">{ch_role}</div>'
                f'</div>'
            )
        chars_html += '</div>'

    has_interactive_nodes = len(nodes) > 0
    if has_interactive_nodes:
        # Interactive scenario: button starts the journey through nodes
        cta_button = (
            f'<button type="button" class="sp-btn sp-btn-primary" '
            f'onclick="window.SP&&SP.startScenario(this.closest(\'.sp-scenario\'))">'
            f'▶ Iniciar Cenário Interativo</button>'
        )
    else:
        # Fallback: simple "mark as done" button
        cta_button = (
            f'<button type="button" class="sp-btn sp-btn-primary" '
            f'onclick="window.SP&&SP.markClicked(this.closest(\'.sp-scenario\'))">'
            f'Marcar como concluído ✓</button>'
        )

    return (
        f'<div class="sp-scenario sp-interactive" data-interactive="scenario" data-required="true" '
        f'data-interactive-id="scenario-{slide_idx}-{el_idx}" '
        f'data-scenario="{scenario_attr}">'
        f'<div class="sp-scenario-intro">'
        f'<div class="sp-scenario-icon">🎯</div>'
        f'<h3 class="sp-scenario-title">{title}</h3>'
        f'<p>{desc}</p>'
        + (f'<p style="font-size:13px;opacity:.78;font-style:italic;margin-top:8px"><strong>📋 Contexto:</strong> {context}</p>' if context else '')
        + chars_html +
        f'{cta_button}'
        f'</div>'
        f'<div class="sp-scenario-play" hidden></div>'
        f'</div>'
    )


def _inject_contrast_safety_net(html: str) -> str:
    """Inject a small JavaScript that fixes white-on-white (or any
    low-contrast) text inside interactive simulators.

    Why this is needed: the AI-Agent prompt asks the LLM to produce HTML
    drag-and-drop / quiz / flashcard simulators. The LLM often produces
    cards with `color: white` on a light pastel `background` (or vice
    versa) because it copies typical "dark mode" patterns without
    checking contrast against the actual brand-kit background. End
    result: invisible text on the slide — reported by users.

    The script runs once on DOMContentLoaded, walks every text-bearing
    element, computes the effective background by ascending the tree
    until a non-transparent color is found, and forces a contrasting
    foreground if the WCAG contrast ratio is below 3.0 (the minimum
    for large text per WCAG 2.1 AA). It NEVER touches elements that
    are already legible — designs that were intentionally white-on-dark
    are preserved.

    The injection is safe to apply repeatedly (idempotent — guarded by
    a sentinel `data-sp-contrast-safety` attribute on the html root).
    """
    # Generated games ship with a curated dark palette. Gradient-only
    # surfaces do not expose a useful computed backgroundColor, so the generic
    # heuristic can incorrectly turn their labels black. Preserve the authored
    # game palette; the safety-net remains active for LLM-made simulators.
    if "QuestionEngine" in html and re.search(r'\b(?:game|app)\b', html, re.IGNORECASE):
        return html

    safety_script = """
<script>(function(){
  if(document.documentElement.hasAttribute('data-sp-contrast-safety'))return;
  document.documentElement.setAttribute('data-sp-contrast-safety','1');
  function run(){
    function parseColor(str){
      if(!str)return null;
      var m=str.match(/rgba?\\(([^)]+)\\)/);
      if(!m)return null;
      var p=m[1].split(',').map(function(s){return parseFloat(s.trim());});
      if(p.length<3)return null;
      var a=p.length>=4?p[3]:1;
      return {r:p[0],g:p[1],b:p[2],a:a};
    }
    function lum(c){
      function ch(v){v=v/255;return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4);}
      return 0.2126*ch(c.r)+0.7152*ch(c.g)+0.0722*ch(c.b);
    }
    function contrast(a,b){
      var L1=lum(a),L2=lum(b);
      var l=Math.max(L1,L2),d=Math.min(L1,L2);
      return (l+0.05)/(d+0.05);
    }
    function effectiveBg(el){
      // Walk up the DOM until we find a non-transparent background.
      // Default to white if we reach the root with no opaque ancestor.
      var node=el;
      while(node && node.nodeType===1){
        var cs=window.getComputedStyle(node);
        var bg=parseColor(cs.backgroundColor);
        if(bg && bg.a>0.1) return bg;
        // Some authors use background-image gradients without setting
        // a fallback color — assume a light surface in that case
        // (most brand kits default to light backgrounds).
        if(cs.backgroundImage && cs.backgroundImage!=='none'){
          return {r:240,g:240,b:240,a:1};
        }
        node=node.parentElement;
      }
      return {r:255,g:255,b:255,a:1};
    }
    function hasDirectText(el){
      for(var i=0;i<el.childNodes.length;i++){
        var n=el.childNodes[i];
        if(n.nodeType===3 && n.nodeValue && n.nodeValue.trim()) return true;
      }
      return false;
    }
    // Run twice — once immediately, once after 600ms to catch elements
    // populated by the simulator's own JS (drag-and-drop libraries
    // often inject cards async after init).
    function pass(){
      var els=document.querySelectorAll('body *');
      for(var i=0;i<els.length;i++){
        var el=els[i];
        if(!hasDirectText(el)) continue;
        var cs=window.getComputedStyle(el);
        var fg=parseColor(cs.color);
        if(!fg) continue;
        var bg=effectiveBg(el);
        if(contrast(fg,bg)<3.0){
          // Pick whichever direction maximizes legibility.
          var dark={r:15,g:23,b:42,a:1}, light={r:241,g:245,b:249,a:1};
          var pick=contrast(dark,bg)>contrast(light,bg)?'#0f172a':'#f1f5f9';
          el.style.setProperty('color',pick,'important');
          // Also tighten text-shadow if any white shadow would dim
          // the now-dark text against a light background.
          if(cs.textShadow && cs.textShadow!=='none'){
            el.style.setProperty('text-shadow','none','important');
          }
        }
      }
    }
    pass();
    setTimeout(pass,600);
    setTimeout(pass,2000);
  }
  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded',run);
  } else {
    run();
  }
})();</script>
"""
    # Inject right before </body> so the simulator's own initialization
    # runs first; we then run our post-pass to catch anything left
    # invisible. If no </body> tag is found, append at the end — still
    # gets executed by the iframe loader.
    if "</body>" in html.lower():
        # Case-insensitive replace of the last </body>
        idx = html.lower().rfind("</body>")
        return html[:idx] + safety_script + html[idx:]
    return html + safety_script


def _render_simulator_element_inner(el: dict, project_id: str, assets_dir: str, base_url: str, slide_idx: int, el_idx: int) -> str:
    sim_html = el.get("htmlContent") or el.get("content") or ""
    sim_html = _inline_assets_in_html(sim_html, project_id, assets_dir, base_url)
    # Auto-fit legacy interactive docs missing the __stage wrapper so the
    # 960x540 design centers and scales to the export iframe.
    from services.ai_agent import _wrap_interactive_fullbleed
    sim_html = _wrap_interactive_fullbleed(sim_html)
    if "<meta" not in sim_html.lower() and "charset" not in sim_html.lower():
        sim_html = '<meta charset="utf-8">\n' + sim_html
    # Inject the contrast safety-net so simulators with white-on-white
    # text become legible without requiring the author to regenerate.
    sim_html = _inject_contrast_safety_net(sim_html)
    sim_html_b64 = base64.b64encode(sim_html.encode("utf-8")).decode("ascii") if sim_html else ""
    return (
        f'<div class="sp-simulator sp-interactive" data-interactive="simulator" data-required="true" '
        f'data-interactive-id="simulator-{slide_idx}-{el_idx}">'
        f'<div class="sp-simulator-label">🎮 Simulador interativo</div>'
        f'<iframe sandbox="allow-scripts allow-same-origin allow-forms" loading="lazy" '
        f'src="data:text/html;charset=utf-8;base64,{sim_html_b64}" '
        f'style="width:100%;height:520px;border:0;border-radius:12px;background:#0f172a"></iframe>'
        f'<button type="button" class="sp-btn sp-btn-primary sp-iframe-done" '
        f'onclick="window.SP&&SP.markClicked(this.closest(\'.sp-interactive\'))" '
        f'style="margin-top:12px;width:100%">'
        f'✓ Concluí o simulador — liberar próxima seção'
        f'</button>'
        f'</div>'
    )


# --------------------------------------------------------------------------- main


def generate_single_page_html(
    project_doc: dict,
    assets_dir: str,
    base_url: str = "",
    questions: Optional[List[dict]] = None,
    tutor_config: Optional[dict] = None,
    scorm_mode: bool = False,
    gamification_config: Optional[dict] = None,
) -> str:
    """Generate a complete standalone single-page HTML for the given project.

    When scorm_mode=True, injects SCORM 1.2 runtime hooks (window.SCORM):
      - lesson_location for resume
      - suspend_data for completed interactives + quiz scores
      - cmi.interactions for quiz answer tracking
      - cmi.core.score for the running score
      - lesson_status="completed" + success_status="passed" when all sections
        are unlocked AND all quizzes passed mastery (>=80% by default)

    When gamification_config is provided AND has enabled=true, injects the
    Gamification engine + hooks at quiz/scenario/course completion points
    (badges, feedback modals, final summary).
    """
    project_id = project_doc.get("id", "")
    name = project_doc.get("name", "Curso")
    course = project_doc.get("course", {}) or {}
    slides = course.get("slides", []) or []
    metadata = course.get("metadata", {}) or {}
    course_title = metadata.get("title") or name
    visual_journey = (
        metadata.get("visualCourseMode") == "illustrated_journey"
        or metadata.get("playerTemplate") == "visual_journey"
        or project_doc.get("playerTemplate") == "visual_journey"
    )
    # Branded loader config (title + accent color) derived from the
    # project's brand kit + course metadata.
    from services.loader_config import resolve_loader_config
    _loader_cfg = resolve_loader_config(project_doc)
    loader_title = _loader_cfg["title_html"]
    loader_primary = _loader_cfg["primary"]
    loader_accent = _loader_cfg["accent"]
    # The single-page HTML used legacy hard-coded chrome colors. Resolve and
    # append the same company tokens used by traditional SCORM/HTML instead.
    from services.player_theme import (
        build_single_page_player_theme_css,
        resolve_player_theme,
        resolve_tutor_theme,
    )
    player_theme_css = build_single_page_player_theme_css(
        resolve_player_theme(project_doc)
    )
    # Defensive parity for direct exporter callers and preview routes: Tutor
    # inherits the company identity even when the caller omitted ``theme``.
    if tutor_config and not tutor_config.get("theme"):
        tutor_config = dict(tutor_config)
        tutor_config["theme"] = resolve_tutor_theme(project_doc)
    # Strip leading UUID-like prefix from project name (common in PPT-imported projects)
    course_title = re.sub(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}_", "", course_title, flags=re.IGNORECASE)

    questions_lookup: Dict[str, dict] = {q.get("id"): q for q in (questions or []) if q.get("id")}

    sections_html: List[str] = []
    sections_index: List[Dict[str, Any]] = []

    for s_idx, slide in enumerate(slides):
        slide_title = slide.get("title") or f"Seção {s_idx + 1}"
        elements = slide.get("elements", []) or []
        rendered_elements: List[str] = []
        # Detect timeline: any element with startTime > 0 or endTime > 0
        section_max_end_time = 0.0
        for el_for_timing in elements:
            try:
                st = float(el_for_timing.get("startTime") or 0)
            except (TypeError, ValueError):
                st = 0.0
            try:
                et_raw = el_for_timing.get("endTime")
                et = float(et_raw) if et_raw is not None else 0.0
            except (TypeError, ValueError):
                et = 0.0
            section_max_end_time = max(section_max_end_time, st, et)
        # Detect avatar (HeyGen) + scene-image pair so we can compose them
        # as a SINGLE positioned stage block — otherwise both render as
        # separate stacked blocks and the avatar appears ABOVE the scene
        # instead of overlaid on top of it.
        slide_w_for_pair = int(slide.get("width") or 1920) or 1920
        avatar_pair = _find_avatar_scene_pair(elements, slide_w_for_pair)
        composed_indices = set()
        if avatar_pair:
            composed_indices = {avatar_pair["avatar_idx"], avatar_pair["scene_idx"]}

        # ALSO handle the case where the scene is the slide's `backgroundImage`
        # (PPT-imported aspect-locked slides). The pair-finder above only
        # matches an actual <image> element, but PPT slides have the scene
        # baked into slide.backgroundImage. In that case, find a lone avatar
        # and overlay it on the bg via aspect-locked positioning.
        bg_avatar = None
        if not avatar_pair and slide.get("backgroundImage"):
            bg_avatar = _find_avatar_for_bg_scene(elements)
            if bg_avatar:
                composed_indices.add(bg_avatar["avatar_idx"])

        # When the slide has a backgroundImage (PPT-imported or author-set
        # scene), elements should be rendered at their EDITOR positions
        # (x/y/width/height converted to percentages of slide.width × slide.height)
        # as absolute-positioned overlays inside the section-inner card.
        # This honors the layout the author crafted in the Editor — text
        # boxes, buttons, links all appear exactly where they were placed
        # ON TOP of the scene image. Without this, elements fall into the
        # body strip at the bottom and lose their original positioning.
        use_absolute_positioning = bool(slide.get("backgroundImage"))
        absolute_elements: List[str] = []
        try:
            slide_canvas_w = float(slide.get("width") or 0)
            slide_canvas_h = float(slide.get("height") or 0)
        except (TypeError, ValueError):
            slide_canvas_w = slide_canvas_h = 0

        for e_idx, el in enumerate(elements):
            # Skip elements that will be composed into the avatar-stage block
            if e_idx in composed_indices:
                continue
            try:
                render_el = el
                # Normalize infographics through the stable contextual
                # template. Do not depend only on Visual Journey metadata:
                # older Agent projects frequently saved them as generic HTML.
                slide_kind = str(slide.get("contentType") or slide.get("type") or "").lower()
                # Old Agent projects sometimes persisted every interactive
                # slide as generic ``content``.  The pedagogical title is a
                # stronger signal in that case and prevents Flashcards and
                # Simulators from being migrated into the generic game shell.
                slide_title = str(slide.get("title") or "").strip().lower()
                if re.match(r"^flashcards?\b", slide_title):
                    slide_kind = "flashcard"
                elif re.match(r"^simula(?:dor|cao|ção)\b", slide_title):
                    slide_kind = "simulator"
                elif re.match(r"^(?:jogo|game)\b", slide_title):
                    slide_kind = "game"
                if str(el.get("type") or "").lower() == "html":
                    from services.ai_agent import _build_infographic_fallback_html, _infographic_html_needs_repair
                    infographic_raw = str(el.get("htmlContent") or el.get("content") or "")
                    repair_infographic = (
                        slide_kind == "infographic"
                        or _infographic_html_needs_repair(infographic_raw)
                    )
                else:
                    repair_infographic = False
                if repair_infographic:
                    render_el = dict(el)
                    render_el["htmlContent"] = _build_infographic_fallback_html(slide)
                    render_el["htmlDisplayMode"] = "fit"
                    render_el["width"] = 960
                    render_el["height"] = 540
                # Repair already-created courses where the AI saved the
                # question-game shell under a simulator slide. New courses are
                # protected during generation; this export-time guard makes
                # the correction retroactive without database migration.
                if slide_kind == "simulator" and str(el.get("type") or "").lower() == "html":
                    from services.ai_agent import _build_simulator_fallback_html, _interactive_html_is_functional, _simulator_html_is_actually_a_game
                    simulator_raw = str(el.get("htmlContent") or el.get("content") or "")
                    if _simulator_html_is_actually_a_game(simulator_raw) or not _interactive_html_is_functional(simulator_raw, "simulator"):
                        repair_slide = dict(slide)
                        repair_slide["elements"] = []
                        render_el = dict(el)
                        render_el["htmlContent"] = _build_simulator_fallback_html(repair_slide)
                        render_el["htmlDisplayMode"] = "fit"
                        render_el["width"] = 960
                        render_el["height"] = 540
                # Flashcards are a study/retrieval activity, not a quiz game.
                # Repair generic game HTML retroactively for both HTML and
                # SCORM exports, including projects with lost contentType.
                if slide_kind == "flashcard" and str(el.get("type") or "").lower() == "html":
                    from services.ai_agent import _build_flashcard_fallback_html, _interactive_html_is_functional
                    flashcard_raw = str(el.get("htmlContent") or el.get("content") or "")
                    if not _interactive_html_is_functional(flashcard_raw, "flashcard"):
                        repair_slide = dict(slide)
                        repair_slide["elements"] = []
                        render_el = dict(el)
                        render_el["htmlContent"] = _build_flashcard_fallback_html(repair_slide)
                        render_el["htmlDisplayMode"] = "fit"
                        render_el["width"] = 960
                        render_el["height"] = 540
                # Existing projects may still contain the original generic
                # game shell. Upgrade it during every HTML/SCORM-style single
                # page export, retaining the exact embedded question snapshot.
                # Do not rely on slide.contentType here: older Agent projects
                # often saved game slides as a generic content/HTML slide.
                # The embedded QuestionEngine signature is the authoritative
                # signal for the migration.
                # Some Agent versions persisted a game document in an
                # element typed `simulator` or `scenario`.  Restricting this
                # migration to `html` left those exports on the broken
                # class-based stage (the visible vertical line).  The
                # QuestionEngine signature is a safer discriminator than the
                # element type, so inspect every iframe-capable element.
                if slide_kind not in ("simulator", "flashcard") and str(el.get("type") or "").lower() in ("html", "simulator", "scenario"):
                    from services.ai_agent import _game_html_uses_legacy_single_stage, _repair_legacy_game_html
                    legacy_game_raw = str(el.get("htmlContent") or el.get("content") or "")
                    if _game_html_uses_legacy_single_stage(legacy_game_raw):
                        render_el = dict(el)
                        render_el["type"] = "html"
                        render_el["htmlContent"] = _repair_legacy_game_html(slide, legacy_game_raw)
                        render_el["htmlDisplayMode"] = "fit"
                        render_el["height"] = 540
                html_part = _render_element(render_el, project_id, assets_dir, base_url,
                                              s_idx, e_idx, questions_lookup)
                if not html_part:
                    continue
                # Try absolute positioning for bg-image slides
                if use_absolute_positioning and slide_canvas_w > 0 and slide_canvas_h > 0:
                    try:
                        ex = float(el.get("x") or 0)
                        ey = float(el.get("y") or 0)
                        ew = float(el.get("width") or 0)
                        eh = float(el.get("height") or 0)
                    except (TypeError, ValueError):
                        ex = ey = ew = eh = 0
                    if ew > 0 and eh > 0:
                        left_pct = max(0.0, min(100.0, (ex / slide_canvas_w) * 100.0))
                        top_pct = max(0.0, min(100.0, (ey / slide_canvas_h) * 100.0))
                        width_pct = max(1.0, min(100.0, (ew / slide_canvas_w) * 100.0))
                        height_pct = max(1.0, min(100.0, (eh / slide_canvas_h) * 100.0))
                        wrapped = (
                            f'<div class="sp-bg-element" style="position:absolute;'
                            f'left:{left_pct:.2f}%;top:{top_pct:.2f}%;'
                            f'width:{width_pct:.2f}%;height:{height_pct:.2f}%;'
                            f'z-index:2;overflow:visible">{html_part}</div>'
                        )
                        absolute_elements.append(wrapped)
                        continue
                # Fallback: append to body flow (legacy behavior)
                rendered_elements.append(html_part)
            except Exception:
                continue

        # Inject the composed avatar-over-scene stage. We prepend it so the
        # avatar+scene visual appears as the primary visual focus of the
        # section — text/quiz elements flow naturally below it.
        if avatar_pair:
            stage_html = _render_avatar_stage(
                avatar_pair["scene_el"], avatar_pair["avatar_el"],
                project_id, assets_dir, base_url, s_idx,
            )
            if stage_html:
                rendered_elements.insert(0, stage_html)

        # Append synthetic timeline gate when section has a timeline (>0).
        # This turns the timeline auto-play into a "required interactive" — section
        # only unlocks after the JS runtime fires SP.markClicked on this gate.
        if section_max_end_time > 0:
            rendered_elements.append(
                f'<div class="sp-timeline-gate sp-interactive" '
                f'data-interactive="timeline" data-required="true" '
                f'data-interactive-id="timeline-{s_idx}" '
                f'data-section-duration="{section_max_end_time}">'
                f'<div class="sp-timeline-progress">'
                f'<div class="sp-timeline-progress-bar"></div>'
                f'</div>'
                f'<div class="sp-timeline-hint">⏱ Reproduzindo sequência temporal — aguarde o fim para liberar a próxima seção</div>'
                f'</div>'
            )

        # Render slide-level narration (slide.audio[]) — auto-plays when section
        # becomes active; non-blocking. Appended at the END of section body so
        # it doesn't compete with primary content for vertical real estate.
        narration_html = _render_slide_narration(slide, s_idx, project_id, assets_dir, base_url)
        if narration_html:
            rendered_elements.append(narration_html)
        # Render slide-level SFX (type="sfx") — hidden one-shots triggered on
        # section enter. Non-blocking, no UI.
        sfx_html = _render_slide_sfx(slide, s_idx, project_id, assets_dir, base_url)
        if sfx_html:
            rendered_elements.append(sfx_html)
        locked_attr = 'data-locked="true"' if s_idx > 0 else ''

        # Zoom effect (set by Tutorial Agent importer): when present, the
        # runtime animates a "magnify on hotspot" effect on a dedicated
        # `.sp-zoom-stage` wrapper that holds JUST the background-image and
        # the absolute-positioned overlays (hotspot ring, instruction text).
        # The card title and body strip stay OUTSIDE the stage so they
        # don't scale with the zoom.
        zoom_attrs = ""
        has_zoom = False
        zoom_data = slide.get("zoomEffect")
        if isinstance(zoom_data, dict):
            try:
                zoom_scale = float(zoom_data.get("scale", 2.0))
                if zoom_scale > 1.0:
                    zoom_attrs = (
                        f' data-zoom-scale="{zoom_scale}"'
                        f' data-zoom-fx="{float(zoom_data.get("focusX", 50))}"'
                        f' data-zoom-fy="{float(zoom_data.get("focusY", 50))}"'
                        f' data-zoom-intro="{int(zoom_data.get("intro", 800))}"'
                        f' data-zoom-hold="{int(zoom_data.get("hold", 2400))}"'
                        f' data-zoom-outro="{int(zoom_data.get("outro", 600))}"'
                    )
                    has_zoom = True
            except (TypeError, ValueError):
                zoom_attrs = ""
                has_zoom = False

        bg_color = (slide.get("background") or "").strip()
        bg_image_url = slide.get("backgroundImage") or ""
        if bg_image_url:
            bg_image_url = _resolve_asset_url(bg_image_url, project_id, assets_dir, base_url)
        # Slide canvas dimensions (PPT-imported slides carry the original
        # PowerPoint frame size — typically 1280×720 / 1920×1080). We use
        # this to lock the section card to the slide's aspect ratio so the
        # PPT-imported background renders at full size instead of being
        # squashed into a thin banner.
        try:
            slide_w_for_card = float(slide.get("width") or 0)
            slide_h_for_card = float(slide.get("height") or 0)
        except (TypeError, ValueError):
            slide_w_for_card = slide_h_for_card = 0
        card_styles = []
        section_class = "sp-section"
        if visual_journey:
            section_class += " sp-journey-section"
            # Full-slide HTML games/simulators must never enter a narrative
            # split-grid: that compressed a complete 16:9 app into a narrow
            # right column. Detect both new metadata and legacy full-width
            # authored elements so already-created projects export correctly.
            rich_types = {"game", "simulator", "scenario", "infographic", "timeline", "case_study", "flashcard", "quiz"}
            content_type = str(slide.get("contentType") or "").strip().lower()
            def _is_fullbleed_interactive(candidate: dict) -> bool:
                if str(candidate.get("type") or "").lower() not in ("html", "simulator", "scenario", "quiz"):
                    return False
                if str(candidate.get("htmlDisplayMode") or "").lower() == "fit":
                    return True
                # Legacy rich HTML may not carry htmlDisplayMode. Require an
                # actual document/script signature; width alone is unsafe
                # because normal title/header HTML is also authored at 1680px.
                raw_candidate = str(candidate.get("htmlContent") or candidate.get("content") or "")
                has_app_signature = bool(re.search(r"<(?:html|body|script)\b", raw_candidate, re.IGNORECASE))
                try:
                    candidate_width = float(candidate.get("width") or 0)
                except (TypeError, ValueError):
                    candidate_width = 0.0
                return has_app_signature and candidate_width >= max(1200.0, slide_w_for_card * .72)
            fullbleed_html = any(
                _is_fullbleed_interactive(el) for el in elements
            )
            if content_type in rich_types or fullbleed_html:
                layout = "interactive_stage"
            else:
                layout = str(slide.get("journeyLayout") or "").strip().lower()
                if not layout:
                    layout = {
                        "context": "cinematic_scene", "observe": "guided_observation",
                        "decide": "decision_split", "practice": "workbench",
                        "reflect": "reflection",
                    }.get(str(slide.get("narrativeBeat") or "context").lower(), "cinematic_scene")
                # Cinematic overlay requires a real scene image. Applying it
                # to text-only covers/content created dark empty panels.
                has_scene_image = bool(slide.get("backgroundImage")) or any(
                    str(el.get("type") or "").lower() == "image" and
                    bool(el.get("src") or el.get("imageUrl") or el.get("content"))
                    for el in elements
                )
                if layout == "cinematic_scene" and not has_scene_image:
                    layout = "reflection"
            layout = re.sub(r"[^a-z0-9_-]", "", layout) or "cinematic_scene"
            section_class += f" sp-layout-{layout.replace('_', '-')}"
        if bg_color:
            card_styles.append(f"background-color:{_esc(bg_color)}")
            if _is_dark_color(bg_color):
                card_styles.append("color:#f1f5f9")
                section_class += " sp-dark"
        if bg_image_url:
            # When the slide has a zoom effect, the background-image is moved
            # into a dedicated `.sp-zoom-stage` wrapper that we can scale
            # independently of the card chrome. Otherwise paint the bg
            # directly on the card (legacy behavior, preserves PPT imports).
            # 2026-05-25: honor `backgroundImageFit` per slide. Modo Fiel
            # slides set `"contain"` so the WHOLE PDF page is visible
            # (no cropping of title/sides when aspect ratios differ).
            fit_mode = slide.get("backgroundImageFit")
            if not fit_mode:
                fit_mode = "contain" if slide.get("_pdfFaithful") else "cover"
            if not has_zoom:
                card_styles.append(f"background-image:url({_esc(bg_image_url)})")
                card_styles.append(f"background-size:{fit_mode}")
                card_styles.append("background-position:center")
                card_styles.append("background-repeat:no-repeat")
            section_class += " sp-has-bg-image"
            if has_zoom:
                section_class += " sp-has-zoom"
            # Preserve slide aspect-ratio so PPT-imported slides render full size
            # (mat the section's max-width 1080px → height ~607px for 16:9).
            # Only set when both dims are sane to avoid math errors.
            if slide_w_for_card > 0 and slide_h_for_card > 0:
                # Express as integer ratio (CSS prefers `1280/720` style)
                card_styles.append(f"aspect-ratio:{int(slide_w_for_card)}/{int(slide_h_for_card)}")
                # Ensure a sensible minimum height on small viewports too
                card_styles.append("min-height:520px")
                section_class += " sp-aspect-locked"
        card_style = f' style="{";".join(card_styles)}"' if card_styles else ''

        # Optional darkening/lightening scrim over the background image —
        # set by the Aesthetic Analyzer when text needs more contrast over
        # busy imagery. Format: rgba string OR keyword "dark"/"light".
        # SUPPRESSED when the image came from the Brand Library — the
        # author picked it intentionally and a stale Aesthetic-Analyzer
        # overlay would unexpectedly darken the brand image. Override
        # via `backgroundImageOverlayForce=true` if the user really wants
        # the scrim on top of a brand-library bg.
        bg_overlay = (slide.get("backgroundImageOverlay") or "").strip()
        bg_source = (slide.get("backgroundImageSource") or "").strip()
        bg_overlay_force = bool(slide.get("backgroundImageOverlayForce"))
        overlay_html = ""
        if bg_overlay and bg_image_url and (bg_source != "brand_library" or bg_overlay_force):
            if bg_overlay == "dark":
                overlay_css = "background:linear-gradient(180deg,rgba(0,0,0,0.45),rgba(0,0,0,0.65))"
            elif bg_overlay == "light":
                overlay_css = "background:linear-gradient(180deg,rgba(255,255,255,0.55),rgba(255,255,255,0.75))"
            else:
                # Treat as raw color value (e.g. rgba(0,0,0,0.5))
                overlay_css = f"background:{_esc(bg_overlay)}"
            overlay_html = (
                '<div class="sp-bg-overlay" aria-hidden="true" '
                f'style="position:absolute;inset:0;{overlay_css};pointer-events:none;z-index:0"></div>'
            )

        # Compose avatar overlay INSIDE the section-inner (over the bg-image)
        # — only when slide has bg-image AND a HeyGen avatar that we removed
        # from the regular elements pass above.
        bg_avatar_html = ""
        if bg_avatar:
            bg_avatar_html = _render_avatar_overlay_for_bg(
                bg_avatar["avatar_el"], slide, project_id, assets_dir, base_url, s_idx,
            )

        # Absolute-positioned elements (when slide has bg-image) live as
        # direct children of section-inner so their %-coords map to the
        # whole card area (where the bg-image is). Body elements (audio
        # narration, sfx, fallback non-positioned) stay in the body strip.
        absolute_elements_html = "\n      ".join(absolute_elements) if absolute_elements else ""

        # When the slide has a zoom effect, the bg-image and the absolute
        # overlays (hotspot, instruction text) are wrapped in a single
        # `.sp-zoom-stage` element. The stage is what receives the
        # `transform: scale()` so the title/body strip/avatar overlay don't
        # get distorted along with it.
        if has_zoom and bg_image_url:
            # 2026-05-25: honor `backgroundImageFit` here too.
            zoom_fit = slide.get("backgroundImageFit")
            if not zoom_fit:
                zoom_fit = "contain" if slide.get("_pdfFaithful") else "cover"
            stage_style = (
                f'background-image:url({_esc(bg_image_url)});'
                f'background-size:{zoom_fit};background-position:center;'
                'background-repeat:no-repeat'
            )
            stage_block = (
                f'    <div class="sp-zoom-stage" style="{stage_style}">\n'
                f'      {overlay_html}\n'
                f'      {absolute_elements_html}\n'
                f'    </div>\n'
            )
        else:
            stage_block = (
                f'    {overlay_html}\n'
                f'    {absolute_elements_html}\n'
            )

        module_name = str(slide.get("moduleName") or "Jornada de aprendizagem")
        narrative_beat = str(slide.get("narrativeBeat") or "context")
        journey_meta = (
            f'<div class="sp-journey-meta"><span>{_esc(module_name)}</span>'
            f'<span class="sp-journey-beat">{_esc(narrative_beat)}</span></div>'
            if visual_journey else ""
        )
        section = (
            f'<section class="{section_class}" data-index="{s_idx}" '
            f'data-title="{_esc(slide_title)}" '
            f'{locked_attr}{zoom_attrs}>\n'
            f'  <div class="sp-section-inner"{card_style}>\n'
            f'{stage_block}'
            f'    {journey_meta}\n'
            f'    <h2 class="sp-section-title">{_esc(slide_title)}</h2>\n'
            f'    <div class="sp-section-body">\n'
            f'      {chr(10).join(rendered_elements)}\n'
            f'    </div>\n'
            f'    {bg_avatar_html}\n'
            f'  </div>\n'
            f'</section>\n'
        )
        sections_html.append(section)
        sections_index.append({
            "index": s_idx,
            "title": slide_title,
            "moduleName": module_name,
            "narrativeBeat": narrative_beat,
            "librasScript": slide.get("librasScript", "") or "",
        })

    sections_index_json = json.dumps(sections_index, ensure_ascii=False).replace("</", "<\\/")

    # Look for course-level background music (type="background" audio on any
    # slide). The first one found becomes the ambient loop for the entire page.
    bg_music = _find_background_music(course, project_id, assets_dir, base_url)

    # Use the global course-level background only as fallback (default network pattern)
    bg_image = ""

    # ---------- HTML
    return _BUILD_PAGE(
        title=course_title,
        bg_image=bg_image,
        sections_html="\n".join(sections_html),
        sections_index_json=sections_index_json,
        total_sections=len(sections_html),
        scorm_mode=scorm_mode,
        gamification_config=gamification_config,
        tutor_config=tutor_config,
        bg_music=bg_music,
        loader_title=loader_title,
        loader_primary=loader_primary,
        loader_accent=loader_accent,
        player_theme_css=player_theme_css,
        visual_journey=visual_journey,
        enable_vlibras=bool(project_doc.get("enableVlibras", True)),
        backend_url=base_url,
    )


_VISUAL_JOURNEY_CSS = r'''
body.sp-visual-journey {
  --journey-ink: #172033;
  --journey-muted: #667085;
  --journey-paper: #fbfaf7;
  background: #0d1320;
}
html:has(body.sp-visual-journey) { scroll-padding-top: 72px; }
.sp-visual-journey .sp-main {
  padding: 70px 0 0;
  background:
    radial-gradient(circle at 15% 10%, rgba(45,212,191,.13), transparent 30%),
    radial-gradient(circle at 85% 35%, rgba(59,130,246,.12), transparent 32%),
    #0d1320;
}
.sp-visual-journey .sp-journey-section {
  min-height: calc(100dvh - 70px);
  display: flex;
  align-items: center;
  scroll-margin-top: 70px;
  scroll-snap-align: start;
  margin: 0;
  padding: clamp(8px, 1.5vh, 16px) clamp(8px, 1.4vw, 22px);
  background: linear-gradient(180deg, #f8fafc 0%, #f5f8fb 100%);
}
.sp-visual-journey .sp-journey-section + .sp-journey-section {
  border-top: 1px solid #dbe3ec;
}
.sp-visual-journey .sp-journey-section .sp-section-inner {
  position: relative;
  width: min(1380px, 100%);
  min-height: min(760px, calc(100dvh - 102px));
  margin: 0 auto;
  padding: clamp(28px, 5vw, 72px);
  border-radius: 18px;
  background: var(--journey-paper);
  color: var(--journey-ink);
  border: 1px solid rgba(255,255,255,.16);
  box-shadow: 0 10px 34px rgba(15,23,42,.10);
  overflow: hidden;
  container-type: inline-size;
}
.sp-visual-journey .sp-journey-section:nth-child(even) .sp-section-inner {
  background: linear-gradient(145deg, #f8fafc 0%, #eef6f5 100%);
}
.sp-visual-journey .sp-journey-meta {
  position: relative;
  z-index: 4;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 22px;
  color: #087f73;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: .14em;
  text-transform: uppercase;
}
.sp-visual-journey .sp-journey-meta::before {
  content: '';
  width: 34px;
  height: 3px;
  flex: 0 0 34px;
  border-radius: 99px;
  background: #14b8a6;
}
.sp-visual-journey .sp-journey-meta > span:first-child { margin-right: auto; }
.sp-visual-journey .sp-journey-beat {
  padding: 7px 11px;
  border: 1px solid rgba(13,148,136,.22);
  border-radius: 999px;
  background: rgba(20,184,166,.08);
  letter-spacing: .08em;
}
.sp-visual-journey .sp-section-title {
  position: relative;
  z-index: 4;
  max-width: 850px;
  margin: 0 0 28px;
  color: var(--journey-ink);
  font-family: Manrope, Inter, system-ui, sans-serif;
  font-style: normal;
  text-transform: none;
  font-size: clamp(30px, 3.4vw, 50px);
  line-height: 1.08;
  letter-spacing: -.03em;
}
.sp-visual-journey .sp-section-body { position: relative; z-index: 3; }
.sp-visual-journey .sp-section-body p,
.sp-visual-journey .sp-section-body li {
  color: var(--journey-muted);
  font-size: clamp(17px, 1.5vw, 22px);
  line-height: 1.58;
}
.sp-visual-journey .sp-has-bg-image .sp-section-inner::after {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: linear-gradient(90deg, rgba(10,18,32,.86) 0%, rgba(10,18,32,.45) 48%, rgba(10,18,32,.08) 100%);
  z-index: 1;
}
.sp-visual-journey .sp-has-bg-image .sp-section-title,
.sp-visual-journey .sp-has-bg-image .sp-section-body p,
.sp-visual-journey .sp-has-bg-image .sp-section-body li { color: #fff; }
.sp-visual-journey .sp-drawer { backdrop-filter: blur(18px); }

/* The journey is not a repeated text+image template. Each narrative beat
   receives a distinct composition; generated header strips are suppressed
   because the player already exposes chapter/module context. */
.sp-visual-journey .sp-journey-section .sp-section-body > .sp-html:first-child:has(+ .sp-html) {
  display: none;
}
.sp-visual-journey .sp-journey-section .sp-section-body {
  display: grid;
  gap: clamp(20px, 3vw, 42px);
  align-items: center;
}
.sp-visual-journey .sp-journey-section .sp-section-body > * { min-width: 0; }
.sp-visual-journey .sp-layout-guided-observation .sp-section-body {
  grid-template-columns: minmax(0, 1.12fr) minmax(420px, .88fr);
}
.sp-visual-journey .sp-layout-guided-observation .sp-image { grid-column: 1; grid-row: 1 / span 2; }
.sp-visual-journey .sp-layout-guided-observation .sp-html { grid-column: 2; }
.sp-visual-journey .sp-layout-decision-split .sp-section-body {
  grid-template-columns: minmax(320px, .9fr) minmax(0, 1.1fr);
}
.sp-visual-journey .sp-layout-decision-split .sp-image { grid-column: 1; }
.sp-visual-journey .sp-layout-decision-split .sp-html { grid-column: 2; }
.sp-visual-journey .sp-layout-workbench .sp-section-body {
  grid-template-columns: minmax(280px, .72fr) minmax(0, 1.28fr);
  padding: 22px;
  border: 1px solid rgba(13,148,136,.16);
  border-radius: 22px;
  background: linear-gradient(145deg, rgba(20,184,166,.08), rgba(59,130,246,.06));
}
.sp-visual-journey .sp-layout-workbench .sp-image { grid-column: 2; grid-row: 1; }
.sp-visual-journey .sp-layout-workbench .sp-html { grid-column: 1; grid-row: 1; }

/* Observation pairs use a balanced editorial split when the viewport can
   genuinely support it; only compact screens fall back to vertical flow. */
.sp-visual-journey .sp-layout-guided-observation .sp-section-body:has(iframe) {
  grid-template-columns: minmax(0, 1.08fr) minmax(520px, .92fr);
  max-width: 1320px;
  margin-inline: auto;
  align-items: center;
}
.sp-visual-journey .sp-layout-guided-observation .sp-section-body:has(iframe) .sp-image,
.sp-visual-journey .sp-layout-guided-observation .sp-section-body:has(iframe) .sp-html {
  grid-row: 1 !important;
  width: 100% !important;
  min-width: 0;
}
.sp-visual-journey .sp-layout-guided-observation .sp-section-body:has(iframe) .sp-image { grid-column: 1 !important; }
.sp-visual-journey .sp-layout-guided-observation .sp-section-body:has(iframe) .sp-html { grid-column: 2 !important; }
.sp-visual-journey .sp-layout-guided-observation .sp-section-body:has(iframe) .sp-html iframe {
  display: block;
  width: 100% !important;
  min-height: 0 !important;
  height: auto !important;
  aspect-ratio: 16 / 9;
  border-radius: 18px !important;
  box-shadow: 0 16px 44px rgba(15,23,42,.14);
}
.sp-visual-journey .sp-layout-reflection .sp-section-title { text-align: center; margin-inline: auto; }
.sp-visual-journey .sp-layout-reflection .sp-section-body { max-width: 920px; margin: 0 auto; }
.sp-visual-journey .sp-layout-reflection .sp-image img { max-height: 330px; object-fit: cover; width: 100%; }
/* Games, simulators, timelines, cases and infographics own the whole stage.
   They are 16:9 applications, never side panels in an editorial grid. */
.sp-visual-journey .sp-layout-interactive-stage { min-height: auto; }
.sp-visual-journey .sp-layout-interactive-stage .sp-section-inner {
  width: min(1320px, 100%);
  min-height: 0;
  padding: clamp(12px, 1.5vw, 20px);
  background: linear-gradient(145deg, #f8fafc, #eef2f7);
}
.sp-visual-journey .sp-layout-interactive-stage .sp-journey-meta {
  margin: 0 4px 6px; font-size: 10px; letter-spacing: .11em;
}
.sp-visual-journey .sp-layout-interactive-stage .sp-section-title {
  max-width: none; margin: 0 4px 10px; font-family: Inter, Manrope, system-ui, sans-serif;
  font-size: clamp(20px, 2vw, 30px); line-height: 1.14; letter-spacing: -.02em;
}
.sp-visual-journey .sp-layout-interactive-stage .sp-section-body {
  display: block !important;
  width: 100%; max-width: none; margin: 0; padding: 0;
}
.sp-visual-journey .sp-layout-interactive-stage .sp-section-body > * {
  width: 100% !important; max-width: none !important; grid-column: 1 !important;
}
.sp-visual-journey .sp-layout-interactive-stage .sp-html,
.sp-visual-journey .sp-layout-interactive-stage .sp-simulator,
.sp-visual-journey .sp-layout-interactive-stage .sp-quiz,
.sp-visual-journey .sp-layout-interactive-stage .sp-scenario {
  width: 100%; margin: 0; padding: 0; border-radius: 16px; overflow: hidden;
  background: transparent;
}
.sp-visual-journey .sp-layout-interactive-stage .sp-scenario,
.sp-visual-journey .sp-layout-interactive-stage .sp-quiz {
  max-height: min(72vh, 720px); overflow: auto; overscroll-behavior: contain;
}
.sp-visual-journey .sp-layout-interactive-stage .sp-scenario-title { font-size: clamp(24px, 3vw, 38px); }
.sp-visual-journey .sp-layout-interactive-stage .sp-scenario p { font-size: clamp(15px, 1.35vw, 19px); }
.sp-visual-journey .sp-layout-interactive-stage .sp-html > iframe,
.sp-visual-journey .sp-layout-interactive-stage .sp-simulator > iframe {
  display: block;
  width: min(100%, calc((100dvh - 238px) * 1.77778)) !important;
  height: auto !important; min-height: 0 !important; aspect-ratio: 16 / 9;
  max-height: calc(100dvh - 238px); margin: 0 auto;
  border: 0 !important; border-radius: 16px !important; background: transparent;
  box-shadow: 0 16px 44px rgba(15,23,42,.16);
}
.sp-visual-journey .sp-layout-interactive-stage .sp-iframe-done {
  position: sticky; bottom: 10px; z-index: 12;
  width: auto !important; min-width: 250px; margin: 8px auto 0 !important; display: block;
  padding: 10px 18px; border-radius: 999px; box-shadow: 0 10px 28px rgba(15,23,42,.2);
}

@media (max-height: 760px) and (min-width: 721px) {
  .sp-visual-journey .sp-main { padding-top: 58px; padding-bottom: 72px; }
  .sp-visual-journey .sp-layout-interactive-stage { align-items: flex-start; }
  .sp-visual-journey .sp-layout-interactive-stage .sp-section-inner { padding: 10px 14px; }
  .sp-visual-journey .sp-layout-interactive-stage .sp-journey-meta { margin-bottom: 3px; }
  .sp-visual-journey .sp-layout-interactive-stage .sp-section-title { font-size: 20px; margin-bottom: 6px; }
  .sp-visual-journey .sp-layout-interactive-stage .sp-html > iframe,
  .sp-visual-journey .sp-layout-interactive-stage .sp-simulator > iframe {
    width: min(100%, calc((100dvh - 190px) * 1.77778)) !important;
    max-height: calc(100dvh - 190px);
  }
  .sp-visual-journey .sp-layout-interactive-stage .sp-iframe-done { margin-top: 5px !important; padding: 8px 16px; }
}

/* At laptop widths, side rails become unpleasant reading columns. Keep the
   visual rhythm, but switch to a deliberate vertical story rather than
   shrinking text and interactions until they clip. */
@media (max-width: 1450px) and (min-width: 721px) {
  .sp-visual-journey .sp-layout-decision-split .sp-section-body,
  .sp-visual-journey .sp-layout-workbench .sp-section-body {
    grid-template-columns: minmax(0, 1fr);
    max-width: 980px;
    margin-inline: auto;
  }
  .sp-visual-journey .sp-layout-decision-split .sp-image,
  .sp-visual-journey .sp-layout-decision-split .sp-html,
  .sp-visual-journey .sp-layout-workbench .sp-image,
  .sp-visual-journey .sp-layout-workbench .sp-html {
    grid-column: 1 !important;
    grid-row: auto !important;
    width: 100% !important;
  }
  .sp-visual-journey .sp-layout-decision-split .sp-image,
  .sp-visual-journey .sp-layout-workbench .sp-image { max-width: 860px; margin-inline: auto; }
}
@media (max-width: 1199px) {
  .sp-visual-journey .sp-layout-guided-observation .sp-section-body:has(iframe) {
    grid-template-columns: minmax(0, 1fr);
    max-width: 980px;
  }
  .sp-visual-journey .sp-layout-guided-observation .sp-section-body:has(iframe) .sp-image,
  .sp-visual-journey .sp-layout-guided-observation .sp-section-body:has(iframe) .sp-html {
    grid-column: 1 !important; grid-row: auto !important;
  }
}
.sp-visual-journey .sp-layout-cinematic-scene .sp-section-inner { padding: 0; background: #101827; }
.sp-visual-journey .sp-layout-cinematic-scene .sp-journey-meta,
.sp-visual-journey .sp-layout-cinematic-scene .sp-section-title {
  position: absolute; left: clamp(28px, 5vw, 70px); right: 42%; z-index: 8;
}
.sp-visual-journey .sp-layout-cinematic-scene .sp-journey-meta { top: 42px; color: #5eead4; }
.sp-visual-journey .sp-layout-cinematic-scene .sp-section-title { top: 105px; color: #fff; text-shadow: 0 3px 22px #000; }
.sp-visual-journey .sp-layout-cinematic-scene .sp-section-body { display: block; min-height: 650px; }
.sp-visual-journey .sp-layout-cinematic-scene .sp-image { position: absolute; inset: 0; }
.sp-visual-journey .sp-layout-cinematic-scene .sp-image img {
  width: 100%; height: 100%; max-width: none; object-fit: cover; border-radius: 0 !important; box-shadow: none !important;
}
.sp-visual-journey .sp-layout-cinematic-scene .sp-image::after {
  content: ''; position: absolute; inset: 0;
  background: linear-gradient(90deg, rgba(5,10,20,.92) 0%, rgba(5,10,20,.68) 42%, rgba(5,10,20,.06) 78%);
}
.sp-visual-journey .sp-layout-cinematic-scene .sp-html:not(:first-child) {
  position: absolute; left: clamp(28px, 5vw, 70px); bottom: 52px; width: min(620px, 52%); z-index: 7;
  padding: 20px 24px; border-left: 4px solid #2dd4bf; border-radius: 0 16px 16px 0;
  background: rgba(9,18,32,.72); backdrop-filter: blur(12px); color: #fff;
}
.sp-visual-journey .sp-layout-cinematic-scene .sp-html:not(:first-child) * { color: #fff !important; }

/* Guided image exploration: numbered pins reveal evidence from the authored
   scene. This makes the illustration necessary to complete the observation. */
.sp-evidence-scene { position: relative; display: grid; gap: 12px; }
.sp-evidence-prompt { font-weight: 750; color: #0f766e; font-size: 15px; }
.sp-evidence-media { position: relative; min-height: 360px; overflow: hidden; border-radius: 20px; background: #dbe4ea; }
.sp-evidence-media img { width: 100%; height: 100%; min-height: 360px; object-fit: cover; display: block; transition: transform .45s ease; }
.sp-evidence-scene.is-explored .sp-evidence-media img { transform: scale(1.025); }
.sp-evidence-pin { position: absolute; width: 42px; height: 42px; border-radius: 50%; border: 3px solid #fff; color: #fff; background: #0d9488; font-weight: 900; cursor: pointer; box-shadow: 0 0 0 8px rgba(20,184,166,.2),0 8px 24px rgba(0,0,0,.28); animation: spPinPulse 2.1s infinite; }
.sp-evidence-pin-1 { left: 18%; top: 24%; }
.sp-evidence-pin-2 { left: 61%; top: 38%; animation-delay: .35s; }
.sp-evidence-pin-3 { right: 13%; bottom: 18%; animation-delay: .7s; }
@keyframes spPinPulse { 50% { box-shadow: 0 0 0 14px rgba(20,184,166,0),0 8px 24px rgba(0,0,0,.28); } }
.sp-evidence-cards { display: grid; gap: 8px; }
.sp-evidence-card { display: none; align-items: flex-start; gap: 10px; padding: 11px 13px; border-radius: 12px; background: #ecfdf5; color: #115e59; animation: spEvidenceIn .28s ease both; }
.sp-evidence-card.is-visible { display: flex; }
.sp-evidence-card b { display: grid; place-items: center; flex: 0 0 25px; height: 25px; border-radius: 50%; background: #0d9488; color: #fff; }
@keyframes spEvidenceIn { from { opacity: 0; transform: translateY(8px); } }
@media (max-width: 760px) {
  .sp-visual-journey .sp-main { padding: 64px 0 0; }
  .sp-visual-journey .sp-journey-section { min-height: calc(100dvh - 64px); margin: 0; padding: 6px; }
  .sp-visual-journey .sp-journey-section .sp-section-inner {
    min-height: calc(100dvh - 76px); padding: 24px 20px; border-radius: 12px;
  }
  .sp-visual-journey .sp-journey-meta { align-items: flex-start; flex-wrap: wrap; }
  .sp-visual-journey .sp-section-title { font-size: clamp(30px, 10vw, 46px); }
  .sp-visual-journey .sp-layout-guided-observation .sp-section-body,
  .sp-visual-journey .sp-layout-decision-split .sp-section-body,
  .sp-visual-journey .sp-layout-workbench .sp-section-body { grid-template-columns: 1fr; }
  .sp-visual-journey .sp-layout-guided-observation .sp-image,
  .sp-visual-journey .sp-layout-guided-observation .sp-html,
  .sp-visual-journey .sp-layout-decision-split .sp-image,
  .sp-visual-journey .sp-layout-decision-split .sp-html,
  .sp-visual-journey .sp-layout-workbench .sp-image,
  .sp-visual-journey .sp-layout-workbench .sp-html { grid-column: 1; grid-row: auto; }
  .sp-visual-journey .sp-layout-interactive-stage .sp-section-inner { padding: 10px; border-radius: 14px; }
  .sp-visual-journey .sp-layout-interactive-stage .sp-section-title { font-size: 24px; }
  .sp-visual-journey .sp-layout-interactive-stage .sp-html > iframe,
  .sp-visual-journey .sp-layout-interactive-stage .sp-simulator > iframe { max-height: none; }
  .sp-visual-journey .sp-layout-cinematic-scene .sp-section-title { right: 20px; top: 120px; }
  .sp-visual-journey .sp-layout-cinematic-scene .sp-html:not(:first-child) { width: auto; right: 20px; }
}
'''


def _BUILD_PAGE(
    title: str,
    bg_image: str,
    sections_html: str,
    sections_index_json: str,
    total_sections: int,
    scorm_mode: bool = False,
    gamification_config: Optional[dict] = None,
    tutor_config: Optional[dict] = None,
    bg_music: Optional[dict] = None,
    loader_title: str = "Carregando curso…",
    loader_primary: str = "#3b82f6",
    loader_accent: str = "#60a5fa",
    enable_vlibras: bool = True,
    backend_url: str = "",
    player_theme_css: str = "",
    visual_journey: bool = False,
) -> str:
    css = _CSS
    js = _JS.replace("__SECTIONS_INDEX__", sections_index_json) \
            .replace("__SCORM_MODE__", "true" if scorm_mode else "false")
    scorm_script = '<script src="scorm-api.js"></script>' if scorm_mode else ''

    vlibras_block = ""
    if enable_vlibras:
        proxy_base = backend_url.rstrip("/") + "/api/vlibras-proxy" if backend_url else ""
        vlibras_block = f'''<!-- VLibras - acessibilidade em LIBRAS -->
<div vw class="enabled">
  <div vw-access-button class="active"></div>
  <div vw-plugin-wrapper><div class="vw-plugin-top-wrapper"></div></div>
</div>
<script>
(function() {{
  var PROXY_BASE = {json.dumps(proxy_base)};
  if (PROXY_BASE) {{
    var domainMap = {{
      "dicionario2.vlibras.gov.br": PROXY_BASE + "/dicionario2",
      "traducao2.vlibras.gov.br": PROXY_BASE + "/traducao2"
    }};
    var originalOpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function(method, url) {{
      var openArgs = arguments;
      if (typeof url === "string") {{
        Object.keys(domainMap).some(function(domain) {{
          if (url.indexOf(domain) === -1) return false;
          try {{
            var parsed = new URL(url);
            openArgs[1] = domainMap[domain] + parsed.pathname + parsed.search;
          }} catch (error) {{ console.warn("[VLibras] Proxy URL error", error); }}
          return true;
        }});
      }}
      return originalOpen.apply(this, openArgs);
    }};
  }}

  window.__scormifyVlibrasQueue = "";
  window.scormifyTranslateLibras = function(text) {{
    if (!text) return;
    window.__scormifyVlibrasQueue = text;
    if (window.plugin && typeof window.plugin.translate === "function") {{
      try {{
        window.plugin.translate(text);
        window.__scormifyVlibrasQueue = "";
      }} catch (error) {{ console.warn("[VLibras] Translation error", error); }}
    }}
  }};

  var script = document.createElement("script");
  script.src = "https://vlibras.gov.br/app/vlibras-plugin.js";
  script.async = true;
  script.onload = function() {{
    try {{
      new window.VLibras.Widget({{position: "R", avatar: "random"}});
      var attempts = 0;
      var readyPoll = setInterval(function() {{
        attempts += 1;
        if (window.plugin && typeof window.plugin.translate === "function") {{
          clearInterval(readyPoll);
          if (window.__scormifyVlibrasQueue) {{
            window.scormifyTranslateLibras(window.__scormifyVlibrasQueue);
          }}
        }} else if (attempts >= 120) {{
          clearInterval(readyPoll);
        }}
      }}, 1000);
    }} catch (error) {{ console.warn("[VLibras] Initialization error", error); }}
  }};
  script.onerror = function() {{
    console.warn("[VLibras] Plugin script unavailable. Check LMS internet/CSP policy.");
  }};
  document.head.appendChild(script);
}})();
</script>'''

    # Course-level background music (type="background" audio): render ONE
    # looping <audio> + a toggle button. Browsers block autoplay until the
    # user interacts — the JS runtime waits for the first click/keydown.
    bg_music_html = ""
    bg_music_button_html = ""
    if bg_music and bg_music.get("src"):
        bg_music_html = (
            f'<audio id="sp-bg-music" class="sp-bg-music" loop preload="auto" '
            f'src="{_esc(bg_music["src"])}" data-volume="{bg_music["volume"]}" '
            f'data-testid="sp-bg-music"></audio>'
        )
        bg_music_button_html = (
            '<button type="button" class="sp-bg-music-toggle" data-testid="sp-bg-music-toggle" '
            'aria-label="Música ambiente" title="Música ambiente"><span class="sp-bg-music-icon">🎵</span></button>'
        )

    # Gamification: inject engine + config when enabled
    gamification_script = ""
    if gamification_config and gamification_config.get("enabled"):
        try:
            engine_path = Path(__file__).parent / "export_assets" / "gamification.js"
            engine_js = engine_path.read_text(encoding="utf-8")
            config_json = json.dumps(gamification_config, ensure_ascii=False).replace("</", "<\\/")
            gamification_script = (
                f'<script>{engine_js}</script>\n'
                f'<script>'
                f'window.GAMIFICATION_CONFIG = {config_json};'
                f'document.addEventListener("DOMContentLoaded", function(){{'
                f'  if (window.Gamification) {{ Gamification.init(window.GAMIFICATION_CONFIG); }}'
                f'}});'
                f'</script>'
            )
        except Exception:
            gamification_script = ""

    # AI Tutor: inject inline CSS + JS + config when admin toggled enabled
    tutor_script = ""
    tutor_style = ""
    if tutor_config and tutor_config.get("enabled"):
        try:
            assets_root = Path(__file__).parent / "export_assets"
            tutor_css = (assets_root / "tutor.css").read_text(encoding="utf-8")
            from services.player_theme import build_tutor_theme_css
            tutor_css += "\n" + build_tutor_theme_css(tutor_config.get("theme"))
            tutor_js = (assets_root / "tutor.js").read_text(encoding="utf-8")
            # Force cssInlined=true so the widget skips fetching styles/tutor.css (which doesn't exist in single-page)
            tutor_cfg = dict(tutor_config)
            tutor_cfg["cssInlined"] = True
            tutor_cfg_json = json.dumps(tutor_cfg, ensure_ascii=False).replace("</", "<\\/")
            tutor_style = (
                f'<style data-tutor-css="1">{tutor_css}\n'
                f'/* Single Page positioning override — Tutor FAB on the LEFT to avoid collision with .sp-next-btn (right). */\n'
                f'.tutor-fab{{left:24px !important;right:auto !important}}\n'
                f'.tutor-panel{{left:24px !important;right:auto !important}}\n'
                f'@media (max-width: 480px){{\n'
                f'  .tutor-fab{{left:16px !important;right:auto !important;bottom:16px}}\n'
                f'  .tutor-panel{{left:0 !important;right:0 !important}}\n'
                f'}}\n'
                f'</style>'
            )
            tutor_script = (
                f'<script>{tutor_js}</script>\n'
                f'<script>'
                f'window.TUTOR_CONFIG = {tutor_cfg_json};'
                f'document.addEventListener("DOMContentLoaded", function(){{'
                f'  if (window.AiTutor) {{ AiTutor.init(window.TUTOR_CONFIG); }}'
                f'}});'
                f'</script>'
            )
        except Exception:
            tutor_script = ""
            tutor_style = ""
    bg_layer = (
        f'<div class="sp-bg-image" style="background-image:url({_esc(bg_image)})"></div>'
        if bg_image else
        '<div class="sp-bg-pattern"></div>'
    )
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_esc(title)}</title>
<style>{css}\n{player_theme_css}\n{_VISUAL_JOURNEY_CSS if visual_journey else ''}</style>
{tutor_style}
{scorm_script}
</head>
<body class="{'sp-visual-journey' if visual_journey else ''}">
<!-- ── Initial loading overlay (SCORM single-page): covers viewport
     until the first section's assets settle. Critical for LMSes on
     narrow bandwidth — without it the learner sees broken-image
     placeholders before assets stream in. Self-contained CSS + JS so
     it works even if the rest of the bundle is still parsing.  ── -->
<div id="scormify-loader" role="status" aria-label="Carregando curso" data-testid="scorm-initial-loader">
  <style>
    #scormify-loader {{
      position: fixed; inset: 0; z-index: 99999;
      background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
      color: #f1f5f9;
      display: flex; align-items: center; justify-content: center;
      flex-direction: column;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      transition: opacity 0.5s ease;
    }}
    #scormify-loader.hidden {{ opacity: 0; pointer-events: none; }}
    #scormify-loader .ldr-spin {{
      width: 64px; height: 64px;
      border: 4px solid rgba(255,255,255,0.12);
      border-top-color: {loader_primary};
      border-radius: 50%;
      animation: scormify-spin 0.9s linear infinite;
      margin-bottom: 24px;
    }}
    #scormify-loader .ldr-title {{
      font-size: 18px; font-weight: 600; margin-bottom: 14px;
      text-align: center; padding: 0 16px; max-width: min(640px, 90vw);
    }}
    #scormify-loader .ldr-bar-track {{
      width: min(320px, 60vw); height: 6px;
      background: rgba(255,255,255,0.12);
      border-radius: 999px; overflow: hidden;
    }}
    #scormify-loader .ldr-bar-fill {{
      height: 100%; width: 0%;
      background: linear-gradient(90deg, {loader_primary}, {loader_accent});
      border-radius: 999px;
      transition: width 0.25s ease;
    }}
    #scormify-loader .ldr-percent {{
      font-size: 13px; opacity: 0.7;
      margin-top: 10px; font-variant-numeric: tabular-nums;
    }}
    @keyframes scormify-spin {{
      from {{ transform: rotate(0deg); }}
      to   {{ transform: rotate(360deg); }}
    }}
  </style>
  <div class="ldr-spin" aria-hidden="true"></div>
  <div class="ldr-title">{loader_title}</div>
  <div class="ldr-bar-track" aria-hidden="true">
    <div class="ldr-bar-fill" id="scormify-loader-bar"></div>
  </div>
  <div class="ldr-percent" id="scormify-loader-percent">0%</div>
</div>
<script>
  (function() {{
    var overlay = document.getElementById('scormify-loader');
    var bar = document.getElementById('scormify-loader-bar');
    var pctLabel = document.getElementById('scormify-loader-percent');
    var hidden = false;
    function setProgress(p) {{
      p = Math.max(0, Math.min(100, p));
      if (bar) bar.style.width = p.toFixed(0) + '%';
      if (pctLabel) pctLabel.textContent = p.toFixed(0) + '%';
    }}
    function hide() {{
      if (hidden) return;
      hidden = true;
      setProgress(100);
      setTimeout(function() {{
        if (overlay) {{
          overlay.classList.add('hidden');
          setTimeout(function() {{
            if (overlay && overlay.parentNode) overlay.parentNode.removeChild(overlay);
          }}, 600);
        }}
      }}, 180);
    }}
    function firstSectionAssets() {{
      // The single-page exporter renders each slide as a top-level
      // <section> (often with class containing "slide" or
      // "sp-section"). We pick the FIRST section to gate the overlay
      // — once its images/videos load the user has visible content.
      var sec = document.querySelector('main section, article section, section.sp-slide, section[data-slide-index], section');
      if (!sec) return null;
      var imgs = Array.from(sec.querySelectorAll('img'));
      var vids = Array.from(sec.querySelectorAll('video'));
      return {{sec: sec, imgs: imgs, vids: vids}};
    }}
    function track() {{
      var info = firstSectionAssets();
      if (!info) {{ setTimeout(hide, 250); return; }}
      var total = info.imgs.length + info.vids.length;
      if (total === 0) {{ setTimeout(hide, 250); return; }}
      var loaded = 0;
      function bump() {{
        loaded++;
        setProgress((loaded / total) * 95);
        if (loaded >= total) hide();
      }}
      info.imgs.forEach(function(im) {{
        if (im.complete && im.naturalWidth > 0) bump();
        else {{
          im.addEventListener('load', bump, {{once: true}});
          im.addEventListener('error', bump, {{once: true}});
        }}
      }});
      info.vids.forEach(function(v) {{
        if (v.readyState >= 2) bump();
        else {{
          v.addEventListener('loadeddata', bump, {{once: true}});
          v.addEventListener('error', bump, {{once: true}});
        }}
      }});
    }}
    if (document.readyState === 'loading') {{
      document.addEventListener('DOMContentLoaded', track);
    }} else {{
      track();
    }}
    // Hard safety net: never block more than 15 s.
    setTimeout(hide, 15000);
    // Coarse progress while waiting for DOMContentLoaded.
    var coarse = 5;
    var ph = setInterval(function() {{
      if (hidden) {{ clearInterval(ph); return; }}
      coarse = Math.min(coarse + 3, 35);
      setProgress(coarse);
    }}, 250);
  }})();
</script>
{bg_layer}

<header class="sp-header" data-testid="sp-header">
  <button class="sp-menu-btn" type="button" aria-label="Menu" data-testid="sp-menu-btn"
          onclick="window.SP&&SP.toggleDrawer()">
    <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor"
         stroke-width="2" stroke-linecap="round"><path d="M3 6h18"/><path d="M3 12h18"/><path d="M3 18h18"/></svg>
  </button>
  <h1 class="sp-title">{_esc(title)}</h1>
  <div class="sp-progress" aria-label="Progresso">
    <div class="sp-progress-fill" data-testid="sp-progress-fill"></div>
  </div>
  <button type="button" class="sp-fullscreen-btn" data-testid="sp-fullscreen-btn"
          aria-label="Modo Tela Cheia" title="Modo Tela Cheia (F11)">
    <svg class="sp-icon-expand" viewBox="0 0 24 24" width="20" height="20" fill="none"
         stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M8 3H5a2 2 0 0 0-2 2v3"/><path d="M21 8V5a2 2 0 0 0-2-2h-3"/>
      <path d="M3 16v3a2 2 0 0 0 2 2h3"/><path d="M16 21h3a2 2 0 0 0 2-2v-3"/>
    </svg>
    <svg class="sp-icon-shrink" viewBox="0 0 24 24" width="20" height="20" fill="none"
         stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M8 3v3a2 2 0 0 1-2 2H3"/><path d="M21 8h-3a2 2 0 0 1-2-2V3"/>
      <path d="M3 16h3a2 2 0 0 1 2 2v3"/><path d="M16 21v-3a2 2 0 0 1 2-2h3"/>
    </svg>
  </button>
  {bg_music_button_html}
</header>

{bg_music_html}
{vlibras_block}

<aside class="sp-drawer" data-testid="sp-drawer" aria-hidden="true">
  <ul class="sp-drawer-list" data-testid="sp-drawer-list"></ul>
</aside>

<main class="sp-main" data-testid="sp-main">
{sections_html}
<section class="sp-end-card sp-section" data-index="{total_sections}" data-final="true" data-locked="true">
  <div class="sp-section-inner sp-end-inner">
    <div class="sp-end-icon">🎓</div>
    <h2>Curso Concluído!</h2>
    <p>Parabéns por concluir todas as seções do curso.</p>
  </div>
</section>
</main>

<button type="button" class="sp-next-btn" data-testid="sp-next-btn" hidden
        onclick="window.SP&&SP.advance()" aria-label="Próxima seção">
  <svg viewBox="0 0 24 24" width="32" height="32" fill="none" stroke="currentColor"
       stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
    <polyline points="6 9 12 15 18 9"></polyline>
  </svg>
</button>

<script>{js}</script>
{gamification_script}
{tutor_script}
</body>
</html>
"""


# --------------------------------------------------------------------------- CSS

# JS/CSS runtime lives in `sp_runtime/` — extracted in the 2026-04-29
# refactor so the file is editable with proper syntax highlighting and
# Python LOC stays manageable. Both files are loaded once at import time.
_RUNTIME_DIR = Path(__file__).parent / 'sp_runtime'
_CSS = (_RUNTIME_DIR / 'styles.css').read_text(encoding='utf-8')
_JS = (_RUNTIME_DIR / 'runtime.js').read_text(encoding='utf-8')
