"""AI-generated render plan for the Whiteboard.

Given a natural-language description from the author, asks OpenAI
(with a legacy provider fallback) to return a structured
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
import math
import os
import re
import uuid
from typing import Optional

logger = logging.getLogger("server.whiteboard_ai")

CANVAS_W = 1920
CANVAS_H = 1080
MARGIN = 140
MAX_OPS = 12   # 4 text + 8 shapes worst case


def _whiteboard_ai_credentials() -> tuple[str, str, str]:
    """Resolve the configured provider without breaking legacy installs."""
    openai_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if openai_key:
        model = (
            os.environ.get("OPENAI_WHITEBOARD_MODEL")
            or os.environ.get("OPENAI_TEXT_MODEL")
            or "gpt-4o"
        ).strip()
        return openai_key, "openai", model

    legacy_key = (os.environ.get("EMERGENT_LLM_KEY") or "").strip()
    if legacy_key:
        model = (
            os.environ.get("WHITEBOARD_LEGACY_MODEL")
            or "claude-sonnet-4-5-20250929"
        ).strip()
        return legacy_key, "anthropic", model

    raise RuntimeError(
        "OPENAI_API_KEY não configurada para o Whiteboard IA"
    )

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
   - **BULLETS / MARCADORES DE LISTA**: quando o autor pedir "bullets",
     "itens", "marcadores", "lista colorida" ou similar, use circle MUITO
     PEQUENO (rx=ry entre **12 e 22 px**) posicionado à ESQUERDA do
     texto correspondente (gap horizontal ~30-50px). NUNCA use um circle
     grande tentando "envolver" cada item de lista — o efeito visual fica
     poluído e os círculos se sobrepõem. O bullet é um marcador discreto,
     não uma moldura.
     Exemplo: para um item "Compatível com LMS" em (x=300, y=400, font_size=60),
     o bullet correspondente seria:
       {"type": "circle", "cx": 250, "cy": 420, "rx": 16, "ry": 16, "color": "#dc2626", "width": 6}

3. {"type": "rectangle", "x": <int>, "y": <int>, "w": <int>, "h": <int>, "color": "<#hex|nome>", "width": <int 4-10>}
   - Retângulo com canto superior-esquerdo (x,y) e largura/altura.
   - Use para criar caixas em torno de definições, exemplos, conclusões.

4. {"type": "arrow", "x1": <int>, "y1": <int>, "x2": <int>, "y2": <int>, "color": "<#hex|nome>", "width": <int 4-10>}
   - Seta de (x1,y1) → (x2,y2). A ponta fica em (x2,y2).
   - Use para conectar conceitos, apontar para palavras, mostrar fluxo.

5. {"type": "underline", "x1": <int>, "y1": <int>, "x2": <int>, "color": "<#hex|nome>", "width": <int 3-8>}
   - Sublinhado horizontal. y2 fica igual a y1.
   - Use para enfatizar palavras-chave já escritas.

6. {"type": "icon", "name": "<nome-em-ingles>", "x": <int>, "y": <int>, "size": <int 100-400>, "color": "<#hex|nome>", "width": <int 3-8>}
   - Desenha um OBJETO em line-art traçado pela caneta (árvore, cadeira,
     casa, pessoa...). x,y são o CENTRO do desenho; size é a largura total.
   - Use SEMPRE que o autor pedir para "desenhar" um objeto do mundo real.
   - "name" em inglês kebab-case do catálogo Lucide. Exemplos disponíveis:
     tree-deciduous, tree-pine, trees, armchair, rocking-chair, house,
     building, factory, store, school, hospital, church, car, truck, bus,
     plane, rocket, sailboat, bike, train-front, user, users, baby, brain,
     heart, hand, eye, ear, footprints, dog, cat, bird, fish, rabbit,
     turtle, bug, lightbulb, laptop, smartphone, monitor, tv, camera,
     printer, keyboard, mouse, headphones, mic, book-open, notebook-pen,
     graduation-cap, pencil, briefcase, banknote, coins, credit-card,
     piggy-bank, wallet, chart-column, chart-pie, trending-up, target,
     trophy, medal, award, crown, shield, settings, wrench, hammer, key,
     lock, mail, phone, clock, calendar, hourglass, bell, music, star,
     sun, moon, cloud, cloud-rain, umbrella, snowflake, flame, leaf,
     flower, sprout, apple, coffee, pizza, utensils, cake, shopping-cart,
     gift, package, map, map-pin, globe, compass, flag, search, thumbs-up,
     smile, frown, stethoscope, pill, syringe, dumbbell, gamepad-2,
     handshake, scale, gavel, anchor, sword, wand — e qualquer outro nome
     válido do catálogo Lucide (o sistema faz correspondência aproximada).
   - Deixe um espaço livre de pelo menos size×size na posição escolhida;
     não sobreponha icons a textos ou outras formas.
   - Combine com um "text" LOGO ABAIXO do desenho como legenda
     (y do texto ≈ y + size/2 + 40) quando fizer sentido.

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

- Setas NUNCA devem entrar em caixas ou círculos: cada endpoint da seta
  deve ficar a pelo menos 25px FORA da borda das formas que conecta.
  O sistema recorta automaticamente setas que invadem formas, mas
  prefira acertar de primeira.

REGRAS CRÍTICAS:
- Cada operação DEVE ter um `id` curto e único (ex.: "conceito_a",
  "caixa_a", "seta_a").
- Texto dentro de uma forma DEVE informar `container_id` com o id da
  rectangle/circle correspondente.
- Seta conectando elementos DEVE informar `from_id` e `to_id`.
- Sublinhado DEVE informar `target_id` com o id do texto sublinhado.
- Textos devem ser objetivos; prefira uma linha com até 48 caracteres.
- Não adicione outros campos além dos especificados e dos vínculos
  semânticos `id`, `container_id`, `from_id`, `to_id`, `target_id`.
- Coordenadas SEMPRE inteiros.
- Cores SEMPRE como "#RRGGBB" ou nome básico em inglês.
- Retorne APENAS o JSON, sem markdown, sem ```json fences, sem texto antes/depois.
- O array "ops" deve ter no máximo 12 itens no total.
- Se o pedido for ambíguo, faça uma interpretação razoável e descreva no "summary".

EXEMPLO DE SAÍDA:
{
  "summary": "Vou escrever 'Vendas Q4' centralizado, fazer um círculo vermelho em volta, e desenhar uma seta apontando para baixo até o valor 'R$ 1M'.",
  "ops": [
    {"id": "vendas", "type": "text", "text": "Vendas Q4", "x": 720, "y": 280, "font_size": 90, "color": "#1f2937", "container_id": "destaque_vendas"},
    {"id": "destaque_vendas", "type": "circle", "cx": 950, "cy": 320, "rx": 280, "ry": 80, "color": "#dc2626", "width": 6},
    {"id": "meta", "type": "text", "text": "R$ 1M", "x": 820, "y": 660, "font_size": 110, "color": "#16a34a"},
    {"id": "fluxo", "type": "arrow", "x1": 960, "y1": 420, "x2": 960, "y2": 640, "color": "#2563eb", "width": 7, "from_id": "destaque_vendas", "to_id": "meta"}
  ]
}
"""


