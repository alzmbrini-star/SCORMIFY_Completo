"""Aesthetic Analyzer - AI-powered course visual quality analysis and auto-fix.

Detection happens via LLM but **application** of fixes goes through a
deterministic post-validation pipeline that ENFORCES WCAG AA contrast and
adds semi-transparent backdrops/scrims when text would otherwise be
invisible. This is what gives the Analyzer real visual impact instead of
just nudging colors a little bit.
"""
import os
import json
import re
import uuid
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request, Depends
from routes.deps import db
from routes.auth import get_current_user, require_auth
from emergentintegrations.llm.chat import LlmChat, UserMessage
from services import wcag

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Aesthetics"])

EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
MODEL = ("gemini", "gemini-3-flash-preview")
FALLBACK = ("openai", "gpt-4o")


def _extract_json(text: str):
    m = re.search(r"```json\s*([\s\S]*?)```", text)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        return None


def _build_slide_context(slide: dict, slide_idx: int) -> str:
    """Extract visual properties from a slide for analysis."""
    bg = slide.get("background", "#FFFFFF")
    bg_img = slide.get("backgroundImage")
    bg_opacity = slide.get("backgroundImageOpacity", 1.0)
    title = slide.get("title", "")
    elements = slide.get("elements", [])
    width = slide.get("width", 1920)
    height = slide.get("height", 820)

    lines = [f"SLIDE {slide_idx + 1}: \"{title}\" ({width}x{height})"]
    lines.append(f"  Background: {bg}" + (f" + image (opacity {bg_opacity}) — multicolored, contrast unpredictable" if bg_img else ""))

    for i, el in enumerate(elements):
        el_type = el.get("type", "text")
        style = el.get("style", {})
        x, y = el.get("x", 0), el.get("y", 0)
        w, h = el.get("width", 100), el.get("height", 100)
        content = (el.get("content") or "")[:80]
        font_size = style.get("fontSize")
        font_color = style.get("fontColor") or style.get("fill")
        font_family = style.get("fontFamily")
        opacity = style.get("opacity", 1.0)
        fill = style.get("fill")
        text_bg = style.get("textBackgroundColor") or style.get("backgroundColor")

        desc = f"  [{i}] {el_type} at ({x:.0f},{y:.0f}) size {w:.0f}x{h:.0f}"
        if font_size:
            desc += f" fontSize={font_size}"
        if font_color:
            desc += f" fontColor={font_color}"
        if font_family:
            desc += f" font={font_family}"
        if fill:
            desc += f" fill={fill}"
        if text_bg:
            desc += f" textBg={text_bg}"
        if opacity and opacity < 1:
            desc += f" opacity={opacity}"

        # Compute & report ACTUAL WCAG ratio so the LLM can prioritize.
        if font_color and bg and not bg_img:
            try:
                ratio = wcag.contrast_ratio(font_color, bg)
                desc += f" wcag={ratio:.2f}:1"
                if ratio < 4.5:
                    desc += " (FAILS-AA)"
            except Exception:
                pass

        if el_type == "html":
            html = (el.get("htmlContent") or "")[:200]
            desc += f"\n    HTML: {html}"
        elif content:
            desc += f"\n    Text: {content}"

        lines.append(desc)

    return "\n".join(lines)


