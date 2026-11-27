import asyncio
import copy
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from routes.export import _export_snapshot, _start_export_task, _active_export_tasks


@pytest.mark.asyncio
async def test_export_options_override_snapshot_without_saving_course():
    project = {'singlePageMode': False, 'enableVlibras': True,
               'course': {'slides': [{'id': 'original', 'elements': [{'type': 'quiz'}]}]}}
    before = copy.deepcopy(project)
    request = AsyncMock()
    request.json.return_value = {'singlePage': True, 'enableVlibras': False}
    snapshot, single = await _export_snapshot(request, project)
    assert single and snapshot['singlePageMode'] and not snapshot['enableVlibras']
    assert project == before and snapshot['course'] == before['course']


@pytest.mark.asyncio
async def test_defaults_and_guided_path_preserve_existing_behavior():
    request = AsyncMock()
    request.json.side_effect = ValueError('empty body')
    assert (await _export_snapshot(request, {'singlePageMode': True}))[1]
    request.json.side_effect = None
    request.json.return_value = {'singlePage': True}
    assert not (await _export_snapshot(request, {'course': {'metadata': {'guidedPath': True}}}))[1]


@pytest.mark.asyncio
@pytest.mark.parametrize('body', [[], {'singlePage': 'false'}, {'enableVlibras': 1}])
async def test_invalid_options_rejected(body):
    request = AsyncMock()
    request.json.return_value = body
    with pytest.raises(HTTPException) as error:
        await _export_snapshot(request, {})
    assert error.value.status_code == 422


@pytest.mark.asyncio
async def test_document_task_retained_until_completion():
    release = asyncio.Event()
    task = _start_export_task(release.wait())
    assert task in _active_export_tasks
    release.set()
    await task
    await asyncio.sleep(0)
    assert task not in _active_export_tasks
