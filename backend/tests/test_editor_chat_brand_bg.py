"""Tests for Editor Chat brand background ops (2026-05-21).

User requested ability to ask the Editor Chat:
- "Apply the brand background on all slides"
- "Create N slides with brand background"
- "Apply brand background on slides 2 to 5"
"""
from routes.editor_chat import _apply_ops, _resolve_brand_background


BG = [
    {"id": "casset_aaa", "name": "Capa Corporativa", "category": "cover",
     "tags": ["capa"], "url": "/api/companies/co1/assets/casset_aaa/file"},
    {"id": "casset_bbb", "name": "Fundo Conteudo", "category": "content",
     "tags": ["conteudo"], "url": "/api/companies/co1/assets/casset_bbb/file"},
]


def _course():
    return [
        {"id": "s0", "title": "A", "order": 0, "background": "#fff", "elements": []},
        {"id": "s1", "title": "B", "order": 1, "background": "#fff", "elements": []},
        {"id": "s2", "title": "C", "order": 2, "background": "#fff", "elements": []},
    ]


class TestResolveBrandBackground:
    def test_picks_first_when_no_id(self):
        b = _resolve_brand_background(BG)
        assert b["id"] == "casset_aaa"

    def test_picks_matching_id(self):
        b = _resolve_brand_background(BG, "casset_bbb")
        assert b["name"] == "Fundo Conteudo"

    def test_empty_library_returns_none(self):
        assert _resolve_brand_background([]) is None

    def test_unknown_id_falls_back_to_first(self):
        b = _resolve_brand_background(BG, "casset_zzz")
        # Fallback to first so the user action still produces an effect.
        assert b["id"] == "casset_aaa"


class TestAddSlideWithBrandBackground:
    def test_use_brand_background_true_attaches_first_asset(self):
        slides = _course()
        _apply_ops(slides, [{
            "type": "add_slide",
            "insertAfter": 2,
            "useBrandBackground": True,
        }], brand_backgrounds=BG)
        new_slide = slides[3]
        assert new_slide.get("backgroundImage") == BG[0]["url"]

    def test_brand_asset_id_attaches_specific_asset(self):
        slides = _course()
        _apply_ops(slides, [{
            "type": "add_slide",
            "insertAfter": 2,
            "brandAssetId": "casset_bbb",
        }], brand_backgrounds=BG)
        assert slides[3]["backgroundImage"] == BG[1]["url"]

    def test_no_brand_means_no_background_image(self):
        slides = _course()
        _apply_ops(slides, [{
            "type": "add_slide",
            "insertAfter": 2,
        }], brand_backgrounds=BG)
        # No useBrand flag → backgroundImage NOT set
        assert "backgroundImage" not in slides[3]

    def test_use_brand_with_empty_library_is_silent(self):
        slides = _course()
        _apply_ops(slides, [{
            "type": "add_slide",
            "insertAfter": 2,
            "useBrandBackground": True,
        }], brand_backgrounds=[])
        # Still creates the slide, just without backgroundImage.
        assert len(slides) == 4
        assert "backgroundImage" not in slides[3]

    def test_bulk_creation_with_brand_bg(self):
        slides = _course()
        _apply_ops(slides, [{
            "type": "add_slide",
            "insertAfter": 2,
            "count": 5,
            "useBrandBackground": True,
        }], brand_backgrounds=BG)
        # All 5 new slides receive the brand background.
        for i in range(3, 8):
            assert slides[i].get("backgroundImage") == BG[0]["url"]

    def test_applied_op_flags_brand_used(self):
        slides = _course()
        applied = _apply_ops(slides, [{
            "type": "add_slide",
            "insertAfter": 0,
            "useBrandBackground": True,
        }], brand_backgrounds=BG)
        assert applied[0].get("brandBackgroundUsed") is True


class TestApplyBrandBackgroundOp:
    def test_all_slides_default_when_no_range(self):
        slides = _course()
        applied = _apply_ops(slides, [{
            "type": "apply_brand_background",
        }], brand_backgrounds=BG)
        # Default = all slides receive the first brand asset.
        for s in slides:
            assert s.get("backgroundImage") == BG[0]["url"]
        assert applied[0]["affectedSlides"] == [0, 1, 2]

    def test_explicit_all_slides_flag(self):
        slides = _course()
        _apply_ops(slides, [{
            "type": "apply_brand_background",
            "allSlides": True,
            "brandAssetId": "casset_bbb",
        }], brand_backgrounds=BG)
        for s in slides:
            assert s["backgroundImage"] == BG[1]["url"]

    def test_range_from_to(self):
        slides = _course()
        applied = _apply_ops(slides, [{
            "type": "apply_brand_background",
            "fromIndex": 1,
            "toIndex": 2,
        }], brand_backgrounds=BG)
        # Slide 0 untouched, slides 1 and 2 receive the bg.
        assert "backgroundImage" not in slides[0]
        assert slides[1]["backgroundImage"] == BG[0]["url"]
        assert slides[2]["backgroundImage"] == BG[0]["url"]
        assert applied[0]["affectedSlides"] == [1, 2]

    def test_range_clamped_to_valid_indices(self):
        slides = _course()
        _apply_ops(slides, [{
            "type": "apply_brand_background",
            "fromIndex": -5,
            "toIndex": 999,
        }], brand_backgrounds=BG)
        for s in slides:
            assert s["backgroundImage"] == BG[0]["url"]

    def test_empty_library_is_silent_noop(self):
        slides = _course()
        applied = _apply_ops(slides, [{
            "type": "apply_brand_background",
            "allSlides": True,
        }], brand_backgrounds=[])
        for s in slides:
            assert "backgroundImage" not in s
        assert applied == []


class TestSetSlideBackgroundImage:
    def test_set_via_brand_asset_id(self):
        slides = _course()
        _apply_ops(slides, [{
            "type": "set_slide_background_image",
            "slideIndex": 1,
            "brandAssetId": "casset_bbb",
        }], brand_backgrounds=BG)
        assert slides[1]["backgroundImage"] == BG[1]["url"]

    def test_set_via_explicit_url(self):
        slides = _course()
        _apply_ops(slides, [{
            "type": "set_slide_background_image",
            "slideIndex": 1,
            "imageUrl": "/custom/path.png",
        }], brand_backgrounds=[])
        assert slides[1]["backgroundImage"] == "/custom/path.png"

    def test_clear_removes_background_image(self):
        slides = _course()
        slides[1]["backgroundImage"] = "/old/bg.png"
        _apply_ops(slides, [{
            "type": "set_slide_background_image",
            "slideIndex": 1,
            "clear": True,
        }])
        assert "backgroundImage" not in slides[1]

    def test_out_of_range_silently_skipped(self):
        slides = _course()
        applied = _apply_ops(slides, [{
            "type": "set_slide_background_image",
            "slideIndex": 99,
            "brandAssetId": "casset_aaa",
        }], brand_backgrounds=BG)
        assert applied == []
