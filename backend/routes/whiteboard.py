"""HTTP routes for the self-hosted Whiteboard / Hand-writer video
generator. Endpoints:

  POST /api/whiteboard/generate   — kicks off an async render job. Returns
                                    `{jobId, statusUrl}` so the frontend
                                    can poll for completion (renders can
                                    easily exceed 100s for long APNGs,
                                    causing Cloudflare 520s on a sync
                                    request — async pattern bypasses
                                    that).
  GET  /api/job/{job_id}          — generic job status polling (already
                                    exists in projects_crud).
  GET  /api/whiteboard/file/{name} — serve the generated MP4 / APNG.

The job result payload mirrors what the old sync endpoint returned, so
the frontend only needs to wait for `result` to be populated."""
from __future__ import annotations

import asyncio
import logging
import uuid as _uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from routes.deps import db, now_utc, create_job, update_job, jobs
from routes.auth import require_auth
from services.whiteboard_renderer import (
    OUTPUT_DIR, render_whiteboard_video, list_available_fonts,
)

logger = logging.getLogger("server")
router = APIRouter(prefix="/whiteboard", tags=["Whiteboard"])


class WhiteboardGenerateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)
    title: Optional[str] = Field(default=None, max_length=200)
    fontSize: Optional[int] = Field(default=84, ge=40, le=240)
    charsPerSecond: Optional[float] = Field(default=6.0, ge=2.0, le=40.0)
    fontFamily: Optional[str] = Field(default=None, max_length=64)
    transparent: Optional[bool] = Field(default=False)
    # RTF / color extensions:
    # - `inkColor` is a default hex like "#1a1a1a" applied to plain text.
    # - `textHtml` lets the frontend send rich HTML where inline color
    #   spans (and <font color=...>) override the default per segment.
    inkColor: Optional[str] = Field(default=None, max_length=20)
    textHtml: Optional[str] = Field(default=None, max_length=8000)
    # When true, the generated video appends an eraser sweep after the
    # writing finishes — simulating a felt eraser wiping the board. Useful
    # for chaining multiple Whiteboard clips on the Timeline so the prior
    # text disappears before the next one starts writing.
    eraseAtEnd: Optional[bool] = Field(default=False)
    # Eraser motion pattern. "horizontal" sweeps each stripe left→right.
    # "zigzag" alternates direction per stripe so the eraser follows a
    # continuous serpentine path — feels more human.
    eraseStyle: Optional[str] = Field(default="horizontal", pattern="^(horizontal|zigzag)$")
    # Optional binding — when both are provided, the generated videoUrl
    # is written to the matching slide element so the author doesn't have
    # to manually paste it. When omitted, the URL is just returned.
    projectId: Optional[str] = None
    slideId: Optional[str] = None


@router.post("/generate")
async def generate_whiteboard_video(
    payload: WhiteboardGenerateRequest,
    user: dict = Depends(require_auth),
):
    """Kick off an async whiteboard render job and return its id.

    Returns 202-ish payload `{jobId, statusUrl}`. The frontend polls
    `/api/job/{jobId}` until `status == 'completed'` and reads the same
    fields the old sync endpoint returned from `result`.
    """
    # Pre-parse the ink color so an invalid value fails fast (400) before
    # we spin up a background task.
    ink_rgb = None
    if payload.inkColor:
        from services.whiteboard_renderer import _parse_color
        ink_rgb = _parse_color(payload.inkColor)

    job_id = str(_uuid.uuid4())
    job_data = {
        "id": job_id,
        "type": "whiteboard_generate",
        "status": "processing",
        "progress": 0,
        "message": "Renderizando whiteboard...",
        "result": None,
    }
    jobs[job_id] = job_data
    await create_job(job_id, job_data)

    asyncio.create_task(
        _run_whiteboard_job(
            job_id=job_id,
            payload=payload,
            ink_rgb=ink_rgb,
        )
    )

    return {
        "jobId": job_id,
        "statusUrl": f"/api/job/{job_id}",
    }


