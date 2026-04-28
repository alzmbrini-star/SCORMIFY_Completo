"""End-to-end SCORM 1.2 single-page test using a mock LMS in a real browser.

Requires the SCORM zip already extracted to /tmp/scorm_test and a local HTTP
server running on localhost:8765 (started by the test fixture).
"""
import os
import json
import subprocess
import time
import urllib.request
import zipfile
from pathlib import Path

import pytest


SCORM_TEST_DIR = Path("/tmp/scorm_test")
PORT = 8765


@pytest.fixture(scope="module")
def scorm_pkg():
    """Extract the latest single-page SCORM zip into SCORM_TEST_DIR."""
    SCORM_TEST_DIR.mkdir(exist_ok=True)
    exports_dir = Path("/app/backend/storage/exports")
    zips = sorted(exports_dir.glob("*_singlepage_*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    assert zips, "No single-page SCORM zip found — run test_single_page_export first"
    latest = zips[0]
    with zipfile.ZipFile(latest) as z:
        z.extractall(SCORM_TEST_DIR)
    (SCORM_TEST_DIR / "lms.html").write_text(_LMS_HTML, encoding="utf-8")
    return SCORM_TEST_DIR


@pytest.fixture(scope="module")
def http_server(scorm_pkg):
    """Spawn a local http server for the SCORM package."""
    proc = subprocess.Popen(
        ["python", "-m", "http.server", str(PORT)],
        cwd=str(scorm_pkg),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(20):
        try:
            urllib.request.urlopen(f"http://localhost:{PORT}/lms.html", timeout=1)
            break
        except Exception:
            time.sleep(0.2)
    yield f"http://localhost:{PORT}"
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except Exception:
        proc.kill()


def test_scorm_api_js_exposes_required_methods(scorm_pkg):
    api_js = (scorm_pkg / "scripts" / "scorm-api.js").read_text()
    for method in ("init", "setLocation", "saveSuspend", "getSuspend",
                   "recordInteraction", "setScore", "complete", "commit", "finish"):
        assert f"{method}:" in api_js, f"scorm-api.js missing {method}"
    assert "findAPI" in api_js


def test_index_html_has_scorm_mode_true(scorm_pkg):
    idx = (scorm_pkg / "index.html").read_text()
    assert 'src="scripts/scorm-api.js"' in idx
    assert "SCORM_MODE = true" in idx
    assert "scormSaveState" in idx
    assert "scormReportQuiz" in idx
    assert "scormUpdateScore" in idx
    assert "scormMarkComplete" in idx
    assert "scormRestoreState" in idx


def test_imsmanifest_lists_scorm_resources(scorm_pkg):
    manifest = (scorm_pkg / "imsmanifest.xml").read_text()
    assert 'scormtype="sco"' in manifest
    assert 'href="index.html"' in manifest
    assert 'href="scripts/scorm-api.js"' in manifest
    assert "1.2" in manifest
    # Identifier must be NCName-safe (no hyphens for max LMS compatibility)
    import re as _re
    m = _re.search(r'identifier="([^"]+)"', manifest)
    assert m, "Missing identifier"
    assert "-" not in m.group(1), f"Identifier contains hyphens (some LMS reject these): {m.group(1)}"


def test_e2e_lms_initialize_and_lesson_status(http_server):
    """Real browser: load LMS, advance one section, verify cmi.* is set."""
    pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(f"{http_server}/lms.html")
        page.wait_for_load_state("networkidle", timeout=8000)
        page.wait_for_timeout(1500)  # give SCO time to initialize

        # Inspect cmiData inside the LMS frame (top window)
        cmi = page.evaluate("() => window.cmiData")
        assert cmi is not None
        assert cmi.get("cmi.core.lesson_status") == "incomplete", \
            f"Expected lesson_status=incomplete after init, got {cmi.get('cmi.core.lesson_status')}"

        # Inside iframe, drive SP runtime to advance from section 0 to section 1
        frame = page.frame_locator("#sco")
        result = page.evaluate("""() => {
          var sco = document.getElementById('sco');
          var w = sco.contentWindow;
          if (!w.SP || !w.SCORM) return { error: 'SP or SCORM not loaded yet' };
          // Advance from section 0 (which has no required interactives) to section 1
          w.SP.advance();
          return {
            api_initialized: w.SCORM.initialized,
            currentIndex: 1,
          };
        }""")
        assert result.get("api_initialized") is True, f"SCORM not initialized: {result}"

        # Wait for commit
        page.wait_for_timeout(800)

        cmi_after = page.evaluate("() => window.cmiData")
        # lesson_location should now be "1"
        assert cmi_after.get("cmi.core.lesson_location") == "1", \
            f"Expected lesson_location='1', got {cmi_after.get('cmi.core.lesson_location')}"
        # suspend_data should be a non-empty JSON
        sd_raw = cmi_after.get("cmi.suspend_data", "")
        assert sd_raw, "Expected non-empty cmi.suspend_data after advance"
        sd = json.loads(sd_raw)
        assert sd.get("currentIndex") == 1, sd
        assert "1" in [str(k) for k in sd.get("unlocked", {})], f"Unlocked should contain 1: {sd}"

        browser.close()


def test_e2e_resume_after_reload(http_server):
    """Reload the LMS and verify the SCO resumes from cmi.core.lesson_location."""
    pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        # First visit — advance a few sections
        page.goto(f"{http_server}/lms.html")
        page.wait_for_load_state("networkidle", timeout=8000)
        page.wait_for_timeout(1500)
        page.evaluate("""() => {
          var w = document.getElementById('sco').contentWindow;
          if (!w.SP) return;
          w.SP.advance();
          w.SP.advance();
        }""")
        page.wait_for_timeout(1000)
        cmi_before = page.evaluate("() => window.cmiData")
        assert cmi_before.get("cmi.core.lesson_location") == "2"

        # Reload (LMS keeps cmiData in localStorage)
        page.evaluate("() => document.getElementById('sco').src = 'index.html?t=' + Date.now()")
        page.wait_for_timeout(2500)

        # Verify the SP runtime restored state
        restored = page.evaluate("""() => {
          var w = document.getElementById('sco').contentWindow;
          if (!w.SP) return null;
          // Inspect data-locked attributes — sections 0,1,2 should be unlocked
          var unlocked0 = !document.getElementById('sco').contentDocument.querySelector('.sp-section[data-index="0"][data-locked]');
          var unlocked1 = !document.getElementById('sco').contentDocument.querySelector('.sp-section[data-index="1"][data-locked]');
          var unlocked2 = !document.getElementById('sco').contentDocument.querySelector('.sp-section[data-index="2"][data-locked]');
          return { unlocked0: unlocked0, unlocked1: unlocked1, unlocked2: unlocked2 };
        }""")
        assert restored is not None
        assert restored["unlocked0"] is True
        assert restored["unlocked1"] is True
        assert restored["unlocked2"] is True, f"Resume failed to unlock section 2: {restored}"

        browser.close()


def test_e2e_advance_to_end_card_marks_completion(http_server):
    """Drive SP.advance() through ALL sections and assert window.SCORM.complete()
    is called and cmi.core.lesson_status is set to 'passed' or 'completed'.
    Covers: 'advance to end-card calls SCORM.complete(passed)'."""
    pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        # Clear LMS state from prior tests
        page.goto(f"{http_server}/lms.html")
        page.evaluate("() => { try { localStorage.removeItem('cmi'); } catch(e){} }")
        page.goto(f"{http_server}/lms.html")
        page.wait_for_load_state("networkidle", timeout=8000)
        page.wait_for_timeout(1500)

        section_count = page.evaluate("""() => {
          var w = document.getElementById('sco').contentWindow;
          if (!w.SP) return 0;
          var d = document.getElementById('sco').contentDocument;
          return d.querySelectorAll('.sp-section[data-index]').length;
        }""")
        assert section_count and section_count > 0, "No SP sections found in iframe"

        page.evaluate(
            """(n) => {
              var w = document.getElementById('sco').contentWindow;
              for (var i = 0; i < n; i++) { try { w.SP.advance(); } catch(e){} }
            }""",
            section_count + 1,
        )
        page.wait_for_timeout(1200)

        cmi = page.evaluate("() => window.cmiData")
        status = (cmi or {}).get("cmi.core.lesson_status", "")
        assert status in ("passed", "completed"), (
            f"After advancing to end-card, expected lesson_status in (passed, completed), "
            f"got {status!r}; full cmi: {cmi}"
        )
        browser.close()


# ----- Mock LMS HTML
_LMS_HTML = """<!DOCTYPE html>
<html><head><title>Mock LMS</title></head><body>
<iframe id="sco" src="about:blank" style="width:100%;height:600px;border:1px solid #888"></iframe>
<script>
window.cmiData = JSON.parse(localStorage.getItem('cmi') || '{}');
['cmi.core.lesson_status','cmi.core.lesson_location','cmi.suspend_data',
 'cmi.core.score.raw','cmi.core.score.max','cmi.core.score.min'].forEach(function(k){
  if (!(k in window.cmiData)) window.cmiData[k] = '';
});
if (!window.cmiData['cmi.core.lesson_status']) window.cmiData['cmi.core.lesson_status'] = 'not attempted';
window.API = {
  LMSInitialize: function(){ return 'true'; },
  LMSFinish: function(){ localStorage.setItem('cmi', JSON.stringify(window.cmiData)); return 'true'; },
  LMSGetValue: function(k){ return window.cmiData[k] || ''; },
  LMSSetValue: function(k,v){ window.cmiData[k] = v; return 'true'; },
  LMSCommit: function(){ localStorage.setItem('cmi', JSON.stringify(window.cmiData)); return 'true'; },
  LMSGetLastError: function(){ return '0'; },
  LMSGetErrorString: function(){ return ''; },
  LMSGetDiagnostic: function(){ return ''; }
};
document.getElementById('sco').src = 'index.html';
</script>
</body></html>"""

        # Drive advance() past the last section to trig