ANALYSIS_PROMPT = """Voce e um especialista em Design Visual e UX para cursos e-learning. Sua missao e identificar problemas SEVEROS de legibilidade e propor correcoes AGRESSIVAS que produzam mudancas visuais significativas.

## Foco na deteccao
1. **CONTRASTE WCAG AA**: contraste minimo 4.5:1 entre texto e fundo. Quando o slide tem `+ image (multicolored)` no background, SEMPRE proponha plate (textBackgroundColor) - o fundo e imprevisivel.
2. **HARMONIZACAO VISUAL**: paleta inconsistente, cores que brigam.
3. **TAMANHO DE FONTES**: corpo <16px, titulos <24px sao inaceitaveis.
4. **LEGIBILIDADE EM HTML**: simuladores/cenarios/quizzes com texto invisivel sobre fundos escuros do slide.
5. **LAYOUT**: sobreposicao, elementos cortados, falta de margem.

DADOS DOS SLIDES (com WCAG calculado quando aplicavel):
{slides_data}

## Tipos de fix disponiveis
- `style` — muda propriedades do elemento. Use para: fontColor, fontSize, fontFamily, fontWeight, textBackgroundColor (plate), padding, borderRadius, textShadow, opacity.
- `text_plate` — adiciona backdrop semi-transparente atras de texto (preferencial quando slide tem backgroundImage). Sem campos extras: o servidor escolhe a cor do plate automaticamente baseado no fontColor.
- `slide_overlay` — adiciona scrim escuro/claro sobre `backgroundImage` do slide inteiro. Use para slides PPT com texto sobre cenario complexo. `changes: {{"overlay": "dark"}}` ou `"light"`.
- `position` — muda x, y, width, height.
- `background` — muda background do slide. `changes: {{"background": "#FFFFFF"}}`.
- `html_style` — injeta CSS em htmlContent. SEMPRE use `!important`. Inclua tambem reset de inline styles via `[style*="color"]{{color:X !important}}`. Ex: `cssInjection: "body,body *{{color:#fff !important;font-size:16px !important}} [style*=color]{{color:#fff !important}}"`.

## Regras CRITICAS para gerar fixes
- Cores: prefira preto puro `#0f172a` ou branco puro `#f8fafc` (contraste maximo). NAO use cinza `#888` — falha WCAG.
- Quando ha `+ image` no background do slide:
   - Para CADA texto exposto, adicione `text_plate` (backdrop) E ajuste `fontColor` para branco se nao for.
   - Considere adicionar `slide_overlay: dark` ao slide para escurecer a imagem inteira.
- Para HTML elements (simuladores/cenarios), `html_style` DEVE conter:
   - `body,body * {{color:X !important}}` para forcar cor do texto
   - `[style*="color"] {{color:X !important}}` para neutralizar styles inline
   - `font-size` minimo 16px com !important
- Para fontes: corpo 16-18px, subtitulos 24-28px, titulos 32-40px.
- Cada fix deve produzir uma mudanca PERCEPTIVEL. Evite micro-ajustes (e.g. 14px -> 15px).

## Severidade
- alta: WCAG fail, texto invisivel, fonte <12px, sobreposicao critica
- media: WCAG borderline (3-4.5:1), fonte 12-14px corpo
- baixa: harmonizacao, microajustes de espacamento

## Categorias
- contraste, harmonizacao, fonte, layout, consistencia, legibilidade_html

## Formato de resposta
```json
{{
  "score": 65,
  "summary": "Resumo geral em 2-3 frases",
  "issues": [
    {{
      "id": "issue_1",
      "slideIndex": 0,
      "elementIndex": 2,
      "severity": "alta",
      "category": "contraste",
      "description": "Texto branco sobre fundo claro - WCAG 1.5:1, falha critica",
      "fix": {{
        "type": "style",
        "changes": {{"fontColor": "#0f172a", "fontSize": 18, "textBackgroundColor": "rgba(248,250,252,0.85)", "padding": "8px 12px", "borderRadius": "6px"}}
      }}
    }},
    {{
      "id": "issue_2",
      "slideIndex": 0,
      "elementIndex": 3,
      "severity": "alta",
      "category": "legibilidade_html",
      "description": "Simulador com texto cinza sobre fundo escuro do slide",
      "fix": {{
        "type": "html_style",
        "cssInjection": "body,body *{{color:#f8fafc !important;font-size:16px !important}} [style*=\\"color\\"]{{color:#f8fafc !important}}"
      }}
    }},
    {{
      "id": "issue_3",
      "slideIndex": 1,
      "severity": "media",
      "category": "contraste",
      "description": "Slide com cenario complexo, varios textos sobrepostos",
      "fix": {{
        "type": "slide_overlay",
        "changes": {{"overlay": "dark"}}
      }}
    }}
  ],
  "globalSuggestions": []
}}
```
"""


@router.post("/aesthetics/analyze/{project_id}")
async def analyze_aesthetics(project_id: str, request: Request, user: dict = Depends(require_auth)):
    """Analyze course aesthetics and return issues with suggested fixes."""
    project = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(404, "Project not found")

    slides = project.get("course", {}).get("slides", [])
    if not slides:
        raise HTTPException(400, "No slides to analyze")

    # Build context for AI
    slides_data = "\n\n".join(_build_slide_context(s, i) for i, s in enumerate(slides))

    # Call AI
    prompt = ANALYSIS_PROMPT.format(slides_data=slides_data)

    for provider, model in [MODEL, FALLBACK]:
        try:
            chat = LlmChat(
                api_key=EMERGENT_KEY,
                session_id=f"aesthetics_{project_id}_{uuid.uuid4().hex[:6]}",
                system_message="Voce e um especialista em Design Visual e UX. Responda sempre em JSON valido.",
            ).with_model(provider, model)
            raw = await chat.send_message(UserMessage(text=prompt))
            result = _extract_json(raw)
            if result:
                # Store analysis in DB
                await db.aesthetic_analyses.update_one(
                    {"projectId": project_id},
                    {"$set": {
                        "projectId": project_id,
                        "analysis": result,
                        "analyzedAt": datetime.now(timezone.utc).isoformat(),
                        "userId": user.get("user_id", ""),
                    }},
                    upsert=True
                )
                return result
        except Exception as e:
            logger.warning(f"Aesthetics analysis with {provider}/{model} failed: {str(e)[:80]}")
            continue

    raise HTTPException(500, "Failed to analyze aesthetics")


