"""Project-scoped bank for rich assessment questions."""
from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from routes.auth import require_auth
from routes.deps import db
from routes.projects_common import load_authorized_project

router = APIRouter(prefix="/assessment-questions", tags=["Assessment Bank"])
QUESTION_TYPES = {"single_choice", "multiple_choice", "ordering", "categorization"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean(value: Any, limit: int = 2000) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def make_id(prefix: str = "aq") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def json_response(value: Any) -> dict:
    raw = str(value or "").strip()
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw, re.I)
    if fenced:
        raw = fenced.group(1).strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("A IA não retornou JSON válido")
        parsed = json.loads(raw[start:end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("A IA não retornou uma avaliação válida")
    return parsed


def normalise(raw: dict, project: dict, user_id: str, item_id: str = "") -> dict:
    if not isinstance(raw, dict):
        raise ValueError("Questão inválida")
    qtype = clean(raw.get("type"), 60) or "single_choice"
    if qtype not in QUESTION_TYPES:
        raise ValueError("Tipo de questão não suportado")
    prompt = clean(raw.get("prompt") or raw.get("text"), 1800)
    if not prompt:
        raise ValueError("Informe o enunciado da questão")

    def attachment(source):
        if not isinstance(source, dict) or not source.get('url'):
            return None
        url = clean(source.get('url'), 4000)
        prefix = f'/api/projects/{project.get("id")}/assets/'
        if not url.startswith(prefix) or not re.fullmatch(r'[A-Za-z0-9_.-]+', url[len(prefix):]) or '..' in url[len(prefix):]:
            raise ValueError('Anexe um arquivo deste projeto para usar na questão')
        kind = clean(source.get('kind'), 40)
        if kind not in {'image', 'video', 'document'}:
            raise ValueError('Tipo de anexo inválido')
        return {'url': url, 'kind': kind, 'name': clean(source.get('name'), 300)}

    options = []
    for index, option in enumerate(raw.get("options") or raw.get("alternatives") or []):
        option = {"text": option} if isinstance(option, str) else option
        if not isinstance(option, dict):
            continue
        text = clean(option.get("text"), 700)
        media = attachment(option.get('media'))
        if text or media:
            options.append({"id": clean(option.get("id"), 100) or f"op_{index + 1}", "text": text, "isCorrect": option.get("isCorrect") is True, "media": media})

    items = []
    for index, item in enumerate(raw.get("items") or []):
        item = {"text": item} if isinstance(item, str) else item
        if not isinstance(item, dict):
            continue
        text = clean(item.get("text"), 700)
        media = attachment(item.get('media'))
        if text or media:
            items.append({"id": clean(item.get("id"), 100) or f"item_{index + 1}", "text": text, "correctTarget": clean(item.get("correctTarget"), 160), "media": media})

    targets = []
    for index, target in enumerate(raw.get("targets") or []):
        target = {"label": target} if isinstance(target, str) else target
        if not isinstance(target, dict):
            continue
        label = clean(target.get("label") or target.get("text"), 200)
        if label:
            targets.append({"id": clean(target.get("id"), 120) or f"target_{index + 1}", "label": label})
    correct_order = [clean(value, 120) for value in (raw.get("correctOrder") or []) if clean(value, 120)]
    for entries in (options, items, targets):
        ids = [entry['id'] for entry in entries]
        if len(set(ids)) != len(ids) or any(not re.fullmatch(r'[A-Za-z0-9_-]+', item) for item in ids):
            raise ValueError('Identificadores de alternativas, itens e destinos devem ser únicos e válidos')

    if qtype in {"single_choice", "multiple_choice"}:
        correct_count = sum(1 for option in options if option["isCorrect"])
        if len(options) < 2:
            raise ValueError("Inclua ao menos duas alternativas")
        if qtype == "single_choice" and correct_count != 1:
            raise ValueError("Escolha simples precisa ter exatamente uma resposta correta")
        if qtype == "multiple_choice" and correct_count < 1:
            raise ValueError("Marque ao menos uma resposta correta")
    if qtype == "ordering":
        if len(items) < 2:
            raise ValueError("Inclua ao menos duas etapas para ordenar")
        item_ids = {item["id"] for item in items}
        if correct_order and (len(correct_order) != len(items) or set(correct_order) != item_ids):
            raise ValueError('A ordem correta deve conter cada etapa uma única vez')
        correct_order = correct_order or [item["id"] for item in items]
    if qtype == "categorization":
        target_ids = {target["id"] for target in targets}
        if len(items) < 2 or len(targets) < 2 or any(item["correctTarget"] not in target_ids for item in items):
            raise ValueError("Classificação requer itens, categorias e destino correto para cada item")

    source_media = raw.get("media") if isinstance(raw.get("media"), dict) else {}
    media_url = clean(source_media.get("url") or raw.get("mediaUrl"), 4000)
    if source_media.get('source') == 'external':
        if source_media.get('kind') != 'video':
            raise ValueError('Links externos são permitidos apenas para vídeos de apoio')
        from services.assessment_video_links import assessment_video_link
        video = assessment_video_link(media_url)
        media = {'url': video['url'], 'kind': 'video', 'source': 'external',
                 'provider': video['provider'], 'name': clean(source_media.get('name'),300) or 'Vídeo · ' + video['provider']}
    else:
        media = attachment({"url": media_url, "kind": source_media.get("kind") or raw.get("mediaKind"), "name": source_media.get("name") or raw.get("mediaName")})
    return {
        "id": item_id or clean(raw.get("id"), 100) or make_id(),
        "projectId": str(project.get("id") or ""), "companyId": str(project.get("companyId") or ""),
        "category": clean(raw.get("category"), 140) or "Geral", "title": clean(raw.get("title"), 300) or prompt[:90],
        "type": qtype, "prompt": prompt, "instructions": clean(raw.get("instructions"), 800),
        "options": options, "items": items, "targets": targets, "correctOrder": correct_order,
        "media": media, "explanation": clean(raw.get("explanation"), 1800),
        "points": max(1, min(100, int(raw.get("points") or 1))), "updatedAt": now(),
        "createdAt": raw.get("createdAt") or now(), "createdBy": user_id,
    }


@router.get("")
async def list_questions(projectId: str, user: dict = Depends(require_auth)):
    project = await load_authorized_project(projectId, user)
    items = await db.assessment_questions.find({"projectId": str(project.get("id"))}, {"_id": 0}).sort("updatedAt", -1).to_list(1000)
    return {"items": items}


@router.post("")
async def create_question(payload: dict, user: dict = Depends(require_auth)):
    project = await load_authorized_project(clean(payload.get("projectId"), 120), user)
    try:
        question = normalise(payload, project, str(user.get("user_id") or ""))
    except (ValueError, TypeError) as exc:
        raise HTTPException(400, str(exc)) from exc
    question['id'] = make_id()
    await db.assessment_questions.insert_one(dict(question))
    return question


@router.put("/{question_id}")
async def update_question(question_id: str, payload: dict, user: dict = Depends(require_auth)):
    project = await load_authorized_project(clean(payload.get("projectId"), 120), user)
    existing = await db.assessment_questions.find_one({"id": question_id, "projectId": str(project.get("id"))}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "Questão de avaliação não encontrada")
    try:
        question = normalise({**existing, **payload}, project, str(user.get("user_id") or ""), question_id)
    except (ValueError, TypeError) as exc:
        raise HTTPException(400, str(exc)) from exc
    question["createdAt"] = existing.get("createdAt") or question["createdAt"]
    await db.assessment_questions.update_one({"id": question_id, "projectId": str(project.get("id"))}, {"$set": question})
    return question


@router.delete("/{question_id}")
async def delete_question(question_id: str, projectId: str, user: dict = Depends(require_auth)):
    project = await load_authorized_project(projectId, user)
    result = await db.assessment_questions.delete_one({"id": question_id, "projectId": str(project.get("id"))})
    if not result.deleted_count:
        raise HTTPException(404, "Questão de avaliação não encontrada")
    return {"status": "deleted"}


@router.post("/generate")
async def generate_questions(payload: dict, user: dict = Depends(require_auth)):
    project = await load_authorized_project(clean(payload.get("projectId"), 120), user)
    topic = clean(payload.get("prompt"), 6000)
    try:
        count = max(1, min(12, int(payload.get("count") or 5)))
    except (ValueError, TypeError) as exc:
        raise HTTPException(400, 'Quantidade de questões inválida') from exc
    if not topic:
        raise HTTPException(400, "Informe o tema ou conteúdo da avaliação")
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(503, "A geração por IA requer OPENAI_API_KEY configurada no servidor")
    model = os.environ.get("OPENAI_QUIZ_MODEL", "").strip() or os.environ.get("OPENAI_TEXT_MODEL", "").strip() or "gpt-4o"
    system = '''Você cria avaliações profissionais em português brasileiro. Responda somente JSON válido.
Crie questões claras e variadas dos tipos single_choice, multiple_choice, ordering e categorization.
Cada questão deve conter type, title, category, prompt (enunciado), instructions e explanation (feedback).
Para alternativas use options com id, text, isCorrect. Para ordering use items com id/text e correctOrder com os IDs.
Para categorization use targets com id/label e items com id/text/correctTarget. Não invente URLs de mídia.
Formato: {"questions":[{...}]}'''
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(api_key=api_key, session_id=f"assessment-{uuid.uuid4()}", system_message=system).with_model("openai", model).with_params(temperature=0.35)
        response = await chat.send_message(UserMessage(text=f"Crie exatamente {count} questões sobre:\n{topic}"))
        parsed = json_response(response)
        questions, warnings = [], []
        for raw in (parsed.get("questions") or [])[:count]:
            try:
                questions.append(normalise(raw, project, str(user.get("user_id") or ""), make_id()))
            except (ValueError, TypeError) as exc:
                warnings.append(str(exc))
        if not questions:
            raise ValueError("A IA não produziu questões válidas")
        await db.assessment_questions.insert_many([dict(question) for question in questions])
        return {"items": questions, "generated": len(questions), "warnings": warnings[:5]}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, f"Não foi possível gerar a avaliação: {str(exc)[:220]}") from exc
