"""Admin settings, reports and AI tutor routes"""
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from typing import Optional
from datetime import datetime, timezone
import uuid
import os
import logging

from routes.deps import db, now_utc
from routes.auth import require_auth

logger = logging.getLogger("server")

router = APIRouter(tags=["Admin"])

# CORS headers for tutor endpoint (called cross-origin from SCORM/LMS)
TUTOR_CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
    "Access-Control-Max-Age": "86400",
}


@router.get("/dashboard/metrics")
async def get_dashboard_metrics():
    """Get dashboard metrics: total courses, total slides, total exports"""
    try:
        total_projects = await db.projects.count_documents({})
        
        # Count total slides across all projects
        pipeline = [
            {"$project": {"slideCount": {"$size": {"$ifNull": ["$course.slides", []]}}}},
            {"$group": {"_id": None, "total": {"$sum": "$slideCount"}}}
        ]
        slide_result = await db.projects.aggregate(pipeline).to_list(1)
        total_slides = slide_result[0]["total"] if slide_result else 0
        
        # Count exports from the exports tracking collection
        total_exports = await db.export_logs.count_documents({})
        
        return {
            "totalCourses": total_projects,
            "totalSlides": total_slides,
            "totalExports": total_exports,
        }
    except Exception as e:
        logger.error(f"Dashboard metrics error: {e}")
        return {
            "totalCourses": 0,
            "totalSlides": 0,
            "totalExports": 0,
        }



@router.get("/admin/tutor-settings")
async def get_tutor_settings():
    settings = await db.settings.find_one({"key": "tutor"}, {"_id": 0})
    if not settings:
        settings = {
            "key": "tutor", "enabled": True, "messageLimit": 50,
            "suggestedQuestions": [], "systemPrompt": "", "tutorName": "Tutor IA",
            "apiUrl": ""  # Empty means use default BASE_URL
        }
    return settings


@router.put("/admin/tutor-settings")
async def update_tutor_settings(request: Request):
    data = await request.json()
    data["key"] = "tutor"
    await db.settings.update_one({"key": "tutor"}, {"$set": data}, upsert=True)
    return {"status": "ok", "message": "Tutor settings updated"}


