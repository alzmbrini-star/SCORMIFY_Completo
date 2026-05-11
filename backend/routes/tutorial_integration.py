"""Tutorial Agent integration — import step-by-step tutorials produced by
the external Auto-Instructor agent into Scormify projects.

The external service hosts ready tutorials with embedded screenshots and
narration text. Scormify pulls a tutorial, downloads each screenshot as
an asset, and turns each step into a slide ready for the editor.
"""
import os
import uuid
import logging
import httpx
from typing import Optional
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from routes.deps import db, PROJECTS_DIR
from routes.auth import require_auth
from services.asset_store import store_asset_async

logger = logging.getLogger("server")
router = APIRouter(tags=["Tutorial Integration"])


def _agent_base() -> str:
    return (os.environ.get("TUTORIAL_AGENT_URL") or "").rstrip("/")


def _agent_headers() -> dict:
    key = os.environ.get("TUTORIAL_AGENT_API_KEY", "")
    if not key:
        raise HTTPException(503, "TUTORIAL_AGENT_API_KEY nao configurada")
    return {"X-API-Key": key}


# ---------------------------------------------------------------------------
# Proxy: list / get / start / status — keeps the API key inside the backend
# so the frontend never touches it.
# ---------------------------------------------------------------------------

@router.get("/tutorial-integration/list")
async def list_tutorials(user: dict = Depends(require_auth)):
    """Proxy: list all tutorials available on the external Agent."""
    url = f"{_agent_base()}/api/v1/tutorials"
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(url, headers=_agent_headers())
            r.raise_for_status()
            return r.json()
    except httpx.HTTPError as e:
        logger.warning(f"tutorial list error: {e}")
        raise HTTPException(502, f"Falha ao listar tutoriais: {str(e)[:120]}")


@router.get("/tutorial-integration/tutorials/{tutorial_id}")
async def get_tutorial(tutorial_id: str, embed: bool = False, user: dict = Depends(require_auth)):
    """Proxy: get one tutorial's full data. When embed=True, screenshots
    come as base64 (heavier but no second request needed)."""
    suffix = "?embed_data=true" if embed else ""
    url = f"{_agent_base()}/api/v1/tutorials/{tutorial_id}{suffix}"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(url, headers=_agent_headers())
            r.raise_for_status()
            return r.json()
    except httpx.HTTPError as e:
        raise HTTPException(502, f"Falha ao obter tutorial: {str(e)[:120]}")


@router.post("/tutorial-integration/tutorials/{tutorial_id}/generate")
async def start_generation(tutorial_id: str, user: dict = Depends(require_auth)):
    """Proxy: trigger the external Agent to generate the tutorial assets."""
    url = f"{_agent_base()}/api/v1/tutorials/{tutorial_id}/generate"
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(url, headers=_agent_headers())
            r.raise_for_status()
            return r.json()
    except httpx.HTTPError as e:
        raise HTTPException(502, f"Falha ao gerar: {str(e)[:120]}")


@router.get("/tutorial-integration/tutorials/{tutorial_id}/status")
async def get_status(tutorial_id: str, user: dict = Depends(require_auth)):
    """Proxy: poll tutorial generation status."""
    url = f"{_agent_base()}/api/v1/tutorials/{tutorial_id}/status"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url, headers=_agent_headers())
            r.raise_for_status()
            return r.json()
    except httpx.HTTPError as e:
        raise HTTPException(502, f"Falha no status: {str(e)[:120]}")


# ---------------------------------------------------------------------------
# Convert a Tutorial Agent step -> Scormify slide
# ---------------------------------------------------------------------------

async def _download_screenshot_to_assets(
    tutorial_id: str,
    step_id: str,
    project_id: str,
) -> Optional[str]:
    """Download a step screenshot from the Agent and persist it as a
    Scormify asset. Returns the asset URL or None on failure."""
    url = f"{_agent_base()}/api/v1/tutorials/{tutorial_id}/steps/{step_id}/screenshot"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(url, headers=_agent_headers())
            r.raise_for_status()
            content = r.content
    except httpx.HTTPError as e:
        logger.warning(f"screenshot download failed for step {step_id}: {e}")
        return None

    # Save to disk and persist in MongoDB (so it survives K8s restarts)
    fname = f"tutorial_{step_id[:10]}.png"
    assets_dir = Path(PROJECTS_DIR) / project_id / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    dest = assets_dir / fname
    try:
        dest.write_bytes(content)
        await store_asset_async(db, project_id, fname, str(dest))
    except Exception as e:
        logger.error(f"failed to persist screenshot {fname}: {e}")
        return None
    return f"/api/projects/{project_id}/assets/{fname}"


