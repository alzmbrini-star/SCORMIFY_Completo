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
- `edit_element_style`: {slideIndex: int, elementIndex: int, style: {fontColor?, fontSize?, fontWeight?, backgroundColor?, textAlign?}}
- `add_text_element`: {slideIndex: int, content: str, x?: number, y?: number, width?: number, height?: number, fontSize?: int, fontColor?: str}
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


def _apply_ops(slides: list, ops: list) -> list:
    """Mutate slides in-place applying a list of editor ops. Returns the
    list of ops that were actually applied (skips malformed ones)."""
    applied = []
    for op in ops:
        try:
            t = op.get("type")
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
                        for k in ("fontColor", "fontSize", "fontWeight", "backgroundColor", "textAlign", "borderRadius", "padding"):
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

    summary = _build_course_summary(slides)
    history = (data.get("history") or [])[-6:]

    user_prompt = (
        f"CURSO ATUAL (resumo):\n{json.dumps(summary, ensure_ascii=False)[:8000]}\n\n"
        f"CONVERSA:\n{json.dumps(history, ensure_ascii=False) if history else '(primeira mensagem)'}\n\n"
        f"AUTOR: {message}"
    )
    raw = await _call_llm(SYSTEM_PROMPT, user_prompt, f"editor_chat_{project_id}")
    parsed = _extract_json(raw)
    reply = parsed.get("reply") or "Entendi."
    ops = parsed.get("ops") or []

    # Snapshot BEFORE mutating so the user can revert (shares the same
    # `aesthetic_snapshots` collection so existing Revert button works).
    snapshot_slides = _copy.deepcopy(slides) if ops else None

    applied = _apply_ops(slides, ops)

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