async def generate_render_plan(
    description: str,
    *,
    base_color: Optional[str] = None,
    allow_color_per_shape: bool = True,
) -> dict:
    """Ask the configured LLM to produce a render plan for the given
    natural-language description.

    Returns a dict {"summary": str, "ops": list[dict]}. Raises on any
    LLM or parsing failure — caller should surface a clean error to the
    UI rather than rendering an empty whiteboard."""
    if not description or not description.strip():
        raise ValueError("description is required")

    key, provider, model = _whiteboard_ai_credentials()

    from emergentintegrations.llm.chat import LlmChat, UserMessage  # type: ignore

    user_msg = _build_user_message(description, base_color, allow_color_per_shape)

    chat = LlmChat(
        api_key=key,
        session_id=f"wb-plan-{uuid.uuid4().hex}",
        system_message=SYSTEM_PROMPT,
    ).with_model(provider, model)
    if provider == "openai":
        chat = chat.with_params(
            temperature=0.2,
            response_format={"type": "json_object"},
        )

    resp = await chat.send_message(UserMessage(text=user_msg))
    if not resp:
        raise RuntimeError("LLM returned empty response")

    plan = _parse_plan(str(resp))
    return prepare_render_plan(
        plan,
        base_color=base_color,
        allow_color_per_shape=allow_color_per_shape,
    )


