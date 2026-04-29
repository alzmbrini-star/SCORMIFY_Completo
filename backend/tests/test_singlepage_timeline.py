"""Tests: timeline (auto-play sequencial) for elements with startTime/endTime in
Single Page export. Implementação opção (a) — quando o aluno chega na seção,
elementos com startTime>0 ficam invisíveis e revelam-se em sequência. A seção
é gateada por um botão sintético `.sp-timeline-gate` que só completa após o
fim da timeline.
"""
from services.single_page_exporter import (
    _maybe_wrap_with_timeline,
    generate_single_page_html,
)


def test_element_without_timing_passes_through():
    el = {"type": "text", "content": "x"}
    out = _maybe_wrap_with_timeline("<div>x</div>", el)
    # No wrap when no timing
    assert out == "<div>x</div>"


def test_element_with_starttime_gets_wrapped():
    el = {"type": "text", "startTime": 5.5}
    out = _maybe_wrap_with_timeline("<div>x</div>", el)
    assert 'class="sp-element-timed"' in out
    assert 'data-start-time="5.5"' in out
    assert "data-end-time" not in out


def test_element_with_endtime_only_gets_wrapped():
    el = {"type": "text", "endTime": 10.0}
    out = _maybe_wrap_with_timeline("<div>x</div>", el)
    assert 'class="sp-element-timed"' in out
    assert 'data-end-time="10.0"' in out


def test_element_with_zero_starttime_NOT_wrapped():
    el = {"type": "text", "startTime": 0, "endTime": 0}
    out = _maybe_wrap_with_timeline("<div>x</div>", el)
    assert "sp-element-timed" not in out


def test_element_with_invalid_starttime_NOT_wrapped():
    el = {"type": "text", "startTime": "garbage"}
    out = _maybe_wrap_with_timeline("<div>x</div>", el)
    assert "sp-element-timed" not in out


def test_section_with_timeline_gets_synthetic_gate():
    """When ANY element in a section has startTime>0, the export must inject
    a `.sp-timeline-gate` interactive that the JS will auto-complete after
    the timeline finishes — gating progression."""
    project = {
        "id": "p1", "name": "Test",
        "course": {"slides": [
            {"id": "s1", "title": "Tem timeline", "elements": [
                {"type": "text", "content": "Aparece em 5s", "startTime": 5},
                {"type": "image", "src": "/x.png", "startTime": 10, "endTime": 15},
            ]},
            {"id": "s2", "title": "Sem timeline", "elements": [
                {"type": "text", "content": "Estatica"},
            ]},
        ]},
    }
    html = generate_single_page_html(project, "/tmp", "")
    # Section 0 has timeline gate, section 1 does not
    section_0 = html.split('data-index="0"')[1].split('data-index="1"')[0]
    section_1 = html.split('data-index="1"')[1].split('data-index="2"')[0] if 'data-index="2"' in html else html.split('data-index="1"')[1]
    assert "sp-timeline-gate" in section_0
    assert 'data-required="true"' in section_0
    # Section duration is the max(start, end) of all elements (15.0 in this case)
    assert 'data-section-duration="15.0"' in section_0
    # Section 1 (no timeline) should NOT have a gate
    assert "sp-timeline-gate" not in section_1


def test_timeline_engine_present_in_js_runtime():
    """The JS runtime always ships the `startSectionTimeline` engine (so the
    timeline plays for any course that has timed elements). Engine uses
    IntersectionObserver to detect viewport entry."""
    project = {
        "id": "p1", "name": "Test",
        "course": {"slides": [{"id": "s1", "title": "x", "elements": []}]},
    }
    html = generate_single_page_html(project, "/tmp", "")
    # Engine functions present
    assert "function startSectionTimeline" in html
    assert "function observeTimelines" in html
    assert "IntersectionObserver" in html
    # Reveals at startTime
    assert "el.classList.add('sp-revealed')" in html
    # Hides at endTime
    assert "el.classList.add('sp-hidden')" in html
    # Auto-completes the gate after timeline ends
    assert "SP.markClicked(gate)" in html


def test_unlock_triggers_timeline_kickoff():
    """When a section is unlocked AND it contains a timeline gate, the JS
    should kickoff the timeline (in case IntersectionObserver already fired)."""
    project = {
        "id": "p1", "name": "Test",
        "course": {"slides": [{"id": "s1", "title": "x", "elements": []}]},
    }
    html = generate_single_page_html(project, "/tmp", "")
    # In unlockSection, we re-trigger when section has timeline-gate
    assert "sec.querySelector('.sp-timeline-gate')" in html
    assert "startSectionTimeline(sec)" in html


def test_timeline_gate_css_present():
    """Gate must have visible progress bar + transition CSS for fade in/out."""
    project = {
        "id": "p1", "name": "Test",
        "course": {"slides": [{"id": "s1", "title": "x", "elements": []}]},
    }
    html = generate_single_page_html(project, "/tmp", "")
    assert ".sp-element-timed" in html
    assert ".sp-element-timed.sp-revealed" in html
    assert ".sp-element-timed.sp-hidden" in html
    assert ".sp-timeline-progress-bar" in html
