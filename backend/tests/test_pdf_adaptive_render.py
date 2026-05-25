"""Tests for adaptive PDF rendering parameters (2026-05-25).

Production OOM mitigation: large PDFs render at reduced resolution/quality
to keep peak memory under the pod's ~512Mi limit.
"""
from services.pdf_extractor import (
    _pick_render_params,
    SLIDE_WIDTH, SLIDE_HEIGHT, FAITHFUL_JPEG_QUALITY,
    ADAPTIVE_LARGE_PDF_BYTES, ADAPTIVE_HUGE_PDF_BYTES,
)


class TestPickRenderParams:
    def test_small_pdf_uses_full_quality(self):
        w, h, q = _pick_render_params(5 * 1024 * 1024)
        assert (w, h, q) == (SLIDE_WIDTH, SLIDE_HEIGHT, FAITHFUL_JPEG_QUALITY)

    def test_large_pdf_reduces_quality(self):
        w, h, q = _pick_render_params(15 * 1024 * 1024)
        # Should be smaller than default
        assert w < SLIDE_WIDTH
        assert h < SLIDE_HEIGHT
        assert q < FAITHFUL_JPEG_QUALITY

    def test_huge_pdf_uses_smallest(self):
        w_huge, h_huge, q_huge = _pick_render_params(30 * 1024 * 1024)
        w_large, h_large, q_large = _pick_render_params(15 * 1024 * 1024)
        # Huge should be even smaller than large
        assert w_huge < w_large
        assert h_huge < h_large
        assert q_huge < q_large

    def test_boundary_at_large_threshold(self):
        # At exactly the threshold, still small params
        w1, _, _ = _pick_render_params(ADAPTIVE_LARGE_PDF_BYTES)
        # 1 byte over → large bucket
        w2, _, _ = _pick_render_params(ADAPTIVE_LARGE_PDF_BYTES + 1)
        assert w1 == SLIDE_WIDTH
        assert w2 < SLIDE_WIDTH

    def test_boundary_at_huge_threshold(self):
        w1, _, _ = _pick_render_params(ADAPTIVE_HUGE_PDF_BYTES)
        w2, _, _ = _pick_render_params(ADAPTIVE_HUGE_PDF_BYTES + 1)
        # Just under = large bucket, just over = huge bucket
        assert w1 > w2

    def test_zero_bytes_safe(self):
        w, h, q = _pick_render_params(0)
        assert (w, h, q) == (SLIDE_WIDTH, SLIDE_HEIGHT, FAITHFUL_JPEG_QUALITY)

    def test_peak_pixmap_memory_dropped(self):
        """Sanity: pixmap memory is width*height*3. Huge mode should be
        roughly 60% less than default."""
        w_def, h_def, _ = _pick_render_params(1024)
        w_huge, h_huge, _ = _pick_render_params(30 * 1024 * 1024)
        mem_def = w_def * h_def * 3
        mem_huge = w_huge * h_huge * 3
        # At least 40% memory savings expected
        assert mem_huge < mem_def * 0.6
