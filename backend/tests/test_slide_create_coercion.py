"""Regression test: SlideCreate must tolerate non-int width/height inputs
that come from PPT-imported projects whose existing slides store dimensions
as strings or floats. Before this fix, adding a new slide to such a project
returned 422 in production.
"""
import pytest
from models import SlideCreate


class TestSlideCreateDimensionCoercion:
    def test_normal_int_kept(self):
        s = SlideCreate(width=1920, height=820)
        assert s.width == 1920
        assert s.height == 820

    def test_default_when_omitted(self):
        s = SlideCreate()
        assert s.width == 1920
        assert s.height == 820

    def test_string_digits_coerced(self):
        # Production data: "1280" coming from PPT importer
        s = SlideCreate(width="1280", height="720")
        assert s.width == 1280
        assert s.height == 720

    def test_string_with_px_suffix_coerced(self):
        s = SlideCreate(width="1920px", height="820px")
        assert s.width == 1920
        assert s.height == 820

    def test_float_coerced(self):
        s = SlideCreate(width=1280.5, height=720.0)
        assert s.width == 1280
        assert s.height == 720

    def test_zero_falls_back_to_default(self):
        s = SlideCreate(width=0, height=0)
        assert s.width == 1920
        assert s.height == 1920  # fallback for both

    def test_none_falls_back_to_default(self):
        # Pydantic might treat None as "use default"; we coerce to safe value
        s = SlideCreate(width=None, height=None)
        assert s.width == 1920
        assert s.height == 1920

    def test_garbage_string_falls_back(self):
        s = SlideCreate(width="not a number", height="abc")
        assert s.width == 1920
        assert s.height == 1920

    def test_other_fields_still_work(self):
        s = SlideCreate(title="Test Slide", background="#abc123", width=1024, height=768)
        assert s.title == "Test Slide"
        assert s.background == "#abc123"
        assert s.width == 1024
