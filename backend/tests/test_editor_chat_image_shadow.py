import asyncio
import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from fastapi import HTTPException
from routes.editor_chat import _apply_ops, editor_chat
from services.editor_shadow_chat import plan_image_shadow, shadow_configuration


def sample():
    return [
        {'id':'s1','title':'Aula','notes':'Preserve esta nota','backgroundImage':'background.png','elements':[
            {'id':'title','type':'text','content':'Título','style':{'fontSize':24}},
            {'id':'im1','type':'image','src':'original.png','x':12,'y':30,'width':400,'height':300,'animations':[{'effect':'fade'}],'style':{'opacity':.8}},
            {'id':'quiz','type':'quiz','quizConfig':{'questionIds':['q1'],'passingScore':70}},
            {'id':'html','type':'html','htmlContent':'<img src="internal.png">'}]},
        {'id':'s2','title':'Captura','notes':'Outra nota','elements':[
            {'id':'im2','type':'image','src':'screenshot.png','sourceDocumentImage':True},
            {'id':'im3','type':'image','src':'cutout.png'}]}]


@pytest.mark.parametrize('command,preset',[
    ('Aplicar sombra media em todas as imagens','medium'),
    ('Aplique sombra MÉDIA em todas as imagens','medium'),
    ('Coloque sombra suave em todas as imagens','soft'),
    ('Aplicar sombra forte em todo o curso','strong'),
    ('Remover sombra de todas as imagens','none')])
def test_explicit_bulk_commands_only_change_image_shadow(command,preset):
    slides=sample();before=copy.deepcopy(slides);plan=plan_image_shadow(command,slides)
    applied=_apply_ops(slides,plan['ops'])
    assert len(applied)==3
    for si,slide in enumerate(slides):
        assert slide['notes']==before[si]['notes']
        for ei,element in enumerate(slide['elements']):
            if element['type']=='image':
                assert element['imageShadow']['preset']==preset
                assert {k:v for k,v in element.items() if k!='imageShadow'}==before[si]['elements'][ei]
            else:assert element==before[si]['elements'][ei]
    assert slides[0]['backgroundImage']=='background.png'
    assert _apply_ops(slides,plan['ops'])==[]  # No duplicate changes/snapshot needed.


def test_scope_uses_current_slide_and_selected_image_identifiers():
    slides=sample()
    plan=plan_image_shadow('Aplicar sombra suave nas imagens do slide atual',slides,'s2','im2')
    assert plan['ops'][0]['scope']=='slide'
    assert len(_apply_ops(slides,plan['ops']))==2
    assert 'imageShadow' not in slides[0]['elements'][1]
    plan=plan_image_shadow('Remover sombra da imagem selecionada',slides,'s2','im2')
    assert len(_apply_ops(slides,plan['ops']))==1
    assert slides[1]['elements'][0]['imageShadow']['preset']=='none'
    assert slides[1]['elements'][1]['imageShadow']['preset']=='soft'
    plan=plan_image_shadow('Aplicar sombra forte nas imagens do slide 1',slides)
    assert len(_apply_ops(slides,plan['ops']))==1


@pytest.mark.parametrize('command',[
    'Aplicar sombra nas imagens','Aplicar sombra média nas imagens',
    'Aplicar sombra forte na imagem selecionada','Aplicar sombra suave no slide atual',
    'Aplicar sombra suave nas imagens dos slides 2 a 4',
    'Aplicar sombra media no slide 99','Não aplique sombra média em todas as imagens',
    'Aplicar sombra media em todas as imagens exceto a capa',
    'Aplicar sombra media na segunda imagem do slide 1',
    'Como aplicar sombra média em todas as imagens?'])
def test_ambiguous_missing_context_invalid_slide_and_help_never_mutate(command):
    slides=sample();before=copy.deepcopy(slides)
    plan=plan_image_shadow(command,slides)
    assert plan is not None and plan['ops']==[]
    assert slides==before


def test_custom_controls_preserve_existing_values_and_validate_before_mutation():
    old={'preset':'custom','mode':'frame','color':'#112233','x':3,'y':9,'opacity':32,'blur':18}
    assert shadow_configuration(old,{'color':'#445566'})=={**old,'color':'#445566'}
    plan=plan_image_shadow('Aplicar sombra media com cor #334155 e intensidade 35% e suavidade 20px e deslocamento horizontal -4px e vertical 8px em todas as imagens',sample())
    assert plan['ops'][0]['shadow']=={'preset':'medium','color':'#334155','opacity':35,'blur':20,'x':-4,'y':8}
    for patch in ({'opacity':99},{'blur':-1},{'color':'red;url(bad)'},{'src':'replacement.png'},{'preset':'unknown'}):
        slides=sample();before=copy.deepcopy(slides)
        assert _apply_ops(slides,[{'type':'set_image_shadow','scope':'course','shadow':patch}])==[]
        assert slides==before


