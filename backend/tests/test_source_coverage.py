import io
import json
import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from docx import Document
from services import ai_agent
from services.source_coverage import complete_source, docx_text, source_sections, source_contract, ensure_coverage, batch_source


@pytest.mark.parametrize('topic,last', [('Jardinagem','Controle de pragas'),('Cibersegurança','Resposta a incidentes'),('Culinária','Conservação e validade')])
def test_all_numbered_topics_are_planned_without_theme_templates(topic,last):
    text=f'Introdução ao curso de {topic}.\n\nUnidade 1 Fundamentos\n\n• Explicar a preparação do ambiente e os cuidados essenciais.\n\nUnidade 2 {last}\n\n• Demonstrar {last} com exemplos e riscos.\n\nProjeto final\n\nAplicar o conhecimento em um caso completo.'
    plan=ensure_coverage({'modules':[{'title':'Introdução','slides':[{'id':'end','type':'summary'}]}]},text)
    refs={r for m in plan['modules'] for s in m['slides'] for r in s.get('sourceRefs',[])}
    expected={i['id'] for section in source_sections(text) for i in section['items']}
    assert refs==expected
    assert plan['modules'][-1]['slides'][-1]['id']=='end'
    assert ensure_coverage(plan,text)==plan
    assert last in json.dumps(plan,ensure_ascii=False)


def test_unnumbered_large_document_includes_middle_and_final_paragraphs():
    paragraphs=[f'Assunto {i}: '+'Cuidados específicos e exemplos concretos. '*15 for i in range(40)]
    paragraphs[-1]+=' PROCEDIMENTO_FINAL_OBRIGATORIO'
    text='\n\n'.join(paragraphs)
    plan=ensure_coverage({'modules':[]},text)
    sections=source_sections(text)
    all_text=' '.join(i['text'] for section in sections for i in section['items'])
    assert ' '.join(text.split())==all_text
    assert 'PROCEDIMENTO_FINAL_OBRIGATORIO' in json.dumps(plan)
    assert all(len(s.get('sourceRefs',[]))<=2 for m in plan['modules'] for s in m['slides'])
    assert len(complete_source(text))>12000
    with pytest.raises(ValueError,match='nenhum trecho'): complete_source('x'*120001)


def test_docx_preserves_table_position_and_heading_hierarchy():
    doc=Document(); doc.add_heading('Unidade 1 Fluxo',1);doc.add_paragraph('Primeira orientação.')
    table=doc.add_table(rows=1,cols=2);table.cell(0,0).text='Campo';table.cell(0,1).text='Valor importante'
    doc.add_paragraph('Segunda orientação.');doc.add_heading('Unidade 2 Encerramento',1);doc.add_paragraph('Última orientação.')
    output=io.BytesIO();doc.save(output)
    text=docx_text(output.getvalue())
    assert text.index('Primeira')<text.index('Valor importante')<text.index('Segunda')<text.index('Última')
    assert '# Unidade 1' in text
    assert len(source_sections(text))==2


def test_meaningful_subheadings_are_not_discarded():
    text='Unidade 1 Segurança\n\n## Tratamento de incidentes\n\nRegistrar o evento e suas evidências.'
    scope=source_sections(text)
    assert 'Tratamento de incidentes' in ' '.join(i['text'] for s in scope for i in s['items'])


@pytest.mark.asyncio
async def test_analysis_and_structure_receive_tail_after_old_prefix_limits(monkeypatch):
    text='Unidade 1 Preparação\n\n'+'Uma explicação integral do assunto e seus detalhes. '*280+'\n\nUnidade 2 Encerramento\n\nPROCEDIMENTO_FINAL_OBRIGATORIO com exemplo e aplicação.'
    prompts=[]
    class Chat:
        async def send_message(self,message):
            prompts.append(message.text)
            return json.dumps({'title':'Curso','suggestedModules':1,'mainTopics':['início'],'modules':[{'title':'Início','slides':[]} ]})
    monkeypatch.setattr(ai_agent,'_new_chat',lambda *a,**k:Chat())
    analysis=await ai_agent.analyze_content('qa',text)
    structure=await ai_agent.generate_structure('qa',text,{'enabledResources':{}})
    assert all('PROCEDIMENTO_FINAL_OBRIGATORIO' in p for p in prompts)
    assert 'Encerramento' in ' '.join(analysis['mainTopics'])
    assert structure['sourceCoverage']['items']>10
    assert structure['sourceCoverage']['plannedItems']==structure['sourceCoverage']['items']


