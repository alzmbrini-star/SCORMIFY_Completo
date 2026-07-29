"""Regression tests for the backend URL embedded in SCORM/HTML exports."""

from starlette.requests import Request

from routes.export import _get_external_url


def _request(host: str, *, referer: str = "", forwarded_host: str = "") -> Request:
    headers = [(b"host", host.encode())]
    if referer:
        headers.append((b"referer", referer.encode()))
    if forwarded_host:
        headers.extend([
            (b"x-forwarded-host", forwarded_host.encode()),
            (b"x-forwarded-proto", b"https"),
        ])
    return Request({
        "type": "http",
        "method": "POST",
        "scheme": "https",
        "path": "/api/course/project/export-scorm",
        "raw_path": b"/api/course/project/export-scorm",
        "query_string": b"",
        "headers": headers,
        "server": (host, 443),
        "client": ("127.0.0.1", 12345),
    })


def test_frontend_referer_never_becomes_tutor_api_url():
    request = _request(
        "scormify-completo.onrender.com",
        referer="https://scormify-app.onrender.com/editor/project",
    )

    assert _get_external_url(request) == "https://scormify-completo.onrender.com"


def test_forwarded_backend_host_has_priority():
    request = _request(
        "internal-render-host",
        referer="https://scormify-app.onrender.com/editor/project",
        forwarded_host="scormify-completo.onrender.com",
    )

    assert _get_external_url(request) == "https://scormify-completo.onrender.com"


def test_runtime_backend_url_is_used_without_request(monkeypatch):
    monkeypatch.setenv("PUBLIC_BACKEND_URL", "https://scormify-completo.onrender.com/")

    assert _get_external_url() == "https://scormify-completo.onrender.com"
