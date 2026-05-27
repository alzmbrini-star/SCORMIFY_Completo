"""Conversational chat for the Editor — lets the author tweak a published
course via natural language instead of clicking around.

The LLM translates intent into structured ops that mutate `project.course.slides`
directly in MongoDB. Mirrors the Storyboard chat architecture but uses the
full Editor schema (elements with `style`, positions, etc.).
"""
import os
import re
import json
import uuid
import logging
import copy as _copy
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from routes.deps import db
from routes.auth import require_auth

logger = logging.getLogger("server")
router = APIRouter(tags=["Editor Chat"])

SYSTEM_PROMPT = """Voce e um assistente conversacional de edicao de cursos e-learning.

O autor te pede alteracoes em linguagem natural sobre um curso JA PUBLICADO. Sua tarefa:
1. Interpretar a intencao.
2. Gerar RESPOSTA amigavel em portugues explicando o que vai fazer.
3. Gerar lista ESTRUTURADA de operacoes que o backend aplica atomicamente.

## Tipos de operacao suportados
- `edit_slide_title`: {slideIndex: int, title: str}
- `edit_element_content`: {slideIndex: int, elementIndex: int, content: str}
- `edit_element_style`: {slideIndex: int, elementIndex: int, style: {fontColor?, fontSize?, fontWeight?, textAlign?, fontFamily?}}
- `add_text_element`: {slideIndex: int, content: str, x?: number, y?: number, width?: number, height?: number, fontSize?: int, fontColor?: str}
- `add_slide`: {insertAfter: int, count?: int (default 1, max 20), title?: str, content?: str, background?: "#hex", narrationScript?: str, useBrandBackground?: bool, brandAssetId?: str}
   - Use SEMPRE que o autor pedir "adicionar slide", "inserir slide", "criar slide", "novo slide" etc.
   - `insertAfter` e o slideIndex (0-based) APOS o qual inserir. Para inserir no inicio use -1; para inserir no fim use o ultimo indice.
   - Se o autor pedir "adicione N slides" / "insira N slides", use `count: N` (max 20 por seguranca).
   - Quando `count > 1` e `title` for fornecido, o backend numera automaticamente: "Title 1", "Title 2", etc.
   - `content` e opcional — se fornecido vira um paragrafo do corpo do slide.
   - `background` herda do slide anterior se omitido.
   - `useBrandBackground: true` → o backend usa o PRIMEIRO background da Biblioteca de Marca da empresa (se houver). Use quando o autor pedir "fundo da marca", "background da empresa", "imagem da marca".
   - `brandAssetId` → use o ID exato de um asset listado em BIBLIOTECA DE MARCA quando o autor mencionar por nome/categoria (ex: "use o fundo 'Capa Corporativa'").
- `set_slide_background_image`: {slideIndex: int, brandAssetId?: str, imageUrl?: str, clear?: bool}
   - Define a imagem de fundo de UM slide. Use `brandAssetId` para puxar da Biblioteca de Marca. `clear: true` remove o backgroundImage.
- `apply_brand_background`: {brandAssetId?: str, fromIndex?: int, toIndex?: int, allSlides?: bool}
   - Propaga um background de marca para MULTIPLOS slides. Sem `brandAssetId`, usa o primeiro `background` da biblioteca.
   - `allSlides: true` aplica em TODOS os slides do curso.
   - Ou use `fromIndex`/`toIndex` (inclusive) para um intervalo (ex: slides 2 a 5 → fromIndex=1, toIndex=4).
- `apply_brand_palette`: {target?: "primary"|"accent"|"secondary", fromIndex?: int, toIndex?: int, allSlides?: bool, clearBackgroundImage?: bool}
   - Aplica a PALETA da marca: pinta `slide.background` com a cor escolhida do BrandKit e atualiza `fontColor` de TODOS os elementos de texto para garantir contraste WCAG AA.
   - `target` (default "primary"): qual cor da paleta usar. "accent" e "secondary" tambem aceitos.
   - `clearBackgroundImage: true` remove qualquer imagem de fundo dos slides afetados (volta para a cor solida da paleta).
   - Default e aplicar em TODOS os slides. Use `fromIndex`/`toIndex` para um intervalo.
   - Se o autor pedir "aplique a fonte da marca", use essa op (a fontFamily do BrandKit e aplicada automaticamente nos textos).
- `apply_brand_identity`: {brandAssetId?, paletteTarget?, fromIndex?, toIndex?, allSlides?, applyBackground?:bool, applyPalette?:bool, applyLogo?:bool, logoCorner?: "top-right"|"top-left"|"bottom-right"|"bottom-left"|"bottom-center", logoSize?: int|"small"|"medium"|"large"}
   - **Op combinada / "Identidade Visual Completa" / "Brand Kit Completo"**: aplica de uma so vez (1) fundo de marca (imagem da biblioteca) + (2) paleta (cor + fonte) + (3) logo como marca d'agua no canto.
   - Use SEMPRE que o autor pedir "aplique a identidade visual", "marca completa", "identidade da empresa", "aplicar branding", **"aplique o brand kit"**, **"brand kit completo"**, **"kit completo da marca"**, **"kit da empresa"**.
   - Todos os 3 componentes ativos por padrao. Para desligar algum: `applyLogo:false` (so cores+fundo), `applyBackground:false` (so cores+logo), etc.
   - **CRITICO**: NUNCA inclua `logoCorner` no op a menos que o autor mencione EXPLICITAMENTE um canto/posicao (ex: "canto inferior direito", "no topo", "centralizado"). Caso contrario, omita o campo — o backend usa a posicao configurada pelo super admin no BrandKit (`logoPlacement`).
   - **CRITICO**: NUNCA inclua `logoSize` no op a menos que o autor mencione EXPLICITAMENTE um tamanho (ex: "logo grande", "logo pequeno", "logo de 200px"). Caso contrario, omita — o backend usa o tamanho configurado no BrandKit.
   - Funciona em todos os slides por default; use `fromIndex`/`toIndex` para um intervalo.
- `delete_element`: {slideIndex: int, elementIndex: int}
- `change_slide_background`: {slideIndex: int, background: "#hex"}
- `move_slide`: {fromIndex: int, toIndex: int}
- `delete_slide`: {slideIndex: int}

## Regras
- Indices sao 0-based internamente. O usuario fala "slide 3" (1-based), voce converte para 2.
- Cores: use HEX `#rrggbb`. Se o usuario disser "mais escuro", escolha tons apropriados.
- Se a instrucao for ambigua, retorne ops=[] e peca esclarecimento no reply.
- Para `add_text_element` sem coordenadas explicitas, use x=100, y=100, width=600, height=60, fontSize=20.
- NAO regere imagens ou audio (isso e feito em outra interface).
- NAO altere elementos tipo html/quiz/scenario diretamente (estruturas complexas).
- **PROIBIDO** propor `backgroundColor`, `textBackgroundColor`, `padding`, `borderRadius`, `boxShadow`, `textShadow` em `style` — o usuario rejeitou plates/overlays atras do texto. Para resolver contraste sobre imagens, mude APENAS `fontColor` (preto `#0f172a` ou branco `#f8fafc`).
- Se a BIBLIOTECA DE MARCA estiver vazia e o autor pedir "fundo da marca", responda no `reply` que a empresa ainda nao tem backgrounds cadastrados e nao gere ops.

## Exemplos de inserir slides
- "Adicione 5 slides em branco no fim" → 1 op: `{"type":"add_slide","insertAfter":<ultimo_index>,"count":5,"title":"Novo Slide"}`
- "Insira 3 slides depois do slide 2" → 1 op: `{"type":"add_slide","insertAfter":1,"count":3}`
- "Crie um slide sobre Segurança no Trabalho após o slide 4" → 1 op: `{"type":"add_slide","insertAfter":3,"title":"Segurança no Trabalho","content":"Pontos principais sobre seguranca no ambiente de trabalho..."}`

## Exemplos com Biblioteca de Marca
- "Aplique o fundo da marca em todos os slides" → 1 op: `{"type":"apply_brand_background","allSlides":true}`
- "Crie 3 slides com fundo da marca da empresa" → 1 op: `{"type":"add_slide","insertAfter":<ultimo>,"count":3,"useBrandBackground":true}`
- "Use o fundo Capa Corporativa em todos os slides" → 1 op com `brandAssetId` do asset cujo nome/categoria casa com "Capa Corporativa": `{"type":"apply_brand_background","brandAssetId":"casset_xxx","allSlides":true}`
- "Coloque o fundo da marca nos slides 2 ao 5" → 1 op: `{"type":"apply_brand_background","fromIndex":1,"toIndex":4}`

## Exemplos com Paleta de Marca (cores + fonte)
- "Aplique a paleta da marca em todos os slides" → 1 op: `{"type":"apply_brand_palette","allSlides":true}`
- "Use a cor de destaque (accent) da marca como fundo" → 1 op: `{"type":"apply_brand_palette","allSlides":true,"target":"accent"}`
- "Aplique as cores da marca e remova imagens de fundo" → 1 op: `{"type":"apply_brand_palette","allSlides":true,"clearBackgroundImage":true}`
- "Aplique a fonte da marca em todos os slides" → 1 op: `{"type":"apply_brand_palette","allSlides":true}` (a fonte do BrandKit e aplicada junto com a cor)

## Exemplos com Identidade Visual Completa (combinado)
- "Aplique a identidade visual completa da empresa" → 1 op: `{"type":"apply_brand_identity","allSlides":true}`
- "Aplique o branding da empresa neste curso" → 1 op: `{"type":"apply_brand_identity","allSlides":true}`
- "Aplique o brand kit completo para todos os slides" → 1 op: `{"type":"apply_brand_identity","allSlides":true}`
- "Aplique o kit da marca completo" → 1 op: `{"type":"apply_brand_identity","allSlides":true}`
- "Coloque a marca completa, mas sem o logo" → 1 op: `{"type":"apply_brand_identity","allSlides":true,"applyLogo":false}`
- "Aplique a identidade nos slides 2 a 5 com logo no canto inferior direito" → 1 op: `{"type":"apply_brand_identity","fromIndex":1,"toIndex":4,"logoCorner":"bottom-right"}`
- "Aplique a marca com logo grande no canto inferior direito" → 1 op: `{"type":"apply_brand_identity","allSlides":true,"logoCorner":"bottom-right","logoSize":"large"}`
- "Aplique a identidade visual com o logo pequeno" → 1 op: `{"type":"apply_brand_identity","allSlides":true,"logoSize":"small"}`
- "Coloque o branding com logo de 200px" → 1 op: `{"type":"apply_brand_identity","allSlides":true,"logoSize":200}`

## Formato JSON estrito
```json
{
  "reply": "Vou mudar o titulo do slide 3 e adicionar uma caixa de texto com sua observacao.",
  "ops": [
    {"type": "edit_slide_title", "slideIndex": 2, "title": "Novo Titulo"},
    {"type": "add_text_element", "slideIndex": 2, "content": "Observacao importante"}
  ]
}
```
Se nao entender, retorne ops=[] com reply pedindo esclarecimento.
"""


