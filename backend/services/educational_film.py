"""Pure film validation, revision-bound approvals and itemized media estimates."""
import copy
import hashlib
import json
import math
import re
from typing import List, Literal
from pydantic import BaseModel, Field, ConfigDict

RATES_VERSION = '2026-11-18-v1'
VIDEO_RATES = {'gen4_turbo': .05, 'gen4.5': .12}


class Character(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=8, max_length=400)
    voiceId: str = Field(default='', max_length=100)


class Scene(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=1, max_length=100)
    visual: str = Field(max_length=600)
    narration: str = Field(max_length=110)
    speaker: Literal['narrator','character1','character2','character3','character4','character5','character6'] = 'narrator'
    visibleCharacters: List[int] = Field(default_factory=list, max_length=3)
    duration: Literal[5,10] = 10


class Board(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=3, max_length=160)
    topic: str = Field(min_length=20, max_length=12000)
    style: Literal['2d','3d'] = '2d'
    model: Literal['gen4_turbo','gen4.5'] = 'gen4_turbo'
    characters: List[Character] = Field(min_length=1, max_length=6)
    scenes: List[Scene] = Field(min_length=3, max_length=30)
    narratorVoice: str = Field(default='', max_length=100)
    allowOtherVoices: bool = False
    music: bool = True
    musicPrompt: str = Field(default='Trilha instrumental educativa suave, acolhedora, sem vozes, sem imitar artistas.', max_length=800)
    musicVolume: int = Field(default=15, ge=0, le=35)


def normalized_board(value, complete=False):
    board = Board.model_validate(value).model_dump()
    for i, scene in enumerate(board['scenes']):
        if complete and (len(scene['visual'].strip()) < 15 or not scene['narration'].strip()):
            raise ValueError(f'Complete a ação visual e a fala da cena {i+1}.')
        if len(scene['narration']) > (55 if scene['duration']==5 else 110):
            raise ValueError(f'Cena {i+1}: reduza a fala para caber na duração; não será congelado o último quadro.')
        if scene['speaker']!='narrator' and int(scene['speaker'].removeprefix('character'))>len(board['characters']):
            raise ValueError('A cena pede um personagem que não foi definido.')
        cast=scene['visibleCharacters']
        if len(set(cast))!=len(cast) or any(n<1 or n>len(board['characters']) for n in cast):
            raise ValueError(f'Cena {i+1}: selecione personagens válidos, sem repetição.')
        if complete and len(board['characters'])>3 and not cast:
            raise ValueError(f'Cena {i+1}: informe até três personagens visíveis; divida cenas de grupo em planos.')
        # Preserve revisions and approvals of saved films created before cast selection existed.
        if not cast:scene.pop('visibleCharacters',None)
    if complete and board['music'] and len(board['musicPrompt'].strip())<10:
        raise ValueError('Descreva uma trilha instrumental original, sem citar artistas.')
    return board


def revision(board):
    return hashlib.sha256(json.dumps(board,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def voice_for(board,scene):
    if scene['speaker']=='narrator':return board['narratorVoice']
    return board['characters'][int(scene['speaker'][-1])-1]['voiceId'] or board['narratorVoice']


def media_keys(board):
    return [*(f'character_{i}' for i in range(len(board['characters']))),
            *(k for i in range(len(board['scenes'])) for k in (f'frame_{i}',f'voice_{i}',f'video_{i}')),
            *(['music'] if board['music'] else [])]


def quote(film):
    board=normalized_board(film['board'],True)
    if film.get('storyboardApproval')!=revision(board):raise ValueError('Aprove primeiro a versão atual do storyboard.')
    operations=film.get('operations',{})
    if any(v.get('status') in ('sending','unknown') for v in operations.values()):
        raise ValueError('Há envio pago não confirmado. Não haverá repetição automática; confira o provedor antes de continuar.')
    needed=lambda key: operations.get(key,{}).get('status') not in ('ready','submitted')
    # Submitted tasks are only polled again; their paid creation is not repeated.
    images=sum(needed(k) for k in media_keys(board) if k.startswith(('character_','frame_')))
    seconds=sum(s['duration'] for i,s in enumerate(board['scenes']) if needed(f'video_{i}'))
    chars=sum(len(s['narration']) for i,s in enumerate(board['scenes']) if needed(f'voice_{i}'))
    voice_calls=sum(needed(f'voice_{i}') for i in range(len(board['scenes'])))
    duration=sum(s['duration'] for s in board['scenes'])
    items=[{'label':'Imagens Gen-4 Image 720p','quantity':images,'unit':'imagens','usd':round(images*.05,4)},
           {'label':'Vídeos '+board['model'],'quantity':seconds,'unit':'segundos','usd':round(seconds*VIDEO_RATES[board['model']],4)},
           {'label':'Voz PT-BR ElevenLabs (estimativa conservadora)','quantity':chars,'unit':'caracteres','usd':round(max(chars*.0001,voice_calls*.01),4)},
           {'label':'Trilha instrumental Runway','quantity':duration if board['music'] and needed('music') else 0,'unit':'segundos',
            'usd':round(duration/60*.20,4) if board['music'] and needed('music') else 0}]
    total=round(sum(i['usd'] for i in items),4)
    payload={'revision':revision(board),'ratesVersion':RATES_VERSION,'items':items,'estimatedUsd':total,
             'suggestedCeilingUsd':math.ceil(total*1.2*100)/100,'duration':duration,'imageCount':images,
             'disclaimer':'Estimativa em USD, sem impostos, câmbio ou infraestrutura. A cobrança real depende da tarifa/conta dos provedores. O teto controla as chamadas planejadas; não é garantia de valor da fatura. Sem novas tentativas pagas automáticas.'}
    payload['id']=revision(payload)
    return payload


def require_ready(film,expected_revision):
    if film.get('revision')!=expected_revision:raise ValueError('O storyboard mudou. Reabra e aprove a versão atual.')
    if film.get('storyboardApproval')!=expected_revision:raise ValueError('Storyboard não aprovado.')
    budget=film.get('budgetApproval') or {}
    fresh=quote(film)
    if budget.get('quoteId')!=fresh['id'] or budget.get('revision')!=expected_revision:
        raise ValueError('Orçamento não aprovado ou desatualizado.')
    if not math.isfinite(float(budget.get('ceilingUsd',0))) or budget['ceilingUsd']<fresh['estimatedUsd']:
        raise ValueError('O orçamento excede o limite autorizado.')
    board=normalized_board(film['board'],True)
    for scene in board['scenes']:
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}',voice_for(board,scene)):
            raise ValueError('Selecione a voz PT-BR do narrador e dos personagens que falam.')
    return board


def project_shell(film,owner,company_id,created):
    return {'id':film['projectId'],'name':film['board']['title']+' — Filme educativo',
        'description':'Projeto independente de filme educativo. O curso de origem não é alterado.',
        'userId':owner,'companyId':company_id,'source':'educational_film','status':'draft','createdAt':created,'updatedAt':created,
        'course':{'id':film['projectId'],'metadata':{'title':film['board']['title']},'width':1280,'height':720,
          'slides':[{'id':film['slideId'],'title':film['board']['title'],'order':0,'width':1280,'height':720,'background':'#0f172a','elements':[],'duration':5}],
          'questions':[]}}
