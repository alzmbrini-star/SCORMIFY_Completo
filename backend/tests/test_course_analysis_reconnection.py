import ast
import asyncio
import copy
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
import pytest
from fastapi import Depends, Request, HTTPException


def scope(cached):
    path=Path(__file__).resolve().parents[1]/'routes/agent.py'
    node=next(n for n in ast.parse(path.read_text(encoding='utf-8')).body if getattr(n,'name','')=='agent_analyze_course')
    project={'id':'p','source':'manual','course':{'slides':[{'id':'s','elements':[]}]}}
    load=AsyncMock(return_value=project)
    collection=SimpleNamespace(find_one=AsyncMock(return_value=cached),delete_one=AsyncMock(),update_one=AsyncMock())
    env={'router':SimpleNamespace(post=lambda *a,**k:lambda f:f),'Request':Request,'Depends':Depends,'require_auth':lambda:None,
         'load_authorized_project':load,'db':SimpleNamespace(analysis_cache=collection),'datetime':datetime,'timezone':timezone,
         'asyncio':asyncio,'os':SimpleNamespace(environ={}), 'uuid':uuid,'HTTPException':HTTPException,'logger':MagicMock()}
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),env)
    return SimpleNamespace(**env),project,collection


@pytest.mark.asyncio
@pytest.mark.parametrize('status',['processing','error','done',None])
async def test_status_read_never_starts_deletes_or_mutates(status):
    row=None if status is None else {'status':status,'runId':'active','updatedAt':datetime.now(timezone.utc).isoformat(),
        'result':{'overallScore':7,'improvements':[]},'error':'Falha da execução'}
    s,project,collection=scope(row);before=copy.deepcopy(project)
    request=SimpleNamespace(query_params={'status_only':'true'})
    first=await s.agent_analyze_course('p',request,{'id':'u'})
    second=await s.agent_analyze_course('p',request,{'id':'u'})
    assert first==second and project==before
    collection.delete_one.assert_not_awaited();collection.update_one.assert_not_awaited()
    assert first.get('status') == (status if status in ('processing','error') else 'not_started' if status is None else None)


@pytest.mark.asyncio
async def test_stale_status_does_not_restart_paid_work():
    s,_,collection=scope({'status':'processing','updatedAt':(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat()})
    result=await s.agent_analyze_course('p',SimpleNamespace(query_params={'status_only':'true'}),{})
    assert result['status']=='error' and 'Retomar análise' in result['error']
    collection.update_one.assert_not_awaited();collection.delete_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_authorization_precedes_status_cache():
    s,_,collection=scope(None)
    s.load_authorized_project.side_effect=HTTPException(404,'Project not found')
    with pytest.raises(HTTPException):
        await s.agent_analyze_course('other',SimpleNamespace(query_params={'status_only':'true'}),{})
    collection.find_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_completed_initial_response_can_be_read_again_after_disconnect():
    s,_,collection=scope({'status':'done','result':{'overallScore':7,'improvements':[]}})
    result=await s.agent_analyze_course('p',SimpleNamespace(query_params={'resume_partial':'true'}),{})
    assert result['overallScore']==7
    collection.delete_one.assert_not_awaited();collection.update_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_interrupted_legacy_run_requires_explicit_resume_and_preserves_project(monkeypatch):
    s,p,collection=scope({'status':'processing','updatedAt':datetime.now(timezone.utc).isoformat()})
    before=copy.deepcopy(p)
    response=await s.agent_analyze_course('p',SimpleNamespace(query_params={'status_only':'true'}),{})
    assert response['status']=='error' and 'interrompida' in response['error']
    collection.update_one.assert_not_awaited()
    thread=MagicMock();monkeypatch.setattr('threading.Thread',thread)
    response=await s.agent_analyze_course('p',SimpleNamespace(query_params={'resume_partial':'true'}),{})
    assert response['status']=='processing' and p==before
    update=collection.update_one.call_args.args[1]['$set']
    assert update['runId'] and update['heartbeatAt']
    thread.return_value.start.assert_called_once()


def test_heartbeat_detects_deployments_dead_workers_and_leaves_live_work_alone():
    from services.course_analysis_jobs import interrupted
    now=datetime.now(timezone.utc)
    cache={'runId':'r','deploymentRevision':'revision','heartbeatAt':now.isoformat()}
    assert not interrupted(cache,'revision',now)
    assert interrupted(cache,'new-revision',now)
    assert interrupted({**cache,'heartbeatAt':(now-timedelta(minutes=3)).isoformat()},'revision',now)
    assert interrupted({'status':'processing','updatedAt':now.isoformat()},'revision',now)


@pytest.mark.asyncio
async def test_changed_course_does_not_reuse_prior_revision_result():
    s,_,collection=scope({'status':'done','sourceUpdatedAt':'older','result':{'overallScore':7,'improvements':[]}})
    result=await s.agent_analyze_course('p',SimpleNamespace(query_params={'status_only':'true'}),{})
    assert result['status']=='not_started'
    collection.update_one.assert_not_awaited()
