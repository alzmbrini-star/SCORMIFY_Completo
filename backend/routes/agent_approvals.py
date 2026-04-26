"""Agent approval workflow routes — extracted from routes/agent.py.

Endpoints in this module:
  - GET  /api/agent/approval-queue                                  (list pending)
  - POST /api/agent/courses/{project_id}/submit-improvements-for-approval
  - POST /api/agent/improvement-approvals/{approval_id}/approve
  - POST /api/agent/improvement-approvals/{approval_id}/reject
  - POST /api/agent/clear-stuck-caches                              (super_admin)

These were grouped together because they:
  1. Operate on the `improvement_approvals` collection
  2. Implement a single coherent flow (submit → approve/reject)
  3. Are used by aprovadores / company_admin only — safe to isolate
"""
import copy
import uuid
import asyncio
import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException, Request, Depends

from routes.deps import db
from routes.auth import require_auth, has_role, has_any_role
from routes.projects_common import load_authorized_project

logger = logging.getLogger("server")

router = APIRouter(tags=["Agent - Approvals"])


# ============================================================================
# APPROVAL QUEUE (combined: storyboard sessions + improvement approvals)
# ============================================================================

@router.get("/agent/approval-queue")
async def get_approval_queue(request: Request, user: dict = Depends(require_auth)):
    """Get storyboard sessions in the approval pipeline.
    - Aprovador: sees ONLY pending_approval sessions targeted at their company
    - Super Admin: sees ALL pending_approval + approved sessions
    - Company Admin: sees pending_approval + approved targeted at their company
    """
    role = user.get("role")
    company_id = user.get("companyId")

    if role == "aprovador":
        if not company_id:
            raise HTTPException(403, "Aprovador must belong to a company")
        query = {"step": "pending_approval", "targetCompanyId": company_id}
    elif role == "super_admin":
        query = {"step": {"$in": ["pending_approval", "approved"]}}
    elif role == "company_admin":
        if not company_id:
            raise HTTPException(403, "Company admin must belong to a company")
        query = {"step": {"$in": ["pending_approval", "approved"]}, "targetCompanyId": company_id}
    else:
        raise HTTPException(403, "Acesso negado")

    sessions = await db.agent_sessions.find(
        query,
        {"_id": 0, "contentText": 0}
    ).sort("updatedAt", -1).to_list(100)

    # Enrich with user names
    for s in sessions:
        uid = s.get("userId")
        if uid:
            u = await db.users.find_one({"user_id": uid}, {"_id": 0, "name": 1, "email": 1})
            if u:
                s["userName"] = u.get("name", u.get("email", ""))

    # Also fetch improvement approvals
    if role == "aprovador":
        imp_query = {"status": "pending", "targetCompanyId": company_id}
    elif role == "super_admin":
        imp_query = {"status": {"$in": ["pending", "approved", "rejected"]}}
    elif role == "company_admin":
        imp_query = {"status": {"$in": ["pending", "approved", "rejected"]}, "targetCompanyId": company_id}
    else:
        imp_query = {}

    improvement_approvals = await db.improvement_approvals.find(
        imp_query,
        {"_id": 0}
    ).sort("submittedAt", -1).to_list(100)

    for ia in improvement_approvals:
        uid = ia.get("submittedBy")
        if uid:
            u = await db.users.find_one({"user_id": uid}, {"_id": 0, "name": 1, "email": 1})
            if u:
                ia["submitterName"] = u.get("name", u.get("email", ""))
        ia["_type"] = "improvement"

    for s in sessions:
        s["_type"] = "storyboard"

    combined = sessions + improvement_approvals
    combined.sort(key=lambda x: x.get("updatedAt") or x.get("submittedAt") or "", reverse=True)

    return combined


# ============================================================================
# SUBMIT IMPROVEMENTS FOR APPROVAL
# ============================================================================

