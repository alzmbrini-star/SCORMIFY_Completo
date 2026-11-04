"""Offline tests: no HeyGen calls, no paid model generations."""
import copy
import json
import shutil
import subprocess
from pathlib import Path
import pytest
from services.video_quiz import build_video_quiz, normalize_video_quiz


def sample():
    return dict(src='https://example.org/avatar.mp4', title='Avatar', checkpoints=[dict(
        at=10, question='Qual é a resposta?', options=['Uma', 'Duas'], correctIndex=1,
        explanation='A resposta é duas, conforme a fala.', maxAttempts=3)])


def test_script_data_is_escaped_and_no_external_runtime():
    data = sample()
    data['checkpoints'][0]['question'] = '</script><img src=x onerror=alert(1)>'
    config, html = build_video_quiz(data)
    snapshot = html.split('<script id="video-quiz-data" type="application/json">')[1].split('</script>')[0]
    assert json.loads(snapshot)['checkpoints'][0]['question'] == data['checkpoints'][0]['question']
    assert '<img src=x' not in html
    assert 'script src=' not in html
    assert len(config['key']) == 20


@pytest.mark.parametrize('patch', [dict(at=float('nan')), dict(at=-1), dict(at=True),
    dict(options=['', 'B']), dict(correctIndex=5), dict(maxAttempts=0),
    dict(explanation=''), dict(relative=True, at=1), dict(maxAttempts=11)])
def test_reject_invalid_question(patch):
    data = sample(); data['checkpoints'][0].update(patch)
    with pytest.raises(ValueError): normalize_video_quiz(data)


@pytest.mark.parametrize('source', ['javascript:alert(1)', '//example.com/video',
    'https://youtu.be/abc', 'https://iframe.mediadelivery.net/embed/123/abc',
    '<iframe src="https://example.org">', 'data:text/html,hi'])
def test_reject_non_video_sources(source):
    data = sample(); data['src'] = source
    with pytest.raises(ValueError): normalize_video_quiz(data)


def test_sort_and_revision_key():
    data = sample(); data['checkpoints'].append(dict(data['checkpoints'][0], at=5))
    normalized = normalize_video_quiz(data)
    assert [c['at'] for c in normalized['checkpoints']] == [5, 10]
    modified = copy.deepcopy(data); modified['checkpoints'][0]['explanation'] += '!'
    assert normalize_video_quiz(modified)['key'] != normalized['key']
    data['checkpoints'][1]['at'] = 10
    with pytest.raises(ValueError): normalize_video_quiz(data)


def test_export_embeds_project_video(tmp_path):
    from services.assessment_assets import inline_assessment_assets
    data = sample(); data['src'] = '/api/projects/project-a/assets/avatar.mp4'
    _, html = build_video_quiz(data)
    (tmp_path / 'avatar.mp4').write_bytes(b'video fixture')
    exported = inline_assessment_assets(html, str(tmp_path))
    assert 'data:video/mp4;base64,' in exported
    assert '/api/projects/project-a/assets/avatar.mp4' not in exported


def test_missing_export_video_does_not_silently_break(tmp_path, monkeypatch):
    from services.assessment_assets import inline_assessment_assets
    monkeypatch.delenv('MONGO_URL', raising=False)
    data = sample(); data['src'] = '/api/projects/project-a/assets/missing.mp4'
    _, html = build_video_quiz(data)
    with pytest.raises(ValueError): inline_assessment_assets(html, str(tmp_path))


def test_runtime_behaviors():
    root = Path(__file__).resolve().parents[2]
    node = shutil.which('node')
    assert node, 'Node required for runtime test'
    result = subprocess.run([node, str(root / 'tests/video-quiz-runtime.cjs')],
                            input=build_video_quiz(sample())[1], text=True,
                            encoding='utf-8', capture_output=True, cwd=root)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'runtime checks passed' in result.stdout


def test_single_page_connects_opaque_frame_resume_and_completion(tmp_path):
    from services.single_page_exporter import _render_html_element_inner
    config, document = build_video_quiz(sample())
    rendered = _render_html_element_inner(dict(type='html', height=650, htmlContent=document, videoQuizConfig=config), 'p1', str(tmp_path), '', 0, 0)
    assert f'data-video-quiz-key="{config["key"]}"' in rendered
    assert 'display:none' in rendered.split('sp-iframe-done')[1]


def test_agent_question_planner_uses_only_supplied_script(monkeypatch):
    import asyncio
    import sys
    import types
    from services.video_quiz import plan_video_questions
    recorded = []
    class Chat:
        async def send_message(self, message):
            recorded.append(message.text)
            return json.dumps({'checkpoints': [sample()['checkpoints'][0]] * 2})
    stub = types.SimpleNamespace(_new_chat=lambda _: Chat(), _extract_json=json.loads,
                                 UserMessage=lambda **kwargs: types.SimpleNamespace(**kwargs))
    monkeypatch.setitem(sys.modules, 'services.ai_agent', stub)
    rows = asyncio.run(plan_video_questions('O avatar explica o funcionamento das válvulas, sem falar de outros temas.'))
    assert [r['at'] for r in rows] == [1/3, 2/3]
    assert all(r['relative'] and r['maxAttempts'] == 3 for r in rows)
    assert 'válvulas' in recorded[0]


def test_agent_background_callback_keeps_questions_and_supplies_video():
    import ast
    import asyncio
    from unittest.mock import AsyncMock
    root = Path(__file__).resolve().parents[1]
    tree = ast.parse((root / 'routes/agent.py').read_text(encoding='utf-8'))
    function = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == '_update_slide_with_heygen_video')
    element = dict(htmlContent='<div data-heygen-slide="s1">Aguarde</div>', videoQuizPending=dict(title='Vídeo', checkpoints=sample()['checkpoints']))
    projects = type('Projects', (), {'find_one': AsyncMock(return_value={'course': {'slides': [{'id': 's1', 'elements': [element]}]}}), 'update_one': AsyncMock()})()
    namespace = {'db': type('DB', (), {'projects': projects})()}
    exec(compile(ast.Module(body=[function], type_ignores=[]), 'callback', 'exec'), namespace)
    asyncio.run(namespace['_update_slide_with_heygen_video']('p1', 's1', sample()['src']))
    update = projects.update_one.call_args.args[1]
    assert update['$set']['course.slides.0.elements.0.videoQuizConfig']['checkpoints'][0]['question'] == sample()['checkpoints'][0]['question']
    assert 'video-quiz-data' in update['$set']['course.slides.0.elements.0.htmlContent']


def test_configurations_do_not_share_resume_across_elements():
    data = sample(); data['instanceId'] = 'element-1'
    other = dict(data, instanceId='element-2')
    assert normalize_video_quiz(data)['key'] != normalize_video_quiz(other)['key']
