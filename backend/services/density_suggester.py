"""Density Suggester — given a text-heavy slide / section, asks an LLM
(Claude Sonnet via Emergent universal key) for visual alternatives the
author can apply with one click.

Suggestion categories returned by the LLM (we cap at 3-4 per call):
  - "summarize"     → concise rewrite, same intent in <50% the words
  - "split"         → split into 2 separate slides
  - "bullets"       → convert prose to scannable bullet list
  - "comparison"    → side-by-side comparison table (for "X vs Y" content)
  - "infographic"   → numbered-icons / step-list layout
  - "diagram"       → flowchart / process visualization (returns a prompt
                      the image generator can run)

Every suggestion ships a `transformedText` (or `transformedBullets`) that
the frontend can apply via a one-click button without a second round trip.
For "diagram" / "infographic" types that need new imagery, the suggestion
ships an `imagePrompt` the caller can feed to Leonardo/Gemini.
"""
import json
import logging
import os
from typing import Dict, List, Optional

from services.llm_config import openai_api_key, openai_text_model

logger = logging.getLogger(__name__)


SUGGESTION_TYPES = ("summarize", "split", "bullets", "comparison", "infographic", "diagram")


def _build_prompt(title: str, text: str, bullets: List[str], reasons: List[str]) -> str:
    """Compose the LLM prompt. We embed the diagnostic reasons so the LLM
    knows WHY the slide was flagged — yields more targeted suggestions."""
    bullet_block = "\n".join(f"  - {b}" for b in bullets) if bullets else "  (sem bullets)"
    reasons_block = "; ".join(reasons) or "denso visualmente"
    return f"""Voce e um especialista em design instrucional. Um slide foi diagnosticado como TEXTUAL DEMAIS pelos seguintes motivos: {reasons_block}.

SLIDE ATUAL:
Titulo: {title or "(sem titulo)"}
Corpo:
{text or "(sem corpo)"}
Bullets:
{bullet_block}

Sua tarefa: gerar 3 sugestoes DISTINTAS para tornar este slide mais visual e engajante. Para cada sugestao, escolha um tipo entre: summarize, split, bullets, comparison, infographic, diagram.

Responda EXCLUSIVAMENTE com um JSON valido no formato:
{{
  "suggestions": [
    {{
      "type": "summarize",
      "title": "Titulo curto da sugestao (max 6 palavras)",
      "description": "Frase explicando o beneficio (max 18 palavras)",
      "transformedText": "Novo corpo do slide ja transformado (pronto pra aplicar)",
      "transformedBullets": ["bullet 1", "bullet 2", "bullet 3"],
      "imagePrompt": "Descricao em pt-BR para gerar imagem de apoio (so se relevante; senao string vazia). DEVE incluir explicitamente: 'TODOS os textos, rotulos, legendas e titulos da imagem em PORTUGUES BRASILEIRO (pt-BR), sem palavras em ingles.'",
      "requiresImage": false
    }}
  ]
}}

Regras importantes:
- transformedText em pt-BR, conciso, voz ativa.
- transformedBullets em pt-BR, no maximo 5 itens, frases curtas (≤8 palavras).
- Se a sugestao for "split", coloque a primeira metade em transformedText e a segunda metade no segundo objeto de suggestion (use 2 sugestoes consecutivas).
- Para "diagram" e "infographic" deixe requiresImage=true e preencha imagePrompt em **PORTUGUES BRASILEIRO (pt-BR)** (max 35 palavras). Sempre termine o imagePrompt com: ". Todos os rotulos, titulos e legendas em portugues do Brasil. NAO usar texto em ingles." — essa instrucao final e OBRIGATORIA quando requiresImage=true.
- Nunca repita o texto original quase identico — uma sugestao deve transformar de verdade.

Responda APENAS o JSON, sem markdown, sem explicacao."""


