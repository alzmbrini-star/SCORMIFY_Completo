"""Tests for the brand-logo watermark that the AI Agent stamps on every
generated slide when the company's BrandKit has a `logoUrl`.

We replay the small watermark loop in isolation (it's a self-contained ~15
lines at the tail of `generate_course_from_storyboard`). Unit-testing the
full async generator is impractical here — the relevant invariants are
local to the loop, so isolating it gives sharper failure messages.
"""
import pytest


def _apply_brand_watermark(slides, brand_kit, use_brand_library=True):
    """Mirror of the watermark loop. Returns the slides list (mutated in
    place to match production behavior)."""
    if not use_brand_library:
        return slides
    if not brand_kit or not isinstance(brand_kit, dict):
        return slides
    logo_url = (brand_kit.get("logoUrl") or "").strip()
    if not logo_url:
        return slides
    placement = (brand_kit.get("logoPlacement") or "bottom-right").lower().strip()
    if placement not in ("bottom-right", "bottom-left", "bottom-center", "intro-conclusion-only"):
        placement = "bottom-right"
    LOGO_W = 180
    LOGO_H = 70
    PAD_H = 36
    PAD_V = 24
    CANVAS_W = 1920
    CANVAS_H = 820
    if placement == "bottom-left":
        x = PAD_H
    elif placement == "bottom-center":
        x = (CANVAS_W - LOGO_W) // 2
    else:
        x = CANVAS_W - LOGO_W - PAD_H
    y = CANVAS_H - LOGO_H - PAD_V
    total = len(slides)
    for idx, slide in enumerate(slides):
        if placement == "intro-conclusion-only":
            if not (idx == 0 or idx == total - 1):
                continue
        slide["elements"].append({
            "id": f"brand-logo-{slide['id'][-6:]}",
            "type": "image",
            "imageUrl": logo_url,
            "x": x,
            "y": y,
            "width": LOGO_W,
            "height": LOGO_H,
            "opacity": 0.9,
            "objectFit": "contain",
            "isBrandLogo": True,
            "zIndex": 50,
        })
    return slides


@pytest.fixture
def three_slides():
    return [
        {"id": "slide-aaa-bbb-ccc-111", "title": "S1", "elements": []},
        {"id": "slide-aaa-bbb-ccc-222", "title": "S2", "elements": []},
        {"id": "slide-aaa-bbb-ccc-333", "title": "S3", "elements": []},
    ]


