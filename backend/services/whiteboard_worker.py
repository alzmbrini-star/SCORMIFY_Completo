"""CLI worker that renders a Whiteboard in an ISOLATED child process.

Why a separate process instead of asyncio.to_thread inside the API
worker? Two production-critical reasons:

1. OOM isolation — on memory-tight production pods, a render that
   exceeds the container budget gets SIGKILL'ed by the kernel. When the
   render lives inside the API process, the KILL takes down the whole
   backend (every request 502/520s). In a child process only the child
   dies; the parent detects the non-zero exit and fails the job
   gracefully with a friendly message.
2. Memory return — CPython rarely returns freed heap back to the OS
   (arena fragmentation), so RSS stays inflated after every render.
   A short-lived child gives 100% of the memory back on exit.

Usage:  python services/whiteboard_worker.py <spec.json> <result.json>

spec.json:   {"kind": "text"|"plan", "params": {...render kwargs...}}
result.json: {"ok": true, "url": ..., "info": {...}}
             {"ok": false, "error": "...", "errorType": "ValueError"}
Exit code 0 on success, 1 on handled error.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _render(spec: dict):
    kind = spec.get("kind")
    params = dict(spec.get("params") or {})
    if kind == "text":
        from services.whiteboard_renderer import render_whiteboard_video
        ink = params.get("ink_color")
        if ink is not None:
            params["ink_color"] = tuple(ink)
        return asyncio.run(render_whiteboard_video(**params))
    if kind == "plan":
        from services.whiteboard_plan_renderer import render_whiteboard_plan
        plan = params.pop("plan")
        return asyncio.run(render_whiteboard_plan(plan, **params))
    raise ValueError(f"unknown render kind: {kind!r}")


def main() -> int:
    spec_path, result_path = sys.argv[1], sys.argv[2]
    with open(spec_path, encoding="utf-8") as f:
        spec = json.load(f)
    try:
        rel_url, info = _render(spec)
    except Exception as e:  # noqa: BLE001
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump({
                "ok": False,
                "error": str(e)[:1000],
                "errorType": type(e).__name__,
            }, f)
        return 1
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump({"ok": True, "url": rel_url, "info": info}, f)
    return 0


if __name__ == "__main__":
    sys.exit(main())