def test_unrelated_commands_keep_existing_llm_path():
    assert plan_image_shadow('Mude o título do slide 3',sample()) is None
    assert plan_image_shadow('Ajustar sombra dos textos',sample()) is None


def setup_route(monkeypatch, matched=1, slides=None):
    import routes.editor_chat as route
    import routes.projects_common as common
    project={'id':'p','updatedAt':'version-before','course':{'slides':slides if slides is not None else sample()}}
    load=AsyncMock(return_value=copy.deepcopy(project));monkeypatch.setattr(common,'load_authorized_project',load)
    monkeypatch.setattr(route,'_load_brand_backgrounds',AsyncMock(return_value=[]))
    monkeypatch.setattr(route,'_load_brand_kit',AsyncMock(return_value={}))
    monkeypatch.setattr(route,'_load_brand_logo',AsyncMock(return_value=''))
    llm=AsyncMock(side_effect=AssertionError('No paid LLM for shadow commands'));monkeypatch.setattr(route,'_call_llm',llm)
    projects=SimpleNamespace(update_one=AsyncMock(return_value=SimpleNamespace(matched_count=matched)))
    snapshots=SimpleNamespace(update_one=AsyncMock())
    monkeypatch.setattr(route,'db',SimpleNamespace(projects=projects,aesthetic_snapshots=snapshots))
    return project,projects,snapshots,llm,load


def test_route_persists_only_shadow_metadata_and_retains_undo_without_ai(monkeypatch):
    project,projects,snapshots,llm,load=setup_route(monkeypatch)
    response=asyncio.run(editor_chat('p',{'message':'Aplicar sombra media em todas as imagens'}, {'user_id':'u'}))
    assert len(response['ops'])==3 and response['snapshotCreated']
    assert '3 imagem(ns) em 2 slide(s)' in response['reply']
    llm.assert_not_awaited();load.assert_awaited_once_with('p',{'user_id':'u'})
    query,update=projects.update_one.call_args_list[0].args
    assert query['updatedAt']=='version-before'
    assert query['course.slides.0.elements.1.id']=='im1'
    assert 'course.slides' not in update['$set']
    assert all(key=='updatedAt' or key.endswith('.imageShadow') for key in update['$set'])
    snapshot=snapshots.update_one.call_args.args[1]['$set']
    assert snapshot['slidesBefore']==project['course']['slides']


def test_revision_conflict_does_not_overwrite_course_or_create_undo(monkeypatch):
    _,projects,snapshots,_,_=setup_route(monkeypatch,matched=0)
    with pytest.raises(HTTPException) as error:
        asyncio.run(editor_chat('p',{'message':'Aplicar sombra média em todas as imagens'}, {'user_id':'u'}))
    assert error.value.status_code==409
    snapshots.update_one.assert_not_awaited()
    assert projects.update_one.await_count==1


def test_help_and_no_targets_have_no_writes_no_ai_no_fake_success(monkeypatch):
    _,projects,snapshots,llm,_=setup_route(monkeypatch,slides=[{'id':'s','elements':[{'id':'h','type':'html','htmlContent':'<img>'}]}])
    response=asyncio.run(editor_chat('p',{'message':'Aplicar sombra média em todas as imagens'}, {'user_id':'u'}))
    assert not response['ops'] and not response['snapshotCreated']
    assert 'Não encontrei' in response['reply']
    response=asyncio.run(editor_chat('p',{'message':'Como aplicar sombra média em todas as imagens?'}, {'user_id':'u'}))
    assert not response['ops'] and 'No Chat do Editor' in response['reply']
    projects.update_one.assert_not_awaited();snapshots.update_one.assert_not_awaited();llm.assert_not_awaited()


def test_authorization_is_checked_before_any_operation(monkeypatch):
    import routes.projects_common as common
    _,projects,snapshots,_,_=setup_route(monkeypatch)
    monkeypatch.setattr(common,'load_authorized_project',AsyncMock(side_effect=HTTPException(403,'Forbidden')))
    with pytest.raises(HTTPException) as error:
        asyncio.run(editor_chat('p',{'message':'Aplicar sombra média em todas as imagens'}, {'user_id':'outsider'}))
    assert error.value.status_code==403
    projects.update_one.assert_not_awaited();snapshots.update_one.assert_not_awaited()
