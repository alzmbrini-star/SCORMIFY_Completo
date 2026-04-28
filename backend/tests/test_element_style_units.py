"""Regression tests for ElementStyle field validators that accept CSS strings
with units (e.g. "24px", "1.5rem", "8px"). Bug reported by user: SCORM and
HTML exports failed with 500 on projects whose slides had fontSize="24px"
(string with px) — the legacy Project Pydantic model rejected those values.

Fix: ElementStyle now coerces numeric strings with units in fontSize,
strokeWidth, and borderRadius via a single field_validator(mode='before').
"""
import pytest

from models import ElementStyle, ElementUpdate, Project


def test_fontSize_accepts_px_string():
    s = ElementStyle(fontSize="24px")
    assert s.fontSize == 24.0


def test_fontSize_accepts_rem_string():
    s = ElementStyle(fontSize="1.5rem")
    assert s.fontSize == 1.5


def test_fontSize_accepts_pt_string():
    s = ElementStyle(fontSize="14pt")
    assert s.fontSize == 14.0


def test_fontSize_accepts_negative_numeric_string():
    s = ElementStyle(fontSize="-2px")
    assert s.fontSize == -2.0


def test_fontSize_accepts_plain_number():
    s = ElementStyle(fontSize=18)
    assert s.fontSize == 18.0


def test_fontSize_empty_string_becomes_none():
    s = ElementStyle(fontSize="")
    assert s.fontSize is None


def test_fontSize_invalid_string_becomes_none():
    s = ElementStyle(fontSize="auto")
    assert s.fontSize is None


def test_strokeWidth_borderRadius_accept_units():
    s = ElementStyle(strokeWidth="2px", borderRadius="8px", fontSize="34px")
    assert s.strokeWidth == 2.0
    assert s.borderRadius == 8.0
    assert s.fontSize == 34.0


def test_ElementUpdate_with_unit_strings():
    u = ElementUpdate(style={"fontSize": "24px", "borderRadius": "8px"})
    assert u.style.fontSize == 24.0
    assert u.style.borderRadius == 8.0


def test_full_Project_parse_with_fontSize_px_string():
    """Regression: the exact failing case from the user's bug report."""
    proj = {
        "id": "p1",
        "name": "NR35 Test",
        "course": {
            "metadata": {"title": "NR35"},
            "slides": [
                {"id": "s1", "title": "Slide 1", "elements": [
                    {"id": "e1", "type": "text", "style": {"fontSize": "24px"}},
                    {"id": "e2", "type": "text", "style": {"fontSize": "34px"}},
                ]}
            ]
        }
    }
    p = Project(**proj)
    assert p.course.slides[0].elements[0].style.fontSize == 24.0
    assert p.course.slides[0].elements[1].style.fontSize == 34.0