def _build_course_summary(slides: list) -> list:
    """Compact summary for the LLM — titles + first N chars of each element."""
    summary = []
    for i, sl in enumerate(slides):
        els_brief = []
        for ei, el in enumerate((sl.get("elements") or [])[:10]):
            t = el.get("type", "")
            # Skip binary-heavy fields (html, scenarios, quiz) — LLM can't
            # safely edit those and including them bloats the prompt.
            if t in ("html", "scenario", "quiz"):
                els_brief.append({"i": ei, "type": t, "summary": "(interactive, not editable via chat)"})
                continue
            c = (el.get("content") or "")[:200]
            els_brief.append({"i": ei, "type": t, "content": c})
        summary.append({
            "index": i,
            "title": sl.get("title", ""),
            "background": sl.get("background", "#ffffff"),
            "elements": els_brief,
        })
    return summary


async def _call_llm(system_prompt: str, user_prompt: str, session_key: str) -> str:
    """Call the LLM with automatic fallback gemini → openai."""
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    emergent_key = os.environ.get("EMERGENT_LLM_KEY", "")
    for provider, model in (("gemini", "gemini-3-flash-preview"), ("openai", "gpt-4o")):
        try:
            chat = LlmChat(
                api_key=emergent_key,
                session_id=f"{session_key}_{uuid.uuid4().hex[:6]}",
                system_message=system_prompt,
            ).with_model(provider, model)
            return await chat.send_message(UserMessage(text=user_prompt))
        except Exception as e:
            logger.warning(f"editor_chat LLM {provider} error: {str(e)[:80]}")
            continue
    raise HTTPException(502, "LLM indisponivel")


