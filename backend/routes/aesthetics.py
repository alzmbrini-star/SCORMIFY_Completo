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
from bs4 import BeautifulSoup
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


def _classify_slide(slide: dict, idx: int, total: int) -> str:
    """Classify slide role to drive font-size suggestions:
      - 'capa'       — first slide / cover with few elements + big title
      - 'html_heavy' — slide where the dominant/only element is HTML
                       (simulators/scenarios/quizzes built by the AI Agent).
                       These have internal typography that MUST be preserved
                       — we only touch critical contrast.
      - 'conteudo'   — regular content slide (text + image + maybe small html).
    """
    elements = slide.get("elements") or []
    if not elements:
        return "capa" if idx == 0 else "conteudo"

    # html-heavy: more than 50% of elements are HTML, OR a single HTML covers
    # most of the slide area (likely a full-bleed simulator).
    html_count = sum(1 for e in elements if (e.get("type") == "html"))
    if html_count and html_count / max(1, len(elements)) >= 0.5:
        return "html_heavy"
    slide_w = float(slide.get("width") or 1920) or 1920
    slide_h = float(slide.get("height") or 820) or 820
    slide_area = slide_w * slide_h
    for e in elements:
        if e.get("type") != "html":
            continue
        try:
            w = float(e.get("width") or 0)
            h = float(e.get("height") or 0)
        except (TypeError, ValueError):
            continue
        if w * h >= slide_area * 0.55:
            return "html_heavy"

    # capa: first slide, OR slide with few elements + a title-shaped text
    if idx == 0 and len(elements) <= 4:
        return "capa"
    text_count = sum(1 for e in elements if e.get("type") == "text")
    if len(elements) <= 3 and text_count >= 1:
        # short slides feel like covers/section dividers
        title_lower = (slide.get("title") or "").lower()
        if any(kw in title_lower for kw in ("capa", "cover", "intro", "apresenta", "bem-vindo", "welcome", "boas-vindas")):
            return "capa"

    return "conteudo"


def _build_slide_context(slide: dict, slide_idx: int, total: int = 1) -> str:
    """Extract visual properties from a slide for analysis."""
    bg = slide.get("background", "#FFFFFF")
    bg_img = slide.get("backgroundImage")
    bg_opacity = slide.get("backgroundImageOpacity", 1.0)
    title = slide.get("title", "")
    elements = slide.get("elements", [])
    width = slide.get("width", 1920)
    height = slide.get("height", 820)
    role = _classify_slide(slide, slide_idx, total)
    role_label = {"capa": "CAPA", "html_heavy": "HTML-PESADO", "conteudo": "CONTEUDO"}[role]

    lines = [f"SLIDE {slide_idx} [{role_label}]: \"{title}\" ({width}x{height})  (use slideIndex={slide_idx} when reporting issues for this slide)"]
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


