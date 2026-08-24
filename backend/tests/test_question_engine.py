from services.question_engine import QuestionEngine, normalize_question, quiz_to_game_row
from services.ai_agent import _build_game_fallback_html


def test_portuguese_excel_columns_are_normalized_for_all_games():
    question = normalize_question({
        "ID": "MAT-001", "Série": "8º ano", "Disciplina": "Matemática",
        "Tema": "Porcentagem", "Nível de dificuldade": "Médio",
        "Pergunta": "Quanto é 20% de 100?", "Alternativa A": "10",
        "Alternativa B": "20", "Alternativa C": "30", "Alternativa D": "40",
        "Resposta correta": "B", "Explicação": "Vinte por cento de 100 é 20.",
    }, "company_test", "admin_test")
    assert question["companyId"] == "company_test"
    assert question["externalId"] == "MAT-001"
    assert question["difficulty"] == "medio"
    assert len(question["alternatives"]) == 4
    assert QuestionEngine.validate_answer(question, "B")


def test_question_engine_filters_without_coupling_to_game_mechanics():
    questions = [
        {"id": "1", "topic": "Frações", "difficulty": "facil", "correctAnswer": "A"},
        {"id": "2", "topic": "Frações", "difficulty": "dificil", "correctAnswer": "B"},
        {"id": "3", "topic": "Geometria", "difficulty": "medio", "correctAnswer": "C"},
    ]
    engine = QuestionEngine(questions)
    assert len(engine.get_questions_by_topic("frações")) == 2
    assert engine.get_questions_by_difficulty("dificil")[0]["id"] == "2"
    assert engine.get_question("3")["topic"] == "Geometria"


def test_imported_questions_are_embedded_in_offline_game_snapshot():
    bank = [{
        "id": "gq_1", "topic": "Segurança", "difficulty": "facil",
        "question": "Qual equipamento protege a cabeça?",
        "alternatives": [
            {"id": "A", "text": "Capacete"}, {"id": "B", "text": "Luva"},
            {"id": "C", "text": "Bota"}, {"id": "D", "text": "Colete"},
        ],
        "correctAnswer": "A", "explanation": "O capacete protege a cabeça.",
    }]
    output = _build_game_fallback_html({"title": "Segurança no Trabalho"}, bank)
    assert "Qual equipamento protege a cabeça?" in output
    assert "O capacete protege a cabeça." in output
    assert "QuestionEngine" in output


def test_quiz_bank_question_is_converted_for_educational_games():
    quiz = {
        "id": "quiz-123",
        "projectId": "project-1",
        "text": "Qual conduta protege os dados?",
        "alternatives": [
            {"id": "alt-a", "text": "Compartilhar a senha", "isCorrect": False},
            {"id": "alt-b", "text": "Usar autenticação multifator", "isCorrect": True},
        ],
        "explanation": "A autenticação multifator adiciona uma camada de segurança.",
        "tags": ["Segurança da Informação"],
    }
    row = quiz_to_game_row(quiz, "Curso de Segurança")
    game_question = normalize_question(row, "company-test", "admin-test")
    assert game_question["question"] == quiz["text"]
    assert game_question["correctAnswer"] == "alt-b"
    assert game_question["topic"] == "Segurança da Informação"
    assert QuestionEngine.validate_answer(game_question, "alt-b")