async def generate_visual_suggestions(
    *,
    title: str = "",
    text: str = "",
    bullets: Optional[List[str]] = None,
    reasons: Optional[List[str]] = None,
) -> List[Dict]:
    """Call the LLM and return a list of suggestion dicts. Returns an empty
    list on any failure — the caller falls back to deterministic suggestions
    or "no suggestions available" in the UI.
    """
    bullets = bullets or []
    reasons = reasons or []

    try:
        from openai import AsyncOpenAI
        key = openai_api_key()
        if not key:
            logger.warning("OPENAI_API_KEY missing — density suggester disabled")
            return _fallback_suggestions(text, bullets)

        model = openai_text_model("OPENAI_DENSITY_MODEL", default="gpt-4o")
        client = AsyncOpenAI(
            api_key=key,
            timeout=float(os.environ.get("OPENAI_DENSITY_TIMEOUT_SECONDS", "45")),
            max_retries=2,
        )
        prompt = _build_prompt(title, text, bullets, reasons)
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Voce e um especialista em design instrucional. Responda apenas JSON valido."},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.35,
        )
        choices = getattr(response, "choices", None) or []
        resp = getattr(getattr(choices[0], "message", None), "content", "") if choices else ""
        if not resp:
            return _fallback_suggestions(text, bullets)

        # The model occasionally wraps the JSON in ```json fences — strip them.
        s = str(resp).strip()
        if s.startswith("```"):
            s = s.strip("`").strip()
            if s.lower().startswith("json"):
                s = s[4:].strip()
        data = json.loads(s)
        out = data.get("suggestions") or []
        # Validate + normalize each suggestion
        normalized = []
        for i, sug in enumerate(out[:4]):
            if not isinstance(sug, dict):
                continue
            t = (sug.get("type") or "summarize").lower().strip()
            if t not in SUGGESTION_TYPES:
                t = "summarize"
            image_prompt = (sug.get("imagePrompt") or "").strip()[:400]
            # The model occasionally labels an option as infographic/diagram
            # but forgets `requiresImage`, causing the frontend to apply only
            # the rewritten text. Visual suggestion types are authoritative.
            requires_image = (
                t in ("infographic", "diagram")
                or bool(image_prompt)
                or sug.get("requiresImage") is True
            )
            if requires_image and not image_prompt:
                subject = (
                    (sug.get("title") or "").strip()
                    or title.strip()
                    or text.strip()[:180]
                    or "conteudo educacional"
                )
                image_prompt = (
                    f"Ilustracao educacional visual sobre {subject}. Composicao clara, "
                    "profissional, com icones e formas, sem blocos longos de texto."
                )[:400]
            normalized.append({
                "id": f"sug-{i}",
                "type": t,
                "title": (sug.get("title") or "").strip()[:80],
                "description": (sug.get("description") or "").strip()[:240],
                "transformedText": (sug.get("transformedText") or "").strip(),
                "transformedBullets": [
                    b.strip() for b in (sug.get("transformedBullets") or [])
                    if isinstance(b, str) and b.strip()
                ][:6],
                "imagePrompt": image_prompt,
                "requiresImage": requires_image,
            })
        return normalized or _fallback_suggestions(text, bullets)
    except Exception as e:
        logger.warning(f"density LLM call failed: {e}")
        return _fallback_suggestions(text, bullets)


def _fallback_suggestions(text: str, bullets: List[str]) -> List[Dict]:
    """When the LLM is unavailable, ship a minimal deterministic suggestion
    so the UI still feels useful. We just propose 'summarize by truncation'
    and 'convert to bullets' — better than an empty list."""
    out = []
    if text:
        # Truncate to ~half the original length, ending at a sentence boundary
        target = max(80, len(text) // 2)
        cut = text[:target]
        last_dot = max(cut.rfind("."), cut.rfind("!"), cut.rfind("?"))
        if last_dot > target * 0.4:
            cut = cut[:last_dot + 1]
        out.append({
            "id": "fb-summarize",
            "type": "summarize",
            "title": "Resumir conteudo",
            "description": "Reduz o texto pela metade mantendo a primeira metade do conteudo.",
            "transformedText": cut.strip(),
            "transformedBullets": [],
            "imagePrompt": "",
            "requiresImage": False,
        })
    if text and not bullets:
        # Naive bullet extraction: one bullet per sentence (up to 5)
        import re
        sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()][:5]
        out.append({
            "id": "fb-bullets",
            "type": "bullets",
            "title": "Converter em bullets",
            "description": "Transforma o paragrafo em bullets escaneaveis.",
            "transformedText": "",
            "transformedBullets": sentences,
            "imagePrompt": "",
            "requiresImage": False,
        })
    return out
