"""Tests for the BrandKit applier — the helper that injects a company's
visual identity (colors + font) into the design-template palette used by the
AI Agent slide builder.

These tests cover the pure function `apply_brand_kit_to_palette` extensively.
The async DB-fetch `fetch_brand_kit` is exercised via a simple mock in one
test (it's a thin wrapper, no need for elaborate scenarios)."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from services.brand_kit_applier import (
    apply_brand_kit_to_palette,
    fetch_brand_kit,
    _is_hex_color,
    _lighten_hex,
)


# ---------------------------------------------------------------------------
# Hex color validation
# ---------------------------------------------------------------------------

class TestHexValidator:
    @pytest.mark.parametrize("v", [
        "#abc", "#abcd", "#aabbcc", "#aabbccdd",
        "#000000", "#FFFFFF", "#0F172A",
    ])
    def test_valid_hex(self, v):
        assert _is_hex_color(v) is True

    @pytest.mark.parametrize("v", [
        None, "", "abc", "rgb(0,0,0)", "#xyz",
        "#12345",          # invalid length
        "#1234567",        # invalid length (7 digits)
        "blue", 123, [], {}, "  ", "#",
    ])
    def test_invalid_hex(self, v):
        assert _is_hex_color(v) is False


# ---------------------------------------------------------------------------
# Lightening helper — used to derive accentLight from accentColor
# ---------------------------------------------------------------------------

class TestLighten:
    def test_pure_black_lightens_toward_gray(self):
        out = _lighten_hex("#000000", 0.5)
        assert out == "#808080"

    def test_pure_white_stays_white(self):
        assert _lighten_hex("#ffffff", 0.9) == "#ffffff"

    def test_3digit_shorthand_expands_then_lightens(self):
        # #f00 (red) → expand to #ff0000, lighten 50% → middling pink
        out = _lighten_hex("#f00", 0.5)
        # Red stays, green/blue go from 0 to ~128
        assert out.startswith("#ff") and out.endswith("8080")

    def test_alpha_channel_stripped_in_8digit(self):
        out = _lighten_hex("#0f172aff", 0.5)
        # Alpha was dropped, base color was lightened — not the raw alpha hex
        assert out == _lighten_hex("#0f172a", 0.5)

    def test_invalid_input_returns_unchanged(self):
        assert _lighten_hex("not-a-color", 0.5) == "not-a-color"


# ---------------------------------------------------------------------------
# apply_brand_kit_to_palette — the main function
# ---------------------------------------------------------------------------

@pytest.fixture
def base_palette():
    """A plausible design-template palette."""
    return {
        "primary": "#0f172a",
        "accent": "#c9a227",
        "accentLight": "#fef3c7",
        "contentBg": "#f8fafc",
        "text": "#1e293b",
        "fontHeading": "'Inter', sans-serif",
        "fontBody": "'Inter', sans-serif",
        "headerStyle": "solid",
        "cornerRadius": "12px",
    }


class TestApplyBrandKit:
    def test_none_brand_kit_returns_copy_unchanged(self, base_palette):
        out = apply_brand_kit_to_palette(base_palette, None)
        # All keys identical
        assert out == base_palette
        # But it's a new dict so mutating one doesn't affect the other
        out["primary"] = "#changed"
        assert base_palette["primary"] == "#0f172a"

    def test_empty_brand_kit_returns_copy_unchanged(self, base_palette):
        out = apply_brand_kit_to_palette(base_palette, {})
        assert out == base_palette

    def test_primary_color_overrides_palette_primary(self, base_palette):
        kit = {"primaryColor": "#eb6d24"}
        out = apply_brand_kit_to_palette(base_palette, kit)
        assert out["primary"] == "#eb6d24"
        # Other keys untouched
        assert out["accent"] == base_palette["accent"]
        assert out["text"] == base_palette["text"]

    def test_secondary_color_maps_to_text(self, base_palette):
        kit = {"secondaryColor": "#606060"}
        out = apply_brand_kit_to_palette(base_palette, kit)
        assert out["text"] == "#606060"
        # Primary untouched
        assert out["primary"] == base_palette["primary"]

    def test_accent_color_overrides_and_derives_light(self, base_palette):
        kit = {"accentColor": "#eb6d24"}
        out = apply_brand_kit_to_palette(base_palette, kit)
        assert out["accent"] == "#eb6d24"
        # accentLight must be DIFFERENT from accent and from the original
        assert out["accentLight"] != base_palette["accentLight"]
        assert out["accentLight"] != "#eb6d24"
        # Lightened version should be a valid hex
        assert _is_hex_color(out["accentLight"])

    def test_font_family_wraps_in_quotes_when_spaces(self, base_palette):
        kit = {"fontFamily": "Open Sans"}
        out = apply_brand_kit_to_palette(base_palette, kit)
        assert out["fontHeading"] == "'Open Sans', sans-serif"
        assert out["fontBody"] == "'Open Sans', sans-serif"

    def test_font_family_single_word_gets_fallback(self, base_palette):
        kit = {"fontFamily": "Inter"}
        out = apply_brand_kit_to_palette(base_palette, kit)
        # Single word doesn't get quoted but still gets the fallback
        assert out["fontHeading"] == "Inter, sans-serif"
        assert out["fontBody"] == "Inter, sans-serif"

    def test_font_family_with_fallback_passes_through(self, base_palette):
        """When the user typed a full stack like 'Inter, sans-serif', leave it."""
        kit = {"fontFamily": "Inter, sans-serif"}
        out = apply_brand_kit_to_palette(base_palette, kit)
        assert out["fontHeading"] == "Inter, sans-serif"

    def test_empty_font_family_string_ignored(self, base_palette):
        kit = {"fontFamily": "   "}
        out = apply_brand_kit_to_palette(base_palette, kit)
        assert out["fontHeading"] == base_palette["fontHeading"]

    def test_invalid_hex_value_is_silently_ignored(self, base_palette):
        """A bogus value (e.g. typo in the admin form) must not corrupt the
        palette — fall back to the design template's value."""
        kit = {"primaryColor": "not-a-color", "accentColor": "rgb(255,0,0)"}
        out = apply_brand_kit_to_palette(base_palette, kit)
        assert out["primary"] == base_palette["primary"]
        assert out["accent"] == base_palette["accent"]

    def test_partial_brand_kit_only_overrides_provided_fields(self, base_palette):
        """User filled only primary — accent and text must keep the template's."""
        kit = {"primaryColor": "#eb6d24"}
        out = apply_brand_kit_to_palette(base_palette, kit)
        assert out["primary"] == "#eb6d24"
        assert out["accent"] == base_palette["accent"]
        assert out["text"] == base_palette["text"]
        assert out["fontHeading"] == base_palette["fontHeading"]

    def test_full_brand_kit_overrides_all_fields(self, base_palette):
        kit = {
            "primaryColor": "#eb6d24",
            "secondaryColor": "#606060",
            "accentColor": "#3b82f6",
            "fontFamily": "Roboto",
        }
        out = apply_brand_kit_to_palette(base_palette, kit)
        assert out["primary"] == "#eb6d24"
        assert out["text"] == "#606060"
        assert out["accent"] == "#3b82f6"
        assert "Roboto" in out["fontHeading"]
        assert "Roboto" in out["fontBody"]

    def test_original_palette_is_not_mutated(self, base_palette):
        """Defensive: the caller may want to log the original palette later."""
        snapshot = dict(base_palette)
        kit = {"primaryColor": "#eb6d24", "fontFamily": "Roboto"}
        _ = apply_brand_kit_to_palette(base_palette, kit)
        assert base_palette == snapshot

    def test_unknown_brand_kit_keys_ignored(self, base_palette):
        """Forward-compat: future brand kit fields (logoUrl, etc.) shouldn't
        break the applier."""
        kit = {"primaryColor": "#eb6d24", "logoUrl": "/some/logo.png", "tone": "playful"}
        out = apply_brand_kit_to_palette(base_palette, kit)
        assert out["primary"] == "#eb6d24"
        # Unknown keys silently dropped, no crash


