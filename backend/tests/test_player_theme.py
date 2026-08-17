from services.player_theme import DEFAULTS, resolve_player_theme


def test_player_theme_preserves_legacy_defaults_when_company_has_no_override():
    theme = resolve_player_theme({"brandKit": {}})
    assert theme["canvas"] == DEFAULTS["canvas"]
    assert theme["header"] == DEFAULTS["header"]
    assert theme["navigation"] == DEFAULTS["navigation"]


def test_company_can_customize_each_player_surface_and_text_contrast_is_automatic():
    theme = resolve_player_theme({
        "brandKit": {
            "playerCanvasColor": "#f1f5f9",
            "playerHeaderColor": "#ffffff",
            "playerNavigationColor": "#123456",
            "playerAccentColor": "#facc15",
        }
    })
    assert theme["canvas"] == "#f1f5f9"
    assert theme["header"] == "#ffffff"
    assert theme["navigation"] == "#123456"
    assert theme["accent"] == "#facc15"
    assert theme["headerText"] == "#0f172a"
    assert theme["navigationText"] == "#f8fafc"
    assert theme["accentText"] == "#0f172a"


def test_invalid_player_color_falls_back_safely():
    theme = resolve_player_theme({
        "brandKit": {"playerCanvasColor": "red; display:none"}
    })
    assert theme["canvas"] == DEFAULTS["canvas"]
