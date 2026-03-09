"""Quiz questions CRUD, generation and submission routes"""
from fastapi import APIRouter, HTTPException, UploadFile, File
from typing import List, Optional
import uuid
import os
import json
import logging
import aiofiles

from routes.deps import db, now_utc, serialize_doc, UPLOADS_DIR
from models import (
    QuizQuestion, QuizQuestionCreate, QuizQuestionUpdate, QuizAlternative,
    QuizConfig, QuizAttempt, QuizGenerateRequest, QuizSubmitRequest
)

logger = logging.getLogger("server")

router = APIRouter(tags=["Questions"])


@router.get("/questions")
async def list_questions(project_id: Optional[str] = None):
    query = {"projectId": project_id} if project_id else {}
    docs = await db.questions.find(query, {"_id": 0}).to_list(1000)
    return docs


@router.get("/questions/{question_id}")
async def get_question(question_id: str):
    doc = await db.questions.find_one({"id": question_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Question not found")
    return doc


@router.post("/questions")
async def create_question(data: QuizQuestionCreate):
    from models import generate_id
    q = {
        "id": generate_id(),
        "projectId": data.projectId,
        "slideId": data.slideId,
        "type": data.type,
        "questionText": data.questionText,
        "alternatives": [a.model_dump() for a in data.alternatives] if data.alternatives else [],
        "correctAnswer": data.correctAnswer,
        "explanation": data.explanation or "",
        "points": data.points,
        "order": data.order,
        "createdAt": now_utc().isoformat(),
    }
    await db.questions.insert_one(q)
    q.pop('_id', None)
    return q


@router.put("/questions/{question_id}")
async def update_question(question_id: str, data: QuizQuestionUpdate):
    existing = await db.questions.find_one({"id": question_id})
    if not existing:
        raise HTTPException(404, "Question not found")
    update = data.model_dump(exclude_unset=True)
    if "alternatives" in update and update["alternatives"]:
        update["alternatives"] = [a if isinstance(a, dict) else a.model_dump() for a in update["alternatives"]]
    update["updatedAt"] = now_utc().isoformat()
    await db.questions.update_one({"id": question_id}, {"$set": update})
    doc = await db.questions.find_one({"id": question_id}, {"_id": 0})
    return doc


@router.delete("/questions/{question_id}")
async def delete_question(question_id: str):
    result = await db.questions.delete_one({"id": question_id})
    if result.deleted_count == 0:
        raise HTTPException(404, "Question not found")
    return {"status": "deleted"}


@router.post("/questions/generate")
async def generate_questions_with_ai(request: QuizGenerateRequest):
    emergent_key = os.environ.get('EMERGENT_LLM_KEY')
    if not emergent_key:
        raise HTTPException(status_code=500, detail="AI API key not configured")
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        if request.questionType == "true_false":
            type_instruction = """Gere APENAS questoes de Verdadeiro ou Falso. Cada questao DEVE ter type "true_false" e exatamente 2 alternativas: "Verdadeiro" e "Falso"."""
        elif request.questionType == "multiple_choice":
            type_instruction = """Gere APENAS questoes de Multipla Escolha. Cada questao deve ter exatamente 4 alternativas, sendo apenas 1 correta."""
        else:
            type_instruction = """Gere uma mistura de questoes de Multipla Escolha e Verdadeiro/Falso."""
        system_message = f"""Voce e um especialista em criar questoes de quiz educacionais.
{type_instruction}
REGRAS: 1. SEMPRE responda em portugues brasileiro 2. Crie questoes claras e objetivas 3. Inclua explicacao para cada resposta correta
FORMATO DE RESPOSTA (JSON valido):
{{"questions": [
  {{"type": "multiple_choice", "text": "Qual e a capital?", "alternatives": [{{"text": "A", "isCorrect": false}}, {{"text": "B", "isCorrect": true}}, {{"text": "C", "isCorrect": false}}, {{"text": "D", "isCorrect": false}}], "explanation": "..."}},
  {{"type": "true_false", "text": "O sol e uma estrela.", "alternatives": [{{"text": "Verdadeiro", "isCorrect": true}}, {{"text": "Falso", "isCorrect": false}}], "explanation": "..."}}
]}}
IMPORTANTE: Questoes true_false DEVEM SEMPRE ter o campo "alternatives" com "Verdadeiro" e "Falso".
RESPONDA APENAS COM O JSON, SEM TEXTO ADICIONAL."""
        chat = LlmChat(api_key=emergent_key, session_id=f"quiz-gen-{uuid.uuid4()}", system_message=system_message).with_model("openai", "gpt-4o")
        if request.source == "document" and request.documentContent:
            full_prompt = f"Com base no seguinte conteudo, gere {request.count} questoes:\n\n{request.documentContent}"
        else:
            full_prompt = f"Gere {request.count} questoes sobre: {request.prompt}"
            if request.context:
                full_prompt += f"\n\nContexto: {request.context}"
        response = await chat.send_message(UserMessage(text=full_prompt))
        cleaned_response = response.strip()
        if cleaned_response.startswith("```"):
            cleaned_response = cleaned_response.split("```")[1]
            if cleaned_response.startswith("json"):
                cleaned_response = cleaned_response[4:]
        if cleaned_response.endswith("```"):
            cleaned_response = cleaned_response[:-3]
        parsed = json.loads(cleaned_response.strip())
        questions_data = parsed.get("questions", [])
        saved_questions = []
        for q_data in questions_data:
            alternatives = []
            q_type = q_data.get("type", "multiple_choice")
            # Force correct type when user explicitly requested true_false
            if request.questionType == "true_false":
                q_type = "true_false"
            for alt in q_data.get("alternatives", []):
                alternatives.append(QuizAlternative(text=alt.get("text", ""), isCorrect=alt.get("isCorrect", False)).model_dump())
            # Fallback: ensure true_false always has Verdadeiro/Falso alternatives
            if q_type == "true_false" and len(alternatives) < 2:
                # Try to detect correct answer from the question context
                correct_answer = q_data.get("answer", q_data.get("correct", ""))
                is_true = str(correct_answer).lower() in ("true", "verdadeiro", "v")
                alternatives = [
                    QuizAlternative(text="Verdadeiro", isCorrect=is_true).model_dump(),
                    QuizAlternative(text="Falso", isCorrect=not is_true).model_dump(),
                ]
            question = QuizQuestion(projectId=request.projectId, type=q_type, text=q_data.get("text", ""), alternatives=alternatives, explanation=q_data.get("explanation"), tags=["ai-generated"])
            question_dict = question.model_dump()
            question_dict['createdAt'] = question.createdAt.isoformat()
            question_dict['updatedAt'] = question.updatedAt.isoformat()
            await db.questions.insert_one(question_dict)
            saved_questions.append(serialize_doc(question_dict))
        return {"success": True, "questions": saved_questions, "count": len(saved_questions)}
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="AI returned invalid format. Please try again.")
    except ImportError:
        raise HTTPException(status_code=500, detail="AI integration library not available")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Quiz generation error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate questions: {str(e)}")


@router.post("/questions/parse-doc")
async def parse_doc_file(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(('.doc', '.docx')):
        raise HTTPException(status_code=400, detail="Only .doc and .docx files are accepted")
    try:
        from docx import Document
        content = await file.read()
        temp_path = UPLOADS_DIR / f"temp_{uuid.uuid4()}_{file.filename}"
        async with aiofiles.open(temp_path, 'wb') as f:
            await f.write(content)
        doc = Document(str(temp_path))
        full_text = []
        for para in doc.paragraphs:
            if para.text.strip():
                full_text.append(para.text.strip())
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        full_text.append(cell.text.strip())
        os.remove(temp_path)
        extracted_text = "\n\n".join(full_text)
        return {"success": True, "filename": file.filename, "text": extracted_text, "wordCount": len(extracted_text.split())}
    except ImportError:
        raise HTTPException(status_code=500, detail="python-docx library not installed")
    except Exception as e:
        logger.error(f"Doc parsing error: {e}")
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.remove(temp_path)
        raise HTTPException(status_code=500, detail=f"Failed to parse document: {str(e)}")


@router.post("/quiz/submit")
async def submit_quiz(request: QuizSubmitRequest):
    question_ids = [a["questionId"] for a in request.answers]
    questions = await db.questions.find({"id": {"$in": question_ids}}, {"_id": 0}).to_list(100)
    questions_map = {q["id"]: q for q in questions}
    total_points = 0
    earned_points = 0
    results = []
    for answer in request.answers:
        question = questions_map.get(answer["questionId"])
        if not question:
            continue
        total_points += question.get("points", 1)
        correct_alt = None
        selected_alt = None
        for alt in question.get("alternatives", []):
            if alt.get("isCorrect"):
                correct_alt = alt
            if alt.get("id") == answer.get("selectedAlternativeId"):
                selected_alt = alt
        is_correct = selected_alt and selected_alt.get("isCorrect", False)
        if is_correct:
            earned_points += question.get("points", 1)
        results.append({
            "questionId": answer["questionId"], "questionText": question.get("text"),
            "selectedAlternativeId": answer.get("selectedAlternativeId"),
            "selectedText": selected_alt.get("text") if selected_alt else None,
            "correctAlternativeId": correct_alt.get("id") if correct_alt else None,
            "correctText": correct_alt.get("text") if correct_alt else None,
            "isCorrect": is_correct, "explanation": question.get("explanation")
        })
    percentage = (earned_points / total_points * 100) if total_points > 0 else 0
    final_score = round(percentage / 10, 1)
    passed = percentage >= 60
    attempt = QuizAttempt(quizId=request.quizId, projectId="", answers=results, score=final_score, percentage=round(percentage, 1), passed=passed, completedAt=now_utc())
    attempt_dict = attempt.model_dump()
    attempt_dict['createdAt'] = attempt.createdAt.isoformat()
    attempt_dict['completedAt'] = attempt.completedAt.isoformat() if attempt.completedAt else None
    await db.quiz_attempts.insert_one(attempt_dict)
    return {"success": True, "attemptId": attempt.id, "score": final_score, "percentage": round(percentage, 1), "passed": passed, "totalQuestions": len(results), "correctAnswers": sum(1 for r in results if r["isCorrect"]), "results": results}


@router.get("/quiz/attempts/{project_id}")
async def get_quiz_attempts(project_id: str, quiz_id: Optional[str] = None):
    query = {"projectId": project_id}
    if quiz_id:
        query["quizId"] = quiz_id
    attempts = await db.quiz_attempts.find(query, {"_id": 0}).sort("createdAt", -1).to_list(100)
    return attempts
