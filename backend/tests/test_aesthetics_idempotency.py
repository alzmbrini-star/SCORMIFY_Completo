"""Tests for the IDEMPOTENCY of html_style fix application + deep clean.

The Aesthetic Analyzer was accumulating `<style data-aesthetic-fix>` tags
on every Apply — older universal-selector rules from previous (buggy)
Analyzer versions stayed in the htmlContent and continued breaking
simulators even after the code was fixed.

Now:
- Each apply STRIPS all prior aesthetic-fix tags before injecting new
- The deep-clean endpoint removes ALL of them across the entire project
- The cleaned htmlContent is persisted even if the new fix is empty
"""
import pytest
from routes.aesthetics import (
    _clean_aesthetic_fixes_from_html,
    _apply_html_style_fix,
)


class TestCleanAestheticFixesFromHtml:
    def test_removes_single_tag(self):
        html = '<html><head><style data-aesthetic-fix="1">body * {color:#fff}</style></head><body>x</body></html>'
        out = _clean_aesthetic_fixes_from_html(html)
        assert "data-aesthetic-fix" not in out
        assert "body *" not in out

    def test_removes_multiple_accumulated_tags(self):
        # Real corruption case: 3 apply runs piled tags up
        html = (
            '<html><head>'
            '<style data-aesthetic-fix="1">body * {color:#fff}</style>'
            '<style>.real-css {color:#000}</style>'
            '<style data-aesthetic-fix="1">body p {color:red}</style>'
            '<style data-aesthetic-fix="1">.x {color:blue}</style>'
            '</head><body>x</body></html>'
        )
        out = _clean_aesthetic_fixes_from_html(html)
        assert out.count('data-aesthetic-fix') == 0
        # Real CSS preserved
        assert ".real-css" in out

    def test_no_op_when_no_tag(self):
        html = '<html><head><style>.real {color:red}</style></head><body>x</body></html>'
        out = _clean_aesthetic_fixes_from_html(html)
        assert out == html

    def test_empty_html(self):
        assert _clean_aesthetic_fixes_from_html("") == ""
        assert _clean_aesthetic_fixes_from_html(None) is None

    def test_preserves_simulator_internal_styles(self):
        html = (
            '<html><head>'
            '<style>.option-btn{background:#22d3ee;color:#000;padding:0.5em}</style>'
            '<style data-aesthetic-fix="1">body * {color:#fff !important}</style>'
            '</head><body><button class="option-btn">x</button></body></html>'
        )
        out = _clean_aesthetic_fixes_from_html(html)
        # Simulator's intentional CSS survives
        assert ".option-btn" in out
        assert "#22d3ee" in out
        assert "#000" in out
        # Bad accumulated rule removed
        assert "data-aesthetic-fix" not in out


class TestApplyIdempotency:
    def test_re_applying_does_not_accumulate_tags(self):
        element = {
            "type": "html",
            "htmlContent": "<html><head><style>.x{color:red}</style></head><body>x</body></html>",
        }
        # First apply
        _apply_html_style_fix(
            element,
            css=".x { color: #f8fafc }",
            target_color="#f8fafc",
            preserve_html_typography=True,
        )
        first = element["htmlContent"]
        assert first.count('data-aesthetic-fix') == 1

        # Second apply — should REPLACE not stack
        _apply_html_style_fix(
            element,
            css=".x { color: #0f172a }",
            target_color="#0f172a",
            preserve_html_typography=True,
        )
        second = element["htmlContent"]
        assert second.count('data-aesthetic-fix') == 1, (
            f"Tags accumulated after re-apply: {second.count('data-aesthetic-fix')}"
        )
        # The new color is the one in the html (not the old)
        assert "#0f172a" in second

    def test_apply_with_empty_final_css_still_cleans_old_tags(self):
        """Critical: if the LLM only emits universal rules (which get
        stripped to empty), we must STILL clean previously accumulated
        bad tags. Otherwise the corruption persists forever."""
        element = {
            "type": "html",
            "htmlContent": (
                '<html><head>'
                '<style>.real-class{color:#000}</style>'
                '<style data-aesthetic-fix="1">body * {color:#fff !important}</style>'
                '</head><body>x</body></html>'
            ),
        }
        # Apply with a CSS that gets stripped to nothing in preserve mode
        result = _apply_html_style_fix(
            element,
            css="body * { color: #fff }",  # all universal — will be stripped
            target_color=None,  # no fallback color override
            preserve_html_typography=True,
        )
        assert result is True, "Should report cleanup as a successful apply"
        out = element["htmlContent"]
        assert "data-aesthetic-fix" not in out
        # Real simulator CSS preserved
        assert ".real-class" in out


class TestDeepCleanRegex:
    """The regex must match tags written with single OR double quotes,
    and must not accidentally match similar non-aesthetic-fix tags."""
    def test_double_quoted_attribute(self):
        html = '<style data-aesthetic-fix="1">body{color:red}</style>'
        assert _clean_aesthetic_fixes_from_html(html) == ""

    def test_single_quoted_attribute(self):
        html = "<style data-aesthetic-fix='1'>body{color:red}</style>"
        assert _clean_aesthetic_fixes_from_html(html) == ""

    def test_does_not_match_unrelated_data_attribute(self):
        html = '<style data-something-else="1">body{color:red}</style>'
        out = _clean_aesthetic_fixes_from_html(html)
        # data-something-else should be preserved
        assert out == html