# ---------------------------------------------------------------------------
# Deterministic fix application
# ---------------------------------------------------------------------------

def _effective_bg_for_element(slide: dict) -> tuple:
    """Return (bg_color_str, has_image). When the slide has a backgroundImage,
    we treat it as 'busy/multicolored' and force plate-based fixes regardless
    of the underlying solid color."""
    bg_color = (slide.get("background") or "#ffffff").strip()
    has_image = bool(slide.get("backgroundImage"))
    return bg_color, has_image


def _apply_style_fix(element: dict, slide: dict, changes: dict) -> bool:
    """Apply style changes WITH WCAG enforcement and automatic plate insertion.

    Returns True if any change was applied. Mutates `element` in place.
    """
    if "style" not in element or not isinstance(element.get("style"), dict):
        element["style"] = {}
    style = element["style"]

    bg_color, has_image = _effective_bg_for_element(slide)

    applied_any = False
    for key, val in (changes or {}).items():
        if val in (None, ""):
            continue

        # WCAG enforcement: any fontColor change is validated against the
        # effective background. If the LLM proposed a still-poor color, we
        # silently upgrade to pure black/white.
        if key == "fontColor":
            if has_image:
                # On busy backgrounds, we want pure white text + dark plate.
                # Override LLM suggestion to maximize contrast over the image.
                final_color = wcag.LIGHT_FALLBACK
            else:
                final_color = wcag.enforce_min_contrast(str(val), bg_color, 4.5)
            style["fontColor"] = final_color
            applied_any = True
            continue

        # Numeric font-size sanity guard — LLM sometimes returns small values.
        if key == "fontSize":
            try:
                size = int(val) if not isinstance(val, str) else int(re.sub(r"[^\d]", "", str(val)))
                if size < 14:
                    size = 16
                style["fontSize"] = size
                applied_any = True
                continue
            except (ValueError, TypeError):
                pass

        style[key] = val
        applied_any = True

    # Auto-add plate when slide has bgImage and the element has visible text
    # AND we just touched its color/font. Plates are the single most effective
    # contrast booster for busy backgrounds — far more reliable than picking
    # an alternate color.
    if has_image and (element.get("type") == "text" or element.get("content")):
        if "textBackgroundColor" not in style and "backgroundColor" not in style:
            # Pick plate color that contrasts with the (now-corrected) fontColor.
            plate = wcag.pick_plate_color(style.get("fontColor") or "#ffffff")
            style["textBackgroundColor"] = plate
            style.setdefault("padding", "10px 14px")
            style.setdefault("borderRadius", "8px")
            applied_any = True

    return applied_any


def _apply_text_plate(element: dict, slide: dict) -> bool:
    """Add a semi-transparent backdrop behind a text/content element."""
    if "style" not in element or not isinstance(element.get("style"), dict):
        element["style"] = {}
    style = element["style"]

    fg = style.get("fontColor") or wcag.LIGHT_FALLBACK
    plate = wcag.pick_plate_color(fg)

    style["textBackgroundColor"] = plate
    style.setdefault("padding", "10px 14px")
    style.setdefault("borderRadius", "8px")
    # Boost shadow for extra readability over busy backgrounds.
    style.setdefault("textShadow", "0 1px 3px rgba(0,0,0,0.35)")
    return True


def _apply_slide_overlay(slide: dict, changes: dict) -> bool:
    """Set a darken/lighten scrim over the slide's backgroundImage."""
    overlay = (changes or {}).get("overlay", "dark")
    if overlay not in ("dark", "light"):
        # Accept arbitrary rgba/hex too
        overlay = str(overlay)
    slide["backgroundImageOverlay"] = overlay
    return True


_INLINE_COLOR_RE = re.compile(r"""style\s*=\s*(['"])([^'"]*)\1""", re.IGNORECASE)


def _strengthen_css_injection(css: str, target_text_color: str = None) -> str:
    """Wrap LLM-provided CSS with !important and aggressive selectors so
    inline styles inside the HTML element cannot win specificity.

    If `target_text_color` is provided, append a universal color override.
    """
    css = (css or "").strip()
    parts = []
    if css:
        # Naive but effective: ensure every declaration ends with !important.
        # Don't double-add when already present.
        def _add_important(m):
            decl = m.group(0).rstrip()
            return decl if "!important" in decl else decl + " !important"

        # Match css properties (property:value). Stops before ; } or end-of-string.
        css_with_important = re.sub(
            r"([a-zA-Z\-]+\s*:\s*[^;{}!]+)(?=\s*[;}]|\s*$)",
            _add_important,
            css,
        )
        parts.append(css_with_important)

    if target_text_color:
        parts.append(
            f"body,body *,body p,body span,body div,body li,body td,body th{{color:{target_text_color} !important}}"
            f"[style*=\"color\"]{{color:{target_text_color} !important}}"
        )

    return " ".join(parts)


