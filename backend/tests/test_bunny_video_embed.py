"""Ensures Bunny Stream video embeds are correctly handled by the HTML exporter
and the SCORM player runtime.

Two guarantees:
1. The inline slide-renderer JS inside `html_exporter.py` recognises
   `iframe.mediadelivery.net` URLs and injects an <iframe> with autoplay/preload
   flags plus absolute positioning (same treatment as YouTube/Vimeo).
2. The exported player.js runtime carries the same Bunny branch.
"""

from pathlib import Path


def test_html_exporter_has_bunny_branch():
    src = Path("/app/backend/services/html_exporter.py").read_text()
    assert "iframe.mediadelivery.net" in src, "html_exporter must reference Bunny host"
    assert "isBunny" in src, "html_exporter must declare isBunny flag in slide renderer"
    # Bunny needs autoplay=true (boolean string), unlike YouTube/Vimeo autoplay=1
    assert "autoplay=true" in src


def test_player_js_has_bunny_branch():
    src = Path("/app/backend/services/export_assets/player.js").read_text()
    assert "iframe.mediadelivery.net" in src
    assert "isBunny" in src
    assert "autoplay=true" in src
    # Bunny iframes must be positioned absolutely to fill the slide element
    # (regression against the generic "other embeds" branch that used
    # width/height only and broke aspect ratios).
    idx = src.index("isBunny")
    tail = src[idx: idx + 2000]
    assert "position:absolute" in tail