def prepare_render_plan(
    plan: dict,
    *,
    base_color: Optional[str] = None,
    allow_color_per_shape: bool = True,
) -> dict:
    """Normalize and deterministically improve any AI or saved plan."""
    plan = _normalize_plan(
        plan,
        base_color=base_color,
        allow_color_per_shape=allow_color_per_shape,
    )
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
    # 5-6. Final geometric polish: center/fit texts inside their shapes
    #    and retract arrow endpoints to shape borders (never inside).
    plan = polish_plan_geometry(plan)
    plan["quality"] = _plan_quality_report(plan)
    return plan


def polish_plan_geometry(plan: dict) -> dict:
    """Deterministic geometry cleanup, safe to run on ANY plan (new or a
    previously-saved one being re-rendered):

    1. Texts associated with a rectangle/circle are font-shrunk until
       they FIT inside the shape and are re-centered in it — fixes
       labels bleeding out of their boxes/ellipses.
    2. Arrow endpoints that land inside a shape are retracted along the
       arrow's direction to the shape border + gap — arrows connect
       edge-to-edge instead of piercing the shapes.
    """
    plan = _fit_and_center_texts_in_shapes(plan)
    plan = _separate_free_texts(plan)
    plan = _clamp_texts_to_canvas(plan)
    plan = _align_underlines_to_targets(plan)
    plan = _resolve_linked_arrows(plan)
    plan = _retract_arrows_from_shapes(plan)
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
            # Min 10px (was 20) so bullets / small markers survive the
            # clamp without being inflated.
            op["rx"] = max(10, op["rx"])
            op["ry"] = max(10, op["ry"])
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
            "op": op,
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
                linked_id = tb["op"].get("container_id")
                if linked_id and linked_id != op.get("id"):
                    continue
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
                if (linked_id and linked_id == op.get("id")) or (
                    vertical_match and horizontal_overlap
                ):
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
            # GUARD: Small circles (≤25px both radii) are bullets / list
            # markers / decorative dots — they should NEVER grow to
            # "enclose" nearby text. Without this guard, the autofit
            # would balloon a tiny 16x16 bullet up to 200x80 to wrap
            # around the item's text label, producing huge overlapping
            # ovals stacked vertically (the exact bug from the user
            # screenshot 2026-02).
            if rx <= 25 and ry <= 25:
                continue
            # Ellipse bbox.
            bx0, by0, bx1, by1 = cx - rx, cy - ry, cx + rx, cy + ry
            for tb in text_boxes:
                linked_id = tb["op"].get("container_id")
                if linked_id and linked_id != op.get("id"):
                    continue
                vertical_match = (by0 - PAD) <= tb["cy"] <= (by1 + PAD)
                horizontal_overlap = not (tb["x1"] < bx0 - PAD or tb["x0"] > bx1 + PAD)
                if (linked_id and linked_id == op.get("id")) or (
                    vertical_match and horizontal_overlap
                ):
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

    allowed_types = {"text", "circle", "rectangle", "arrow", "underline", "icon"}
    ops_out: list[dict] = []
    for op in ops_in[:MAX_OPS]:
        if not isinstance(op, dict):
            continue
        t = (op.get("type") or "").lower().strip()
        if t not in allowed_types:
            continue
        cleaned = {"type": t}
        op_id = _safe_id(op.get("id"))
        if op_id:
            cleaned["id"] = op_id
        if t == "text":
            cleaned.update({
                "text": str(op.get("text") or "").strip()[:240],
                "x": _clamp_int(op.get("x"), MARGIN, CANVAS_W - MARGIN),
                "y": _clamp_int(op.get("y"), MARGIN, CANVAS_H - MARGIN),
                "font_size": _clamp_int(op.get("font_size", 80), 36, 140),
            })
            container_id = _safe_id(op.get("container_id"))
            if container_id:
                cleaned["container_id"] = container_id
            if not cleaned["text"]:
                continue
        elif t == "circle":
            cleaned.update({
                "cx": _clamp_int(op.get("cx"), 0, CANVAS_W),
                "cy": _clamp_int(op.get("cy"), 0, CANVAS_H),
                # Min radius lowered from 20 → 10 so the AI can output
                # tiny bullets / list markers without the clamp forcing
                # them to grow.
                "rx": _clamp_int(op.get("rx", 80), 10, CANVAS_W // 2),
                "ry": _clamp_int(op.get("ry", op.get("rx", 80)), 10, CANVAS_H // 2),
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
            from_id = _safe_id(op.get("from_id"))
            to_id = _safe_id(op.get("to_id"))
            if from_id:
                cleaned["from_id"] = from_id
            if to_id:
                cleaned["to_id"] = to_id
        elif t == "underline":
            y = _clamp_int(op.get("y1"), 0, CANVAS_H)
            cleaned.update({
                "x1": _clamp_int(op.get("x1"), 0, CANVAS_W),
                "y1": y,
                "x2": _clamp_int(op.get("x2"), 0, CANVAS_W),
                "width": _clamp_int(op.get("width", 5), 3, 10),
            })
            target_id = _safe_id(op.get("target_id"))
            if target_id:
                cleaned["target_id"] = target_id
        elif t == "icon":
            from .whiteboard_icons import resolve_icon_name
            resolved = resolve_icon_name(op.get("name"))
            if not resolved:
                continue
            size = _clamp_int(op.get("size", 220), 80, 500)
            cleaned.update({
                "name": resolved,
                "x": _clamp_int(op.get("x"), size // 2, CANVAS_W - size // 2),
                "y": _clamp_int(op.get("y"), size // 2, CANVAS_H - size // 2),
                "size": size,
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


def _safe_id(value) -> str:
    candidate = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value or "").strip())
    return candidate.strip("_")[:64]


def _clamp_int(v, lo: int, hi: int) -> int:
    try:
        i = int(round(float(v)))
    except (TypeError, ValueError):
        i = lo
    return max(lo, min(hi, i))


# ── geometry polish: text-in-shape fitting + arrow retraction ────────

TEXT_INNER_PAD = 22      # min clearance between text and shape border
ARROW_GAP = 16           # arrows stop this many px BEFORE a shape border
MIN_ARROW_LEN = 30       # don't retract an arrow into nothingness
MIN_FIT_FONT = 24        # never shrink boxed text below this


def _shape_aabb_poly(sh: dict) -> tuple[float, float, float, float]:
    if sh["type"] == "rectangle":
        return (sh["x"], sh["y"], sh["x"] + sh["w"], sh["y"] + sh["h"])
    return (sh["cx"] - sh["rx"], sh["cy"] - sh["ry"],
            sh["cx"] + sh["rx"], sh["cy"] + sh["ry"])


def _shape_center(sh: dict) -> tuple[float, float]:
    if sh["type"] == "rectangle":
        return (sh["x"] + sh["w"] / 2.0, sh["y"] + sh["h"] / 2.0)
    return (float(sh["cx"]), float(sh["cy"]))


def _text_fits_shape(sh: dict, tw: float, th: float, pad: float) -> bool:
    if sh["type"] == "rectangle":
        return tw + 2 * pad <= sh["w"] and th + 2 * pad <= sh["h"]
    rx, ry = max(1.0, sh["rx"] - pad), max(1.0, sh["ry"] - pad)
    # A centered w×h rect fits in an ellipse iff (w/2/rx)² + (h/2/ry)² ≤ 1.
    return (tw / 2 / rx) ** 2 + (th / 2 / ry) ** 2 <= 1.0


def _text_metrics(text: str, font_size: int) -> tuple[int, int, int]:
    """(ink_width, ink_height, top_offset) with the real whiteboard font.
    `top_offset` is the gap between the draw anchor (top-left of the em
    box, what PIL's draw.text uses) and the first ink pixel — needed to
    center the VISIBLE glyphs, not the em box."""
    try:
        from PIL import ImageFont
        from .whiteboard_renderer import _resolve_font_path  # type: ignore
        font = ImageFont.truetype(str(_resolve_font_path(None)), font_size)
        bbox = font.getbbox(text)
        w = max(int(font.getlength(text)), bbox[2] - bbox[0])
        return w, bbox[3] - bbox[1], bbox[1]
    except Exception:
        return int(len(text) * font_size * 0.55), int(font_size * 0.75), int(font_size * 0.2)


def _fit_and_center_texts_in_shapes(plan: dict) -> dict:
    """Shrink + re-center each text inside the shape it belongs to."""
    ops = plan.get("ops") or []
    shapes = [
        op for op in ops
        if op.get("type") in ("rectangle", "circle")
        # Tiny circles are bullets/markers — never treat as containers.
        and not (op["type"] == "circle" and op.get("rx", 0) <= 25 and op.get("ry", 0) <= 25)
    ]
    if not shapes:
        return plan
    shape_by_id = {sh.get("id"): sh for sh in shapes if sh.get("id")}
    for top in ops:
        if top.get("type") != "text" or not top.get("text"):
            continue
        tw, th = _measure_text_bbox(top["text"], top["font_size"])
        tx0, ty0 = top["x"], top["y"]
        # Associate with the shape it overlaps the most.
        best = shape_by_id.get(top.get("container_id"))
        best_area = float(tw * th) if best else 0.0
        if best is None:
            for sh in shapes:
                bx0, by0, bx1, by1 = _shape_aabb_poly(sh)
                ix = max(0.0, min(bx1, tx0 + tw) - max(bx0, tx0))
                iy = max(0.0, min(by1, ty0 + th) - max(by0, ty0))
                if ix * iy > best_area:
                    best, best_area = sh, ix * iy
        # Meaningful overlap only (>30% of the text area) — otherwise the
        # text is a free-standing label near, not inside, the shape.
        if not best or best_area < 0.3 * (tw * th):
            continue
        fs = int(top["font_size"])
        while fs > MIN_FIT_FONT:
            tw, th = _measure_text_bbox(top["text"], fs)
            if _text_fits_shape(best, tw, th, TEXT_INNER_PAD):
                break
            fs -= 3
        if fs != top["font_size"]:
            logger.info(
                "whiteboard-plan: shrunk %r %d → %d to fit its shape",
                top["text"][:30], top["font_size"], fs,
            )
        top["font_size"] = fs
        ink_w, ink_h, top_off = _text_metrics(top["text"], fs)
        scx, scy = _shape_center(best)
        top["x"] = int(round(scx - ink_w / 2.0))
        top["y"] = int(round(scy - ink_h / 2.0 - top_off))
    return plan


def _text_aabb(op: dict) -> tuple[float, float, float, float]:
    ink_w, ink_h, top_off = _text_metrics(op["text"], int(op["font_size"]))
    x0 = float(op["x"])
    y0 = float(op["y"] + top_off)
    return x0, y0, x0 + ink_w, y0 + ink_h


def _separate_free_texts(plan: dict) -> dict:
    """Move independent labels just enough to prevent visible overlap."""
    texts = [
        op for op in plan.get("ops", [])
        if op.get("type") == "text" and not op.get("container_id")
    ]
    texts.sort(key=lambda op: (op.get("y", 0), op.get("x", 0)))
    gap = 22
    for index, current in enumerate(texts):
        for previous in texts[:index]:
            ax0, ay0, ax1, ay1 = _text_aabb(previous)
            bx0, by0, bx1, by1 = _text_aabb(current)
            horizontal_overlap = min(ax1, bx1) - max(ax0, bx0)
            vertical_overlap = min(ay1, by1) - max(ay0, by0)
            if horizontal_overlap <= 0 or vertical_overlap <= 0:
                continue
            shift = int(math.ceil(ay1 + gap - by0))
            candidate = current["y"] + shift
            _, _, _, candidate_bottom = _text_aabb({**current, "y": candidate})
            if candidate_bottom <= CANVAS_H - MARGIN:
                current["y"] = candidate
            else:
                current["y"] = max(MARGIN, int(ay0 - gap - (by1 - by0)))
    return plan


def _clamp_texts_to_canvas(plan: dict) -> dict:
    """Keep the visible ink, rather than only the text anchor, on canvas."""
    for op in plan.get("ops", []):
        if op.get("type") != "text":
            continue
        x0, y0, x1, y1 = _text_aabb(op)
        if x0 < MARGIN:
            op["x"] += int(math.ceil(MARGIN - x0))
        elif x1 > CANVAS_W - MARGIN:
            op["x"] -= int(math.ceil(x1 - (CANVAS_W - MARGIN)))
        x0, y0, x1, y1 = _text_aabb(op)
        if y0 < MARGIN:
            op["y"] += int(math.ceil(MARGIN - y0))
        elif y1 > CANVAS_H - MARGIN:
            op["y"] -= int(math.ceil(y1 - (CANVAS_H - MARGIN)))
    return plan


def _align_underlines_to_targets(plan: dict) -> dict:
    """Derive exact underline geometry from its referenced text."""
    ops = plan.get("ops", [])
    by_id = {op.get("id"): op for op in ops if op.get("id")}
    for op in ops:
        if op.get("type") != "underline" or not op.get("target_id"):
            continue
        target = by_id.get(op["target_id"])
        if not target or target.get("type") != "text":
            continue
        x0, _, x1, y1 = _text_aabb(target)
        op["x1"] = _clamp_int(x0, 0, CANVAS_W)
        op["x2"] = _clamp_int(x1, 0, CANVAS_W)
        op["y1"] = _clamp_int(y1 + 10, 0, CANVAS_H)
    return plan


def _operation_center(op: dict) -> Optional[tuple[float, float]]:
    op_type = op.get("type")
    if op_type in ("rectangle", "circle"):
        return _shape_center(op)
    if op_type == "icon":
        return float(op["x"]), float(op["y"])
    if op_type == "text":
        x0, y0, x1, y1 = _text_aabb(op)
        return (x0 + x1) / 2, (y0 + y1) / 2
    return None


def _resolve_linked_arrows(plan: dict) -> dict:
    """Place linked arrow endpoints at element centers before edge clipping."""
    ops = plan.get("ops", [])
    by_id = {op.get("id"): op for op in ops if op.get("id")}
    for op in ops:
        if op.get("type") != "arrow":
            continue
        source = by_id.get(op.get("from_id"))
        target = by_id.get(op.get("to_id"))
        source_center = _operation_center(source) if source else None
        target_center = _operation_center(target) if target else None
        if source_center:
            op["x1"], op["y1"] = map(lambda v: int(round(v)), source_center)
        if target_center:
            op["x2"], op["y2"] = map(lambda v: int(round(v)), target_center)
    return plan


def _aabb_overlap(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
) -> float:
    return max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(
        0.0, min(a[3], b[3]) - max(a[1], b[1])
    )


def _plan_quality_report(plan: dict) -> dict:
    """Return concise, deterministic quality signals for the author preview."""
    ops = plan.get("ops", [])
    warnings: list[str] = []
    ids = {op.get("id") for op in ops if op.get("id")}

    for op in ops:
        for field in ("container_id", "from_id", "to_id", "target_id"):
            if op.get(field) and op[field] not in ids:
                warnings.append(f"Referência ausente: {op[field]}")

    texts = [op for op in ops if op.get("type") == "text"]
    for index, first in enumerate(texts):
        for second in texts[index + 1:]:
            if first.get("container_id") and first.get("container_id") == second.get("container_id"):
                continue
            if _aabb_overlap(_text_aabb(first), _text_aabb(second)) > 8:
                warnings.append("Há textos sobrepostos")
                break

    for op in texts:
        x0, y0, x1, y1 = _text_aabb(op)
        if x0 < 0 or y0 < 0 or x1 > CANVAS_W or y1 > CANVAS_H:
            warnings.append("Há texto fora da área visível")
            break

    for op in ops:
        if op.get("type") == "arrow":
            length = math.hypot(op["x2"] - op["x1"], op["y2"] - op["y1"])
            if length < MIN_ARROW_LEN:
                warnings.append("Há uma seta curta demais")

    unique_warnings = list(dict.fromkeys(warnings))
    score = max(0, 100 - 12 * len(unique_warnings))
    return {"score": score, "warnings": unique_warnings}


def _entry_t(a: tuple[float, float], b: tuple[float, float], sh: dict, gap: float):
    """First intersection t∈(0,1) of segment a→b with the border of the
    gap-inflated shape, entering from outside. None if no clean entry."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    if sh["type"] == "rectangle":
        x0, y0 = sh["x"] - gap, sh["y"] - gap
        x1, y1 = sh["x"] + sh["w"] + gap, sh["y"] + sh["h"] + gap
        t_enter, t_exit = 0.0, 1.0
        for p, q in ((-dx, a[0] - x0), (dx, x1 - a[0]), (-dy, a[1] - y0), (dy, y1 - a[1])):
            if abs(p) < 1e-9:
                if q < 0:
                    return None
                continue
            t = q / p
            if p < 0:
                t_enter = max(t_enter, t)
            else:
                t_exit = min(t_exit, t)
        if t_enter >= t_exit or t_enter <= 0.0 or t_enter >= 1.0:
            return None
        return t_enter
    # ellipse (circle op)
    rx, ry = sh["rx"] + gap, sh["ry"] + gap
    fx, fy = (a[0] - sh["cx"]) / rx, (a[1] - sh["cy"]) / ry
    gx, gy = dx / rx, dy / ry
    A = gx * gx + gy * gy
    B = 2 * (fx * gx + fy * gy)
    C = fx * fx + fy * fy - 1.0
    if A < 1e-12:
        return None
    disc = B * B - 4 * A * C
    if disc <= 0:
        return None
    t1 = (-B - math.sqrt(disc)) / (2 * A)
    if 0.0 < t1 < 1.0:
        return t1
    return None


def _point_in_shape(p: tuple[float, float], sh: dict, gap: float) -> bool:
    if sh["type"] == "rectangle":
        return (sh["x"] - gap <= p[0] <= sh["x"] + sh["w"] + gap
                and sh["y"] - gap <= p[1] <= sh["y"] + sh["h"] + gap)
    rx, ry = sh["rx"] + gap, sh["ry"] + gap
    return ((p[0] - sh["cx"]) / rx) ** 2 + ((p[1] - sh["cy"]) / ry) ** 2 <= 1.0


def _retract_arrows_from_shapes(plan: dict) -> dict:
    """Pull arrow endpoints out of any shape they pierce, stopping at
    the border + ARROW_GAP. Keeps the arrow's direction intact."""
    ops = plan.get("ops") or []

    def _as_container(sh: dict) -> dict:
        # Icons occupy a size×size box centered at (x, y).
        if sh["type"] == "icon":
            s = sh.get("size") or 220
            return {"type": "rectangle", "x": sh["x"] - s / 2, "y": sh["y"] - s / 2, "w": s, "h": s}
        return sh

    shapes = [_as_container(op) for op in ops
              if op.get("type") in ("rectangle", "circle", "icon")]
    if not shapes:
        return plan
    for op in ops:
        if op.get("type") != "arrow":
            continue
        p1 = (float(op["x1"]), float(op["y1"]))
        p2 = (float(op["x2"]), float(op["y2"]))
        for sh in shapes:
            if _point_in_shape(p2, sh, ARROW_GAP) and not _point_in_shape(p1, sh, ARROW_GAP):
                t = _entry_t(p1, p2, sh, ARROW_GAP)
                if t is not None:
                    p2 = (p1[0] + (p2[0] - p1[0]) * t, p1[1] + (p2[1] - p1[1]) * t)
            if _point_in_shape(p1, sh, ARROW_GAP) and not _point_in_shape(p2, sh, ARROW_GAP):
                t = _entry_t(p2, p1, sh, ARROW_GAP)
                if t is not None:
                    p1 = (p2[0] + (p1[0] - p2[0]) * t, p2[1] + (p1[1] - p2[1]) * t)
        if math.hypot(p2[0] - p1[0], p2[1] - p1[1]) >= MIN_ARROW_LEN:
            if (int(round(p1[0])), int(round(p1[1])), int(round(p2[0])), int(round(p2[1]))) != (op["x1"], op["y1"], op["x2"], op["y2"]):
                logger.info("whiteboard-plan: retracted arrow to shape borders")
            op["x1"], op["y1"] = int(round(p1[0])), int(round(p1[1]))
            op["x2"], op["y2"] = int(round(p2[0])), int(round(p2[1]))
    return plan
