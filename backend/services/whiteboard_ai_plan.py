"""AI-generated render plan for the Whiteboard.

Given a natural-language description from the author, asks Claude
Sonnet 4.5 (via the Emergent LLM Key) to return a structured
"render plan" the renderer can execute — a sequence of text + shape
operations placed on the 1920×1080 canvas.

The model is constrained by:
  - canvas size (1920×1080, with 140px margins on each side)
  - max 8 shape operations (per the product spec — denser layouts
    feel cluttered and the pen-trace animation drags too long)
  - allowed shape types: circle | rectangle | arrow | underline
  - color hints: model may pick distinct colors per shape if the
    `allow_color_per_shape` flag is on; otherwise everything uses
    the author's ink color
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Optional

logger = logging.getLogger("server.whiteboard_ai")

CANVAS_W = 1920
CANVAS_H = 1080
MARGIN = 140
MAX_OPS = 12   # 4 text + 8 shapes worst case

SYSTEM_PROMPT = """\
Você é um especialista em layout de lousa didática (whiteboard).
Dado o pedido do autor (em português), gere um PLANO DE RENDERIZAÇÃO
em JSON estrito que descreva o que a caneta deve escrever/desenhar
em ordem cronológica.

ESPECIFICAÇÃO DO JSON DE SAÍDA:
{
  "summary": "<frase curta em português descrevendo o que será desenhado, para mostrar ao autor antes de renderizar>",
  "ops": [
    // operações em ordem cronológica de execução pela caneta
  ]
}

TIPOS DE OPERAÇÃO PERMITIDOS:

1. {"type": "text", "text": "<conteúdo>", "x": <int>, "y": <int>, "font_size": <int 40-120>, "color": "<#hex|nome>"}
   - Renderiza o texto à mão escrita. `x,y` é o canto superior-esquerdo.
   - Use 60-90 como font_size típico.

2. {"type": "circle", "cx": <int>, "cy": <int>, "rx": <int>, "ry": <int>, "color": "<#hex|nome>", "width": <int 4-10>}
   - Elipse com centro (cx,cy) e raios rx,ry. Para círculo perfeito use rx==ry.
   - Use principalmente para CIRCULAR palavras-chave dentro do texto.

3. {"type": "rectangle", "x": <int>, "y": <int>, "w": <int>, "h": <int>, "color": "<#hex|nome>", "width": <int 4-10>}
   - Retângulo com canto superior-esquerdo (x,y) e largura/altura.
   - Use para criar caixas em torno de definições, exemplos, conclusões.

4. {"type": "arrow", "x1": <int>, "y1": <int>, "x2": <int>, "y2": <int>, "color": "<#hex|nome>", "width": <int 4-10>}
   - Seta de (x1,y1) → (x2,y2). A ponta fica em (x2,y2).
   - Use para conectar conceitos, apontar para palavras, mostrar fluxo.

5. {"type": "underline", "x1": <int>, "y1": <int>, "x2": <int>, "color": "<#hex|nome>", "width": <int 3-8>}
   - Sublinhado horizontal. y2 fica igual a y1.
   - Use para enfatizar palavras-chave já escritas.

REGRAS DE LAYOUT (CANVAS 1920×1080):
- Use a área útil: x entre 140 e 1780, y entre 140 e 940.
- Não sobreponha textos uns aos outros. Use linhas separadas verticalmente
  (typically ~120-160px entre linhas de texto).
- Coloque cada operação de FORMA depois das operações de TEXTO relacionadas
  — a caneta sempre escreve primeiro, depois enfatiza/sublinha/circula.
- Máximo de 8 formas geométricas. Texto livre não conta para esse limite.
- Cores: se receber instrução de cor específica, respeite. Caso contrário
  use #1f2937 (cinza-escuro) para texto e cores expressivas para destaque
  (vermelho #dc2626 para alertas, azul #2563eb para neutros, verde #16a34a
  para positivos).

