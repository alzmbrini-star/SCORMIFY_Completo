"""VLibras CORS proxy routes"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, Response, HTMLResponse
from pathlib import Path
import httpx
import logging

logger = logging.getLogger("server")

router = APIRouter(tags=["VLibras"])

_VLIBRAS_DOMAINS = {
    "dicionario2": "https://dicionario2.vlibras.gov.br",
    "traducao2": "https://traducao2.vlibras.gov.br",
}
_VLIBRAS_BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Referer": "https://www.vlibras.gov.br/",
    "Origin": "https://www.vlibras.gov.br",
}


async def _vlibras_proxy_request(domain_key: str, path: str, request: Request):
    base_url = _VLIBRAS_DOMAINS.get(domain_key)
    if not base_url:
        raise HTTPException(status_code=400, detail="Invalid VLibras domain key")
    url = f"{base_url}/{path}" if path else base_url
    query = str(request.query_params)
    if query:
        url += f"?{query}"
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            if request.method == "POST":
                body = await request.body()
                content_type = request.headers.get("content-type", "application/json")
                resp = await client.post(url, content=body, headers={**_VLIBRAS_BROWSER_HEADERS, "Content-Type": content_type})
            else:
                resp = await client.get(url, headers=_VLIBRAS_BROWSER_HEADERS)
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            media_type=resp.headers.get("content-type", "application/octet-stream"),
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
                "Cache-Control": "public, max-age=86400" if request.method == "GET" else "no-cache",
            },
        )
    except Exception as e:
        logger.warning(f"VLibras proxy error ({domain_key}/{path}): {e}")
        raise HTTPException(status_code=502, detail=f"VLibras proxy error: {str(e)}")


@router.api_route("/vlibras-proxy/dicionario2/{path:path}", methods=["GET", "OPTIONS"])
async def vlibras_dicionario_proxy(path: str, request: Request):
    if request.method == "OPTIONS":
        return Response(status_code=204, headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Max-Age": "86400",
        })
    return await _vlibras_proxy_request("dicionario2", path, request)


@router.api_route("/vlibras-proxy/traducao2/{path:path}", methods=["GET", "POST", "OPTIONS"])
async def vlibras_traducao_proxy(path: str, request: Request):
    if request.method == "OPTIONS":
        return Response(status_code=204, headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Max-Age": "86400",
        })
    return await _vlibras_proxy_request("traducao2", path, request)


@router.get("/vlibras-dict/{path:path}")
async def vlibras_dict_proxy_legacy(path: str, request: Request):
    return await _vlibras_proxy_request("dicionario2", path, request)


@router.get("/vlibras-test/{path:path}")
async def vlibras_test_assets(path: str):
    test_dir = Path(__file__).parent.parent / "static_test" / "scorm_live"
    file_path = test_dir / path
    if file_path.exists() and file_path.is_file():
        media_types = {'.js': 'application/javascript', '.css': 'text/css', '.json': 'application/json', '.png': 'image/png', '.jpg': 'image/jpeg', '.mp3': 'audio/mpeg', '.html': 'text/html'}
        return FileResponse(str(file_path), media_type=media_types.get(file_path.suffix.lower(), 'application/octet-stream'))
    raise HTTPException(status_code=404, detail="File not found")


@router.get("/vlibras-test")
async def vlibras_test():
    test_dir = Path(__file__).parent.parent / "static_test" / "scorm_live"
    html_path = test_dir / "index.html"
    html = html_path.read_text()
    html = html.replace('<head>', '<head>\n    <base href="/api/vlibras-test/">')
    return HTMLResponse(content=html)


@router.get("/vlibras-simple-test")
async def vlibras_simple_test():
    test_path = Path(__file__).parent.parent / "static_test" / "vlibras_simple_test.html"
    html = test_path.read_text()
    return HTMLResponse(content=html)


@router.get("/vlibras-proxy-test")
async def vlibras_proxy_test(request: Request):
    test_path = Path(__file__).parent.parent / "static_test" / "vlibras_proxy_test.html"
    html = test_path.read_text()
    origin = request.headers.get('origin', '')
    if not origin:
        fwd_host = request.headers.get('x-forwarded-host', '')
        scheme = request.headers.get('x-forwarded-proto', 'https')
        if fwd_host:
            origin = f"{scheme}://{fwd_host}"
        else:
            try:
                env_path = Path(__file__).parent.parent.parent / "frontend" / ".env"
                for line in env_path.read_text().splitlines():
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        origin = line.split("=", 1)[1].strip()
                        break
            except Exception:
                host = request.headers.get('host', '')
                origin = f"https://{host}" if host else ''
    proxy_base = origin.rstrip('/') + '/api/vlibras-proxy'
    html = html.replace('__PROXY_BASE__', proxy_base)
    return HTMLResponse(content=html)
