import pytest

from routes.projects_media import _pdf_page_render_scale


def test_pdf_pages_default_to_high_resolution(monkeypatch):
    monkeypatch.delenv("PDF_PAGE_RENDER_DPI", raising=False)
    monkeypatch.delenv("PDF_PAGE_MAX_DIMENSION", raising=False)
    scale = _pdf_page_render_scale(595, 842)
    assert scale == pytest.approx(240 / 72)
    assert 2800 <= round(842 * scale) <= 2810


def test_pdf_page_render_respects_memory_dimension_cap(monkeypatch):
    monkeypatch.setenv("PDF_PAGE_RENDER_DPI", "360")
    monkeypatch.setenv("PDF_PAGE_MAX_DIMENSION", "3200")
    scale = _pdf_page_render_scale(1000, 2000)
    assert scale == pytest.approx(1.6)
    assert round(2000 * scale) == 3200


def test_pdf_page_render_rejects_unreasonable_env_values(monkeypatch):
    monkeypatch.setenv("PDF_PAGE_RENDER_DPI", "9999")
    monkeypatch.setenv("PDF_PAGE_MAX_DIMENSION", "99999")
    scale = _pdf_page_render_scale(612, 792)
    assert scale <= 5000 / 792
