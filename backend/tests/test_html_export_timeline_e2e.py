"""End-to-end test: generate HTML, open in a real browser, and check
the timeline actually fires (elements appear at startTime, hide at endTime).

Run only when Playwright is available; otherwise skip cleanly so the
suite stays portable.
"""
import asyncio
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

playwright = pytest.importorskip("playwright.async_api")

from services.html_exporter import generate_standalone_html  # noqa: E402


def _course_with_timeline():
    return {
        "id": "p1", "name": "Timeline E2E", "enableVlibras": False,
        "course": {
            "metadata": {"title": "Timeline E2E"},
            "slides": [{
                "id": "s1", "title": "S", "width": 1280, "height": 720,
                "background": "#ffffff", "duration": 10,
                "elements": [
                    # Visible from t=0
                    {"id": "e0", "type": "text", "content": "ALWAYS",
                     "x": 100, "y": 100, "width": 400, "height": 60,
                     "style": {"fontSize": 32, "fontColor": "#000"}},
                    # Appears at t=1.5
                    {"id": "e1", "type": "text", "content": "DELAYED",
                     "x": 100, "y": 250, "width": 400, "height": 60,
                     "startTime": 1.5,
                     "style": {"fontSize": 32, "fontColor": "#000"}},
                    # Hides at t=1
                    {"id": "e2", "type": "text", "content": "EARLY",
                     "x": 100, "y": 400, "width": 400, "height": 60,
                     "endTime": 1,
                     "style": {"fontSize": 32, "fontColor": "#000"}},
                ],
                "annotations": [],
            }],
        },
    }


async def _run():
    html = await generate_standalone_html(
        project=_course_with_timeline(),
        assets_dir="/tmp",
        base_url="",
        questions=None,
        backend_url="",
        tutor_config=None,
    )
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False,
                                     mode="w", encoding="utf-8") as f:
        f.write(html)
        path = f.name

    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        try:
            await page.goto(f"file://{path}")
            # Wait for the first slide to render.
            await page.wait_for_selector("#element-0", timeout=5000)

            # ── t = 0.2 s: ALWAYS visible, DELAYED hidden, EARLY visible
            await page.wait_for_timeout(200)
            states = await page.evaluate("""
                () => ({
                  always: window.getComputedStyle(document.getElementById('element-0')).visibility,
                  delayed_vis: window.getComputedStyle(document.getElementById('element-1')).visibility,
                  delayed_op: parseFloat(window.getComputedStyle(document.getElementById('element-1')).opacity),
                  early: window.getComputedStyle(document.getElementById('element-2')).visibility,
                })
            """)
            assert states["always"] == "visible"
            # DELAYED (startTime=1.5) must still be hidden at t=0.2.
            assert states["delayed_vis"] == "hidden" or states["delayed_op"] == 0, states
            assert states["early"] == "visible", states

            # ── t = 1.3 s: EARLY (endTime=1) must be gone (display:none).
            await page.wait_for_timeout(1300)
            after_early = await page.evaluate("""
                () => ({
                  early: window.getComputedStyle(document.getElementById('element-2')).display,
                })
            """)
            assert after_early["early"] == "none", after_early

            # ── t = 2.0 s: DELAYED (startTime=1.5) must now be visible.
            await page.wait_for_timeout(700)
            after_delayed = await page.evaluate("""
                () => ({
                  delayed_vis: window.getComputedStyle(document.getElementById('element-1')).visibility,
                  delayed_op: parseFloat(window.getComputedStyle(document.getElementById('element-1')).opacity),
                })
            """)
            assert after_delayed["delayed_vis"] == "visible", after_delayed
            assert after_delayed["delayed_op"] > 0.8, after_delayed
        finally:
            await browser.close()
            os.unlink(path)


def test_e2e_timeline_in_real_browser():
    asyncio.run(_run())
