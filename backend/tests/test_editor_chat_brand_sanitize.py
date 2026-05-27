"""Regression tests for the production bug: LLM was hallucinating
`logoCorner: "top-right"` + `logoSize: 96` into `apply_brand_identity` ops
even when the user just said "Aplique o brand kit completo" — silently
overriding the super admin's BrandKit config (bottom-left + 160 px).
"""
from routes.editor_chat import (
    _user_mentioned_corner,
    _user_mentioned_size,
    _sanitize_brand_ops,
)


# ---- Detection helpers --------------------------------------------------

def test_corner_detection_simple():
    assert _user_mentioned_corner("logo no canto superior direito")
    assert _user_mentioned_corner("coloque a marca no centro")
    assert _user_mentioned_corner("logo na esquerda")
    assert _user_mentioned_corner("bottom-right corner please")


def test_corner_detection_negative():
    assert not _user_mentioned_corner("Aplique o brand kit completo para todos os slides")
    assert not _user_mentioned_corner("aplique a marca completa")
    assert not _user_mentioned_corner("identidade visual completa")
    assert not _user_mentioned_corner("")


def test_size_detection_simple():
    assert _user_mentioned_size("logo grande")
    assert _user_mentioned_size("logo pequeno")
    assert _user_mentioned_size("logo de 200px")
    assert _user_mentioned_size("ajuste o tamanho do logo")


def test_size_detection_negative():
    assert not _user_mentioned_size("Aplique o brand kit completo")
    assert not _user_mentioned_size("aplique a identidade visual")


# ---- Sanitizer ----------------------------------------------------------

def test_sanitize_strips_corner_when_user_silent():
    """The exact production scenario: user says 'aplique o brand kit completo'
    but LLM hallucinates `logoCorner: top-right`. Must be stripped."""
    ops = [{
        "type": "apply_brand_identity", "allSlides": True,
        "logoCorner": "top-right", "logoSize": 96,
    }]
    cleaned = _sanitize_brand_ops(ops, "Aplique o brand kit completo para todos os slides")
    assert "logoCorner" not in cleaned[0]
    assert "logoSize" not in cleaned[0]
    # Other fields preserved
    assert cleaned[0]["type"] == "apply_brand_identity"
    assert cleaned[0]["allSlides"] is True


def test_sanitize_preserves_corner_when_user_asks():
    ops = [{
        "type": "apply_brand_identity", "allSlides": True,
        "logoCorner": "bottom-right", "logoSize": "large",
    }]
    cleaned = _sanitize_brand_ops(ops, "Aplique a identidade com logo grande no canto inferior direito")
    assert cleaned[0]["logoCorner"] == "bottom-right"
    assert cleaned[0]["logoSize"] == "large"


def test_sanitize_only_strips_unrequested_axis():
    """User mentioned size but not corner → keep size, strip corner."""
    ops = [{
        "type": "apply_brand_identity", "allSlides": True,
        "logoCorner": "top-right", "logoSize": "large",
    }]
    cleaned = _sanitize_brand_ops(ops, "aplique a marca com logo grande")
    assert "logoCorner" not in cleaned[0]
    assert cleaned[0]["logoSize"] == "large"


def test_sanitize_leaves_other_ops_alone():
    ops = [
        {"type": "edit_slide_title", "slideIndex": 0, "title": "X", "logoCorner": "top-left"},
        {"type": "apply_brand_palette", "allSlides": True},
    ]
    cleaned = _sanitize_brand_ops(ops, "aplique o brand kit completo")
    # apply_brand_palette doesn't have these fields anyway
    # edit_slide_title's logoCorner is irrelevant (and we don't strip from it)
    assert cleaned[0].get("logoCorner") == "top-left"
    assert cleaned[1]["type"] == "apply_brand_palette"