ANALYSIS_PROMPT = """Voce e um especialista em Design Visual e UX para cursos e-learning. Sua missao e identificar problemas SEVEROS de legibilidade e propor correcoes AGRESSIVAS que produzam mudancas visuais significativas SEM destruir a harmonia visual existente.

## INDEXACAO DE SLIDES (CRITICO!)
- Cada slide vem rotulado como `SLIDE N` onde N e o **slideIndex (0-based)** que voce DEVE usar no campo `slideIndex` da resposta.
- NAO faca conversoes — copie o numero exato que aparece no rotulo "SLIDE N".
- Errar o slideIndex significa aplicar o fix no slide ERRADO. Confira duas vezes antes de finalizar.

## Tipos de slide (importante!)
Cada slide vem rotulado entre colchetes:
- `[CAPA]` — capas / divisorias de modulo / aberturas. Hierarquia tipografica MAIOR: titulo principal **48-72px** (bold), subtitulo 22-28px, body 18-20px. Uma capa minimalista com pouco texto e MUITO espaco e sinal de qualidade — NAO encha de elementos.
- `[CONTEUDO]` — slide de conteudo regular. Hierarquia padrao: titulo h1 **32-40px**, h2 24-28px, corpo de texto **16-20px**, legenda 13-14px.
- `[HTML-PESADO]` — slide cujo conteudo principal e um simulador / cenario / quiz / jogo construido em HTML pelo Agente IA. Esses elementos tem **identidade visual propria, com tipografia interna intencional**. **NAO imponha tamanhos de fonte absolutos em px** — isso QUEBRA a harmonia que o Agente construiu. Voce so deve corrigir:
   - Contraste critico (texto invisivel),
   - Use SOMENTE unidades RELATIVAS `em`/`%` ou cores. Ex: `body{{color:#fff !important}} h1,h2,h3{{color:#fff !important}}`. **NUNCA escreva `font-size: 18px` em html_style** — se precisar ajustar tamanho, use `font-size: 1.05em !important` (5% maior).
   - Se o simulador tem fundo claro `#f0f2f5` em curso dark, troque para `background:#0f172a` ou cor neutra escura — mas mantenha a tipografia interna do simulador intacta.

## Foco na deteccao
1. **CONTRASTE WCAG AA**: contraste minimo 4.5:1 entre texto e fundo. Quando o slide tem `+ image (multicolored)`, SEMPRE proponha plate (textBackgroundColor) — o fundo e imprevisivel.
2. **HARMONIZACAO VISUAL**: cores que brigam entre si. Mas NAO troque cores de simuladores HTML — eles seguem identidade propria.
3. **TAMANHO DE FONTES**: aplicar regras de hierarquia ACIMA segundo o tipo de slide. Para HTML-PESADO so atue se a fonte estiver visivelmente apequenada (ex: <12px hardcoded).
4. **LEGIBILIDADE EM HTML**: simuladores com texto invisivel.
5. **LAYOUT**: sobreposicao, elementos cortados.

DADOS DOS SLIDES (com WCAG calculado quando aplicavel):
{slides_data}

## Tipos de fix disponiveis
- `style` — muda propriedades do elemento. Use para: fontColor, fontSize, fontFamily, fontWeight, textBackgroundColor (plate), padding, borderRadius, textShadow, opacity.
- `text_plate` — adiciona backdrop semi-transparente atras de texto.
- `slide_overlay` — adiciona scrim escuro/claro sobre `backgroundImage`. `changes: {{"overlay": "dark"}}` ou `"light"`.
- `position` — muda x, y, width, height.
- `background` — muda background do slide.
- `html_style` — injeta CSS em htmlContent. **REGRAS RIGIDAS para slides HTML-PESADO**:
   - **PROIBIDO seletores universais**: `*`, `body *`, `body` bare, `html`, `[style*=color]`. Se voce usar, o servidor DESCARTA a regra inteira.
   - **OBRIGATORIO seletores targetados**: classe (`.option-btn`), id (`#prompt-box`), ou tag-com-classe (`p.error`). Sem eles, NADA e injetado e o problema permanece.
   - SEMPRE com `!important` em cada declaracao
   - Para font-size, USE `em`/`rem`/`%` (nunca px)
   - NAO injete padding/margin/line-height (sao stripados)
   - **Estrategia recomendada**: leia o htmlContent, identifique a CLASSE OU ID exata do elemento problemático, e direcione apenas ele.

## Regras CRITICAS
- Prefira preto puro `#0f172a` ou branco puro `#f8fafc` — NUNCA cinza intermediario.
- Em slides com `+ image`: para CADA texto exposto, adicione `text_plate` E ajuste `fontColor`. Considere `slide_overlay: dark`.
- Cada fix deve produzir mudanca PERCEPTIVEL. Evite micro-ajustes (14px -> 15px).
- Para slides HTML-PESADO, **emita NO MAXIMO 1 issue por slide** — nao gere ruido sobre simuladores que ja funcionam visualmente bem.

## Severidade
- alta: WCAG fail, texto invisivel, fonte <12px corpo, sobreposicao critica, capa sem hierarquia
- media: WCAG borderline (3-4.5:1), fonte 12-14px corpo, capa com titulo <40px
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
      "severity": "alta",
      "category": "fonte",
      "description": "Capa com titulo 24px - hierarquia insuficiente, deveria ser 48-64px",
      "fix": {{
        "type": "style",
        "changes": {{"fontSize": 56, "fontWeight": "bold"}}
      }}
    }},
    {{
      "id": "issue_3",
      "slideIndex": 4,
      "elementIndex": 0,
      "severity": "alta",
      "category": "legibilidade_html",
      "description": "Botao .option-btn com texto cinza claro sobre fundo cyan (1.8:1)",
      "fix": {{
        "type": "html_style",
        "cssInjection": ".option-btn{{color:#0f172a !important}} .option-btn:hover{{color:#000 !important}}"
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
    slides_data = "\n\n".join(_build_slide_context(s, i, len(slides)) for i, s in enumerate(slides))

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


# ---------------------------------------------------------------------------
# HTML inline style propagation (BS4-powered)
# ---------------------------------------------------------------------------
# When the LLM proposes a style change on a type=html element, the outer
# element style.* changes alone do NOT propagate to inline <h2 style="...">
# rules inside the iframe-rendered htmlContent. We must REWRITE those inline
# styles directly so the visible text actually changes.

_TEXT_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6", "p", "span", "li", "td", "th", "strong", "b", "em", "div", "label")


def _extract_styled_tag_colors(soup: BeautifulSoup):
    """Walk every tag in `soup` and return a list of dicts:
        [{"tag": Tag, "color": "#xxx", "source": "style|font_attr", "size_px": float|None}]

    Captures BOTH modern inline `style="color:X"` AND legacy HTML4
    `<font color="X">` attributes. The AI Agent generates a mix of both,
    and earlier versions of this analyzer ignored `<font>` → polarity
    detection got fooled into picking the wrong plate.
    """
    entries = []
    for tag in soup.find_all(True):
        # Inline style="color:X"
        style_attr = tag.get("style", "") or ""
        m_col = re.search(r"\bcolor\s*:\s*([^;\"\']+)", style_attr, re.IGNORECASE)
        m_sz = re.search(r"\bfont-size\s*:\s*([\d.]+)\s*px", style_attr, re.IGNORECASE)
        size_px = float(m_sz.group(1)) if m_sz else None
        if m_col:
            entries.append({
                "tag": tag,
                "color": m_col.group(1).strip().rstrip(';').strip(),
                "source": "style",
                "size_px": size_px,
            })
        # Legacy <font color="X">
        if tag.name == "font" and tag.get("color"):
            entries.append({
                "tag": tag,
                "color": str(tag.get("color")).strip(),
                "source": "font_attr",
                "size_px": size_px,  # may be inherited
            })
    return entries


def _pick_dominant_color(entries) -> str:
    """From `_extract_styled_tag_colors` output, pick the color that
    represents the slide's primary text identity. Strategy:
      1. The color of the entry with the largest `size_px` (the title)
         — assuming we can resolve it.
      2. Fallback to the most common color across all entries.
    """
    if not entries:
        return wcag.LIGHT_FALLBACK
    # Prefer the entry with the largest known font-size
    sized = [e for e in entries if e["size_px"]]
    if sized:
        biggest = max(sized, key=lambda e: e["size_px"])
        return biggest["color"]
    # Otherwise the most common color
    from collections import Counter
    return Counter(e["color"] for e in entries).most_common(1)[0][0]


def _rewrite_inline_color(style_attr: str, new_color: str, html_bg: str,
                          only_when_failing: bool = False) -> str:
    """Replace every `color: X` inside an inline style attribute.

    When `only_when_failing=True`, only replaces if the current color fails
    WCAG (ratio < 4.5) against `html_bg`. This protects intentional brand
    accent colors that are already legible.
    """
    def _do(m):
        cur = m.group(1).strip().rstrip(';').strip()
        if only_when_failing:
            try:
                if wcag.contrast_ratio(cur, html_bg) >= 4.5:
                    return m.group(0)  # keep as-is, already legible
            except Exception:
                pass
        return f"color:{new_color}"
    return re.sub(r"\bcolor\s*:\s*([^;]+)", _do, style_attr, flags=re.IGNORECASE)


def _rewrite_inline_font_size(style_attr: str, scale: float, target_size: int = None,
                              is_dominant_tag: bool = False) -> str:
    """Scale inline font-size declarations. When `is_dominant_tag=True` and
    `target_size` is set, the largest size in the attribute is replaced
    EXACTLY with target_size (so the title gets the LLM's intended size
    rather than scale * old_size which can drift)."""
    def _do(m):
        val = m.group(1).strip()
        px_match = re.match(r"([\d.]+)\s*px", val, re.IGNORECASE)
        if not px_match:
            return m.group(0)
        cur = float(px_match.group(1))
        if is_dominant_tag and target_size is not None:
            new_px = int(target_size)
        else:
            new_px = max(12, int(round(cur * scale)))
        return f"font-size:{new_px}px"
    return re.sub(r"\bfont-size\s*:\s*([^;]+)", _do, style_attr, flags=re.IGNORECASE)


def _rewrite_inline_font_weight(style_attr: str, new_weight) -> str:
    """Replace inline font-weight if present, else leave attribute alone.
    We DON'T inject font-weight into elements that didn't have one — that
    would over-bold body text."""
    return re.sub(r"\bfont-weight\s*:\s*[^;]+", f"font-weight:{new_weight}", style_attr, flags=re.IGNORECASE)


def _inject_html_bg_plate(element: dict, slide: dict) -> bool:
    """For type=html elements on slides with a busy backgroundImage,
    inject a SURGICAL backdrop applied per-text-block (not full-body) so
    text remains legible while the decorative image stays fully visible
    around the content.

    Strategy (surgical-plate, opt-C in the conversation):
      - Identify TOP-LEVEL text blocks: h1-h6, p, li, blockquote, td/th
      - Each block gets:
          background-color: <plate>  (semi-transparent)
          padding: 8px 14px
          border-radius: 8px
          display: inline-block (so the plate wraps the text run only, not
                                the full width of the iframe)
      - The iframe's html/body stay FULLY TRANSPARENT — the slide's
        backgroundImage decoration is preserved at 100% opacity around
        every plate.
      - Polarity follows the dominant text color: light text → dark plate;
        dark text → light cream plate.

    Idempotent: strips any prior aesthetic-fix `<style>` tags before
    re-injecting. Returns True if htmlContent was mutated.
    """
    if element.get("type") != "html":
        return False
    if not slide.get("backgroundImage"):
        return False
    html = element.get("htmlContent") or ""
    if not html:
        return False

    # Strip prior aesthetic-fix tags so we don't pile up backdrops.
    cleaned = _clean_aesthetic_fixes_from_html(html)
    try:
        soup = BeautifulSoup(cleaned, "html.parser")
    except Exception as exc:
        logger.warning(f"BS4 parse failed in _inject_html_bg_plate: {exc}")
        return False

    # Determine dominant text color from BOTH modern inline styles AND
    # legacy <font color="X"> attributes. Earlier versions missed <font>
    # which led to picking the wrong plate polarity on AI-generated slides
    # that emit HTML4 markup.
    entries = _extract_styled_tag_colors(soup)
    intended_fg = _pick_dominant_color(entries)

    try:
        is_dark_text = wcag.is_dark_background(intended_fg)
    except Exception:
        is_dark_text = False

    if is_dark_text:
        plate_rgba = "rgba(248,250,252,0.88)"
        text_color_fallback = wcag.DARK_FALLBACK
    else:
        plate_rgba = "rgba(15,23,42,0.78)"
        text_color_fallback = wcag.LIGHT_FALLBACK

    # CSS-only rule using attribute markers. We add `data-aesthetic-plate`
    # to each candidate text block so the rule selector is bulletproof
    # against any prior inline styles. Using `box-decoration-break: clone`
    # so multi-line text gets a plate per line wrap (cleaner look).
    rule = (
        # Keep the iframe transparent — the decorative bgImage shines through.
        "html,body{background:transparent !important;}"
        # Each text block gets a surgical plate around its CONTENT box only.
        "[data-aesthetic-plate]{"
        f"background-color:{plate_rgba} !important;"
        "padding:8px 14px !important;"
        "border-radius:8px !important;"
        "box-decoration-break:clone;"
        "-webkit-box-decoration-break:clone;"
        f"color:{text_color_fallback};"
        "}"
        # Tags without their own inline color inherit the plate's default.
        "[data-aesthetic-plate] *:not([style*=\"color\"]):not(font[color]){color:inherit;}"
    )

    # Mark text blocks. We tag block-level text containers (h1-h6, p, li,
    # blockquote, td/th) — but skip tiny inline tags (span, b, em) so the
    # plate doesn't fragment the look of bold/italic runs.
    _PLATE_TARGETS = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote", "td", "th"}
    mutated_any_block = False
    for tag in soup.find_all(_PLATE_TARGETS):
        # Skip tags whose direct text is empty (pure-container blocks).
        if not (tag.get_text(strip=True) or "").strip():
            continue
        # Avoid re-marking already-tagged blocks (idempotency on direct re-runs).
        if tag.has_attr("data-aesthetic-plate"):
            continue
        tag["data-aesthetic-plate"] = "1"
        mutated_any_block = True

    style_tag = soup.new_tag("style", attrs={"data-aesthetic-fix": "1"})
    style_tag.string = rule
    if soup.head:
        soup.head.append(style_tag)
    elif soup.body:
        soup.body.insert(0, style_tag)
    else:
        soup.insert(0, style_tag)

    new_html = str(soup)
    if new_html != html:
        element["htmlContent"] = new_html
        return True
    # If only the style tag changed but we marked no blocks, that's still a
    # write — return True so callers know we touched the element.
    return mutated_any_block


def _propagate_style_to_html_content(element: dict, changes: dict, slide: dict) -> bool:
    """For type=html elements, rewrite inline styles inside htmlContent so
    that fontSize/fontWeight/fontColor changes from `changes` actually
    become visible.

    Returns True if htmlContent was mutated.

    Strategy:
      - Detect the simulator's internal background → used for WCAG checks.
      - If `fontSize` change: find the LARGEST inline `font-size: Npx` in
        the htmlContent and treat it as the "title". Map it to the new
        target size; scale all other inline sizes proportionally.
      - If `fontColor` change: rewrite every inline `color: X` whose current
        contrast against the html bg fails WCAG (or whose color is the
        same as the previous title color). PRESERVES intentional accent
        colors that are already legible (e.g., orange badge on dark bg).
      - If `fontWeight` change: only updates tags that already declare a
        font-weight (i.e., headings/strong/b). Avoids over-bolding body.
      - Fallback: when there are NO inline font-sizes (rare; usually
        relying on browser defaults), inject a `<style data-aesthetic-fix>`
        block targeting `h1-h6` with the new size/weight/color.
    """
    if element.get("type") != "html":
        return False
    html = element.get("htmlContent") or ""
    if not html:
        return False

    new_size = changes.get("fontSize")
    new_color = changes.get("fontColor")
    new_weight = changes.get("fontWeight")
    if not any([new_size, new_color, new_weight]):
        return False

    # Strip any prior aesthetic-fix injection so we start fresh & idempotent.
    html = _clean_aesthetic_fixes_from_html(html)

    # Determine effective bg for contrast checks.
    slide_bg = (slide.get("background") or "#ffffff").strip()
    html_bg = _extract_dominant_html_bg(html) or slide_bg

    # Try to parse with BS4. If parse fails (extremely rare), bail out
    # gracefully and let the upstream <style>-injection path handle it.
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception as exc:
        logger.warning(f"BS4 parse failed in _propagate_style_to_html_content: {exc}")
        return False

    # Coerce new_size to int when possible.
    target_size = None
    if new_size is not None:
        try:
            target_size = int(str(new_size).strip().rstrip("px"))
        except (ValueError, TypeError):
            target_size = None

    # First pass: detect the dominant (largest) font-size & its tag.
    sized_entries = []  # [(tag, current_px)]
    for tag in soup.find_all(style=True):
        m = re.search(r"font-size\s*:\s*([\d.]+)\s*px", tag.get("style", "") or "", re.IGNORECASE)
        if m:
            try:
                sized_entries.append((tag, float(m.group(1))))
            except ValueError:
                continue

    scale = None
    dominant_tag = None
    if target_size and sized_entries:
        dominant_tag, max_px = max(sized_entries, key=lambda x: x[1])
        if max_px > 0:
            scale = float(target_size) / max_px

    mutated = False

    # Second pass: rewrite inline styles tag-by-tag.
    for tag in soup.find_all(style=True):
        style_attr = tag.get("style", "") or ""
        new_style = style_attr

        # font-size scaling
        if scale is not None:
            new_style = _rewrite_inline_font_size(
                new_style,
                scale,
                target_size=target_size,
                is_dominant_tag=(tag is dominant_tag),
            )

        # color rewrite — three modes:
        #  1. LLM proposed new_color → force on every inline color that
        #     either fails WCAG or matches the previous dominant color.
        #  2. No new_color but inline color FAILS WCAG against html_bg
        #     → defense-in-depth, force a high-contrast polarity.
        if new_color:
            # Validate proposed color against html bg; flip if it makes
            # text invisible there.
            final_color = new_color
            try:
                if wcag.contrast_ratio(final_color, html_bg) < 4.5:
                    final_color = wcag.pick_high_contrast_color(html_bg)
            except Exception:
                pass
            new_style = _rewrite_inline_color(
                new_style, final_color, html_bg, only_when_failing=True
            )
        else:
            # Defense-in-depth: even without an explicit fontColor request,
            # rewrite any inline color that fails WCAG against the simulator
            # background (e.g., white text on white html bg).
            fallback_color = wcag.pick_high_contrast_color(html_bg)
            new_style = _rewrite_inline_color(
                new_style, fallback_color, html_bg, only_when_failing=True
            )

        # font-weight — only replaces if attribute already has one.
        if new_weight:
            new_style = _rewrite_inline_font_weight(new_style, new_weight)

        if new_style != style_attr:
            tag["style"] = new_style
            mutated = True

    # ------------------------------------------------------------------
    # LEGACY <font color="X"> rewrite
    # The AI Agent sometimes emits HTML4 `<font color="...">` wrappers
    # instead of inline `style="color:..."`. We need to rewrite those too
    # so the visible color actually changes.
    #
    # Rule: ONLY rewrite when the current color fails WCAG (< 4.5) against
    # the html bg. This preserves intentional brand-accent colors that are
    # already legible (e.g., orange on navy).
    # ------------------------------------------------------------------
    for font_tag in soup.find_all("font", color=True):
        cur = str(font_tag.get("color") or "").strip()
        if not cur:
            continue
        try:
            cur_ratio = wcag.contrast_ratio(cur, html_bg)
        except Exception:
            cur_ratio = 99.0
        if cur_ratio >= 4.5:
            # Already legible — DO NOT touch (preserves accents).
            continue
        # Failing WCAG: pick a replacement. Prefer the LLM-proposed color
        # (after validating against the bg); otherwise auto-flip polarity.
        if new_color:
            final_color = new_color
            try:
                if wcag.contrast_ratio(final_color, html_bg) < 4.5:
                    final_color = wcag.pick_high_contrast_color(html_bg)
            except Exception:
                pass
        else:
            final_color = wcag.pick_high_contrast_color(html_bg)
        if cur.lower() != final_color.lower():
            font_tag["color"] = final_color
            mutated = True

    # ------------------------------------------------------------------
    # INJECTED STYLE BLOCK (fallback only)
    # When the htmlContent has NO inline font-sizes but the LLM still
    # wants a size bump, inject a <style data-aesthetic-fix> targeting
    # h1-h6. The bgImage plate is handled separately by
    # `_inject_html_bg_plate` so the two concerns stay independent.
    # ------------------------------------------------------------------
    if target_size and not sized_entries:
        rule = f"h1,h2,h3,h4,h5,h6 {{ font-size: {target_size}px !important;"
        if new_weight:
            rule += f" font-weight: {new_weight} !important;"
        if new_color:
            final_color = new_color
            try:
                if wcag.contrast_ratio(final_color, html_bg) < 4.5:
                    final_color = wcag.pick_high_contrast_color(html_bg)
            except Exception:
                pass
            rule += f" color: {final_color} !important;"
        rule += " }"
        style_tag = soup.new_tag("style", attrs={"data-aesthetic-fix": "1"})
        style_tag.string = rule
        if soup.head:
            soup.head.append(style_tag)
        elif soup.body:
            soup.body.insert(0, style_tag)
        else:
            soup.insert(0, style_tag)
        mutated = True

    if mutated:
        element["htmlContent"] = str(soup)
        return True

    # No inline mutation happened — restore the cleaned (no aesthetic-fix
    # tags) html anyway so prior injected styles don't linger.
    if html != element.get("htmlContent"):
        element["htmlContent"] = html
        return True
    return False


def _apply_style_fix(element: dict, slide: dict, changes: dict) -> bool:
    """Apply style changes WITH WCAG enforcement and automatic plate insertion.

    Returns True if any change was applied. Mutates `element` in place.

    Defense-in-depth (2026-05-18): even when the suggestion is purely about
    font-size or layout, we ALWAYS recheck the element's current fontColor
    against the effective background. If contrast is below WCAG AA (4.5:1),
    we silently force a high-contrast color. This catches the case the user
    reported — applying a "Fontes" suggestion on a slide where the text is
    white-on-white doesn't visually change anything because the change set
    only had fontSize. Now we sweep the color too.
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

    # ------------------------------------------------------------------
    # POST-FIX CONTRAST SWEEP (defense in depth)
    # Even if the suggestion didn't include fontColor, the SLIDE itself
    # might have invisible text. Whenever we touch ANY textual element
    # we also verify its current fontColor against the effective background.
    # ------------------------------------------------------------------
    is_textual = (
        element.get("type") in ("text", "html", "paragraph", "title", "heading")
        or element.get("content")
        or element.get("htmlContent")
    )
    if is_textual:
        current_color = style.get("fontColor") or style.get("color") or "#000000"
        try:
            ratio = wcag.contrast_ratio(current_color, bg_color)
        except Exception:
            ratio = 99.0  # be permissive when parsing fails
        if ratio < 4.5:
            # On busy backgrounds we always go to LIGHT (paired with a plate
            # below). On solid backgrounds we pick the polarity that wins.
            if has_image:
                forced = wcag.LIGHT_FALLBACK
            else:
                forced = wcag.pick_high_contrast_color(bg_color)
            if forced != current_color:
                style["fontColor"] = forced
                style["color"] = forced  # keep both keys in sync for renderers
                applied_any = True
            # For HTML-bearing elements (slides built by the AI Agent often
            # use type='html' with inline `<p style="color:#fff">`), the
            # style.fontColor change alone won't reach those nested inline
            # rules. Inject an override CSS rule with !important to defeat
            # them. _apply_html_style_fix is idempotent (strips prior
            # aesthetic-fix tags before injecting).
            if element.get("htmlContent"):
                override_css = (
                    f"body, body *, p, h1, h2, h3, h4, h5, h6, span, li, td, th, "
                    f"div {{ color: {forced if forced != current_color else style.get('fontColor', '#0f172a')} !important; }}"
                )
                _apply_html_style_fix(
                    element,
                    override_css,
                    target_color=style.get("fontColor"),
                    preserve_html_typography=False,
                )
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

    # ------------------------------------------------------------------
    # HTML INLINE STYLE PROPAGATION (the real fix for the user's bug)
    # When the element renders htmlContent inside an iframe, mutations to
    # element.style.fontSize / fontWeight / fontColor are INVISIBLE because
    # the iframe shows the inline `<h2 style="font-size:31px;color:#fff">`.
    # Rewrite those inline rules so the visible content actually changes.
    # ------------------------------------------------------------------
    if element.get("type") == "html" and element.get("htmlContent"):
        # Build the effective change set, prefering style.* values that have
        # already been validated/forced above (e.g., post-sweep enforced color).
        effective_changes = {
            "fontSize": style.get("fontSize") if "fontSize" in (changes or {}) else None,
            "fontWeight": style.get("fontWeight") if "fontWeight" in (changes or {}) else None,
            "fontColor": style.get("fontColor") if ("fontColor" in (changes or {}) or "fontColor" in style) else None,
        }
        # Drop None entries to keep semantics tight.
        effective_changes = {k: v for k, v in effective_changes.items() if v is not None}
        if effective_changes:
            if _propagate_style_to_html_content(element, effective_changes, slide):
                applied_any = True

        # BACKGROUND-IMAGE PLATE for html elements on busy slides.
        # Runs independently of font changes — any style fix that touches
        # an html element on a slide WITH backgroundImage should also
        # guarantee the content sits on a known readable backdrop.
        if applied_any and has_image:
            if _inject_html_bg_plate(element, slide):
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


