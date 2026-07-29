import pytest
from fastapi import HTTPException

from routes import projects_crud


def _job(**overrides):
    value = {
        "id": "job-1",
        "status": "processing",
        "progress": 10,
        "message": "working",
        "result": None,
    }
    value.update(overrides)
    return value


@pytest.mark.asyncio
async def test_job_from_another_company_is_hidden(monkeypatch):
    async def fake_get_job(_job_id):
        return _job(companyId="company-b", userId="user-b")

    monkeypatch.setattr(projects_crud, "get_job", fake_get_job)

    with pytest.raises(HTTPException) as exc:
        await projects_crud.get_job_status(
            "job-1",
            {"user_id": "user-a", "companyId": "company-a", "role": "editor"},
        )

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_job_from_same_company_is_visible(monkeypatch):
    async def fake_get_job(_job_id):
        return _job(companyId="company-a", userId="user-b")

    monkeypatch.setattr(projects_crud, "get_job", fake_get_job)

    result = await projects_crud.get_job_status(
        "job-1",
        {"user_id": "user-a", "companyId": "company-a", "role": "editor"},
    )

    assert result.id == "job-1"
    assert result.status == "processing"


@pytest.mark.asyncio
async def test_super_admin_can_inspect_legacy_job(monkeypatch):
    async def fake_get_job(_job_id):
        return _job()

    monkeypatch.setattr(projects_crud, "get_job", fake_get_job)

    result = await projects_crud.get_job_status(
        "job-1",
        {"user_id": "root", "role": "super_admin"},
    )

    assert result.id == "job-1"
