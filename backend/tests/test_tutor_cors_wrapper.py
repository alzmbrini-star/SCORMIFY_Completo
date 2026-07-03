"""Regression tests for the ASGI CORS wrapper that reflects the origin
back to cross-origin callers (LMS-hosted exported courses).

Background: Cloudflare in front of the production backend strips
`Access-Control-Allow-Origin: *` from POST responses, breaking cross-origin
feedback from courses hosted inside third-party LMSs (Moodle, TalentLMS, ...).
The wrapper in `server.py` intercepts these endpoints and reflects the
concrete `Origin` header instead.

If a future change removes /tutor/feedback from the wrapper again, the admin
Tutor dashboard will silently show 0 for feedback counts — hard to spot.
"""

from pathlib import Path

SERVER_SRC = Path("/app/backend/server.py").read_text()


def test_tutor_cors_wrapper_covers_feedback_endpoint():
    """The wrapper must intercept /tutor/feedback so Cloudflare doesn't strip
    Access-Control-Allow-Origin on the POST response.
    """
    # Must declare the feedback path in the paths tuple
    assert '"/tutor/feedback"' in SERVER_SRC, (
        "/tutor/feedback must be in the CORS reflection whitelist; otherwise "
        "cross-origin POSTs from LMSs get their CORS header stripped by "
        "Cloudflare and the admin dashboard silently loses feedback rows."
    )
    # And /tutor/chat must remain covered
    assert '"/tutor/chat"' in SERVER_SRC


def test_tutor_cors_wrapper_uses_any_check_not_hardcoded_path():
    """Guard against a future refactor accidentally hardcoding a single path
    check (which was the original bug). The wrapper must iterate paths."""
    # Either _TUTOR_CORS_PATHS tuple or a `for p in ...` loop must be present
    assert "_TUTOR_CORS_PATHS" in SERVER_SRC or "any(p in path" in SERVER_SRC