async def _run_whiteboard_job(
    job_id: str,
    payload: "WhiteboardGenerateRequest",
    ink_rgb,
):
    """Background worker that performs the actual render + slide bind.

    Pushes the final `videoUrl` + meta into the job `result` so the
    polling frontend can finish the flow."""
    try:
        rel_url, info = await render_whiteboard_video(
            text=payload.text,
            title=payload.title or None,
            font_size=payload.fontSize or 84,
            chars_per_second=payload.charsPerSecond or 6.0,
            font_family=payload.fontFamily or None,
            transparent=bool(payload.transparent),
            ink_color=ink_rgb,
            text_html=payload.textHtml or None,
            erase_at_end=bool(payload.eraseAtEnd),
            erase_style=payload.eraseStyle or "horizontal",
        )
    except ValueError as e:
        await update_job(job_id, {
            "status": "failed",
            "message": str(e)[:500],
        })
        return
    except Exception as e:  # noqa: BLE001
        logger.exception("whiteboard generate failed: %s", e)
        await update_job(job_id, {
            "status": "failed",
            "message": f"render failed: {e}"[:500],
        })
        return

    # Bind to slide if requested (same logic as the previous sync flow).
    if payload.projectId and payload.slideId:
        project = await db.projects.find_one(
            {"id": payload.projectId}, {"_id": 0}
        )
        if project:
            slides = (project.get("course") or {}).get("slides") or []
            slide_idx = next(
                (i for i, s in enumerate(slides) if s.get("id") == payload.slideId),
                None,
            )
            if slide_idx is not None:
                slide = slides[slide_idx]
                elements = slide.get("elements") or []
                # Note: we intentionally APPEND the new whiteboard instead
                # of replacing existing ones. The author can have multiple
                # whiteboards on the same slide to chain them via Timeline
                # (e.g. "write text 1 → erase → write text 2 → erase").
                # If the user wants to replace, they can delete the old
                # element from the Editor manually.
                is_apng = info.get("format") == "apng"
                # Stagger position slightly when there are pre-existing
                # whiteboards so they don't visually stack identically in
                # the Editor canvas. The Timeline still controls playback
                # order independently of position.
                existing_wb = sum(
                    1 for e in elements
                    if isinstance(e, dict) and e.get("isWhiteboard")
                )
                # Make the stagger meaningfully visible. Previously 24px
                # offset with 1280×720 elements meant the new whiteboard
                # essentially covered the previous one — authors thought
                # the older clip was "deleted" when in fact it was just
                # hidden behind. 80px diagonal stagger keeps the corner
                # of every prior whiteboard visible so the author can
                # click through to it in the Layers panel.
                offset = min(existing_wb * 80, 400)
                base_x = 320 + offset
                base_y = 50 + offset
                # Friendly element label shown in the Layers panel. Uses
                # the dialog Título if provided, otherwise falls back to
                # a sequence number so multiple whiteboards stay visually
                # distinguishable ("Whiteboard 1", "Whiteboard 2", …).
                wb_name = (payload.title or "").strip() or f"Whiteboard {existing_wb + 1}"
                if is_apng:
                    new_el = {
                        "id": str(_uuid.uuid4()),
                        "type": "image",
                        "src": rel_url,
                        "name": wb_name,
                        "x": base_x,
                        "y": base_y,
                        "width": 1280,
                        "height": 720,
                        "zIndex": len(elements),
                        "isWhiteboard": True,
                        "isAnimatedPng": True,
                        "style": {"backgroundColor": "transparent"},
                    }
                else:
                    new_el = {
                        "id": str(_uuid.uuid4()),
                        "type": "video",
                        "src": rel_url,
                        "name": wb_name,
                        "x": base_x,
                        "y": base_y,
                        "width": 1280,
                        "height": 720,
                        "zIndex": len(elements),
                        "isWhiteboard": True,
                        "autoplay": True,
                        "loop": False,
                        "controls": True,
                        "style": {},
                    }
                elements.append(new_el)
                set_fields = {
                    f"course.slides.{slide_idx}.whiteboardMeta": info,
                    f"course.slides.{slide_idx}.elements": elements,
                    "updatedAt": now_utc().isoformat(),
                }
                if not is_apng:
                    set_fields[f"course.slides.{slide_idx}.videoUrl"] = rel_url
                await db.projects.update_one(
                    {"id": payload.projectId},
                    {"$set": set_fields},
                )

    result = {"videoUrl": rel_url, **info}
    await update_job(job_id, {
        "status": "completed",
        "progress": 100,
        "message": "Whiteboard pronto",
        "result": result,
    })


