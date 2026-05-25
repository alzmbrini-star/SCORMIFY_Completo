"""Tests for `backgroundImageFit` plumbing on Modo Fiel slides (2026-05-25).

PDF Faithful Mode renders the PDF page AS the slide background. When the
PDF's aspect ratio differs from the slide canvas (1280x546 ≈ 2.34:1 vs
Letter ≈ 2.59:1), `object-fit:cover` crops the top/sides — exactly the
bug the user reported in SCORM exports. The fix sets
`backgroundImageFit:"contain"` on every faithful slide so the WHOLE page
is visible (letter-boxed if necessary).
"""
from services.pdf_extractor import build_faithful_slides


def _fake_pages(n=2):
    return [
        {"page_num": i + 1, "filename": f"page_{i+1}.jpg",
         "text": "linha de teste"}
        for i in range(n)
    ]


class TestFaithfulSlideBgFit:
    def test_every_slide_has_backgroundImageFit_contain(self):
        slides = build_faithful_slides(_fake_pages(3), "proj_x")
        assert len(slides) == 3
        for s in slides:
            assert s.get("backgroundImageFit") == "contain"

    def test_pdfFaithful_marker_kept(self):
        slides = build_faithful_slides(_fake_pages(1), "proj_x")
        assert slides[0].get("_pdfFaithful") is True

    def test_backgroundImage_url_format(self):
        slides = build_faithful_slides(_fake_pages(1), "proj_x")
        url = slides[0]["backgroundImage"]
        assert url.startswith("/api/projects/proj_x/assets/")
        assert url.endswith(".jpg")
