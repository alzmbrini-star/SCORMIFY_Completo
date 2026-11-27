"""SlideKiln transport and offline packaging. Never retries a billable POST.

The provider deck remains one interactive HTML module, not native PPT objects.
All package resources are local and embedded, avoiding vendor retention links.
"""
import base64
import io
import json
import mimetypes
import os
import posixpath
import re
import zipfile
from pathlib import PurePosixPath
from urllib.parse import unquote, urlsplit
import httpx

BASE = 'https://slidekiln.com/backend'
MAX_INPUT = 32 * 1024 * 1024
MAX_DOCUMENT = 10 * 1024 * 1024
MAX_ZIP = 24 * 1024 * 1024
VERSION = 'slidekiln-2026-11-27-v2'

# Install before the vendor player: its window-level keyboard navigation must
# not consume native media keys or prevent the browser's default Play/Pause.
MEDIA_KEYS = '''<script id="sk-media-keyboard-v1">(()=>{
const mediaEvent=e=>e.composedPath().some(n=>n&&/^(AUDIO|VIDEO)$/.test(n.tagName));
const keys=new Set([' ','Spacebar','ArrowLeft','ArrowRight','ArrowUp','ArrowDown','PageUp','PageDown','Home','End','f','F']);
window.addEventListener('keydown',e=>{if(mediaEvent(e)&&keys.has(e.key))e.stopImmediatePropagation();});
window.addEventListener('keyup',e=>{if(mediaEvent(e)&&keys.has(e.key))e.stopImmediatePropagation();});
})();</script>'''


def runtime_document(html):
    """Non-persistent compatibility fix for new and already imported decks."""
    if 'id="sk-media-keyboard-v1"' in html:
        return html
    return re.sub(r'(<head\b[^>]*>)', lambda m: m[0] + MEDIA_KEYS,
                  html, count=1, flags=re.I)


def configured():
    return bool(os.environ.get('SLIDEKILN_API_KEY', '').strip())


def pptx_info(data, filename):
    if not filename.lower().endswith('.pptx'):
        raise ValueError('SlideKiln aceita somente .pptx. Para .ppt, use o ConvertAPI ou salve como .pptx.')
    if not data or len(data) > MAX_INPUT:
        raise ValueError('O limite desta integração é 32 MB por PPTX.')
    files = safe_zip(data, total_limit=64 * 1024 * 1024)
    if '[Content_Types].xml' not in files or 'ppt/presentation.xml' not in files:
        raise ValueError('Arquivo PPTX inválido.')
    slides = [n for n in files if re.fullmatch(r'ppt/slides/slide\d+\.xml', n)]
    if not 1 <= len(slides) <= 500:
        raise ValueError('Envie uma apresentação com 1 a 500 slides.')
    return {'slides': len(slides)}


def safe_zip(data, total_limit=64 * 1024 * 1024):
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > 8000 or sum(e.file_size for e in entries) > total_limit:
                raise ValueError('Pacote excede o limite seguro de descompactação.')
            result = {}
            for entry in entries:
                name = entry.orig_filename
                if entry.is_dir():
                    continue
                if (name in result or '\\' in name or '\x00' in name or
                    PurePosixPath(name).is_absolute() or '..' in PurePosixPath(name).parts or
                    ':' in name or (entry.external_attr >> 16) & 0o170000 == 0o120000 or
                    entry.flag_bits & 1):
                    raise ValueError('Pacote contém caminho ou entrada não permitida.')
                result[name] = archive.read(entry)
            return result
    except (zipfile.BadZipFile, RuntimeError) as exc:
        raise ValueError('Pacote ZIP/PPTX inválido.') from exc


async def submit(client, data, filename, quote_id):
    # No follow_redirects: do not send the API key to an unexpected host.
    response = await client.post(BASE + '/v1/jobs',
        headers={'Authorization': 'Bearer ' + os.environ['SLIDEKILN_API_KEY'].strip(),
                 'Idempotency-Key': quote_id},
        files={'file': (filename, data, 'application/vnd.openxmlformats-officedocument.presentationml.presentation')},
        data={'options': json.dumps({'hosted': False, 'externalId': quote_id,
                                     'videoMaxHeight': 1080, 'videoCrf': 28})})
    response.raise_for_status()
    ident = response.json().get('jobId', '')
    import uuid
    uuid.UUID(ident)
    return ident


async def status(client, ident):
    response = await client.get(BASE + '/v1/jobs/' + ident,
        headers={'Authorization': 'Bearer ' + os.environ['SLIDEKILN_API_KEY'].strip()})
    response.raise_for_status()
    return response.json()


