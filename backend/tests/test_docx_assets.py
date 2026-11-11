import base64
import io
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from PIL import Image
from docx import Document
from services.docx_assets import extract_docx_source, save_source_images, copy_source_images, reference_elements
from services.source_coverage import ensure_coverage, source_sections
from services import ai_agent


def sample_docx():
    picture=io.BytesIO(); Image.new('RGB',(640,240),'blue').save(picture,format='PNG')
    doc=Document();doc.add_heading('Unidade 1 Preparação',1);doc.add_paragraph('Explicar os cuidados e os procedimentos do início do processo.')
    doc.add_picture(io.BytesIO(picture.getvalue()))
    doc.add_paragraph('Figura 1 Captura da preparação.')
    doc.add_heading('Unidade 2 Encerramento',1);doc.add_paragraph('Verificar o encerramento e registrar as evidências da execução.')
    doc.add_picture(io.BytesIO(picture.getvalue()))
    output=io.BytesIO();doc.save(output)
    return output.getvalue(),picture.getvalue()


def test_docx_preserves_exact_image_bytes_and_unit_association():
    raw, png=sample_docx(); text, images=extract_docx_source(raw)
    assert len(images)==2
    assert all(base64.b64decode(i['data'])==png for i in images)
    sections=source_sections(text)
    assert sections[0]['images']==[images[0]['filename']]
    assert sections[1]['images']==[images[1]['filename']]
    plan=ensure_coverage({'modules':[]},text)
    assert len([s for m in plan['modules'] for s in m['slides'] if s.get('sourceImageOnly')])==2
    assert ensure_coverage(plan,text)==plan
    assert all('[IMG:' not in i['text'] for s in sections for i in s['items'])


@pytest.mark.asyncio
async def test_images_are_durable_copied_not_moved_and_missing_asset_blocks():
    _,images=extract_docx_source(sample_docx()[0])
    assets=SimpleNamespace(update_one=AsyncMock(),find_one=AsyncMock(return_value={**images[0],'project_id':'source'}))
    db=SimpleNamespace(project_assets=assets)
    meta=await save_source_images(db,images,'owner','company')
    assert len(meta['images'])==2 and 'data' not in meta['images'][0]
    await copy_source_images(db,meta,'new-course')
    assert assets.update_one.call_count==4
    assert assets.update_one.call_args.args[1]['$set']['project_id']=='new-course'
    assets.find_one.return_value=None
    with pytest.raises(ValueError,match='captura original'): await copy_source_images(db,meta,'new-course')


def test_reference_layout_uses_contain_and_fits_slide_without_cropping():
    _,images=extract_docx_source(sample_docx()[0])
    elements=reference_elements({'sourceImage':images[0]['filename'],'title':'Tela original <segura>'},'new-course')
    image=next(e for e in elements if e['type']=='image')
    assert image['objectFit']=='contain'
    assert '/new-course/assets/docx_' in image['src']
    assert all(e['x']+e['width']<=1920 and e['y']+e['height']<=820 for e in elements)
    assert '&lt;segura&gt;' in elements[0]['content']


@pytest.mark.asyncio
async def test_screenshot_storyboard_and_course_do_not_call_image_ai(monkeypatch):
    _,images=extract_docx_source(sample_docx()[0])
    slide={'id':'screenshot','type':'content','sourceImageOnly':True,'sourceRequired':True,
           'sourceImage':images[0]['filename'],'title':'Preparação original','purpose':'Observar a captura.'}
    chat=AsyncMock(side_effect=AssertionError('No AI for an original screenshot'))
    monkeypatch.setattr(ai_agent,'_new_chat',chat)
    # No textual inventory: isolate the deterministic screenshot compilation.
    storyboard=await ai_agent.generate_storyboard('qa','Breve fonte.',{'modules':[{'title':'Unidade','slides':[slide]}]}, {})
    assert storyboard['slides'][0]['sourceImageOnly'] is True
    assert not chat.called
    result=await ai_agent.generate_course_from_storyboard('qa',storyboard,{'title':'Teste'},project_id='new-course')
    assert result['slides'][0]['sourceImageOnly'] is True
    assert any(e.get('sourceDocumentImage') for e in result['slides'][0]['elements'])
    assert result['heygenPending']==[]


def test_tutor_documents_original_images_and_reupload():
    from services.creator_guide import topics_for
    text=' '.join(next(t for t in topics_for({'role':'super_admin'}) if t['id']=='agent')['steps'])
    assert 'capturas incorporadas' in text and 'reenviados' in text