# ---------------------------------------------------------------------------
# fetch_brand_kit — DB plumbing
# ---------------------------------------------------------------------------

class TestFetchBrandKit:
    @pytest.mark.asyncio
    async def test_returns_kit_when_present(self):
        db = MagicMock()
        db.companies.find_one = AsyncMock(return_value={
            "brandKit": {"primaryColor": "#eb6d24", "fontFamily": "Roboto"},
        })
        out = await fetch_brand_kit(db, "company_didaxis001")
        assert out is not None
        assert out["primaryColor"] == "#eb6d24"

    @pytest.mark.asyncio
    async def test_returns_none_when_company_missing(self):
        db = MagicMock()
        db.companies.find_one = AsyncMock(return_value=None)
        out = await fetch_brand_kit(db, "ghost_company")
        assert out is None

    @pytest.mark.asyncio
    async def test_returns_none_when_brand_kit_empty(self):
        db = MagicMock()
        db.companies.find_one = AsyncMock(return_value={"brandKit": {}})
        out = await fetch_brand_kit(db, "c1")
        # Empty dict means no kit configured — treat as None
        assert out is None

    @pytest.mark.asyncio
    async def test_returns_none_on_missing_company_id(self):
        db = MagicMock()
        out = await fetch_brand_kit(db, "")
        assert out is None
        # And we never hit the DB
        db.companies.find_one.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_none_on_db_exception(self):
        db = MagicMock()
        db.companies.find_one = AsyncMock(side_effect=Exception("db down"))
        out = await fetch_brand_kit(db, "c1")
        # Graceful — slide generation must NOT crash because brand kit fetch failed
        assert out is None