async def download(client, ident):
    # Capability download redirects are followed only to the provider's GCS host.
    url = BASE + '/v1/jobs/' + ident + '/download'
    for _ in range(4):
        async with client.stream('GET', url) as response:
            if response.status_code in (301, 302, 303, 307, 308):
                url = response.headers.get('location', '')
                parsed = urlsplit(url)
                if (parsed.scheme != 'https' or parsed.hostname != 'storage.googleapis.com'
                    or parsed.username or parsed.password or parsed.port not in (None, 443)):
                    raise ValueError('Destino de download inesperado; nenhuma credencial foi enviada.')
                continue
            response.raise_for_status()
            output = bytearray()
            async for chunk in response.aiter_bytes():
                output.extend(chunk)
                if len(output) > MAX_ZIP:
                    raise ValueError('Pacote convertido excede 24 MB. Nenhuma nova conversão será iniciada automaticamente.')
            return bytes(output)
    raise ValueError('Download excedeu o limite de redirecionamentos.')


def offline_document(data):
    files = safe_zip(data)
    if not {'index.html', 'assets/player.js', 'assets/styles.css'} <= files.keys():
        raise ValueError('Formato do pacote SlideKiln não reconhecido.')
    raw = files['index.html'].decode('utf-8')

    def resource(url, base=''):
        parts = urlsplit(url)
        if parts.scheme or parts.netloc or not parts.path or url.startswith('/'):
            raise ValueError('Recurso externo não permitido no pacote.')
        path = posixpath.normpath(posixpath.join(base, unquote(parts.path)))
        if path not in files or path.startswith('../'):
            raise ValueError('Recurso ausente no pacote: ' + path[:100])
        mime = mimetypes.guess_type(path)[0] or 'application/octet-stream'
        return 'data:' + mime + ';base64,' + base64.b64encode(files[path]).decode('ascii')

    css = files['assets/styles.css'].decode('utf-8')
    css = re.sub(r'url\([\'\"]?([^\)\'\"]+)[\'\"]?\)', lambda m: 'url("' + resource(m[1], 'assets') + '")', css)
    if '@import' in css.lower():
        raise ValueError('Folha de estilos externa não permitida.')
    raw = re.sub(r'<link\b[^>]*href=[\'\"]assets/styles.css[\'\"][^>]*>', lambda _: '<style>' + css + '</style>', raw, flags=re.I)
    js = files['assets/player.js'].decode('utf-8').replace('</script', '<\\/script')
    raw = re.sub(r'<script\b[^>]*src=[\'\"]assets/player.js[\'\"][^>]*>\s*</script>', lambda _: '<script>' + js + '</script>', raw, flags=re.I)
    raw = re.sub(r'\b(src|poster)=[\'\"]([^\'\"]+)[\'\"]', lambda m: m[1] + '="' + resource(m[2]) + '"', raw, flags=re.I)
    # Inline SVG assets may reference media through href/xlink:href.
    raw = re.sub(r'\b((?:xlink:)?href)=[\'\"](assets/[^\'\"]+)[\'\"]', lambda m: m[1] + '="' + resource(m[2]) + '"', raw, flags=re.I)
    if re.search(r'<script\b[^>]*\bsrc\s*=|<iframe\b|<base\b|<object\b|<embed\b|<form\b', raw, re.I):
        raise ValueError('O pacote contém conteúdo externo não suportado.')
    policy = "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; font-src data:; media-src data: blob:; connect-src 'none'; frame-src 'none'; base-uri 'none'; form-action 'none'"
    raw = raw.replace('<head>', '<head><meta http-equiv="Content-Security-Policy" content="' + policy + '">', 1)
    raw = runtime_document(raw.replace('</body>', MOBILE + '</body>'))
    if len(raw.encode('utf-8')) > MAX_DOCUMENT:
        raise ValueError('Apresentação interativa excede 10 MB após incorporação. Reduza vídeos/imagens antes de aprovar outra conversão; a chamada atual não será repetida.')
    return raw


