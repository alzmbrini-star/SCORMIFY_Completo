import copy
import uuid
import pytest
from services.astryx_revision import revision_plan,create_revision,remap
from services.astryx_revision import source_token as fingerprint

PID='11223344-1122-3344-5566-778899aabbcc'
def project():
 return {'id':PID,'name':'Antigo','companyId':'tenant','course':{'metadata':{'title':'Antigo'},'slides':[
  {'id':'lesson','title':'Lição','width':1920,'height':820,'notes':'Nota original','elements':[{'id':'text','type':'text','content':'<p>Texto integral com <strong>ênfase</strong> e conceitos.</p>'},{'id':'image','type':'image','src':f'/api/projects/{PID}/assets/capture.png','alt':'Captura acessível'}]},
  {'id':'quiz','title':'Quiz','elements':[{'id':'q','type':'quiz','quizConfig':{'questionIds':['question-original'],'adaptiveMode':True}}]},
  {'id':'activity','title':'Atividade','elements':[{'id':'sim','type':'html','htmlContent':'<script>var state=1;</script><button>Ação</button>'}]},
  {'id':'animated','title':'Animada','elements':[{'type':'text','content':'Texto animado','animations':[{'effect':'fade'}]}]},
  {'id':'picture','title':'PPT','sourceImageOnly':True,'elements':[{'type':'image','src':f'/api/projects/{PID}/assets/capture.png','alt':'Slide original'}]}
 ]}}

def test_preview_is_read_only_selective_protects_activities_and_all_image_pixels():
 assert remap('Nota 1 sobre q1 e questão',{'1':'replacement','q1':'question-new'})=='Nota 1 sobre q1 e questão'
 assert remap('{"questionId":"q1"}',{'q1':'question-new'})=='{"questionId":"question-new"}'
 p=project();before=copy.deepcopy(p)
 styled,rows=revision_plan(p,['lesson','picture','animated'],{'style':'studio','theme':'dark'})
 assert p==before and len(styled['course']['slides'])==5
 for i in (1,2):assert styled['course']['slides'][i]==p['course']['slides'][i]
 assert [r['eligible'] for r in rows]==[True,False,False,True,True]
 animated=styled['course']['slides'][3]['elements'][0]
 assert animated['animations']==p['course']['slides'][3]['elements'][0]['animations']
 assert 'Texto animado' in animated['htmlContent']
 html=styled['course']['slides'][0]['elements'][0]['htmlContent']
 assert 'Texto integral' in html and 'Captura acessível' in html and 'capture.png' in html
 assert styled['course']['slides'][0]['notes']=='Nota original'
 assert 'Slide original' in rows[-1]['html']
 with pytest.raises(ValueError):revision_plan(p,['missing'],{})
 p['course']['slides'][0]['elements']=[{'type':'html','htmlContent':'<img src="https://example.test/original.png" alt="Gamma original">'}]
 converted,_=revision_plan(p,['lesson'],{})
 assert 'https://example.test/original.png' in converted['course']['slides'][0]['elements'][0]['htmlContent']

class Cursor:
 def __init__(self,rows):self.rows=iter(copy.deepcopy(rows))
 def __aiter__(self):return self
 async def __anext__(self):
  try:return next(self.rows)
  except StopIteration:raise StopAsyncIteration
def matches(row,query):
 return all(any(matches(row,q) for q in v) if k=='$or' else row.get(k) in v['$in'] if isinstance(v,dict) else row.get(k)==v for k,v in query.items())
class Collection:
 def __init__(self,rows=()):self.rows=copy.deepcopy(list(rows));self.writes=[]
 def find(self,q):return Cursor([r for r in self.rows if matches(r,q)])
 async def find_one(self,q,*args):return copy.deepcopy(next((r for r in self.rows if matches(r,q)),None))
 async def update_one(self,q,update,**kwargs):
  self.writes.append((q,update));
  if not any(matches(r,q) for r in self.rows):self.rows.append(copy.deepcopy(update['$setOnInsert']))
class DB:
 def __init__(self,p):
  self.data={'projects':Collection([p]),'questions':Collection([{'id':'question-original','projectId':PID,'text':'Pergunta','explanation':'Reforço','difficulty':2}]),'project_assets':Collection([{'project_id':PID,'filename':'capture.png','data':'original-binary'}])}
 def __getitem__(self,k):return self.data.setdefault(k,Collection())
 def __getattr__(self,k):return self[k]

@pytest.mark.asyncio
async def test_copy_owns_assets_and_banks_idempotently_without_modifying_source(tmp_path):
 p=project();before=copy.deepcopy(p);db=DB(p);request_id=str(uuid.uuid4())
 result=await create_revision(db,p,['lesson','picture'],{},fingerprint(p),request_id,'editor','now',tmp_path)
 assert p==before and db.projects.rows[0]==before and len(db.projects.rows)==2
 clone=db.projects.rows[1];assert clone['id']==result['projectId'] and clone['companyId']=='tenant'
 assert len(clone['course']['slides'])==5 and clone['course']['slides'][2]==p['course']['slides'][2]
 qid=clone['course']['slides'][1]['elements'][0]['quizConfig']['questionIds'][0]
 assert qid!='question-original' and db.questions.rows[1]['text']=='Pergunta'
 assert db.questions.rows[1]['projectId']==clone['id']
 assert db.project_assets.rows[1]['data']=='original-binary' and db.project_assets.rows[1]['project_id']==clone['id']
 assert PID not in clone['course']['slides'][0]['elements'][0]['htmlContent']
 await create_revision(db,p,['lesson','picture'],{},fingerprint(p),request_id,'editor','now',tmp_path)
 assert len(db.projects.rows)==2
 with pytest.raises(ValueError,match='outras opções'):await create_revision(db,p,['lesson'],{},fingerprint(p),request_id,'editor','now',tmp_path)

@pytest.mark.asyncio
async def test_stale_preview_or_missing_media_never_publishes_clone(tmp_path):
 p=project();db=DB(p)
 with pytest.raises(ValueError,match='mudou'):await create_revision(db,p,['lesson'],{},'stale',str(uuid.uuid4()),'editor','now',tmp_path)
 db.project_assets.rows=[]
 with pytest.raises(ValueError,match='mídia'):await create_revision(db,p,['lesson'],{},fingerprint(p),str(uuid.uuid4()),'editor','now',tmp_path)
 assert len(db.projects.rows)==1

@pytest.mark.asyncio
async def test_preview_and_create_routes_enforce_editor_and_project_access(monkeypatch):
 from routes import projects_crud as routes
 from fastapi import HTTPException
 p=project();db=DB(p);monkeypatch.setattr(routes,'db',db)
 from unittest.mock import AsyncMock
 access=AsyncMock(return_value=p);monkeypatch.setattr(routes,'load_authorized_project',access)
 user={'user_id':'u','role':'editor'}
 data=await routes.astryx_revision_options(PID,user)
 assert data['slides'][0]['eligible'];access.assert_awaited_once_with(PID,user)
 with pytest.raises(HTTPException) as error:await routes.astryx_revision_options(PID,{'role':'student'})
 assert error.value.status_code==403
