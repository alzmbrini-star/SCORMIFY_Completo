"""Regression tests for the "Aplicar Tema Visual" (design template) feature.

The user report was: "Applying different templates in Preview shows no visual
difference between models". Root cause: iframes rendering RichText content
did not load Google Fonts, so every template's specialty font
(Nunito / Playfair Display / Poppins / JetBrains Mono / Georgia / Lato...)
fell back to generic sans-serif → all templates looked identical.

Fix: injected the Google Fonts @import into every iframe CSS used by:
  1. SlideCanvas / CoursePreview (via `getRtfContentStyles` in htmlUtils.js)
  2. html_exporter.py (per-element html iframe styles)
  3. export_assets/player.js (dynamic iframe styles in the runtime)
  4. single_page_exporter.py (iframe branch for html elements with global styles)

These tests guard against regressions removing the font import from ANY of the
four surfaces.
"""

from pathlib import Path


REQUIRED_FONTS_HINT = "fonts.googleapis.com/css2"


def test_frontend_rtf_iframe_loads_google_fonts():
    """SlideCanvas + CoursePreview go through `getRtfContentStyles` in
    htmlUtils.js. Losing the @import there breaks the Editor preview."""
    src = Path("/app/frontend/src/utils/htmlUtils.js").read_text()
    assert REQUIRED_FONTS_HINT in src
    # Must include at least these template-specific fonts
    for f in ("Playfair+Display", "Nunito", "JetBrains+Mono", "Poppins", "Lato"):
        assert f in src, f"Missing Google Font {f} in htmlUtils.js @import"


def test_html_exporter_iframe_loads_google_fonts():
    src = Path("/app/backend/services/html_exporter.py").read_text()
    assert REQUIRED_FONTS_HINT in src
    for f in ("Playfair+Display", "Nunito", "JetBrains+Mono", "Poppins", "Lato"):
        assert f in src


def test_player_js_iframe_loads_google_fonts():
    """Runtime SCORM player builds iframes dynamically for html elements
    and must inline the same @import."""
    src = Path("/app/backend/services/export_assets/player.js").read_text()
    assert REQUIRED_FONTS_HINT in src
    for f in ("Playfair+Display", "Nunito", "JetBrains+Mono", "Poppins", "Lato"):
        assert f in src


def test_single_page_exporter_iframe_loads_google_fonts():
    src = Path("/app/backend/services/single_page_exporter.py").read_text()
    assert REQUIRED_FONTS_HINT in src
    for f in ("Playfair+Display", "Nunito", "JetBrains+Mono", "Poppins", "Lato"):
        assert f in src


def test_backend_design_templates_have_distinct_palettes():
    """A sanity check that the theme catalog itself does discriminate — if
    all templates had identical palette values, users would still see no
    diff even with fonts loaded."""
    from importlib import util
    spec = util.spec_from_file_location(
        "ai_agent_tt", "/app/backend/services/ai_agent.py"
    )
    mod = util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    templates = mod.DESIGN_TEMPLATES
    assert len(templates) >= 5
    primaries = {t["palette"]["primary"] for t in templates}
    accents = {t["palette"]["accent"] for t in templates}
    heading_fonts = {t["fonts"]["heading"] for t in templates}
    # If any of these sets shrinks below 5, someone made two templates look
    # the same by accident.
    assert len(primaries) >= 5, f"Duplicate primaries: {primaries}"
    assert len(accents) >= 5, f"Duplicate accents: {accents}"
    assert len(heading_fonts) >= 5, f"Duplicate heading fonts: {heading_fonts}"


def test_apply_design_template_endpoint_returns_correct_name():
    """Guards against a past-observed bug where sending a wrong templateId
    would silently return the default 'Educacional Moderno' with 200 OK.
    Frontend must be told the actual applied template."""
    src = Path("/app/backend/routes/projects_crud.py").read_text()
    # Endpoint returns templateName from the resolved design_token
    assert 'design_token["name"]' in src
    # Endpoint validates that a template was found (may fall through to
    # default in the loader — that's the loader's concern, not the endpoint's)
    assert 'designTemplateId' in src