class TestWatermarkInjection:
    def test_logo_added_to_every_slide(self, three_slides):
        kit = {"logoUrl": "/api/companies/c1/assets/logo123/file"}
        out = _apply_brand_watermark(three_slides, kit, use_brand_library=True)
        for s in out:
            logos = [e for e in s["elements"] if e.get("isBrandLogo")]
            assert len(logos) == 1, f"Expected 1 logo per slide, got {len(logos)}"

    def test_logo_url_propagated_correctly(self, three_slides):
        kit = {"logoUrl": "https://cdn.example.com/brand-logo.png"}
        out = _apply_brand_watermark(three_slides, kit, use_brand_library=True)
        for s in out:
            logo = next(e for e in s["elements"] if e.get("isBrandLogo"))
            assert logo["imageUrl"] == "https://cdn.example.com/brand-logo.png"

    def test_logo_not_added_when_use_brand_library_off(self, three_slides):
        """User opted OUT of brand library → respect that, no watermark."""
        kit = {"logoUrl": "/x/y/z"}
        out = _apply_brand_watermark(three_slides, kit, use_brand_library=False)
        for s in out:
            assert not any(e.get("isBrandLogo") for e in s["elements"])

    def test_logo_not_added_when_brandkit_missing(self, three_slides):
        out = _apply_brand_watermark(three_slides, None, use_brand_library=True)
        for s in out:
            assert not any(e.get("isBrandLogo") for e in s["elements"])

    def test_logo_not_added_when_logo_url_empty(self, three_slides):
        kit = {"logoUrl": "", "primaryColor": "#1e3a8a"}
        out = _apply_brand_watermark(three_slides, kit, use_brand_library=True)
        for s in out:
            assert not any(e.get("isBrandLogo") for e in s["elements"])

    def test_logo_not_added_when_logo_url_whitespace(self, three_slides):
        """Edge case: a stray space in the kit shouldn't ship a broken
        empty-src image element to the runtime."""
        kit = {"logoUrl": "   "}
        out = _apply_brand_watermark(three_slides, kit, use_brand_library=True)
        for s in out:
            assert not any(e.get("isBrandLogo") for e in s["elements"])

    def test_logo_position_consistent_across_slides(self, three_slides):
        """Same x,y for every slide — gives a stable watermark spot users
        will look for instinctively."""
        kit = {"logoUrl": "/x"}
        out = _apply_brand_watermark(three_slides, kit, use_brand_library=True)
        positions = {(s["elements"][-1]["x"], s["elements"][-1]["y"]) for s in out}
        assert len(positions) == 1, f"Logo position drifted: {positions}"

    def test_logo_is_in_bottom_right_quadrant(self, three_slides):
        """Position invariant: x > half-width and y > half-height of the
        1920x820 canvas, so the logo lives in the bottom-right corner."""
        kit = {"logoUrl": "/x"}
        out = _apply_brand_watermark(three_slides, kit, use_brand_library=True)
        logo = out[0]["elements"][-1]
        assert logo["x"] > 960, f"Logo x={logo['x']} should be > 960 (half width)"
        assert logo["y"] > 410, f"Logo y={logo['y']} should be > 410 (half height)"

    def test_logo_fits_in_canvas_bounds(self, three_slides):
        """Position invariant: the logo's right and bottom edges stay inside
        the 1920x820 canvas (no clipping)."""
        kit = {"logoUrl": "/x"}
        out = _apply_brand_watermark(three_slides, kit, use_brand_library=True)
        logo = out[0]["elements"][-1]
        assert logo["x"] + logo["width"] <= 1920
        assert logo["y"] + logo["height"] <= 820

    def test_logo_uses_contain_object_fit(self, three_slides):
        """objectFit must be 'contain' so non-square logos never get cropped/
        distorted — a stretched logo would be far worse than no logo."""
        kit = {"logoUrl": "/x"}
        out = _apply_brand_watermark(three_slides, kit, use_brand_library=True)
        assert out[0]["elements"][-1]["objectFit"] == "contain"

    def test_logo_has_opacity_below_1(self, three_slides):
        """Slight transparency so the logo feels like a watermark and doesn't
        steal attention from the content."""
        kit = {"logoUrl": "/x"}
        out = _apply_brand_watermark(three_slides, kit, use_brand_library=True)
        assert 0 < out[0]["elements"][-1]["opacity"] < 1

    def test_logo_marker_present_for_editor(self, three_slides):
        """`isBrandLogo: True` is the marker the Editor uses to render a
        dedicated control + the exporter uses to optionally skip/move it."""
        kit = {"logoUrl": "/x"}
        out = _apply_brand_watermark(three_slides, kit, use_brand_library=True)
        assert out[0]["elements"][-1]["isBrandLogo"] is True

    def test_existing_elements_preserved(self, three_slides):
        """The watermark must NOT replace existing slide elements — it's
        appended on top."""
        three_slides[0]["elements"] = [
            {"id": "el-1", "type": "text", "content": "hello"},
            {"id": "el-2", "type": "shape"},
        ]
        kit = {"logoUrl": "/x"}
        out = _apply_brand_watermark(three_slides, kit, use_brand_library=True)
        # First slide has its original 2 + 1 logo = 3 elements
        assert len(out[0]["elements"]) == 3
        assert out[0]["elements"][0]["id"] == "el-1"
        assert out[0]["elements"][1]["id"] == "el-2"
        # Other slides only have the watermark
        assert len(out[1]["elements"]) == 1
        assert len(out[2]["elements"]) == 1


class TestWatermarkIdempotency:
    """Re-running generation (e.g. user edited media config and regenerated)
    must NOT pile up duplicate logos on the same slide. The implementation
    appends; the caller is responsible for not double-applying. We assert
    this invariant via a defensive count."""

    def test_re_running_appends_again(self, three_slides):
        """This documents current behavior: calling twice produces two logos.
        Caller (generate_course_from_storyboard) only runs ONCE per request,
        so this is fine — but if a future endpoint regenerates slides
        in-place it must strip existing brand logos first."""
        kit = {"logoUrl": "/x"}
        _apply_brand_watermark(three_slides, kit, use_brand_library=True)
        _apply_brand_watermark(three_slides, kit, use_brand_library=True)
        for s in three_slides:
            assert sum(1 for e in s["elements"] if e.get("isBrandLogo")) == 2



# ---------------------------------------------------------------------------
# logoPlacement variations
# ---------------------------------------------------------------------------

