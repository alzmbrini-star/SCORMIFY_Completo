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
            "mp4": "video/mp4", "webm": "video/webm",
        }
        mime = mime_map.get(ext, "application/octet-stream")
        data = base64.b64encode(p.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{data}"
    except Exception:
        return None


def _resolve_asset_url(url: str, project_id: str, assets_dir: str, base_url: str = "") -> str:
    """Convert a /api/projects/<id>/assets/<file> URL to an inlined data URI
    when the file exists on disk. Falls back to absolute base_url + path.
    """
    if not url:
        return url
    if url.startswith("data:") or url.startswith("blob:"):
        return url
    # Match local project asset path
    m = re.match(r"^/api/projects/[^/]+/assets/(.+)$", url)
    if m:
        fname = m.group(1)
        local_path = Path(assets_dir) / fname
        data_uri = _b64_data_uri(str(local_path))
        if data_uri:
            return data_uri
        # Fallback to remote
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
    """Replace asset URLs inside an htmlContent fragment with data URIs."""
    if not html_str:
        return ""

    def repl(match: re.Match) -> str:
        full = match.group(0)
        url = match.group(1)
        new_url = _resolve_asset_url(url, project_id, assets_dir, base_url)
        return full.replace(url, new_url)

    pattern = re.compile(r'(?:src|href)\s*=\s*"(/api/projects/[^"]+)"')
    return pattern.sub(repl, html_str)


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
    else:
        return ""
    return _maybe_wrap_with_timeline(rendered, el)


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
def _render_text_element_inner(el: dict) -> str:
    content = el.get("content") or ""
    style = el.get("style") or {}
    css_parts = []
    for k, v in style.items():
        if v in (None, ""):
            continue
        # Skip absolute positioning fields if any leaked into style
        if k in ("position", "top", "left", "right", "bottom"):
            continue
        css_parts.append(f"{_kebab(k)}:{_esc(v)}")
    style_attr = ";".join(css_parts)
    return f'<div class="sp-text" style="{style_attr}">{_safe_text_html(content)}</div>'


def _render_image_element_inner(el: dict, project_id: str, assets_dir: str, base_url: str) -> str:
    src = el.get("src") or el.get("content") or ""
    src = _resolve_asset_url(src, project_id, assets_dir, base_url)
    alt = _esc(el.get("alt", ""))
    style = el.get("style") or {}
    radius = style.get("borderRadius", "8px")
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


def _render_html_element_inner(el: dict, project_id: str, assets_dir: str, base_url: str,
                                 slide_idx: int, el_idx: int) -> str:
    raw = el.get("htmlContent") or el.get("content") or ""
    raw = _inline_assets_in_html(raw, project_id, assets_dir, base_url)
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
            '<style>html,body{margin:0 !important;padding:0 !important;'
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
    if is_interactive:
        return (
            f'<div class="sp-html sp-interactive" data-interactive="html" data-required="true" '
            f'onclick="window.SP&&SP.markClicked(this)">'
            f'{raw}'
            f'<div class="sp-html-hint">👆 Clique aqui para liberar a próxima seção</div>'
            f'</div>'
        )
    return f'<div class="sp-html">{raw}</div>'


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
    return (
        f'<div class="sp-quiz sp-interactive" data-interactive="quiz" data-required="true" '
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


def _render_simulator_element_inner(el: dict, project_id: str, assets_dir: str, base_url: str, slide_idx: int, el_idx: int) -> str:
    sim_html = el.get("htmlContent") or el.get("content") or ""
    sim_html = _inline_assets_in_html(sim_html, project_id, assets_dir, base_url)
    if "<meta" not in sim_html.lower() and "charset" not in sim_html.lower():
        sim_html = '<meta charset="utf-8">\n' + sim_html
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
        for e_idx, el in enumerate(elements):
            try:
                html_part = _render_element(el, project_id, assets_dir, base_url,
                                              s_idx, e_idx, questions_lookup)
                if html_part:
                    rendered_elements.append(html_part)
            except Exception:
                continue

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
        locked_attr = 'data-locked="true"' if s_idx > 0 else ''

        bg_color = (slide.get("background") or "").strip()
        bg_image_url = slide.get("backgroundImage") or ""
        if bg_image_url:
            bg_image_url = _resolve_asset_url(bg_image_url, project_id, assets_dir, base_url)
        card_styles = []
        section_class = "sp-section"
        if bg_color:
            card_styles.append(f"background-color:{_esc(bg_color)}")
            if _is_dark_color(bg_color):
                card_styles.append("color:#f1f5f9")
                section_class += " sp-dark"
        if bg_image_url:
            card_styles.append(f"background-image:url({_esc(bg_image_url)})")
            card_styles.append("background-size:cover")
            card_styles.append("background-position:center")
            section_class += " sp-has-bg-image"
        card_style = f' style="{";".join(card_styles)}"' if card_styles else ''

        section = (
            f'<section class="{section_class}" data-index="{s_idx}" '
            f'data-title="{_esc(slide_title)}" '
            f'{locked_attr}>\n'
            f'  <div class="sp-section-inner"{card_style}>\n'
            f'    <h2 class="sp-section-title">{_esc(slide_title)}</h2>\n'
            f'    <div class="sp-section-body">\n'
            f'      {chr(10).join(rendered_elements)}\n'
            f'    </div>\n'
            f'  </div>\n'
            f'</section>\n'
        )
        sections_html.append(section)
        sections_index.append({"index": s_idx, "title": slide_title})

    sections_index_json = json.dumps(sections_index, ensure_ascii=False).replace("</", "<\\/")

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
    )


def _BUILD_PAGE(
    title: str,
    bg_image: str,
    sections_html: str,
    sections_index_json: str,
    total_sections: int,
    scorm_mode: bool = False,
    gamification_config: Optional[dict] = None,
    tutor_config: Optional[dict] = None,
) -> str:
    css = _CSS
    js = _JS.replace("__SECTIONS_INDEX__", sections_index_json) \
            .replace("__SCORM_MODE__", "true" if scorm_mode else "false")
    scorm_script = '<script src="scorm-api.js"></script>' if scorm_mode else ''

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
<style>{css}</style>
{tutor_style}
{scorm_script}
</head>
<body>
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
</header>

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

_CSS = """
*{box-sizing:border-box;margin:0;padding:0}
html,body{background:#071122;color:#0f172a;font-family:'Segoe UI',Roboto,system-ui,-apple-system,sans-serif;
  scroll-behavior:smooth;min-height:100vh}
body{position:relative;overflow-x:hidden}

/* ---- background ---- */
.sp-bg-image,.sp-bg-pattern{position:fixed;inset:0;z-index:-1;background-color:#0a2540;background-size:cover;background-position:center}
.sp-bg-pattern{
  background:#0a2540 url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='400' height='400' viewBox='0 0 400 400'><g stroke='%23ffffff14' stroke-width='1'><circle cx='40' cy='80' r='2' fill='%23ffffff20'/><circle cx='350' cy='120' r='2' fill='%23ffffff20'/><circle cx='200' cy='250' r='2' fill='%23ffffff20'/><circle cx='90' cy='320' r='2' fill='%23ffffff20'/><line x1='40' y1='80' x2='350' y2='120'/><line x1='40' y1='80' x2='200' y2='250'/><line x1='350' y1='120' x2='200' y2='250'/><line x1='200' y1='250' x2='90' y2='320'/></g></svg>") repeat
}

/* ---- top header ---- */
.sp-header{position:fixed;top:0;left:0;right:0;z-index:50;height:54px;background:#000;color:#fff;display:flex;align-items:center;padding:0 18px;gap:14px}
.sp-menu-btn{background:transparent;color:#fff;border:0;padding:8px;cursor:pointer;border-radius:6px;display:flex;align-items:center;justify-content:center}
.sp-menu-btn:hover{background:#ffffff14}
.sp-title{flex:1;text-align:right;font-style:italic;font-weight:500;font-size:14px;letter-spacing:.6px;text-transform:uppercase;color:#e2e8f0}
.sp-progress{position:absolute;left:0;right:0;bottom:0;height:4px;background:#1e293b}
.sp-progress-fill{width:0%;height:100%;background:linear-gradient(90deg,#facc15,#84cc16);transition:width .4s ease}

/* ---- drawer ---- */
.sp-drawer{position:fixed;top:54px;left:0;width:300px;max-width:85vw;height:calc(100vh - 54px);background:#0a1424;color:#e2e8f0;transform:translateX(-100%);transition:transform .3s ease;z-index:40;overflow-y:auto;padding:14px;border-right:1px solid #1e293b;box-shadow:6px 0 24px rgba(0,0,0,.4)}
.sp-drawer[data-open="true"]{transform:translateX(0)}
.sp-drawer-list{list-style:none;display:flex;flex-direction:column;gap:6px}
.sp-drawer-list li{padding:10px 12px;border-radius:8px;border:1px solid transparent;cursor:pointer;font-size:13px;display:flex;align-items:center;gap:10px;transition:background .2s}
.sp-drawer-list li.unlocked:hover{background:#1e293b;border-color:#334155}
.sp-drawer-list li.locked{opacity:.45;cursor:not-allowed}
.sp-drawer-list li.active{background:#1e3a5f;border-color:#2563eb}
.sp-drawer-list li.completed::before{content:"✓";color:#84cc16;font-weight:700;font-size:14px}
.sp-drawer-list li.locked::before{content:"🔒";font-size:13px}
.sp-drawer-list li.unlocked:not(.completed):not(.locked)::before{content:"▶";color:#facc15;font-size:11px}

/* ---- main + sections ---- */
.sp-main{padding:54px 0 80px;display:flex;flex-direction:column;gap:0;width:100%;max-width:none}
.sp-section{min-height:100vh;padding:50px 16px;position:relative;width:100%;box-sizing:border-box}
.sp-section[data-locked="true"]{display:none}
.sp-section.unlocked,
.sp-section:first-of-type:not([data-locked]){display:block;animation:sp-fade-in .6s ease}
@keyframes sp-fade-in{from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:translateY(0)}}
.sp-section-inner{width:100%;max-width:1080px;margin:0 auto;background:#fff;border-radius:14px;padding:48px 56px;box-shadow:0 20px 60px rgba(0,0,0,.35);box-sizing:border-box}
.sp-section-title{font-family:Georgia,'Times New Roman',serif;font-style:italic;color:#1e3a8a;font-size:34px;font-weight:400;text-transform:uppercase;letter-spacing:.5px;margin-bottom:28px;line-height:1.1;text-align:center}
.sp-section.sp-dark .sp-section-title{color:#fde047}
.sp-section.sp-dark .sp-section-body{color:inherit}
.sp-section-body{display:flex;flex-direction:column;gap:24px;color:#0f172a;font-size:15px;line-height:1.7;align-items:center}
.sp-section-body > *{width:100%;max-width:880px}

/* Element styles (flow blocks; no absolute positioning) */
.sp-text{font-size:15px;line-height:1.7;color:inherit}
.sp-image{margin:0;display:flex;justify-content:center}
.sp-image img{box-shadow:0 6px 20px rgba(0,0,0,.18);max-height:540px}
.sp-html{font-size:15px;line-height:1.7;color:inherit}
.sp-html *{max-width:100%}
.sp-html img{max-width:100%;height:auto;border-radius:8px}

/* Video / Avatar — keep within reasonable bounds (max 720px wide on desktop) */
.sp-video,.sp-audio{display:flex;flex-direction:column;gap:8px;max-width:720px;margin:0 auto}
.sp-video video{width:100%;max-width:720px;max-height:480px;border-radius:8px;background:#000;display:block}
.sp-audio audio{width:100%;border-radius:8px;background:#0f172a}
.sp-video-label,.sp-audio-label{font-weight:700;color:#0a2540;font-size:14px}
.sp-section.sp-dark .sp-video-label,
.sp-section.sp-dark .sp-audio-label{color:#facc15}

.sp-interactive{position:relative;background:#fef9c3;border-radius:12px;padding:18px;border:3px solid #facc15;transition:all .3s;box-shadow:0 4px 16px rgba(250,204,21,.25)}
.sp-interactive[data-completed="true"]:not(.sp-quiz):not(.sp-scenario){border-color:#84cc16;background:#f7fee7;box-shadow:0 2px 8px rgba(132,204,22,.2)}
.sp-interactive[data-completed="true"]::after{content:"✓";position:absolute;top:8px;right:12px;color:#fff;background:#84cc16;font-weight:700;font-size:16px;width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;z-index:10;box-shadow:0 2px 6px rgba(132,204,22,.4)}

.sp-audio-hint,.sp-video-hint,.sp-html-hint{display:inline-block;background:#0a2540;color:#facc15;padding:6px 12px;border-radius:999px;font-size:11px;font-weight:700;letter-spacing:.5px;text-transform:uppercase;align-self:flex-start;margin-top:4px}
.sp-interactive[data-completed="true"] .sp-audio-hint,
.sp-interactive[data-completed="true"] .sp-video-hint,
.sp-interactive[data-completed="true"] .sp-html-hint{display:none}

/* Avatar HeyGen — sem card amarelo, fundo transparente para misturar com o background da slide */
.sp-avatar-wrap{position:relative}
.sp-avatar-wrap[data-completed="true"]::after{content:"✓";position:absolute;top:0;right:8px;color:#fff;background:#84cc16;font-weight:700;font-size:14px;width:24px;height:24px;border-radius:50%;display:flex;align-items:center;justify-content:center;z-index:10;box-shadow:0 2px 6px rgba(132,204,22,.4)}
.sp-avatar-wrap[data-completed="true"] .sp-avatar-hint{display:none}
.sp-avatar-wrap video{background:transparent !important}

/* Timeline (auto-play sequencial: respeita startTime/endTime de cada elemento) */
.sp-element-timed{opacity:0;transform:translateY(20px);transition:opacity .5s ease,transform .5s ease;will-change:opacity,transform}
.sp-element-timed.sp-revealed{opacity:1;transform:translateY(0)}
.sp-element-timed.sp-hidden{opacity:0;transform:translateY(-10px);pointer-events:none}
.sp-timeline-gate{display:flex;flex-direction:column;align-items:center;gap:8px;padding:14px 18px}
.sp-timeline-progress{width:100%;height:6px;background:rgba(0,0,0,.08);border-radius:999px;overflow:hidden}
.sp-timeline-progress-bar{height:100%;background:linear-gradient(90deg,#6366f1,#ec4899);width:0%;transition:width .15s linear;border-radius:999px}
.sp-timeline-hint{font-size:11px;color:inherit;opacity:.7;font-style:italic}
.sp-timeline-gate[data-completed="true"]{background:#dcfce7 !important;border-color:#84cc16 !important}
.sp-timeline-gate[data-completed="true"] .sp-timeline-hint{color:#15803d;opacity:1;font-style:normal;font-weight:600}
.sp-timeline-gate[data-completed="true"] .sp-timeline-hint::before{content:"✓ "}

.sp-quiz{text-align:center;background:linear-gradient(135deg,#1e3a8a 0%,#2563eb 100%)!important;color:#fff!important;border-color:#3b82f6!important;padding:24px}
.sp-quiz[data-completed="true"]{background:#0f5132!important;border-color:#84cc16!important;color:#dcfce7!important}
.sp-quiz-icon{font-size:42px;margin-bottom:10px}
.sp-quiz-title{font-size:20px;margin-bottom:6px;color:inherit}
.sp-quiz-meta{font-size:13px;opacity:.85;margin-bottom:14px;color:inherit}
.sp-quiz-body{margin-top:18px;text-align:left;background:#fff;color:#0f172a;border-radius:8px;padding:18px}
.sp-quiz-body[hidden]{display:none}
.sp-quiz-opt:hover{border-color:#2563eb!important;background:#eff6ff}

.sp-scenario{text-align:center;background:linear-gradient(135deg,#7c2d12 0%,#ea580c 100%)!important;color:#fff!important;border-color:#fb923c!important;padding:24px}
.sp-scenario[data-completed="true"]{background:linear-gradient(135deg,#14532d 0%,#16a34a 100%)!important;border-color:#84cc16!important;color:#dcfce7!important}
.sp-scenario h3,.sp-scenario p{color:inherit;margin:8px 0}
.sp-scenario h3{font-size:20px}
.sp-scenario p{font-size:13px;opacity:.92}
.sp-scenario-icon{font-size:42px}

.sp-simulator{padding:8px;background:#fff;border-color:#cbd5e1}
.sp-simulator-label{font-weight:700;color:#1e3a8a;font-size:14px;margin-bottom:8px}

.sp-btn{display:inline-block;padding:10px 28px;border-radius:8px;border:0;cursor:pointer;font-weight:600;font-size:14px;transition:transform .15s,box-shadow .15s}
.sp-btn:hover{transform:translateY(-1px);box-shadow:0 6px 16px rgba(0,0,0,.2)}
.sp-btn-primary{background:#facc15;color:#0a2540}
.sp-btn-primary:hover{background:#fbbf24}
.sp-btn-ghost{background:transparent;color:#fff;border:2px solid #fff}

/* ---- next chevron ---- */
.sp-next-btn{
  position:fixed;right:18px;bottom:24px;z-index:60;
  width:56px;height:56px;border-radius:50%;border:0;cursor:pointer;
  background:#facc15;color:#0a2540;
  display:flex;align-items:center;justify-content:center;
  box-shadow:0 10px 28px rgba(0,0,0,.45);
}
.sp-next-btn::before{
  content:"";position:absolute;inset:-4px;border-radius:50%;
  background:transparent;border:3px solid rgba(250,204,21,.5);
  animation:sp-pulse-ring 2s ease-in-out infinite;pointer-events:none;
}
.sp-next-btn:hover{background:#fbbf24;transform:scale(1.06)}
.sp-next-btn[hidden]{display:none}
@keyframes sp-pulse-ring{0%,100%{transform:scale(1);opacity:.7}50%{transform:scale(1.18);opacity:0}}

/* ---- end card ---- */
.sp-end-card .sp-section-inner{background:linear-gradient(135deg,#16a34a,#84cc16);color:#fff;text-align:center;padding:60px 40px}
.sp-end-icon{font-size:72px;margin-bottom:12px}
.sp-end-card h2{font-size:32px;margin-bottom:8px}
.sp-end-card p{font-size:15px;opacity:.95}
.sp-end-inner{align-items:center;text-align:center}

/* ---- responsive ---- */
@media (max-width: 640px){
  .sp-section{padding:30px 8px}
  .sp-section-inner{padding:30px 22px;border-radius:10px}
  .sp-section-title{font-size:24px;margin-bottom:18px}
  .sp-title{font-size:11px}
  .sp-next-btn{right:12px;bottom:16px;width:48px;height:48px}
  .sp-interactive{padding:16px}
  .sp-section-body{font-size:14px}
}
@media (min-width: 1600px){
  .sp-section-inner{max-width:1180px}
}
"""

# --------------------------------------------------------------------------- JS Runtime

_JS = """
(function(){
  var SECTIONS = __SECTIONS_INDEX__;
  var SCORM_MODE = __SCORM_MODE__;
  var state = {
    currentIndex: 0,
    unlocked: {0: true},
    completed: {},
    quizScores: {},
    interactionIdx: 0,
  };

  function $(sel, root){ return (root||document).querySelector(sel); }
  function $$(sel, root){ return Array.prototype.slice.call((root||document).querySelectorAll(sel)); }

  // --- SCORM helpers (no-op when SCORM_MODE=false or window.SCORM missing) ---
  function scormSaveState(){
    if (!SCORM_MODE || !window.SCORM || !window.SCORM.api) return;
    try {
      window.SCORM.saveSuspend({
        unlocked: state.unlocked,
        completed: state.completed,
        quizScores: state.quizScores,
        currentIndex: state.currentIndex,
      });
      window.SCORM.setLocation(String(state.currentIndex));
      window.SCORM.commit();
    } catch (e) {}
  }
  function scormReportQuiz(quizId, response, correct, qIdx, qText){
    if (!SCORM_MODE || !window.SCORM || !window.SCORM.api) return;
    try {
      window.SCORM.recordInteraction(quizId + ':q' + qIdx, qText, response, correct);
    } catch (e) {}
  }
  function scormUpdateScore(){
    if (!SCORM_MODE || !window.SCORM || !window.SCORM.api) return;
    var totalCorrect = 0, totalQuestions = 0;
    Object.keys(state.quizScores).forEach(function(k){
      totalCorrect += state.quizScores[k].correct;
      totalQuestions += state.quizScores[k].total;
    });
    var raw = totalQuestions > 0 ? Math.round((totalCorrect/totalQuestions)*100) : 0;
    try { window.SCORM.setScore(raw, 100, 0); } catch (e) {}
  }
  function scormMarkComplete(){
    if (!SCORM_MODE || !window.SCORM || !window.SCORM.api) return;
    var allUnlocked = Object.keys(state.unlocked).length >= (SECTIONS.length + 1);
    var quizzesPassed = Object.keys(state.quizScores).every(function(k){
      return state.quizScores[k].pct >= 80;
    });
    var passed = allUnlocked && (Object.keys(state.quizScores).length === 0 || quizzesPassed);
    try {
      window.SCORM.complete(passed);
      window.SCORM.commit();
    } catch (e) {}
  }
  function scormRestoreState(){
    if (!SCORM_MODE || !window.SCORM || !window.SCORM.api) return false;
    try {
      var data = window.SCORM.getSuspend();
      if (!data) return false;
      Object.keys(data.unlocked || {}).forEach(function(k){
        var idx = parseInt(k, 10);
        if (!isNaN(idx)) {
          state.unlocked[idx] = true;
          var sec = $('.sp-section[data-index="'+idx+'"]');
          if (sec) { sec.removeAttribute('data-locked'); sec.classList.add('unlocked'); }
        }
      });
      state.completed = data.completed || {};
      state.quizScores = data.quizScores || {};
      // Mark interactives data-completed=true based on sections that were completed
      Object.keys(state.completed).forEach(function(k){
        var sec = $('.sp-section[data-index="'+k+'"]');
        if (!sec) return;
        $$('[data-required="true"]', sec).forEach(function(el){
          el.dataset.completed = 'true';
        });
      });
      var resumeIdx = data.currentIndex != null ? parseInt(data.currentIndex, 10) : 0;
      if (!isNaN(resumeIdx) && state.unlocked[resumeIdx]) {
        state.currentIndex = resumeIdx;
        setTimeout(function(){
          var sec = $('.sp-section[data-index="'+resumeIdx+'"]');
          if (sec) sec.scrollIntoView({behavior:'instant', block:'start'});
        }, 100);
      }
      return true;
    } catch (e) { return false; }
  }

  function updateProgress(){
    var unlockedCount = Object.keys(state.unlocked).length;
    var pct = Math.min(100, Math.round((unlockedCount-1) / Math.max(1, SECTIONS.length) * 100));
    if (state.currentIndex >= SECTIONS.length) pct = 100;
    var fill = $('.sp-progress-fill');
    if (fill) fill.style.width = pct + '%';
  }

  function buildDrawer(){
    var ul = $('.sp-drawer-list');
    if (!ul) return;
    ul.innerHTML = '';
    SECTIONS.forEach(function(item){
      var li = document.createElement('li');
      li.dataset.index = item.index;
      li.textContent = item.title;
      li.dataset.testid = 'sp-drawer-item-' + item.index;
      if (state.unlocked[item.index]) li.classList.add('unlocked');
      else li.classList.add('locked');
      if (state.completed[item.index]) li.classList.add('completed');
      if (state.currentIndex === item.index) li.classList.add('active');
      li.addEventListener('click', function(){
        if (!state.unlocked[item.index]) return;
        SP.gotoSection(item.index);
      });
      ul.appendChild(li);
    });
  }

  function unlockSection(idx){
    state.unlocked[idx] = true;
    var sec = $('.sp-section[data-index="'+idx+'"]');
    if (sec){
      sec.removeAttribute('data-locked');
      sec.classList.add('unlocked');
      // If this section has a timeline, start it now (it might already be in
      // viewport and the IntersectionObserver may not re-fire since intersectionRatio
      // didn't change — only data-locked did).
      if (sec.querySelector('.sp-timeline-gate')) {
        setTimeout(function(){ startSectionTimeline(sec); }, 200);
      }
    }
    buildDrawer();
    updateProgress();
    scormSaveState();
  }

  function getCurrentSection(){
    return $('.sp-section[data-index="'+state.currentIndex+'"]');
  }

  function isSectionComplete(idx){
    var sec = $('.sp-section[data-index="'+idx+'"]');
    if (!sec) return false;
    var pending = $$('[data-required="true"]', sec).filter(function(el){
      return el.dataset.completed !== 'true';
    });
    return pending.length === 0;
  }

  function updateNextButton(){
    var btn = $('.sp-next-btn');
    if (!btn) return;
    var idx = state.currentIndex;
    if (idx >= SECTIONS.length){ btn.hidden = true; return; }
    if (isSectionComplete(idx)){
      btn.hidden = false;
    } else {
      btn.hidden = true;
    }
  }

  // Detect which section is currently in viewport (for drawer "active" + next button gating)
  function detectActiveSection(){
    var sections = $$('.sp-section[data-index]');
    var midline = window.innerHeight * 0.4 + window.scrollY;
    var current = state.currentIndex;
    sections.forEach(function(sec){
      var top = sec.offsetTop;
      var bottom = top + sec.offsetHeight;
      if (top <= midline && bottom > midline){
        var idx = parseInt(sec.dataset.index, 10);
        if (idx !== current && state.unlocked[idx]){
          state.currentIndex = idx;
          buildDrawer();
        }
      }
    });
    updateNextButton();
  }

  // ---- public API
  window.SP = {
    markPlayed: function(el){
      if (!el) return;
      el.dataset.completed = 'true';
      this.checkSectionCompletion(el);
    },
    markClicked: function(el){
      if (!el) return;
      el.dataset.completed = 'true';
      this.checkSectionCompletion(el);
    },
    checkSectionCompletion: function(el){
      var sec = el.closest('.sp-section');
      if (!sec) return;
      var idx = parseInt(sec.dataset.index, 10);
      if (isSectionComplete(idx)){
        state.completed[idx] = true;
        buildDrawer();
        updateNextButton();
        scormSaveState();
      }
    },
    advance: function(){
      var idx = state.currentIndex;
      var nextIdx = idx + 1;
      // If end-card section
      if (nextIdx > SECTIONS.length){ return; }
      state.currentIndex = nextIdx;          // update BEFORE unlockSection so SCORM saves the new location
      unlockSection(nextIdx);
      var nextSec = $('.sp-section[data-index="'+nextIdx+'"]');
      if (nextSec){ nextSec.scrollIntoView({behavior:'smooth', block:'start'}); }
      // when reaching end card, dispatch course-completed + mark SCORM completed
      if (nextIdx >= SECTIONS.length){
        scormMarkComplete();
        try {
          window.dispatchEvent(new CustomEvent('sp:course-completed', {
            detail: { quizScores: state.quizScores }
          }));
        } catch(e){}
        // Gamification: trigger course completion badges + final summary
        try {
          if (window.Gamification && typeof Gamification.onCourseComplete === 'function') {
            Gamification.onCourseComplete();
          }
        } catch(e){}
      }
    },
    gotoSection: function(idx){
      if (!state.unlocked[idx]) return;
      state.currentIndex = idx;
      var sec = $('.sp-section[data-index="'+idx+'"]');
      if (sec){ sec.scrollIntoView({behavior:'smooth', block:'start'}); }
      this.toggleDrawer(false);
      buildDrawer();
      updateNextButton();
    },
    toggleDrawer: function(force){
      var d = $('.sp-drawer');
      if (!d) return;
      var isOpen = d.dataset.open === 'true';
      var nextOpen = (typeof force === 'boolean') ? force : !isOpen;
      d.dataset.open = nextOpen ? 'true' : 'false';
      d.setAttribute('aria-hidden', nextOpen ? 'false' : 'true');
    },
    startScenario: function(scenarioEl){
      try {
        var data = JSON.parse(scenarioEl.dataset.scenario || '{}');
      } catch(e) { return; }
      var nodes = data.nodes || [];
      if (!nodes.length) { SP.markClicked(scenarioEl); return; }
      var nodeMap = {};
      nodes.forEach(function(n){ nodeMap[n.id] = n; });
      // Hide intro, show play area
      var intro = scenarioEl.querySelector('.sp-scenario-intro');
      if (intro) intro.hidden = true;
      var play = scenarioEl.querySelector('.sp-scenario-play');
      if (!play) return;
      play.hidden = false;
      play.style.background = '#fff';
      play.style.color = '#0f172a';
      play.style.borderRadius = '8px';
      play.style.padding = '20px';
      play.style.textAlign = 'left';
      var totalPoints = 0;
      var maxPoints = 0;
      var optimalChoices = 0;
      var totalChoices = 0;
      // Compute max possible points (assume optimal at every node)
      nodes.forEach(function(n){
        if (n.choices && n.choices.length) {
          var maxP = Math.max.apply(null, n.choices.map(function(c){ return c.points || 0; }));
          maxPoints += maxP;
        }
      });
      function renderNode(nodeId){
        var n = nodeMap[nodeId];
        if (!n) return;
        var html = '';
        if (n.title) {
          html += '<h4 style="margin:0 0 10px 0;font-size:18px;color:#1e3a8a">' + escapeHtml(n.title) + '</h4>';
        }
        if (n.character_speaking) {
          html += '<div style="font-size:12px;font-weight:700;color:#7c2d12;text-transform:uppercase;letter-spacing:.5px;margin-bottom:8px">💬 ' + escapeHtml(n.character_speaking) + '</div>';
        }
        if (n.narrative) {
          html += '<div style="font-size:14px;line-height:1.6;margin-bottom:16px;white-space:pre-wrap">' + escapeHtml(n.narrative) + '</div>';
        }
        if (n.is_ending) {
          var endLabel = n.ending_type === 'positive' ? '🎉 Final Positivo' : (n.ending_type === 'negative' ? '⚠️ Final com Aprendizado' : '🏁 Final');
          var endColor = n.ending_type === 'positive' ? '#16a34a' : (n.ending_type === 'negative' ? '#dc2626' : '#2563eb');
          var pct = maxPoints > 0 ? Math.round((totalPoints/maxPoints)*100) : 100;
          html += '<div style="background:' + endColor + ';color:#fff;padding:14px;border-radius:8px;text-align:center;font-weight:700;margin-bottom:10px">'
                + endLabel + ' • Score: ' + totalPoints + '/' + maxPoints + ' (' + pct + '%)'
                + '</div>';
          if (n.score) {
            html += '<div style="font-size:13px;color:#64748b;text-align:center">Avaliação do nó: ' + escapeHtml(String(n.score)) + '</div>';
          }
          html += '<button type="button" class="sp-btn sp-btn-primary" style="margin-top:14px;width:100%" '
                + 'onclick="window.SP.markClicked(this.closest(&quot;.sp-scenario&quot;))">'
                + '✓ Concluir cenário e liberar próxima seção</button>';
          play.innerHTML = html;
          // Track scenario completion stats for SCORM
          state.quizScores[scenarioEl.dataset.interactiveId] = {
            correct: optimalChoices, total: totalChoices, pct: pct
          };
          scormUpdateScore();
          scormSaveState();
          // Gamification: trigger scenario badges + feedback modal
          try {
            if (window.Gamification && typeof Gamification.onScenarioComplete === 'function') {
              var scenarioTitle = (scenarioEl.querySelector('.sp-scenario-title') || {}).textContent || 'Cenário';
              Gamification.onScenarioComplete(pct, scenarioTitle);
            }
          } catch(e){}
        } else if (n.choices && n.choices.length) {
          html += '<div style="font-weight:600;font-size:13px;color:#475569;margin-bottom:10px">Qual sua decisão?</div>';
          html += '<div class="sp-scenario-choices" style="display:flex;flex-direction:column;gap:10px">';
          n.choices.forEach(function(ch, ci){
            html += '<button type="button" class="sp-scenario-choice" data-choice-idx="' + ci + '" '
                  + 'style="text-align:left;padding:14px 16px;border:2px solid #cbd5e1;background:#f8fafc;border-radius:8px;cursor:pointer;font-size:13px;line-height:1.5;color:#0f172a;transition:all .15s">'
                  + '<span style="display:inline-block;background:#1e3a8a;color:#fff;width:22px;height:22px;border-radius:50%;text-align:center;font-weight:700;margin-right:8px;font-size:11px;line-height:22px">' + (ci+1) + '</span>'
                  + escapeHtml(ch.text)
                  + '</button>';
          });
          html += '</div>';
          // Tutor IA hint button — only when AiTutor is loaded (admin toggled enabled)
          if (window.AiTutor) {
            html += '<button type="button" class="sp-scenario-hint" '
                  + 'style="margin-top:14px;display:inline-flex;align-items:center;gap:6px;padding:8px 14px;background:rgba(99,102,241,.12);color:#4f46e5;border:1px dashed #818cf8;border-radius:999px;font-size:12px;font-weight:600;cursor:pointer">'
                  + '💡 Pedir dica do Tutor IA</button>';
          }
          play.innerHTML = html;
          // Wire hint button (contextualized prompt for current node)
          var hintBtn = play.querySelector('.sp-scenario-hint');
          if (hintBtn) {
            hintBtn.addEventListener('click', function(){
              try {
                var nodeTitle = n.title || '';
                var narrative = (n.narrative || '').substring(0, 400);
                var choicesText = (n.choices || []).map(function(c, i){ return (i+1) + ') ' + (c.text || ''); }).join(' | ');
                var prompt = 'Estou em um cenário interativo "' + (scenarioEl.querySelector('.sp-scenario-title') || {}).textContent + '"'
                           + (nodeTitle ? ', no nó "' + nodeTitle + '"' : '')
                           + '. Contexto: ' + narrative
                           + '. Minhas opções são: ' + choicesText
                           + '. Pode me ajudar a refletir sobre o que considerar antes de escolher? (não me dê a resposta direta)';
                if (typeof AiTutor.toggle === 'function') AiTutor.toggle();
                var input = document.getElementById('tutor-input');
                if (input) { input.value = prompt; input.focus(); }
              } catch(e) {}
            });
          }
          play.querySelectorAll('.sp-scenario-choice').forEach(function(btn, ci){
            btn.addEventListener('mouseenter', function(){ btn.style.borderColor='#2563eb'; btn.style.background='#eff6ff'; });
            btn.addEventListener('mouseleave', function(){ btn.style.borderColor='#cbd5e1'; btn.style.background='#f8fafc'; });
            btn.addEventListener('click', function(){
              var ch = n.choices[ci];
              totalChoices++;
              if (ch.is_optimal) optimalChoices++;
              totalPoints += (ch.points || 0);
              showFeedback(ch, n);
            });
          });
        } else {
          // Node has no choices and no ending — fallback
          html += '<button type="button" class="sp-btn sp-btn-primary" '
                + 'onclick="window.SP.markClicked(this.closest(&quot;.sp-scenario&quot;))">Encerrar cenário</button>';
          play.innerHTML = html;
        }
      }
      function showFeedback(choice, fromNode){
        var bgColor = choice.is_optimal ? '#dcfce7' : '#fef2f2';
        var borderColor = choice.is_optimal ? '#16a34a' : '#dc2626';
        var textColor = choice.is_optimal ? '#15803d' : '#991b1b';
        var icon = choice.is_optimal ? '✅' : '⚠️';
        var label = choice.is_optimal ? 'Excelente escolha!' : 'Pense bem nas consequências:';
        var html = '<div style="background:' + bgColor + ';border:2px solid ' + borderColor + ';color:' + textColor + ';padding:16px;border-radius:8px;margin-bottom:14px">'
                 + '<div style="font-weight:700;margin-bottom:6px">' + icon + ' ' + label + ' (+' + (choice.points||0) + ' pts)</div>'
                 + '<div style="font-size:13px;line-height:1.5">' + escapeHtml(choice.feedback || '') + '</div>'
                 + '</div>';
        // Proactive Tutor IA button after sub-optimal choice (only if AiTutor loaded)
        var showTutorRescue = !choice.is_optimal && window.AiTutor;
        if (showTutorRescue) {
          html += '<button type="button" class="sp-scenario-rescue" '
                + 'style="width:100%;margin-bottom:12px;padding:10px 14px;background:linear-gradient(135deg,#6366f1,#8b5cf6);color:#fff;border:0;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:8px">'
                + '🤖 Quer entender melhor por quê?</button>';
        }
        var nextId = choice.next_node_id;
        if (nextId && nodeMap[nextId]) {
          html += '<button type="button" class="sp-btn sp-btn-primary" style="width:100%" id="sp-scenario-continue">Continuar →</button>';
          play.innerHTML = html;
          wireRescueBtn(choice);
          play.querySelector('#sp-scenario-continue').addEventListener('click', function(){
            renderNode(nextId);
            play.scrollIntoView({behavior:'smooth', block:'nearest'});
          });
        } else {
          // No next node — treat as ending
          var pct = maxPoints > 0 ? Math.round((totalPoints/maxPoints)*100) : 100;
          html += '<div style="background:#2563eb;color:#fff;padding:14px;border-radius:8px;text-align:center;font-weight:700;margin-bottom:10px">'
                + '🏁 Cenário concluído • Score: ' + totalPoints + '/' + maxPoints + ' (' + pct + '%)'
                + '</div>';
          html += '<button type="button" class="sp-btn sp-btn-primary" style="width:100%" '
                + 'onclick="window.SP.markClicked(this.closest(&quot;.sp-scenario&quot;))">'
                + '✓ Liberar próxima seção</button>';
          play.innerHTML = html;
          wireRescueBtn(choice);
          state.quizScores[scenarioEl.dataset.interactiveId] = { correct: optimalChoices, total: totalChoices, pct: pct };
          scormUpdateScore();
          scormSaveState();
          // Gamification: trigger scenario badges + feedback modal (fallback ending — no next_node_id)
          try {
            if (window.Gamification && typeof Gamification.onScenarioComplete === 'function') {
              var scenarioTitle = (scenarioEl.querySelector('.sp-scenario-title') || {}).textContent || 'Cenário';
              Gamification.onScenarioComplete(pct, scenarioTitle);
            }
          } catch(e){}
        }
      }
      function escapeHtml(s){
        return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
      }
      function wireRescueBtn(choice){
        var btn = play.querySelector('.sp-scenario-rescue');
        if (!btn) return;
        btn.addEventListener('click', function(){
          try {
            var scTitle = (scenarioEl.querySelector('.sp-scenario-title') || {}).textContent || 'cenário';
            var prompt = 'Em um cenário sobre "' + scTitle + '", eu escolhi: "' + (choice.text || '') + '". '
                       + 'O sistema disse que essa não é a melhor escolha. '
                       + (choice.feedback ? 'O feedback foi: "' + choice.feedback + '". ' : '')
                       + 'Pode me ajudar a entender por que essa decisão é problemática e quais princípios eu deveria considerar para escolher melhor da próxima vez?';
            if (typeof AiTutor.toggle === 'function') AiTutor.toggle();
            var input = document.getElementById('tutor-input');
            if (input) { input.value = prompt; input.focus(); }
          } catch(e){}
        });
      }
      // Start at the first node
      renderNode(nodes[0].id);
      play.scrollIntoView({behavior:'smooth', block:'nearest'});
    },
    startQuiz: function(quizEl){
      var qs = JSON.parse(quizEl.dataset.questions || '[]');
      var body = quizEl.querySelector('.sp-quiz-body');
      var startBtn = quizEl.querySelector('.sp-btn-primary');
      if (startBtn) startBtn.style.display = 'none';
      if (!body) return;
      body.hidden = false;
      var html = '<form class="sp-quiz-form">';
      qs.forEach(function(q, qi){
        html += '<fieldset class="sp-quiz-question" data-q-idx="'+qi+'" style="margin-bottom:18px;border:0;padding:0">';
        html += '<legend style="font-weight:600;margin-bottom:10px;font-size:15px">'+(qi+1)+'. '+(q.text||q.question||'')+'</legend>';
        (q.options||[]).forEach(function(opt, oi){
          var optText = (typeof opt === 'string') ? opt : (opt.text || opt.label || '');
          html += '<label class="sp-quiz-opt" data-opt-idx="'+oi+'" style="display:block;padding:8px 12px;margin:4px 0;cursor:pointer;border:2px solid #e2e8f0;border-radius:6px;transition:all .15s">'
                + '<input type="radio" name="q'+qi+'" value="'+oi+'" style="margin-right:8px"> '+optText
                + '</label>';
        });
        if (q.explanation) {
          html += '<div class="sp-quiz-explanation" hidden style="margin-top:8px;padding:10px 14px;border-left:4px solid #2563eb;background:#eff6ff;font-size:13px;color:#1e3a8a"><strong>💡 Explicação:</strong> '+q.explanation+'</div>';
        }
        html += '</fieldset>';
      });
      html += '<button type="button" class="sp-btn sp-btn-primary sp-quiz-submit">Enviar Respostas</button>';
      html += '<div class="sp-quiz-result" style="margin-top:14px;padding:14px;border-radius:8px;font-weight:700;font-size:16px;text-align:center"></div>';
      html += '</form>';
      body.innerHTML = html;
      var submit = body.querySelector('.sp-quiz-submit');
      var result = body.querySelector('.sp-quiz-result');
      submit.addEventListener('click', function(){
        var correct = 0;
        qs.forEach(function(q, qi){
          var selRadio = body.querySelector('input[name="q'+qi+'"]:checked');
          var fieldset = body.querySelector('.sp-quiz-question[data-q-idx="'+qi+'"]');
          var labels = fieldset.querySelectorAll('.sp-quiz-opt');
          var pickedIdx = selRadio ? parseInt(selRadio.value, 10) : -1;
          var qCorrectIdx = -1;
          (q.options||[]).forEach(function(opt, oi){
            var isThisCorrect = (typeof opt === 'object' && opt && opt.correct) || oi === q.correctAnswer || oi === q.correctIndex;
            if (isThisCorrect) qCorrectIdx = oi;
          });
          // Visual feedback per option
          labels.forEach(function(lbl, oi){
            lbl.style.cursor = 'default';
            var input = lbl.querySelector('input');
            if (input) input.disabled = true;
            if (oi === qCorrectIdx) {
              // The correct answer — always green
              lbl.style.borderColor = '#16a34a';
              lbl.style.background = '#f0fdf4';
              lbl.style.color = '#15803d';
              lbl.style.fontWeight = '600';
              lbl.innerHTML += ' <span style="color:#16a34a;font-weight:700;margin-left:6px">✓ Correta</span>';
            } else if (oi === pickedIdx) {
              // Picked but wrong — red
              lbl.style.borderColor = '#dc2626';
              lbl.style.background = '#fef2f2';
              lbl.style.color = '#991b1b';
              lbl.innerHTML += ' <span style="color:#dc2626;font-weight:700;margin-left:6px">✗ Sua resposta</span>';
            } else {
              lbl.style.opacity = '0.55';
            }
          });
          // Show explanation if available
          var exp = fieldset.querySelector('.sp-quiz-explanation');
          if (exp) exp.hidden = false;
          var isCorrect = (pickedIdx === qCorrectIdx);
          if (isCorrect) correct++;
          // Tutor IA rescue: if wrong answer + AiTutor loaded, offer detailed explanation per question
          if (!isCorrect && window.AiTutor) {
            var tutorBtn = document.createElement('button');
            tutorBtn.type = 'button';
            tutorBtn.className = 'sp-quiz-tutor';
            tutorBtn.innerHTML = '🤖 Pedir explicação detalhada ao Tutor IA';
            tutorBtn.style.cssText = 'margin-top:10px;padding:8px 14px;background:linear-gradient(135deg,#6366f1,#8b5cf6);color:#fff;border:0;border-radius:8px;font-size:12px;font-weight:600;cursor:pointer;display:inline-flex;align-items:center;gap:6px';
            tutorBtn.addEventListener('click', function(){
              try {
                var qLabel = (q.text || q.question || '').substring(0, 400);
                var pickedText = (q.options && q.options[pickedIdx]) ? (typeof q.options[pickedIdx] === 'object' ? q.options[pickedIdx].text : q.options[pickedIdx]) : '(em branco)';
                var correctText = (q.options && q.options[qCorrectIdx]) ? (typeof q.options[qCorrectIdx] === 'object' ? q.options[qCorrectIdx].text : q.options[qCorrectIdx]) : '';
                var prompt = 'Em um quiz, a pergunta foi: "' + qLabel + '". '
                           + 'Eu respondi: "' + pickedText + '" (errei). '
                           + 'A resposta correta era: "' + correctText + '". '
                           + (q.explanation ? 'A explicação curta diz: "' + q.explanation + '". ' : '')
                           + 'Pode me explicar de forma mais detalhada por que minha resposta está incorreta e o raciocínio para chegar na resposta certa?';
                if (typeof AiTutor.toggle === 'function') AiTutor.toggle();
                var input = document.getElementById('tutor-input');
                if (input) { input.value = prompt; input.focus(); }
              } catch(e){}
            });
            fieldset.appendChild(tutorBtn);
          }
          // SCORM cmi.interactions tracking per question
          var qText = (q.text || q.question || '').substring(0, 250);
          scormReportQuiz(quizEl.dataset.interactiveId, String(pickedIdx), isCorrect, qi, qText);
        });
        var total = qs.length || 1;
        var pct = Math.round((correct/total)*100);
        state.quizScores[quizEl.dataset.interactiveId] = { correct: correct, total: total, pct: pct };
        // Final result banner
        var passed = pct >= 80;
        result.textContent = 'Você acertou ' + correct + ' de ' + total + ' (' + pct + '%) — ' +
          (passed ? '🎉 Aprovado!' : 'Revise as questões em vermelho');
        result.style.background = passed ? '#dcfce7' : '#fef2f2';
        result.style.color = passed ? '#15803d' : '#991b1b';
        result.style.border = '2px solid ' + (passed ? '#16a34a' : '#dc2626');
        SP.markClicked(quizEl);
        scormUpdateScore();
        scormSaveState();
        // Gamification: trigger quiz badges + feedback modal
        try {
          if (window.Gamification && typeof Gamification.onQuizComplete === 'function') {
            Gamification.onQuizComplete(pct, total, correct);
          }
        } catch(e){}
        submit.disabled = true;
        submit.style.display = 'none';
      });
    }
  };

  // ----- Timeline engine: respects per-element startTime/endTime -----
  // When a section enters viewport, we play through the timeline:
  // each .sp-element-timed gets `.sp-revealed` at its startTime (fade-in)
  // and optionally `.sp-hidden` at its endTime. The synthetic .sp-timeline-gate
  // updates a progress bar and is auto-completed when the timeline finishes.
  var timelinePlayed = {};
  function startSectionTimeline(sec){
    var idx = sec.dataset.index;
    if (timelinePlayed[idx]) return;
    var gate = sec.querySelector('.sp-timeline-gate');
    if (!gate) return;
    timelinePlayed[idx] = true;
    var timed = Array.from(sec.querySelectorAll('.sp-element-timed'));
    if (!timed.length) {
      // Section was marked as having timeline but no timed elements survived render.
      // Just mark the gate as completed.
      SP.markClicked(gate);
      return;
    }
    var totalDuration = parseFloat(gate.dataset.sectionDuration || '0') || 0;
    var startedAt = Date.now();
    timed.forEach(function(el){
      var st = parseFloat(el.dataset.startTime || '0') || 0;
      var et = parseFloat(el.dataset.endTime || '0') || 0;
      // Reveal at startTime (or immediately if 0)
      setTimeout(function(){ el.classList.add('sp-revealed'); }, Math.max(0, st * 1000));
      // Hide at endTime if defined
      if (et > 0 && et > st) {
        setTimeout(function(){ el.classList.add('sp-hidden'); }, et * 1000);
      }
    });
    // Update progress bar every 100ms until end
    var bar = gate.querySelector('.sp-timeline-progress-bar');
    var progressTimer = setInterval(function(){
      var elapsed = (Date.now() - startedAt) / 1000;
      var pct = totalDuration > 0 ? Math.min(100, (elapsed / totalDuration) * 100) : 100;
      if (bar) bar.style.width = pct.toFixed(1) + '%';
      if (elapsed >= totalDuration) {
        clearInterval(progressTimer);
        if (bar) bar.style.width = '100%';
        SP.markClicked(gate);
      }
    }, 100);
  }

  function observeTimelines(){
    var sectionsWithTimeline = $$('.sp-section').filter(function(sec){
      return sec.querySelector('.sp-timeline-gate');
    });
    if (!sectionsWithTimeline.length || typeof IntersectionObserver === 'undefined') return;
    var io = new IntersectionObserver(function(entries){
      entries.forEach(function(entry){
        if (entry.isIntersecting && entry.intersectionRatio >= 0.4) {
          var sec = entry.target;
          // Only play once unlocked (so the locked overlay doesn't trigger it)
          if (!sec.hasAttribute('data-locked')) {
            startSectionTimeline(sec);
          }
        }
      });
    }, { threshold: [0.4] });
    sectionsWithTimeline.forEach(function(sec){ io.observe(sec); });
  }

  document.addEventListener('DOMContentLoaded', function(){
    if (SCORM_MODE && window.SCORM) {
      try { window.SCORM.init(); } catch(e) {}
      scormRestoreState();
    }
    buildDrawer();
    updateProgress();
    updateNextButton();
    observeTimelines();
    window.addEventListener('scroll', detectActiveSection, {passive:true});
    document.addEventListener('click', function(){ setTimeout(updateNextButton, 50); }, true);
    if (SCORM_MODE && window.SCORM) {
      window.addEventListener('beforeunload', function(){
        try { window.SCORM.finish(); } catch(e){}
      });
    }
  });
})();
"""