async def _load_brand_kit(company_id: str) -> dict:
    """Fetch the company's BrandKit (primary/secondary/accent colors + font).
    Returns empty dict when no kit / no company. Lightweight wrapper that
    avoids importing the full brand_kit_applier on every chat call."""
    if not company_id:
        return {}
    try:
        doc = await db.companies.find_one(
            {"id": company_id},
            {"_id": 0, "brandKit": 1, "name": 1},
        )
    except Exception as exc:
        logger.warning(f"editor_chat: brand kit fetch failed: {exc}")
        return {}
    if not doc:
        return {}
    kit = doc.get("brandKit") or {}
    # Surface a `companyName` alias so the LLM can address the user properly.
    if doc.get("name"):
        kit = dict(kit)
        kit["companyName"] = doc["name"]
    return kit


async def _load_brand_logo(company_id: str, brand_kit: dict = None) -> str:
    """Resolve the company's brand logo URL.

    Priority order:
      1. First `type=logo` asset registered in the Brand Library (recent).
      2. `brandKit.logoUrl` (if set on the BrandKit).
      3. `company.logo` field (top-level legacy field).
    Returns the resolved URL or empty string when nothing is configured.
    """
    if not company_id:
        return ""
    # 1. Library asset
    try:
        row = await db.company_assets_meta.find_one(
            {"companyId": company_id, "type": "logo", "isActive": {"$ne": False}},
            {"_id": 0, "id": 1},
            sort=[("createdAt", -1)],
        )
        if row and row.get("id"):
            return f"/api/companies/{company_id}/assets/{row['id']}/file"
    except Exception as exc:
        logger.warning(f"editor_chat: brand logo asset fetch failed: {exc}")
    # 2. BrandKit field
    if brand_kit and brand_kit.get("logoUrl"):
        return str(brand_kit["logoUrl"])
    # 3. Legacy company.logo
    try:
        doc = await db.companies.find_one({"id": company_id}, {"_id": 0, "logo": 1})
        if doc and doc.get("logo"):
            return str(doc["logo"])
    except Exception:
        pass
    return ""


async def _load_brand_backgrounds(company_id: str) -> list:
    """Fetch the active brand backgrounds for a company. Returns a list of
    light dicts: {id, name, category, tags, url}. Empty when company has
    no brand library or no `type=background` assets registered.

    The Editor Chat surface uses this to:
      1. Show the LLM what is available (so it can pick by name/category).
      2. Resolve `useBrandBackground: true` / `brandAssetId` at apply time.
    """
    if not company_id:
        return []
    try:
        rows = await db.company_assets_meta.find(
            {"companyId": company_id, "type": "background", "isActive": {"$ne": False}},
            {"_id": 0, "id": 1, "name": 1, "category": 1, "tags": 1, "filename": 1},
        ).sort("createdAt", -1).to_list(50)
    except Exception as exc:
        logger.warning(f"editor_chat: brand bg fetch failed: {exc}")
        return []
    out = []
    for r in rows:
        out.append({
            "id": r.get("id"),
            "name": r.get("name") or r.get("filename") or r.get("id"),
            "category": r.get("category") or "generic",
            "tags": r.get("tags") or [],
            "url": f"/api/companies/{company_id}/assets/{r.get('id')}/file",
        })
    return out


def _resolve_brand_background(brand_backgrounds: list, brand_asset_id: str = None) -> dict:
    """Pick a brand background to use. If `brand_asset_id` is given, find
    that specific asset; otherwise return the FIRST (most recently created)
    background from the library. Returns None if no match / empty library.
    """
    if not brand_backgrounds:
        return None
    if brand_asset_id:
        for b in brand_backgrounds:
            if b.get("id") == brand_asset_id:
                return b
        # No match: fall back to first so the action still produces an effect
        # — the user explicitly asked for a brand background.
        return brand_backgrounds[0]
    return brand_backgrounds[0]


def _user_mentioned_corner(message: str) -> bool:
    """Detect whether the author's free-text message mentions a logo corner.
    Used as a guardrail: if the user did NOT say anything about position,
    we must NEVER let the LLM's hallucinated `logoCorner` override the
    BrandKit's configured `logoPlacement` (which is the source of truth
    set by the super admin in the UI)."""
    if not message:
        return False
    return bool(re.search(
        r"\b(canto|cantos|topo|fundo|superior|inferior|esquerd[ao]s?|"
        r"direit[ao]s?|centro|centralizado|"
        r"top[\s-]?right|top[\s-]?left|bottom[\s-]?right|"
        r"bottom[\s-]?left|bottom[\s-]?center)\b",
        message,
        re.IGNORECASE,
    ))


def _user_mentioned_size(message: str) -> bool:
    """Detect whether the author's message mentions logo size."""
    if not message:
        return False
    return bool(re.search(
        r"\b(tamanho|tamanhos|pequen[ao]s?|m[ée]di[ao]s?|grande|grandes|"
        r"maior|menor|mini|tiny|small|medium|large|big|"
        r"\d+\s*p[xX]|\d+\s*pixels?)\b",
        message,
        re.IGNORECASE,
    ))


