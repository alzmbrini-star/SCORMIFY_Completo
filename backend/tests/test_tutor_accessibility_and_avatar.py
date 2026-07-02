"""Ensures the Tutor IA widget carries accessibility controls (A+/A-,
contrast) and honors a custom avatar image passed through tutorConfig.

The widget is Vanilla JS embedded into exported courses, so we validate
the static assets themselves.
"""

from pathlib import Path


JS_PATH = Path("/app/backend/services/export_assets/tutor.js")
CSS_PATH = Path("/app/backend/services/export_assets/tutor.css")


def test_widget_exposes_accessibility_functions():
    js = JS_PATH.read_text()
    # Public API must include the new toggles used by the a11y bar buttons
    assert "changeFontSize: changeFontSize" in js
    assert "setContrast: setContrast" in js
    # Bar must be rendered in the header
    assert "tutor-a11y-bar" in js
    assert "tutor-a11y-contrast" in js
    # Persisted preferences
    assert "tutor-a11y-font" in js
    assert "tutor-a11y-contrast" in js


def test_widget_supports_custom_avatar():
    js = JS_PATH.read_text()
    # config.avatarUrl must be read when building the header
    assert "config.avatarUrl" in js
    # And produce an <img> tag when set
    assert 'alt="' in js  # avatar img has alt
    css = CSS_PATH.read_text()
    # Avatar container must clip images cleanly (rounded, cover)
    assert ".tutor-avatar img" in css
    assert "object-fit: cover" in css


def test_contrast_and_font_theme_classes_exist():
    css = CSS_PATH.read_text()
    for cls in [
        ".tutor-panel.tutor-contrast-light",
        ".tutor-panel.tutor-contrast-high",
        ".tutor-panel.tutor-font-large",
        ".tutor-panel.tutor-font-xlarge",
        ".tutor-panel.tutor-font-small",
    ]:
        assert cls in css, f"Missing theme class {cls}"


def test_avatar_url_propagates_through_exporters():
    scorm_src = Path("/app/backend/services/scorm_exporter.py").read_text()
    assert "'avatarUrl'" in scorm_src, "SCORM exporter must forward avatarUrl into tutorConfig"

    export_route = Path("/app/backend/routes/export.py").read_text()
    # Both tutor_settings blocks (HTML export path & Modo Fiel path) must
    # read avatarUrl from the admin settings document.
    assert export_route.count("'avatarUrl': settings_doc.get('avatarUrl'") >= 2


def test_admin_default_settings_include_avatar_url():
    src = Path("/app/backend/routes/admin.py").read_text()
    assert '"avatarUrl"' in src
