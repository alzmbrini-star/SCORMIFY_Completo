import asyncio,copy
from datetime import datetime,timezone,timedelta
from unittest.mock import AsyncMock
import pytest
from services import film_exchange as fx
from services.creator_guide import GUIDE
from tests.test_educational_films import scope,film

NOW=datetime(2026,11,19,14,0,tzinfo=timezone.utc)

def test_parses_most_recent_official_sale_rate_preserving_publication_date():
    data=fx.parse_reference([{'data':'17/11/2026','valor':'5.7851'},{'data':'18/11/2026','valor':'5.8102'}],NOW)
    assert data['rate']==5.8102 and data['asOfDate']=='2026-11-18'
    assert data['retrievedAt']==NOW.isoformat() and data['source'].startswith('Banco Central')
    assert data['base']=='USD' and data['currency']=='BRL'

@pytest.mark.parametrize('rows',[
    [],{},[{'data':'20/11/2026','valor':'6'}],[{'data':'01/11/2026','valor':'5'}],
    [{'data':'18/11/2026','valor':x} for x in ['nan','inf','0','-1','1000']],
    [{'data':'not a date','valor':'5.5'}],[{'data':'18/11/2026','valor':'bad'}]])
def test_invalid_future_stale_or_nonfinite_quotes_have_no_fixed_fallback(rows):
    with pytest.raises(ValueError):fx.parse_reference(rows,NOW)

@pytest.fixture
def clean(monkeypatch):
    for key,value in [('_cache',None),('_fresh_until',0),('_retry_after',0),('_lock',asyncio.Lock())]:monkeypatch.setattr(fx,key,value)

@pytest.mark.asyncio
async def test_cache_is_shared_bounded_and_does_not_return_mutable_state(clean,monkeypatch):
    sample=fx.parse_reference([{'data':'18/11/2026','valor':'5.8102'}],NOW)
    fetch=AsyncMock(return_value=sample);monkeypatch.setattr(fx,'_fetch_reference',fetch)
    results=await asyncio.gather(*(fx.usd_brl_reference() for _ in range(6)))
    fetch.assert_awaited_once();results[0]['rate']=999
    assert (await fx.usd_brl_reference())['rate']==5.8102

@pytest.mark.asyncio
async def test_outage_explicitly_returns_no_rate_and_cools_down(clean,monkeypatch):
    fetch=AsyncMock(side_effect=RuntimeError('private provider diagnostic'))
    monkeypatch.setattr(fx,'_fetch_reference',fetch)
    first=await fx.usd_brl_reference();second=await fx.usd_brl_reference()
    assert first==second and first['available'] is False and 'rate' not in first
    assert 'private' not in str(first);fetch.assert_awaited_once()

@pytest.mark.asyncio
async def test_recent_cached_rate_is_labeled_stale_but_old_cache_is_not_used(clean,monkeypatch):
    actual=datetime.now(timezone.utc)
    sample=fx.parse_reference([{'data':actual.strftime('%d/%m/%Y'),'valor':'5.8102'}],actual-timedelta(hours=1) if actual.hour>0 else actual)
    monkeypatch.setattr(fx,'_cache',sample);monkeypatch.setattr(fx,'_fetch_reference',AsyncMock(side_effect=ValueError()))
    result=await fx.usd_brl_reference()
    assert result['stale'] and result['asOfDate']==sample['asOfDate'] and result['retrievedAt']==sample['retrievedAt'] and result['notice']
    fx._cache={**sample,'retrievedAt':(actual-timedelta(hours=25)).isoformat()}
    assert not (await fx.usd_brl_reference())['available']

@pytest.mark.asyncio
async def test_exchange_route_is_authorized_read_only_and_does_not_change_approvals(monkeypatch):
    f=film(True);before=copy.deepcopy(f);s=scope(f)
    monkeypatch.setattr(fx,'usd_brl_reference',AsyncMock(return_value={'available':True,'rate':5.8102,'asOfDate':'2026-11-18'}))
    result=await s.exchange_rate({'id':'u','companyId':'c'})
    assert result['rate']==5.8102 and f==before;s.can_edit.assert_called_once()
    s.run.assert_not_awaited();s.db.projects.update_one.assert_not_awaited();s.db.educational_films.update_one.assert_not_awaited()

def test_tutor_documents_brl_reference_and_usd_authority():
    text=str(next(t for t in GUIDE if t['id']=='film-budget-brl'))
    for term in ('Limite para aprovação (R$)','Banco Central','SGS 1','último dia útil','IOF','não inventa taxa fixa','dólares'):
        assert term.casefold() in text.casefold()
