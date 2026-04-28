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


# --------------------------------------------------------------------------- element renderers


def _render_text_element(el: dict) -> str:
    content = el.get("content") or ""
    style = el.get("style") or {}
    css_parts = []
    for k, v in style.items():
        if v in (None, ""):
            continue
        css_parts.append(f"{_kebab(k)}:{_esc(v)}")
    style_attr = ";".join(css_parts)
    return (
        f'<div class="sp-text" style="{style_attr}">'
        f'{_safe_text_html(content)}'
        f'</div>'
    )


def _kebab(name: str) -> str:
    return re.sub(r"([A-Z])", r"-\1", name).lower()


def _safe_text_html(s: str) -> str:
    """Allow <br> and basic inline tags but escape everything else."""
    if s is None:
        return ""
    # Basic line-break preservation
    return re.sub(r"\r?\n", "<br>", _esc(s))


def _render_image_element(el: dict, project_id: str, assets_dir: str, base_url: str) -> str:
    src = el.get("src") or el.get("content") or ""
    src = _resolve_asset_url(src, project_id, assets_dir, base_url)
    alt = _esc(el.get("alt", ""))
    style = el.get("style") or {}
    radius = style.get("borderRadius", "8px")
    return (
        f'<figure class="sp-image">'
        f'<img src="{_esc(src)}" alt="{alt}" loading="lazy" '
        f'style="border-radius:{_esc(radius)};max-width:100%;height:auto" />'
        f'</figure>'
    )


def _render_audio_element(el: dict, project_id: str, assets_dir: str, base_url: str, idx: int) -> str:
    src = el.get("src") or el.get("audioUrl") or el.get("content") or ""
    src = _resolve_asset_url(src, project_id, assets_dir, base_url)
    title = _esc(el.get("title", "Áudio"))
    return (
        f'<div class="sp-audio sp-interactive" data-interactive="audio" data-required="true" '
        f'data-interactive-id="audio-{idx}">'
        f'<div class="sp-audio-label">{title}</div>'
        f'<audio controls preload="metadata" src="{_esc(src)}" '
        f'onplay="window.SP&&SP.markPlayed(this.closest(\'.sp-interactive\'))"></audio>'
        f'<div class="sp-audio-hint">▶ Reproduza para liberar a próxima seção</div>'
        f'</div>'
    )


def _render_video_element(el: dict, project_id: str, assets_dir: str, base_url: str, idx: int) -> str:
    src = el.get("src") or el.get("videoUrl") or el.get("content") or ""
    src = _resolve_asset_url(src, project_id, assets_dir, base_url)
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


def _render_html_element(el: dict, project_id: str, assets_dir: str, base_url: str) -> str:
    raw = el.get("htmlContent") or el.get("content") or ""
    raw = _inline_assets_in_html(raw, project_id, assets_dir, base_url)
    # If the HTML contains <style>, <script>, <body>, or <html> tags, those would
    # leak into the course CSS scope and break the page layout (eg a simulator's
    # `body{display:flex;width:960px}` would shrink the whole single-page body).
    # Sandbox such complex HTML inside an iframe via srcdoc.
    has_global_styles = bool(re.search(r"<\s*(style|script|body|html|head)\b", raw, re.IGNORECASE))
    if has_global_styles:
        b64 = base64.b64encode(raw.encode("utf-8")).decode("ascii")
        # Pick a reasonable height — most legacy simulators target 540px
        # Iframe sandbox blocks click-bubbling to the parent, so we add an
        # explicit "Concluí esta interação" button OUTSIDE the iframe that the
        # user clicks after exploring the panel.
        return (
            f'<div class="sp-html sp-interactive" data-interactive="html" data-required="true">'
            f'<iframe sandbox="allow-scripts allow-same-origin allow-forms" loading="lazy" '
            f'src="data:text/html;base64,{b64}" '
            f'style="width:100%;min-height:540px;border:0;border-radius:8px;background:#fff;display:block"></iframe>'
            f'<button type="button" class="sp-btn sp-btn-primary sp-iframe-done" '
            f'onclick="window.SP&&SP.markClicked(this.closest(\'.sp-interactive\'))" '
            f'style="margin-top:12px;width:100%">'
            f'✓ Concluí a interação acima — liberar próxima seção'
            f'</button>'
            f'</div>'
        )
    # Heuristic: if the html contains a <button>, <details>, or [onclick] we mark
    # the whole block as an interactive that must be clicked at least once.
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


