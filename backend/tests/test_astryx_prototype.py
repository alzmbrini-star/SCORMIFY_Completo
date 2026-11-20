import copy
import base64
import re
import io
import json
import uuid
import zipfile
from unittest.mock import AsyncMock
from xml.etree import ElementTree as ET

import pytest
from pydantic import ValidationError
from services.astryx_prototype import AstryxContent, assets, creation_id, prototype_project, render_documents


def expand_embedded(text):
    return text + '\n' + '\n'.join(base64.b64decode(s).decode('utf-8') for s in re.findall(r'(?:__B64__:|data:text/html;(?:charset=utf-8;)?base64,)([A-Za-z0-9+/=]+)', text))


def test_real_astryx_static_components_and_license_are_embedded():
    documents = render_documents(AstryxContent())
    assert len(documents) == 3
    for document in documents:
        assert 'data-astryx-theme="neutral"' in document
        assert 'Copyright (c) 2026 Meta Platforms, Inc.' in document
        assert '@@CONTENT@@' not in document
        assert 'cdn.jsdelivr' not in document and 'esm.sh' not in document
        assert '@media(max-width:640px)' in document
        assert 'grid-template-columns:minmax(0,1fr)' in document
        assert 'object-fit:contain' in document
    assert 'astryx-card' in documents[0]
    assert 'astryx-button' in documents[2] and 'Tentar novamente' in documents[2]
    assert 'sem nota no LMS' in documents[2]


def test_text_and_feedback_cannot_escape_the_document():
    attack = '</script><img src=x onerror=alert(1)>'
    docs = render_documents(AstryxContent(title=attack, body=attack, feedback=attack, options=['<b>A</b>', 'B', 'C']))
    assert attack not in ''.join(docs)
    assert '&lt;/script&gt;' in docs[0]
    assert '\\u003c/script\\u003e' in docs[2]
    assert '&lt;b&gt;A&lt;/b&gt;' in docs[2]


@pytest.mark.parametrize('kwargs', [
    {'image': 'https://internal.example/secret'}, {'image': 'data:image/svg+xml;base64,PHN2Zz4='},
    {'image': 'data:image/png;base64,bm90IGFuIGltYWdl'}, {'title': '  '},
    {'options': ['a', 'a', 'b']}, {'options': ['a', 'b']}, {'correct': 3},
    {'accent': 'url(https://evil.example)'}])
def test_untrusted_content_is_rejected(kwargs):
    with pytest.raises(ValidationError):
        AstryxContent(**kwargs)


def test_original_data_is_not_touched_and_ids_cannot_target_existing_projects():
    data = AstryxContent()
    before = data.model_dump()
    old = {'course': {'slides': [{'id': 'old', 'elements': [{'type': 'quiz', 'questionIds': ['q1']}]}]}}
    preserved = copy.deepcopy(old)
    a, b = prototype_project(data), prototype_project(data)
    assert a['id'] != b['id']
    assert len(a['course']['slides']) == 3 and old == preserved and data.model_dump() == before
    token = uuid.uuid4()
    assert creation_id('alice', token) == creation_id('alice', token)
    assert creation_id('alice', token) != creation_id('bob', token)


@pytest.mark.asyncio
async def test_actual_html_and_scorm_exporters_preserve_three_documents(tmp_path):
    from services.html_exporter import generate_standalone_html
    from services.scorm_exporter import export_scorm_package
    from models import Project
    p = prototype_project(AstryxContent())
    before = copy.deepcopy(p)
    output = expand_embedded(await generate_standalone_html(p, str(tmp_path)))
    assert 'astryxPrototype' in output and 'Verificar resposta' in output
    assert assets()[1] in output and 'id="astryx-mobile-host"' in output
    archive = export_scorm_package(Project(**p), str(tmp_path), str(tmp_path))
    with zipfile.ZipFile(archive) as z:
        manifest = ET.fromstring(z.read('imsmanifest.xml'))
        resources = manifest.findall('.//{*}resource')
        assert resources and resources[0].attrib['href'].split('?', 1)[0] in z.namelist()
        bundle = expand_embedded(''.join(z.read(n).decode('utf-8', errors='replace') for n in z.namelist() if n.endswith(('.html', '.json', '.js'))))
        assert 'astryxPrototype' in bundle
        assert 'ax-confirm' in bundle and 'ax-reset' in bundle
        assert 'data:image/svg+xml;base64,' in bundle
        exported_course = json.loads(z.read('course.json'))
        assert len(exported_course['slides']) == 3
        for slide in exported_course['slides']:
            assert assets()[1] in slide['elements'][0]['htmlContent']
        assert 'id="astryx-mobile-host"' in z.read('index.html').decode()
    assert p == before


