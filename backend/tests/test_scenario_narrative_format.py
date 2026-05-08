"""Tests for the scenario narrative formatter heuristic.

The LLM generates long walls of text with embedded dialogue for scenario
endings. Our formatter splits on blank lines and detects quoted blocks
(>40 chars between paired quotes) so they render as highlighted cards
instead of inline text — matching the JS implementation in
sp_runtime/runtime.js, export_assets/scenario-controller.js and
components/scenario/ScenarioPlayer.jsx.

We re-implement the same heuristic in Python here to lock the behaviour.
"""
import re
import pytest


QUOTE_CHARS_OPEN = ('"', '\u201C', '\u2018', "'")
QUOTE_CHARS_CLOSE = ('"', '\u201D', '\u2019', "'")


def format_narrative(text: str):
    """Return [(kind, content)] list where kind is 'p' or 'quote'."""
    if not text:
        return []
    t = text.replace("\r\n", "\n").strip()
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", t) if p.strip()]
    # Single mega-paragraph: look for a big quoted chunk
    if len(paragraphs) == 1:
        m = re.search(r"(['\"\u2018\u2019\u201C\u201D])([^'\"\u2018\u2019\u201C\u201D]{40,})\1", paragraphs[0])
        if m:
            before = paragraphs[0][:m.start()].strip()
            quote = m.group(2).strip()
            after = paragraphs[0][m.end():].strip()
            paragraphs = []
            if before:
                paragraphs.append(before)
            paragraphs.append({"quoted": quote})
            if after:
                paragraphs.append(after)
    else:
        out = []
        for p in paragraphs:
            if isinstance(p, dict):
                out.append(p)
                continue
            f, l = p[:1], p[-1:]
            if len(p) > 30 and f in QUOTE_CHARS_OPEN and l in QUOTE_CHARS_CLOSE:
                out.append({"quoted": p[1:-1].strip()})
            else:
                out.append(p)
        paragraphs = out
    result = []
    for p in paragraphs:
        if isinstance(p, dict):
            result.append(("quote", p["quoted"]))
        else:
            result.append(("p", p))
    return result


class TestFormatNarrative:
    def test_empty(self):
        assert format_narrative("") == []
        assert format_narrative(None) == []

    def test_single_simple_paragraph(self):
        r = format_narrative("Um parágrafo comum.")
        assert r == [("p", "Um parágrafo comum.")]

    def test_multiple_paragraphs_preserved(self):
        r = format_narrative("Primeiro.\n\nSegundo.\n\nTerceiro.")
        assert len(r) == 3
        assert all(k == "p" for k, _ in r)

    def test_email_inline_extracted_as_quote(self):
        """User's exact bug: email-resposta aparecia inline como parede."""
        text = (
            "Seu email está completo. Agora vamos ver a resposta da Dra. Helena: "
            "'Prezado(a) [Seu Nome], Excelente e-mail. A clareza e a precisão foram impecáveis. "
            "O formulário foi enviado e aguardamos sua presença.' "
            "Sua comunicação foi impecável e consistente."
        )
        r = format_narrative(text)
        kinds = [k for k, _ in r]
        assert "quote" in kinds, f"Quoted block should have been extracted; got {kinds}"
        quote_content = next(c for k, c in r if k == "quote")
        assert "Prezado(a)" in quote_content
        assert "Excelente e-mail" in quote_content

    def test_whole_paragraph_wrapped_in_quotes_becomes_quote(self):
        text = 'Introdução.\n\n"Esta é uma citação inteira bem longa que vale destacar em card."\n\nFim.'
        r = format_narrative(text)
        kinds = [k for k, _ in r]
        assert kinds == ["p", "quote", "p"]

    def test_short_quotes_NOT_extracted(self):
        """Aspas curtas tipo 'ok' ou 'sim' não devem virar cards."""
        text = 'A pessoa disse "sim" e saiu.'
        r = format_narrative(text)
        # Should stay as a single paragraph — the quote is too short
        assert len(r) == 1
        assert r[0][0] == "p"

    def test_preserves_content_fidelity(self):
        """No content should be lost during formatting."""
        text = "Parte 1.\n\n'Mensagem importante com quarenta caracteres aqui XXXX' parte 2"
        r = format_narrative(text)
        # All original text present in some form
        full = " ".join(c for _, c in r)
        assert "Parte 1" in full
        assert "Mensagem importante" in full
        assert "parte 2" in full
