"""Aesthetic Analyzer - AI-powered course visual quality analysis and auto-fix."""
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
    lines.append(f"  Background: {bg}" + (f" + image (opacity {bg_opacity})" if bg_img else ""))

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

        desc = f"  [{i}] {el_type} at ({x:.0f},{y:.0f}) size {w:.0f}x{h:.0f}"
        if font_size:
            desc += f" fontSize={font_size}"
        if font_color:
            desc += f" fontColor={font_color}"
        if font_family:
            desc += f" font={font_family}"
        if fill:
            desc += f" fill={fill}"
        if opacity and opacity < 1:
            desc += f" opacity={opacity}"
        if el_type == "html":
            html = (el.get("htmlContent") or "")[:200]
            desc += f"\n    HTML: {html}"
        elif content:
            desc += f"\n    Text: {content}"

        lines.append(desc)

    return "\n".join(lines)


ANALYSIS_PROMPT = """Voce e um especialista em Design Visual e UX para cursos e-learning.

Analise os slides a seguir e identifique TODOS os problemas visuais/esteticos. Foque em:

1. **CONTRASTE DE CORES**: Fontes vs background - cores que nao realcam, texto invisivel ou dificil de ler. Inclui simuladores, cenarios, desafios e quizzes (elementos HTML).
2. **HARMONIZACAO VISUAL**: Cores que nao combinam, paleta inconsistente entre slides.
3. **TAMANHO DE FONTES**: Fontes muito pequenas (<16px para corpo, <24px para titulos) ou muito grandes. Deve ser legivel em desktop E mobile.
4. **LAYOUT E ESPACAMENTO**: Elementos sobrepostos, mal alinhados, sem margem suficiente, ou fora da area visivel.
5. **CONSISTENCIA**: Slides com estilos muito diferentes entre si (fontes, cores, espacamento).
6. **LEGIBILIDADE EM HTML**: Elementos HTML (simuladores, cenarios, jogos) com cores de texto que nao contrastam com o background do slide.

DADOS DOS SLIDES:
{slides_data}

Para CADA problema encontrado, gere uma correcao especifica. Responda em JSON:
```json
{{
  "score": 85,
  "summary": "Resumo geral da qualidade estetica em 2-3 frases",
  "issues": [
    {{
      "id": "issue_1",
      "slideIndex": 0,
      "elementIndex": 2,
      "severity": "alta",
      "category": "contraste",
      "description": "Texto branco sobre fundo claro - impossivel de ler",
      "fix": {{
        "type": "style",
        "changes": {{"fontColor": "#1a1a2e", "fontSize": 18}}
      }}
    }}
  ],
  "globalSuggestions": [
    {{
      "description": "Padronizar fonte de titulos para 28px em todos os slides",
      "affectedSlides": [0, 2, 5]
    }}
  ]
}}
```

REGRAS para os fixes:
- "type": "style" = muda propriedades do style do elemento (fontColor, fontSize, fontFamily, fill, opacity, etc)
- "type": "position" = muda x, y, width, height do elemento
- "type": "background" = muda background do slide
- "type": "html_style" = injeta CSS inline no htmlContent (para simuladores/cenarios/quizzes)
- Para html_style, inclua "cssInjection" com o CSS a injetar (ex: "body{{color:#fff;font-size:16px}}")
- score: 0-100 (100 = perfeito)
- severity: "alta", "media", "baixa"
- category: "contraste", "harmonizacao", "fonte", "layout", "consistencia", "legibilidade_html"
- Seja ESPECIFICO nos fixes - inclua valores exatos de cor, tamanho, posicao
- Prefira cores escuras sobre fundos claros e cores claras sobre fundos escuros
- Para fontes: minimo 16px corpo, 24px subtitulos, 32px+ titulos
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


@router.post("/aesthetics/apply-fix/{project_id}")
async def apply_aesthetic_fix(project_id: str, request: Request, user: dict = Depends(require_auth)):
    """Apply a specific aesthetic fix or all fixes to a project."""
    body = await request.json()
    fix_ids = body.get("fixIds", [])  # specific issue IDs, or empty for all
    apply_all = body.get("applyAll", False)

    project = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(404, "Project not found")

    # Get stored analysis
    analysis_doc = await db.aesthetic_analyses.find_one({"projectId": project_id}, {"_id": 0})
    if not analysis_doc or not analysis_doc.get("analysis"):
        raise HTTPException(400, "No analysis found. Run analyze first.")

    issues = analysis_doc["analysis"].get("issues", [])
    if not issues:
        return {"applied": 0, "message": "No issues to fix"}

    # Filter issues to apply
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
                changes = fix.get("changes", {})
                if "style" not in element:
                    element["style"] = {}
                for key, val in changes.items():
                    element["style"][key] = val
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
                if css and element.get("htmlContent"):
                    html = element["htmlContent"]
                    if "<style>" in html:
                        html = html.replace("</style>", f"\n{css}\n</style>", 1)
                    else:
                        style_tag = f"<style>{css}</style>"
                        if "<head>" in html:
                            html = html.replace("<head>", f"<head>{style_tag}", 1)
                        elif "<body" in html:
                            html = html.replace("<body", f"{style_tag}<body", 1)
                        else:
                            html = f"{style_tag}{html}"
                    element["htmlContent"] = html
                applied += 1

        except Exception as e:
            logger.warning(f"Failed to apply fix {issue.get('id')}: {e}")

    # Save updated project
    if applied > 0:
        await db.projects.update_one(
            {"id": project_id},
            {"$set": {
                "course.slides": slides,
                "updatedAt": datetime.now(timezone.utc).isoformat(),
            }}
        )

    return {"applied": applied, "total": len(to_apply), "message": f"{applied} correcoes aplicadas"}
