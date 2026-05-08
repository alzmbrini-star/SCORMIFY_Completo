"""Tests for the numeric-field normalization migration."""
import pytest
from routes.admin_migrations import (
    _coerce_to_int,
    _coerce_to_float,
    _normalize_dict_in_place,
    _normalize_project_inplace,
    INT_FIELDS_SLIDE,
    FLOAT_FIELDS_SLIDE,
    FLOAT_FIELDS_ELEMENT,
    FLOAT_FIELDS_STYLE,
)


class TestCoerceToInt:
    def test_int_kept(self):
        assert _coerce_to_int(5) == (5, False)

    def test_float_truncated(self):
        assert _coerce_to_int(5.7) == (5, True)

    def test_string_with_digits(self):
        assert _coerce_to_int("1280") == (1280, True)
        assert _coerce_to_int("1280px") == (1280, True)

    def test_negative_string(self):
        assert _coerce_to_int("-50px") == (-50, True)

    def test_garbage_returns_none(self):
        assert _coerce_to_int("abc") == (None, False)
        assert _coerce_to_int(None) == (None, False)

    def test_bool_untouched(self):
        # Don't accidentally turn True into 1
        assert _coerce_to_int(True) == (True, False)


class TestCoerceToFloat:
    def test_float_kept(self):
        assert _coerce_to_float(5.5) == (5.5, False)

    def test_int_widened(self):
        # We mark int as 'changed' since type widens int → float
        assert _coerce_to_float(5) == (5.0, True)

    def test_string_with_decimal(self):
        v, changed = _coerce_to_float("12.5")
        assert v == 12.5 and changed is True

    def test_string_with_unit(self):
        v, changed = _coerce_to_float("1.5em")
        assert v == 1.5 and changed is True

    def test_garbage_returns_none(self):
        assert _coerce_to_float("nope") == (None, False)


class TestNormalizeDictInPlace:
    def test_coerces_int_field(self):
        d = {"width": "1280"}
        changes = _normalize_dict_in_place(d, ("width",), ())
        assert d["width"] == 1280
        assert changes == 1

    def test_coerces_float_field(self):
        d = {"x": "10.5"}
        changes = _normalize_dict_in_place(d, (), ("x",))
        assert d["x"] == 10.5
        assert changes == 1

    def test_no_op_when_clean(self):
        d = {"width": 1280, "x": 10.0}
        changes = _normalize_dict_in_place(d, ("width",), ("x",))
        assert changes == 0

    def test_skips_missing_keys(self):
        d = {"width": 1280}
        changes = _normalize_dict_in_place(d, ("height",), ())
        assert changes == 0


class TestNormalizeProjectInplace:
    def test_dirty_ppt_imported_project(self):
        """Real-world case: PPT-imported project with strings everywhere."""
        project = {
            "id": "p1",
            "course": {
                "slides": [
                    {
                        "id": "s1",
                        "width": "1280",        # → 1280
                        "height": "720px",      # → 720
                        "duration": "5.5",      # → 5.5
                        "elements": [
                            {
                                "id": "e1",
                                "x": "100",
                                "y": "200.5",
                                "width": "300",
                                "height": "150",
                                "style": {"fontSize": "24px", "opacity": "0.8"},
                            }
                        ],
                        "audio": [
                            {"volume": "0.7", "duration": "12"}
                        ],
                    }
                ]
            }
        }
        breakdown = _normalize_project_inplace(project)
        slide = project["course"]["slides"][0]
        assert slide["width"] == 1280
        assert slide["height"] == 720
        assert slide["duration"] == 5.5
        el = slide["elements"][0]
        assert el["x"] == 100.0
        assert el["y"] == 200.5
        assert el["width"] == 300.0
        assert el["height"] == 150.0
        assert el["style"]["fontSize"] == 24.0
        assert el["style"]["opacity"] == 0.8
        assert slide["audio"][0]["volume"] == 0.7
        assert slide["audio"][0]["duration"] == 12.0

        # Breakdown
        assert breakdown["slide_dims"] == 2  # width + height
        assert breakdown["slide_durations"] == 1
        assert breakdown["element_pos_size"] == 4  # x + y + width + height
        assert breakdown["element_styles"] == 2
        assert breakdown["audio_props"] == 2

    def test_clean_project_no_changes(self):
        project = {
            "id": "p1",
            "course": {
                "slides": [
                    {"width": 1280, "height": 720, "duration": 5.5, "elements": []}
                ]
            }
        }
        breakdown = _normalize_project_inplace(project)
        assert sum(breakdown.values()) == 0

    def test_handles_missing_course(self):
        project = {"id": "p1"}
        breakdown = _normalize_project_inplace(project)
        assert sum(breakdown.values()) == 0

    def test_handles_malformed_slides(self):
        project = {"id": "p1", "course": {"slides": "not a list"}}
        breakdown = _normalize_project_inplace(project)
        assert sum(breakdown.values()) == 0
