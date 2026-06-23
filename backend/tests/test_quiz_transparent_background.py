"""
Regression: Quiz `transparentBackground` toggle should propagate through all three exporters:
- single_page_exporter (adds CSS class)
- html_exporter (conditional inline JS for start/play/results screens)
- export_assets/player.js + quiz-controller.js (used by SCORM packages)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.single_page_exporter import _render_quiz_element_inner
from services.html_exporter import generate_html_template


def _make_course(transparent: bool):
    return {
        'slides': [{
            'id': 's1', 'duration': 5,
            'elements': [{
                'id': 'q1',
                'type': 'quiz',
                'x': 0, 'y': 0, 'width': 400, 'height': 300,
                'quizConfig': {
                    'title': 'Quiz X',
                    'questionIds': ['qq-1'],
                    'transparentBackground': transparent,
                }
            }]
        }],
        'questions': [],
    }


# ---------- single_page_exporter ----------

def test_sp_quiz_transparent_class_added_when_flag_true():
    el = {'quizConfig': {'title': 'T', 'questionIds': [], 'transparentBackground': True}}
    out = _render_quiz_element_inner(el, 0, 0, {})
    assert 'sp-quiz-transparent' in out
    # Composite class string preserved
    assert 'sp-quiz sp-interactive sp-quiz-transparent' in out


def test_sp_quiz_transparent_class_omitted_when_flag_missing_or_false():
    el_missing = {'quizConfig': {'title': 'T', 'questionIds': []}}
    el_false = {'quizConfig': {'title': 'T', 'questionIds': [], 'transparentBackground': False}}
    for el in (el_missing, el_false):
        out = _render_quiz_element_inner(el, 0, 0, {})
        assert 'sp-quiz-transparent' not in out
        # but the standard quiz classes are still there
        assert 'class="sp-quiz sp-interactive"' in out


# ---------- html_exporter ----------

def test_html_exporter_template_contains_conditional_quiz_branches():
    html = generate_html_template('T', _make_course(True), 960, 540, enable_vlibras=False)
    # start screen branch
    assert 'quizTransparent = elem.quizConfig.transparentBackground === true' in html
    # play screen branch
    assert 'quizTransparent = quiz.config && quiz.config.transparentBackground === true' in html
    # results screen branch (uses quizResultsOuterBg var)
    assert 'quizResultsOuterBg' in html


def test_html_exporter_template_compiles_for_opaque_quiz():
    """The template is generated identically regardless of the flag value;
    flag is evaluated at runtime in the browser. Smoke check that compilation works."""
    html = generate_html_template('T', _make_course(False), 960, 540, enable_vlibras=False)
    assert len(html) > 1000
    assert 'transparentBackground' in html  # the runtime check is baked in


# ---------- export_assets (SCORM) ----------

EXPORT_ASSETS = Path(__file__).resolve().parents[1] / 'services' / 'export_assets'


def test_player_js_has_transparent_quiz_branch():
    src = (EXPORT_ASSETS / 'player.js').read_text(encoding='utf-8')
    assert '_quizTransparent = _quizCfg.transparentBackground === true' in src
    assert "el.style.background = 'transparent'" in src


def test_quiz_controller_js_has_transparent_play_and_results_branches():
    src = (EXPORT_ASSETS / 'quiz-controller.js').read_text(encoding='utf-8')
    # Play screen
    assert 'quizTransparent = quiz.config.transparentBackground === true' in src
    # Results screen
    assert 'quizResultsTransparent = quiz.config.transparentBackground === true' in src


def test_sp_runtime_styles_has_transparent_rules():
    css = (EXPORT_ASSETS.parent / 'sp_runtime' / 'styles.css').read_text(encoding='utf-8')
    assert '.sp-quiz.sp-quiz-transparent' in css
    assert 'background:transparent!important' in css