def _sanitize_brand_ops(ops: list, message: str) -> list:
    """Strip `logoCorner` / `logoSize` from `apply_brand_identity` ops when
    the user didn't explicitly mention them. The LLM tends to hallucinate
    these fields (defaulting to "top-right" / 96) which silently overrides
    the super admin's BrandKit config — causing the production bug where
    "Aplique o brand kit completo" landed the logo at top-right at the
    wrong size despite the kit configured for bottom-left + 160 px."""
    if not isinstance(ops, list):
        return ops
    mentions_corner = _user_mentioned_corner(message)
    mentions_size = _user_mentioned_size(message)
    if mentions_corner and mentions_size:
        return ops  # nothing to strip
    for op in ops:
        if not isinstance(op, dict):
            continue
        if op.get("type") != "apply_brand_identity":
            continue
        if not mentions_corner:
            op.pop("logoCorner", None)
        if not mentions_size:
            op.pop("logoSize", None)
    return ops


def _extract_json(raw: str) -> dict:
    m = re.search(r"```json\s*([\s\S]*?)```", raw)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError:
        return {"reply": raw[:500], "ops": []}


def _apply_ops(slides: list, ops: list, brand_backgrounds: list = None, brand_kit: dict = None, brand_logo_url: str = "") -> list:
    """Mutate slides in-place applying a list of editor ops. Returns the
    list of ops that were actually applied (skips malformed ones).

    `brand_backgrounds` is the pre-fetched list of company brand backgrounds
    (see `_load_brand_backgrounds`). Used by `add_slide` /
    `apply_brand_background` / `set_slide_background_image` to resolve
    `brandAssetId` and `useBrandBackground:true` flags.

    `brand_kit` is the pre-fetched BrandKit (primary/secondary/accent +
    font). Used by `apply_brand_palette` to update slide colors / text.

    `brand_logo_url` is the pre-resolved logo URL of the company. Used by
    `apply_brand_identity` to inject a watermark image element.
    """
    brand_backgrounds = brand_backgrounds or []
    brand_kit = brand_kit or {}
    applied = []
    for op in ops:
        try:
            t = (op or {}).get("type") if isinstance(op, dict) else None
            if t == "edit_slide_title":
                i = int(op["slideIndex"])
                if 0 <= i < len(slides):
                    slides[i]["title"] = str(op.get("title", ""))
                    applied.append({"type": t, "slideIndex": i})
            elif t == "edit_element_content":
                si, ei = int(op["slideIndex"]), int(op["elementIndex"])
                if 0 <= si < len(slides):
                    els = slides[si].get("elements") or []
                    if 0 <= ei < len(els):
                        # Only edit text-style elements (avoid breaking quizzes/html)
                        if els[ei].get("type") in ("text", "shape"):
                            els[ei]["content"] = str(op.get("content", ""))
                            applied.append({"type": t, "slideIndex": si, "elementIndex": ei})
            elif t == "edit_element_style":
                si, ei = int(op["slideIndex"]), int(op["elementIndex"])
                if 0 <= si < len(slides):
                    els = slides[si].get("elements") or []
                    if 0 <= ei < len(els):
                        style = els[ei].get("style") or {}
                        patch = op.get("style") or {}
                        # 2026-05-19: plate-related keys are FORBIDDEN. The
                        # user explicitly rejected `backgroundColor`/
                        # `textBackgroundColor`/`padding`/`borderRadius`
                        # behind text. Contrast must be resolved via
                        # `fontColor` only. We also pro-actively strip any
                        # existing plate residue from this element.
                        BANNED = {
                            "backgroundColor", "textBackgroundColor",
                            "padding", "borderRadius",
                            "boxShadow", "box-shadow",
                            "textShadow", "text-shadow",
                        }
                        for k in BANNED:
                            style.pop(k, None)
                        for k in ("fontColor", "fontSize", "fontWeight", "textAlign", "fontFamily"):
                            if k in patch and patch[k] not in (None, ""):
                                style[k] = patch[k]
                        els[ei]["style"] = style
                        applied.append({"type": t, "slideIndex": si, "elementIndex": ei})
            elif t == "add_text_element":
                si = int(op["slideIndex"])
                if 0 <= si < len(slides):
                    els = slides[si].setdefault("elements", [])
                    els.append({
                        "id": str(uuid.uuid4()),
                        "type": "text",
                        "content": str(op.get("content", "")),
                        "x": float(op.get("x", 100)),
                        "y": float(op.get("y", 100)),
                        "width": float(op.get("width", 600)),
                        "height": float(op.get("height", 60)),
                        "style": {
                            "fontSize": int(op.get("fontSize", 20)),
                            "fontColor": op.get("fontColor") or "#0f172a",
                        },
                    })
                    applied.append({"type": t, "slideIndex": si, "newElementIndex": len(els) - 1})
            elif t == "add_slide":
                # Insert N new blank slides after a given index. Supports
                # bulk insertion via `count` (default 1, capped at 20).
                # 2026-05-21: requested by user to be able to ask
                # "adicione N slides" via Editor Chat.
                insert_after = int(op.get("insertAfter", len(slides) - 1))
                # Clamp: -1 means "insert at start"; >= len-1 means "append at end".
                insert_after = max(-1, min(len(slides) - 1, insert_after))
                try:
                    count = int(op.get("count", 1))
                except (TypeError, ValueError):
                    count = 1
                count = max(1, min(20, count))

                base_title = str(op.get("title") or "Novo Slide").strip() or "Novo Slide"
                content_text = str(op.get("content") or "").strip()
                # Inherit background from the previous slide if not provided.
                prev_bg = "#FFFFFF"
                if 0 <= insert_after < len(slides):
                    prev_bg = slides[insert_after].get("background") or "#FFFFFF"
                bg = str(op.get("background") or prev_bg)
                narration = str(op.get("narrationScript") or "")

                # 2026-05-21: brand background support. When the user asks
                # "crie 3 slides com fundo da marca", the LLM sets
                # `useBrandBackground:true` (or `brandAssetId`). Resolve here.
                bg_image_url = ""
                use_brand = bool(op.get("useBrandBackground"))
                brand_asset_id = op.get("brandAssetId") or None
                if use_brand or brand_asset_id:
                    asset = _resolve_brand_background(brand_backgrounds, brand_asset_id)
                    if asset and asset.get("url"):
                        bg_image_url = asset["url"]

                inserted_at = []
                for n in range(count):
                    title_n = f"{base_title} {n + 1}" if count > 1 else base_title
                    elements = []
                    if content_text:
                        # Plain HTML paragraph centered on the slide canvas.
                        html_content = (
                            f'<p style="margin:0;font-size:26px;line-height:1.5">'
                            f'{content_text.replace(chr(60), "&lt;").replace(chr(62), "&gt;")}</p>'
                        )
                        elements.append({
                            "id": str(uuid.uuid4()),
                            "type": "text",
                            "content": content_text,
                            "htmlContent": html_content,
                            "x": 80, "y": 200, "width": 1760, "height": 420,
                            "style": {"fontSize": 26, "fontColor": "#0f172a"},
                        })
                    new_slide = {
                        "id": str(uuid.uuid4()),
                        "title": title_n,
                        "order": insert_after + 1 + n,
                        "width": 1920,
                        "height": 820,
                        "background": bg,
                        "elements": elements,
                        "annotations": [],
                        "transition": {"type": "fade", "duration": 0.5},
                        "audio": [],
                        "notes": "",
                        "narrationScript": narration,
                        "duration": 5.0,
                    }
                    if bg_image_url:
                        new_slide["backgroundImage"] = bg_image_url
                    pos = insert_after + 1 + n
                    slides.insert(pos, new_slide)
                    inserted_at.append(pos)

                # Re-number order field on every slide so it stays canonical.
                for i, s in enumerate(slides):
                    s["order"] = i

                applied.append({
                    "type": t,
                    "insertedAt": inserted_at,
                    "count": count,
                    "brandBackgroundUsed": bool(bg_image_url),
                })
            elif t == "set_slide_background_image":
                # Set or clear backgroundImage on a single slide.
                si = int(op["slideIndex"])
                if 0 <= si < len(slides):
                    if op.get("clear"):
                        slides[si].pop("backgroundImage", None)
                        applied.append({"type": t, "slideIndex": si, "cleared": True})
                    else:
                        img_url = op.get("imageUrl")
                        if op.get("brandAssetId") or (img_url is None and brand_backgrounds):
                            asset = _resolve_brand_background(
                                brand_backgrounds, op.get("brandAssetId")
                            )
                            if asset:
                                img_url = asset.get("url")
                        if img_url:
                            slides[si]["backgroundImage"] = str(img_url)
                            applied.append({"type": t, "slideIndex": si, "url": img_url})
            elif t == "apply_brand_background":
                # Propagate a brand background to a range of slides (or all).
                if not brand_backgrounds:
                    # Library empty — no-op so the LLM's verbal reply explains
                    # the situation; the apply layer just skips silently.
                    continue
                asset = _resolve_brand_background(
                    brand_backgrounds, op.get("brandAssetId")
                )
                if not asset or not asset.get("url"):
                    continue
                img_url = asset["url"]
                if op.get("allSlides") or (
                    op.get("fromIndex") is None and op.get("toIndex") is None
                ):
                    start, end = 0, len(slides) - 1
                else:
                    try:
                        start = max(0, int(op.get("fromIndex", 0)))
                        end = min(len(slides) - 1, int(op.get("toIndex", len(slides) - 1)))
                    except (TypeError, ValueError):
                        start, end = 0, len(slides) - 1
                if end < start:
                    continue
                affected = []
                for idx in range(start, end + 1):
                    slides[idx]["backgroundImage"] = img_url
                    affected.append(idx)
                applied.append({
                    "type": t,
                    "affectedSlides": affected,
                    "assetId": asset.get("id"),
                    "url": img_url,
                })
            elif t == "apply_brand_palette":
                # Apply the company's BrandKit colors (and optionally font)
                # to slides: paints `slide.background` with `primaryColor`
                # (or accent if explicitly requested) and sweeps every
                # textual element's `fontColor` to win WCAG AA contrast
                # against the new background. Defense-in-depth strips any
                # plate residue while at it.
                if not brand_kit:
                    continue
                # Hex sanity
                def _hex(v):
                    return v if isinstance(v, str) and v.startswith("#") and len(v) in (4, 7) else None
                primary = _hex(brand_kit.get("primaryColor"))
                accent = _hex(brand_kit.get("accentColor"))
                secondary = _hex(brand_kit.get("secondaryColor"))
                font_family = (brand_kit.get("fontFamily") or "").strip() or None

                # Which palette color to use as slide bg?
                target = (op.get("target") or "primary").lower()
                if target == "accent" and accent:
                    chosen_bg = accent
                elif target == "secondary" and secondary:
                    chosen_bg = secondary
                else:
                    chosen_bg = primary or accent or secondary
                if not chosen_bg:
                    # No usable color in the kit — skip silently.
                    continue

                # Range: allSlides default, else fromIndex/toIndex inclusive.
                if op.get("allSlides") or (
                    op.get("fromIndex") is None and op.get("toIndex") is None
                ):
                    start, end = 0, len(slides) - 1
                else:
                    try:
                        start = max(0, int(op.get("fromIndex", 0)))
                        end = min(len(slides) - 1, int(op.get("toIndex", len(slides) - 1)))
                    except (TypeError, ValueError):
                        start, end = 0, len(slides) - 1
                if end < start or not slides:
                    continue

                # Plate keys that must be stripped from any text element we touch.
                BANNED_STYLE_KEYS = {
                    "backgroundColor", "textBackgroundColor",
                    "padding", "borderRadius",
                    "boxShadow", "box-shadow",
                    "textShadow", "text-shadow",
                }

                from services import wcag  # lazy import — only when invoked
                # Pick the fallback (dark vs light) that gives the BEST
                # WCAG contrast against the chosen background. This beats
                # `pick_high_contrast_color` for mid-luminance bgs (e.g.,
                # amber) where the luminance-threshold heuristic can pick
                # the wrong polarity.
                try:
                    dark_ratio = wcag.contrast_ratio(wcag.DARK_FALLBACK, chosen_bg)
                    light_ratio = wcag.contrast_ratio(wcag.LIGHT_FALLBACK, chosen_bg)
                    best_text_color = (
                        wcag.LIGHT_FALLBACK if light_ratio >= dark_ratio
                        else wcag.DARK_FALLBACK
                    )
                except Exception:
                    best_text_color = wcag.pick_high_contrast_color(chosen_bg)
                affected_slides = []
                text_swaps = 0
                for idx in range(start, end + 1):
                    sl = slides[idx]
                    # 1. Paint solid background (clear any image bg if explicitly requested)
                    sl["background"] = chosen_bg
                    if op.get("clearBackgroundImage"):
                        sl.pop("backgroundImage", None)
                    # 2. Sweep every textual element: enforce WCAG AA and
                    # apply brand font if provided. Skip html/quiz/scenario
                    # to avoid breaking simulator internal typography.
                    for el in (sl.get("elements") or []):
                        if not isinstance(el, dict):
                            continue
                        if el.get("type") in ("html", "quiz", "scenario", "image", "shape"):
                            continue
                        st = el.get("style")
                        if not isinstance(st, dict):
                            st = {}
                            el["style"] = st
                        # Strip plate residue
                        for k in BANNED_STYLE_KEYS:
                            st.pop(k, None)
                        # Apply the best-contrast text color we computed.
                        st["fontColor"] = best_text_color
                        # Keep `color` alias in sync for legacy renderers.
                        st["color"] = best_text_color
                        if font_family:
                            st["fontFamily"] = font_family
                        text_swaps += 1
                    affected_slides.append(idx)

                applied.append({
                    "type": t,
                    "affectedSlides": affected_slides,
                    "backgroundUsed": chosen_bg,
                    "textElementsUpdated": text_swaps,
                    "fontFamily": font_family,
                })
            elif t == "apply_brand_identity":
                # Combined op: applies brand background image + brand palette
                # (colors + font) + brand logo as watermark, all in one go.
                # Designed as the "instant onboarding" for imported courses
                # where the author wants the whole identity sweep applied.
                affected_slides_list = []
                bg_url_used = ""
                palette_bg_used = ""
                logo_inserted_count = 0
                text_swaps = 0
                font_family_applied = None

                # ---- Resolve targets / range ----
                if op.get("allSlides") or (
                    op.get("fromIndex") is None and op.get("toIndex") is None
                ):
                    start, end = 0, len(slides) - 1
                else:
                    try:
                        start = max(0, int(op.get("fromIndex", 0)))
                        end = min(len(slides) - 1, int(op.get("toIndex", len(slides) - 1)))
                    except (TypeError, ValueError):
                        start, end = 0, len(slides) - 1
                if end < start or not slides:
                    continue

                # Flags — default ALL components ON.
                add_bg = op.get("applyBackground", True)
                add_palette = op.get("applyPalette", True)
                add_logo = op.get("applyLogo", True) and bool(brand_logo_url)

                # ---- 1. Brand background image ----
                if add_bg and brand_backgrounds:
                    asset = _resolve_brand_background(brand_backgrounds, op.get("brandAssetId"))
                    if asset and asset.get("url"):
                        bg_url_used = asset["url"]

                # ---- 2. Palette: resolve text color (best WCAG ratio) ----
                def _hex(v):
                    return v if isinstance(v, str) and v.startswith("#") and len(v) in (4, 7) else None
                primary = _hex(brand_kit.get("primaryColor"))
                accent = _hex(brand_kit.get("accentColor"))
                secondary = _hex(brand_kit.get("secondaryColor"))
                font_family = (brand_kit.get("fontFamily") or "").strip() or None
                target = (op.get("paletteTarget") or "primary").lower()
                if target == "accent" and accent:
                    palette_bg_used = accent
                elif target == "secondary" and secondary:
                    palette_bg_used = secondary
                else:
                    palette_bg_used = primary or accent or secondary or ""

                if add_palette and palette_bg_used:
                    from services import wcag
                    try:
                        dark_ratio = wcag.contrast_ratio(wcag.DARK_FALLBACK, palette_bg_used)
                        light_ratio = wcag.contrast_ratio(wcag.LIGHT_FALLBACK, palette_bg_used)
                        best_text_color = (
                            wcag.LIGHT_FALLBACK if light_ratio >= dark_ratio
                            else wcag.DARK_FALLBACK
                        )
                    except Exception:
                        best_text_color = wcag.pick_high_contrast_color(palette_bg_used)
                    BANNED_STYLE_KEYS = {
                        "backgroundColor", "textBackgroundColor",
                        "padding", "borderRadius",
                        "boxShadow", "box-shadow",
                        "textShadow", "text-shadow",
                    }
                else:
                    best_text_color = None
                    BANNED_STYLE_KEYS = set()

                # ---- 3. Logo watermark placement ----
                # Author can override per-op via `logoCorner` (top-right /
                # top-left / bottom-right / bottom-left / bottom-center).
                # Falls back to `brand_kit.logoPlacement` configured in the
                # Super Admin Brand Kit UI, then defaults to bottom-right.
                _kit_placement = (brand_kit.get("logoPlacement") or "").strip().lower()
                logo_corner = (op.get("logoCorner") or "").strip().lower()
                if not logo_corner:
                    # Map BrandKit values → corner. "intro-conclusion-only"
                    # uses bottom-right with a per-slide filter applied below.
                    if _kit_placement in ("bottom-right", "bottom-left", "bottom-center", "top-right", "top-left"):
                        logo_corner = _kit_placement
                    elif _kit_placement == "intro-conclusion-only":
                        logo_corner = "bottom-right"
                    else:
                        logo_corner = "bottom-right"
                # Track intro-conclusion-only intent so we can skip middle slides.
                _intro_concl_only = (_kit_placement == "intro-conclusion-only")

                # Resolve logo size: op param overrides BrandKit setting. Accepts
                # named presets ("small"=64, "medium"=96, "large"=160), a raw
                # integer, OR a numeric string ("160" or "160px"). Defensive
                # parsing because production DB values from older saves may be
                # stored as strings depending on the path that persisted them.
                LOGO_SIZE_PRESETS = {"small": 64, "medium": 96, "large": 160}

                def _resolve_logo_size(raw):
                    if raw is None or isinstance(raw, bool):
                        return None
                    if isinstance(raw, (int, float)):
                        try:
                            n = int(raw)
                            return max(32, min(320, n)) if n > 0 else None
                        except (TypeError, ValueError):
                            return None
                    if isinstance(raw, str):
                        s = raw.strip().lower()
                        if not s:
                            return None
                        if s in LOGO_SIZE_PRESETS:
                            return LOGO_SIZE_PRESETS[s]
                        try:
                            n = int(float(s.rstrip("px").strip()))
                            return max(32, min(320, n)) if n > 0 else None
                        except (TypeError, ValueError):
                            return None
                    return None

                logo_size = (
                    _resolve_logo_size(op.get("logoSize"))
                    or _resolve_logo_size(brand_kit.get("logoSize"))
                    or 96
                )
                # Logos are usually horizontal/wide. Use logoSize as the WIDTH
                # of the bounding box and make the height a shorter band so
                # `objectFit: contain` shows the logo at full configured width
                # instead of shrinking it to fit a square. Aspect ~2.5:1 matches
                # the static export path (`apply_brand_logo_to_slides`).
                logo_w = logo_size
                logo_h = max(32, int(round(logo_size / 2.5)))
                # Log the resolved values so we can diagnose production issues
                # by inspecting backend logs. Cheap one-liner per apply.
                logger.info(
                    "editor_chat apply_brand_identity: kit.logoSize=%r op.logoSize=%r → logo_size=%d (w=%d h=%d) corner=%s",
                    brand_kit.get("logoSize"), op.get("logoSize"),
                    logo_size, logo_w, logo_h, logo_corner,
                )
                margin = 24
                canvas_w, canvas_h = 1920, 820
                if logo_corner == "top-left":
                    lx, ly = margin, margin
                elif logo_corner == "bottom-right":
                    lx, ly = canvas_w - logo_w - margin, canvas_h - logo_h - margin
                elif logo_corner == "bottom-left":
                    lx, ly = margin, canvas_h - logo_h - margin
                elif logo_corner == "bottom-center":
                    lx, ly = (canvas_w - logo_w) // 2, canvas_h - logo_h - margin
                else:  # top-right
                    lx, ly = canvas_w - logo_w - margin, margin

                # ---- Apply per-slide ----
                for idx in range(start, end + 1):
                    sl = slides[idx]
                    # 1) Brand background image
                    if bg_url_used:
                        sl["backgroundImage"] = bg_url_used
                    # 2) Palette: solid background + sweep text colors
                    if add_palette and palette_bg_used:
                        sl["background"] = palette_bg_used
                        for el in (sl.get("elements") or []):
                            if not isinstance(el, dict):
                                continue
                            if el.get("type") in ("html", "quiz", "scenario", "image", "shape"):
                                continue
                            st = el.get("style")
                            if not isinstance(st, dict):
                                st = {}
                                el["style"] = st
                            for k in BANNED_STYLE_KEYS:
                                st.pop(k, None)
                            st["fontColor"] = best_text_color
                            st["color"] = best_text_color
                            if font_family:
                                st["fontFamily"] = font_family
                                font_family_applied = font_family
                            text_swaps += 1
                    # 3) Logo watermark — insert if missing, or sync size/position/src
                    # of any existing brand-logo element so re-running the command
                    # with a new logoSize/logoCorner actually updates the slide.
                    # When BrandKit placement is "intro-conclusion-only", skip
                    # middle slides AND strip any stale logo lingering there.
                    if add_logo:
                        els = sl.get("elements") or []
                        is_first = (idx == start)
                        is_last = (idx == end)
                        skip_logo_here = _intro_concl_only and not (is_first or is_last)
                        existing_idx = None
                        for ei, e in enumerate(els):
                            if isinstance(e, dict) and e.get("isBrandLogo"):
                                existing_idx = ei
                                break
                        if skip_logo_here:
                            # Drop any stale logo on middle slides.
                            if existing_idx is not None:
                                els.pop(existing_idx)
                                sl["elements"] = els
                        elif existing_idx is None:
                            els.append({
                                "id": str(uuid.uuid4()),
                                "type": "image",
                                "src": brand_logo_url,
                                "x": lx, "y": ly,
                                "width": logo_w, "height": logo_h,
                                "isBrandLogo": True,
                                "alt": "Logo da empresa",
                                "style": {"opacity": 0.9, "objectFit": "contain"},
                            })
                            sl["elements"] = els
                            logo_inserted_count += 1
                        else:
                            existing = els[existing_idx]
                            existing["src"] = brand_logo_url
                            existing["x"] = lx
                            existing["y"] = ly
                            existing["width"] = logo_w
                            existing["height"] = logo_h
                            existing.setdefault("style", {})
                            existing["style"]["objectFit"] = "contain"
                            existing.setdefault("alt", "Logo da empresa")
                            logo_inserted_count += 1
                    affected_slides_list.append(idx)

                applied.append({
                    "type": t,
                    "affectedSlides": affected_slides_list,
                    "backgroundImageUsed": bg_url_used,
                    "paletteBackgroundUsed": palette_bg_used if add_palette else "",
                    "logoInsertedCount": logo_inserted_count,
                    "logoSizeResolved": logo_size,
                    "logoCornerResolved": logo_corner,
                    "kitLogoSizeRaw": brand_kit.get("logoSize"),
                    "textElementsUpdated": text_swaps,
                    "fontFamily": font_family_applied,
                })
            elif t == "delete_element":
                si, ei = int(op["slideIndex"]), int(op["elementIndex"])
                if 0 <= si < len(slides):
                    els = slides[si].get("elements") or []
                    if 0 <= ei < len(els):
                        els.pop(ei)
                        applied.append({"type": t, "slideIndex": si, "elementIndex": ei})
            elif t == "change_slide_background":
                i = int(op["slideIndex"])
                if 0 <= i < len(slides):
                    slides[i]["background"] = str(op.get("background", "#ffffff"))
                    applied.append({"type": t, "slideIndex": i})
            elif t == "move_slide":
                f, to = int(op["fromIndex"]), int(op["toIndex"])
                if 0 <= f < len(slides) and 0 <= to < len(slides):
                    moved = slides.pop(f)
                    slides.insert(to, moved)
                    applied.append({"type": t, "fromIndex": f, "toIndex": to})
            elif t == "delete_slide":
                i = int(op["slideIndex"])
                if 0 <= i < len(slides):
                    slides.pop(i)
                    applied.append({"type": t, "slideIndex": i})
        except (ValueError, TypeError, KeyError) as e:
            logger.warning(f"editor_chat skipped op {op}: {e}")
            continue
    return applied


