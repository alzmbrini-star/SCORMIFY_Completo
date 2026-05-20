"""Tests for html_container_bg_stripper — removes "island plates" from
htmlContent wrapper divs.
"""
from services.html_container_bg_stripper import strip_html_container_backgrounds


def test_strips_full_bleed_wrapper_background():
    """The AI Agent's typical island wrapper must lose its background."""
    html = (
        '<div style="width:100%;height:100%;background:#3b82f6;">'
        '<h1 style="color:#ffffff;">Microlearning</h1>'
        '</div>'
    )
    new_html, stripped = strip_html_container_backgrounds(html, "#ffffff")
    assert stripped >= 1
    # Background declaration is gone
    assert "background:#3b82f6" not in new_html
    # Text and other styles preserved
    assert "<h1" in new_html
    assert "color:#ffffff" in new_html


def test_preserves_badge_chip_button():
    """Cosmetic accent boxes (badges/chips/buttons) must KEEP their bg."""
    html = (
        '<div class="badge" style="background:#f59e0b;">NOVO</div>'
        '<span class="chip" style="background:#3b82f6;">Tag</span>'
        '<button class="btn" style="background:#0f172a;">Click</button>'
    )
    new_html, stripped = strip_html_container_backgrounds(html, "#ffffff")
    assert stripped == 0
    assert "background:#f59e0b" in new_html
    assert "background:#3b82f6" in new_html
    assert "background:#0f172a" in new_html


def test_strips_wrapper_with_text_leaf():
    """Wrapper div containing >20 chars of text gets bg stripped."""
    html = (
        '<div style="background:#3b82f6;padding:20px;">'
        'Conteúdo de texto longo dentro do wrapper'
        '</div>'
    )
    new_html, stripped = strip_html_container_backgrounds(html, "#ffffff")
    assert stripped == 1
    assert "background:#3b82f6" not in new_html
    # Other styles (padding) preserved
    assert "padding:20px" in new_html


def test_preserves_table_cells():
    """<td>/<th> backgrounds are intentional table styling — keep them."""
    html = (
        '<table><tr>'
        '<td style="background:#f3f4f6;">Cell A</td>'
        '<td style="background:#e5e7eb;">Cell B</td>'
        '</tr></table>'
    )
    new_html, stripped = strip_html_container_backgrounds(html, "#ffffff")
    assert stripped == 0
    assert "background:#f3f4f6" in new_html


def test_idempotent():
    html = (
        '<div style="width:100%;height:100%;background:#3b82f6;">'
        '<h1>Title</h1>'
        '</div>'
    )
    once, n1 = strip_html_container_backgrounds(html, "#ffffff")
    twice, n2 = strip_html_container_backgrounds(once, "#ffffff")
    assert n2 == 0
    assert once == twice


def test_no_change_when_no_background():
    html = '<div style="padding:20px;"><p>Hi</p></div>'
    new_html, stripped = strip_html_container_backgrounds(html, "#ffffff")
    assert stripped == 0
    assert new_html == html


def test_user_real_pattern_intelbras_itec():
    """Reproduces the user's screenshot: AI-generated Card with hard
    `background:#3b82f6` wrapper that conflicted with white slide bg."""
    html = (
        '<div style="width:100%;height:100%;background:#3b82f6;'
        'display:flex;align-items:center;justify-content:center;">'
        '<div><h1 style="color:#ffffff;font-size:72px;">'
        'Microlearning: A Nova Era do T&D</h1></div>'
        '</div>'
    )
    new_html, stripped = strip_html_container_backgrounds(html, "#ffffff")
    assert stripped >= 1
    # The outer #3b82f6 is gone
    assert "#3b82f6" not in new_html
    # Layout properties preserved (so the centering still works)
    assert "display:flex" in new_html
    # Title text intact
    assert "Microlearning" in new_html


def test_handles_empty_and_none():
    assert strip_html_container_backgrounds("", "#fff") == ("", 0)
    assert strip_html_container_backgrounds(None, "#fff") == ("", 0)
