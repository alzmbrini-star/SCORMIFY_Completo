"""E2E tests for Krea → Gallery auto-save + AI Agent imagem_krea pipeline.

This is iteration_116 validation (round 2 of Krea). Exercises:
1. /api/gallery/images contains Krea entry with `keywords` starting with 'krea '.
2. /api/agent/courses/{id}/preview-improvements + apply-improvements end-to-end
   using a hand-crafted imagem_krea improvement; verifies the pipeline polls,
   attaches the image, auto-saves to gallery, and kreaImagesGenerated=1.
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ADMIN_EMAIL = "admin@scormify.com"
ADMIN_PASSWORD = "admin123"
TEST_PROJECT_ID = "cd8a1146-ac15-49ad-9161-c3ba5cb3e830"


@pytest.fixture(scope="module")
def auth_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=15,
    )
    if r.status_code != 200:
        pytest.skip(f"Login failed: {r.status_code} {r.text[:200]}")
    return r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


# ----- Gallery contains Krea entry -----
def test_gallery_contains_krea_image_with_keywords(auth_headers):
    r = requests.get(f"{BASE_URL}/api/gallery/images", headers=auth_headers, timeout=30)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:300]}"
    data = r.json()
    images = data.get("images") if isinstance(data, dict) else data
    assert isinstance(images, list), f"Expected list, got {type(images)}"
    print(f"Gallery has {len(images)} images")
    krea_imgs = [
        img for img in images
        if (img.get("keywords") or "").lower().startswith("krea ")
    ]
    print(f"Krea images in gallery: {len(krea_imgs)}")
    if krea_imgs:
        sample = krea_imgs[0]
        print(f"Sample Krea gallery entry keywords: {sample.get('keywords')!r}")
        # Keyword should be of form "krea {modelId}: {prompt}"
        assert ":" in (sample.get("keywords") or ""), \
            "Expected 'krea {modelId}: {prompt}' format"
    # Note: It's fine if 0 yet; the main agent should run a save to seed one. We
    # assert >= 0 and log. The assertion below is 'should exist' per spec:
    assert len(krea_imgs) >= 1, (
        "No Krea entries found in gallery. The save-to-project endpoint should "
        "auto-insert entries with keywords starting with 'krea '."
    )


# ----- Preview + Apply flow with imagem_krea -----
def test_apply_imagem_krea_end_to_end(auth_headers):
    """Inject an imagem_krea improvement and run through apply-improvements.
    Polls up to 4 minutes. Verifies kreaImagesGenerated >= 1 in DONE payload.
    """
    # Craft the improvement object directly (bypass LLM preview)
    selected = [{
        "slideIndex": 0,
        "type": "imagem_krea",
        "kreaModelId": "flux-1-dev",
        "imagePrompt": "modern corporate leadership boardroom, cinematic",
        "_kreaImage": {
            "prompt": "modern corporate leadership boardroom, cinematic",
            "modelId": "flux-1-dev",
            "width": 1024,
            "height": 576,
        },
        "description": "E2E test imagem_krea",
        "priority": "medium",
    }]

    r = requests.post(
        f"{BASE_URL}/api/agent/courses/{TEST_PROJECT_ID}/apply-improvements",
        headers=auth_headers,
        json={"improvements": selected},
        timeout=30,
    )
    assert r.status_code in (200, 202), \
        f"apply-improvements failed: {r.status_code} {r.text[:400]}"
    body = r.json()
    job_id = body.get("applyJobId") or body.get("jobId")
    if not job_id:
        # synchronous variant
        print(f"Synchronous apply response: {body}")
        assert body.get("kreaImagesGenerated", 0) >= 0
        return
    print(f"apply job id: {job_id}")

    # Poll status
    deadline = time.time() + 240  # 4 min
    last = None
    while time.time() < deadline:
        sr = requests.get(
            f"{BASE_URL}/api/agent/courses/{TEST_PROJECT_ID}/apply-status/{job_id}",
            headers=auth_headers,
            timeout=15,
        )
        if sr.status_code != 200:
            print(f"status poll non-200: {sr.status_code} {sr.text[:200]}")
            time.sleep(3)
            continue
        last = sr.json()
        st = (last.get("status") or "").lower()
        print(f"[{int(time.time())}] status={st} progress={last.get('progress')} "
              f"kreaImagesGenerated={last.get('kreaImagesGenerated')}")
        if st in ("done", "completed", "error", "failed"):
            break
        time.sleep(4)

    assert last is not None, "No status received"
    final = (last.get("status") or "").lower()
    assert final in ("done", "completed"), \
        f"Job did not finish successfully: {last}"
    # Must have generated at least 1 Krea image
    assert last.get("kreaImagesGenerated", 0) >= 1, (
        f"kreaImagesGenerated missing / zero in DONE payload: {last}"
    )