@router.get("/file/{name}")
async def serve_whiteboard_file(name: str):
    """Stream the generated video (MP4 or WebM with alpha) with a long
    cache TTL — same script means CDN-friendly idempotent caching."""
    # Sanitize: name must be wb_<hex>.{mp4|webm|png} to prevent path
    # traversal. .png is used for animated APNG outputs (transparent).
    valid_ext = name.endswith(".mp4") or name.endswith(".webm") or name.endswith(".png")
    ok_name = (
        name.startswith("wb_")
        and valid_ext
        and "/" not in name
        and ".." not in name
    )
    if not ok_name:
        raise HTTPException(404, "invalid name")
    path = OUTPUT_DIR / name
    if not path.exists():
        raise HTTPException(404, "video not found")
    if name.endswith(".webm"):
        media_type = "video/webm"
    elif name.endswith(".png"):
        media_type = "image/apng"
    else:
        media_type = "video/mp4"
    return FileResponse(
        str(path), media_type=media_type,
        headers={"Cache-Control": "public, max-age=2592000, immutable"},
    )


@router.get("/fonts")
async def whiteboard_fonts():
    """Return the catalog of bundled handwriting/marker fonts available
    for the whiteboard renderer."""
    return {"fonts": list_available_fonts()}


@router.get("/health")
async def whiteboard_health():
    """Diagnostic: verifies font + hand asset + ffmpeg binary are ready.

    Crucial for production debugging: hitting this from the browser /
    admin panel tells you instantly whether the K8s pod has the binary
    AND can encode (or whether we'd hit a 500 on first generate)."""
    from services.whiteboard_renderer import (
        HAND_PATH, _resolve_ffmpeg_binary, _resolve_font_path,
    )
    default_font = _resolve_font_path(None)
    info = {
        "fontOk": Path(default_font).exists(),
        "fontPath": str(default_font),
        "availableFonts": [f["id"] for f in list_available_fonts()],
        "handOk": Path(HAND_PATH).exists(),
        "outputDir": str(OUTPUT_DIR),
        "outputDirOk": OUTPUT_DIR.exists(),
    }
    try:
        info["ffmpegPath"] = _resolve_ffmpeg_binary()
        info["ffmpegOk"] = True
    except Exception as e:
        info["ffmpegPath"] = None
        info["ffmpegOk"] = False
        info["ffmpegError"] = str(e)
    return info



# =====================================================================
# AI-assisted text generation
# =====================================================================

class WhiteboardAITextRequest(BaseModel):
    # Optional free-form instruction from the author (tone, focus, etc.)
    userPrompt: Optional[str] = Field(default=None, max_length=500)
    # Slide binding — when present we build a rich context from the slide.
    projectId: Optional[str] = None
    slideId: Optional[str] = None
    # Hard cap on the generated text length (suits the whiteboard's
    # ~300-char recommendation).
    maxChars: int = Field(default=280, ge=80, le=600)


def _extract_slide_context(slide: dict) -> str:
    """Build a compact text context from a slide for the AI prompt.

    Includes the slide title, any text/HTML element content, narration
    script (if present), and notes. Strips HTML tags for clarity."""
    import re
    parts: list[str] = []
    title = (slide.get("title") or "").strip()
    if title:
        parts.append(f"Título do slide: {title}")
    elements = slide.get("elements") or []
    body_chunks: list[str] = []
    for el in elements:
        if not isinstance(el, dict):
            continue
        if el.get("type") in ("text", "html"):
            raw = el.get("content") or el.get("htmlContent") or ""
            if not raw:
                continue
            clean = re.sub(r"<[^>]+>", " ", raw)
            clean = re.sub(r"\s+", " ", clean).strip()
            if clean:
                body_chunks.append(clean)
    if body_chunks:
        parts.append("Conteúdo atual do slide:\n" + "\n".join(body_chunks)[:1500])
    narration = (slide.get("narration") or "").strip()
    if narration:
        parts.append(f"Roteiro de narração: {narration[:600]}")
    notes = (slide.get("notes") or "").strip()
    if notes:
        parts.append(f"Notas do apresentador: {notes[:600]}")
    extracted = (slide.get("extractedText") or "").strip()
    if extracted and extracted not in (narration + " " + " ".join(body_chunks)):
        parts.append(f"Texto extraído (PPT): {extracted[:600]}")
    return "\n\n".join(parts).strip()


