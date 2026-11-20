import ast
import asyncio
import copy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from services.simulator_legend import repair_legend, legend_rows, MARKER
from services.component_authoring import stored_model


def sample():
    return {'title': 'Matriz', 'actions': [{'id': 'advance', 'feedback': 'ok'}],
            'visual': {'illustrations': [{'src': 'data:image/png;base64,UNCHANGED'}], 'nodes': [
                {'id': 'root', 'type': 'group'},
                {'id': 'legenda_matriz', 'type': 'group', 'parent': 'root'},
                {'id': 'title', 'type': 'text', 'parent': 'legenda_matriz', 'attrs': {'text': 'Legenda:'}},
                {'id': 'item', 'type': 'text', 'parent': 'legenda_matriz', 'attrs': {'text': '- Atividade Crítica', 'fill': '#FFCDD2'}}]}}


def html(model=None):
    return '<body><script id="scormify-simulator-plan">' + json.dumps(model or sample()).replace('<', '\\u003c') + '</script></body>'


def test_only_appends_presentation_and_is_idempotent():
    original = html(); result = repair_legend(original)['html']
    assert result.split('<script id="' + MARKER)[0] == original[:-7]
    assert stored_model(result) == stored_model(original)
    assert repair_legend(result) == {'html': result, 'changed': False}
    assert 'text.textContent=row.text' in result
    assert 'font:16px/1.4' in result
    assert 'background:#fff;color:#10243b' in result


@pytest.mark.parametrize('change', ['states', 'bindings', 'action', 'visibleWhen', 'ancestor', 'template', 'motion'])
def test_dynamic_legend_refused(change):
    model = sample(); group = model['visual']['nodes'][1]
    if change == 'motion':
        model['visual']['motions'] = [{'node': 'root', 'kind': 'rotate'}]
    elif change == 'ancestor':
        model['visual']['nodes'][0]['visibleWhen'] = False
    elif change == 'template':
        model['visual']['nodes'][-1]['attrs']['text'] = '{state}'
    else:
        group[change] = False if change == 'visibleWhen' else ['dynamic']
    with pytest.raises(ValueError): repair_legend(html(model))


def test_text_never_interpreted_as_markup():
    model = sample(); model['visual']['nodes'][-1]['attrs']['text'] = '</script><img src=x onerror=alert(1)>'
    result = repair_legend(html(model))
    # Test payload of appended script only; pre-existing content is never rewritten.
    appended = result['html'].split('<script id="' + MARKER)[1]
    assert '<img' not in appended
    assert '\\u003c' in appended


class HttpError(Exception):
    def __init__(self, status_code, detail):
        self.status_code, self.detail = status_code, detail


def route_scope(collection):
    from datetime import datetime, timezone
    scope = dict(asyncio=asyncio, HTTPException=HttpError, Depends=lambda _: None, require_auth=None,
                 db=SimpleNamespace(agent_sessions=collection), datetime=datetime, timezone=timezone)
    path = Path(__file__).resolve().parents[1] / 'routes/html_generation_jobs.py'
    for node in ast.parse(path.read_text(encoding='utf-8')).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in {'_owner', 'save_legend'}:
            node.decorator_list = []
            exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), scope)
    return scope


def test_only_one_element_written_among_120_slides():
    source = html()
    slides = [{'elements': [{'type': 'html', 'htmlContent': source}], 'notes': 'preserve'} for _ in range(120)]
    session = {'storyboard': {'slides': slides}, 'documentExtraction': {'images': ['capture'] * 11}}
    before = copy.deepcopy(session)
    collection = SimpleNamespace(find_one=AsyncMock(return_value=session),
                                 update_one=AsyncMock(return_value=SimpleNamespace(modified_count=1)))
    body = SimpleNamespace(sourceHtml=source, slideIndex=91, elementIndex=0)
    asyncio.run(route_scope(collection)['save_legend']('draft', body, {'user_id': 'owner'}))
    query, update = collection.update_one.call_args.args
    path = 'storyboard.slides.91.elements.0.htmlContent'
    assert query == {'id': 'draft', 'userId': 'owner', path: source}
    assert set(update['$set']) == {path, 'updatedAt'}
    assert stored_model(update['$set'][path]) == stored_model(source)
    assert session == before


@pytest.mark.parametrize('case,status', [('owner', 404), ('stale', 409), ('concurrent', 409)])
def test_ownership_and_concurrent_edits_protected(case, status):
    source = html(); session = {'storyboard': {'slides': [{'elements': [{'type': 'html', 'htmlContent': source}]}]}}
    collection = SimpleNamespace(find_one=AsyncMock(return_value=session),
                                 update_one=AsyncMock(return_value=SimpleNamespace(modified_count=1)))
    body = SimpleNamespace(sourceHtml=source, slideIndex=0, elementIndex=0)
    if case == 'owner': collection.find_one.return_value = None
    if case == 'stale': body.sourceHtml += ' '
    if case == 'concurrent':
        collection.update_one.return_value.modified_count = 0
        collection.find_one.side_effect = [session, None]
    with pytest.raises(HttpError) as err:
        asyncio.run(route_scope(collection)['save_legend']('draft', body, {'user_id': 'owner'}))
    assert err.value.status_code == status
    if case != 'concurrent': collection.update_one.assert_not_awaited()