@router.get("/admin/reports")
async def get_admin_reports(request: Request, user: dict = Depends(require_auth)):
    is_super = user.get("role") == "super_admin"
    user_company_id = user.get("companyId")
    if not is_super and user.get("role") != "company_admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    if is_super:
        companies = await db.companies.find({"isActive": True}, {"_id": 0}).to_list(1000)
    else:
        company = await db.companies.find_one({"id": user_company_id}, {"_id": 0})
        companies = [company] if company else []
    company_ids = [c["id"] for c in companies]
    users_query = {"companyId": {"$in": company_ids}} if company_ids else {}
    if is_super:
        users_query = {}
    all_users = await db.users.find(users_query, {"_id": 0, "passwordHash": 0}).to_list(5000)
    users_map = {u["user_id"]: u for u in all_users}
    projects_query = {}
    if is_super:
        projects_query = {}  # Show ALL projects for super admin
    else:
        projects_query = {"companyId": user_company_id}
    projects = await db.projects.find(
        projects_query,
        {"_id": 0, "id": 1, "name": 1, "companyId": 1, "userId": 1, "createdAt": 1, "createdByAgent": 1, "source": 1, "status": 1, "course.slides": {"$size": "$course.slides"}}
    ).sort("createdAt", -1).to_list(5000)
    usage_query = {}
    if not is_super:
        usage_query = {"companyId": user_company_id}
    usage_logs = await db.usage_logs.find(usage_query, {"_id": 0}).to_list(10000)
    USD_TO_BRL = 5.50
    reports = []
    for company in companies:
        company_id = company["id"]
        company_projects = [p for p in projects if p.get("companyId") == company_id]
        company_usage = [u for u in usage_logs if u.get("companyId") == company_id]
        company_users = [u for u in all_users if u.get("companyId") == company_id]
        total_cost_usd = sum(
            u.get("estimatedCost", {}).get("textGeneration", 0) +
            u.get("estimatedCost", {}).get("imageGeneration", 0) +
            u.get("estimatedCost", {}).get("narration", 0)
            for u in company_usage
        )
        total_slides = sum(u.get("details", {}).get("slides", 0) for u in company_usage)
        total_images = sum(u.get("details", {}).get("aiImages", 0) for u in company_usage)
        total_narrations = sum(u.get("details", {}).get("narrations", 0) for u in company_usage)
        project_details = []
        for p in company_projects:
            editor_id = p.get("userId")
            editor = users_map.get(editor_id, {})
            # Determine source/origin of the project
            source = p.get("source", "")
            if not source:
                source = "agent" if p.get("createdByAgent") else "manual"
            project_details.append({
                "id": p.get("id"), "name": p.get("name"), "createdAt": p.get("createdAt"),
                "editorId": editor_id, "editorName": editor.get("name", "Desconhecido"),
                "editorEmail": editor.get("email", ""),
                "source": source,
            })
        reports.append({
            "company": {"id": company_id, "name": company["name"], "slug": company.get("slug", "")},
            "stats": {
                "totalCourses": len(company_projects), "totalSlides": total_slides,
                "totalAiImages": total_images, "totalNarrations": total_narrations,
                "totalCostUSD": round(total_cost_usd, 4), "totalCostBRL": round(total_cost_usd * USD_TO_BRL, 2),
            },
            "editors": [
                {"id": u["user_id"], "name": u["name"], "email": u["email"]}
                for u in company_users if u.get("role") in ("editor", "company_admin")
            ],
            "courses": project_details[:50],
        })
    if is_super:
        orphan_projects = [p for p in projects if not p.get("companyId")]
        orphan_usage = [u for u in usage_logs if not u.get("companyId")]
        if orphan_projects:
            total_cost_orphan = sum(
                u.get("estimatedCost", {}).get("textGeneration", 0) +
                u.get("estimatedCost", {}).get("imageGeneration", 0) +
                u.get("estimatedCost", {}).get("narration", 0)
                for u in orphan_usage
            )
            reports.append({
                "company": {"id": None, "name": "Sem Empresa (Projetos Orfaos)", "slug": "orphan"},
                "stats": {
                    "totalCourses": len(orphan_projects),
                    "totalSlides": sum(u.get("details", {}).get("slides", 0) for u in orphan_usage),
                    "totalAiImages": sum(u.get("details", {}).get("aiImages", 0) for u in orphan_usage),
                    "totalNarrations": sum(u.get("details", {}).get("narrations", 0) for u in orphan_usage),
                    "totalCostUSD": round(total_cost_orphan, 4),
                    "totalCostBRL": round(total_cost_orphan * USD_TO_BRL, 2),
                },
                "editors": [],
                "courses": [
                    {"id": p.get("id"), "name": p.get("name"), "createdAt": p.get("createdAt"),
                     "editorId": p.get("userId"), "editorName": users_map.get(p.get("userId"), {}).get("name", "Desconhecido"),
                     "source": p.get("source") or ("agent" if p.get("createdByAgent") else "manual")}
                    for p in orphan_projects[:50]
                ],
            })
    return {"reports": reports, "generatedAt": datetime.now(timezone.utc).isoformat(), "currency": {"USD_TO_BRL": USD_TO_BRL}}


@router.options("/tutor/chat")
async def tutor_chat_options():
    """Explicit OPTIONS handler for CORS preflight from SCORM/LMS domains"""
    return JSONResponse(content="", headers=TUTOR_CORS_HEADERS)


