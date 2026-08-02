"""Regression tests for contextual media and interactive slide fallbacks."""
from __future__ import annotations

import json
import re

import pytest

from services import ai_agent


def test_contextual_prompt_uses_real_slide_content():
    prompt = ai_agent._build_contextual_image_prompt(
        "data security, compliance",
        {
            "title": "Proteção de dados na universidade corporativa",
            "moduleName": "Governança",
            "elements": [{"content": "<p>Controle de acesso e conformidade com a LGPD.</p>"}],
        },
    )

    assert "Proteção de dados" in prompt
    assert "Governança" in prompt
    assert "LGPD" in prompt
    assert "no random landscape" in prompt


@pytest.mark.asyncio
async def test_failed_image_generation_never_uses_random_picsum(monkeypatch, tmp_path):
    async def no_image(_prompt):
        return None

    async def random_fallback_must_not_run(*_args, **_kwargs):
        raise AssertionError("random image fallback was called")

    monkeypatch.setattr(ai_agent, "_openai_image_bytes", no_image)
    monkeypatch.setattr(ai_agent, "_legacy_gemini_image_bytes", no_image)
    monkeypatch.setattr(ai_agent, "_fetch_picsum_image", random_fallback_must_not_run)

    result = await ai_agent._fetch_stock_image(
        "segurança da informação", str(tmp_path), "project-1", {"title": "Segurança"}
    )
    assert result is None


def test_placeholder_flashcard_html_is_rejected():
    placeholder = """<!DOCTYPE html><html lang='pt-BR'><head>
    <style>/* CSS styles here */</style></head><body>
    <div id='flashcards'>/* Flashcards HTML content here */</div>
    <script>/* JavaScript for flashcard interactions */</script></body></html>"""

    assert not ai_agent._interactive_html_is_functional(placeholder, "flashcard")


def test_flashcard_fallback_has_five_real_cards_and_interactions():
    generated = ai_agent._build_flashcard_fallback_html(
        {
            "title": "Segurança de dados",
            "moduleName": "Governança digital",
            "notes": (
                "O controle de acesso limita dados a pessoas autorizadas. "
                "A autenticação multifator reduz o risco de invasão. "
                "A LGPD orienta o tratamento responsável de dados pessoais. "
                "Backups testados apoiam a continuidade do negócio. "
                "Incidentes devem ser registrados e tratados rapidamente."
            ),
        }
    )

    assert ai_agent._interactive_html_is_functional(generated, "flashcard")
    cards = json.loads(re.search(r"const cards=(\[.*?\]);let index", generated).group(1))
    assert len(cards) == 5
    assert "rotateY(180deg)" in generated
    assert "Não sei" in generated
    assert "Resultado:" in generated
    assert "CSS styles here" not in generated
