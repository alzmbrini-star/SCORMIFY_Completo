"""Tests for editor-chat and media-chat op application.

The LLM calls are mocked — we test the application layer that mutates
the project/session state given a list of structured ops.
"""
import pytest
from routes.editor_chat import _apply_ops, _build_course_summary


class TestBuildCourseSummary:
    def test_includes_title_and_text_content(self):
        slides = [
            {"title": "Intro", "background": "#fff", "elements": [
                {"type": "text", "content": "Hello world"},
            ]}
        ]
        summary = _build_course_summary(slides)
        assert summary[0]["title"] == "Intro"
        assert summary[0]["elements"][0]["content"] == "Hello world"

    def test_marks_interactive_as_non_editable(self):
        slides = [
            {"title": "Quiz Slide", "elements": [
                {"type": "html", "htmlContent": "<div>simulator</div>"},
                {"type": "quiz", "content": ""},
            ]}
        ]
        summary = _build_course_summary(slides)
        assert "not editable" in summary[0]["elements"][0]["summary"]
        assert "not editable" in summary[0]["elements"][1]["summary"]

    def test_truncates_long_content(self):
        slides = [
            {"title": "x", "elements": [{"type": "text", "content": "a" * 500}]}
        ]
        summary = _build_course_summary(slides)
        assert len(summary[0]["elements"][0]["content"]) == 200


class TestApplyOps:
    def test_edit_slide_title(self):
        slides = [{"title": "Old", "elements": []}]
        applied = _apply_ops(slides, [{"type": "edit_slide_title", "slideIndex": 0, "title": "New"}])
        assert slides[0]["title"] == "New"
        assert len(applied) == 1

    def test_edit_element_content_only_for_text(self):
        slides = [{
            "title": "x",
            "elements": [
                {"type": "text", "content": "old"},
                {"type": "html", "htmlContent": "<div/>"},
            ],
        }]
        applied = _apply_ops(slides, [
            {"type": "edit_element_content", "slideIndex": 0, "elementIndex": 0, "content": "new"},
            # Attempt to edit html — should be silently skipped (not in text/shape)
            {"type": "edit_element_content", "slideIndex": 0, "elementIndex": 1, "content": "evil"},
        ])
        assert slides[0]["elements"][0]["content"] == "new"
        assert slides[0]["elements"][1]["htmlContent"] == "<div/>"  # untouched
        assert len(applied) == 1

    def test_edit_element_style_merges_patch(self):
        slides = [{"elements": [{"type": "text", "style": {"fontColor": "#000"}}]}]
        _apply_ops(slides, [{
            "type": "edit_element_style", "slideIndex": 0, "elementIndex": 0,
            "style": {"fontSize": 24, "fontWeight": "bold"},
        }])
        s = slides[0]["elements"][0]["style"]
        # Original keeps + new merged
        assert s["fontColor"] == "#000"
        assert s["fontSize"] == 24
        assert s["fontWeight"] == "bold"

    def test_add_text_element_with_defaults(self):
        slides = [{"elements": []}]
        _apply_ops(slides, [{"type": "add_text_element", "slideIndex": 0, "content": "Hello"}])
        els = slides[0]["elements"]
        assert len(els) == 1
        assert els[0]["type"] == "text"
        assert els[0]["content"] == "Hello"
        assert els[0]["x"] == 100
        assert els[0]["style"]["fontSize"] == 20

    def test_delete_element(self):
        slides = [{"elements": [{"type": "text"}, {"type": "text"}]}]
        _apply_ops(slides, [{"type": "delete_element", "slideIndex": 0, "elementIndex": 1}])
        assert len(slides[0]["elements"]) == 1

    def test_change_slide_background(self):
        slides = [{"background": "#fff"}]
        _apply_ops(slides, [{"type": "change_slide_background", "slideIndex": 0, "background": "#000"}])
        assert slides[0]["background"] == "#000"

    def test_move_slide(self):
        slides = [{"title": "A"}, {"title": "B"}, {"title": "C"}]
        _apply_ops(slides, [{"type": "move_slide", "fromIndex": 0, "toIndex": 2}])
        assert [s["title"] for s in slides] == ["B", "C", "A"]

    def test_delete_slide(self):
        slides = [{"title": "A"}, {"title": "B"}]
        _apply_ops(slides, [{"type": "delete_slide", "slideIndex": 0}])
        assert slides == [{"title": "B"}]

    def test_out_of_bounds_ops_silently_skipped(self):
        slides = [{"title": "A", "elements": []}]
        applied = _apply_ops(slides, [
            {"type": "edit_slide_title", "slideIndex": 999, "title": "X"},
            {"type": "edit_element_content", "slideIndex": 0, "elementIndex": 999, "content": "X"},
        ])
        assert applied == []
        assert slides[0]["title"] == "A"

    def test_malformed_op_skipped(self):
        slides = [{"title": "A"}]
        applied = _apply_ops(slides, [
            {"type": "edit_slide_title"},  # missing slideIndex
            {"type": "unknown_op_type", "slideIndex": 0},
        ])
        assert applied == []