@router.post("/agent/courses/{project_id}/submit-improvements-for-approval")
async def submit_improvements_for_approval(project_id: str, request: Request, user: dict = Depends(require_auth)):
    """Submit improvement preview for approval by a company's aprovador."""
    body = await request.json()
    preview_id = body.get("previewId")
    target_company_id = body.get("targetCompanyId")
    improvements = body.get("improvements", [])
    selected_new_slides = body.get("selectedNewSlides")

    if not preview_id:
        raise HTTPException(400, "previewId is required")
    if not target_company_id:
        raise HTTPException(400, "targetCompanyId is required")

    # Verify project exists and the user can access it
    project = await load_authorized_project(project_id, user)

    company = await db.companies.find_one({"id": target_company_id}, {"_id": 0, "name": 1, "id": 1})
    if not company:
        raise HTTPException(404, "Company not found")

    preview = await db.improvement_previews.find_one({"id": preview_id}, {"_id": 0})
    if not preview:
        raise HTTPException(404, "Preview not found - generate a preview first")

    # Lazy import to avoid circular dependency with routes.agent
    from routes.agent import _apply_ai_result_to_slides
    from models import generate_id

    original_slides = project.get("course", {}).get("slides", [])
    ai_result = preview.get("aiResult", {})

    after_slides = copy.deepcopy(original_slides)
    _apply_ai_result_to_slides(after_slides, ai_result, generate_id)

    affected_indices = set()
    for upd in ai_result.get("updatedSlides", []):
        idx = upd.get("slideIndex")
        if idx is not None and 0 <= idx < len(original_slides):
            affected_indices.add(idx)

    def _extract_html_for_approval(slide):
        htmls = []
        for el in slide.get("elements", []):
            c = el.get("htmlContent") or el.get("content") or ""
            if c and isinstance(c, str):
                htmls.append(c)
        return htmls

    comparisons = []
    for idx in sorted(affected_indices):
        comparisons.append({
            "slideIndex": idx,
            "title": {
                "before": original_slides[idx].get("title", ""),
                "after": after_slides[idx].get("title", ""),
            },
            "htmlBefore": _extract_html_for_approval(original_slides[idx]),
            "htmlAfter": _extract_html_for_approval(after_slides[idx]),
        })

    new_slide_previews = []
    for ns in ai_result.get("newSlides", []):
        new_slide_previews.append({
            "afterIndex": ns.get("afterIndex", 0),
            "title": ns.get("title", "Novo Slide"),
            "html": [e.get("content", "") for e in ns.get("elements", []) if e.get("content")],
        })

    approval_id = str(uuid.uuid4())
    await db.improvement_approvals.insert_one({
        "id": approval_id,
        "projectId": project_id,
        "projectTitle": project.get("title", "Sem titulo"),
        "previewId": preview_id,
        "targetCompanyId": target_company_id,
        "targetCompanyName": company.get("name", ""),
        "improvements": improvements,
        "selectedNewSlides": selected_new_slides,
        "comparisons": comparisons,
        "newSlides": new_slide_previews,
        "updatedCount": len(comparisons),
        "newCount": len(new_slide_previews),
        "status": "pending",
        "submittedBy": user.get("user_id"),
        "submittedAt": datetime.now(timezone.utc).isoformat(),
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    })

    # Send email to aprovadors (fire-and-forget)
    try:
        from services.email_service import notify_approval_submitted
        aprovadors = await db.users.find(
            {"companyId": target_company_id, "roles": {"$in": ["aprovador", "company_admin"]}},
            {"_id": 0, "email": 1}
        ).to_list(20)
        course_title = project.get("title", "Sem titulo")
        author_name = user.get("name", "Usuario")
        for apr in aprovadors:
            if apr.get("email"):
                asyncio.create_task(
                    notify_approval_submitted(apr["email"], author_name, course_title, approval_id)
                )
    except Exception as e:
        logger.warning(f"Failed to send improvement approval notification: {e}")

    return {
        "status": "ok",
        "approvalId": approval_id,
        "targetCompany": company.get("name", ""),
        "updatedCount": len(comparisons),
        "newCount": len(new_slide_previews),
    }


# ============================================================================
# APPROVE / REJECT
# ============================================================================