def _audio_ext_from_content_type(ct: str) -> str:
    """Pick a sensible file extension based on the audio MIME type."""
    ct = (ct or "").lower()
    if "wav" in ct:
        return ".wav"
    if "ogg" in ct:
        return ".ogg"
    if "webm" in ct:
        return ".webm"
    return ".mp3"


def _resolve_audio_url(audio_url: str) -> str:
    """Turn whatever the Agent gives us into a full URL we can fetch.

    The Agent may return:
      - `https://host/...mp3`     → use as-is
      - `/api/v1/.../audio`       → prefix with agent base
      - `bucket/path/file.mp3`    → s3-like path → prefix with `_agent_base()/files/`
    """
    if not audio_url:
        return ""
    s = audio_url.strip()
    if s.startswith("http://") or s.startswith("https://"):
        return s
    base = _agent_base()
    if s.startswith("/"):
        return f"{base}{s}"
    # Looks like a storage path; route through the Agent's static file proxy
    return f"{base}/api/files/{s.lstrip('/')}"


async def _download_step_audio_to_assets(
    tutorial_id: str,
    step_id: str,
    project_id: str,
    audio_url_hint: Optional[str],
    audio_base64: Optional[str] = None,
) -> Optional[dict]:
    """Download a step's narration audio and persist it as an asset.

    Returns the `slide.audio[]` entry shape:
        {id, type, src, filename, duration, volume}
    or None when no audio could be obtained.
    """
    content: Optional[bytes] = None
    content_type = "audio/mpeg"

    # 1) Try embedded base64 first (cheapest — no extra request)
    if audio_base64:
        import base64 as _b64
        try:
            content = _b64.b64decode(audio_base64)
        except Exception as e:
            logger.warning(f"step {step_id}: audio_base64 decode failed: {e}")
            content = None

    # 2) Try the hint URL provided in the step payload
    if content is None and audio_url_hint:
        target = _resolve_audio_url(audio_url_hint)
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                r = await client.get(target, headers=_agent_headers())
                if r.status_code == 200:
                    content = r.content
                    content_type = r.headers.get("content-type") or content_type
        except httpx.HTTPError as e:
            logger.warning(f"step {step_id}: audio_url fetch failed ({target}): {e}")

    # 3) Fall back to the dedicated step audio endpoint
    if content is None:
        fallback = f"{_agent_base()}/api/v1/tutorials/{tutorial_id}/steps/{step_id}/audio"
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                r = await client.get(fallback, headers=_agent_headers())
                if r.status_code == 200:
                    content = r.content
                    content_type = r.headers.get("content-type") or content_type
        except httpx.HTTPError as e:
            logger.warning(f"step {step_id}: audio endpoint failed: {e}")

    if not content:
        return None

    # Sanity: very small responses are probably error JSON in disguise
    if len(content) < 200:
        return None

    ext = _audio_ext_from_content_type(content_type)
    audio_id = str(uuid.uuid4())
    fname = f"tutorial_audio_{step_id[:10]}_{audio_id[:8]}{ext}"
    assets_dir = Path(PROJECTS_DIR) / project_id / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    dest = assets_dir / fname
    try:
        dest.write_bytes(content)
        await store_asset_async(db, project_id, fname, str(dest))
    except Exception as e:
        logger.error(f"failed to persist tutorial audio {fname}: {e}")
        return None

    return {
        "id": audio_id,
        "type": "narration",
        "src": f"/api/projects/{project_id}/assets/{fname}",
        "filename": fname,
        "duration": 0,
        "volume": 1.0,
        "source": "tutorial_agent",  # provenance tag for debugging
    }


def _generate_step_description(step: dict, idx: int) -> str:
    """Build a human-readable description when the Agent's narration is empty.
    Uses action_type + selector to synthesize a clear instruction."""
    explicit = (step.get("narration") or step.get("description") or step.get("instruction") or "").strip()
    if explicit:
        return explicit

    action = (step.get("action_type") or "").lower()
    selector = step.get("selector") or step.get("element_text") or ""
    # selector format may be "a:text:Relatórios" or just plain text
    label = selector
    if ":" in label:
        parts = label.split(":")
        # Prefer the last meaningful part (the user-visible text)
        label = parts[-1].strip() or parts[-2].strip() if len(parts) >= 2 else parts[0]

    if action == "click":
        return f"Clique em \"{label}\"." if label else "Clique no elemento destacado."
    if action == "type":
        text_val = step.get("typed_text") or step.get("input") or ""
        return f"Digite \"{text_val}\" no campo destacado." if text_val else "Preencha o campo destacado."
    if action == "scroll":
        return "Role a tela ate visualizar o conteudo a seguir."
    if action == "wait":
        return "Aguarde o carregamento da pagina."
    if action == "navigate":
        url = step.get("url") or ""
        return f"Acesse {url}." if url else "Acesse o endereco indicado."
    # Default fallback
    return f"Passo {idx + 1}: siga a indicacao destacada na tela."