def _extract_dominant_html_bg(html: str):
    """Inspect the htmlContent of a simulator/quiz/scenario to detect the
    DOMINANT background color the user actually sees. Returns a CSS color
    string (`#fff`, `rgb(...)`, etc.) or None when undetectable.

    Strategy (in priority order):
      1. body { background[-color]: ... } in any <style> block
      2. <body style="background[-color]: ..."> inline
      3. The first inline `background[-color]` on a top-level container
         (.container, main, .wrapper, .card, .game-container, etc.) — these
         are the visible "page" of the simulator.
      4. None.

    Why this matters:
        Earlier the Analyzer injected `body,body * {color:#fff !important}`
        regardless of the simulator's INTERNAL background. Simulators built
        by the AI Agent often use `body{background:#fff}` so they look like
        clean white cards on top of the dark slide. Forcing white text on
        white background made everything invisible.
    """
    if not html:
        return None

    # 1. <style>...body { background: X }...</style>
    for m in re.finditer(r"<style[^>]*>([\s\S]*?)</style>", html, re.IGNORECASE):
        block = m.group(1)
        bg_match = re.search(
            r"\bbody\s*\{[^}]*?\bbackground(?:-color)?\s*:\s*([^;}]+)",
            block,
            re.IGNORECASE,
        )
        if bg_match:
            val = bg_match.group(1).strip().rstrip(';').strip()
            if val and "gradient" not in val.lower() and "url(" not in val.lower():
                return val

    # 2. <body style="background: X">
    body_inline = re.search(r"<body[^>]*\bstyle\s*=\s*[\"']([^\"']*)[\"']", html, re.IGNORECASE)
    if body_inline:
        bg_match = re.search(
            r"\bbackground(?:-color)?\s*:\s*([^;]+)",
            body_inline.group(1),
            re.IGNORECASE,
        )
        if bg_match:
            val = bg_match.group(1).strip()
            if val and "gradient" not in val.lower() and "url(" not in val.lower():
                return val

    # 3. First top-level container with inline bg
    m = re.search(
        r"<(?:div|main|section|article)\b[^>]*class\s*=\s*[\"'][^\"']*(?:container|wrapper|card|game|app|main|content)[^\"']*[\"'][^>]*\bstyle\s*=\s*[\"']([^\"']*)[\"']",
        html,
        re.IGNORECASE,
    )
    if m:
        bg_match = re.search(r"\bbackground(?:-color)?\s*:\s*([^;]+)", m.group(1), re.IGNORECASE)
        if bg_match:
            val = bg_match.group(1).strip()
            if val and "gradient" not in val.lower() and "url(" not in val.lower():
                return val

    return None


