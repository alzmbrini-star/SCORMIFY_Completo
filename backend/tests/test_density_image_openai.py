import base64
import io
from types import SimpleNamespace

import pytest
from PIL import Image

from services.openai_image import generate_openai_image


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
