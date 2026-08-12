from pathlib import Path


PLAYER = Path(__file__).resolve().parents[1] / "services" / "export_assets" / "player.js"


def test_classic_scorm_player_upgrades_legacy_simulator_stages():
    source = PLAYER.read_text(encoding="utf-8")
    assert "wrappedHtml.indexOf('__stage') !== -1" in source
    assert "wrappedHtml.indexOf('__scormify_fit_v3') === -1" in source
    assert 'st.style.position="absolute"' in source
    assert 'st.querySelectorAll("*")' in source
    assert 'r.bottom-sr.top' in source


def test_classic_scorm_player_uses_safe_padding_and_full_height_measurement():
    source = PLAYER.read_text(encoding="utf-8")
    assert "maxY=Math.max(540,st.scrollHeight,st.offsetHeight)" in source
    assert "(innerHeight-p*2)/ch" in source


def test_classic_scorm_player_keeps_utf8_navigation_labels():
    source = PLAYER.read_text(encoding="utf-8")
    assert "PrÃ³ximo" not in source
    assert "â†’" not in source
    assert "Próximo →" in source
    assert "✓ Concluído" in source


def test_html_export_uses_the_same_descendant_bounds_fit():
    source = (PLAYER.parents[1] / "html_exporter.py").read_text(encoding="utf-8")
    assert "__scormify_fit_v3" in source
    assert 'st.querySelectorAll(\"*\")' in source
    assert "r.bottom-sr.top" in source