@router.post("/tutor/chat")
async def tutor_chat(request: Request):
    data = await request.json()
    user_message = data.get("message", "")
    course_topic = data.get("courseTopic", "")
    course_context = data.get("courseContext", "")
    history = data.get("history", [])
    session_id = data.get("sessionId", str(uuid.uuid4()))
    project_id = data.get("projectId", "")
    company_id = data.get("companyId", "")
    if not user_message:
        raise HTTPException(status_code=400, detail="Message is required")
    settings = await db.settings.find_one({"key": "tutor"}, {"_id": 0})
    if not settings or not settings.get("enabled", True):
        raise HTTPException(status_code=403, detail="AI Tutor is disabled")
    message_limit = settings.get("messageLimit", 50)
    tutor_name = settings.get("tutorName", "Tutor IA")
    custom_prompt = settings.get("systemPrompt", "")
    msg_count = len([m for m in history if m.get("role") == "user"])
    if msg_count >= message_limit:
        return JSONResponse(
            content={"response": f"Voce atingiu o limite de {message_limit} mensagens para esta sessao.", "limitReached": True},
            headers=TUTOR_CORS_HEADERS
        )
    emergent_key = os.environ.get('EMERGENT_LLM_KEY', '')
    if not emergent_key:
        raise HTTPException(status_code=500, detail="AI service not configured")
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        system_msg = f"""Voce e o "{tutor_name}", um tutor educacional especializado e amigavel.
Seu papel e ajudar alunos a entender o conteudo do curso sobre: {course_topic}

REGRAS IMPORTANTES:
1. Responda SOMENTE com base no conteudo fornecido abaixo em "CONTEUDO DO CURSO".
2. Se o aluno perguntar sobre algo que NAO esta no conteudo do curso, diga claramente que esse tema nao e abordado no curso.
3. Use linguagem clara e acessivel
4. De exemplos praticos baseados no conteudo real do curso
5. Incentive o aluno a revisar slides especificos quando relevante
6. Responda no mesmo idioma da pergunta do aluno
7. Mantenha respostas concisas (maximo 3 paragrafos)

CONTEUDO DO CURSO:
{course_context}"""
        if custom_prompt:
            system_msg += f"\n\nINSTRUCOES ADICIONAIS DO INSTRUTOR:\n{custom_prompt}"
        chat = LlmChat(
            api_key=emergent_key, session_id=f"tutor-{session_id}", system_message=system_msg
        ).with_model("gemini", "gemini-3-flash-preview")
        for msg in history[-10:]:
            if msg.get("role") == "user":
                await chat.send_message(UserMessage(text=msg["content"]))
        response = await chat.send_message(UserMessage(text=user_message))

        # Log the question for analytics dashboard
        try:
            await db.tutor_logs.insert_one({
                "sessionId": session_id,
                "projectId": project_id,
                "companyId": company_id,
                "courseTopic": course_topic,
                "question": user_message,
                "response": response[:500] if isinstance(response, str) else str(response)[:500],
                "createdAt": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as log_err:
            logger.warning(f"Failed to log tutor question (non-fatal): {log_err}")

        return JSONResponse(
            content={"response": response, "limitReached": False, "messagesUsed": msg_count + 1, "messageLimit": message_limit},
            headers=TUTOR_CORS_HEADERS
        )
    except Exception as e:
        logger.error(f"Tutor chat error: {e}")
        raise HTTPException(status_code=500, detail=f"AI service error: {str(e)}")



# =============================================================================
# TUTOR ANALYTICS DASHBOARD
# =============================================================================

@router.get("/admin/tutor-dashboard")
async def get_tutor_dashboard(request: Request, user: dict = Depends(require_auth)):
    """Get tutor question analytics grouped by course and company.
    - Super Admin: sees all data
    - Company Admin: sees only data for their company
    """
    role = user.get("role")
    company_id = user.get("companyId")

    if role not in ("super_admin", "company_admin"):
        raise HTTPException(403, "Acesso negado")

    # Build match filter
    match_filter = {}
    if role == "company_admin" and company_id:
        match_filter["companyId"] = company_id

    # Aggregate questions by course topic
    pipeline = [
        {"$match": match_filter} if match_filter else {"$match": {}},
        {"$group": {
            "_id": {
                "projectId": "$projectId",
                "companyId": "$companyId",
                "courseTopic": "$courseTopic",
            },
            "totalQuestions": {"$sum": 1},
            "questions": {"$push": {
                "question": "$question",
                "response": "$response",
                "createdAt": "$createdAt",
                "sessionId": "$sessionId",
            }},
            "lastActivity": {"$max": "$createdAt"},
        }},
        {"$sort": {"totalQuestions": -1}},
    ]

    results = await db.tutor_logs.aggregate(pipeline).to_list(200)

    # Enrich with project and company names
    courses = []
    for r in results:
        group_key = r["_id"]
        project_id = group_key.get("projectId", "")
        cid = group_key.get("companyId", "")

        project_name = group_key.get("courseTopic", "Curso desconhecido")
        if project_id:
            project = await db.projects.find_one({"id": project_id}, {"_id": 0, "name": 1})
            if project:
                project_name = project.get("name", project_name)

        company_name = ""
        if cid:
            comp = await db.companies.find_one({"id": cid}, {"_id": 0, "name": 1})
            if comp:
                company_name = comp.get("name", "")

        # Count unique question texts (top questions)
        question_counts = {}
        for q in r["questions"]:
            qtxt = q.get("question", "").strip().lower()
            if qtxt:
                question_counts[qtxt] = question_counts.get(qtxt, 0) + 1

        top_questions = sorted(question_counts.items(), key=lambda x: -x[1])[:10]

        courses.append({
            "projectId": project_id,
            "companyId": cid,
            "courseName": project_name,
            "companyName": company_name,
            "totalQuestions": r["totalQuestions"],
            "uniqueQuestions": len(question_counts),
            "lastActivity": r.get("lastActivity", ""),
            "topQuestions": [{"question": q, "count": c} for q, c in top_questions],
            "recentQuestions": sorted(r["questions"], key=lambda x: x.get("createdAt", ""), reverse=True)[:20],
        })

    # Summary stats
    total_questions = sum(c["totalQuestions"] for c in courses)
    total_courses = len(courses)

    # Company summary (for super admin)
    company_summary = {}
    for c in courses:
        cname = c["companyName"] or "Sem empresa"
        if cname not in company_summary:
            company_summary[cname] = {"companyId": c["companyId"], "totalQuestions": 0, "courses": 0}
        company_summary[cname]["totalQuestions"] += c["totalQuestions"]
        company_summary[cname]["courses"] += 1

    return {
        "totalQuestions": total_questions,
        "totalCourses": total_courses,
        "companies": [{"name": k, **v} for k, v in sorted(company_summary.items(), key=lambda x: -x[1]["totalQuestions"])],
        "courses": courses,
    }


@router.get("/admin/tutor-dashboard/course/{project_id}")
async def get_tutor_course_detail(project_id: str, request: Request, user: dict = Depends(require_auth)):
    """Get detailed tutor analytics for a specific course."""
    role = user.get("role")
    company_id = user.get("companyId")

    if role not in ("super_admin", "company_admin"):
        raise HTTPException(403, "Acesso negado")

    match_filter = {"projectId": project_id}
    if role == "company_admin" and company_id:
        match_filter["companyId"] = company_id

    logs = await db.tutor_logs.find(
        match_filter,
        {"_id": 0}
    ).sort("createdAt", -1).to_list(500)

    # Count question frequency
    question_counts = {}
    for log in logs:
        qtxt = log.get("question", "").strip().lower()
        if qtxt:
            if qtxt not in question_counts:
                question_counts[qtxt] = {"question": log["question"], "count": 0, "lastAsked": log.get("createdAt", "")}
            question_counts[qtxt]["count"] += 1

    top_questions = sorted(question_counts.values(), key=lambda x: -x["count"])

    # Get project name
    project = await db.projects.find_one({"id": project_id}, {"_id": 0, "name": 1})

    return {
        "projectId": project_id,
        "courseName": project.get("name", "Curso") if project else "Curso",
        "totalQuestions": len(logs),
        "uniqueQuestions": len(question_counts),
        "topQuestions": top_questions[:30],
        "recentLogs": logs[:50],
    }
