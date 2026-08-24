from services.player_theme import (
    DEFAULTS,
    TUTOR_DEFAULTS,
    build_single_page_player_theme_css,
    build_tutor_theme_css,
    resolve_player_theme,
    resolve_tutor_theme,
)
from services.single_page_exporter import generate_single_page_html


def test_single_page_css_uses_resolved_company_colors():
    project = {"brandKit": {
        "playerCanvasColor": "#112233",
        "playerHeaderColor": "#223344",
        "playerNavigationColor": "#334455",
        "playerAccentColor": "#ffcc00",
        "playerSidebarColor": "#445566",
        "playerSidebarItemColor": "#556677",
        "playerSidebarActiveColor": "#667788",
    }}
    css = build_single_page_player_theme_css(resolve_player_theme(project))
    assert "html, body { background: #112233; }" in css
    assert ".sp-header { background: #223344;" in css
    assert ".sp-progress { background: #334455; }" in css
    assert ".sp-progress-fill { background: #ffcc00; }" in css
    assert ".sp-drawer { background: #445566;" in css
    assert "background: #556677" in css
    assert "background: #667788" in css


def test_single_page_and_tutor_share_the_company_brand_kit():
    project = {"brandKit": {
        "playerAccentColor": "#123456",
        "playerNavigationColor": "#234567",
        "tutorHeaderColor": "#345678",
        "tutorPanelColor": "#456789",
    }}
    player_css = build_single_page_player_theme_css(resolve_player_theme(project))
    tutor = resolve_tutor_theme(project)
    assert "#123456" in player_css
    assert tutor["header"] == "#345678"
    assert tutor["panel"] == "#456789"


def test_player_theme_preserves_legacy_defaults_when_company_has_no_override():
    theme = resolve_player_theme({"brandKit": {}})
    assert theme["canvas"] == DEFAULTS["canvas"]
    assert theme["header"] == DEFAULTS["header"]
    assert theme["navigation"] == DEFAULTS["navigation"]
    assert theme["sidebar"] == DEFAULTS["sidebar"]
    assert theme["sidebarHeader"] == DEFAULTS["sidebarHeader"]


def test_company_can_customize_each_player_surface_and_text_contrast_is_automatic():
    theme = resolve_player_theme({
        "brandKit": {
            "playerCanvasColor": "#f1f5f9",
            "playerHeaderColor": "#ffffff",
            "playerNavigationColor": "#123456",
            "playerAccentColor": "#facc15",
            "playerSidebarColor": "#f8fafc",
            "playerSidebarHeaderColor": "#fde68a",
            "playerSidebarItemColor": "#1e3a8a",
            "playerSidebarActiveColor": "#fef3c7",
        }
    })
    assert theme["canvas"] == "#f1f5f9"
    assert theme["header"] == "#ffffff"
    assert theme["navigation"] == "#123456"
    assert theme["accent"] == "#facc15"
    assert theme["headerText"] == "#0f172a"
    assert theme["navigationText"] == "#f8fafc"
    assert theme["accentText"] == "#0f172a"
    assert theme["sidebarText"] == "#0f172a"
    assert theme["sidebarHeaderText"] == "#0f172a"
    assert theme["sidebarItemText"] == "#f8fafc"
    assert theme["sidebarActiveText"] == "#0f172a"


def test_invalid_player_color_falls_back_safely():
    theme = resolve_player_theme({
        "brandKit": {"playerCanvasColor": "red; display:none"}
    })
    assert theme["canvas"] == DEFAULTS["canvas"]


def test_tutor_inherits_company_player_colors_and_calculates_contrast():
    theme = resolve_tutor_theme({
        "brandKit": {
            "playerAccentColor": "#ef4444",
            "playerNavigationColor": "#fee2e2",
            "playerSidebarItemColor": "#7f1d1d",
        }
    })
    assert theme["header"] == "#ef4444"
    assert theme["panel"] == "#fee2e2"
    assert theme["message"] == "#7f1d1d"
    assert theme["panelText"] == "#0f172a"
    assert theme["messageText"] == "#f8fafc"


def test_dedicated_tutor_colors_override_player_and_generate_scoped_css():
    theme = resolve_tutor_theme({
        "brandKit": {
            "playerAccentColor": "#ef4444",
            "tutorHeaderColor": "#112233",
            "tutorPanelColor": "#ffffff",
            "tutorAccentColor": "#facc15",
            "tutorMessageColor": "#334155",
        }
    })
    assert theme["header"] == "#112233"
    assert theme["panel"] == "#ffffff"
    assert theme["accent"] == "#facc15"
    css = build_tutor_theme_css(theme)
    assert ".tutor-fab" in css
    assert ".tutor-contrast-light" in css
    assert "#112233" in css
    assert "#facc15" in css


def test_tutor_preserves_legacy_palette_without_brand_kit():
    theme = resolve_tutor_theme({"brandKit": {}})
    assert theme["header"] == TUTOR_DEFAULTS["header"]
    assert theme["panel"] == TUTOR_DEFAULTS["panel"]
    assert theme["customized"] is False
    assert build_tutor_theme_css(theme) == ""


def test_visual_journey_uses_cinematic_single_page_chapters():
    project = {
        "id": "journey-1",
        "name": "NR-1 na Prática",
        "playerTemplate": "visual_journey",
        "course": {
            "metadata": {
                "title": "NR-1 na Prática",
                "visualCourseMode": "illustrated_journey",
                "playerTemplate": "visual_journey",
            },
            "slides": [{
                "id": "s1", "title": "Uma situação de risco", "moduleName": "Capítulo 1",
                "narrativeBeat": "observe", "elements": [], "width": 1920, "height": 820,
            }],
        },
    }
    html = generate_single_page_html(project, "/tmp/no-assets", "")
    assert 'body class="sp-visual-journey"' in html
    assert "sp-journey-section" in html
    assert "Capítulo 1" in html
    assert "sp-journey-beat" in html
    assert "fotografia" not in html  # internal prompt metadata never leaks to learners