def _step_to_slide(
    step: dict,
    screenshot_url: Optional[str],
    slide_idx: int,
    zoom_level: float = 2.5,
    audio_data: Optional[dict] = None,
) -> dict:
    """Convert one tutorial step into a Scormify slide dict."""
    title = step.get("title") or f"Passo {slide_idx + 1}"
    body_text = _generate_step_description(step, slide_idx)
    # Prefer the explicit narration field when provided so the slide's
    # narrationScript matches whatever generated the audio file.
    explicit_narration = (step.get("narration") or "").strip()
    narration_for_tts = (explicit_narration or body_text)[:2000]

    elements = []
    # Add the instruction text overlay
    if body_text:
        elements.append({
            "id": str(uuid.uuid4()),
            "type": "text",
            "content": body_text[:500],
            "x": 60,
            "y": 620,
            "width": 1160,
            "height": 80,
            "style": {
                "fontSize": 22,
                "fontColor": "#f8fafc",
                "textBackgroundColor": "rgba(15,23,42,0.85)",
                "padding": "12px 20px",
                "borderRadius": "10px",
                "textAlign": "center",
            },
        })

    # Hotspot/click marker — visual circle at the clicked coordinates so
    # the learner knows exactly where the action happens.
    cx = step.get("click_x")
    cy = step.get("click_y")
    has_focus = False
    focus_x = focus_y = None
    if cx is not None and cy is not None:
        try:
            cx_int = int(cx)
            cy_int = int(cy)
            focus_x, focus_y = cx_int, cy_int
            has_focus = True
            elements.append({
                "id": str(uuid.uuid4()),
                "type": "shape",
                "shape": "circle",
                "x": float(cx_int - 28),
                "y": float(cy_int - 28),
                "width": 56,
                "height": 56,
                "style": {
                    "fill": "rgba(244,114,182,0.0)",
                    "borderColor": "#f472b6",
                    "borderWidth": 4,
                    "borderRadius": "50%",
                    "boxShadow": "0 0 0 4px rgba(244,114,182,0.35), 0 0 20px rgba(244,114,182,0.5)",
                },
            })
        except (TypeError, ValueError):
            pass

    slide = {
        "id": str(uuid.uuid4()),
        "title": title,
        "background": "#0f172a",
        "width": 1280,
        "height": 720,
        "elements": elements,
        "narrationScript": narration_for_tts,
        "notes": "",
    }
    if screenshot_url:
        slide["backgroundImage"] = screenshot_url
        slide["backgroundImageOpacity"] = 1.0

    # Zoom effect: when the step has a click point AND the tutorial declares a
    # zoom_level, mark the slide so the player can animate a "magnify on the
    # hotspot" effect. The renderer transforms `scale(zoom) translate(-fx, -fy)`
    # on the bg image during the hold window.
    try:
        zoom = float(zoom_level or 1.0)
    except (TypeError, ValueError):
        zoom = 1.0
    if has_focus and zoom and zoom > 1.0:
        # Express focus point as PERCENTAGE of the screenshot dimensions so
        # the player can compute the transform without knowing pixel sizes
        # (screenshots may not be exactly 1280x720 — many are 1366x768 etc).
        # We fall back to the slide canvas if the source dimensions are unknown.
        src_w = step.get("screenshot_width") or 1280
        src_h = step.get("screenshot_height") or 720
        try:
            fx_pct = (focus_x / float(src_w)) * 100
            fy_pct = (focus_y / float(src_h)) * 100
            # Clamp to a safe window so the zoomed-in region stays fully
            # within the visible card. transform-origin at 0% or 100% pushes
            # half the magnified image off-screen.
            fx_pct = max(15.0, min(85.0, fx_pct))
            fy_pct = max(15.0, min(85.0, fy_pct))
        except (TypeError, ValueError, ZeroDivisionError):
            fx_pct, fy_pct = 50.0, 50.0
        slide["zoomEffect"] = {
            "scale": round(zoom, 2),
            "focusX": round(fx_pct, 2),  # percent (0-100)
            "focusY": round(fy_pct, 2),
            "intro": 800,                # ms — fade-in zoom
            "hold": 2400,                # ms — stay zoomed while learner reads
            "outro": 600,                # ms — zoom out at end
        }

    # Audio: when the Tutorial Agent already produced a narration audio file
    # we attach it to slide.audio[] so the Single Page / SCORM exporters auto-
    # play it just like ElevenLabs-generated narration.
    if audio_data:
        slide["audio"] = [audio_data]

    return slide


