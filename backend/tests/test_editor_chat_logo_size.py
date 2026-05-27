"""Tests for editor_chat apply_brand_identity logo sizing + brand-kit
re-apply semantics. Regression coverage for the production bug where:
  1. "Aplique o brand kit completo para todos os slides" emitted
     `apply_brand_palette` (no logo) instead of `apply_brand_identity`.
  2. The logo ignored BrandKit's `logoPlacement` (always landed top-right)
     and used a square 96x96 bounding box that visually shrunk wide logos.
"""
from routes.editor_chat import _apply_ops


def _slide(title: str = "S", elements=None) -> dict:
    return {
        "id": "s_" + title,
        "title": title,
        "background": "#FFFFFF",
        "elements": elements or [],
    }


def _kit(**overrides) -> dict:
    base = {
        "primaryColor": "#1e3a8a",
        "accentColor": "#f59e0b",
        "secondaryColor": "#0f172a",
        "fontFamily": "Inter",
    }
    base.update(overrides)
    return base


def _logo(slide):
    return next(e for e in slide["elements"] if e.get("isBrandLogo"))


def test_default_size_is_96_with_landscape_aspect():
    """Default logoSize=96 → box is 96 wide × 38 tall (~2.5:1 aspect),
    matching the legacy static export path so wide logos look natural."""
    slides = [_slide("A")]
    _apply_ops(slides, [{"type": "apply_brand_identity", "allSlides": True}],
               brand_backgrounds=[], brand_kit=_kit(), brand_logo_url="/logo.png")
    logo = _logo(slides[0])
    assert logo["width"] == 96
    assert logo["height"] == 38   # round(96 / 2.5) = 38


def test_uses_kit_logo_size():
    slides = [_slide("A")]
    _apply_ops(slides, [{"type": "apply_brand_identity", "allSlides": True}],
               brand_backgrounds=[], brand_kit=_kit(logoSize=160), brand_logo_url="/logo.png")
    logo = _logo(slides[0])
    assert logo["width"] == 160
    assert logo["height"] == 64  # round(160 / 2.5) = 64


def test_op_overrides_kit_size():
    slides = [_slide("A")]
    _apply_ops(slides, [{"type": "apply_brand_identity", "allSlides": True, "logoSize": "large"}],
               brand_backgrounds=[], brand_kit=_kit(logoSize=96), brand_logo_url="/logo.png")
    logo = _logo(slides[0])
    assert logo["width"] == 160


def test_op_size_int_clamped():
    for raw, expected_w in ((9999, 320), (0, 32)):
        sl = _slide("A")
        _apply_ops([sl], [{"type": "apply_brand_identity", "allSlides": True, "logoSize": raw}],
                   brand_backgrounds=[], brand_kit=_kit(), brand_logo_url="/logo.png")
        assert _logo(sl)["width"] == expected_w


def test_uses_kit_placement_bottom_left():
    """Regression: if BrandKit.logoPlacement='bottom-left' and the op doesn't
    set logoCorner, the logo must land bottom-left, NOT default top-right."""
    slides = [_slide("A")]
    kit = _kit(logoPlacement="bottom-left", logoSize=96)
    _apply_ops(slides, [{"type": "apply_brand_identity", "allSlides": True}],
               brand_backgrounds=[], brand_kit=kit, brand_logo_url="/logo.png")
    logo = _logo(slides[0])
    # bottom-left: x = margin (24), y = canvas_h - logo_h - margin
    assert logo["x"] == 24
    assert logo["y"] == 820 - 38 - 24


def test_uses_kit_placement_bottom_center():
    slides = [_slide("A")]
    kit = _kit(logoPlacement="bottom-center")
    _apply_ops(slides, [{"type": "apply_brand_identity", "allSlides": True}],
               brand_backgrounds=[], brand_kit=kit, brand_logo_url="/logo.png")
    logo = _logo(slides[0])
    # bottom-center: x = (canvas_w - logo_w) / 2 = (1920 - 96) / 2 = 912
    assert logo["x"] == 912
    assert logo["y"] == 820 - 38 - 24


