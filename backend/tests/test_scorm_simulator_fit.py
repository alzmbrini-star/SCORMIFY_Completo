from pathlib import Path


PLAYER = Path(__file__).resolve().parents[1] / "services" / "export_assets" / "player.js"
SCORM_EXPORTER = Path(__file__).resolve().parents[1] / "services" / "scorm_exporter.py"
PLAYER_TEMPLATE = PLAYER.parent / "player_template.html"


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


def test_scorm_game_viewport_uses_the_active_slide_object_not_its_index():
    source = PLAYER.read_text(encoding="utf-8")
    assert "var activeSlide = (course && course.slides && course.slides[currentSlide]) || {};" in source
    assert "activeSlide.type === 'game'" in source
    assert "var viewportSlide = activeSlide;" in source
    assert "currentSlide.type === 'game'" not in source


def test_scorm_games_expand_to_the_real_slide_dimensions():
    source = PLAYER.read_text(encoding="utf-8")
    assert "var slideWidth = activeSlide.width || 960;" in source
    assert "var slideHeight = activeSlide.height || 540;" in source
    assert "viewportWidth - gameMarginX * 2" in source
    assert "viewportHeight - gameMarginY * 2" in source


def test_scorm_game_fit_falls_back_to_the_real_game_root():
    source = PLAYER.read_text(encoding="utf-8")
    assert "__scormify_game_fit_v9" in source
    assert 'responsive=fixed&&fixed.querySelector("main.app,main.game,.app,.game")' in source
    assert 'st.style.setProperty("width","100%","important")' in source


def test_scorm_exporter_persists_full_slide_game_geometry_in_course_json():
    source = SCORM_EXPORTER.read_text(encoding="utf-8")
    assert "game_source.startswith('__B64__:')" in source
    assert "'interactiveType': 'game'" in source
    assert "'width': slide_width" in source
    assert "'height': slide_height" in source
    assert "'objectFit': 'cover'" in source
    assert "'htmlDisplayMode': 'fit'" in source


def test_scorm_export_uses_a_unique_cache_key_for_lms_resources():
    exporter = SCORM_EXPORTER.read_text(encoding="utf-8")
    template = PLAYER_TEMPLATE.read_text(encoding="utf-8")
    player = PLAYER.read_text(encoding="utf-8")
    assert 'launch_href=f"index.html?v={export_token}"' in exporter
    assert 'scripts/player.js?v=__EXPORT_TOKEN__' in template
    assert 'window.__SCORMIFY_EXPORT_TOKEN__' in template
    assert "fetch('course.json' + (exportToken ? '?v='" in player
