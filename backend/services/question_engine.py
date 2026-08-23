"""Shared, storage-agnostic question normalization for educational games."""
from __future__ import annotations

import json
import random
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable


FIELD_ALIASES = {
    "externalId": ("id", "externalid", "codigo", "código"),
    "grade": ("serie", "série", "ano", "grade"),
    "subject": ("disciplina", "subject"),
    "topic": ("tema", "assunto", "topic"),
    "difficulty": ("nivel", "nível", "nivel de dificuldade", "nível de dificuldade", "dificuldade", "difficulty"),
    "question": ("pergunta", "questao", "questão", "question", "texto"),
    "correctAnswer": ("respostacorreta", "resposta correta", "gabarito", "correctanswer"),
    "explanation": ("explicacao", "explicação", "comentario", "comentário", "explanation"),
    "imageUrl": ("imagem", "image", "imageurl"),
    "audioUrl": ("audio", "áudio", "audiourl"),
    "videoUrl": ("video", "vídeo", "videourl"),
}


def _key(value: Any) -> str:
    return re.sub(r"[^a-z0-9áàâãéêíóôõúüç ]", "", str(value or "").strip().lower())


def _value(row: dict, field: str, default: Any = "") -> Any:
    normalized = {_key(k): v for k, v in row.items()}
    for alias in FIELD_ALIASES[field]:
        if _key(alias) in normalized and normalized[_key(alias)] not in (None, ""):
            return normalized[_key(alias)]
    return default


def _alternatives(row: dict) -> list[dict]:
    raw = row.get("alternatives") or row.get("alternativas")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            raw = [part.strip() for part in re.split(r"\s*[|;]\s*", raw) if part.strip()]
    if not isinstance(raw, list):
        indexed = []
        for label in ("a", "b", "c", "d", "e", "f"):
            for prefix in ("alternativa", "opcao", "opção", "option"):
                expected = {_key(prefix + label), _key(prefix + " " + label)}
                candidate = next((v for k, v in row.items() if _key(k) in expected), None)
                if candidate not in (None, ""):
                    indexed.append(str(candidate).strip())
                    break
        raw = indexed
    result = []
    for index, item in enumerate(raw or []):
        if isinstance(item, dict):
            text = str(item.get("text") or item.get("texto") or "").strip()
            item_id = str(item.get("id") or chr(65 + index))
        else:
            text, item_id = str(item).strip(), chr(65 + index)
        if text:
            result.append({"id": item_id, "text": text})
    return result


def normalize_question(row: dict, company_id: str, created_by: str = "") -> dict:
    """Normalize Portuguese/English import columns into one stable contract."""
    alternatives = _alternatives(row)
    correct_raw = str(_value(row, "correctAnswer", "")).strip()
    correct_id = correct_raw.upper()
    if correct_id not in {alt["id"].upper() for alt in alternatives}:
        matched = next((alt["id"] for alt in alternatives if alt["text"].casefold() == correct_raw.casefold()), "")
        correct_id = matched or correct_id
    if not str(_value(row, "question", "")).strip():
        raise ValueError("Pergunta vazia")
    if len(alternatives) < 2:
        raise ValueError("A questão precisa de pelo menos duas alternativas")
    if not correct_id:
        raise ValueError("Resposta correta não informada")
    difficulty = _key(_value(row, "difficulty", "medio"))
    difficulty = {"fácil": "facil", "médio": "medio", "difícil": "dificil"}.get(difficulty, difficulty)
    if difficulty not in ("facil", "medio", "dificil"):
        difficulty = "medio"
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": f"gq_{uuid.uuid4().hex[:16]}",
        "externalId": str(_value(row, "externalId", "")).strip(),
        "companyId": company_id,
        "grade": str(_value(row, "grade", "")).strip(),
        "subject": str(_value(row, "subject", "Geral")).strip() or "Geral",
        "topic": str(_value(row, "topic", "Geral")).strip() or "Geral",
        "difficulty": difficulty,
        "question": str(_value(row, "question", "")).strip(),
        "alternatives": alternatives,
        "correctAnswer": correct_id,
        "explanation": str(_value(row, "explanation", "")).strip(),
        "media": {
            "image": str(_value(row, "imageUrl", "")).strip(),
            "audio": str(_value(row, "audioUrl", "")).strip(),
            "video": str(_value(row, "videoUrl", "")).strip(),
        },
        "active": True,
        "timesAnswered": 0,
        "timesCorrect": 0,
        "createdBy": created_by,
        "createdAt": now,
        "updatedAt": now,
    }


class QuestionEngine:
    """Pure in-memory engine used by API adapters and unit tests."""

    def __init__(self, questions: Iterable[dict]):
        self.questions = list(questions)

    def get_question(self, question_id: str) -> dict | None:
        return next((q for q in self.questions if q.get("id") == question_id), None)

    def get_questions_by_topic(self, topic: str) -> list[dict]:
        return [q for q in self.questions if str(q.get("topic", "")).casefold() == topic.casefold()]

    def get_questions_by_difficulty(self, difficulty: str) -> list[dict]:
        return [q for q in self.questions if q.get("difficulty") == difficulty]

    def get_random_question(self, **filters: str) -> dict | None:
        choices = self.questions
        for field, value in filters.items():
            if value:
                choices = [q for q in choices if str(q.get(field, "")).casefold() == str(value).casefold()]
        return random.choice(choices) if choices else None

    @staticmethod
    def validate_answer(question: dict, answer: str) -> bool:
        return str(question.get("correctAnswer", "")).casefold() == str(answer or "").casefold()
