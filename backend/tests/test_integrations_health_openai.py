import pytest


@pytest.mark.asyncio
async def test_openai_health_uses_official_models_endpoint(monkeypatch):
    from routes import health

    seen = {}

    class Response:
        status_code = 200
        text = ""

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, headers=None, **kwargs):
            seen["url"] = url
            seen["authorization"] = (headers or {}).get("Authorization")
            return Response()

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_TEXT_MODEL", "gpt-test")
    monkeypatch.setattr(health.httpx, "AsyncClient", Client)

    result = await health._check_openai()

    assert result["status"] == "ok"
    assert result["provider"] == "OpenAI"
    assert result["model"] == "gpt-test"
    assert seen == {
        "url": "https://api.openai.com/v1/models",
        "authorization": "Bearer sk-test",
    }


@pytest.mark.asyncio
async def test_openai_health_reports_current_variable_name(monkeypatch):
    from routes import health

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = await health._check_openai()

    assert result["status"] == "not_configured"
    assert result["error"] == "OPENAI_API_KEY not set"
