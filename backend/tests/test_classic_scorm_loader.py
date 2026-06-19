"""Regression test: the classic (non-single-page) SCORM exporter must
also ship the branded loading overlay.

This was a gap in the original implementation — the user reported
exporting from preview and not seeing the loader, because the
classic exporter uses a separate `player_template.html` that wasn't
updated. The fix injected `__LOADER_*__` placeholders into the
template and made `export_scorm_package` resolve the brand kit.
"""
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models import Project  # noqa: E402
from services.scorm_exporter import export_scorm_package  # noqa: E402


def _project_with_branding(primary="#dc2626", loader_title=None, loader_color=None):
    course = {
        "metadata": {"title": "Acme Trainings", "language": "pt-BR"},
        "slides": [{
            "id": "s1", "title": "Intro", "order": 0,
            "width": 1280, "height": 720, "background": "#fff",
            "elements": [], "annotations": [],
        }],
    }
    brand_kit = {"primaryColor": primary}
    if loader_title:
        brand_kit["loaderTitle"] = loader_title
    if loader_color:
        brand_kit["loaderColor"] = loader_color
    return {
        "id": "p-classic-1",
        "name": "Acme Trainings",
        "ownerId": "u1",
        "course": course,
        "brandKit": brand_kit,
    }


def _export_and_read_index(project_dict):
    """Run the classic SCORM exporter and return the bundled index.html
    as a decoded string."""
    project = Project(**project_dict)
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = export_scorm_package(
            project=project,
            storage_dir=tmp,
            output_dir=tmp,
            backend_url="",
        )
        with zipfile.ZipFile(zip_path) as z:
            assert "index.html" in z.namelist()
            return z.read("index.html").decode("utf-8")


def test_classic_scorm_emits_loader_overlay():
    html = _export_and_read_index(_project_with_branding())
    assert 'id="scormify-loader"' in html
    assert 'data-testid="scorm-initial-loader"' in html
    # Placeholders must have been replaced.
    assert "__LOADER_PRIMARY__" not in html
    assert "__LOADER_ACCENT__" not in html
    assert "__LOADER_TITLE__" not in html


def test_classic_scorm_picks_up_brand_primary_color():
    html = _export_and_read_index(_project_with_branding(primary="#16a34a"))
    # Brand color must appear in the loader CSS (border + gradient).
    assert html.count("#16a34a") >= 2


def test_classic_scorm_honors_brand_loader_title_override():
    html = _export_and_read_index(
        _project_with_branding(
            loader_title="Carregando treinamento corporativo…",
        )
    )
    assert "Carregando treinamento corporativo" in html


def test_classic_scorm_falls_back_to_course_title_when_no_loader_title():
    html = _export_and_read_index(_project_with_branding())
    assert "Acme Trainings" in html  # course title appears in the loader message


def test_classic_scorm_loader_color_overrides_primary_color():
    """When the brand kit has both `primaryColor` and `loaderColor`,
    the loader uses `loaderColor` (the more specific knob)."""
    html = _export_and_read_index(
        _project_with_branding(
            primary="#dc2626",
            loader_color="#0ea5e9",
        )
    )
    # Loader's border-top + gradient should reference 0ea5e9
    assert html.count("#0ea5e9") >= 2
