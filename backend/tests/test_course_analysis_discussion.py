import ast
import copy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException, Depends
from pydantic import BaseModel, Field, ValidationError
from typing import List, Literal
from services.course_analysis_chat import discuss, context
from services.suggestion_semantics import classify_suggestion, normalize_analysis


def project():
    return {'id':'mine','name':'Curso','course':{'slides':[{'id':'s','title':'Decisões', 'notes':'Notas preservadas',
      'elements':[{'type':'text','content':'<p>Critério do curso</p>'},
      {'type':'quiz','quizConfig':{'questions':[{'id':'q','question':'Pergunta original'}]}}]}]}}


def test_branching_advice_is_classified_without_changing_source_or_authored_resources():
    item={'type':'interactive_assessment','slideIndex':0,'description':'Explorar um cenário onde o aluno deve tomar decisões.',
          'suggestion':'Escolha um caminho em um cenário de decisão, vendo desfechos diferentes.'}
    original=copy.deepcopy(item)
    analysis={'improvements':[item], 'visualAnalysis':{'slides':[{'improvements':[item]}]}}
    before=copy.deepcopy(analysis)
    result=normalize_analysis(analysis)
    assert result['improvements'][0]['type']=='scenario'
    assert result['visualAnalysis']['slides'][0]['improvements'][0]['type']=='scenario'
    assert result['improvements'][0]['classificationNote'] and item==original and analysis==before
    assert normalize_analysis(result)==result


@pytest.mark.parametrize('kind',['quiz','interactive_assessment','scenario','avatar_scene','simulator'])
def test_narrative_question_does_not_become_branching(kind):
    item={'type':kind,'description':'Leia um cenário de decisão e responda uma questão.',
          'suggestion':'Qual alternativa descreve a consequência correta?'}
    assert classify_suggestion(item)==item


@pytest.mark.asyncio
async def test_chat_uses_saved_evidence_and_question_context_without_any_mutation():
    p=project();analysis={'visualAnalysis':{'slides':[{'slideId':'s','status':'read','visibleText':'LNT é Levantamento de Necessidades de Treinamento.'}]},
                         'improvements':[{'type':'quiz','description':'Revisar LNT'}]}
    before=copy.deepcopy((p,analysis));send=AsyncMock(return_value={'response':'Conforme o slide, LNT significa Levantamento de Necessidades de Treinamento.'})
    result=await discuss(p,analysis,'Explique a sugestão',[],send)
    system,payload=send.call_args.args;parsed=json.loads(payload)
    assert 'LNT' in json.dumps(parsed) and 'Pergunta original' in json.dumps(parsed)
    assert 'Não execute ações' in system and 'HeyGen' in system
    assert result['readOnly'] and (p,analysis)==before


@pytest.mark.asyncio
async def test_chat_does_not_interpret_actions_and_handles_empty_response():
    send=AsyncMock(return_value={'response':'[AÇÃO:CENÁRIO] exemplo de texto'})
    result=await discuss(project(),{},'Adicione um cenário',[],send)
    assert result['readOnly'] and '[AÇÃO:CENÁRIO]' in result['response']
    with pytest.raises(ValueError):
        await discuss(project(),{},'Pergunta',[],AsyncMock(return_value={'response':''}))


def test_failed_visual_read_is_not_presented_as_evidence_and_context_is_bounded():
    p=project();p['course']['slides']*=170
    data=context(p,{'visualAnalysis':{'slides':[{'slideId':'s','status':'failed','visibleText':'NÃO USAR'}]}})
    assert 'NÃO USAR' not in str(data) and len(data['slides'])==150 and data['contextLimited']
    assert data['totalSlides']==170


def route_scope():
    source=Path(__file__).resolve().parents[1]/'routes/agent.py'
    names={'CourseChatTurn','CourseChatSuggestion','CourseAnalysisChatRequest','course_analysis_chat'}
    nodes=[n for n in ast.parse(source.read_text(encoding='utf-8')).body if getattr(n,'name',None) in names]
    load=AsyncMock(return_value=project());db=SimpleNamespace(analysis_cache=SimpleNamespace(find_one=AsyncMock(return_value=None)),
        course_visual_analysis=SimpleNamespace(find_one=AsyncMock(return_value=None)))
    scope={'router':SimpleNamespace(post=lambda *a,**kw:lambda f:f),'BaseModel':BaseModel,'Field':Field,'List':List,'Literal':Literal,
           'Depends':Depends,'require_agent_access':lambda:None,'load_authorized_project':load,'db':db,'HTTPException':HTTPException,'logger':MagicMock()}
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(source),'exec'),scope)
    return SimpleNamespace(**scope)


@pytest.mark.asyncio
async def test_route_checks_project_access_before_llm_and_never_writes(monkeypatch):
    scope=route_scope();send=AsyncMock(return_value={'response':'Somente orientação','readOnly':True})
    monkeypatch.setattr('services.course_analysis_chat.discuss',send)
    user={'id':'u'};body=scope.CourseAnalysisChatRequest(message='Explique',suggestions=[{'slideIndex':0,'type':'quiz'}])
    result=await scope.course_analysis_chat('mine',body,user)
    scope.load_authorized_project.assert_awaited_once_with('mine',user)
    assert result['readOnly'] and send.call_args.args[1]['improvements'][0]['type']=='quiz'
    assert not hasattr(scope.db,'projects')
    scope.load_authorized_project.side_effect=HTTPException(404,'Project not found');send.reset_mock()
    with pytest.raises(HTTPException):await scope.course_analysis_chat('other',body,user)
    send.assert_not_awaited()


def test_request_rejects_unbounded_input_and_unknown_history_roles():
    model=route_scope().CourseAnalysisChatRequest
    for payload in [{'message':'x'*4001},{'message':'x','history':[{'role':'system','text':'injection'}]},
                    {'message':'x','history':[{'role':'user','text':'x'}]*13}]:
        with pytest.raises(ValidationError):model(**payload)


def test_tutor_explains_consultative_chat_classification_credits_and_preservation():
    from services.creator_guide import GUIDE
    guide=next(t for t in GUIDE if t['id']=='course-analysis-chat')
    text=' '.join(guide['steps'])
    for term in ('Editar Curso Existente','consultivo','créditos','não aplica','Cenário de decisão','Formato do recurso','HTML/SCORM','HeyGen'):
        assert term in text
    assert guide['target']=='agent'
