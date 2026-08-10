import base64
import io
from types import SimpleNamespace

import pytest
from PIL import Image

from services.openai_image import OpenAIImageError, generate_openai_image


@pytest.mark.asyncio
async def test_openai_image_generation_returns_normalized_jpeg(monkeypatch):
    source = io.BytesIO()
    Image.new("RGBA", (640, 360), (20, 100, 220, 180)).save(source, format="PNG")
    encoded = base64.b64encode(source.getvalue()).decode("ascii")
    captured = {}

    class FakeImages:
        async def generate(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(data=[SimpleNamespace(b64_json=encoded, url=None)])

    class FakeClient:
        def __init__(self, **kwargs):
            captured["client"] = kwargs
            self.images = FakeImages()

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_IMAGE_MODEL", "gpt-test-image")
    monkeypatch.setattr("openai.AsyncOpenAI", FakeClient)

    output = await generate_openai_image("Ilustracao educacional")

    assert output and output.startswith(b"\xff\xd8")
    assert captured["model"] == "gpt-test-image"
    assert captured["size"] == "1536x1024"
    with Image.open(io.BytesIO(output)) as image:
        assert image.mode == "RGB"
        assert image.size == (640, 360)


@pytest.mark.asyncio
async def test_openai_image_generation_without_key_returns_none(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert await generate_openai_image("teste") is None


@pytest.mark.asyncio
async def test_openai_image_retries_compatible_model(monkeypatch):
    source = io.BytesIO()
    Image.new("RGB", (32, 18), "blue").save(source, format="JPEG")
    encoded = base64.b64encode(source.getvalue()).decode("ascii")
    models = []

    class ModelUnavailable(Exception):
        status_code = 400

    class FakeImages:
        async def generate(self, **kwargs):
            models.append(kwargs["model"])
            if len(models) == 1:
                raise ModelUnavailable("model is not available")
            return SimpleNamespace(data=[SimpleNamespace(b64_json=encoded, url=None)])

    class FakeClient:
        def __init__(self, **_kwargs):
            self.images = FakeImages()

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_IMAGE_MODEL", "gpt-image-new")
    monkeypatch.setenv("OPENAI_IMAGE_FALLBACK_MODEL", "gpt-image-1")
    monkeypatch.setattr("openai.AsyncOpenAI", FakeClient)

    assert await generate_openai_image("teste")
    assert models == ["gpt-image-new", "gpt-image-1"]


@pytest.mark.asyncio
async def test_openai_image_preserves_safe_upstream_reason(monkeypatch):
    class QuotaError(Exception):
        status_code = 429

    class FakeImages:
        async def generate(self, **_kwargs):
            raise QuotaError("insufficient quota")

    class FakeClient:
        def __init__(self, **_kwargs):
            self.images = FakeImages()

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("openai.AsyncOpenAI", FakeClient)

    with pytest.raises(OpenAIImageError, match="429.*insufficient quota"):
        await generate_openai_image("teste")
