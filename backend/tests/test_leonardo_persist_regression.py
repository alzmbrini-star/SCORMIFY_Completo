"""Regression test: every code path that downloads a Leonardo image to disk
MUST also persist it to MongoDB via store_asset_async. Without this, the
image disappears on K8s pod restart in production (ephemeral local disk).

We can't easily run the full ai_agent flow in pytest because it requires
emergent LLM key + Leonardo API + actual generation. Instead, this test
statically verifies that EVERY callsite of `download_image_to_disk` for
Leonardo is followed by a `store_asset_async` call.
"""
import pytest
import re
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent  # /app/backend


def _gather_code_files() -> dict:
    """Return {filepath: content} for every backend Python file that may
    download Leonardo images."""
    out = {}
    for p in BACKEND_ROOT.rglob("*.py"):
        # Skip tests, migrations, virtualenvs
        if any(part in p.parts for part in ("tests", "__pycache__", "node_modules", "venv", ".venv")):
            continue
        try:
            txt = p.read_text(encoding="utf-8")
        except Exception:
            continue
        if "download_image_to_disk" in txt and "leonardo" in txt.lower():
            out[str(p.relative_to(BACKEND_ROOT))] = txt
    return out


def test_every_leonardo_download_persists_to_mongo():
    """Each `download_image_to_disk(...)` call in any Leonardo path MUST
    have `store_asset_async(...)` within the next ~30 lines (same try
    block / function body)."""
    files = _gather_code_files()
    assert files, "No backend files referencing download_image_to_disk found"

    failures = []
    for relpath, content in files.items():
        lines = content.splitlines()
        for idx, line in enumerate(lines):
            if "download_image_to_disk" not in line:
                continue
            # Skip imports / function definitions
            if "import" in line or "def download" in line or "async def download" in line:
                continue
            # Look in the next 40 lines for store_asset_async
            window = "\n".join(lines[idx: idx + 40])
            if "store_asset_async" not in window:
                failures.append(f"{relpath}:{idx+1} → download_image_to_disk without nearby store_asset_async")

    assert not failures, (
        "Leonardo image persistence regression!\n" +
        "\n".join(failures) +
        "\n\nEvery download_image_to_disk call MUST be followed by store_asset_async "
        "in the same function block — otherwise images disappear on K8s pod restart."
    )