def _render_quiz_element(el: dict, slide_idx: int, el_idx: int, questions_lookup: Dict[str, dict]) -> str:
    cfg = el.get("quizConfig") or {}
    qids = cfg.get("questionIds") or []
    title = _esc(cfg.get("title", "Quiz"))
    # Normalize each question into the shape expected by the embedded JS:
    #   { id, text, options: [{ text, correct }] }
    # The DB schema uses 'alternatives' with 'isCorrect' — translate it here.
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
    # Escape for HTML attribute (handles ', ", &, <, > safely)
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


def _render_scenario_element(el: dict, slide_idx: int, el_idx: int) -> str:
    sd = el.get("scenarioData") or {}
    title = _esc(sd.get("title", "Cenário interativo"))
    desc = _esc(sd.get("description", ""))
    return (
        f'<div class="sp-scenario sp-interactive" data-interactive="scenario" data-required="true" '
        f'data-interactive-id="scenario-{slide_idx}-{el_idx}" '
        f'onclick="window.SP&&SP.markClicked(this)">'
        f'<div class="sp-scenario-icon">🎯</div>'
        f'<h3>{title}</h3>'
        f'<p>{desc}</p>'
        f'<button type="button" class="sp-btn sp-btn-primary">Iniciar Cenário</button>'
        f'</div>'
    )


def _render_simulator_element(el: dict, project_id: str, assets_dir: str, base_url: str, slide_idx: int, el_idx: int) -> str:
    """Simulators are rendered inline in an iframe/srcdoc. Sandbox blocks click
    bubbling, so we add an explicit 'concluí' button below the iframe."""
    sim_html = el.get("htmlContent") or el.get("content") or ""
    sim_html = _inline_assets_in_html(sim_html, project_id, assets_dir, base_url)
    sim_html_b64 = base64.b64encode(sim_html.encode("utf-8")).decode("ascii") if sim_html else ""
    return (
        f'<div class="sp-simulator sp-interactive" data-interactive="simulator" data-required="true" '
        f'data-interactive-id="simulator-{slide_idx}-{el_idx}">'
        f'<div class="sp-simulator-label">🎮 Simulador interativo</div>'
        f'<iframe sandbox="allow-scripts allow-same-origin allow-forms" loading="lazy" '
        f'src="data:text/html;base64,{sim_html_b64}" '
        f'style="width:100%;height:520px;border:0;border-radius:12px;background:#0f172a"></iframe>'
        f'<button type="button" class="sp-btn sp-btn-primary sp-iframe-done" '
        f'onclick="window.SP&&SP.markClicked(this.closest(\'.sp-interactive\'))" '
        f'style="margin-top:12px;width:100%">'
        f'✓ Concluí o simulador — liberar próxima seção'
        f'</button>'
        f'</div>'
    )


def _render_element(el: dict, project_id: str, assets_dir: str, base_url: str,
                     slide_idx: int, el_idx: int, questions_lookup: Dict[str, dict]) -> str:
    etype = (el.get("type") or "text").lower()
    if etype == "text":
        return _render_text_element(el)
    if etype == "image":
        return _render_image_element(el, project_id, assets_dir, base_url)
    if etype == "audio":
        return _render_audio_element(el, project_id, assets_dir, base_url, el_idx)
    if etype == "video":
        return _render_video_element(el, project_id, assets_dir, base_url, el_idx)
    if etype == "html":
        return _render_html_element(el, project_id, assets_dir, base_url)
    if etype == "quiz":
        return _render_quiz_element(el, slide_idx, el_idx, questions_lookup)
    if etype == "scenario":
        return _render_scenario_element(el, slide_idx, el_idx)
    if etype == "simulator":
        return _render_simulator_element(el, project_id, assets_dir, base_url, slide_idx, el_idx)
    # fallback: ignore unknown
    return ""


