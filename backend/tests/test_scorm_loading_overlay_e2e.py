"""E2E: open a generated SCORM index.html in Chromium and verify the
loading overlay (a) appears immediately, (b) becomes hidden once the
DOM finishes settling, (c) doesn't block the page beyond the 15 s
safety net.
"""
import asyncio
import os
import sys
import tempfile
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

playwright = pytest.importorskip("playwright.async_api")

from services.scorm_single_page_exporter import export_single_page_scorm_package  # noqa: E402


def _course():
    return {
        "id": "p1", "name": "E2E Loader",
        "course": {
            "metadata": {"title": "E2E Loader"},
            "slides": [
                {"id": "s1", "title": "S1", "width": 1280, "height": 720,
                 "background": "#fff", "duration": 5, "elements": [], "annotations": []},
                {"id": "s2", "title": "S2", "width": 1280, "height": 720,
                 "background": "#fff", "duration": 5, "elements": [], "annotations": []},
            ],
        },
    }


async def _run():
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = export_single_page_scorm_package(
            project_doc=_course(),
            storage_dir=tmp,
            output_dir=tmp,
            backend_url="",
        )
        # Extract to serve via file://
        extract_dir = Path(tmp) / "extracted"
        extract_dir.mkdir()
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(extract_dir)
        index_path = extract_dir / "index.html"
        assert index_path.exists()

        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            try:
                await page.goto(f"file://{index_path}")
                # ── t≈0: loader must be present and visible.
                loader_exists = await page.locator("#scormify-loader").count()
                assert loader_exists == 1
                visible_state = await page.evaluate("""
                    () => {
                        var el = document.getElementById('scormify-loader');
                        if (!el) return 'missing';
                        var cs = window.getComputedStyle(el);
                        return {opacity: cs.opacity, display: cs.display, hasHidden: el.classList.contains('hidden')};
                    }
                """)
                assert visible_state["display"] != "none"

                # ── t≈2s: course with no images → loader should be
                #    hidden (DOMContentLoaded → track → no assets → hide).
                await page.wait_for_timeout(2500)
                later_state = await page.evaluate("""
                    () => {
                        var el = document.getElementById('scormify-loader');
                        // After hide() the overlay is removed from DOM.
                        return !el || el.classList.contains('hidden');
                    }
                """)
                assert later_state is True, "loader should be hidden by t=2.5s when there are no assets to wait for"
            finally:
                await browser.close()


def test_scorm_loader_appears_and_hides():
    asyncio.run(_run())