# Pattern that matches a single CSS rule (selector list + declaration block).
_CSS_RULE_RE = re.compile(r"([^{}]+)\{([^{}]*)\}", re.MULTILINE)
_DECL_RE = re.compile(r"([a-zA-Z\-]+)\s*:\s*([^;]+?)(?:!important)?\s*(?:;|$)", re.IGNORECASE)


def _parse_html_css_rules(html: str):
    """Extract every CSS rule from <style> blocks in the htmlContent.

    Returns a list of dicts: [{"selector": "...", "color": "#fff",
    "background": "#e6e9ff"}]. Multiple rules with the same selector are
    merged into a single record.
    """
    if not html or "<style" not in html.lower():
        return []

    by_selector = {}
    for sm in re.finditer(r"(<style[^>]*>)([\s\S]*?)</style>", html, re.IGNORECASE):
        opening = sm.group(1)
        block = sm.group(2)
        if 'data-aesthetic-fix' in opening:
            continue
        block_clean = re.sub(r"/\*[\s\S]*?\*/", "", block)
        for r in _CSS_RULE_RE.finditer(block_clean):
            selectors = r.group(1).strip()
            decls = r.group(2)
            if selectors.lstrip().startswith("@"):
                continue
            color = None
            bg = None
            for d in _DECL_RE.finditer(decls):
                prop = d.group(1).lower().strip()
                val = d.group(2).strip()
                if prop == "color":
                    color = val
                elif prop in ("background-color", "background"):
                    if "gradient" in val.lower() or "url(" in val.lower():
                        continue
                    first = val.split()[0] if val else val
                    if first:
                        bg = first
            if not color and not bg:
                continue
            for sel in [s.strip() for s in selectors.split(",") if s.strip()]:
                rec = by_selector.setdefault(sel, {"selector": sel, "color": None, "background": None})
                if color and not rec["color"]:
                    rec["color"] = color
                if bg and not rec["background"]:
                    rec["background"] = bg
    return list(by_selector.values())