# --------------------------------------------------------------------------- main


def generate_single_page_html(
    project_doc: dict,
    assets_dir: str,
    base_url: str = "",
    questions: Optional[List[dict]] = None,
    tutor_config: Optional[dict] = None,
    scorm_mode: bool = False,
) -> str:
    """Generate a complete standalone single-page HTML for the given project.

    When scorm_mode=True, injects SCORM 1.2 runtime hooks (window.SCORM):
      - lesson_location for resume
      - suspend_data for completed interactives + quiz scores
      - cmi.interactions for quiz answer tracking
      - cmi.core.score for the running score
      - lesson_status="completed" + success_status="passed" when all sections
        are unlocked AND all quizzes passed mastery (>=80% by default)
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
        for e_idx, el in enumerate(elements):
            try:
                html_part = _render_element(el, project_id, assets_dir, base_url,
                                              s_idx, e_idx, questions_lookup)
                if html_part:
                    rendered_elements.append(html_part)
            except Exception:
                continue
        locked_attr = 'data-locked="true"' if s_idx > 0 else ''

        # Per-slide background: solid color (slide.background) and/or image (slide.backgroundImage)
        bg_color = slide.get("background") or ""
        bg_image_url = slide.get("backgroundImage") or ""
        if bg_image_url:
            bg_image_url = _resolve_asset_url(bg_image_url, project_id, assets_dir, base_url)
        bg_styles = []
        if bg_color:
            bg_styles.append(f"background-color:{_esc(bg_color)}")
        if bg_image_url:
            bg_styles.append(f"background-image:url({_esc(bg_image_url)})")
            bg_styles.append("background-size:cover")
            bg_styles.append("background-position:center")
        section_style = f' style="{";".join(bg_styles)}"' if bg_styles else ''

        section = (
            f'<section class="sp-section" data-index="{s_idx}" '
            f'data-title="{_esc(slide_title)}" '
            f'{locked_attr}{section_style}>\n'
            f'  <div class="sp-section-inner">\n'
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
    )


def _BUILD_PAGE(
    title: str,
    bg_image: str,
    sections_html: str,
    sections_index_json: str,
    total_sections: int,
    scorm_mode: bool = False,
) -> str:
    css = _CSS
    js = _JS.replace("__SECTIONS_INDEX__", sections_index_json) \
            .replace("__SCORM_MODE__", "true" if scorm_mode else "false")
    scorm_script = '<script src="scorm-api.js"></script>' if scorm_mode else ''
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
.sp-section-body{display:flex;flex-direction:column;gap:24px;color:#0f172a;font-size:15px;line-height:1.7}

/* element styles */
.sp-text{font-size:15px;line-height:1.7;color:#0f172a}
.sp-image{margin:0;display:flex;justify-content:center}
.sp-image img{box-shadow:0 6px 20px rgba(0,0,0,.18)}
.sp-html{font-size:15px;line-height:1.7;color:#0f172a}
.sp-html *{max-width:100%}
.sp-html img{max-width:100%;height:auto;border-radius:8px}

.sp-interactive{position:relative;background:#fef9c3;border-radius:12px;padding:22px;border:3px solid #facc15;transition:all .3s;box-shadow:0 4px 16px rgba(250,204,21,.25);animation:sp-attention 2.5s ease-in-out infinite}
.sp-interactive[data-completed="true"]{border-color:#84cc16;background:#f7fee7;animation:none;box-shadow:0 2px 8px rgba(132,204,22,.2)}
.sp-interactive[data-completed="true"]::after{content:"✓";position:absolute;top:10px;right:14px;color:#fff;background:#84cc16;font-weight:700;font-size:18px;width:32px;height:32px;border-radius:50%;display:flex;align-items:center;justify-content:center;box-shadow:0 2px 6px rgba(132,204,22,.4)}
.sp-interactive::before{content:"";position:absolute;top:-3px;left:-3px;right:-3px;bottom:-3px;border-radius:14px;border:3px solid #facc15;opacity:.6;pointer-events:none}
.sp-interactive[data-completed="true"]::before{display:none}
@keyframes sp-attention{0%,100%{box-shadow:0 4px 16px rgba(250,204,21,.25)}50%{box-shadow:0 6px 24px rgba(250,204,21,.55)}}

.sp-audio,.sp-video{display:flex;flex-direction:column;gap:10px}
.sp-audio audio,.sp-video video{width:100%;border-radius:8px;background:#0f172a}
.sp-audio-label,.sp-video-label{font-weight:700;color:#0a2540;font-size:15px;display:flex;align-items:center;gap:8px}
.sp-audio-label::before{content:"🎧";font-size:20px}
.sp-audio-hint,.sp-video-hint,.sp-html-hint{display:inline-block;background:#0a2540;color:#facc15;padding:8px 14px;border-radius:999px;font-size:12px;font-weight:700;letter-spacing:.5px;text-transform:uppercase;align-self:flex-start;margin-top:4px;animation:sp-pulse-hint 2s ease-in-out infinite}
@keyframes sp-pulse-hint{0%,100%{transform:scale(1)}50%{transform:scale(1.04)}}
.sp-interactive[data-completed="true"] .sp-audio-hint,
.sp-interactive[data-completed="true"] .sp-video-hint,
.sp-interactive[data-completed="true"] .sp-html-hint{display:none}

.sp-quiz{text-align:center;background:linear-gradient(135deg,#1e3a8a 0%,#2563eb 100%);color:#fff;border-color:#3b82f6}
.sp-quiz[data-completed="true"]{background:#0f5132;border-color:#84cc16;color:#dcfce7}
.sp-quiz-icon{font-size:42px;margin-bottom:10px}
.sp-quiz-title{font-size:20px;margin-bottom:6px}
.sp-quiz-meta{font-size:13px;opacity:.85;margin-bottom:14px}
.sp-quiz-body{margin-top:18px;text-align:left;background:#fff;color:#0f172a;border-radius:8px;padding:18px}
.sp-quiz-body[hidden]{display:none}
.sp-quiz-opt:hover{border-color:#2563eb!important;background:#eff6ff}
.sp-quiz-opt input:checked + *,
.sp-quiz-opt:has(input:checked){border-color:#2563eb!important;background:#dbeafe}

.sp-scenario{background:linear-gradient(135deg,#7c2d12 0%,#ea580c 100%);color:#fff;text-align:center;border-color:#fb923c}
.sp-scenario h3{margin:8px 0;font-size:20px}
.sp-scenario p{font-size:13px;opacity:.92;margin-bottom:12px}
.sp-scenario-icon{font-size:42px}

.sp-simulator{padding:8px}
.sp-simulator-label{font-weight:600;color:#1e3a8a;font-size:14px;margin-bottom:8px}

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
        $$('.sp-interactive[data-required="true"]', sec).forEach(function(el){
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
    var pending = $$('.sp-interactive[data-required="true"]', sec).filter(function(el){
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
        submit.disabled = true;
        submit.style.display = 'none';
      });
    }
  };

  document.addEventListener('DOMContentLoaded', function(){
    if (SCORM_MODE && window.SCORM) {
      try { window.SCORM.init(); } catch(e) {}
      scormRestoreState();
    }
    buildDrawer();
    updateProgress();
    updateNextButton();
    window.addEventListener('scroll', detectActiveSection, {passive:true});
    // Also re-check next button after any user interaction (covers click-reveal accordions etc.)
    document.addEventListener('click', function(){ setTimeout(updateNextButton, 50); }, true);
    // SCORM finish on unload
    if (SCORM_MODE && window.SCORM) {
      window.addEventListener('beforeunload', function(){
        try { window.SCORM.finish(); } catch(e){}
      });
    }
  });
})();
"""
