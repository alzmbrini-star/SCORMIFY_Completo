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

1. {"type": "text", "text": "<conteúdo>", "x": <int>, "y": <int>, "font_size": <int 36-110>, "color": "<#hex|nome>"}
   - Renderiza o texto à mão escrita. `x,y` é o canto superior-esquerdo.
   - Default seguro: font_size 60-70 para textos curtos (<10 chars),
     font_size 40-55 para textos médios (10-20 chars). Veja regras de
     layout abaixo para fonts que precisam caber em uma zona específica.

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
- **ZONAS HORIZONTAIS** (use no máximo UMA zona por shape boxed):
    LEFT zone   : x ∈ [140,  620]   (largura útil ~480px)
    CENTER zone : x ∈ [700, 1220]   (largura útil ~520px)
    RIGHT zone  : x ∈ [1300, 1780]  (largura útil ~480px)
  Os gaps [620,700] e [1220,1300] são RESPIRADOUROS — NÃO coloque
  shapes que cruzem essas faixas. O sistema vai automaticamente
  reduzir o font_size do seu texto se ele for largo demais para a
  zona escolhida, então PREFIRA fonts menores em vez de cruzar zonas.
- **ESPAÇAMENTO VERTICAL**: shapes empilhadas verticalmente na mesma
  zona devem ter mínimo 60px entre o `bottom` de uma e o `top` da
  próxima. Não cole as caixas — respiro entre elas evita poluição.
- Não sobreponha textos uns aos outros. Use linhas separadas verticalmente
  (typically ~140-180px entre linhas de texto).
- A fonte usada é uma manuscrita estilo "Caveat" — bem mais LARGA que
  fontes comuns. Para CALCULAR largura aproximada: cada caractere ocupa
  ~0.55 × font_size em px. Ex.: "PowerPoint/PDF/Word" (19 chars) em
  font_size=70 ⇒ largura ≈ 19 × 0.55 × 70 ≈ 731px ❌ (estoura zona de 480px).
  Para caber em uma zona, use font_size=40 ⇒ 19 × 0.55 × 40 ≈ 418px ✓.
- **REGRA DE OURO PARA TEXTO EM CAIXA**: font_size ≤ (largura_zona − 80) ÷ (len(texto) × 0.55)
  Textos longos (>15 chars) em zonas estreitas devem usar font_size 40-55.
  Textos curtos (<10 chars) podem usar font_size 70-90.
- Caixas (rectangle) e círculos (circle) que ENVOLVAM um texto devem ser
  pelo menos 30-50px maiores que o texto em cada direção. Em caso de
  dúvida, GENEROSIDADE > apertado.
- Coloque cada operação de FORMA depois das operações de TEXTO relacionadas
  — a caneta sempre escreve primeiro, depois enfatiza/sublinha/circula.
- Máximo de 8 formas geométricas. Texto livre não conta para esse limite.
- Cores: se receber instrução de cor específica, respeite. Caso contrário
  use #1f2937 (cinza-escuro) para texto e cores expressivas para destaque
  (vermelho #dc2626 para alertas, azul #2563eb para neutros, verde #16a34a
  para positivos).

POST-PROCESSAMENTO (importante saber):
- O sistema executa DEPOIS de você um auto-fit que aumenta caixas se o
  texto não couber. Se você usar font_size muito grande, a caixa vai
  crescer e invadir a próxima zona, causando sobreposição. **Prefira
  font_size pequeno** para textos longos.
