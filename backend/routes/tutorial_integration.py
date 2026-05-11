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


def _step_to_slide(step: dict, screenshot_url: Optional[str], slide_idx: int, zoom_level: float = 2.5) -> dict:
    """Convert one tutorial step into a Scormify slide dict."""
    title = step.get("title") or f"Passo {slide_idx + 1}"
    body_text = _generate_step_description(step, slide_idx)
    narration_for_tts = (step.get("narration") or body_text)[:2000]

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

    return slide


async def _convert_tutorial_to_slides(tutorial: dict, project_id: str) -> list:
    """Walk all steps, download each screenshot, build slide list."""
    steps = tutorial.get("steps") or []
    zoom_level = tutorial.get("zoom_level") or 1.0
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
                tutorial.get("id") or "", step_id, project_id,
            )
        slides.append(_step_to_slide(step, screenshot_url, idx, zoom_level=zoom_level))
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