@pytest.mark.asyncio
async def test_storyboard_uses_assigned_context_and_preserves_full_explanation(monkeypatch):
    text='Unidade 1 Início\n\nOrientar o preparo e apresentar o processo de forma fundamentada.\n\nUnidade 2 Final\n\nPROCEDIMENTO_FINAL_OBRIGATORIO precisa ser desenvolvido com exemplo e cuidados.'
    plan=ensure_coverage({'modules':[]},text); prompts=[]
    body='<h2>Procedimento explicado</h2><p>'+'Uma explicação desenvolvida com exemplo concreto e orientação aplicável ao processo. '*16+'</p>'
    class Chat:
        async def send_message(self,message):
            prompts.append(message.text)
            raw=message.text.split('Slides a gerar: ',1)[1].split('\n',1)[0]
            batch=json.loads(raw)
            return json.dumps({'slides':[dict(s,elements=[{'type':'text','content':body}]) for s in batch]})
    monkeypatch.setattr(ai_agent,'_new_chat',lambda *a,**k:Chat())
    result=await ai_agent.generate_storyboard('qa',text,plan,{'enabledResources':{}})
    assert 'PROCEDIMENTO_FINAL_OBRIGATORIO' in '\n'.join(prompts)
    assert all(s['elements'][0]['content']==body for s in result['slides'])
    assert all(s['sourceRefs'] for s in result['slides'] if s.get('sourceRequired'))
    assert result['sourceCoverage']['status']=='generated'


def test_game_quota_never_replaces_required_explanation():
    text='Unidade 1 Teste\n\n• Definir as condições iniciais do trabalho.\n\n• Explicar as regras e cuidados com evidências.\n\n• Demonstrar o encerramento com rastreabilidade.'
    plan=ensure_coverage({'modules':[]},text)
    result=ai_agent._premiumize_course_structure(plan,{'resourceBalance':'maxima','enabledResources':{'game':True,'simulator':True,'quiz':True}})
    assert all(s['type']=='content' for m in result['modules'] for s in m['slides'] if s.get('sourceRequired'))


def test_missing_scope_gets_meaningful_titles_intro_before_units_and_final_summary():
    text='Ambientação necessária ao assunto.\n\nUnidade 1 Operação\n\nVerificar as condições iniciais e explicar o procedimento com um exemplo.'
    original={'modules':[{'title':'Capa','slides':[{'type':'title'}]}, {'title':'Operação','slides':[]}]}
    plan=ensure_coverage(original,text)
    assert plan['modules'][1]['id']=='source_SRC000'
    assert plan['modules'][-1]['slides'][-1]['type']=='summary'
    assert 'Verificar as condições' in plan['modules'][-1]['slides'][0]['title']
    assert plan==ensure_coverage(plan,text)


def test_tutor_explains_scope_counter_and_old_course_limit():
    from services.creator_guide import topics_for
    text=' '.join(next(t for t in topics_for({'role':'super_admin'}) if t['id']=='agent')['steps'])
    for phrase in ['120 mil','Escopo do material','sem descarte','85 palavras','cursos já criados']:
        assert phrase in text
def test_summary_batch_keeps_whole_source_despite_local_excerpt():
    from services.source_coverage import batch_source
    source='Unidade 1 Preparação\nPreparar o trabalho.\nUnidade 2 Conclusão\nConcluir o trabalho.'
    assert batch_source(source,[{'type':'content','sourceExcerpt':'Somente conclusão'}, {'type':'summary'}])==source

