"""Shared, storage-agnostic question normalization for educational games."""
from __future__ import annotations

import json
import random
import re
import uuid
import io
import zipfile
from datetime import datetime, timezone
from typing import Any, Iterable
from xml.sax.saxutils import escape


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

GAME_QUESTION_TEMPLATE_HEADERS = [
    "ID", "Série", "Disciplina", "Tema", "Nível de dificuldade",
    "Pergunta", "Alternativa A", "Alternativa B", "Alternativa C",
    "Alternativa D", "Resposta correta", "Explicação", "Imagem", "Áudio", "Vídeo",
]


def build_question_template_xlsx() -> bytes:
    """Create a dependency-free Excel template accepted by the importer."""
    example = [
        "SEG-001", "Ensino Médio", "Segurança da Informação", "Senhas",
        "Médio", "Qual prática aumenta a segurança de uma conta?",
        "Compartilhar a senha", "Usar autenticação multifator",
        "Reutilizar a mesma senha", "Anotar a senha em local público", "B",
        "A autenticação multifator adiciona uma camada extra de proteção.", "", "", "",
    ]
    rows = [GAME_QUESTION_TEMPLATE_HEADERS, example]
    row_xml = []
    for row_index, values in enumerate(rows, start=1):
        cells = []
        for column_index, value in enumerate(values):
            number = column_index + 1
            letters = ""
            while number:
                number, remainder = divmod(number - 1, 26)
                letters = chr(65 + remainder) + letters
            style = ' s="1"' if row_index == 1 else ""
            cells.append(
                f'<c r="{letters}{row_index}" t="inlineStr"{style}>'
                f'<is><t>{escape(str(value))}</t></is></c>'
            )
        row_xml.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    sheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" '
        'activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
        '<cols><col min="1" max="5" width="22" customWidth="1"/>'
        '<col min="6" max="12" width="38" customWidth="1"/>'
        '<col min="13" max="15" width="24" customWidth="1"/></cols>'
        f'<sheetData>{"".join(row_xml)}</sheetData><autoFilter ref="A1:O2"/>'
        '</worksheet>'
    )
    files = {
        "[Content_Types].xml": '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
            '</Types>',
        "_rels/.rels": '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>',
        "xl/workbook.xml": '<?xml version="1.0" encoding="UTF-8"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Questões dos Jogos" sheetId="1" r:id="rId1"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels": '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
            '</Relationships>',
        "xl/styles.xml": '<?xml version="1.0" encoding="UTF-8"?>'
            '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font>'
            '<font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Calibri"/></font></fonts>'
            '<fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill>'
            '<fill><patternFill patternType="solid"><fgColor rgb="FF4F46E5"/><bgColor indexed="64"/></patternFill></fill></fills>'
            '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
            '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
            '<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
            '<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/></cellXfs>'
            '</styleSheet>',
        "xl/worksheets/sheet1.xml": sheet,
    }
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return output.getvalue()


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
    alternative_ids = {alt["id"].upper(): alt["id"] for alt in alternatives}
    if correct_id in alternative_ids:
        # Keep the source ID's exact spelling. Editor Quiz alternatives often
        # use UUID/lowercase IDs and exported games compare those stable IDs.
        correct_id = alternative_ids[correct_id]
    else:
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


def quiz_to_game_row(question: dict, project_title: str = "") -> dict:
    """Translate the Editor Quiz contract into the shared game contract."""
    alternatives = []
    correct_answer = str(question.get("correctAnswer") or "").strip()
    for index, alternative in enumerate(question.get("alternatives") or []):
        if isinstance(alternative, dict):
            alt_id = str(alternative.get("id") or chr(65 + index))
            alt_text = str(alternative.get("text") or alternative.get("texto") or "").strip()
            if alternative.get("isCorrect") is True and not correct_answer:
                correct_answer = alt_id
        else:
            alt_id, alt_text = chr(65 + index), str(alternative).strip()
        if alt_text:
            alternatives.append({"id": alt_id, "text": alt_text})
    tags = [str(tag).strip() for tag in (question.get("tags") or []) if str(tag).strip()]
    return {
        "id": question.get("id", ""),
        "disciplina": question.get("subject") or project_title or "Quiz",
        "tema": question.get("topic") or (tags[0] if tags else project_title) or "Geral",
        "dificuldade": question.get("difficulty") or "medio",
        "pergunta": question.get("text") or question.get("questionText") or "",
        "alternatives": alternatives,
        "resposta correta": correct_answer,
        "explicação": question.get("explanation") or "",
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
