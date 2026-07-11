"""Regression tests for the Whiteboard subprocess isolation + 720p output.

Covers:
1. Worker CLI renders a small text spec → ok:true, 1280x720 output on disk.
2. Worker CLI with invalid input → ok:false / errorType=ValueError / rc=1.
3. Output resolution constants derived from WHITEBOARD_OUTPUT_HEIGHT.
"""
import json
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
WORKER = BACKEND_DIR / "services" / "whiteboard_worker.py"

sys.path.insert(0, str(BACKEND_DIR))


def _run_worker(spec: dict, tmp_path: Path):
    spec_path = tmp_path / "spec.json"
    result_path = tmp_path / "result.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(WORKER), str(spec_path), str(result_path)],
        cwd=str(BACKEND_DIR), capture_output=True, timeout=300,
    )
    data = json.loads(result_path.read_text(encoding="utf-8")) if result_path.exists() else None
    return proc.returncode, data


def test_worker_renders_text_spec(tmp_path):
    rc, data = _run_worker(
        {"kind": "text", "params": {"text": "Ok!", "chars_per_second": 20.0}},
        tmp_path,
    )
    assert rc == 0
    assert data["ok"] is True
    assert data["info"]["resolution"] == "1280x720"
    assert data["url"].startswith("/api/whiteboard/file/wb_")
    from services.whiteboard_renderer import OUTPUT_DIR
    fname = data["url"].rsplit("/", 1)[-1]
    out = OUTPUT_DIR / fname
    assert out.exists() and out.stat().st_size > 0
    out.unlink()


def test_worker_reports_value_error(tmp_path):
    rc, data = _run_worker(
        {"kind": "text", "params": {"text": "   "}},
        tmp_path,
    )
    assert rc == 1
    assert data["ok"] is False
    assert data["errorType"] == "ValueError"


def test_worker_rejects_unknown_kind(tmp_path):
    rc, data = _run_worker({"kind": "nope", "params": {}}, tmp_path)
    assert rc == 1
    assert data["ok"] is False


def test_output_resolution_constants():
    from services.whiteboard_renderer import CANVAS_W, CANVAS_H, OUT_W, OUT_H
    assert (CANVAS_W, CANVAS_H) == (1920, 1080)
    assert (OUT_W, OUT_H) == (1280, 720)
    assert OUT_W % 2 == 0 and OUT_H % 2 == 0
