"""Tests for editor_chat apply_brand_identity logo sizing + brand-kit
re-apply semantics. Regression coverage for the production bug where
"Aplique o brand kit completo para todos os slides" emitted
`apply_brand_palette` (no logo) instead of `apply_brand_identity`, and
for the new author-configurable logo size feature.
"""
from routes.editor_chat import _apply_ops


def _slide(title: str = "S", elements=None) -> dict:
    return {
        "id": "s_" + title,
        "title": title,
        "background": "#FFFFFF",
        "elements": elements or [],
    }


def _kit() -> dict:
    return {
        "primaryColor": "#1e3a8a",
        "accentColor": "#f59e0b",
        "secondaryColor": "#0f172a",
        "fontFamily": "Inter",
    }


def test_apply_brand_identity_inserts_logo_with_default_size():
    slides = [_slide("A"), _slide("B")]
    ops = [{"type": "apply_brand_identity", "allSlides": True}]
    applied = _apply_ops(
        slides, ops,
        brand_backgrounds=[],
        brand_kit=_kit(),
        brand_logo_url="/api/companies/c1/assets/asset1/file",
    )
    assert applied and applied[0]["type"] == "apply_brand_identity"
    for sl in slides:
        logos = [e for e in sl["elements"] if e.get("isBrandLogo")]
        assert len(logos) == 1
        # Default size = 96 px
        assert logos[0]["width"] == 96
        assert logos[0]["height"] == 96


def test_apply_brand_identity_uses_kit_logo_size():
    slides = [_slide("A")]
    kit = _kit()
    kit["logoSize"] = 160
    ops = [{"type": "apply_brand_identity", "allSlides": True}]
    _apply_ops(slides, ops, brand_backgrounds=[], brand_kit=kit, brand_logo_url="/logo.png")
    logo = next(e for e in slides[0]["elements"] if e.get("isBrandLogo"))
    assert logo["width"] == 160
    assert logo["height"] == 160


def test_apply_brand_identity_op_size_overrides_kit():
    slides = [_slide("A")]
    kit = _kit()
    kit["logoSize"] = 96
    ops = [{"type": "apply_brand_identity", "allSlides": True, "logoSize": "large"}]
    _apply_ops(slides, ops, brand_backgrounds=[], brand_kit=kit, brand_logo_url="/logo.png")
    logo = next(e for e in slides[0]["elements"] if e.get("isBrandLogo"))
    assert logo["width"] == 160


def test_apply_brand_identity_op_size_int():
    slides = [_slide("A")]
    ops = [{"type": "apply_brand_identity", "allSlides": True, "logoSize": 200}]
    _apply_ops(slides, ops, brand_backgrounds=[], brand_kit=_kit(), brand_logo_url="/logo.png")
    logo = next(e for e in slides[0]["elements"] if e.get("isBrandLogo"))
    assert logo["width"] == 200


def test_apply_brand_identity_op_size_clamped():
    slides = [_slide("A")]
    # 9999 should clamp to 320, 0 should clamp to 32
    for raw, expected in ((9999, 320), (0, 32)):
        sl = _slide("A")
        _apply_ops([sl], [{"type": "apply_brand_identity", "allSlides": True, "logoSize": raw}],
                   brand_backgrounds=[], brand_kit=_kit(), brand_logo_url="/logo.png")
        logo = next(e for e in sl["elements"] if e.get("isBrandLogo"))
        assert logo["width"] == expected


def test_apply_brand_identity_idempotent_resync_on_reapply():
    """Re-running apply_brand_identity must SYNC size/corner of an existing
    brand-logo element instead of appending a duplicate."""
    slides = [_slide("A")]
    # First apply (default 96, top-right).
    _apply_ops(slides, [{"type": "apply_brand_identity", "allSlides": True}],
               brand_backgrounds=[], brand_kit=_kit(), brand_logo_url="/logo.png")
    # Second apply (large size, bottom-right).
    _apply_ops(slides, [{
        "type": "apply_brand_identity", "allSlides": True,
        "logoSize": "large", "logoCorner": "bottom-right",
    }], brand_backgrounds=[], brand_kit=_kit(), brand_logo_url="/logo.png")
    logos = [e for e in slides[0]["elements"] if e.get("isBrandLogo")]
    assert len(logos) == 1   # no duplicate
    assert logos[0]["width"] == 160
    # bottom-right means y > 0 and x = 1920-160-24
    assert logos[0]["x"] == 1920 - 160 - 24
    assert logos[0]["y"] == 820 - 160 - 24


def test_apply_brand_identity_skips_logo_if_no_url():
    slides = [_slide("A")]
    applied = _apply_ops(slides, [{"type": "apply_brand_identity", "allSlides": True}],
                        brand_backgrounds=[], brand_kit=_kit(), brand_logo_url="")
    assert applied and applied[0]["logoInsertedCount"] == 0
    assert all(not e.get("isBrandLogo") for e in slides[0]["elements"])


def test_apply_brand_identity_applies_palette_colors_and_font():
    slides = [_slide("A", elements=[{
        "id": "t1", "type": "text", "content": "Hello", "style": {},
    }])]
    _apply_ops(slides, [{"type": "apply_brand_identity", "allSlides": True}],
               brand_backgrounds=[], brand_kit=_kit(), brand_logo_url="/logo.png")
    assert slides[0]["background"] == "#1e3a8a"  # primary
    text_el = next(e for e in slides[0]["elements"] if e["type"] == "text")
    assert text_el["style"]["fontFamily"] == "Inter"
    assert text_el["style"]["fontColor"]  # contrast color resolved