MOBILE = '''<style>
html,body{height:100%!important;margin:0!important;overflow:hidden!important}
#viewport{height:calc(100% - 58px)!important;overflow:auto!important;touch-action:pan-x pan-y}
#sk-mobile{position:fixed;bottom:0;left:0;right:0;min-height:54px;display:flex;align-items:center;justify-content:center;gap:6px;padding:2px;background:#001628;color:white;z-index:99999;font:14px Arial}
#sk-mobile button{min-height:44px;min-width:44px;border:1px solid #86cbd1;border-radius:6px;background:#123949;color:white;font:14px Arial;padding:4px 8px}
#sk-mobile button:focus-visible{outline:3px solid #ffcf4a}#sk-counter{white-space:nowrap}.sk-controls{display:none!important}
#sk-canvas{position:relative;overflow:hidden;margin-left:auto;margin-right:auto}#sk-hint{font-size:12px;text-align:center;margin:0;background:#001628;color:white}
@media(min-width:700px){#sk-hint{display:none}}@media(max-width:420px){#sk-mobile{font-size:12px;gap:3px}#sk-mobile button{font-size:12px;padding:3px 5px}}
</style><nav id="sk-mobile" aria-label="Controles da apresentação"><button id="sk-prev" aria-label="Slide anterior">◀</button><span id="sk-counter" aria-live="polite"></span><button id="sk-next" aria-label="Próxima etapa ou slide">▶</button><button id="sk-zoom" aria-pressed="false">Ampliar</button><button id="sk-full">Tela cheia</button></nav>
<script>(()=>{const by=id=>document.getElementById(id);function ready(){const p=window.SlideKiln;if(!p){setTimeout(ready,100);return;}const stage=by('stage'),view=by('viewport'),canvas=document.createElement('div');canvas.id='sk-canvas';view.appendChild(canvas);canvas.appendChild(stage);let zoom=false;const fit=()=>{const w=Number(stage.dataset.w)||1280,h=Number(stage.dataset.h)||720,aw=innerWidth,ah=Math.max(80,innerHeight-58),scale=Math.min(aw/w,ah/h)*(zoom?2.5:1);canvas.style.width=(w*scale)+'px';canvas.style.height=(h*scale)+'px';canvas.style.marginTop=Math.max(0,(ah-h*scale)/2)+'px';stage.style.transform='scale('+scale+')';};const update=()=>{by('sk-counter').textContent=p.current+'/'+p.count;by('sk-prev').disabled=p.current<=1;fit();};by('sk-mobile').addEventListener('click',e=>e.stopPropagation());by('sk-prev').onclick=()=>p.prev();by('sk-next').onclick=()=>p.next();by('sk-full').onclick=()=>p.toggleFullscreen();by('sk-zoom').onclick=()=>{zoom=!zoom;by('sk-zoom').textContent=zoom?'Ajustar':'Ampliar';by('sk-zoom').setAttribute('aria-pressed',String(zoom));fit();};addEventListener('resize',fit);p.on('slidechange',update);update();}ready();})();</script>'''


def module_html(project_id, filename):
    # A sandbox without same-origin prevents converted scripts reading app tokens.
    return ('<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<style id="__scormify_page_mode">html,body{margin:0!important;padding:0!important;width:100%!important;height:100%!important;overflow:hidden!important}body>iframe{position:fixed!important;inset:0!important;width:100vw!important;height:100vh!important;max-width:none!important;border:0}</style>'
            '</head><body><iframe title="Apresentação PowerPoint interativa" sandbox="allow-scripts allow-popups" '
            'allow="autoplay; fullscreen" allowfullscreen src="/api/projects/' + project_id + '/assets/' + filename + '"></iframe>'
            '<script>(()=>{const f=document.querySelector("iframe"),s=f.getAttribute("data-sk-src");if(s&&s.startsWith("data:text/html;base64,")){const raw=atob(s.split(",")[1]),bytes=new Uint8Array(raw.length);for(let i=0;i<raw.length;i++)bytes[i]=raw.charCodeAt(i);const url=URL.createObjectURL(new Blob([bytes],{type:"text/html"}));f.src=url;addEventListener("pagehide",()=>URL.revokeObjectURL(url),{once:true});}})();</script></body></html>')


def inline_module_assets(html, assets_dir):
    """Fail closed rather than ship an export depending on an expiring app asset.
    Existing project asset persistence is reused; no conversion or provider call.
    """
    from pathlib import Path
    pattern = re.compile(r'\bsrc=[\'\"](/api/projects/([a-f0-9-]{36})/assets/([a-f0-9]{32}\.sk\.html))[\'\"]')
    def replace(match):
        path = Path(assets_dir) / match[3]
        if not path.exists():
            from routes import deps
            from services.asset_store import retrieve_asset_sync
            if not retrieve_asset_sync(deps.mongo_url, deps.db_name, match[2], match[3], str(path)):
                raise ValueError('Pacote SlideKiln não disponível para exportação offline. Restaure o arquivo antes de exportar; nenhuma conversão foi solicitada.')
        if path.stat().st_size > MAX_DOCUMENT:
            raise ValueError('Pacote SlideKiln excede o limite de exportação segura.')
        # Patch only the response/export copy; never rewrite stored originals.
        document = runtime_document(path.read_text(encoding='utf-8'))
        encoded = 'data:text/html;base64,' + base64.b64encode(document.encode('utf-8')).decode('ascii')
        # Chrome blocks multi-megabyte data: navigations. The controlled host
        # creates a Blob URL before loading its sandboxed child instead.
        return 'data-sk-src="' + encoded + '"'
    return pattern.sub(replace, html)


def install_host(html):
    """Only a sole SlideKiln module gets a fluid canvas; other slides unchanged."""
    css = '''<style id="slidekiln-fluid-host">
#slide-wrapper:has(iframe[data-slidekiln-module]){padding:0!important;overflow:hidden!important;display:block!important}
#slide-container:has(>.slide-element:only-child>iframe[data-slidekiln-module]){width:100%!important;height:calc(100dvh - 150px)!important;min-height:260px!important;transform:none!important;margin:0!important;box-shadow:none!important}
.slide-element:only-child:has(>iframe[data-slidekiln-module]){left:0!important;top:0!important;width:100%!important;height:100%!important}
iframe[data-slidekiln-module]{width:100%!important;height:100%!important}
</style>'''
    return html.replace('</head>', css + '</head>', 1)