def test_mobile_host_is_exclusive_to_all_prototype_slides():
    from services.astryx_export import is_astryx_course, install_astryx_host
    original = '<html><head></head><body>Existing course</body></html>'
    assert install_astryx_host(original, False) == original
    assert not is_astryx_course({'slides': []})
    p = prototype_project(AstryxContent())
    assert is_astryx_course(p['course'])
    p['course']['slides'].append({'elements': [{'type': 'quiz'}]})
    assert not is_astryx_course(p['course'])


def test_single_page_preserves_the_responsive_document_and_scroll(tmp_path):
    from services.single_page_exporter import generate_single_page_html
    from services.scorm_single_page_exporter import export_single_page_scorm_package
    from models import Project
    p = prototype_project(AstryxContent())
    before = copy.deepcopy(p)
    output = expand_embedded(generate_single_page_html(p, str(tmp_path)))
    assert 'data-astryx-slide=' in output and 'ax-confirm' in output
    assert 'height:auto!important' in output
    archive = export_single_page_scorm_package(p, str(tmp_path), str(tmp_path))
    with zipfile.ZipFile(archive) as z:
        assert 'ax-confirm' in expand_embedded(z.read('index.html').decode())
        ET.fromstring(z.read('imsmanifest.xml'))
    assert p == before


def test_tutor_describes_opt_in_permissions_and_no_existing_course_changes():
    from services.creator_guide import GUIDE
    topic = next(t for t in GUIDE if t['id'] == 'astryx-prototype')
    text = ' '.join(topic['steps'])
    assert topic['action'] == 'astryx'
    for term in ['Ferramentas', 'sem nota', 'MIT', '2 MB', 'não altera', 'não consome']:
        # Credits phrased as "Não ... consome" rather than an invented charge.
        if term == 'não consome':
            assert 'consome créditos de IA' in text
        else:
            assert term.casefold() in text.casefold()


@pytest.mark.asyncio
async def test_routes_preview_has_no_db_writes_and_checks_editor_role(monkeypatch):
    from routes import projects_crud as routes
    from fastapi import HTTPException
    from types import SimpleNamespace
    database = SimpleNamespace(projects=SimpleNamespace(update_one=AsyncMock(), find_one=AsyncMock()))
    monkeypatch.setattr(routes, 'db', database)
    for role in ('student', 'aprovador'):
        with pytest.raises(HTTPException) as err:
            await routes.astryx_preview(AstryxContent(), {'user_id': 'x', 'role': role})
        assert err.value.status_code == 403
    p = await routes.astryx_preview(AstryxContent(), {'user_id': 'x', 'role': 'editor'})
    assert len(p['course']['slides']) == 3
    database.projects.update_one.assert_not_called()
    database.projects.find_one.assert_not_called()


@pytest.mark.asyncio
async def test_create_is_idempotent_insert_only_and_preserves_source_tenant(monkeypatch):
    from types import SimpleNamespace
    from routes import projects_crud as routes
    from fastapi import HTTPException
    stored = {}
    async def save(query, update, upsert=False):
        assert upsert and list(update) == ['$setOnInsert']
        assert query['_id'].startswith('astryx-prototype:')
        stored.setdefault(query['_id'], copy.deepcopy(update['$setOnInsert']))
    async def find(query, projection):
        return stored[query['_id']]
    monkeypatch.setattr(routes, 'db', SimpleNamespace(projects=SimpleNamespace(update_one=save, find_one=find)))
    monkeypatch.setattr(routes, 'resolve_company_id_for_creation', AsyncMock(return_value='own-tenant'))
    original = {'id': 'original', 'companyId': 'client-tenant', 'course': {'slides': [{'id': 'original-slide', 'elements': [{'type': 'quiz', 'questionIds': ['q1']}]}]}}
    before = copy.deepcopy(original)
    auth = AsyncMock(return_value=original)
    monkeypatch.setattr(routes, 'load_authorized_project', auth)
    request = routes.AstryxCreate(content=AstryxContent(), requestId=uuid.uuid4(), sourceProjectId='original')
    user = {'user_id': 'owner', 'role': 'super_admin'}
    a = await routes.astryx_create(request, user)
    b = await routes.astryx_create(request, user)
    assert a['projectId'] == b['projectId'] != 'original'
    assert len(stored) == 1 and original == before
    assert next(iter(stored.values()))['companyId'] == 'client-tenant'
    request.content.title = 'Different payload with same request'
    with pytest.raises(HTTPException) as err:
        await routes.astryx_create(request, user)
    assert err.value.status_code == 409 and len(stored) == 1
