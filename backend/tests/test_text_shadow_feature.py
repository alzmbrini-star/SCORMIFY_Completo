"""Regression tests for the text-shadow feature.

Guards three levels of shadow application (per-element / per-slide / per-course)
and ensures the render layers already carry element-level textShadow through
to the exported courses (SCORM/HTML).
"""

from pathlib import Path


FRONTEND = Path("/app/frontend/src")


def test_text_shadow_controls_exists():
    src = (FRONTEND / "components/editor/TextShadowControls.jsx").read_text()
    # Public API surface
    assert "export default function TextShadowControls" in src
    assert "export function parseShadow" in src
    assert "export function buildShadow" in src
    # Both color and blur controls must be present
    assert 'data-testid="text-shadow-color"' in src
    assert 'data-testid="text-shadow-blur"' in src
    # Explicit disable emits empty string so downstream renderers treat as none
    assert "onChange('');" in src


def test_element_properties_wires_shadow_controls():
    src = (FRONTEND / "pages/Editor/components/ElementProperties.jsx").read_text()
    assert "import TextShadowControls" in src
    assert "TextShadowControls" in src
    # Element-level writes go into style.textShadow via handleStyleChange
    assert "'textShadow'" in src


def test_slide_properties_wires_shadow_with_bulk_apply():
    src = (FRONTEND / "pages/Editor/components/SlideProperties.jsx").read_text()
    assert "TextShadowControls" in src
    assert "textShadowDefault" in src
    # Bulk-apply button + prop must exist
    assert 'onApplyShadowToAllSlides' in src
    assert 'apply-shadow-all-slides' in src
    # Explicit per-element shadows must be preserved when applying slide default
    assert "hasExplicit" in src


def test_editor_passes_apply_shadow_callback():
    src = (FRONTEND / "pages/Editor.jsx").read_text()
    assert "onApplyShadowToAllSlides" in src
    # Iterates every slide
    assert "allSlides.forEach" in src


def test_render_layers_read_element_textshadow():
    """These files already read element.style.textShadow — the feature only
    works if that plumbing stays intact."""
    files = [
        FRONTEND / "components/editor/SlideCanvas.jsx",
        FRONTEND / "components/editor/CoursePreview.jsx",
        FRONTEND / "components/editor/SplitPreview.jsx",
    ]
    for f in files:
        assert "element.style?.textShadow" in f.read_text(), f"{f.name} lost textShadow"


def test_exporter_render_layers_carry_textshadow():
    """Backend renderers (used by scorm/html exports) must inject
    text-shadow CSS when the element has one."""
    html_ex = Path("/app/backend/services/html_exporter.py").read_text()
    assert "text-shadow" in html_ex.lower()
    player = Path("/app/backend/services/export_assets/player.js").read_text()
    assert "textShadow" in player
