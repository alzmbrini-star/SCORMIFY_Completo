"""Regression test for the Tutor IA friendly error mapping (2026-02).

When the upstream LLM call fails with one of the known operational
errors (budget exceeded, rate limit, invalid key), the `/api/tutor/chat`
endpoint must respond with a human-friendly message in Portuguese
instead of raw stack-trace text. Frontend `tutor.js` shows the friendly
detail verbatim when present.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from routes.admin import _map_tutor_llm_error  # noqa: E402


# Real-world exception strings sampled from production traces.
_BUDGET_EXC = Exception(
    "litellm.BadRequestError: OpenAIException - Budget has been "
    "exceeded! Current cost: 68.02845, Max budget: 68.0"
)
_RATE_LIMIT_EXC = Exception(
    "litellm.RateLimitError: 429 - Too many requests, please slow down"
)
_INVALID_KEY_EXC = Exception("OpenAI Invalid API Key — unauthorized")
_UNKNOWN_EXC = Exception("Some completely novel failure mode the LLM came up with")


@pytest.mark.parametrize("exc,expected_status,expected_substring", [
    (_BUDGET_EXC, 503, "OpenAI"),
    (_RATE_LIMIT_EXC, 429, "muitas requisições"),
    (_INVALID_KEY_EXC, 503, "chave OpenAI"),
])
def test_known_errors_map_to_friendly_messages(exc, expected_status, expected_substring):
    status, friendly = _map_tutor_llm_error(exc)
    assert status == expected_status
    assert friendly is not None
    assert expected_substring in friendly
    # The raw `litellm` / `OpenAIException` prefix must NOT leak through.
    assert "litellm" not in friendly.lower()
    assert "BadRequestError" not in friendly


def test_unknown_error_returns_none_so_caller_can_fallback():
    """When the error doesn't match any known pattern, the helper must
    return (500, None) so the caller can fall back to the raw text and
    we don't silently hide truly novel failures."""
    status, friendly = _map_tutor_llm_error(_UNKNOWN_EXC)
    assert status == 500
    assert friendly is None


def test_budget_message_contains_actionable_step():
    """Budget message must tell the admin exactly where to top up."""
    _, friendly = _map_tutor_llm_error(_BUDGET_EXC)
    assert "Billing" in friendly
    assert "Usage" in friendly
