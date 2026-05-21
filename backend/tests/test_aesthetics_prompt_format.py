"""Regression test: ANALYSIS_PROMPT must be safely formattable.

2026-05-19: production crash — an unescaped `{ "type": ... }` JSON example
in the prompt body caused `KeyError: ' "type"'` when calling
`ANALYSIS_PROMPT.format(slides_data=...)`. This test guards against
any future regression where someone adds a literal `{...}` example to
the prompt without escaping it as `{{...}}`.
"""
import pytest
from routes.aesthetics import ANALYSIS_PROMPT


def test_analysis_prompt_formats_without_keyerror():
    """The prompt is a Python format-string. All `{` and `}` that are NOT
    the `{slides_data}` placeholder must be escaped as `{{` / `}}`."""
    try:
        out = ANALYSIS_PROMPT.format(slides_data="SLIDE 0 [CONTEUDO]: text=hi")
    except (KeyError, IndexError, ValueError) as e:
        pytest.fail(
            f"ANALYSIS_PROMPT has an unescaped brace placeholder — "
            f"`str.format()` raised {type(e).__name__}: {e}. "
            f"Escape literal JSON braces as `{{{{` and `}}}}`."
        )
    # Smoke check: result contains the substitution + the expected sections.
    assert "SLIDE 0 [CONTEUDO]" in out
    assert "score" in out  # response format section preserved
    assert "issues" in out


def test_analysis_prompt_has_only_one_placeholder():
    """Only `{slides_data}` is allowed as a real placeholder."""
    import string
    formatter = string.Formatter()
    placeholders = {
        field_name
        for _, field_name, _, _ in formatter.parse(ANALYSIS_PROMPT)
        if field_name is not None
    }
    assert placeholders == {"slides_data"}, (
        f"Unexpected placeholders in ANALYSIS_PROMPT: {placeholders}. "
        f"Only `slides_data` is allowed; everything else must be escaped."
    )
