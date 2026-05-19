"""Tests for html_legacy_normalizer — converts `<font>` markup to inline CSS."""
import pytest
from services.html_legacy_normalizer import (
    has_legacy_font,
    normalize_legacy_html,
)


def test_has_legacy_font_detects_basic():
    assert has_legacy_font('<font color="#000">x</font>') is True
    assert has_legacy_font('<p>plain</p>') is False
    assert has_legacy_font('') is False
    assert has_legacy_font(None) is False


def test_has_legacy_font_case_insensitive():
    assert has_legacy_font('<FONT COLOR="#000">x</FONT>') is True
    assert has_legacy_font('<Font color="red">x</Font>') is True


def test_normalize_color_only():
    out = normalize_legacy_html('<font color="#ff0000">red</font>')
    assert '<font' not in out.lower()
    assert '<span style="color:#ff0000">red</span>' in out


def test_normalize_face_and_size():
    out = normalize_legacy_html('<font face="Arial" size="5">big</font>')
    assert '<font' not in out.lower()
    assert 'font-family:Arial' in out
    assert 'font-size:24px' in out


def test_normalize_color_face_size_all():
    out = normalize_legacy_html('<font face="Verdana" size="3" color="#000000">all</font>')
    assert '<font' not in out.lower()
    assert 'color:#000000' in out
    assert 'font-family:Verdana' in out
    assert 'font-size:16px' in out  # size=3 -> 16px


def test_normalize_preserves_children():
    out = normalize_legacy_html(
        '<font color="#fff"><b>bold</b> and <em>em</em></font>'
    )
    assert '<b>bold</b>' in out
    assert '<em>em</em>' in out
    assert 'color:#fff' in out


def test_normalize_preserves_surrounding_html():
    src = '<h1>Title</h1><p><font color="#000">body</font></p>'
    out = normalize_legacy_html(src)
    assert '<h1>Title</h1>' in out
    assert '<font' not in out.lower()
    assert '<span style="color:#000">body</span>' in out


def test_normalize_idempotent():
    src = '<font color="#abc">x</font>'
    once = normalize_legacy_html(src)
    twice = normalize_legacy_html(once)
    assert once == twice


def test_normalize_empty_strings():
    assert normalize_legacy_html('') == ''
    assert normalize_legacy_html(None) == ''


def test_normalize_no_changes_when_no_font():
    src = '<h1 style="color:#000">x</h1><p>y</p>'
    assert normalize_legacy_html(src) == src


def test_unknown_size_dropped():
    """Sizes outside 1..7 (HTML4 spec) are dropped silently."""
    out = normalize_legacy_html('<font size="42">x</font>')
    # No font-size declared because 42 isn't in the map
    assert 'font-size' not in out
    assert '<span>x</span>' in out or '<span style="">x</span>' in out


def test_real_user_pattern():
    """Pattern from the user's project a0b4069e-... slide 0 el 1."""
    src = (
        '<h1 style="font-family:Inter, sans-serif;font-size:72px;font-weight:900;">'
        '<font color="#000000">Capa: O Jeito Intelbras de Atender</font></h1>'
        '<p><font color="#000000">Bem-vindo ao treinamento...</font></p>'
    )
    out = normalize_legacy_html(src)
    # All <font> tags must be gone
    assert '<font' not in out.lower()
    # Color preserved as inline CSS on the new span
    assert 'color:#000000' in out
    # Original h1 inline style untouched
    assert 'font-size:72px;font-weight:900' in out
    # Title text preserved
    assert 'Capa: O Jeito Intelbras de Atender' in out