- O sistema também aplica um passe de separação que encolhe caixas
  sobrepostas. Para evitar surpresas, mantenha pelo menos 30px de gap
  entre AABBs de shapes distintas.

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
    # ── Spacing pipeline ────────────────────────────────────────────
    # 1. Cap each text op's font_size so its rendered width never
    #    exceeds the available zone (~ canvas/3). Without this guard
    #    the LLM happily emits "PowerPoint/PDF/Word" at font_size 80
    #    (rendered width ~700 px) which forces the autofit step to
    #    grow the surrounding box into the next zone, causing the
    #    boxes to overlap the central circle.
    plan = _cap_text_font_to_zone(plan)
    # 2. Grow shapes to fit (now-correctly-sized) texts.
    plan = _autofit_shapes(plan)
    # 3. Clamp shapes to canvas edges.
    plan = _clamp_shapes_to_canvas(plan)
    # 4. Enforce a minimum gap between any two non-arrow shapes so the
    #    composition reads cleanly even when the LLM places elements
    #    too close together. Shrinks rectangles horizontally when the
    #    collision can be resolved that way; otherwise leaves them
    #    alone (better to clip a couple of px than corrupt arrows).
    plan = _enforce_shape_separation(plan)
    return plan


# ── pre-autofit: clamp text widths to a single zone ─────────────────

# A "zone" is the maximum horizontal slice of canvas that a single
# labelled box is allowed to occupy. With ~140 px side margins and 80
# px gutters between zones, ~530 px ≈ canvas/3 keeps boxes inside their
# zone after autofit grows them by 2×PAD (40 px each side).
MAX_BOXED_TEXT_WIDTH = 420
MIN_FONT_SIZE = 36
SHAPE_MIN_GAP = 30


def _cap_text_font_to_zone(plan: dict) -> dict:
    """For every text op, iteratively reduce font_size until the
    rendered width fits inside one zone (`MAX_BOXED_TEXT_WIDTH`).

    The reduction stops at `MIN_FONT_SIZE` — below that the text would
    be illegible at viewing distance. A loud warning is logged in that
    edge case (it means the LLM picked a label that is just too long
    for a 3-zone layout; the autofit will then grow the box past the
    zone, which the user will see, but at least the text stays
    readable)."""
    for op in plan.get("ops", []):
        if op.get("type") != "text":
            continue
        text = op.get("text") or ""
        fs = int(op.get("font_size") or 80)
        original_fs = fs
        # Step down by 4 px at a time until the rendered width fits or
        # we hit the floor.
        while fs > MIN_FONT_SIZE:
            w, _ = _measure_text_bbox(text, fs)
            if w <= MAX_BOXED_TEXT_WIDTH:
                break
            fs -= 4
        if fs != original_fs:
            logger.info(
                "whiteboard-plan: scaled font_size for %r from %d → %d (zone-fit)",
                text[:30], original_fs, fs,
            )
        op["font_size"] = fs
    return plan


# ── post-autofit: push shapes apart to avoid clutter ────────────────


