"""Editor quiz generation must use OpenAI and validate generated questions."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from emergentintegrations.llm import chat as llm_chat  # noqa: E402
from models import QuizGenerateRequest  # noqa: E402
from routes import questions  # noqa: E402


class FakeInsertResult:
    inserted_id = "inserted"


class FakeQuestionsCollection:
    def __init__(self):
        self.rows = []

    async def insert_one(self, row):
        self.rows.append(dict(row))
        return FakeInsertResult()


class FakeLlmChat:
    captured: dict = {}
    response = ""
    error: Exception | None = None

    def __init__(self, api_key, session_id, system_message=""):
        self.captured.update(
            api_key=api_key,
            session_id=session_id,
            system_message=system_message,
        )

    def with_model(self, provider, model):
        self.captured.update(provider=provider, model=model)
        return self

    def with_params(self, **params):
        self.captured["params"] = params
        return self

    async def send_message(self, message):
        self.captured["prompt"] = message.text
        if self.error:
            raise self.error
        return self.response


def _valid_response() -> str:
    return """```json
{"questions": [
  {
    "type": "multiple_choice",
    "text": "Qual equipamento protege a cabeça?",
    "alternatives": [
      {"text": "Capacete", "isCorrect": true},
      {"text": "Luva", "isCorrect": false},
      {"text": "Bota", "isCorrect": false},
      {"text": "Avental", "isCorrect": false}
    ],
    "explanation": "O capacete protege a cabeça."
  },
  {
    "type": "multiple_choice",
    "text": "O que deve ser feito antes de usar um EPI?",
    "alternatives": [
      {"text": "Inspecioná-lo", "isCorrect": true},
      {"text": "Descartá-lo", "isCorrect": false},
      {"text": "Emprestá-lo", "isCorrect": false},
      {"text": "Ignorar o manual", "isCorrect": false}
    ],
    "explanation": "A inspeção identifica danos."
  }
]}
```"""


@pytest.fixture(autouse=True)
def reset_fakes(monkeypatch):
    FakeLlmChat.captured = {}
    FakeLlmChat.response = _valid_response()
    FakeLlmChat.error = None
    fake_collection = FakeQuestionsCollection()
    monkeypatch.setattr(llm_chat, "LlmChat", FakeLlmChat)
    monkeypatch.setattr(
        questions,
        "db",
        SimpleNamespace(questions=fake_collection),
    )

    async def fake_load_project(project_id, user):
        assert user["companyId"] == "tenant-1"
        return {
            "id": project_id,
            "name": "Segurança do Trabalho",
            "companyId": "tenant-1",
        }

    monkeypatch.setattr(questions, "load_authorized_project", fake_load_project)
    monkeypatch.delenv("OPENAI_QUIZ_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_TEXT_MODEL", raising=False)
    monkeypatch.delenv("EMERGENT_LLM_KEY", raising=False)
    return fake_collection


@pytest.mark.asyncio
async def test_quiz_uses_openai_key_model_and_tenant_context(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("OPENAI_QUIZ_MODEL", "gpt-quiz-test")

    result = await questions.generate_questions_with_ai(
        QuizGenerateRequest(
            projectId="project-1",
            source="prompt",
            prompt="Uso correto de EPIs",
            context="Normas brasileiras",
            questionType="multiple_choice",
            count=2,
        ),
        user={"id": "author-1", "companyId": "tenant-1"},
    )

    assert result["success"] is True
    assert result["count"] == 2
    assert FakeLlmChat.captured["api_key"] == "test-openai-key"
    assert FakeLlmChat.captured["provider"] == "openai"
    assert FakeLlmChat.captured["model"] == "gpt-quiz-test"
    assert FakeLlmChat.captured["params"]["temperature"] == 0.2
    assert "Normas brasileiras" in FakeLlmChat.captured["prompt"]
    assert all(q["companyId"] == "tenant-1" for q in result["questions"])
    assert all(len(q["alternatives"]) == 4 for q in result["questions"])


@pytest.mark.asyncio
async def test_quiz_reports_missing_openai_configuration(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(HTTPException) as exc_info:
        await questions.generate_questions_with_ai(
            QuizGenerateRequest(
                source="prompt",
                prompt="Segurança",
                questionType="multiple_choice",
                count=2,
            ),
            user={"id": "author-1", "companyId": "tenant-1"},
        )

    assert exc_info.value.status_code == 503
    assert "OPENAI_API_KEY" in exc_info.value.detail


@pytest.mark.asyncio
async def test_quiz_rejects_invalid_answer_structure(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    FakeLlmChat.response = """{"questions": [{
      "type": "multiple_choice",
      "text": "Questão inválida",
      "alternatives": [
        {"text": "A", "isCorrect": true},
        {"text": "B", "isCorrect": true},
        {"text": "C", "isCorrect": false},
        {"text": "D", "isCorrect": false}
      ]
    }]}"""

    with pytest.raises(HTTPException) as exc_info:
        await questions.generate_questions_with_ai(
            QuizGenerateRequest(
                source="prompt",
                prompt="Segurança",
                questionType="multiple_choice",
                count=1,
            ),
            user={"id": "author-1", "companyId": "tenant-1"},
        )

    assert exc_info.value.status_code == 422
    assert "formato incompleto" in exc_info.value.detail


@pytest.mark.asyncio
async def test_quiz_maps_openai_quota_error(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    FakeLlmChat.error = RuntimeError("insufficient_quota: billing limit")

    with pytest.raises(HTTPException) as exc_info:
        await questions.generate_questions_with_ai(
            QuizGenerateRequest(
                source="prompt",
                prompt="Segurança",
                questionType="multiple_choice",
                count=2,
            ),
            user={"id": "author-1", "companyId": "tenant-1"},
        )

    assert exc_info.value.status_code == 503
    assert "saldo ou limite" in exc_info.value.detail
