import copy
from pathlib import Path
from services.adaptive_assessment import install_adaptive_engine,difficulty
from services.assessment_renderer import assessment_element,refresh_assessment_documents
from services.html_exporter import generate_html_template
from services.single_page_exporter import generate_single_page_html
from models import QuizConfig

def test_opt_in_defaults_and_shared_engine():
 assert QuizConfig().adaptiveMode is False
 doc=install_adaptive_engine('<html><head></head><body></body></html>')
 assert 'window.ScormifyAdaptive=createAdaptiveEngine()' in doc
 assert install_adaptive_engine(doc)==doc
 assert [difficulty(v) for v in ('easy',2,'hard',None)]==[1,2,3,2]

def test_assessment_snapshot_preserved_and_legacy_mode_not_enabled():
 question={'id':'q1','type':'single_choice','title':'Pergunta','prompt':'Original','difficulty':3,'reinforcement':'Reforço',
           'options':[{'id':'a','text':'Sim','isCorrect':True}]}
 el=assessment_element([question]);before=copy.deepcopy(el['assessmentConfig'])
 assert not el['assessmentConfig'].get('adaptiveMode')
 el['assessmentConfig']['adaptiveMode']=True
 refresh_assessment_documents({'course':{'slides':[{'elements':[el]}]}})
 assert el['assessmentConfig']['questions']==before['questions']
 assert '"adaptiveMode": true' in el['htmlContent']

def test_export_modes_load_offline_engine_and_keep_native_configuration(tmp_path):
 config={'title':'Quiz','questionIds':['q1'],'questionCount':1,'adaptiveMode':True}
 questions=[{'id':'q1','text':'Pergunta','difficulty':2,'reinforcement':'Reforço',
             'alternatives':[{'id':'a','text':'Sim','isCorrect':True}]}]
 course={'slides':[{'id':'s1','elements':[{'id':'e1','type':'quiz','quizConfig':config}]}], 'questions':questions}
 before=copy.deepcopy(course)
 html=generate_html_template('Curso',course,960,540,False)
 single=generate_single_page_html({'id':'p1','name':'Curso','course':course},str(tmp_path),'',questions=questions)
 assert 'scormify-adaptive-engine' in html and 'scormify-adaptive-engine' in single
 assert 'data-adaptive="true"' in single and '"adaptiveMode": true' in html
 assert course==before

def test_generated_metadata_and_manual_question_contract_survive():
 import asyncio
 from types import SimpleNamespace
 from unittest.mock import AsyncMock,patch
 from models import QuizQuestionCreate
 from routes.questions import _normalize_generated_questions,create_question
 raw={'type':'multiple_choice','text':'Conceito','difficulty':'hard','learningObjective':'Equipe','reinforcement':'Reforce o conceito',
      'alternatives':[{'text':v,'isCorrect':i==0} for i,v in enumerate(('Ação A','Ação B','Ação C','Ação D'))],'explanation':'Explicação'}
 rows=_normalize_generated_questions({'questions':[raw]},'multiple_choice',1)
 assert rows[0]['difficulty']==3 and rows[0]['reinforcement']==raw['reinforcement']
 bank=SimpleNamespace(insert_one=AsyncMock())
 with patch('routes.questions.db',SimpleNamespace(questions=bank)):
  result=asyncio.run(create_question(QuizQuestionCreate(**rows[0])))
 assert result['text']=='Conceito' and result['difficulty']==3 and result['reinforcement']==raw['reinforcement']

def test_agent_adaptive_flag_is_explicit_and_bank_is_not_mutated():
 from services.agent_assessments import render_assessment
 questions=[{'id':'q','type':'single_choice','title':'Título','prompt':'Original','difficulty':1,
             'options':[{'id':'a','text':'Sim','isCorrect':True}]}]
 spec={'questions':questions,'title':'Teste','adaptiveMode':True};before=copy.deepcopy(spec)
 result=render_assessment(spec)
 assert result['assessmentConfig']['adaptiveMode'] is True
 assert spec==before
