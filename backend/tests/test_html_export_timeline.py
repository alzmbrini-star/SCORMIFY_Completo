"""Regression test for HTML export timeline support (2026-02 fix).

The previous behaviour:
  - Elements with `startTime > 0` and no PPT animation were rendered
    inline with `visibility:hidden; opacity:0`.
  - The startTime timer applied `animation: fadeIn 0.3s` but did NOT
    reset the inline visibility/opacity. Because the keyframe has no
    `fill-mode: forwards`, after the 0.3 s animation completed the
    element snapped back to invisible.
  - Net effect: timeline scheduling was effectively dead — every
    `startTime > 0` element stayed hidden for the whole slide.

This test exercises the generator on a small synthetic course and
verifies the new code (a) explicitly resets visibility/opacity in the
show timer, and (b) gives the same priority to "initially hidden" over
custom `elem.style.opacity` in the initial render block.
"""
import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.html_exporter import generate_standalone_html  # noqa: E402


def _make_course():
    return {
        "id": "p1",
        "name": "Timeline Test",
        "enableVlibras": False,
        "course": {
            "metadata": {"title": "Timeline Test"},
            "slides": [
                {
                    "id": "s1",
                    "title": "Slide 1",
                    "width": 1280,
                    "height": 720,
                    "background": "#ffffff",
                    "duration": 10,
                    "elements": [
                        # Element A: appears at t=2 (startTime > 0)
                        {
                            "id": "e1",
                            "type": "text",
                            "content": "Aparece em 2 s",
                            "x": 100, "y": 100, "width": 400, "height": 60,
                            "startTime": 2,
                            "style": {"fontSize": 32, "fontColor": "#000"},
                        },
                        # Element B: visible from t=0, disappears at t=5
                        {
                            "id": "e2",
                            "type": "text",
                            "content": "Some at 0 → 5",
                            "x": 100, "y": 200, "width": 400, "height": 60,
                            "startTime": 0,
                            "endTime": 5,
                            "style": {"fontSize": 32, "fontColor": "#000"},
                        },
                        # Element C: custom opacity AND startTime > 0
                        # (previously the custom-opacity branch wrongly
                        # made the element visible from t=0)
                        {
                            "id": "e3",
                            "type": "text",
                            "content": "Custom opacity + delay",
                            "x": 100, "y": 300, "width": 400, "height": 60,
                            "startTime": 3,
                            "style": {"fontSize": 32, "fontColor": "#000",
                                      "opacity": 0.8},
                        },
                    ],
                    "annotations": [],
                }
            ],
        },
    }


def test_html_export_respects_timeline():
    html = asyncio.run(generate_standalone_html(
        project=_make_course(),
        assets_dir="/tmp",
        base_url="",
        questions=None,
        backend_url="",
        tutor_config=None,
    ))

    # 1) The show timer must reset visibility AND opacity (not just set
    #    animation). Look for the literal lines we added.
    assert "element.style.visibility = 'visible'" in html
    assert "element.style.opacity = String(elementOpacity)" in html

    # 2) The hide timer must apply `forwards` fill-mode so the element
    #    stays hidden after fadeOut completes.
    assert "fadeOut 0.3s ease-out forwards" in html

    # 3) The initial-render priority must put `initiallyHidden` BEFORE
    #    the custom opacity branch. We grep for the rough structural
    #    order (initiallyHidden block precedes the !hasAnimations
    #    opacity block).
    init_hidden_idx = html.find("else if (initiallyHidden)")
    custom_op_idx = html.find("else if (!hasAnimations && elem.style && elem.style.opacity")
    assert init_hidden_idx > 0
    assert custom_op_idx > 0
    assert init_hidden_idx < custom_op_idx, (
        "initiallyHidden block must come BEFORE custom-opacity block "
        "so timeline takes precedence over a user-set opacity value"
    )

    # 4) The startTime/endTime values flow into the slides JSON payload
    #    embedded in the HTML (the slide DOM is built at runtime by JS).
    assert '"startTime": 2' in html
    assert '"endTime": 5' in html
    assert '"startTime": 3' in html
    # And the JS that emits the data-* attributes is present.
    assert 'data-start-time="' in html
    assert 'data-end-time="' in html


def test_html_export_emits_timeline_timers():
    html = asyncio.run(generate_standalone_html(
        project=_make_course(),
        assets_dir="/tmp",
        base_url="",
        questions=None,
        backend_url="",
        tutor_config=None,
    ))

    # The timelineTimers array and its push calls must be present.
    assert "var timelineTimers = [];" in html
    assert "timelineTimers.push(showTimer);" in html
    assert "timelineTimers.push(hideTimer);" in html
    # And the cleanup loop on slide change must clear them.
    assert "clearTimeout" in html