async def _convert_tutorial_to_slides(tutorial: dict, project_id: str) -> list:
    """Walk all steps, download each screenshot + narration audio, build slide list."""
    steps = tutorial.get("steps") or []
    zoom_level = tutorial.get("zoom_level") or 1.0
    tutorial_id = tutorial.get("id") or ""
    slides = []
    for idx, step in enumerate(steps):
        step_id = step.get("id") or str(uuid.uuid4())
        # Prefer embedded base64 if the Agent already gave it
        screenshot_url = None
        b64 = step.get("screenshot_base64")
        if b64:
            # Persist base64 to assets
            import base64
            try:
                content = base64.b64decode(b64)
                fname = f"tutorial_{step_id[:10]}.png"
                assets_dir = Path(PROJECTS_DIR) / project_id / "assets"
                assets_dir.mkdir(parents=True, exist_ok=True)
                dest = assets_dir / fname
                dest.write_bytes(content)
                await store_asset_async(db, project_id, fname, str(dest))
                screenshot_url = f"/api/projects/{project_id}/assets/{fname}"
            except Exception as e:
                logger.warning(f"base64 screenshot decode failed: {e}")
                screenshot_url = None
        if not screenshot_url:
            screenshot_url = await _download_screenshot_to_assets(
                tutorial_id, step_id, project_id,
            )

        # Fetch narration audio if the Agent produced one. The download helper
        # is resilient: it tries the explicit audio_url first, then falls back
        # to the dedicated /audio endpoint. Returns None silently when no
        # audio exists for this step (older tutorials, generation not done).
        audio_data = await _download_step_audio_to_assets(
            tutorial_id=tutorial_id,
            step_id=step_id,
            project_id=project_id,
            audio_url_hint=step.get("audio_url"),
            audio_base64=step.get("audio_base64"),
        )

        slides.append(_step_to_slide(
            step, screenshot_url, idx,
            zoom_level=zoom_level,
            audio_data=audio_data,
        ))
    return slides


# ---------------------------------------------------------------------------
# Public endpoint — import tutorial into project
# ---------------------------------------------------------------------------

@router.post("/tutorial-integration/import/{tutorial_id}")
async def import_tutorial(
    tutorial_id: str,
    data: dict,
    user: dict = Depends(require_auth),
):
    """Import a completed tutorial as Scormify slides.

    Body:
      {
        "mode": "new" | "append",          # default "new"
        "projectId": "uuid"                 # required when mode=append
                                            # ignored when mode=new
        "name": "string",                   # optional, overrides tutorial title
        "companyId": "uuid"                 # optional, attribution
      }

    Returns: { projectId, addedSlides, mode }
    """
    mode = (data.get("mode") or "new").lower()
    if mode not in ("new", "append"):
        raise HTTPException(400, "mode deve ser 'new' ou 'append'")

    # Fetch the full tutorial with embedded screenshots
    base = _agent_base()
    headers = _agent_headers()
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.get(
                f"{base}/api/v1/tutorials/{tutorial_id}?embed_data=true",
                headers=headers,
            )
            r.raise_for_status()
            tutorial = r.json()
    except httpx.HTTPError as e:
        raise HTTPException(502, f"Falha ao buscar tutorial: {str(e)[:120]}")

    # Mode: append to existing project
    if mode == "append":
        pid = data.get("projectId")
        if not pid:
            raise HTTPException(400, "projectId e obrigatorio em mode=append")
        project = await db.projects.find_one({"id": pid}, {"_id": 0})
        if not project:
            raise HTTPException(404, "Projeto nao encontrado")
        new_slides = await _convert_tutorial_to_slides(tutorial, pid)
        if not new_slides:
            raise HTTPException(400, "Tutorial nao tem passos com screenshot")
        slides = (project.get("course") or {}).get("slides") or []
        slides.extend(new_slides)
        await db.projects.update_one(
            {"id": pid},
            {"$set": {
                "course.slides": slides,
                "updatedAt": datetime.now(timezone.utc).isoformat(),
            }}
        )
        return {
            "projectId": pid,
            "addedSlides": len(new_slides),
            "mode": "append",
        }

    # Mode: new project
    pid = str(uuid.uuid4())
    new_slides = await _convert_tutorial_to_slides(tutorial, pid)
    if not new_slides:
        raise HTTPException(400, "Tutorial nao tem passos com screenshot")

    project_name = (data.get("name") or tutorial.get("title") or "Tutorial Importado").strip()
    company_id = data.get("companyId")

    doc = {
        "id": pid,
        "name": project_name,
        "userId": user.get("user_id"),
        "companyId": company_id,
        "source": "tutorial_agent",
        "tutorialAgentId": tutorial_id,
        "course": {
            "metadata": {
                "title": project_name,
                "description": tutorial.get("description") or "",
                "language": "pt-BR",
            },
            "slides": new_slides,
        },
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }
    await db.projects.insert_one(doc.copy())  # copy so insertion doesn't add _id back

    return {
        "projectId": pid,
        "addedSlides": len(new_slides),
        "mode": "new",
        "name": project_name,
    }
