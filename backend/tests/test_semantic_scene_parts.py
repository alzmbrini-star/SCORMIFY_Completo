import base64
import copy
import json
import subprocess
from pathlib import Path
import pytest
from services.didactic_visualizations import validate, generated_plan, render
from services.simulator_object_images import candidates, validate_illustrations
from test_didactic_visualizations import fixture
from test_simulator_object_images import png


def composition(topic='Equipamento'):
    data=fixture()
    data.update(title=topic, nodes=[
        {'id':'piece','type':'group','label':topic,'explanation':'A peça inteira aproxima-se da base.',
         'attrs':{'x':170,'y':180},'artwork':{'bounds':[-65,-65,130,130], 'description':'Peça inteira na mesma vista da base.'}},
        {'id':'body','type':'rect','parent':'piece','label':'Corpo','explanation':'Contorno de reserva.',
         'attrs':{'x':-50,'y':-50,'width':100,'height':100,'fill':'#88AABB'}},
        {'id':'detail','type':'circle','parent':'piece','label':'Conexão','explanation':'Detalhe fixo.',
         'attrs':{'x':0,'y':0,'r':20,'fill':'#345678'}},
        {'id':'base','type':'rect','label':'Base','explanation':'Destino da peça.',
         'attrs':{'x':350,'y':140,'width':130,'height':160,'fill':'#8399AA'}},
    ], motions=[{'node':'piece','kind':'transition','cx':0,'cy':0,'dx':120,'dy':0,
                 'cycles':1,'phase':0,'start':2,'end':6}],
       timeline=[{'label':'Preparar','start':0,'end':2},{'label':'Aproximar','start':2,'end':6},
                 {'label':'Observar','start':6,'end':12}])
    return data


@pytest.mark.parametrize('topic',['Queijo: coleta e cura','Engrenagem de transmissão','Pilar protético','Negociação comercial','Evaporação da água'])
def test_subject_independent_compound_piece_and_stage_motion(topic):
    data=composition(topic);before=copy.deepcopy(data)
    clean=validate(data)
    assert clean==validate(clean)
    assert data==before
    parts=candidates(clean)
    assert [p['id'] for p in parts]==['piece']
    assert parts[0]['bounds']==[-65,-65,130,130]
    assert clean['motions'][0]['start']==2 and clean['motions'][0]['end']==6
    assert clean['timeline'][1]['label']=='Aproximar'


def test_never_flatten_a_piece_with_independently_moving_children():
    data=composition()
    data['motions'].append(dict(data['motions'][0],node='detail'))
    assert not candidates(data)
    data=composition();data['nodes'][1]['states']=[{'when':True,'set':{'height':50}}]
    assert not candidates(data)


def test_cosmetic_material_names_do_not_reject_new_generation():
    data=composition();data['nodes'][1]['appearance']={'material':'ceramic','depth':'realistic'}
    clean=generated_plan(data)
    assert clean['nodes'][1]['appearance']=={'material':'matte','depth':'soft'}
    with pytest.raises(ValueError):validate(data)  # saved legacy contract stays explicit


def test_reject_code_and_invalid_part_windows_without_physics_proof():
    for change in ('bounds','description'):
        data=composition();data['nodes'][0]['artwork'][change]='alert(1)' if change=='bounds' else ''
        with pytest.raises(ValueError):validate(data)
    data=composition();data['motions'][0]['end']=1
    with pytest.raises(ValueError):validate(data)
    data=composition();data['nodes'][0]['parent']='body'
    with pytest.raises(ValueError):validate(data)


def test_group_image_motion_pause_legends_and_reset_in_trusted_runtime():
    data=composition()
    data['illustrations']=[{'node':'piece','src':'data:image/png;base64,'+base64.b64encode(png()).decode()}]
    validate_illustrations(data['illustrations'],data['nodes'])
    script=Path(__file__).with_name('semantic_scene_parts.cjs')
    result=subprocess.run(['node',str(script)],input=render(data),text=True,encoding='utf-8',capture_output=True)
    assert result.returncode==0,result.stdout+result.stderr


def test_rule_composition_preserves_actions_and_binds_image_to_whole_group():
    from test_process_demo import process_demo
    from services.rule_simulators import validate_rules, render_rules
    from services.rule_visuals import validate_visual
    spec=validate_rules(process_demo());before=copy.deepcopy(spec)
    data=composition();nodes=data['nodes'];v=spec['variables'][0]
    nodes[0]['bindings']=[{'property':'x','var':v['id'],'input':[v['min'],v['max']],'output':[170,290]}]
    visual={'version':1,'title':'Peças','description':'Aproximação qualitativa das peças.','background':'#EDF3F8',
            'nodes':nodes,'motions':[{'node':'piece','kind':'rotate','cx':0,'cy':0,'dx':0,'dy':0,'cycles':1,'phase':0}]}
    spec['visual']=validate_visual(visual,spec)
    spec['visual']['illustrations']=[{'node':'piece','src':'data:image/png;base64,'+base64.b64encode(png()).decode()}]
    for key in ('variables','actions','goal','failure'):assert spec[key]==before[key]
    html=render_rules(spec)
    assert 'scormify-object-images' in html and 'paintDeclaredMotions' in html
    assert 'e.motionPose=attrs' in html
    result=subprocess.run(['node',str(Path(__file__).with_name('semantic_scene_parts.cjs'))],input=html,
                          text=True,encoding='utf-8',capture_output=True)
    assert result.returncode==0,result.stdout+result.stderr


def test_tutor_explains_composition_and_reexport():
    from services.creator_guide import topics_for
    topic=next(t for t in topics_for({'user_id':'author','role':'editor'}) if t['id']=='simulators')
    steps=' '.join(topic['steps'])
    assert 'peças completas' in steps and 'etapas' in steps and 'reexporte' in steps.lower()
