"""
Regression: HeyGen `/v2/avatars` upstream is slow (~60s+) and exceeds the
60s gateway timeout. We mitigate via:
  - in-memory + MongoDB cache (TTL 30 min)
  - background warm-up on server startup + periodic
  - stale-while-revalidate when cache exists but expired
  - tight 22s timeout on live fetches so we never block past the gateway cap
  - friendly 503 "warming up" message instead of letting the gateway 502
"""
import sys, asyncio
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from routes import deps, heygen as heygen_routes


def _reset_cache():
    deps.heygen_avatars_cache["data"] = None
    deps.heygen_avatars_cache["timestamp"] = None


def _fake_response(status: int, json_body=None, text: str = ""):
    r = MagicMock()
    r.status_code = status
    r.json = MagicMock(return_value=json_body or {})
    r.text = text
    return r


@pytest.mark.asyncio
async def test_avatars_returns_friendly_503_when_no_cache_and_upstream_times_out():
    """Cold cache + upstream timeout → friendly 503, NOT 502/500."""
    _reset_cache()

    async def fake_heygen_request(*args, **kwargs):
        import httpx
        raise httpx.RequestError("connection timeout")

    # Also stub the DB cache load to return False (empty)
    async def fake_load(): return False
    # And stub the background refresh so we don't actually call upstream
    async def fake_refresh(**kwargs): return False

    with patch.object(heygen_routes, "heygen_request", side_effect=fake_heygen_request), \
         patch.object(heygen_routes, "_load_heygen_avatars_cache_from_db", fake_load), \
         patch.object(heygen_routes, "_refresh_heygen_avatars_cache", fake_refresh), \
         patch.object(heygen_routes, "HEYGEN_API_KEY", "fake-key"):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await heygen_routes.list_heygen_avatars(limit=10)
        assert exc_info.value.status_code == 503
        assert "warming up" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_avatars_returns_cached_data_instantly_when_fresh():
    """Fresh cache → response from RAM, no upstream call."""
    _reset_cache()
    deps.heygen_avatars_cache["data"] = [
        {"avatar_id": "a1", "avatar_name": "Alice", "gender": "female"},
        {"avatar_id": "a2", "avatar_name": "Bob", "gender": "male"},
    ]
    deps.heygen_avatars_cache["timestamp"] = datetime.now(timezone.utc)

    fake_request = AsyncMock()  # should not be called

    with patch.object(heygen_routes, "heygen_request", fake_request), \
         patch.object(heygen_routes, "HEYGEN_API_KEY", "fake-key"):
        result = await heygen_routes.list_heygen_avatars(limit=10)
        assert result["total"] == 2
        assert result["cached"] is True
        assert result["stale"] is False
        assert sorted(result["available_genders"]) == ["female", "male"]
        # critical: upstream NOT called when cache is fresh
        fake_request.assert_not_called()

    _reset_cache()


@pytest.mark.asyncio
async def test_avatars_serves_stale_when_upstream_fails_but_cache_exists():
    """Stale cache + upstream times out → serve stale data, NOT 503."""
    _reset_cache()
    deps.heygen_avatars_cache["data"] = [
        {"avatar_id": "a1", "avatar_name": "Old", "gender": "female"},
    ]
    # Make cache expired (older than TTL)
    deps.heygen_avatars_cache["timestamp"] = datetime.now(timezone.utc) - timedelta(seconds=deps.heygen_avatars_cache["ttl"] + 100)

    async def fake_heygen_request(*args, **kwargs):
        import httpx
        raise httpx.RequestError("timeout")
    async def fake_refresh(**kwargs): return False

    with patch.object(heygen_routes, "heygen_request", side_effect=fake_heygen_request), \
         patch.object(heygen_routes, "_refresh_heygen_avatars_cache", fake_refresh), \
         patch.object(heygen_routes, "HEYGEN_API_KEY", "fake-key"):
        # Stale but present cache means must_block_on_fetch is False (we
        # already have data); the endpoint serves cache + schedules refresh.
        result = await heygen_routes.list_heygen_avatars(limit=10)
        assert result["total"] == 1
        assert result["cached"] is True
        # stale is True only when we tried to refresh and fell back; with
        # stale-while-revalidate path the live fetch is skipped, so we just
        # serve cache as-is.

    _reset_cache()


@pytest.mark.asyncio
async def test_avatars_gender_filter_works_on_cached_data():
    _reset_cache()
    deps.heygen_avatars_cache["data"] = [
        {"avatar_id": "a1", "avatar_name": "Alice", "gender": "female"},
        {"avatar_id": "a2", "avatar_name": "Bob", "gender": "male"},
        {"avatar_id": "a3", "avatar_name": "Carla", "gender": "female"},
    ]
    deps.heygen_avatars_cache["timestamp"] = datetime.now(timezone.utc)

    with patch.object(heygen_routes, "HEYGEN_API_KEY", "fake-key"):
        result = await heygen_routes.list_heygen_avatars(limit=10, gender="female")
        assert result["total"] == 2
        assert all(a["gender"] == "female" for a in result["avatars"])
        # available_genders still reflects the full list (so the UI can show all filter options)
        assert sorted(result["available_genders"]) == ["female", "male"]

    _reset_cache()


@pytest.mark.asyncio
async def test_force_refresh_bypasses_cache():
    """force_refresh=True must trigger a live upstream call."""
    _reset_cache()
    deps.heygen_avatars_cache["data"] = [{"avatar_id": "old", "avatar_name": "Old", "gender": "female"}]
    deps.heygen_avatars_cache["timestamp"] = datetime.now(timezone.utc)

    new_payload = {"data": {"avatars": [{"avatar_id": "new", "avatar_name": "New", "gender": "male"}]}}

    async def fake_heygen_request(*args, **kwargs):
        return _fake_response(200, json_body=new_payload)

    with patch.object(heygen_routes, "heygen_request", side_effect=fake_heygen_request), \
         patch.object(heygen_routes, "HEYGEN_API_KEY", "fake-key"), \
         patch.object(heygen_routes, "db", None):  # skip Mongo persist
        result = await heygen_routes.list_heygen_avatars(limit=10, force_refresh=True)
        assert result["total"] == 1
        assert result["avatars"][0]["avatar_id"] == "new"
        # force_refresh path: cached flag should be False
        assert result["cached"] is False

    _reset_cache()


@pytest.mark.asyncio
async def test_missing_api_key_returns_500_immediately():
    _reset_cache()
    with patch.object(heygen_routes, "HEYGEN_API_KEY", ""):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await heygen_routes.list_heygen_avatars()
        assert exc_info.value.status_code == 500
        assert "api key" in exc_info.value.detail.lower()
