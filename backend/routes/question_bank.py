"""Multi-tenant question bank consumed by every educational game."""
from __future__ import annotations

import csv
import io
import json
import random
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, Response

from routes.auth import has_role, require_auth, require_company_admin
from routes.deps import db
from routes.projects_common import load_authorized_project
from services.question_engine import QuestionEngine, normalize_question, quiz_to_game_row, build_question_template_xlsx

router = APIRouter(prefix="/game-questions", tags=["Game Question Bank"])


def _company(user: dict, requested: str = "") -> str:
    if has_role(user, "super_admin"):
        company_id = requested or user.get("companyId") or ""
    else:
        company_id = user.get("companyId") or ""
    if not company_id:
        raise HTTPException(400, "Selecione uma empresa para o banco de questões")
    return company_id


def _xlsx_rows(content: bytes) -> list[dict]:
    """Read the first XLSX worksheet using only the Python standard library."""
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = ["".join(node.itertext()) for node in root.findall("m:si", ns)]
        sheet_name = next((name for name in archive.namelist() if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")), None)
        if not sheet_name:
            return []
        sheet = ET.fromstring(archive.read(sheet_name))
        matrix = []
        for row in sheet.findall(".//m:row", ns):
            values = {}
            for cell in row.findall("m:c", ns):
                ref = cell.attrib.get("r", "A1")
                column = "".join(ch for ch in ref if ch.isalpha())
                value_node = cell.find("m:v", ns)
                inline = cell.find("m:is", ns)
                value = "" if value_node is None else value_node.text or ""
                if cell.attrib.get("t") == "s" and value.isdigit():
                    value = shared[int(value)]
                elif inline is not None:
                    value = "".join(inline.itertext())
                values[column] = value
            matrix.append(values)
        if not matrix:
            return []
        columns = sorted(matrix[0], key=lambda name: (len(name), name))
        headers = [str(matrix[0].get(column, "")).strip() for column in columns]
        return [{headers[i]: row.get(column, "") for i, column in enumerate(columns) if headers[i]} for row in matrix[1:]]


def _parse_upload(filename: str, content: bytes) -> list[dict]:
    lower = filename.lower()
    if lower.endswith(".xlsx"):
        return _xlsx_rows(content)
    text = content.decode("utf-8-sig", errors="replace")
    if lower.endswith(".json"):
        payload = json.loads(text)
        rows = payload.get("questions", []) if isinstance(payload, dict) else payload
        return rows if isinstance(rows, list) else []
    dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    return list(csv.DictReader(io.StringIO(text), dialect=dialect))


@router.get("")
async def list_questions(
    companyId: str = "", grade: str = "", subject: str = "", topic: str = "",
    difficulty: str = "", search: str = "", page: int = Query(1, ge=1),
    pageSize: int = Query(50, ge=1, le=200), user: dict = Depends(require_company_admin),
):
    company_id = _company(user, companyId)
    query = {"companyId": company_id, "active": {"$ne": False}}
    for field, value in (("grade", grade), ("subject", subject), ("topic", topic), ("difficulty", difficulty)):
        if value:
            query[field] = value
    if search:
        query["$or"] = [{"question": {"$regex": search, "$options": "i"}}, {"topic": {"$regex": search, "$options": "i"}}]
    total = await db.game_questions.count_documents(query)
    items = await db.game_questions.find(query, {"_id": 0}).sort("createdAt", -1).skip((page - 1) * pageSize).limit(pageSize).to_list(pageSize)
    facets = {}
    for field in ("grade", "subject", "topic", "difficulty"):
        facets[field] = sorted(value for value in await db.game_questions.distinct(field, {"companyId": company_id}) if value)
    return {"items": items, "total": total, "page": page, "pageSize": pageSize, "facets": facets}


@router.get("/template")
async def download_question_template(user: dict = Depends(require_company_admin)):
    return Response(
        content=build_question_template_xlsx(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="modelo_questoes_jogos.xlsx"'},
    )


@router.get("/catalog")
async def game_question_catalog(
    projectId: str,
    grade: str = "",
    subject: str = "",
    topic: str = "",
    difficulty: str = "",
    pageSize: int = Query(200, ge=1, le=500),
    user: dict = Depends(require_auth),
):
    """Question catalog for the game builder, scoped by the open project.

    Resolving the tenant through an authorized project is essential for super
    admins, whose own account company may differ from the company currently
    being edited.
    """
    project = await load_authorized_project(projectId, user)
    company_id = str(project.get("companyId") or "")
    if not company_id:
        raise HTTPException(400, "O projeto não está vinculado a uma empresa")
    query = {"companyId": company_id, "active": {"$ne": False}}
    for field, value in (("grade", grade), ("subject", subject), ("topic", topic), ("difficulty", difficulty)):
        if value:
            query[field] = value
    items = await db.game_questions.find(query, {"_id": 0}).sort("createdAt", -1).limit(pageSize).to_list(pageSize)
    facets = {}
    for field in ("grade", "subject", "topic", "difficulty"):
        facets[field] = sorted(
            value for value in await db.game_questions.distinct(
                field, {"companyId": company_id, "active": {"$ne": False}}
            ) if value
        )
    return {"items": items, "total": len(items), "facets": facets, "companyId": company_id}


@router.post("/import")
async def import_questions(companyId: str = "", file: UploadFile = File(...), user: dict = Depends(require_company_admin)):
    company_id = _company(user, companyId)
    content = await file.read()
    if len(content) > 15 * 1024 * 1024:
        raise HTTPException(413, "Arquivo maior que 15 MB")
    try:
        rows = _parse_upload(file.filename or "questions.csv", content)
    except Exception as exc:
        raise HTTPException(400, f"Não foi possível ler o arquivo: {exc}") from exc
    valid, errors = [], []
    for index, row in enumerate(rows, start=2):
        try:
            valid.append(normalize_question(row, company_id, user.get("user_id", "")))
        except ValueError as exc:
            errors.append({"row": index, "error": str(exc)})
    if valid:
        await db.game_questions.insert_many(valid, ordered=False)
    return {"imported": len(valid), "rejected": len(errors), "errors": errors[:100]}


@router.post("/bulk")
async def import_api(payload: dict, user: dict = Depends(require_company_admin)):
    company_id = _company(user, str(payload.get("companyId") or ""))
    rows = payload.get("questions") or []
    if not isinstance(rows, list) or len(rows) > 5000:
        raise HTTPException(400, "Envie uma lista com no máximo 5.000 questões")
    valid, errors = [], []
    for index, row in enumerate(rows, start=1):
        try:
            valid.append(normalize_question(row, company_id, user.get("user_id", "")))
        except (ValueError, AttributeError) as exc:
            errors.append({"row": index, "error": str(exc)})
    if valid:
        await db.game_questions.insert_many(valid, ordered=False)
    return {"imported": len(valid), "rejected": len(errors), "errors": errors[:100]}


@router.post("/import-quiz-bank")
async def import_quiz_bank(payload: dict, user: dict = Depends(require_company_admin)):
    """Copy Quiz Generator questions into the tenant's reusable game bank.

    Agent-created legacy questions may not carry companyId, but their project
    does.  Resolving tenant ownership through projects keeps those questions
    available without ever exposing another company's global quiz records.
    """
    company_id = _company(user, str(payload.get("companyId") or ""))
    projects = await db.projects.find(
        {"companyId": company_id}, {"_id": 0, "id": 1, "name": 1, "title": 1}
    ).to_list(10000)
    project_titles = {
        str(project.get("id")): str(project.get("name") or project.get("title") or "Quiz")
        for project in projects if project.get("id")
    }
    ownership = [{"companyId": company_id}]
    if project_titles:
        ownership.append({"projectId": {"$in": list(project_titles)}})
    query: dict = {"$or": ownership}
    requested_ids = [str(item) for item in (payload.get("questionIds") or []) if item]
    if requested_ids:
        query["id"] = {"$in": requested_ids[:5000]}
    source_questions = await db.questions.find(query, {"_id": 0}).to_list(5000)
    source_ids = [str(question.get("id")) for question in source_questions if question.get("id")]
    already_imported = set()
    if source_ids:
        already_imported = set(await db.game_questions.distinct(
            "sourceQuizQuestionId",
            {"companyId": company_id, "sourceQuizQuestionId": {"$in": source_ids}},
        ))
    imported, skipped, errors = [], 0, []
    for question in source_questions:
        source_id = str(question.get("id") or "")
        if not source_id or source_id in already_imported:
            skipped += 1
            continue
        try:
            row = quiz_to_game_row(question, project_titles.get(str(question.get("projectId")), ""))
            normalized = normalize_question(row, company_id, user.get("user_id", ""))
            normalized["source"] = "quiz_bank"
            normalized["sourceQuizQuestionId"] = source_id
            normalized["sourceProjectId"] = str(question.get("projectId") or "")
            imported.append(normalized)
        except ValueError as exc:
            errors.append({"id": source_id, "error": str(exc)})
    if imported:
        await db.game_questions.insert_many(imported, ordered=False)
    return {
        "eligible": len(source_questions),
        "imported": len(imported),
        "skipped": skipped,
        "rejected": len(errors),
        "errors": errors[:100],
    }


@router.get("/random")
async def random_questions(companyId: str = "", grade: str = "", subject: str = "", topic: str = "", difficulty: str = "", count: int = Query(5, ge=1, le=50), user: dict = Depends(require_auth)):
    company_id = _company(user, companyId)
    match = {"companyId": company_id, "active": {"$ne": False}}
    for field, value in (("grade", grade), ("subject", subject), ("topic", topic), ("difficulty", difficulty)):
        if value:
            match[field] = value
    items = await db.game_questions.aggregate([{"$match": match}, {"$sample": {"size": count}}, {"$project": {"_id": 0}}]).to_list(count)
    return {"items": items, "count": len(items)}


@router.post("/{question_id}/validate")
async def validate_answer(question_id: str, payload: dict, user: dict = Depends(require_auth)):
    company_id = _company(user, str(payload.get("companyId") or ""))
    question = await db.game_questions.find_one({"id": question_id, "companyId": company_id}, {"_id": 0})
    if not question:
        raise HTTPException(404, "Questão não encontrada")
    correct = QuestionEngine.validate_answer(question, str(payload.get("answer") or ""))
    await db.game_questions.update_one({"id": question_id}, {"$inc": {"timesAnswered": 1, "timesCorrect": 1 if correct else 0}})
    return {"correct": correct, "explanation": question.get("explanation", "")}


@router.post("/results")
async def save_result(payload: dict, user: dict = Depends(require_auth)):
    company_id = _company(user, str(payload.get("companyId") or ""))
    result = {**payload, "id": f"gr_{random.getrandbits(64):016x}", "companyId": company_id, "userId": user.get("user_id"), "createdAt": datetime.now(timezone.utc).isoformat()}
    result.pop("_id", None)
    await db.game_results.insert_one(dict(result))
    return {"status": "saved", "id": result["id"]}


@router.delete("/{question_id}")
async def delete_question(question_id: str, companyId: str = "", user: dict = Depends(require_company_admin)):
    company_id = _company(user, companyId)
    result = await db.game_questions.update_one({"id": question_id, "companyId": company_id}, {"$set": {"active": False, "updatedAt": datetime.now(timezone.utc).isoformat()}})
    if not result.matched_count:
        raise HTTPException(404, "Questão não encontrada")
    return {"status": "deleted"}
