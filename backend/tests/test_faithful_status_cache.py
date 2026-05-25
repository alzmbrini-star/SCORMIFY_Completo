"""Tests for the in-memory faithful-status cache (2026-05-21).

Production HTTP 520 mitigation: when PyMuPDF/Tesseract hold the GIL in
the worker thread, the polling endpoint MUST still answer fast. We achieve
that with a module-level dict updated by the worker thread.
"""
from routes import pdf_import


def setup_function(_fn):
    """Reset cache between tests."""
    pdf_import._FAITHFUL_STATUS_CACHE.clear()
    pdf_import._FAITHFUL_STATUS_ORDER.clear()


class TestFaithfulStatusCache:
    def test_set_and_read(self):
        pdf_import._faithful_set_cache("p1", {"status": "processing", "progress": 42, "message": "..."})
        assert pdf_import._FAITHFUL_STATUS_CACHE["p1"]["progress"] == 42

    def test_overwrite_keeps_one_entry(self):
        pdf_import._faithful_set_cache("p1", {"status": "processing", "progress": 10})
        pdf_import._faithful_set_cache("p1", {"status": "processing", "progress": 50})
        assert pdf_import._FAITHFUL_STATUS_CACHE["p1"]["progress"] == 50
        assert pdf_import._FAITHFUL_STATUS_ORDER.count("p1") == 1

    def test_empty_project_id_ignored(self):
        pdf_import._faithful_set_cache("", {"status": "x"})
        assert "" not in pdf_import._FAITHFUL_STATUS_CACHE

    def test_non_dict_status_ignored(self):
        pdf_import._faithful_set_cache("p2", "not a dict")
        assert "p2" not in pdf_import._FAITHFUL_STATUS_CACHE

    def test_fifo_eviction_at_cap(self):
        # Use a tight cap for this test by monkeypatching the constant.
        orig_max = pdf_import._FAITHFUL_STATUS_MAX
        pdf_import._FAITHFUL_STATUS_MAX = 3
        try:
            for i in range(5):
                pdf_import._faithful_set_cache(f"p{i}", {"status": "processing"})
            # Only the last 3 should remain (oldest p0, p1 evicted)
            assert "p0" not in pdf_import._FAITHFUL_STATUS_CACHE
            assert "p1" not in pdf_import._FAITHFUL_STATUS_CACHE
            assert "p2" in pdf_import._FAITHFUL_STATUS_CACHE
            assert "p3" in pdf_import._FAITHFUL_STATUS_CACHE
            assert "p4" in pdf_import._FAITHFUL_STATUS_CACHE
            assert len(pdf_import._FAITHFUL_STATUS_CACHE) == 3
        finally:
            pdf_import._FAITHFUL_STATUS_MAX = orig_max

    def test_done_status_replaces_processing(self):
        pdf_import._faithful_set_cache("p1", {"status": "processing", "progress": 50})
        pdf_import._faithful_set_cache("p1", {"status": "done", "progress": 100})
        c = pdf_import._FAITHFUL_STATUS_CACHE["p1"]
        assert c["status"] == "done"
        assert c["progress"] == 100

    def test_error_status_stored(self):
        pdf_import._faithful_set_cache("p1", {"status": "error", "message": "Falha xyz"})
        assert pdf_import._FAITHFUL_STATUS_CACHE["p1"]["status"] == "error"