def _resolve_background_for_selector(rules, sel: str, fallback=None):
    """Best-effort: walk descendant chain to find an effective background.
    For `.card .child`, look up `.card` (parent) if `.child` has no bg.
    """
    rec = next((r for r in rules if r["selector"] == sel), None)
    if rec and rec.get("background"):
        return rec["background"]

    parts = re.split(r"\s+|\s*>\s*|\s*\+\s*|\s*~\s*", sel.strip())
    parts = [p for p in parts if p]
    while len(parts) > 1:
        parts = parts[:-1]
        parent_sel = " ".join(parts)
        rec = next((r for r in rules if r["selector"] == parent_sel), None)
        if rec and rec.get("background"):
            return rec["background"]

    if parts:
        head = parts[0]
        rec = next((r for r in rules if r["selector"] == head), None)
        if rec and rec.get("background"):
            return rec["background"]

    return fallback


def _auto_fix_html_contrast(html: str) -> str:
    """Static analysis of the simulator's <style> blocks to find rules with
    bad WCAG contrast and emit a TARGETED override CSS. Does NOT depend on
    LLM correctness — works deterministically from the htmlContent.

    For each rule with `color: X`, we compute the effective background
    (from the same selector OR an ancestor selector OR the body bg).
    If contrast < 4.5 (WCAG AA), we emit `selector { color: <opposite-polarity> !important }`.
    """
    if not html:
        return ""

    rules = _parse_html_css_rules(html)
    if not rules:
        return ""

    body_bg = _extract_dominant_html_bg(html) or "#ffffff"

    overrides = []
    seen = set()
    for rec in rules:
        color = rec.get("color")
        if not color:
            continue
        sel = rec["selector"].strip()
        if sel in ("*", "body *", "body", "html") or "[style*=" in sel:
            continue

        bg = _resolve_background_for_selector(rules, sel, fallback=body_bg)
        try:
            ratio = wcag.contrast_ratio(color, bg)
        except Exception:
            continue
        if ratio >= 4.5:
            continue

        new_color = wcag.pick_high_contrast_color(bg)
        if sel in seen:
            continue
        seen.add(sel)
        overrides.append(f"{sel} {{ color: {new_color} !important }}")

    return " ".join(overrides)


