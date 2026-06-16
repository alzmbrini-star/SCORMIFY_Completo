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
- A fonte usada é uma manuscrita estilo "Caveat" — bem mais LARGA que
  fontes comuns. Para CALCULAR largura aproximada: cada caractere ocupa
  ~0.55 × font_size em px. Ex.: "PowerPoint/PDF/Word" (19 chars) em
  font_size=80 ⇒ largura ≈ 19 × 0.55 × 80 = 836px. Reserve espaço!
- Caixas (rectangle) e círculos (circle) que ENVOLVAM um texto devem ser
  pelo menos 30-50px maiores que o texto em cada direção. Em caso de
  dúvida, GENEROSIDADE > apertado. Ex.: para uma caixa em torno de
  "PowerPoint/PDF/Word" em font_size 80, use w=900 h=150.
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
    plan = _normalize_plan(plan, base_color=base_color, allow_color_per_shape=allow_color_per_shape)
    # Post-LLM safety net: the model can't predict the rendered width
    # of the Caveat handwriting font (which is ~30-50% wider per char
    # than a typical sans-serif at the same font_size). Without this
    # step the LLM-suggested boxes habitually clip text like
    # "PowerPoint/PDF/Word" out the right side. We measure each text op
    # with the actual font and grow any shape that's meant to wrap it.
    plan = _autofit_shapes(plan)
    # Re-clamp after autofit since growing shapes can push them past the
    # canvas boundary. Better to clip than to draw off-screen.
    plan = _clamp_shapes_to_canvas(plan)
    return plan


def _clamp_shapes_to_canvas(plan: dict) -> dict:
    """Final pass: ensure no shape extends past the canvas edges after
    autofit. Shrinks if necessary."""
    for op in plan.get("ops", []):
        t = op.get("type")
        if t == "rectangle":
            op["x"] = max(0, min(CANVAS_W - 10, op["x"]))
            op["y"] = max(0, min(CANVAS_H - 10, op["y"]))
            op["w"] = max(30, min(CANVAS_W - op["x"], op["w"]))
            op["h"] = max(30, min(CANVAS_H - op["y"], op["h"]))
        elif t == "circle":
            # Pull centers in if the ellipse would extend off-canvas.
            op["rx"] = min(op["rx"], min(op["cx"], CANVAS_W - op["cx"]))
            op["ry"] = min(op["ry"], min(op["cy"], CANVAS_H - op["cy"]))
            op["rx"] = max(20, op["rx"])
            op["ry"] = max(20, op["ry"])
    return plan


def _measure_text_bbox(text: str, font_size: int) -> tuple[int, int]:
    """Return (width, height) of `text` rendered with the default
    whiteboard font (Caveat) at `font_size`.

    Uses `font.getlength()` (advance width) — the visual horizontal
    space the text actually occupies — rather than `getbbox()` which
    returns the tighter ink bbox and underestimates how much room a
    box needs around the text. Falls back to a heuristic if PIL/font
    loading fails — never raises so we don't break the plan flow."""
    try:
        from PIL import ImageFont
        from .whiteboard_renderer import _resolve_font_path  # type: ignore
        font = ImageFont.truetype(str(_resolve_font_path(None)), font_size)
        # Advance width = visual width including final char's right bearing.
        width = int(font.getlength(text))
        bbox = font.getbbox(text)
        height = bbox[3] - bbox[1]
        # Add 8% horizontal safety so descenders/italics don't poke out.
        return (int(width * 1.08), int(height * 1.15))
    except Exception:
        # Caveat is ~0.55× font_size wide per char on average.
        return (int(len(text) * font_size * 0.55), int(font_size * 1.1))


def _autofit_shapes(plan: dict) -> dict:
    """Grow rectangles and circles to comfortably contain any text op
    whose center sits inside them. Uses real font measurements rather
    than the LLM's guess.

    Heuristic for matching shapes ↔ texts:
      - Shape `S` "contains" text op `T` if T's anchor (x,y) is inside
        S's bounding rectangle (with a small tolerance). When the LLM
        outputs a shape paired with a label, this anchor-inside test is
        a reliable association.
      - Once matched, we compute the text's actual rendered bbox and
        expand S to fit it + 30px padding on each side.
    """
    ops = plan.get("ops") or []
    # Pre-compute rendered bboxes for every text op.
    text_boxes: list[dict] = []
    for op in ops:
        if op.get("type") != "text":
            continue
        tw, th = _measure_text_bbox(op["text"], op["font_size"])
        text_boxes.append({
            "x0": op["x"], "y0": op["y"],
            "x1": op["x"] + tw, "y1": op["y"] + th,
            "cx": op["x"] + tw // 2, "cy": op["y"] + th // 2,
        })

    PAD = 30
    for op in ops:
        t = op.get("type")
        if t == "rectangle":
            x0, y0 = op["x"], op["y"]
            x1, y1 = x0 + op["w"], y0 + op["h"]
            for tb in text_boxes:
                # Text whose center is inside the rectangle → expand to fit.
                if x0 - PAD <= tb["cx"] <= x1 + PAD and y0 - PAD <= tb["cy"] <= y1 + PAD:
                    nx0 = min(x0, tb["x0"] - PAD)
                    ny0 = min(y0, tb["y0"] - PAD)
                    nx1 = max(x1, tb["x1"] + PAD)
                    ny1 = max(y1, tb["y1"] + PAD)
                    op["x"], op["y"] = max(0, nx0), max(0, ny0)
                    op["w"], op["h"] = nx1 - op["x"], ny1 - op["y"]
                    x0, y0, x1, y1 = op["x"], op["y"], op["x"] + op["w"], op["y"] + op["h"]
        elif t == "circle":
            cx, cy = op["cx"], op["cy"]
            rx, ry = op["rx"], op["ry"]
            # Ellipse bbox.
            bx0, by0, bx1, by1 = cx - rx, cy - ry, cx + rx, cy + ry
            for tb in text_boxes:
                if bx0 - PAD <= tb["cx"] <= bx1 + PAD and by0 - PAD <= tb["cy"] <= by1 + PAD:
                    # Required half-axes to contain the text's diagonal
                    # with comfort. We use an inscribed-ellipse rule:
                    # a text rectangle of width W and height H fits in an
                    # ellipse iff (W/2/rx)² + (H/2/ry)² <= 1 — so we need
                    # rx and ry slightly larger than W/sqrt(2) and H/sqrt(2).
                    half_w = (tb["x1"] - tb["x0"]) / 2 + PAD
                    half_h = (tb["y1"] - tb["y0"]) / 2 + PAD
                    # Use 1.1× factor for breathing room.
                    new_rx = max(rx, int(half_w * 1.42))   # ~sqrt(2)
                    new_ry = max(ry, int(half_h * 1.42))
                    op["rx"], op["ry"] = new_rx, new_ry
                    rx, ry = new_rx, new_ry
                    bx0, by0, bx1, by1 = cx - rx, cy - ry, cx + rx, cy + ry
    return plan


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
