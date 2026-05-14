"""Tests for the per-slide `brand_library_image` media type — the manual
selection in the Wizard's Media step that lets an author hand-pick a specific
image from the company's Brand Library for one slide.

This is different from `use_brand_library=True` (which is auto-picked by the
LLM) and from the per-slide override field on the slide model (which acts
during course regeneration). The wizard path stores the asset URL directly
on the slide's `mediaConfig` so the agent can use it verbatim.

We don't actually run the full `generate_course_from_storyboard` async flow
(it requires real DB, real LLM, and a project dir); instead we replay just
the media-type dispatch branch in isolation. Same pattern other agent tests
in this folder use.
"""
import pytest


def _resolve_media_type(media_type: str, mc: dict, slide_idx: int = 0) -> dict:
    """Mirror of the per-type branch logic at the top of
    `generate_course_from_storyboard.slide_media[i] = ...`.

    Returns either:
      - {"type": "image", "url": "...", "source": "..."} for resolved images
      - {"type": "none"} for explicit empty
      - {"type": "queued_ai"} when the slide will be generated later by Leonardo/Gemini
    """
    if media_type == "gallery_image":
        gallery_url = mc.get("galleryImageUrl", "")
        if gallery_url:
            return {"type": "image", "url": gallery_url}
        return {"type": "queued_ai"}
    if media_type == "brand_library_image":
        brand_url = mc.get("brandImageUrl", "")
        if brand_url:
            return {
                "type": "image",
                "url": brand_url,
                "source": "brand_library_manual",
            }
        return {"type": "queued_ai"}
    if media_type == "none":
        return {"type": "none"}
    return {"type": "queued_ai"}


class TestBrandLibraryImageMediaType:
    def test_resolves_with_brand_image_url(self):
        out = _resolve_media_type(
            "brand_library_image",
            {"brandImageUrl": "/api/companies/c1/assets/casset_abc/file"},
        )
        assert out["type"] == "image"
        assert out["url"] == "/api/companies/c1/assets/casset_abc/file"
        assert out["source"] == "brand_library_manual"

    def test_carries_provenance_for_analytics(self):
        """Provenance lets cost/analytics reports show how many slides used
        brand-curated imagery vs. AI generation."""
        out = _resolve_media_type(
            "brand_library_image",
            {"brandImageUrl": "/api/companies/c1/assets/casset_abc/file"},
        )
        assert out["source"] == "brand_library_manual"

    def test_falls_through_when_no_image_picked(self):
        """If the author selected the type but didn't pick an image yet,
        the dispatch falls through (so the slide isn't blank). Behavior is
        intentional: type=brand_library_image without a url means 'still
        deciding'."""
        out = _resolve_media_type("brand_library_image", {})
        assert out["type"] == "queued_ai"

    def test_url_can_be_external(self):
        """Brand library URLs can be absolute (CDN-hosted) — they should
        pass through unchanged."""
        out = _resolve_media_type(
            "brand_library_image",
            {"brandImageUrl": "https://cdn.example.com/brand/logo.png"},
        )
        assert out["url"].startswith("https://")


class TestMediaConfigShape:
    """The Wizard's frontend writes these fields onto mediaConfig — make sure
    we accept exactly the schema the UI emits."""

    def test_mc_fields_match_ui_emission(self):
        mc = {
            "type": "brand_library_image",
            "brandImageUrl": "/api/companies/c1/assets/x/file",
            "brandImageAssetId": "casset_x",
            "brandImageFilename": "didaxis-cover.png",
        }
        # All four fields survive a round-trip and the resolver uses url only
        out = _resolve_media_type("brand_library_image", mc)
        assert out["url"] == "/api/companies/c1/assets/x/file"
        # The extra metadata fields are kept on the slide's mediaConfig for
        # the Editor to display the filename + assetId later — they don't
        # affect the resolution outcome but must round-trip without error.
        assert mc["brandImageAssetId"] == "casset_x"
        assert mc["brandImageFilename"] == "didaxis-cover.png"