@router.post("/generate-text")
async def generate_whiteboard_text(
    payload: WhiteboardAITextRequest,
    user: dict = Depends(require_auth),
):
    """Generate a short, didactic text suitable for the whiteboard
    animation. Uses the slide's title/content/narration as automatic
    context, plus an optional free-form instruction from the author.

    Output is plain text (no markdown, no quotes), ≤ maxChars, in the
    same language as the slide. Returns: { text: str, charsUsed: int }.
    """
    import os
    from emergentintegrations.llm.chat import LlmChat, UserMessage  # type: ignore

    key = os.environ.get("EMERGENT_LLM_KEY")
    if not key:
        raise HTTPException(500, "EMERGENT_LLM_KEY not configured")

    # Build context from the slide (if provided).
    slide_context = ""
    if payload.projectId and payload.slideId:
        project = await db.projects.find_one({"id": payload.projectId}, {"_id": 0})
        if project:
            slides = (project.get("course") or {}).get("slides") or []
            slide = next((s for s in slides if s.get("id") == payload.slideId), None)
            if slide:
                slide_context = _extract_slide_context(slide)

    user_prompt = (payload.userPrompt or "").strip()
    max_chars = payload.maxChars

    # If we have neither slide context nor a user prompt, there's
    # nothing to ground the generation on — surface the problem early.
    if not slide_context and not user_prompt:
        raise HTTPException(
            400,
            "Forneça uma instrução (userPrompt) ou um slide com conteúdo.",
        )

    sys_msg = (
        "Você é um redator pedagógico. Sua tarefa é criar um texto CURTO "
        "e didático para ser escrito à mão em uma animação de quadro branco. "
        "REGRAS OBRIGATÓRIAS:\n"
        f"- Máximo {max_chars} caracteres (conte inclusive espaços).\n"
        "- Texto direto, claro e impactante. Sem markdown, sem aspas, sem "
        "listas com bullets — apenas texto puro, no idioma do contexto.\n"
        "- Pode usar quebras de linha (\\n) para destacar frases-chave.\n"
        "- Não inclua o título do slide repetido; o título já será "
        "renderizado separadamente.\n"
        "- Responda APENAS com o texto final, sem preâmbulo nem explicação."
    )

    prompt_parts: list[str] = []
    if slide_context:
        prompt_parts.append("CONTEXTO DO SLIDE:\n" + slide_context)
    if user_prompt:
        prompt_parts.append(
            "INSTRUÇÃO ADICIONAL DO AUTOR:\n" + user_prompt
        )
    prompt_parts.append(
        f"Gere agora o texto para o whiteboard (≤ {max_chars} caracteres):"
    )
    prompt = "\n\n".join(prompt_parts)

    try:
        chat = LlmChat(
            api_key=key,
            session_id=f"wb-text-{payload.slideId or 'free'}",
            system_message=sys_msg,
        ).with_model("openai", "gpt-4o")
        resp = await chat.send_message(UserMessage(text=prompt))
    except Exception as e:  # noqa: BLE001
        logger.exception("whiteboard ai text gen failed: %s", e)
        raise HTTPException(502, f"falha ao gerar texto: {e}")

    text = str(resp or "").strip()
    # Strip wrapping quotes/backticks if the model added them.
    for wrapper in ('"', "'", "`"):
        if text.startswith(wrapper) and text.endswith(wrapper):
            text = text[1:-1].strip()
    # Convert any literal "\n" the model emitted into real newlines —
    # the renderer respects \n as line breaks but ignores the literal
    # 2-char sequence.
    text = text.replace("\\n", "\n").replace("\\r", "")
    # Collapse runs of blank lines and strip per-line whitespace.
    text = "\n".join(line.strip() for line in text.split("\n") if line.strip())
    # Hard cap as safety net.
    if len(text) > max_chars:
        text = text[: max_chars - 1].rstrip() + "…"

    return {"text": text, "charsUsed": len(text)}