def _enforce_shape_separation(plan: dict) -> dict:
    """Detect pairs of non-arrow shapes whose AABBs overlap (or have
    less than `SHAPE_MIN_GAP` of clearance) and shrink the rectangles
    horizontally to restore the gap.

    Two reasons we shrink instead of moving:
      - Arrows reference shape edges by absolute (x1,y1)→(x2,y2). Moving
        a rectangle would visually disconnect the arrow.
      - Rectangle-circle pairs are usually intentional (e.g. central
        circle + side boxes); shrinking the rectangle keeps the
        composition while restoring spacing.
    """
    rect_circle_ops = [op for op in plan.get("ops", [])
                       if op.get("type") in ("rectangle", "circle")]
    if len(rect_circle_ops) < 2:
        return plan

    def aabb(op):
        if op["type"] == "rectangle":
            return (op["x"], op["y"], op["x"] + op["w"], op["y"] + op["h"])
        # circle
        return (op["cx"] - op["rx"], op["cy"] - op["ry"],
                op["cx"] + op["rx"], op["cy"] + op["ry"])

    def overlap_dx(a, b):
        """Return how many pixels the two AABBs overlap horizontally
        (positive = overlap, negative = gap)."""
        ax0, ay0, ax1, ay1 = a
        bx0, by0, bx1, by1 = b
        # Only relevant when vertical ranges actually intersect.
        if ay1 <= by0 or by1 <= ay0:
            return -float("inf")
        return min(ax1, bx1) - max(ax0, bx0)

    # One pass is enough for the typical 4-8 shape plans.
    for i, op_a in enumerate(rect_circle_ops):
        for op_b in rect_circle_ops[i + 1:]:
            ov = overlap_dx(aabb(op_a), aabb(op_b))
            # `ov + SHAPE_MIN_GAP` is how much we need to push apart.
            needed = ov + SHAPE_MIN_GAP
            if needed <= 0:
                continue
            # Prefer shrinking a rectangle (less visible than circle).
            target = None
            if op_a["type"] == "rectangle":
                target = op_a
            elif op_b["type"] == "rectangle":
                target = op_b
            else:
                # Two circles overlapping — unusual; skip rather than risk damage.
                continue
            # Decide which side of `target` to shrink: the side that
            # faces the other shape.
            other = op_b if target is op_a else op_a
            other_box = aabb(other)
            tx0, _, tx1, _ = aabb(target)
            ocx = (other_box[0] + other_box[2]) / 2
            tcx = (tx0 + tx1) / 2
            shrink = int(needed)
            # Don't shrink below 80 px wide — would clip text badly.
            if target["w"] - shrink < 80:
                shrink = max(0, target["w"] - 80)
            if shrink <= 0:
                continue
            if ocx > tcx:
                # Other is to the right → trim target's right side.
                target["w"] -= shrink
            else:
                # Other is to the left → trim target's left side (also bump x).
                target["x"] += shrink
                target["w"] -= shrink
            logger.info(
                "whiteboard-plan: separated overlapping shapes by %dpx (shrunk rect)",
                shrink,
            )
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

    Combines `font.getlength()` (advance width) with `font.getbbox()`
    (ink right edge) and takes the larger — for slanted handwriting
    fonts these can differ noticeably and we always want to size the
    bounding shape against the visually rightmost pixel. Falls back to
    a heuristic if PIL/font loading fails — never raises so we don't
    break the plan flow."""
    try:
        from PIL import ImageFont
        from .whiteboard_renderer import _resolve_font_path  # type: ignore
        font = ImageFont.truetype(str(_resolve_font_path(None)), font_size)
        advance = int(font.getlength(text))
        bbox = font.getbbox(text)
        ink_w = bbox[2] - bbox[0]
        # Use the larger of the two so wide italic strokes (Caveat's "d",
        # "f", "/") never escape the autofit box.
        width = max(advance, ink_w)
        height = bbox[3] - bbox[1]
        # 12% horizontal safety so descenders/italic flicks don't poke
        # out. Heights get 18% for ascender + descender comfort.
        return (int(width * 1.12), int(height * 1.18))
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

    PAD = 40
    for op in ops:
        t = op.get("type")
        if t == "rectangle":
            x0, y0 = op["x"], op["y"]
            x1, y1 = x0 + op["w"], y0 + op["h"]
            for tb in text_boxes:
                # MATCH STRATEGY (2026-02 fix): the previous "text center
                # inside box" rule broke when the LLM produced a NARROW
                # box around WIDE text — the text's center fell off the
                # right edge of the box, the match failed, and the box
                # stayed clipped. We now associate text↔box when the
                # text's vertical center sits inside the box's vertical
                # range (with PAD tolerance) AND the text horizontally
                # overlaps the box even slightly (also with PAD). This
                # correctly catches "text that visually belongs to the
                # box, regardless of how wrong the LLM's width was".
                vertical_match = (y0 - PAD) <= tb["cy"] <= (y1 + PAD)
                horizontal_overlap = not (tb["x1"] < x0 - PAD or tb["x0"] > x1 + PAD)
                if vertical_match and horizontal_overlap:
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
                vertical_match = (by0 - PAD) <= tb["cy"] <= (by1 + PAD)
                horizontal_overlap = not (tb["x1"] < bx0 - PAD or tb["x0"] > bx1 + PAD)
                if vertical_match and horizontal_overlap:
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
