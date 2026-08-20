"""Regression coverage for Editor/Agent visual-theme parity."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_editor_theme_uses_previous_agent_tokens():
    source = (ROOT / "backend/routes/projects_crud.py").read_text(encoding="utf-8")
    assert 'previous_design_template_id = project.get("designTemplateId")' in source
    assert "previous_design_token=previous_design_token" in source


def test_theme_application_matches_agent_background_rules():
    source = (ROOT / "backend/routes/agent.py").read_text(encoding="utf-8")
    assert 'palette.get("coverBg", primary) if is_cover_slide else content_bg' in source
    assert "semantic_color_map" in source
    assert "_translate_agent_tokens" in source
    assert "scenario" in source


def test_editor_marks_the_current_agent_theme():
    dialog = (ROOT / "frontend/src/pages/Editor/dialogs/MediaDialogs.jsx").read_text(encoding="utf-8")
    editor = (ROOT / "frontend/src/pages/Editor.jsx").read_text(encoding="utf-8")
    assert "selectedDesignTemplateId === dt.id" in dialog
    assert "selectedDesignTemplateId={currentProject?.designTemplateId || ''}" in editor
