import json
import pytest
from services.teaching_copy import lesson_html,validate_lesson,clean_image_instructions


BODY='<h2>Trabalho em equipe</h2><p>Uma equipe reúne pessoas com competências complementares, responsabilidades definidas e um objetivo comum. A colaboração exige comunicação, coordenação das tarefas e compromisso com os resultados coletivos. Por exemplo, combinar responsáveis e prazos ajuda a acompanhar uma entrega compartilhada.</p>'
PROMPT='Professional Brazilian corporate training visual about Trabalho em Equipe. Create a process-oriented visual, landscape 16:9, no written text, no logos, no watermark.'


def slide():
    return {'id':'s','title':'Trabalho em Equipe','type':'content','imageKeywords':PROMPT,
            'elements':[{'type':'text','content':BODY},{'type':'text','content':'<p>[IMG:'+PROMPT+']</p>'}]}


def test_all_teaching_blocks_are_kept_in_order_and_image_instructions_removed():
    item=slide();item['elements'].insert(1,{'type':'html','htmlContent':'<p>Exemplo: distribuir tarefas e combinar pontos de acompanhamento.</p>'})
    item['elements'].append({'type':'image','content':'/api/projects/p/assets/photo.png'})
    result=lesson_html(item)
    assert BODY in result and 'Exemplo:' in result
    assert result.index('Uma equipe')<result.index('Exemplo:')
    assert PROMPT not in result and '[IMG:' not in result
    validate_lesson(item)


def test_real_source_markers_survive_but_are_not_a_lesson_alone():
    assert clean_image_instructions('<p>[IMG:docx_image_11.png]</p>')=='<p>[IMG:docx_image_11.png]</p>'
    item={'type':'content','elements':[{'content':'<p>[IMG:docx_image_11.png]</p>'}]}
    with pytest.raises(ValueError,match='CONTEUDO_DIDATICO_AUSENTE'):validate_lesson(item)
    item['sourceImageOnly']=True
    validate_lesson(item)


def test_only_prompt_does_not_satisfy_minimum_words():
    item=slide();item['elements']=item['elements'][1:]
    with pytest.raises(ValueError,match='imageKeywords'):validate_lesson(item)
    item['elements']=[{'type':'text','content':PROMPT}]
    assert not lesson_html(item)


@pytest.mark.parametrize('builder,args',[
 ('_build_content_slide',('image.png',)),('_build_content_slide_no_media',()),
 ('_build_content_slide_with_video',({'type':'youtube','embedUrl':'https://www.youtube.com/embed/test'},)),
 ('_build_content_slide_with_heygen',('pending-id',)),
 ('_build_content_slide_with_embed',({'url':'https://example.test'},'html')),
 ('_build_content_slide_with_button',({'url':'https://example.test','buttonText':'Saiba mais'},)),
])
def test_every_content_layout_uses_lesson_not_last_image_block(builder,args):
    from services import ai_agent
    palette=dict(ai_agent._COURSE_PALETTES[0])
    elements=getattr(ai_agent,builder)(slide(),palette,'Módulo',*args)
    document=' '.join(e.get('htmlContent','') for e in elements)
    assert 'Uma equipe reúne' in document
    assert 'Professional Brazilian' not in document
    assert '[IMG:' not in document


@pytest.mark.asyncio
async def test_storyboard_retries_prompt_only_response_and_retains_true_copy(monkeypatch):
    from services import ai_agent
    from services.source_coverage import ensure_coverage
    source='Unidade 1 Trabalho em Equipe\n\nDefinição de equipe e a importância da colaboração, das responsabilidades e do objetivo comum.'
    structure=ensure_coverage({'modules':[]},source);prompts=[]
    class Chat:
        async def send_message(self,message):
            prompts.append(message.text)
            batch=json.loads(message.text.split('Slides a gerar: ',1)[1].split('\n',1)[0])
            return json.dumps({'slides':[{**s,'elements':slide()['elements'][1:] if len(prompts)==1 else slide()['elements']} for s in batch]})
    monkeypatch.setattr(ai_agent,'_new_chat',lambda *a,**k:Chat())
    async def no_sleep(*a):pass
    monkeypatch.setattr(ai_agent.asyncio,'sleep',no_sleep)
    result=await ai_agent.generate_storyboard('copy-test',source,structure,{})
    assert 'CONTEUDO_DIDATICO_AUSENTE' in prompts[1]
    assert BODY in lesson_html(result['slides'][0])


def test_tutor_explains_separation_and_existing_course_limits():
    from services.creator_guide import topics_for
    topic=next(t for t in topics_for({'role':'super_admin'}) if t['id']=='agent')
    text=' '.join(topic['steps'])
    assert 'imageKeywords' in text and 'não reescreve cursos existentes' in text
