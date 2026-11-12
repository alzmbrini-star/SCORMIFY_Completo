import asyncio
import base64
import copy
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from test_process_visual_refinement import pump_model, pump_scene
from test_simulator_object_images import png
from services.rule_visuals import validate_visual
from services.simulator_object_images import enrich, image_scope, validate_illustrations


def four_pieces():
    model=pump_model();scene=pump_scene()
    for node in scene['nodes'][1:3]:
        node['artwork']={'bounds':[node['attrs']['x'],node['attrs']['y'],150,150],'description':'Reservatório inteiro.'}
    for index in (1,2):
        ident='person'+str(index)
        scene['nodes'] += [dict(id=ident,type='group',label='Personagem '+str(index),attrs={'x':230+index*80,'y':120},bindings=[],states=[],
                               artwork={'bounds':[0,0,60,100],'description':'Pessoa inteira vista de frente, sentada para explicar a operação.'}),
                          dict(id=ident+'_body',type='ellipse',label='Forma de reserva',parent=ident,attrs={'x':30,'y':50,'rx':25,'ry':45,'fill':'#99AACC'},bindings=[],states=[])]
    model['visual']=validate_visual(scene,model)
    src='data:image/png;base64,'+base64.b64encode(png()).decode()
    model['visual']['illustrations']=[{'node':'reservoir1','src':src},{'node':'reservoir2','src':src}]
    return model


def test_existing_images_do_not_stop_missing_characters_or_charge_again():
    model=four_pieces();before=copy.deepcopy(model)
    db=SimpleNamespace(image_gallery=SimpleNamespace(find_one=AsyncMock(return_value=None),update_one=AsyncMock()))
    chat=SimpleNamespace(send_message=AsyncMock(side_effect=AssertionError('Semantic plan already exists')))
    chat.with_model=lambda *a:chat;chat.with_params=lambda **kw:chat
    async def run():
        with image_scope(db,{'user_id':'author','companyId':'company'}):
            result=await enrich({'spec':model,'html':'old'},'assunto livre','{"simulatorOptions":{"objectImages":true}}','qa',max_images=2)
            again=await enrich(result,'assunto livre','{"simulatorOptions":{"objectImages":true}}','qa-again')
            assert again is result
            return result
    with patch('services.llm_config.openai_api_key',return_value='fake'),patch('services.llm_config.simulator_generation_config',return_value=('openai','fake','model')),patch('emergentintegrations.llm.chat.LlmChat',return_value=chat),patch('services.simulator_object_images.generate_piece',AsyncMock(return_value=png())) as paid:
        result=asyncio.run(run())
    assert paid.await_count==2;assert db.image_gallery.update_one.await_count==2
    chat.send_message.assert_not_awaited()
    assert model==before
    assert result['spec']['visual']['illustrations'][:2]==before['visual']['illustrations']
    assert [r['node'] for r in result['spec']['visual']['illustrations']]==['reservoir1','reservoir2','person1','person2']
    assert result['spec']['visual']['nodes']==before['visual']['nodes']
    for key in ('variables','actions','checks','goal','failure'):assert result['spec'][key]==before[key]
    assert 'scormify-object-images' in result['html']


def test_eight_images_are_supported_but_the_total_is_bounded():
    model=four_pieces();scene=model['visual'];src=scene['illustrations'][0]['src']
    for i in range(4):
        scene['nodes'].append(dict(id='extra'+str(i),type='rect',label='Objeto inteiro',attrs={'x':10+i*80,'y':10,'width':80,'height':80,'fill':'#99AABB'},artwork={'bounds':[10+i*80,10,80,80],'description':'Objeto de apoio essencial.'},bindings=[],states=[]))
    ids=['reservoir1','reservoir2','person1','person2']+['extra'+str(i) for i in range(4)]
    rows=[{'node':key,'src':src} for key in ids]
    assert len(validate_illustrations(rows,scene['nodes']))==8
    import pytest
    with pytest.raises(ValueError):validate_illustrations(rows+[rows[0]],scene['nodes'])
