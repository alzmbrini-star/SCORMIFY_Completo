import copy
import json
import pytest
from services.agent_language import normalize_structure_language, pt_br_text, language_instruction


def sample():
    return {'courseTitle':'Gestão e Documentação em Implantodontia',
            'learningObjectives':['Aplicación prática de LGPD'],
            'modules':[{'id':'Gestión', 'title':'Gestión e Documentación',
                        'description':'Introducción ao Design Thinking',
                        'slides':[{'id':'Simulación', 'type':'game',
                                   'title':'Simulación de Gestão de Casos',
                                   'purpose':'Planificación do workflow',
                                   'estimatedDuration':120,
                                   'requiredImagePrompt':'Spanish reference unchanged',
                                   'asset':'https://example.invalid/Simulación.png'}]}]}


def test_reported_mixed_title_is_corrected_without_mutation_or_identifier_changes():
    data=sample();before=copy.deepcopy(data)
    fixed=normalize_structure_language(data)
    assert data==before
    slide=fixed['modules'][0]['slides'][0]
    assert slide['title']=='Simulação de Gestão de Casos'
    assert slide['purpose']=='Planejamento do workflow'
    assert slide['id']=='Simulación' and slide['type']=='game'
    assert slide['estimatedDuration']==120
    assert slide['asset']==before['modules'][0]['slides'][0]['asset']
    assert slide['requiredImagePrompt']==before['modules'][0]['slides'][0]['requiredImagePrompt']
    assert fixed['modules'][0]['description']=='Introdução ao Design Thinking'
    assert normalize_structure_language(fixed)==fixed


@pytest.mark.parametrize('language',['es','es-ES','en','en-US'])
def test_non_portuguese_course_is_not_rewritten(language):
    data=sample();assert normalize_structure_language(data,{'language':language})==data


def test_word_boundaries_case_quotes_brands_and_accents():
    assert pt_br_text('SIMULACIÓN / simulación / Simulación')=='SIMULAÇÃO / simulação / Simulação'
    assert pt_br_text('Simulacio\u0301n')=='Simulação'
    text='Design Thinking, SPIN Selling, LGPD, SimulaciónPlus, "Simulación", “Gestión”, `simulación`'
    assert pt_br_text(text)==text
    assert pt_br_text('https://example.invalid/Simulación')=='https://example.invalid/Simulación'


@pytest.mark.asyncio
@pytest.mark.parametrize('template',[False,True])
async def test_generators_instruct_pt_br_and_clean_model_output_without_retries(monkeypatch,template):
    from services import ai_agent
    calls=[]
    class Chat:
        async def send_message(self,message):
            calls.append(message.text)
            return json.dumps(sample(),ensure_ascii=False)
    monkeypatch.setattr(ai_agent,'_new_chat',lambda *a,**k:Chat())
    config={'enabledResources':{},'resourceBalance':'baixa','title':'Implantodontia'}
    if template:
        data=await ai_agent.generate_structure_from_template('test','Referência',config,ai_agent.COURSE_TEMPLATES[0]['id'])
    else:
        data=await ai_agent.generate_structure('test','Referência',config)
    assert len(calls)==1
    assert language_instruction(config) in calls[0]
    assert data['modules'][0]['slides'][0]['title']=='Simulação de Gestão de Casos'


def test_tutor_documents_language_cleanup():
    from services.creator_guide import GUIDE
    guide=next(t for t in GUIDE if t['id']=='agent')
    assert 'sem uma nova chamada de IA' in ' '.join(guide['steps'])
