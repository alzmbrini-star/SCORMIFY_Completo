"""Extended tests for the Single-Page (vertical scroll) HTML export mode.
Covers: HTML markers, JS runtime exposure, element gating attributes,
drawer (linear strict) markup, end-card lock, override hierarchy edge cases.
"""
import os
import re
import pytest
import requests

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8001")
SUPER = {"email": "admin@scormify.com", "password": "admin123"}


@pytest.fixture(scope="module")
def super_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json=SUPER, timeout=10)
    r.raise_for_status()
    return r.json()["token"]


@pytest.fixture(scope="module")
def project_id(super_token):
    r = requests.get(
        f"{BASE_URL}/api/projects",
        headers={"Authorization": f"Bearer {super_token}"},
        timeout=10,
    )
    r.raise_for_status()
    items = r.json()
    assert len(items) > 0
    return items[0]["id"]


@pytest.fixture(scope="module")
def single_page_html(super_token, project_id):
    """Generate one single-page export and return its full HTML for shared assertions."""
    r = requests.post(
        f"{BASE_URL}/api/course/{project_id}/export-html",
        headers={"Authorization": f"Bearer {super_token}",
                 "Content-Type": "application/json"},
        json={"singlePage": True},
        timeout=60,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    download = body["downloadUrl"]
    f = requests.get(f"{BASE_URL}{download}?preview=1", timeout=30)
    assert f.status_code == 200
    return {"html": f.text, "filename": body["filename"], "downloadUrl": download}


# --- HTML structure & headers -------------------------------------------------

def test_html_header_has_hamburger_progress_and_title(single_page_html):
    html = single_page_html["html"]
    assert "<header" in html, "header tag missing"
    assert 'data-testid="sp-menu-btn"' in html
    # Hamburger is rendered as an inline SVG with three horizontal strokes
    # inside the sp-menu-btn (rather than the literal ☰ glyph).
    menu_btn = re.search(
        r'<button[^>]*data-testid="sp-menu-btn"[^>]*>(.*?)</button>',
        html, flags=re.S,
    )
    assert menu_btn, "sp-menu-btn element missing"
    btn_inner = menu_btn.group(1)
    assert "<svg" in btn_inner, "hamburger SVG missing inside sp-menu-btn"
    assert btn_inner.count("<path") >= 3, "hamburger SVG should have 3 horizontal paths"
    assert 'data-testid="sp-progress-fill"' in html
    assert 'class="sp-progress-fill"' in html


def test_html_drawer_aside_present(single_page_html):
    html = single_page_html["html"]
    assert "<aside" in html, "drawer aside missing"
    # Drawer should contain item entries; locked sections rendered with 🔒 prefix
    assert "sp-drawer" in html


def test_first_section_unlocked_others_locked(single_page_html):
    html = single_page_html["html"]
    sections = re.findall(r'<section[^>]*class="(?:sp-end-card )?sp-section"[^>]*>', html)
    assert len(sections) >= 2
    assert 'data-locked="true"' not in sections[0], (
        f"first section must be unlocked, got: {sections[0]}"
    )
    for s in sections[1:]:
        assert 'data-locked="true"' in s, f"expected locked: {s}"


def test_end_card_section_is_locked_and_final(single_page_html):
    html = single_page_html["html"]
    m = re.search(
        r'<section[^>]*class="sp-end-card sp-section"[^>]*>',
        html,
    )
    assert m, "end-card section not found"
    tag = m.group(0)
    assert 'data-final="true"' in tag
    assert 'data-locked="true"' in tag


def test_next_button_present_and_initially_hidden(single_page_html):
    html = single_page_html["html"]
    m = re.search(r'<button[^>]*data-testid="sp-next-btn"[^>]*>', html)
    assert m, "sp-next-btn missing"
    btn = m.group(0)
    assert "hidden" in btn, "sp-next-btn should be initially hidden"
    assert "SP.advance()" in btn


def test_filename_singlepage_marker(single_page_html):
    fn = single_page_html["filename"]
    assert "_singlepage_" in fn
    assert fn.endswith(".html")


# --- JS runtime exposure ------------------------------------------------------

def test_window_sp_runtime_methods_exposed(single_page_html):
    html = single_page_html["html"]
    # Confirm the runtime registers `window.SP` with the documented surface
    assert "window.SP" in html
    for fn_name in ("advance", "gotoSection", "toggleDrawer",
                    "markPlayed", "markClicked", "startQuiz"):
        assert fn_name in html, f"runtime fn `{fn_name}` missing in JS"
    # Internal helper used by gating
    assert "isSectionComplete" in html


# --- Element gating attributes ------------------------------------------------

def test_audio_elements_have_required_gating_attributes(single_page_html):
    """Every <audio>-wrapping element must declare data-interactive='audio' data-required='true'
    AND its <audio onplay=...> must call SP.markPlayed."""
    html = single_page_html["html"]
    audio_blocks = re.findall(
        r'<div[^>]*data-interactive="audio"[^>]*data-required="true"[^>]*>.*?</div>',
        html, flags=re.S,
    )
    # Project may have zero audios; if present, ensure markPlayed wiring on inner <audio>
    for block in audio_blocks:
        assert "onplay=" in block and "SP.markPlayed" in block


def test_html_interactives_gated(single_page_html):
    """HTML elements that contain <button>/<details>/onclick should be wrapped with
    data-interactive='html' onclick=SP.markClicked."""
    html = single_page_html["html"]
    if 'data-interactive="html"' in html:
        wrappers = re.findall(
            r'<div[^>]*data-interactive="html"[^>]*data-required="true"[^>]*onclick="[^"]*SP\.markClicked',
            html,
        )
        assert len(wrappers) >= 1, "HTML interactive wrapper missing onclick=SP.markClicked"


def test_quiz_scenario_simulator_gating(single_page_html):
    """If the project has any quiz/scenario/simulator slides, each must be
    annotated with data-interactive=<type> data-required='true'."""
    html = single_page_html["html"]
    for kind in ("quiz", "scenario", "simulator"):
        marker = f'data-interactive="{kind}"'
        if marker in html:
            wrappers = re.findall(
                rf'<div[^>]*data-interactive="{kind}"[^>]*data-required="true"[^>]*>',
                html,
            )
            assert len(wrappers) >= 1, f"{kind} block missing data-required='true'"


# --- Override hierarchy edge cases --------------------------------------------

def test_override_singlepage_false_overrides_project_true(super_token, project_id):
    """Body singlePage=false must beat project.singlePageMode=true."""
    requests.put(
        f"{BASE_URL}/api/projects/{project_id}",
        headers={"Authorization": f"Bearer {super_token}",
                 "Content-Type": "application/json"},
        json={"singlePageMode": True},
        timeout=10,
    ).raise_for_status()
    try:
        r = requests.post(
            f"{BASE_URL}/api/course/{project_id}/export-html",
            headers={"Authorization": f"Bearer {super_token}",
                     "Content-Type": "application/json"},
            json={"singlePage": False},
            timeout=60,
        )
        assert r.status_code == 200, r.text
        assert r.json().get("mode") == "traditional"
        assert "_singlepage_" not in r.json().get("filename", "")
    finally:
        requests.put(
            f"{BASE_URL}/api/projects/{project_id}",
            headers={"Authorization": f"Bearer {super_token}",
                     "Content-Type": "application/json"},
            json={"singlePageMode": False},
            timeout=10,
        )


def test_get_project_persists_singlepagemode(super_token, project_id):
    """After PUT singlePageMode=true, GET /api/projects/{id} must echo it back."""
    requests.put(
        f"{BASE_URL}/api/projects/{project_id}",
        headers={"Authorization": f"Bearer {super_token}",
                 "Content-Type": "application/json"},
        json={"singlePageMode": True},
        timeout=10,
    ).raise_for_status()
    try:
        g = requests.get(
            f"{BASE_URL}/api/projects/{project_id}",
            headers={"Authorization": f"Bearer {super_token}"},
            timeout=10,
        )
        assert g.status_code == 200
        assert g.json().get("singlePageMode") is True
    finally:
        requests.put(
            f"{BASE_URL}/api/projects/{project_id}",
            headers={"Authorization": f"Bearer {super_token}",
                     "Content-Type": "application/json"},
            json={"singlePageMode": False},
            timeout=10,
        )


# --- Preview vs download Content-Disposition ---------------------------------

def test_preview_inline_no_attachment(single_page_html):
    f = requests.get(f"{BASE_URL}{single_page_html['downloadUrl']}?preview=1", timeout=15)
    assert f.status_code == 200
    assert f.headers.get("content-type", "").startswith("text/html")
    assert "attachment" not in (f.headers.get("content-disposition", "") or "")


def test_download_forces_attachment(single_page_html):
    f = requests.get(f"{BASE_URL}{single_page_html['downloadUrl']}", timeout=15,
                     allow_redirects=False)
    assert f.status_code == 200
    cd = f.headers.get("content-disposition", "") or ""
    assert "attachment" in cd
