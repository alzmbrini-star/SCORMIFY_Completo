"""Email notification routes - manage and trigger notifications."""
import logging
from fastapi import APIRouter, HTTPException, Request, Depends
from routes.deps import db
from routes.auth import require_auth, get_current_user
from services.email_service import (
    send_email, notify_approval_submitted, notify_approval_approved,
    notify_approval_rejected, notify_course_generated, notify_tutor_summary,
)

logger = logging.getLogger("server")
router = APIRouter(tags=["Notifications"])


@router.post("/notifications/test-email")
async def test_email(request: Request, user: dict = Depends(require_auth)):
    """Send a test email to the current user or a specific email."""
    current_user = await get_current_user(request)
    if not current_user:
        raise HTTPException(401, "Not authenticated")

    body = {}
    try:
        body = await request.json()
    except Exception:
        pass

    email = body.get("email") or current_user.get("email")
    if not email:
        raise HTTPException(400, "No email provided")

    from services.email_service import _base_template
    html = _base_template("Email de Teste", f"""
    <h2 style="color:#10b981;font-size:18px;margin:0 0 12px;">Teste de Notificacao</h2>
    <p>Ola <strong style="color:#a78bfa;">{current_user.get('name', 'Usuario')}</strong>!</p>
    <p>Este e um email de teste do sistema de notificacoes do Scormify.</p>
    <p>Se voce recebeu este email, as notificacoes estao funcionando corretamente.</p>
    """)

    result = await send_email(email, "[Scormify] Teste de Notificacao", html)
    return {"status": result.get("status"), "email": email, "detail": result}


@router.get("/notifications/settings")
async def get_notification_settings(request: Request, user: dict = Depends(require_auth)):
    """Get user notification preferences."""
    current_user = await get_current_user(request)
    if not current_user:
        raise HTTPException(401)

    user_id = current_user.get("user_id")
    settings = await db.notification_settings.find_one({"userId": user_id}, {"_id": 0})

    if not settings:
        settings = {
            "userId": user_id,
            "approval_submitted": True,
            "approval_result": True,
            "course_generated": True,
            "tutor_summary": True,
        }

    return settings


@router.put("/notifications/settings")
async def update_notification_settings(request: Request, user: dict = Depends(require_auth)):
    """Update user notification preferences."""
    current_user = await get_current_user(request)
    if not current_user:
        raise HTTPException(401)

    body = await request.json()
    user_id = current_user.get("user_id")

    await db.notification_settings.update_one(
        {"userId": user_id},
        {"$set": {
            "userId": user_id,
            "approval_submitted": body.get("approval_submitted", True),
            "approval_result": body.get("approval_result", True),
            "course_generated": body.get("course_generated", True),
            "tutor_summary": body.get("tutor_summary", True),
        }},
        upsert=True,
    )
    return {"status": "updated"}


# ── Helper: send notification respecting user preferences ──

async def send_notification(user_id: str, notification_type: str, **kwargs):
    """Send notification if user hasn't disabled it. Returns result dict."""
    # Check preferences
    settings = await db.notification_settings.find_one({"userId": user_id}, {"_id": 0})
    if settings and not settings.get(notification_type, True):
        return {"status": "disabled_by_user"}

    # Get user email
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0, "email": 1, "name": 1})
    if not user or not user.get("email"):
        return {"status": "no_email"}

    email = user["email"]

    if notification_type == "approval_submitted":
        return await notify_approval_submitted(email, **kwargs)
    elif notification_type == "approval_result":
        if kwargs.get("approved"):
            return await notify_approval_approved(email, **kwargs)
        else:
            return await notify_approval_rejected(email, **kwargs)
    elif notification_type == "course_generated":
        return await notify_course_generated(email, **kwargs)
    elif notification_type == "tutor_summary":
        return await notify_tutor_summary(email, **kwargs)

    return {"status": "unknown_type"}