def _strip_universal_selectors(css: str) -> str:
    """Remove rule blocks whose selector list contains any UNIVERSAL or
    overreaching selector. Used in `preserve_html_typography=True` mode to
    prevent the LLM's broad rules from destroying contrast inside nested
    cards/buttons of HTML-pesado simulators.

    Rules dropped:
      - `* { ... }`           → universal
      - `body * { ... }`      → ditto, scoped to body
      - `body { ... }`        → unscoped body color/bg overrides
      - `[style*="color"]`    → matches every inline-styled element
      - `html, body { ... }`  → ditto

    Rules kept (targeted):
      - Class selectors: `.option-btn { ... }`
      - ID selectors: `#prompt { ... }`
      - Specific tags inside body: `body label { ... }`, `body p.error { ... }`

    Strategy: tokenize at `}`, inspect each rule's selector list. If any
    selector is dangerous, drop the whole rule.
    """
    if not css or "{" not in css:
        return css

    DANGEROUS = re.compile(
        r"""(
            ^\s*\*\s*$              # bare *
            |^\s*body\s*\*\s*$      # body *
            |^\s*body\s*$           # bare body
            |^\s*html\s*$           # bare html
            |^\s*html\s*,\s*body\s*$
            |\[style\s*\*=          # any [style*=...] selector
        )""",
        re.IGNORECASE | re.VERBOSE,
    )

    safe_rules = []
    # Walk through CSS one rule at a time. Use a small parser to handle
    # potential nested braces in modern CSS (we don't expect them here, but
    # be defensive).
    i = 0
    while i < len(css):
        # Find next `{`
        brace = css.find("{", i)
        if brace < 0:
            break
        selectors = css[i:brace].strip().rstrip(",").rstrip()
        # Find matching `}`
        depth = 1
        j = brace + 1
        while j < len(css) and depth > 0:
            if css[j] == "{":
                depth += 1
            elif css[j] == "}":
                depth -= 1
            j += 1
        block = css[brace + 1:j - 1]

        # Split selector list by comma; drop the whole rule if ANY selector
        # is dangerous.
        sel_list = [s.strip() for s in selectors.split(",") if s.strip()]
        if sel_list and not any(DANGEROUS.search(sel) for sel in sel_list):
            safe_rules.append(f"{selectors} {{{block}}}")

        i = j

    return " ".join(safe_rules)