def _apply_html_style_fix(element: dict, css: str, target_color: str = None) -> bool:
    """Inject CSS into an HTML element's htmlContent with maximum specificity.

    Strategy: wrap the CSS with !important on every declaration and append a
    universal color override that defeats inline styles. Insert as the
    LAST <style> tag so it wins over earlier <style> blocks.
    """
    html = element.get("htmlContent") or ""
    if not html or not (css or target_color):
        return False

    final_css = _strengthen_css_injection(css, target_text_color=target_color)
    if not final_css:
        return False

    style_tag = f'<style data-aesthetic-fix="1">{final_css}</style>'

    # Append AT THE END of <head>...</head> so it overrides earlier styles.
    if "</head>" in html:
        html = html.replace("</head>", f"{style_tag}</head>", 1)
    elif "</body>" in html:
        # If no head, insert just before </body> so it still applies
        html = html.replace("</body>", f"{style_tag}</body>", 1)
    elif "<body" in html:
        # Wrap-less HTML: prepend the style tag
        html = f"{style_tag}{html}"
    else:
        html = f"{style_tag}{html}"

    element["htmlContent"] = html
    return True


@router.post("/aesthetics/apply-fix/{project_id}")
async def apply_aesthetic_fix(project_id: str, request: Request, user: dict = Depends(require_auth)):
    """Apply a specific aesthetic fix or all fixes to a project.

    Goes through deterministic post-validation that ENFORCES WCAG AA contrast
    and automatically adds plates/scrims when needed."""
    body = await request.json()
    fix_ids = body.get("fixIds", [])
    apply_all = body.get("applyAll", False)

    project = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(404, "Project not found")

    analysis_doc = await db.aesthetic_analyses.find_one({"projectId": project_id}, {"_id": 0})
    if not analysis_doc or not analysis_doc.get("analysis"):
        raise HTTPException(400, "No analysis found. Run analyze first.")

    issues = analysis_doc["analysis"].get("issues", [])
    if not issues:
        return {"applied": 0, "message": "No issues to fix"}

    if apply_all:
        to_apply = issues
    else:
        to_apply = [i for i in issues if i.get("id") in fix_ids]

    if not to_apply:
        return {"applied": 0, "message": "No matching fixes found"}

    slides = project.get("course", {}).get("slides", [])
    applied = 0

    for issue in to_apply:
        try:
            slide_idx = issue.get("slideIndex", -1)
            el_idx = issue.get("elementIndex", -1)
            fix = issue.get("fix", {})
            fix_type = fix.get("type", "")

            if slide_idx < 0 or slide_idx >= len(slides):
                continue
            slide = slides[slide_idx]

            if fix_type == "style" and 0 <= el_idx < len(slide.get("elements", [])):
                element = slide["elements"][el_idx]
                if _apply_style_fix(element, slide, fix.get("changes", {})):
                    applied += 1

            elif fix_type == "text_plate" and 0 <= el_idx < len(slide.get("elements", [])):
                element = slide["elements"][el_idx]
                if _apply_text_plate(element, slide):
                    applied += 1

            elif fix_type == "slide_overlay":
                if _apply_slide_overlay(slide, fix.get("changes", {})):
                    applied += 1

            elif fix_type == "position" and 0 <= el_idx < len(slide.get("elements", [])):
                element = slide["elements"][el_idx]
                changes = fix.get("changes", {})
                for key in ("x", "y", "width", "height"):
                    if key in changes:
                        element[key] = changes[key]
                applied += 1

            elif fix_type == "background":
                changes = fix.get("changes", {})
                if "background" in changes:
                    slide["background"] = changes["background"]
                    applied += 1

            elif fix_type == "html_style" and 0 <= el_idx < len(slide.get("elements", [])):
                element = slide["elements"][el_idx]
                css = fix.get("cssInjection", "")
                # Try to extract a target color from the CSS so the override
                # is even stronger (catches inline `<span style="color:red">`).
                target_color = None
                m = re.search(r"color\s*:\s*(#[0-9a-fA-F]{3,8}|rgba?\([^)]+\))", css or "")
                if m:
                    target_color = m.group(1)
                if _apply_html_style_fix(element, css, target_color=target_color):
                    applied += 1

        except Exception as e:
            logger.warning(f"Failed to apply fix {issue.get('id')}: {e}")

    if applied > 0:
        await db.projects.update_one(
            {"id": project_id},
            {"$set": {
                "course.slides": slides,
                "updatedAt": datetime.now(timezone.utc).isoformat(),
            }}
        )

    return {"applied": applied, "total": len(to_apply), "message": f"{applied} correcoes aplicadas"}
