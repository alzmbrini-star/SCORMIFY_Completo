import copy
import json
from unittest.mock import AsyncMock

import pytest

from services import ai_agent
from services.learning_complements import KINDS, plan_complements, preserve_complement_metadata
from services.source_coverage import ensure_coverage, source_sections, batch_source


def protected(plan):
    return {s['id']: {k:s.get(k) for k in ('type','sourceRefs','sourceExcerpt','sourceImage','sourceImageOnly','purpose')}
            for m in plan['modules'] for s in m['slides'] if s.get('sourceRequired')}


@pytest.mark.parametrize('topic', ['Cultivo de orquídeas', 'Proteção de dados', 'Produção de queijo', 'Gestão de conflitos'])
def test_complements_are_additive_contextual_and_idempotent_across_topics(topic):
    text=f'Unidade 1 {topic}\n\nDefinir os conceitos de {topic}.\n\nExplicar as etapas e comparar procedimentos.\n\n[IMG:docx_001_aaaaaaaaaaaaaaaa.png]\n\nUnidade 2 Aplicação\n\nIdentificar os riscos e decidir a conduta com evidências.'
    plan=ensure_coverage({'modules':[]},text); before=protected(plan)
    cfg={'resourceBalance':'maxima','enabledResources':dict.fromkeys(KINDS,True)}
    result=ai_agent._premiumize_course_structure(plan,cfg)
    assert protected(result)==before
    refs={r for m in result['modules'] for s in m['slides'] if s.get('sourceRequired') for r in s.get('sourceRefs',[])}
    assert refs=={i['id'] for sec in source_sections(text) for i in sec['items']}
    complements=[s for m in result['modules'] for s in m['slides'] if s.get('isComplement')]
    assert complements and all(s['reinforcesSourceRefs'] and s['complementOf'] and s['learningRationale'] for s in complements)
    assert any(topic in s['sourceExcerpt'] for s in complements)
    assert all(s['sourceExcerpt']==batch_source(text,[s]) for s in complements)
    assert all(not s.get('sourceRequired') and not s.get('sourceRefs') for s in complements)
    image=next(s for m in result['modules'] for s in m['slides'] if s.get('sourceImageOnly'))
    assert 'requiredImagePrompt' not in image and 'imageSuggestion' not in image
    lessons=[s for m in result['modules'] for s in m['slides'] if s.get('sourceRequired') and not s.get('sourceImageOnly')]
    assert all(s.get('imageSuggestion',{}).get('approvalStage')=='media' for s in lessons)
    snapshot=copy.deepcopy(result)
    assert ai_agent._premiumize_course_structure(result,cfg)==snapshot
    assert ensure_coverage(result,text)==result
    assert result['modules'][-1]['slides'][-1]['type']=='summary'


@pytest.mark.parametrize('mode',['standard','illustrated_journey'])
def test_disabled_resources_and_simulator_permission_are_respected(mode):
    plan=ensure_coverage({'modules':[]},'Unidade 1 Processo\n\nExplicar etapas do mecanismo e decisões com riscos.')
    enabled=dict.fromkeys(KINDS,False);enabled['flashcard']=True;enabled['simulator']=True
    result=ai_agent._premiumize_course_structure(plan,{'visualCourseMode':mode,'resourceBalance':'maxima',
                   'enabledResources':enabled,'simulatorsAllowed':False})
    complements=[s for m in result['modules'] for s in m['slides'] if s.get('isComplement')]
    assert [s['type'] for s in complements]==['flashcard']


def test_none_enabled_means_no_automatic_paid_complements():
    plan=ensure_coverage({'modules':[]},'Unidade 1 Processo\n\nExplicar o início e o encerramento de forma fundamentada.')
    result=plan_complements(plan,{},dict.fromkeys(KINDS,False))
    assert result['learningComplements']['count']==0


def test_existing_contextual_resource_is_reused_without_duplicate():
    plan=ensure_coverage({'modules':[{'title':'Fundamentos','slides':[{'id':'teach','type':'content',
         'sourceRefs':['SRC001.I001']},{'id':'review','type':'quiz','title':'Revisão original'}]}]},
         'Unidade 1 Fundamentos\n\nExplicar os conceitos essenciais e demonstrar um exemplo.')
    result=plan_complements(plan,{'resourceBalance':'baixa'},{'quiz':True})
    resources=[s for m in result['modules'] for s in m['slides'] if s.get('isComplement')]
    assert len(resources)==1 and resources[0]['id']=='review'


def test_learning_intent_selects_mechanism_or_recall_not_a_topic_template():
    for title, purpose, expected in [('Módulo novo','Explorar o mecanismo e ajustar as etapas do processo.','simulator'),
                                      ('Outro assunto','Definir conceitos e termos do vocabulário.','flashcard')]:
        plan={'modules':[{'title':title,'slides':[{'id':'a','type':'content','sourceRequired':True,
                   'sourceRefs':['SRC001.I001'],'sourceExcerpt':purpose}]}]}
        result=plan_complements(plan,{'resourceBalance':'baixa'},{'simulator':True,'flashcard':True})
        resource=next(s for s in result['modules'][0]['slides'] if s.get('isComplement'))
        assert resource['type']==expected


@pytest.mark.asyncio
async def test_storyboard_preserves_links_without_replacing_lessons_or_calling_image_ai(monkeypatch):
    text='Unidade 1 Fundamentos\n\nDefinir os conceitos e demonstrar um exemplo de aplicação fundamentada.'
    config={'enabledResources':{'quiz':True},'resourceBalance':'baixa'}
    structure=ai_agent._premiumize_course_structure(ensure_coverage({'modules':[]},text),config)
    calls=[]
    class Chat:
        async def send_message(self,message):
            calls.append(message.text)
            batch=json.loads(message.text.split('Slides a gerar: ',1)[1].split('\n',1)[0])
            # Deliberately omit all server metadata: it must not depend on the model echoing it.
            return json.dumps({'slides':[{'id':s['id'],'type':s['type'],'title':s['title'],
                'elements':[{'type':'text','content':'<p>'+'Explicação contextual com exemplo e orientação prática fundamentada na fonte. '*10+'</p>'}],
                'quizQuestions':[]} for s in batch]})
    monkeypatch.setattr(ai_agent,'_new_chat',lambda *a,**k:Chat())
    result=await ai_agent.generate_storyboard('offline-test',text,structure,config)
    resources=[s for s in result['slides'] if s.get('isComplement')]
    assert len(resources)==1 and resources[0]['type']=='quiz'
    assert resources[0]['reinforcesSourceRefs']==['SRC001.I001']
    assert result['learningComplements']['policy']=='additive'
    assert any(s.get('sourceRequired') and s['type']=='content' for s in result['slides'])
    assert any('isComplement' in p and 'COMPLEMENTOS' not in p for p in calls)


def test_metadata_is_carried_for_specialized_and_cached_paths():
    generated=[{'type':'simulator'}]
    source=[{'type':'flashcard','isComplement':True,'complementOf':['lesson'],'reinforcesSourceRefs':['SRC001.I001'],'learningRationale':'Explorar mecanismo'}]
    preserve_complement_metadata(generated,source)
    assert generated[0]['complementOf']==['lesson']
    assert generated[0]['type']=='flashcard'


def test_tutor_explains_additive_resources_and_image_approval():
    from services.creator_guide import topics_for
    text=' '.join(next(t for t in topics_for({'role':'super_admin'}) if t['id']=='agent')['steps'])
    assert 'Complemento didático' in text and 'não são alterados automaticamente' in text
    assert 'Mídia' in text and 'permissão de Administração' in text
