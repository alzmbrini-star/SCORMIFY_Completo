"""Tests that the Editor Chat AI cannot inject plate styles into text
elements via the `edit_element_style` op.

User explicitly rejected plates (textBackgroundColor / backgroundColor /
padding / borderRadius behind text). Even if the LLM ignores the prompt
prohibition, the backend MUST filter banned keys.
"""
from routes.editor_chat import _apply_ops


def _slide_with_text(style=None):
    return [{
        "id": "s1",
        "title": "T",
        "elements": [{
            "id": "e1",
            "type": "text",
            "content": "hello",
            "style": style or {},
        }],
    }]


class TestEditorChatPlatesProhibition:
    def test_backgroundColor_filtered_from_llm_proposal(self):
        slides = _slide_with_text()
        _apply_ops(slides, [{
            "type": "edit_element_style",
            "slideIndex": 0, "elementIndex": 0,
            "style": {"fontColor": "#0f172a", "backgroundColor": "#0f172a"},
        }])
        s = slides[0]["elements"][0]["style"]
        assert s.get("fontColor") == "#0f172a"
        assert "backgroundColor" not in s

    def test_textBackgroundColor_padding_borderRadius_filtered(self):
        slides = _slide_with_text()
        _apply_ops(slides, [{
            "type": "edit_element_style",
            "slideIndex": 0, "elementIndex": 0,
            "style": {
                "fontSize": 24,
                "textBackgroundColor": "rgba(0,0,0,0.7)",
                "padding": "12px",
                "borderRadius": "8px",
                "boxShadow": "0 1px 2px black",
                "textShadow": "0 1px 1px black",
            },
        }])
        s = slides[0]["elements"][0]["style"]
        assert s.get("fontSize") == 24
        for banned in ("textBackgroundColor", "padding", "borderRadius",
                       "boxShadow", "textShadow", "backgroundColor"):
            assert banned not in s, f"banned key {banned} leaked"

    def test_existing_plate_residue_is_stripped(self):
        slides = _slide_with_text(style={
            "fontColor": "#fff",
            "backgroundColor": "#0f172a",
            "textBackgroundColor": "#0f172a",
            "padding": "12px",
            "borderRadius": "8px",
        })
        _apply_ops(slides, [{
            "type": "edit_element_style",
            "slideIndex": 0, "elementIndex": 0,
            "style": {"fontColor": "#000000"},
        }])
        s = slides[0]["elements"][0]["style"]
        assert s.get("fontColor") == "#000000"
        for banned in ("backgroundColor", "textBackgroundColor", "padding", "borderRadius"):
            assert banned not in s

    def test_allowed_keys_passed_through(self):
        slides = _slide_with_text()
        _apply_ops(slides, [{
            "type": "edit_element_style",
            "slideIndex": 0, "elementIndex": 0,
            "style": {
                "fontColor": "#0f172a",
                "fontSize": 18,
                "fontWeight": "bold",
                "fontFamily": "Inter",
                "textAlign": "center",
            },
        }])
        s = slides[0]["elements"][0]["style"]
        assert s["fontColor"] == "#0f172a"
        assert s["fontSize"] == 18
        assert s["fontWeight"] == "bold"
        assert s["fontFamily"] == "Inter"
        assert s["textAlign"] == "center"
