"""Regression tests for the Whiteboard drawing-tool selector (2026-02).

Verifies the new `tool` parameter on `render_whiteboard_video` picks
the right PNG asset and per-tool offsets, and that the validation /
catalog endpoints work end-to-end.
"""
import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.whiteboard_renderer import (  # noqa: E402
    DEFAULT_TOOL,
    HAND_REAL_PATH,
    HAND_WITH_PEN_PATH,
    PEN_PATH,
    TOOL_PROFILES,
    _resolve_tool,
    list_available_tools,
    render_whiteboard_video,
)


def test_tool_profiles_present():
    assert "pen" in TOOL_PROFILES
    assert "hand" in TOOL_PROFILES
    assert "hand_real" in TOOL_PROFILES


def test_resolve_tool_falls_back_for_unknown():
    """Unknown / None / empty must collapse to the default tool."""
    assert _resolve_tool(None)["path"] == PEN_PATH
    assert _resolve_tool("")["path"] == PEN_PATH
    assert _resolve_tool("banana")["path"] == PEN_PATH


def test_resolve_tool_returns_correct_assets():
    assert _resolve_tool("pen")["path"] == PEN_PATH
    assert _resolve_tool("hand")["path"] == HAND_WITH_PEN_PATH
    assert _resolve_tool("hand_real")["path"] == HAND_REAL_PATH


def test_list_available_tools_returns_disk_present_only():
    tools = list_available_tools()
    ids = [t["id"] for t in tools]
    # In CI all three assets should ship; if any are missing, the catalog
    # would silently omit them rather than expose dead choices to the UI.
    assert ids == sorted(ids, key=lambda x: list(TOOL_PROFILES.keys()).index(x))
    if PEN_PATH.exists():
        assert "pen" in ids
    if HAND_WITH_PEN_PATH.exists():
        assert "hand" in ids
    if HAND_REAL_PATH.exists():
        assert "hand_real" in ids


def test_default_tool_is_pen():
    assert DEFAULT_TOOL == "pen"
    assert _resolve_tool(DEFAULT_TOOL)["path"] == PEN_PATH


@pytest.mark.parametrize("tool", ["pen", "hand", "hand_real"])
def test_render_with_each_tool_succeeds(tool):
    """End-to-end: render a short clip with each tool and confirm a
    non-empty file is produced. Catches regressions in offset / scale
    plumbing that would otherwise crash on `img.paste()`."""
    url, info = asyncio.run(render_whiteboard_video(
        text=f"Test {tool}",
        font_size=72,
        chars_per_second=20,
        tool=tool,
        transparent=True,
    ))
    assert url.startswith("/api/whiteboard/file/")
    assert info["fileSize"] > 1000  # non-trivial PNG
    assert info["frames"] > 0
    # Heavier assets are sanity-checked by minimum file size — if the
    # offset/scale plumbing broke and fell back to the small `pen.png`
    # the file would be far smaller than the expected hand renders.
    if tool == "hand":
        assert info["fileSize"] > 500_000, (
            "hand-tool render unexpectedly small — likely fell back to pen asset"
        )
    if tool == "hand_real":
        assert info["fileSize"] > 1_000_000, (
            "hand_real-tool render unexpectedly small — likely fell back to pen asset"
        )
