import copy
import json
import re
from services.agent_quality import repair_html, quality_plan, prepare_new_course, alternative_text, explanation_text
from services.resource_layouts import render_layout


def test_copy_edits_do_not_touch_scripts_or_notes():
    model = {'text': 'Sonegar metas realistas', 'rules': [1, 2]}
    source = '<html><body><h3>Subtítulo da Seção</h3><strong>Sonegar metas realistas</strong><script id="model">'+json.dumps(model)+'</script></body></html>'
    fixed = repair_html(source)
    assert '<h3>' not in fixed
    assert '<strong>Definir metas realistas</strong>' in fixed
    assert json.dumps(model) in fixed
    assert repair_html(fixed) == fixed


def test_card_content_and_interaction_preserved():
    data = {'kind': 'cards', 'title': 'Qualquer tema', 'items': [
        {'front': 'Questão '+str(i), 'back': 'Resposta completa '+str(i)} for i in range(9)]}
    original = render_layout(data)
    fixed = repair_html(original)
    pattern = r'<script id="resource-layout-data" type="application/json">([\s\S]*?)</script>'
    assert re.search(pattern, original)[1] == re.search(pattern, fixed)[1]
    assert 'Math.min(3,Math.floor((innerWidth*.92)/410))' in fixed
    assert "face.onclick" in fixed and "known.add(i)" in fixed and "reviewOnly" in fixed
    assert repair_html(fixed) == fixed


def test_only_course_html_is_patched_preserving_19_slides_and_6_questions():
    project = {'id': 'only-this-project', 'course': {'slides': [
        {'id': str(i), 'notes': 'author note', 'elements': [{'id': 'e'+str(i), 'type': 'html',
          'htmlContent': '<body><h3>Subtítulo da Seção</h3><p>Conteúdo original</p></body>',
          'assessmentConfig': {'questions': [1, 2]}, 'quizConfig': {'questionIds': ['q1']}}]} for i in range(19)],
        'questions': [{'id': 'q'+str(i)} for i in range(6)]}, 'other': 'preserve'}
    before = copy.deepcopy(project)
    patches, report = quality_plan(project)
    assert len(report) == 19
    assert all(re.fullmatch(r'course\.slides\.\d+\.elements\.0\.htmlContent', p) for p in patches)
    assert project == before


def test_image_fallback_only_reuses_course_assets_and_retains_original():
    source = '<body><img id="source" alt="dado original" src="invented.jpg"><script>function flip(){}</script></body>'
    fixed = repair_html(source, '/api/projects/same/assets/existing.png')
    assert 'data-quality-original-src="invented.jpg"' in fixed and 'id="source"' in fixed and 'function flip(){}' in fixed
    assert "addEventListener('load'" in fixed and "addEventListener('error'" not in fixed
    assert 'https://example.invalid' not in repair_html(source)
    assert repair_html(fixed, '/api/projects/same/assets/existing.png') == fixed


def test_options_and_feedback_normalized_without_changing_grading():
    questions = [{'id': 'q1', 'text': 'Qual?', 'alternatives': [
        {'id': 'a', 'text': 'B) Resposta', 'isCorrect': True}],
        'explanation': 'A resposta correta é B porque explica o conceito.', 'points': 2}]
    before = copy.deepcopy(questions)
    slides = [{'id': 's', 'elements': []}]
    out, clean = prepare_new_course(slides, questions)
    assert clean[0]['alternatives'][0] == {'id': 'a', 'text': 'Resposta', 'isCorrect': True}
    assert clean[0]['explanation'] == 'Justificativa: explica o conceito.'
    assert questions == before and out == slides
    assert alternative_text('A vitamina é importante') == 'A vitamina é importante'
    assert explanation_text('A resposta inclui duas partes') == 'A resposta inclui duas partes'


def test_route_authorizes_backs_up_and_updates_only_target_course_html():
    import ast
    import asyncio
    from pathlib import Path
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, patch
    from datetime import datetime, timezone
    project = {'id': 'course-a', 'updatedAt': 'revision', 'course': {'slides': [
        {'id': str(i), 'notes': 'preserved', 'elements': [{'id': 'e', 'type': 'html',
        'htmlContent': '<body><h3>Subtítulo da Seção</h3><p>Explicação real</p></body>',
        'quizConfig': {'questionIds': ['q1', 'q2'], 'shuffleAlternatives': True}}]} for i in range(19)]}}
    before = copy.deepcopy(project)
    from services.agent_quality import fingerprint
    collection = SimpleNamespace(find_one=AsyncMock(return_value=project),
                                 update_one=AsyncMock(return_value=SimpleNamespace(matched_count=1)))
    authorized = AsyncMock()
    scope = {'Depends': lambda _: None, 'require_auth': None, 'Request': object,
             'load_authorized_project': authorized, 'db': SimpleNamespace(projects=collection),
             'now_utc': lambda: datetime.now(timezone.utc)}
    class HttpError(Exception):
        def __init__(self, code, detail): self.status_code = code
    scope['HTTPException'] = HttpError
    path = Path(__file__).resolve().parents[1] / 'routes/projects_crud.py'
    node = next(n for n in ast.parse(path.read_text(encoding='utf-8')).body
                if isinstance(n, ast.AsyncFunctionDef) and n.name == 'apply_quality_review')
    node.decorator_list = []
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), scope)
    request = SimpleNamespace(json=AsyncMock(return_value={'fingerprint': fingerprint(project)}))
    with patch('services.layout_recovery.backup_layout_source', new=AsyncMock(return_value='safe-backup')) as backup:
        result = asyncio.run(scope['apply_quality_review']('course-a', request, {'user_id': 'author'}))
        assert result['backupId'] == 'safe-backup'
        backup.assert_awaited_once()
    authorized.assert_awaited_once_with('course-a', {'user_id': 'author'})
    guard, update = collection.update_one.call_args.args
    assert guard == {'id': 'course-a', 'course': project['course'], 'updatedAt': 'revision'}
    assert all(k == 'updatedAt' or re.fullmatch(r'course\.slides\.\d+\.elements\.0\.htmlContent', k) for k in update['$set'])
    assert project == before
    collection.update_one.reset_mock()
    request.json.return_value = {'fingerprint': 'stale'}
    import pytest
    with pytest.raises(HttpError):
        asyncio.run(scope['apply_quality_review']('course-a', request, {'user_id': 'author'}))
    collection.update_one.assert_not_awaited()
