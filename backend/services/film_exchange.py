"""Read-only official USD/BRL reference; no AI, film writes or fixed fallback rates."""
import asyncio
import copy
import math
import time
from datetime import datetime,timezone,timedelta
import httpx

URL='https://api.bcb.gov.br/dados/serie/bcdata.sgs.1/dados/ultimos/10?formato=json'
SOURCE_URL='https://dadosabertos.bcb.gov.br/dataset/1-taxa-de-cambio---livre---dolar-americano-venda---diario'
_cache=None
_fresh_until=0
_retry_after=0
_lock=asyncio.Lock()

def parse_reference(rows,now):
    if not isinstance(rows,list) or not 1<=len(rows)<=10:raise ValueError('Invalid exchange data')
    valid=[]
    for row in rows:
        try:
            day=datetime.strptime(row['data'],'%d/%m/%Y').date()
            rate=float(row['valor'])
            if math.isfinite(rate) and .1<=rate<=100 and timedelta(0)<=now.date()-day<=timedelta(days=7):
                valid.append((day,rate))
        except (KeyError,TypeError,ValueError):continue
    if not valid:raise ValueError('No recent official exchange rate')
    day,rate=max(valid,key=lambda item:item[0])
    return {'available':True,'base':'USD','currency':'BRL','rate':rate,'asOfDate':day.isoformat(),
        'retrievedAt':now.isoformat(),'source':'Banco Central do Brasil · dólar venda (SGS 1)',
        'sourceUrl':SOURCE_URL,'stale':False}

async def _fetch_reference():
    async with httpx.AsyncClient(timeout=8,follow_redirects=False) as client:
        response=await client.get(URL)
        response.raise_for_status()
        if len(response.content)>24000:raise ValueError('Oversize exchange response')
        return parse_reference(response.json(),datetime.now(timezone.utc))

def _unavailable():
    now=datetime.now(timezone.utc)
    if _cache:
        fetched=datetime.fromisoformat(_cache['retrievedAt'])
        quoted=datetime.fromisoformat(_cache['asOfDate']).date()
        if now-fetched<=timedelta(hours=24) and timedelta(0)<=now.date()-quoted<=timedelta(days=7):
            return {**copy.deepcopy(_cache),'stale':True,
                'notice':'Não foi possível atualizar a cotação. Exibindo a última consulta válida; confira a data antes de aprovar.'}
    return {'available':False,'notice':'Cotação em reais indisponível no momento. Consulte novamente; valores em dólares permanecem como referência. Nenhum orçamento foi aprovado.'}

async def usd_brl_reference():
    global _cache,_fresh_until,_retry_after
    async with _lock:
        current=time.monotonic()
        if _cache and current<_fresh_until:return copy.deepcopy(_cache)
        if current<_retry_after:return _unavailable()
        try:
            result=await _fetch_reference()
            _cache=result;_fresh_until=time.monotonic()+600;_retry_after=0
            return copy.deepcopy(result)
        except Exception:
            _retry_after=time.monotonic()+60
            return _unavailable()
