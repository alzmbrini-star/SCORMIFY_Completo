import base64
import copy
import io
from unittest.mock import AsyncMock,Mock

import pytest
from fastapi import HTTPException
from services.slidekiln_cover import build_cover
from routes import slidekiln as route
from services import slidekiln as provider

PID='150826df-0a9a-4b16-acaa-d675b7fffbe9'
FILE='a'*32+'.sk.html'


def document():
    return '''<html><head><style>@font-face{font-family:'Used';src:url(data:font/woff2;base64,AA==)}@font-face{font-family:'Unused';src:url(data:font/woff2;base64,AAAA)}.slide{display:none}.txt{color:red;background:url(https://tracker.invalid/pixel)}</style><script>danger()</script></head><body><div id="stage" data-w="1280" data-h="720"><section class="slide active"><svg viewBox="0 0 1280 720"><rect width="1280" height="720"/></svg><span style="font-family:'Used'" onclick="bad()">Primeira capa</span><img src="data:image/png;base64,AAAA"><iframe src="https://external.invalid"></iframe><script>bad()</script><video src="data:video/mp4;base64,AAAA"></video></section><section class="slide"><p>Segundo slide não deve aparecer</p></section></div></body></html>'''


def test_passive_cover_contains_only_first_slide_fonts_and_images(tmp_path):
    path=tmp_path/FILE;path.write_text(document(),encoding='utf-8')
    result=build_cover(path)
    assert result['width']==1280 and result['height']==720
    html=result['html']
    assert 'Primeira capa' in html and 'data:image/png;base64,AAAA' in html
    assert 'font-family:\'Used\'' in html and 'Unused' not in html
    assert '<svg' in html and 'display:block!important' in html
    for forbidden in ('<script','<iframe','<video','onclick','tracker.invalid','external.invalid','Segundo slide'):
        assert forbidden not in html
    assert "script-src 'none'" in html and "connect-src 'none'" in html
    assert path.read_text(encoding='utf-8')==document()


def test_cover_reduces_large_image_without_changing_original(tmp_path):
    from PIL import Image
    image=Image.effect_noise((1800,1000),100).convert('RGBA')
    output=io.BytesIO();image.save(output,'PNG')
    uri='data:image/png;base64,'+base64.b64encode(output.getvalue()).decode()
    source=document().replace('data:image/png;base64,AAAA',uri)
    path=tmp_path/FILE;path.write_text(source,encoding='utf-8')
    result=build_cover(path)
    assert 'data:image/webp;base64,' in result['html'] and len(result['html'])<len(source)/3
    assert path.read_text(encoding='utf-8')==source


@pytest.mark.asyncio
async def test_old_and_future_imports_get_cached_cover_without_provider_or_course_writes(tmp_path,monkeypatch):
    project={'id':PID,'course':{'slides':[{'elements':[{'type':'html','source':'slidekiln','htmlContent':provider.module_html(PID,FILE)}]}]}}
    original=copy.deepcopy(project)
    monkeypatch.setattr(route,'load_authorized_project',AsyncMock(return_value=project))
    monkeypatch.setattr(route.deps,'PROJECTS_DIR',tmp_path)
    database=Mock();monkeypatch.setattr(route.deps,'db',database)
    restore=AsyncMock(return_value=(document().encode(),'text/html'))
    monkeypatch.setattr('services.asset_store.retrieve_asset_async',restore)
    submit=AsyncMock(side_effect=AssertionError('No conversions permitted'))
    monkeypatch.setattr(provider,'submit',submit)
    first=await route.course_cover(PID,{'role':'super_admin'})
    second=await route.course_cover(PID,{'role':'super_admin'})
    assert first==second and 'Primeira capa' in first['html']
    restore.assert_awaited_once();submit.assert_not_awaited()
    assert not database.mock_calls and project==original
    assert len(list((tmp_path/PID/'assets').glob('_sk-cover-*.json')))==1


@pytest.mark.asyncio
async def test_authorization_precedes_asset_access(tmp_path,monkeypatch):
    guard=AsyncMock(side_effect=HTTPException(404,'Project not found'))
    monkeypatch.setattr(route,'load_authorized_project',guard)
    restore=AsyncMock();monkeypatch.setattr('services.asset_store.retrieve_asset_async',restore)
    with pytest.raises(HTTPException):await route.course_cover(PID,{'companyId':'other'})
    restore.assert_not_awaited()


@pytest.mark.asyncio
async def test_cross_project_and_missing_modules_fail_closed(monkeypatch):
    for elements in ([],[{'type':'html','source':'slidekiln','htmlContent':provider.module_html('250826df-0a9a-4b16-acaa-d675b7fffbe9',FILE)}]):
        monkeypatch.setattr(route,'load_authorized_project',AsyncMock(return_value={'course':{'slides':[{'elements':elements}]}}))
        with pytest.raises(HTTPException) as exc:await route.course_cover(PID,{})
        assert exc.value.status_code==404