REGRAS CRÍTICAS:
- NÃO adicione campos extras nos objetos.
- Coordenadas SEMPRE inteiros.
- Cores SEMPRE como "#RRGGBB" ou nome básico em inglês.
- Retorne APENAS o JSON, sem markdown, sem ```json fences, sem texto antes/depois.
- O array "ops" deve ter no máximo 12 itens no total.
- Se o pedido for ambíguo, faça uma interpretação razoável e descreva no "summary".

EXEMPLO DE SAÍDA:
{
  "summary": "Vou escrever 'Vendas Q4' centralizado, fazer um círculo vermelho em volta, e desenhar uma seta apontando para baixo até o valor 'R$ 1M'.",
  "ops": [
    {"type": "text", "text": "Vendas Q4", "x": 720, "y": 280, "font_size": 90, "color": "#1f2937"},
    {"type": "circle", "cx": 950, "cy": 320, "rx": 280, "ry": 80, "color": "#dc2626", "width": 6},
    {"type": "text", "text": "R$ 1M", "x": 820, "y": 660, "font_size": 110, "color": "#16a34a"},
    {"type": "arrow", "x1": 960, "y1": 420, "x2": 960, "y2": 640, "color": "#2563eb", "width": 7}
  ]
}
"""


async def generate_render_plan(
    description: str,
    *,
    base_color: Optional[str] = None,
    allow_color_per_shape: bool = True,
) -> dict:
    """Ask Claude Sonnet 4.5 to produce a render plan for the given
    natural-language description.

    Returns a dict {"summary": str, "ops": list[dict]}. Raises on any
    LLM or parsing failure — caller should surface a clean error to the
    UI rather than rendering an empty whiteboard."""
    if not description or not description.strip():
        raise ValueError("description is required")

    key = os.environ.get("EMERGENT_LLM_KEY")
    if not key:
        raise RuntimeError("EMERGENT_LLM_KEY not configured")

    from emergentintegrations.llm.chat import LlmChat, UserMessage  # type: ignore

    user_msg = _build_user_message(description, base_color, allow_color_per_shape)

    chat = LlmChat(
        api_key=key,
        session_id=f"wb-plan-{abs(hash(description)) & 0xFFFFFF:06x}",
        system_message=SYSTEM_PROMPT,
    ).with_model("anthropic", "claude-sonnet-4-5-20250929")

    resp = await chat.send_message(UserMessage(text=user_msg))
    if not resp:
        raise RuntimeError("LLM returned empty response")

    plan = _parse_plan(str(resp))
    return _normalize_plan(plan, base_color=base_color, allow_color_per_shape=allow_color_per_shape)


def _build_user_message(
    description: str,
    base_color: Optional[str],
    allow_color_per_shape: bool,
) -> str:
    color_hint = (
        f"Cor base configurada pelo autor: {base_color}. "
        f"{'Você PODE usar cores diferentes para enfatizar formas distintas.' if allow_color_per_shape else 'Use APENAS essa cor em TODOS os textos e formas.'}"
        if base_color else
        "Sem cor base configurada — use defaults definidos no prompt do sistema."
    )
    return (
        f"PEDIDO DO AUTOR:\n{description.strip()}\n\n"
        f"{color_hint}\n\n"
        "Gere o JSON do plano agora."
    )


_JSON_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _parse_plan(raw: str) -> dict:
    """Strip optional code fences then json.loads. Raises if invalid."""
    text = _JSON_FENCE.sub("", raw.strip()).strip()
    # Sometimes the model prefixes the JSON with a sentence — find the
    # first { and last } and parse the slice between.
    if not text.startswith("{"):
        first = text.find("{")
        last = text.rfind("}")
        if first == -1 or last == -1 or last < first:
            raise ValueError(f"no JSON object in LLM output: {raw[:160]!r}")
        text = text[first : last + 1]
    return json.loads(text)


def _normalize_plan(
    plan: dict,
    *,
    base_color: Optional[str],
    allow_color_per_shape: bool,
) -> dict:
    """Clamp every coordinate to canvas bounds, drop unknown op types,
    enforce the 12-op cap, and coerce colors when single-color mode is
    requested. This is the safety net for an occasionally-creative
    model — the renderer should never receive an out-of-spec op."""
    ops_in = plan.get("ops") or []
    if not isinstance(ops_in, list):
        ops_in = []
    summary = (plan.get("summary") or "").strip()[:400]

    allowed_types = {"text", "circle", "rectangle", "arrow", "underline"}
    ops_out: list[dict] = []
    for op in ops_in[:MAX_OPS]:
        if not isinstance(op, dict):
            continue
        t = (op.get("type") or "").lower().strip()
        if t not in allowed_types:
            continue
        cleaned = {"type": t}
        if t == "text":
            cleaned.update({
                "text": str(op.get("text") or "").strip()[:240],
                "x": _clamp_int(op.get("x"), MARGIN, CANVAS_W - MARGIN),
                "y": _clamp_int(op.get("y"), MARGIN, CANVAS_H - MARGIN),
                "font_size": _clamp_int(op.get("font_size", 80), 36, 140),
            })
            if not cleaned["text"]:
                continue
        elif t == "circle":
            cleaned.update({
                "cx": _clamp_int(op.get("cx"), 0, CANVAS_W),
                "cy": _clamp_int(op.get("cy"), 0, CANVAS_H),
                "rx": _clamp_int(op.get("rx", 80), 20, CANVAS_W // 2),
                "ry": _clamp_int(op.get("ry", op.get("rx", 80)), 20, CANVAS_H // 2),
                "width": _clamp_int(op.get("width", 6), 3, 12),
            })
        elif t == "rectangle":
            cleaned.update({
                "x": _clamp_int(op.get("x"), 0, CANVAS_W),
                "y": _clamp_int(op.get("y"), 0, CANVAS_H),
                "w": _clamp_int(op.get("w", 200), 30, CANVAS_W),
                "h": _clamp_int(op.get("h", 100), 30, CANVAS_H),
                "width": _clamp_int(op.get("width", 6), 3, 12),
            })
        elif t == "arrow":
            cleaned.update({
                "x1": _clamp_int(op.get("x1"), 0, CANVAS_W),
                "y1": _clamp_int(op.get("y1"), 0, CANVAS_H),
                "x2": _clamp_int(op.get("x2"), 0, CANVAS_W),
                "y2": _clamp_int(op.get("y2"), 0, CANVAS_H),
                "width": _clamp_int(op.get("width", 7), 3, 12),
            })
        elif t == "underline":
            y = _clamp_int(op.get("y1"), 0, CANVAS_H)
            cleaned.update({
                "x1": _clamp_int(op.get("x1"), 0, CANVAS_W),
                "y1": y,
                "x2": _clamp_int(op.get("x2"), 0, CANVAS_W),
                "width": _clamp_int(op.get("width", 5), 3, 10),
            })
        # Color: if shape-specific colors disabled, force base_color.
        color_in = op.get("color")
        if not allow_color_per_shape and base_color:
            cleaned["color"] = base_color
        elif color_in:
            cleaned["color"] = str(color_in).strip()[:32]
        elif base_color:
            cleaned["color"] = base_color
        ops_out.append(cleaned)

    return {"summary": summary, "ops": ops_out}


def _clamp_int(v, lo: int, hi: int) -> int:
    try:
        i = int(round(float(v)))
    except (TypeError, ValueError):
        i = lo
    return max(lo, min(hi, i))
