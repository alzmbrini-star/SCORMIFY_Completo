import copy
from pathlib import Path
import pytest
from services.scenario_assets import map_scenario_images
from services.single_page_exporter import _render_scenario_element_inner, generate_single_page_html

def test_only_image_fields_are_mapped_without_touching_source():
    original={'title':'Tema','config':{'imageUrl':'assets/x.png'},'nodes':[{'id':'a','imageUrl':'assets/a.png','narrative':'assets/a.png','choices':[{'feedback':'assets/a.png'}]}]}
    before=copy.deepcopy(original)
    result=map_scenario_images(original,lambda s:'mapped:'+s)
    assert original==before
    assert result['nodes'][0]['imageUrl']=='mapped:assets/a.png'
    assert result['nodes'][0]['narrative']=='assets/a.png'
    assert result['config']['imageUrl']=='mapped:assets/x.png'

def test_single_page_keeps_scene_art_dialogue_and_start_node(tmp_path):
    (tmp_path/'art.png').write_bytes(b'fake-image-test')
    data={'title':'História','start_node_id':'second','nodes':[{'id':'first'},{'id':'second','imageUrl':'/api/projects/p/assets/art.png','dialogue':'Fala curta','decision_prompt':'Como agir?','choices':[{'id':'c','reaction':'Reação'}]}]}
    rendered=_render_scenario_element_inner({'scenarioData':data},0,0,'p',str(tmp_path),'')
    assert 'data:image/png;base64,' in rendered
    assert 'Fala curta' in rendered and 'Reação' in rendered
    assert 'start_node_id' in rendered and 'second' in rendered
    project={'id':'p','course':{'slides':[{'id':'s','elements':[{'type':'scenario','scenarioData':data}]}]}}
    html=generate_single_page_html(project,str(tmp_path),'')
    assert 'ScormifyScenario' in html and 'Confirmar decisão' in html
    assert 'window.ScormifyScenario.mount' in html

@pytest.mark.asyncio
async def test_illustration_failure_does_not_discard_scenario(monkeypatch):
    from services import ai_agent,scenario_service
    async def fail(*args,**kwargs): raise RuntimeError('provider unavailable')
    monkeypatch.setattr(ai_agent,'_fetch_stock_image',fail)
    data={'title':'Tema','nodes':[{'id':'a','choices':[{'id':'c'}]}]}
    before=copy.deepcopy(data)
    await scenario_service.add_scenario_illustration(data,'p')
    assert data==before

@pytest.mark.asyncio
async def test_generated_art_is_attached_to_nodes_not_logic(monkeypatch):
    from services import ai_agent,scenario_service
    async def image(*args,**kwargs): return '/api/projects/p/assets/art.png'
    monkeypatch.setattr(ai_agent,'_fetch_stock_image',image)
    data={'title':'Tema','characters':[],'nodes':[{'id':'a','choices':[{'id':'c'}]},{'id':'b','imageUrl':'https://example.com/own.png'}]}
    await scenario_service.add_scenario_illustration(data,'p')
    assert data['nodes'][0]['imageUrl']=='/api/projects/p/assets/art.png'
    assert data['nodes'][1]['imageUrl']=='https://example.com/own.png'
    assert data['nodes'][0]['choices']==[{'id':'c'}]
