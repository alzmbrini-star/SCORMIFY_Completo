"""Central configuration for Scormify text-generation models.

OpenAI is the canonical provider. ``EMERGENT_LLM_KEY`` is accepted only as a
temporary compatibility fallback so existing installations can be migrated
without an abrupt outage.
"""

from __future__ import annotations

import os


def openai_api_key(*, allow_legacy: bool = True) -> str:
    """Return the server-side OpenAI secret, optionally accepting the old key."""
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if key:
        return key
    if allow_legacy:
        return os.environ.get("EMERGENT_LLM_KEY", "").strip()
    return ""


def openai_text_model(*env_names: str, default: str = "gpt-4o") -> str:
    """Resolve a feature-specific model without changing existing defaults."""
    for name in (*env_names, "OPENAI_TEXT_MODEL"):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return default


def require_openai_api_key(*, allow_legacy: bool = True) -> str:
    key = openai_api_key(allow_legacy=allow_legacy)
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    return key
