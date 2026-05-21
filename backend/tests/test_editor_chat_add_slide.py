"""Tests for the Editor Chat `add_slide` op (single + bulk insertion).

User asked (2026-05-21) to be able to insert N slides via the Editor Chat.
"""
from routes.editor_chat import _apply_ops


def _course():
    return [
        {"id": "s0", "title": "Slide A", "order": 0, "background": "#101010",
         "elements": []},
        {"id": "s1", "title": "Slide B", "order": 1, "background": "#202020",
         "elements": []},
        {"id": "s2", "title": "Slide C", "order": 2, "background": "#303030",
         "elements": []},
    ]


class TestAddSlideOp:
    def test_inserts_single_slide_after_given_index(self):
        slides = _course()
        applied = _apply_ops(slides, [{
            "type": "add_slide",
            "insertAfter": 0,
            "title": "Intro Nova",
        }])
        assert len(slides) == 4
        assert slides[1]["title"] == "Intro Nova"
        # Order field re-numbered canonically.
        assert [s["order"] for s in slides] == [0, 1, 2, 3]
        assert applied[0]["type"] == "add_slide"
        assert applied[0]["insertedAt"] == [1]
        assert applied[0]["count"] == 1

    def test_bulk_insert_count_n(self):
        slides = _course()
        _apply_ops(slides, [{
            "type": "add_slide",
            "insertAfter": 1,
            "count": 5,
            "title": "Modulo",
        }])
        assert len(slides) == 8
        # Inserted after index 1 → positions 2..6
        titles = [s["title"] for s in slides[2:7]]
        assert titles == ["Modulo 1", "Modulo 2", "Modulo 3", "Modulo 4", "Modulo 5"]
        # Original slide C now at the end.
        assert slides[-1]["title"] == "Slide C"
        assert [s["order"] for s in slides] == list(range(8))

    def test_count_cap_at_20(self):
        slides = _course()
        _apply_ops(slides, [{
            "type": "add_slide",
            "insertAfter": 2,
            "count": 9999,
        }])
        assert len(slides) == 3 + 20

    def test_inherits_background_from_previous_slide(self):
        slides = _course()
        _apply_ops(slides, [{
            "type": "add_slide",
            "insertAfter": 1,  # Slide B has bg #202020
            "title": "X",
        }])
        assert slides[2]["background"] == "#202020"

    def test_explicit_background_overrides_inheritance(self):
        slides = _course()
        _apply_ops(slides, [{
            "type": "add_slide",
            "insertAfter": 0,
            "background": "#abcdef",
        }])
        assert slides[1]["background"] == "#abcdef"

    def test_content_creates_text_element(self):
        slides = _course()
        _apply_ops(slides, [{
            "type": "add_slide",
            "insertAfter": 0,
            "title": "Com Texto",
            "content": "Conteudo do paragrafo de teste",
        }])
        new_slide = slides[1]
        assert len(new_slide["elements"]) == 1
        el = new_slide["elements"][0]
        assert el["type"] == "text"
        assert "Conteudo do paragrafo" in el["content"]
        assert "Conteudo do paragrafo" in el["htmlContent"]
        # No plate residue
        for banned in ("backgroundColor", "textBackgroundColor", "padding", "borderRadius"):
            assert banned not in el.get("style", {})

    def test_insert_at_start_with_minus_one(self):
        slides = _course()
        _apply_ops(slides, [{
            "type": "add_slide",
            "insertAfter": -1,
            "title": "Capa Nova",
        }])
        assert slides[0]["title"] == "Capa Nova"
        assert slides[1]["title"] == "Slide A"

    def test_insert_after_negative_out_of_range_clamps(self):
        slides = _course()
        _apply_ops(slides, [{
            "type": "add_slide",
            "insertAfter": -50,
            "title": "X",
        }])
        # Clamped to -1 → inserted at index 0
        assert slides[0]["title"] == "X"

    def test_insert_after_huge_index_appends_at_end(self):
        slides = _course()
        _apply_ops(slides, [{
            "type": "add_slide",
            "insertAfter": 9999,
            "title": "Fim",
        }])
        assert slides[-1]["title"] == "Fim"

    def test_new_slide_has_required_fields(self):
        slides = _course()
        _apply_ops(slides, [{"type": "add_slide", "insertAfter": 0}])
        s = slides[1]
        for key in ("id", "title", "order", "width", "height", "background",
                    "elements", "transition", "audio", "duration"):
            assert key in s, f"missing field {key}"
        assert s["width"] == 1920 and s["height"] == 820

    def test_default_title_when_empty(self):
        slides = _course()
        _apply_ops(slides, [{
            "type": "add_slide",
            "insertAfter": 0,
            "title": "",
        }])
        assert slides[1]["title"] == "Novo Slide"

    def test_malformed_count_falls_back_to_one(self):
        slides = _course()
        _apply_ops(slides, [{
            "type": "add_slide",
            "insertAfter": 0,
            "count": "not-a-number",
        }])
        assert len(slides) == 4

    def test_narration_script_persisted(self):
        slides = _course()
        _apply_ops(slides, [{
            "type": "add_slide",
            "insertAfter": 0,
            "narrationScript": "Esta narracao deve aparecer.",
        }])
        assert slides[1]["narrationScript"] == "Esta narracao deve aparecer."
