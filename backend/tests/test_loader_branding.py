"""Tests for the branded loader customization (2026-02 follow-up).

Verifies that:
  - When a brand kit is set, the loader spinner / progress-bar colors
    reflect the brand's `primaryColor`.
  - When a per-course `loader.title` / `loader.color` is set, it
    overrides the brand kit.
  - The course title is interpolated into the default message
    ("Carregando: <title>…") when no explicit message is given.
  - Malformed colors are silently ignored — never break the export.
  - HTML escaping is applied to the title (no XSS via course name).
"""
import asyncio
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.html_exporter import generate_standalone_html  # noqa: E402
from services.loader_config import (  # noqa: E402
    DEFAULT_PRIMARY,
    DEFAULT_TITLE,
    resolve_loader_config,
)


def _html(project):
    return asyncio.run(generate_standalone_html(
        project=project,
        assets_dir="/tmp",
        base_url="",
        questions=None,
        backend_url="",
        tutor_config=None,
    ))


def _base(title="Curso Teste"):
    return {
        "id": "p1", "name": title, "enableVlibras": False,
        "course": {
            "metadata": {"title": title},
            "slides": [{
                "id": "s1", "title": "S", "width": 1280, "height": 720,
                "background": "#fff", "duration": 5,
                "elements": [], "annotations": [],
            }],
        },
    }


def test_resolve_uses_brand_kit_when_no_override():
    proj = _base("Acme Trainings")
    proj["brandKit"] = {"primaryColor": "#ff8800"}
    cfg = resolve_loader_config(proj)
    assert cfg["primary"] == "#ff8800"
    assert "Acme Trainings" in cfg["title_html"]


def test_resolve_per_course_override_wins_over_brand_kit():
    proj = _base("Anything")
    proj["brandKit"] = {"primaryColor": "#ff8800"}
    proj["course"]["loader"] = {
        "title": "Carregando treinamento exclusivo…",
        "color": "#00ddaa",
        "accentColor": "#aaffee",
    }
    cfg = resolve_loader_config(proj)
    assert cfg["primary"] == "#00ddaa"
    assert cfg["accent"] == "#aaffee"
    assert "exclusivo" in cfg["title_html"]


def test_resolve_invalid_color_falls_back_silently():
    proj = _base("X")
    proj["brandKit"] = {"primaryColor": "not-a-color"}
    proj["course"]["loader"] = {"color": "rgb(255, 0, 0)"}
    cfg = resolve_loader_config(proj)
    assert cfg["primary"] == DEFAULT_PRIMARY


def test_resolve_empty_project_returns_defaults():
    cfg = resolve_loader_config(None)
    assert cfg["title_html"] == DEFAULT_TITLE
    assert cfg["primary"] == DEFAULT_PRIMARY


def test_resolve_html_escapes_course_title():
    proj = _base('Curso <script>alert(1)</script> "perigoso"')
    cfg = resolve_loader_config(proj)
    assert "<script>" not in cfg["title_html"]
    assert "&lt;script&gt;" in cfg["title_html"] or "&quot;" in cfg["title_html"]


def test_resolve_caps_extremely_long_title():
    long = "A" * 300
    proj = _base(long)
    cfg = resolve_loader_config(proj)
    # Plain (un-escaped) length should be <= 80 chars after the
    # "Carregando: " prefix is applied + cap.
    import html
    decoded = html.unescape(cfg["title_html"])
    assert len(decoded) <= 80


def test_standalone_html_contains_brand_color():
    proj = _base("Brand Test")
    proj["brandKit"] = {"primaryColor": "#dc2626"}
    html = _html(proj)
    # The brand color should appear in the loader CSS at least twice
    # (border-top-color + gradient stop).
    assert html.count("#dc2626") >= 2


def test_standalone_html_contains_course_title_in_loader():
    proj = _base("Treinamento Avançado de IA")
    html = _html(proj)
    # The course title should appear in the loader message.
    assert "Treinamento Avançado de IA" in html


def test_scorm_zip_contains_brand_color():
    """Branded loader must survive the SCORM packaging."""
    import tempfile
    from services.scorm_single_page_exporter import export_single_page_scorm_package

    proj = _base("Empresa X")
    proj["brandKit"] = {"primaryColor": "#16a34a"}
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = export_single_page_scorm_package(
            project_doc=proj,
            storage_dir=tmp,
            output_dir=tmp,
            backend_url="",
        )
        with zipfile.ZipFile(zip_path) as z, z.open("index.html") as f:
            content = f.read().decode("utf-8")
    assert "#16a34a" in content
    assert "Empresa X" in content
