"""Authenticated creator help; separate from the public SCORM learner tutor."""
import time,threading
from collections import deque
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from routes.auth import require_auth
from services.creator_guide import topics_for
from services.creator_tutor import answer_question

router=APIRouter(prefix='/creator-tutor',tags=['Creator Tutor'])
_calls={};_lock=threading.Lock()

class HelpMessage(BaseModel):
    role:Literal['user','assistant']
    content:str=Field(min_length=1,max_length=1500)
class HelpRequest(BaseModel):
    message:str=Field(min_length=1,max_length=2000)
    path:str=Field(default='',max_length=180)
    history:list[HelpMessage]=Field(default_factory=list,max_length=8)

def check_rate(owner):
    now=time.monotonic()
    with _lock:
        for key in list(_calls):
            if not _calls[key] or _calls[key][-1]<now-60:_calls.pop(key,None)
        if owner not in _calls and len(_calls)>=2048:raise HTTPException(429,'Tutor ocupado. Tente novamente em um minuto.')
        queue=_calls.setdefault(owner,deque())
        while queue and queue[0]<now-60:queue.popleft()
        if len(queue)>=12:raise HTTPException(429,'Aguarde um minuto antes de enviar novas perguntas.',headers={'Retry-After':'60'})
        queue.append(now)

@router.get('/guide')
async def guide(path:str='',user:dict=Depends(require_auth)):
    return {'topics':[{k:t[k] for k in ('id','title','steps','link')} for t in topics_for(user,path[:180])]}

@router.post('/chat')
async def chat(body:HelpRequest,user:dict=Depends(require_auth)):
    if not body.message.strip():raise HTTPException(422,'Digite uma pergunta para o Tutor.')
    check_rate(user['user_id'])
    return await answer_question(body.message.strip(),user,body.path,[m.model_dump() for m in body.history])