def _strengthen_css_injection(css: str, target_text_color: str = None, preserve_html_typography: bool = False, html_bg=None) -> str:
    """Wrap LLM-provided CSS with !important and aggressive selectors so
    inline styles inside the HTML element cannot win specificity.

    If `target_text_color` is provided, append a universal color override —
    BUT FIRST we validate that the color makes sense against `html_bg` (the
    simulator's internal background). If `target_text_color` would make text
    INVISIBLE (contrast < 4.5:1), we flip it to the opposite polarity. This
    is what fixes the "all text turned invisible" bug.

    When `preserve_html_typography=True` (used for HTML-heavy slides with
    simulators built by the AI Agent), absolute pixel font-size declarations
    are converted to relative `em` units so the simulator's internal
    typography hierarchy is preserved. We also use a NARROWER selector that
    skips elements with their own background (intentional cards/buttons).
    """
    css = (css or "").strip()

    # Sanity-check the proposed text color against the simulator's actual
    # background. If contrast fails AA, swap to the opposite polarity.
    if target_text_color and html_bg:
        try:
            ratio = wcag.contrast_ratio(target_text_color, html_bg)
            if ratio < 4.5:
                target_text_color = wcag.pick_high_contrast_color(html_bg)
        except Exception:
            pass

    # When preserving typography, convert `font-size: Npx` into a tiny
    # relative bump (1.05em) — keeps the simulator's hierarchy but nudges
    # for borderline cases. If the value is already em/rem/%, leave it.
    if preserve_html_typography and css:
        def _scale_font_size(m):
            val = m.group(2).strip().lower()
            if val.endswith(("em", "rem", "%")):
                return m.group(0)
            return f"{m.group(1)}: 1.05em"
        css = re.sub(
            r"(font-size)\s*:\s*([\d.]+\s*[a-z%]*)",
            _scale_font_size,
            css,
            flags=re.IGNORECASE,
        )
        # Strip padding/margin/line-height directives — these belong to the
        # simulator's design language. The analyzer should never touch them.
        css = re.sub(
            r"\b(padding|margin|line-height)\s*:\s*[^;{}]+;?",
            "",
            css,
            flags=re.IGNORECASE,
        )
        # CRITICAL: strip overreaching universal selectors. The LLM often
        # emits `body * { color: #fff }` which destroys contrast in
        # multi-context simulators (white prompt cards on dark body, cyan
        # buttons with dark text). In preserve mode we ONLY allow targeted
        # selectors that name a class or specific element type — universal
        # selectors are dropped wholesale.
        css = _strip_universal_selectors(css)

    parts = []
    if css.strip():
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
        if preserve_html_typography:
            # In preserve mode (HTML-pesado simulators) we DO NOT inject any
            # universal color override at all. Even narrow selectors like
            # `body p` cascade onto <p> tags nested inside white prompt
            # cards (where the card has the background, not the <p>) and
            # turn the text invisible.
            #
            # The LLM-provided css already passed through
            # `_strip_universal_selectors` so any safe (class/id-targeted)
            # rules survive on their own. If the LLM only knows how to
            # propose universal rules, NOTHING is injected — preserving
            # the simulator's intentional contrast.
            pass
        else:
            parts.append(
                f"body,body *,body p,body span,body div,body li,body td,body th{{color:{target_text_color} !important}}"
                f"[style*=\"color\"]{{color:{target_text_color} !important}}"
            )

    return " ".join(parts)

# Pattern matching ALL accumulated aesthetic-fix style tags (with optional
# whitespace inside the attribute and possibly minified content).
_AESTHETIC_FIX_TAG_RE = re.compile(
    r'<style\s+data-aesthetic-fix\s*=\s*[\"\']1[\"\']\s*>[\s\S]*?</style>',
    re.IGNORECASE,
)

# Pattern matching `data-aesthetic-plate="1"` attributes that we add to
# text blocks during surgical-plate injection. Stripping these on cleanup
# keeps the htmlContent reversible.
_AESTHETIC_PLATE_ATTR_RE = re.compile(
    r'\s+data-aesthetic-plate\s*=\s*[\"\']1[\"\']',
    re.IGNORECASE,
)


def _clean_aesthetic_fixes_from_html(html: str) -> str:
    """Remove every `<style data-aesthetic-fix="1">...</style>` tag AND
    every `data-aesthetic-plate="1"` marker that earlier Aesthetic
    Analyzer runs may have injected.

    This is what makes the apply pipeline IDEMPOTENT: re-running with the
    same (or different) fix sequence does not accumulate broken CSS rules
    from previous attempts.
    """
    if not html:
        return html
    if "data-aesthetic-fix" not in html and "data-aesthetic-plate" not in html:
        return html
    html = _AESTHETIC_FIX_TAG_RE.sub("", html)
    html = _AESTHETIC_PLATE_ATTR_RE.sub("", html)
    return html


def _apply_html_style_fix(element: dict, css: str, target_color: str = None, preserve_html_typography: bool = False) -> bool:
    """Inject CSS into an HTML element's htmlContent with maximum specificity.

    Strategy: wrap the CSS with !important on every declaration and append a
    universal color override that defeats inline styles. Insert as the
    LAST <style> tag so it wins over earlier <style> blocks.

    When `preserve_html_typography=True`, refuses to inject px-based
    font-size / padding / margin rules — these would break the simulator's
    internal design language built by the AI Agent.

    The simulator's INTERNAL background is detected from htmlContent via
    `_extract_dominant_html_bg` and used to validate `target_color`. If the
    LLM proposes a color that fails WCAG against that background, we flip
    polarity so text never becomes invisible.

    BEFORE injecting the new fix, all PREVIOUS aesthetic-fix style tags
    are removed so re-running the analyzer does not pile on broken rules.
    """
    html = element.get("htmlContent") or ""
    if not html or not (css or target_color):
        return False

    # IDEMPOTENT: strip any prior aesthetic-fix tags first.
    html = _clean_aesthetic_fixes_from_html(html)

    # Detect the simulator's actual visible background — this is what
    # determines whether `target_color` should be light or dark.
    html_bg = _extract_dominant_html_bg(html)

    final_css = _strengthen_css_injection(
        css,
        target_text_color=target_color,
        preserve_html_typography=preserve_html_typography,
        html_bg=html_bg,
    )
    if not final_css:
        # Even though no new fix was injected, we may have stripped older
        # aesthetic-fix tags above — persist the cleaned html so leftover
        # bad rules from prior runs disappear.
        original = element.get("htmlContent") or ""
        if html != original:
            element["htmlContent"] = html
            return True
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

    # Snapshot the BEFORE state so the user can revert if they don't like
    # the result. We only keep the last snapshot per project — earlier ones
    # are overwritten. Stored as a deepcopy of `course.slides` (the only
    # field the analyzer mutates).
    import copy as _copy
    snapshot_slides = _copy.deepcopy(project.get("course", {}).get("slides", []))

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
                # For HTML-heavy slides (simulators built by the AI Agent),
                # preserve internal typography — don't let the analyzer
                # impose absolute pixel sizes on intentional design.
                slide_role = _classify_slide(slide, slide_idx, len(slides))
                preserve_typo = slide_role == "html_heavy"
                if _apply_html_style_fix(
                    element, css,
                    target_color=target_color,
                    preserve_html_typography=preserve_typo,
                ):
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
        # Persist the snapshot AFTER successful update so user can revert.
        await db.aesthetic_snapshots.update_one(
            {"projectId": project_id},
            {"$set": {
                "projectId": project_id,
                "slidesBefore": snapshot_slides,
                "appliedCount": applied,
                "appliedAt": datetime.now(timezone.utc).isoformat(),
                "userId": user.get("user_id", ""),
            }},
            upsert=True
        )

    return {"applied": applied, "total": len(to_apply), "message": f"{applied} correcoes aplicadas", "canRevert": applied > 0}