@router.post("/projects/{project_id}/editor-chat")
async def editor_chat(project_id: str, data: dict, user: dict = Depends(require_auth)):
    """Conversational editing of a published course via natural language.

    Body: `{message: str, history?: [{role, content}]}`
    Returns: `{reply, ops, slides, snapshotCreated}`
    """
    message = (data.get("message") or "").strip()
    if not message:
        raise HTTPException(400, "Mensagem vazia")

    project = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(404, "Projeto nao encontrado")

    slides = (project.get("course") or {}).get("slides") or []
    if not slides:
        raise HTTPException(400, "Curso sem slides para editar")

    # Pre-load brand backgrounds + brand kit from the project's company so
    # the LLM can suggest them by name/category and the apply path can
    # resolve `brandAssetId` / `useBrandBackground:true` / brand palette
    # ops in a single round-trip.
    company_id = project.get("companyId") or ""
    brand_backgrounds = await _load_brand_backgrounds(company_id)
    brand_kit = await _load_brand_kit(company_id)
    brand_logo_url = await _load_brand_logo(company_id, brand_kit)

    summary = _build_course_summary(slides)
    history = (data.get("history") or [])[-6:]

    brand_section = ""
    if brand_backgrounds:
        # Compact list for the LLM. Cap to first 20 to keep the prompt small.
        brand_list = [
            {"id": b["id"], "name": b["name"], "category": b["category"], "tags": b["tags"]}
            for b in brand_backgrounds[:20]
        ]
        brand_section = (
            f"BIBLIOTECA DE MARCA (backgrounds disponiveis da empresa):\n"
            f"{json.dumps(brand_list, ensure_ascii=False)}\n\n"
        )
    else:
        brand_section = (
            "BIBLIOTECA DE MARCA: vazia. Se o autor pedir 'fundo da marca', "
            "responda no `reply` que a empresa nao tem backgrounds cadastrados "
            "e nao gere ops de background de marca.\n\n"
        )

    # Surface the BrandKit (colors + font) so the LLM can use the
    # `apply_brand_palette` op when the author asks for "paleta da marca",
    # "cores da empresa", "fonte da marca" etc.
    if brand_kit and any(brand_kit.get(k) for k in ("primaryColor", "accentColor", "secondaryColor", "fontFamily")):
        kit_compact = {
            "companyName": brand_kit.get("companyName"),
            "primaryColor": brand_kit.get("primaryColor"),
            "accentColor": brand_kit.get("accentColor"),
            "secondaryColor": brand_kit.get("secondaryColor"),
            "fontFamily": brand_kit.get("fontFamily"),
        }
        brand_section += (
            f"PALETA DE MARCA (BrandKit da empresa):\n"
            f"{json.dumps(kit_compact, ensure_ascii=False)}\n\n"
        )
    else:
        brand_section += (
            "PALETA DE MARCA: BrandKit nao configurado. Se o autor pedir "
            "'paleta da marca' ou 'cores da empresa', responda que a empresa "
            "nao tem BrandKit definido e nao gere ops de palette.\n\n"
        )

    if brand_logo_url:
        brand_section += f"LOGO DA MARCA: disponivel ({brand_logo_url}). Pode ser usado como marca d'agua via `apply_brand_identity`.\n\n"
    else:
        brand_section += "LOGO DA MARCA: nao cadastrado. Se o autor pedir 'identidade visual completa', use `apply_brand_identity` com `applyLogo:false`.\n\n"

    user_prompt = (
        f"CURSO ATUAL (resumo):\n{json.dumps(summary, ensure_ascii=False)[:8000]}\n\n"
        f"{brand_section}"
        f"CONVERSA:\n{json.dumps(history, ensure_ascii=False) if history else '(primeira mensagem)'}\n\n"
        f"AUTOR: {message}"
    )
    raw = await _call_llm(SYSTEM_PROMPT, user_prompt, f"editor_chat_{project_id}")
    parsed = _extract_json(raw)
    reply = parsed.get("reply") or "Entendi."
    ops = parsed.get("ops") or []

    # Guardrail: strip LLM-hallucinated `logoCorner`/`logoSize` from
    # apply_brand_identity ops so the BrandKit config (set in the Super
    # Admin UI) is the source of truth UNLESS the author explicitly
    # mentioned position/size in their message.
    ops = _sanitize_brand_ops(ops, message)

    # Snapshot BEFORE mutating so the user can revert (shares the same
    # `aesthetic_snapshots` collection so existing Revert button works).
    snapshot_slides = _copy.deepcopy(slides) if ops else None

    applied = _apply_ops(slides, ops, brand_backgrounds=brand_backgrounds, brand_kit=brand_kit, brand_logo_url=brand_logo_url)

    if applied:
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
                "appliedCount": len(applied),
                "appliedAt": datetime.now(timezone.utc).isoformat(),
                "userId": user.get("user_id", ""),
                "kind": "editor_chat",
            }},
            upsert=True,
        )
        # Append to chat log (cap 50)
        try:
            await db.projects.update_one(
                {"id": project_id},
                {"$push": {
                    "editorChatLog": {
                        "$each": [
                            {"role": "user", "content": message, "at": datetime.now(timezone.utc).isoformat()},
                            {"role": "assistant", "content": reply, "ops": applied, "at": datetime.now(timezone.utc).isoformat()},
                        ],
                        "$slice": -50,
                    }
                }}
            )
        except Exception:
            pass

    return {
        "reply": reply,
        "ops": applied,
        "opsProposed": len(ops),
        "slides": slides,
        "snapshotCreated": bool(applied),
    }