def test_op_corner_beats_kit_placement():
    slides = [_slide("A")]
    kit = _kit(logoPlacement="bottom-left")
    _apply_ops(slides, [{
        "type": "apply_brand_identity", "allSlides": True, "logoCorner": "top-left",
    }], brand_backgrounds=[], brand_kit=kit, brand_logo_url="/logo.png")
    logo = _logo(slides[0])
    # top-left: 24, 24
    assert logo["x"] == 24 and logo["y"] == 24


def test_intro_conclusion_only_skips_middle_slides():
    slides = [_slide("A"), _slide("B"), _slide("C")]
    kit = _kit(logoPlacement="intro-conclusion-only")
    _apply_ops(slides, [{"type": "apply_brand_identity", "allSlides": True}],
               brand_backgrounds=[], brand_kit=kit, brand_logo_url="/logo.png")
    # First + last get logo, middle does NOT
    assert any(e.get("isBrandLogo") for e in slides[0]["elements"])
    assert not any(e.get("isBrandLogo") for e in slides[1]["elements"])
    assert any(e.get("isBrandLogo") for e in slides[2]["elements"])


def test_intro_conclusion_only_strips_stale_middle_logo():
    """Re-applying with intro-conclusion-only must REMOVE any logo previously
    added to middle slides under a different placement."""
    slides = [_slide("A"), _slide("B"), _slide("C")]
    # First pass: apply with bottom-right (all slides get logo).
    _apply_ops(slides, [{"type": "apply_brand_identity", "allSlides": True}],
               brand_backgrounds=[], brand_kit=_kit(logoPlacement="bottom-right"),
               brand_logo_url="/logo.png")
    assert all(any(e.get("isBrandLogo") for e in s["elements"]) for s in slides)
    # Second pass: switch to intro-conclusion-only.
    _apply_ops(slides, [{"type": "apply_brand_identity", "allSlides": True}],
               brand_backgrounds=[], brand_kit=_kit(logoPlacement="intro-conclusion-only"),
               brand_logo_url="/logo.png")
    assert any(e.get("isBrandLogo") for e in slides[0]["elements"])
    assert not any(e.get("isBrandLogo") for e in slides[1]["elements"])
    assert any(e.get("isBrandLogo") for e in slides[2]["elements"])


def test_idempotent_resync_on_reapply():
    slides = [_slide("A")]
    _apply_ops(slides, [{"type": "apply_brand_identity", "allSlides": True}],
               brand_backgrounds=[], brand_kit=_kit(), brand_logo_url="/logo.png")
    _apply_ops(slides, [{
        "type": "apply_brand_identity", "allSlides": True,
        "logoSize": "large", "logoCorner": "bottom-right",
    }], brand_backgrounds=[], brand_kit=_kit(), brand_logo_url="/logo.png")
    logos = [e for e in slides[0]["elements"] if e.get("isBrandLogo")]
    assert len(logos) == 1
    assert logos[0]["width"] == 160
    assert logos[0]["height"] == 64
    # bottom-right: 1920-160-24, 820-64-24
    assert logos[0]["x"] == 1920 - 160 - 24
    assert logos[0]["y"] == 820 - 64 - 24


def test_skips_logo_if_no_url():
    slides = [_slide("A")]
    applied = _apply_ops(slides, [{"type": "apply_brand_identity", "allSlides": True}],
                        brand_backgrounds=[], brand_kit=_kit(), brand_logo_url="")
    assert applied and applied[0]["logoInsertedCount"] == 0
    assert all(not e.get("isBrandLogo") for e in slides[0]["elements"])


def test_palette_and_font_applied():
    slides = [_slide("A", elements=[{"id": "t1", "type": "text", "content": "Hi", "style": {}}])]
    _apply_ops(slides, [{"type": "apply_brand_identity", "allSlides": True}],
               brand_backgrounds=[], brand_kit=_kit(), brand_logo_url="/logo.png")
    assert slides[0]["background"] == "#1e3a8a"
    txt = next(e for e in slides[0]["elements"] if e["type"] == "text")
    assert txt["style"]["fontFamily"] == "Inter"
    assert txt["style"]["fontColor"]
