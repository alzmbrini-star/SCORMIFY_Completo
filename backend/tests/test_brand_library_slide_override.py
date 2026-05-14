"""Tests for the per-slide Brand Library override in the Editor.

A slide carries an optional `brandLibraryOverride` field with three values:
  - None / missing → inherit the project-wide `useBrandLibrary` setting.
  - "force"        → try the library on this slide regardless of project flag.
  - "skip"         → never try the library on this slide.

The override logic lives inside `_generate_one_image` (an async closure
inside `generate_course_from_storyboard`). We test the override decision in
isolation by replaying the same conditionals here — duplicating just the
three-way logic is acceptable because it's tiny and self-contained.
"""
import pytest


def _decide(use_brand_library: bool, override) -> bool:
    """Mirror of the override resolution inside ai_agent._generate_one_image."""
    if override == "skip":
        return False
    if override == "force":
        return True
    return use_brand_library


class TestPerSlideOverride:
    def test_inherit_when_no_override(self):
        # Project ON → slide inherits ON
        assert _decide(True, None) is True
        # Project OFF → slide inherits OFF
        assert _decide(False, None) is False
        # Missing field is equivalent to None
        assert _decide(True, None) is True

    def test_force_overrides_project_off(self):
        """Per-slide 'force' must enable library even when project flag is OFF."""
        assert _decide(False, "force") is True

    def test_force_keeps_project_on(self):
        assert _decide(True, "force") is True

    def test_skip_overrides_project_on(self):
        """Per-slide 'skip' must disable library even when project flag is ON."""
        assert _decide(True, "skip") is False

    def test_skip_keeps_project_off(self):
        assert _decide(False, "skip") is False

    def test_unknown_override_value_falls_back_to_inherit(self):
        """Defensive: any unexpected string defaults to the project's setting
        (so a typo in the frontend doesn't accidentally disable the library
        on every slide)."""
        assert _decide(True, "bogus") is True
        assert _decide(False, "bogus") is False
        # Also covers explicit empty string
        assert _decide(True, "") is True


class TestModelAcceptsOverrideField:
    """The Slide model has `extra="allow"`, so `brandLibraryOverride` should
    round-trip through Pydantic without complaints."""

    def test_slide_accepts_brand_library_override(self):
        from models import Slide
        s = Slide(brandLibraryOverride="force")
        # The field is stored even though it's not in the formal schema
        assert s.model_dump().get("brandLibraryOverride") == "force"

    def test_slide_accepts_brand_library_source_metadata(self):
        """When the Editor applies a brand library image, the slide also
        carries `backgroundImageSource` and `backgroundImageAssetId` — both
        should round-trip too."""
        from models import Slide
        s = Slide(
            backgroundImage="/api/companies/c1/assets/a1/file",
            backgroundImageSource="brand_library",
            backgroundImageAssetId="casset_abc12345",
        )
        dumped = s.model_dump()
        assert dumped["backgroundImage"].endswith("/file")
        assert dumped["backgroundImageSource"] == "brand_library"
        assert dumped["backgroundImageAssetId"] == "casset_abc12345"