@router.post("/aesthetics/revert/{project_id}")
async def revert_aesthetic_fix(project_id: str, user: dict = Depends(require_auth)):
    """Revert the last apply-fix run by restoring the snapshot saved before it."""
    project = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(404, "Project not found")

    snapshot = await db.aesthetic_snapshots.find_one({"projectId": project_id}, {"_id": 0})
    if not snapshot or "slidesBefore" not in snapshot:
        raise HTTPException(400, "Nenhum snapshot disponivel para reverter")

    await db.projects.update_one(
        {"id": project_id},
        {"$set": {
            "course.slides": snapshot["slidesBefore"],
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        }}
    )
    # Single-shot revert — delete the snapshot so the button disappears in UI.
    await db.aesthetic_snapshots.delete_one({"projectId": project_id})

    return {"reverted": True, "message": "Alteracoes esteticas revertidas com sucesso"}


@router.get("/aesthetics/snapshot-status/{project_id}")
async def aesthetic_snapshot_status(project_id: str, user: dict = Depends(require_auth)):
    """Lightweight check: is there a revertible snapshot for this project?
    Frontend uses this on panel mount to decide whether to show the
    'Reverter' button (e.g., after a refresh)."""
    snapshot = await db.aesthetic_snapshots.find_one(
        {"projectId": project_id},
        {"_id": 0, "appliedAt": 1, "appliedCount": 1}
    )
    if not snapshot:
        return {"hasSnapshot": False}
    return {
        "hasSnapshot": True,
        "appliedAt": snapshot.get("appliedAt"),
        "appliedCount": snapshot.get("appliedCount", 0),
    }


@router.post("/aesthetics/deep-clean/{project_id}")
async def deep_clean_aesthetic_fixes(project_id: str, user: dict = Depends(require_auth)):
    """Strip ALL accumulated `<style data-aesthetic-fix="1">` tags from
    every HTML element in every slide of the project.

    This is the escape hatch for projects whose simulators were corrupted
    by repeated applies of older Analyzer versions (each apply piled on
    new tags without removing prior ones, so universal `body * {color:#fff}`
    rules accumulated and made text invisible). After deep-clean, the
    simulators return to the state the AI Agent originally produced.

    Also takes a snapshot first so this action itself can be reverted.
    """
    project = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(404, "Project not found")

    slides = (project.get("course") or {}).get("slides") or []
    if not slides:
        return {"cleaned": 0, "message": "Nenhum slide para limpar"}

    # Snapshot before — so user can revert if anything goes wrong
    import copy as _copy
    snapshot_slides = _copy.deepcopy(slides)

    cleaned_count = 0
    for slide in slides:
        for el in slide.get("elements", []) or []:
            if el.get("type") != "html":
                continue
            html = el.get("htmlContent") or ""
            if "data-aesthetic-fix" not in html:
                continue
            new_html = _clean_aesthetic_fixes_from_html(html)
            if new_html != html:
                el["htmlContent"] = new_html
                cleaned_count += 1

    if cleaned_count == 0:
        return {"cleaned": 0, "message": "Nada a limpar - nenhuma marcacao do analisador encontrada"}

    await db.projects.update_one(
        {"id": project_id},
        {"$set": {
            "course.slides": slides,
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        }}
    )
    await db.aesthetic_snapshots.update_one(
        {"projectId": project_id},
        {"$set": {
            "projectId": project_id,
            "slidesBefore": snapshot_slides,
            "appliedCount": cleaned_count,
            "appliedAt": datetime.now(timezone.utc).isoformat(),
            "userId": user.get("user_id", ""),
            "kind": "deep_clean",
        }},
        upsert=True
    )

    return {
        "cleaned": cleaned_count,
        "message": f"{cleaned_count} simulador(es) HTML limpo(s) com sucesso",
        "canRevert": True,
    }


@router.post("/aesthetics/auto-fix-contrast/{project_id}")
async def auto_fix_html_contrast(project_id: str, user: dict = Depends(require_auth)):
    """Deterministic, LLM-independent contrast auto-fix for ALL HTML
    simulators in the project.

    For every `<style>` block inside every HTML element, parses the CSS
    rules and computes WCAG ratio for each `color` value against its
    effective background. When ratio < 4.5 (AA fail), emits a TARGETED
    override `selector { color: <opposite-polarity> !important }`.

    This is the escape hatch when the LLM keeps suggesting universal
    selectors that get stripped — we don't need the LLM at all here.
    A snapshot is taken first so the action is revertible.
    """
    project = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(404, "Project not found")

    slides = (project.get("course") or {}).get("slides") or []
    if not slides:
        return {"fixed": 0, "message": "Nenhum slide para analisar"}

    import copy as _copy
    snapshot_slides = _copy.deepcopy(slides)

    fixed_count = 0
    issues_total = 0
    for slide in slides:
        for el in slide.get("elements", []) or []:
            if el.get("type") != "html":
                continue
            html = el.get("htmlContent") or ""
            if not html:
                continue

            # First, strip any existing aesthetic-fix tags to start fresh
            cleaned = _clean_aesthetic_fixes_from_html(html)

            # Analyze the cleaned html for contrast failures
            override_css = _auto_fix_html_contrast(cleaned)
            if not override_css:
                # No issues found in this simulator
                if cleaned != html:
                    el["htmlContent"] = cleaned
                    fixed_count += 1
                continue

            # Inject the targeted override
            new_html = cleaned
            style_tag = f'<style data-aesthetic-fix="1">{override_css}</style>'
            if "</head>" in new_html:
                new_html = new_html.replace("</head>", f"{style_tag}</head>", 1)
            elif "</body>" in new_html:
                new_html = new_html.replace("</body>", f"{style_tag}</body>", 1)
            else:
                new_html = f"{style_tag}{new_html}"
            el["htmlContent"] = new_html
            fixed_count += 1
            # Count overrides emitted (rough proxy for issues fixed)
            issues_total += override_css.count("{ color")

    if fixed_count == 0:
        return {
            "fixed": 0,
            "issuesFixed": 0,
            "message": "Nenhum problema de contraste detectado nos simuladores",
        }

    await db.projects.update_one(
        {"id": project_id},
        {"$set": {
            "course.slides": slides,
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        }}
    )
    await db.aesthetic_snapshots.update_one(
        {"projectId": project_id},
        {"$set": {
            "projectId": project_id,
            "slidesBefore": snapshot_slides,
            "appliedCount": fixed_count,
            "appliedAt": datetime.now(timezone.utc).isoformat(),
            "userId": user.get("user_id", ""),
            "kind": "auto_fix_contrast",
        }},
        upsert=True
    )

    return {
        "fixed": fixed_count,
        "issuesFixed": issues_total,
        "message": f"{issues_total} regra(s) de contraste corrigida(s) em {fixed_count} simulador(es)",
        "canRevert": True,
    }