@router.post("/agent/improvement-approvals/{approval_id}/approve")
async def approve_improvement(approval_id: str, request: Request, user: dict = Depends(require_auth)):
    """Approve an improvement - automatically applies changes to the course."""
    doc = await db.improvement_approvals.find_one({"id": approval_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Improvement approval not found")
    if doc.get("status") != "pending":
        raise HTTPException(400, f"Approval must be pending, current: {doc['status']}")

    company_id = user.get("companyId")
    if not has_any_role(user, "aprovador", "company_admin", "super_admin"):
        raise HTTPException(403, "Only aprovadores can approve improvements")
    if has_role(user, "aprovador") and not has_any_role(user, "super_admin", "company_admin") and company_id != doc.get("targetCompanyId"):
        raise HTTPException(403, "You can only approve improvements targeted to your company")

    project_id = doc.get("projectId")
    preview_id = doc.get("previewId")

    project = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(404, "Project not found")

    preview = await db.improvement_previews.find_one({"id": preview_id}, {"_id": 0})
    if not preview:
        raise HTTPException(404, "Preview data not found - cannot apply improvements")

    from routes.agent import _apply_ai_result_to_slides
    from models import generate_id

    ai_result = preview.get("aiResult", {})
    original_course = copy.deepcopy(project.get("course", {}))
    slides = project.get("course", {}).get("slides", [])

    _apply_ai_result_to_slides(slides, ai_result, generate_id)

    new_slides_data = ai_result.get("newSlides", [])
    new_slides_added = 0
    if new_slides_data:
        for ns in sorted(new_slides_data, key=lambda x: x.get("afterIndex", 0), reverse=True):
            insert_idx = ns.get("afterIndex", len(slides) - 1) + 1
            new_slide = {
                "id": generate_id(),
                "title": ns.get("title", "Novo Slide"),
                "elements": ns.get("elements", []),
                "backgroundImage": "",
                "backgroundColor": "",
            }
            slides.insert(insert_idx, new_slide)
            new_slides_added += 1

    await db.projects.update_one(
        {"id": project_id},
        {"$set": {
            "course.slides": slides,
            "course._preApprovalBackup": original_course.get("slides"),
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        }}
    )

    await db.improvement_approvals.update_one(
        {"id": approval_id},
        {"$set": {
            "status": "approved",
            "approvedBy": user.get("user_id"),
            "approvedAt": datetime.now(timezone.utc).isoformat(),
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        }}
    )

    # Notify author of approval
    try:
        from services.email_service import notify_approval_approved
        author_id = doc.get("submittedBy")
        if author_id:
            author = await db.users.find_one({"user_id": author_id}, {"_id": 0, "email": 1})
            if author and author.get("email"):
                asyncio.create_task(
                    notify_approval_approved(
                        author["email"],
                        user.get("name", "Aprovador"),
                        doc.get("projectTitle", "Curso"),
                    )
                )
    except Exception as e:
        logger.warning(f"Failed to send improvement approved notification: {e}")

    return {
        "status": "approved",
        "projectId": project_id,
        "appliedSlides": len(ai_result.get("updatedSlides", [])),
        "newSlides": new_slides_added,
    }


@router.post("/agent/improvement-approvals/{approval_id}/reject")
async def reject_improvement(approval_id: str, request: Request, user: dict = Depends(require_auth)):
    """Reject an improvement approval."""
    doc = await db.improvement_approvals.find_one({"id": approval_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Improvement approval not found")
    if doc.get("status") != "pending":
        raise HTTPException(400, f"Approval must be pending, current: {doc['status']}")

    company_id = user.get("companyId")
    if not has_any_role(user, "aprovador", "company_admin", "super_admin"):
        raise HTTPException(403, "Only aprovadores can reject improvements")
    if has_role(user, "aprovador") and not has_any_role(user, "super_admin", "company_admin") and company_id != doc.get("targetCompanyId"):
        raise HTTPException(403, "You can only reject improvements targeted to your company")

    body = await request.json()
    reason = body.get("reason", "")

    await db.improvement_approvals.update_one(
        {"id": approval_id},
        {"$set": {
            "status": "rejected",
            "rejectedBy": user.get("user_id"),
            "rejectedAt": datetime.now(timezone.utc).isoformat(),
            "rejectionReason": reason,
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        }}
    )

    # Notify author of rejection
    try:
        from services.email_service import notify_approval_rejected
        author_id = doc.get("submittedBy")
        if author_id:
            author = await db.users.find_one({"user_id": author_id}, {"_id": 0, "email": 1})
            if author and author.get("email"):
                asyncio.create_task(
                    notify_approval_rejected(
                        author["email"],
                        user.get("name", "Aprovador"),
                        doc.get("projectTitle", "Curso"),
                        reason,
                    )
                )
    except Exception as e:
        logger.warning(f"Failed to send improvement rejected notification: {e}")

    return {"status": "rejected", "reason": reason}


# ============================================================================
# ADMIN: clear stuck caches
# ============================================================================

@router.post("/agent/clear-stuck-caches")
async def clear_stuck_caches(user: dict = Depends(require_auth)):
    """Admin endpoint to clear stuck analysis caches and sessions."""
    if not has_role(user, "super_admin"):
        raise HTTPException(403, "Only super_admin can clear caches")

    cache_result = await db.analysis_cache.delete_many({})

    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    stuck_result = await db.agent_sessions.update_many(
        {"step": {"$in": ["analyzing", "structuring"]}, "updatedAt": {"$lt": cutoff}},
        {"$set": {"step": "uploaded", "error": "Reset by admin"}}
    )

    return {
        "cachesCleared": cache_result.deleted_count,
        "stuckSessionsReset": stuck_result.modified_count,
    }