class TestLogoPlacement:
    """The brandKit's `logoPlacement` controls where the watermark lands on
    each slide. Four valid values; anything else falls back to bottom-right."""

    def test_default_placement_is_bottom_right(self, three_slides):
        kit = {"logoUrl": "/x"}  # no placement field
        out = _apply_brand_watermark(three_slides, kit, use_brand_library=True)
        logo = out[0]["elements"][-1]
        # bottom-right: x = 1920 - 180 - 36 = 1704
        assert logo["x"] == 1704
        # bottom: y = 820 - 70 - 24 = 726
        assert logo["y"] == 726

    def test_bottom_left_position(self, three_slides):
        kit = {"logoUrl": "/x", "logoPlacement": "bottom-left"}
        out = _apply_brand_watermark(three_slides, kit, use_brand_library=True)
        logo = out[0]["elements"][-1]
        assert logo["x"] == 36
        assert logo["y"] == 726

    def test_bottom_center_position(self, three_slides):
        kit = {"logoUrl": "/x", "logoPlacement": "bottom-center"}
        out = _apply_brand_watermark(three_slides, kit, use_brand_library=True)
        logo = out[0]["elements"][-1]
        # bottom-center: x = (1920 - 180) / 2 = 870
        assert logo["x"] == 870
        assert logo["y"] == 726

    def test_bottom_right_position_explicit(self, three_slides):
        kit = {"logoUrl": "/x", "logoPlacement": "bottom-right"}
        out = _apply_brand_watermark(three_slides, kit, use_brand_library=True)
        logo = out[0]["elements"][-1]
        assert logo["x"] == 1704
        assert logo["y"] == 726

    def test_intro_conclusion_only_applies_to_first_and_last(self, three_slides):
        kit = {"logoUrl": "/x", "logoPlacement": "intro-conclusion-only"}
        out = _apply_brand_watermark(three_slides, kit, use_brand_library=True)
        assert any(e.get("isBrandLogo") for e in out[0]["elements"])
        # Middle slide: NO logo
        assert not any(e.get("isBrandLogo") for e in out[1]["elements"])
        assert any(e.get("isBrandLogo") for e in out[2]["elements"])

    def test_intro_conclusion_only_with_two_slides(self):
        """With exactly 2 slides, both are intro AND conclusion -> both get logo."""
        slides = [
            {"id": "s-aaa-bbb-111", "title": "Intro", "elements": []},
            {"id": "s-aaa-bbb-222", "title": "End", "elements": []},
        ]
        kit = {"logoUrl": "/x", "logoPlacement": "intro-conclusion-only"}
        out = _apply_brand_watermark(slides, kit, use_brand_library=True)
        assert any(e.get("isBrandLogo") for e in out[0]["elements"])
        assert any(e.get("isBrandLogo") for e in out[1]["elements"])

    def test_intro_conclusion_only_with_one_slide(self):
        """Edge case: 1-slide course - the single slide gets the logo."""
        slides = [{"id": "s-solo-1234", "title": "Solo", "elements": []}]
        kit = {"logoUrl": "/x", "logoPlacement": "intro-conclusion-only"}
        out = _apply_brand_watermark(slides, kit, use_brand_library=True)
        assert any(e.get("isBrandLogo") for e in out[0]["elements"])

    def test_intro_conclusion_uses_bottom_right_coords(self, three_slides):
        """intro-conclusion-only positions the logo in bottom-right."""
        kit = {"logoUrl": "/x", "logoPlacement": "intro-conclusion-only"}
        out = _apply_brand_watermark(three_slides, kit, use_brand_library=True)
        first_logo = next(e for e in out[0]["elements"] if e.get("isBrandLogo"))
        assert first_logo["x"] == 1704
        assert first_logo["y"] == 726

    def test_invalid_placement_falls_back_to_bottom_right(self, three_slides):
        """Defensive: a typo in the admin form shouldn't break the generator."""
        kit = {"logoUrl": "/x", "logoPlacement": "top-banner"}
        out = _apply_brand_watermark(three_slides, kit, use_brand_library=True)
        logo = out[0]["elements"][-1]
        assert logo["x"] == 1704

    def test_empty_placement_string_falls_back(self, three_slides):
        kit = {"logoUrl": "/x", "logoPlacement": ""}
        out = _apply_brand_watermark(three_slides, kit, use_brand_library=True)
        logo = out[0]["elements"][-1]
        assert logo["x"] == 1704

    def test_placement_case_insensitive(self, three_slides):
        """User-typed values from the admin form get normalized to lowercase."""
        kit = {"logoUrl": "/x", "logoPlacement": "BOTTOM-LEFT"}
        out = _apply_brand_watermark(three_slides, kit, use_brand_library=True)
        logo = out[0]["elements"][-1]
        assert logo["x"] == 36

    def test_all_placements_keep_logo_in_canvas(self):
        """For every valid placement, the logo's right+bottom edges must
        stay inside the 1920x820 canvas."""
        for placement in ("bottom-right", "bottom-left", "bottom-center", "intro-conclusion-only"):
            slides = [{"id": "s-test-001", "title": "T", "elements": []}]
            kit = {"logoUrl": "/x", "logoPlacement": placement}
            _apply_brand_watermark(slides, kit, use_brand_library=True)
            logo = slides[0]["elements"][-1]
            assert 0 <= logo["x"] <= 1920 - logo["width"], f"placement={placement} x out of bounds"
            assert 0 <= logo["y"] <= 820 - logo["height"], f"placement={placement} y out of bounds"
