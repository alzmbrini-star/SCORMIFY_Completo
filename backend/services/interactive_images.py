"""Display/export copies only; never changes the bank, library or simulator rules."""
import base64
import io
import json
import re
from functools import lru_cache

_DATA = re.compile(r'(<script\b[^>]*\bid=["\'](assessment-data|scormify-simulator-plan|scormify-visualization-plan)["\'][^>]*>)([\s\S]*?)(</script>)', re.I)

def image_url(url, assets_dir=None):
    # Reuse the exact file/cache policy of Astryx; no remote fetching here.
    import html
    from services.astryx_images import prepare_astryx_images
    if not isinstance(url,str):return url
    tag='<main data-astryx-lesson="1"><img src="'+html.escape(url,quote=True)+'"></main>'
    converted=prepare_astryx_images(tag,assets_dir)
    match=re.search(r'\bsrc="([^"]+)"',converted)
    return html.unescape(match[1]) if match else url

@lru_cache(maxsize=24)
def compact_piece(src):
    """Lossless PNG only: retain pixel size, alpha and existing editor schema."""
    if not isinstance(src,str) or not src.startswith('data:image/png;base64,') or not 40_000<len(src)<340_000:
        return src
    try:
        raw=base64.b64decode(src.split(',',1)[1],validate=True)
        from PIL import Image
        with Image.open(io.BytesIO(raw)) as image:
            if image.format!='PNG' or max(image.size)>512 or getattr(image,'is_animated',False):return src
            output=io.BytesIO();image.save(output,format='PNG',optimize=True,compress_level=9)
        optimized=output.getvalue()
        return 'data:image/png;base64,'+base64.b64encode(optimized).decode() if len(optimized)<len(raw)*.9 else src
    except Exception:return src

def prepare_interactive_images(document, assets_dir=None):
    if not isinstance(document,str):return document
    if document.startswith('__B64__:'):
        try:
            raw=base64.b64decode(document[8:],validate=True).decode('utf-8')
            updated=prepare_interactive_images(raw,assets_dir)
            return document if raw==updated else '__B64__:'+base64.b64encode(updated.encode()).decode()
        except (ValueError,UnicodeError):return document
    def replace(match):
        try:data=json.loads(match[3])
        except (ValueError,TypeError):return match[0]
        changed=False
        def visit(value):
            nonlocal changed
            if isinstance(value,list):return [visit(v) for v in value]
            if not isinstance(value,dict):return value
            result={k:visit(v) for k,v in value.items()}
            if match[2].lower()=='assessment-data' and result.get('kind')=='image' and isinstance(result.get('url'),str):
                updated=image_url(result['url'],assets_dir)
                if updated!=result['url']:result['url']=updated;changed=True
            if match[2].lower()!='assessment-data' and isinstance(result.get('illustrations'),list):
                for piece in result['illustrations']:
                    if not isinstance(piece,dict) or set(piece)!={'node','src'}:continue
                    updated=compact_piece(piece['src'])
                    if updated!=piece['src']:piece['src']=updated;changed=True
            return result
        updated=visit(data)
        if not changed:return match[0]
        return match[1]+json.dumps(updated,ensure_ascii=False).replace('<','\\u003c')+match[4]
    return _DATA.sub(replace,document)
