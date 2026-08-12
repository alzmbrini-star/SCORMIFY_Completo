from pathlib import Path


PLAYER = Path(__file__).resolve().parents[1] / "services" / "export_assets" / "player.js"


def test_classic_scorm_player_upgrades_legacy_simulator_stages():
    source = PLAYER.read_text(encoding="utf-8")
    assert "wrappedHtml.indexOf('__stage') !== -1" in source
    assert "wrappedHtml.indexOf('__scormify_fit_v2') === -1" in source
    assert 'st.style.position="absolute"' in source
    assert 'translate(-50%,-50%) scale(' in source


def test_classic_scorm_player_uses_safe_padding_and_full_height_measurement():
    source = PLAYER.read_text(encoding="utf-8")
    assert "Math.max(st.scrollHeight,st.offsetHeight,540)" in source
    assert "(innerHeight-p*2)/ch" in source
