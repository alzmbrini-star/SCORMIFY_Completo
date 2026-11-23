"""Cached display derivatives for generated Astryx illustrations, never originals."""
import base64
import hashlib
import html
import io
import re
import threading
import tempfile
from pathlib import Path
from urllib.parse import urlsplit, parse_qsl, urlencode, urlunsplit

VERSION = 'v1'
_LOCK = threading.Lock()
_GENERATED = re.compile(r'(?:ai_img|leonardo|gemini|assessment)_[a-fA-F0-9]{8,32}\.(?:png|jpe?g|webp)', re.I)
_IMG = re.compile(r'<img\b[^>]*\bsrc=(["\'])([^"\']+)\1[^>]*>', re.I)

def generated_filename(name):
    return bool(_GENERATED.fullmatch(name or ''))

def display_image(original):
    """Return a cached smaller WebP, or the original on any unsafe/failed case."""
    original = Path(original)
    if not generated_filename(original.name) or not original.is_file():
        return original
    try:
        stat = original.stat()
        if stat.st_size < 120_000:
            return original
        key = hashlib.sha256(f'{VERSION}:{original.resolve()}:{stat.st_size}:{stat.st_mtime_ns}'.encode()).hexdigest()[:24]
        cached = Path(tempfile.gettempdir()) / 'scormify-astryx-display' / (key + '.webp')
        with _LOCK:
            if cached.is_file():
                return cached
            if cached.with_suffix('.original').is_file():
                return original
            from PIL import Image, ImageOps
            with Image.open(original) as source:
                if getattr(source, 'is_animated', False) or source.width * source.height > 16_000_000:
                    return original
                image = ImageOps.exif_transpose(source)
                image = image.convert('RGBA' if 'A' in image.getbands() or 'transparency' in image.info else 'RGB')
                image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
                output = io.BytesIO()
                image.save(output, 'WEBP', quality=90, method=4)
            raw = output.getvalue()
            if len(raw) >= stat.st_size * .9:
                cached.parent.mkdir(exist_ok=True)
                cached.with_suffix('.original').touch()
                return original
            cached.parent.mkdir(exist_ok=True)
            temporary = cached.with_suffix('.tmp')
            temporary.write_bytes(raw)
            temporary.replace(cached)
            return cached
    except Exception:
        # Unsupported/corrupt files and unavailable codecs must still load.
        return original

def prepare_astryx_images(document, assets_dir=None):
    """Query-based Editor display, or optimized offline payload when assets exist.

    Only explicit generated illustration URLs in controlled Astryx lessons qualify.
    Screenshots, logos, quizzes, arbitrary URLs and scripts remain untouched.
    """
    if not isinstance(document, str) or not re.search(r'data-astryx-lesson=["\']', document):
        return document
    def replace(match):
        tag, url = match[0], html.unescape(match[2])
        parts = urlsplit(url)
        asset = re.fullmatch(r'/api/projects/([A-Za-z0-9_-]+)/assets/([^/]+)', parts.path)
        if not asset or not generated_filename(asset[2]):
            return tag
        source = None
        if assets_dir:
            root = Path(assets_dir)
            source = root / asset[2]
            if not source.is_file():
                source = root.parent.parent / asset[1] / 'assets' / asset[2]
        if source and source.is_file():
            optimized = display_image(source)
            # Keep the existing exporter fallback when compression is not useful.
            if optimized != source:
                from services.export_media_stream import CURRENT
                payload = CURRENT.get().file(optimized).split(';base64,', 1)[1] if CURRENT.get() else base64.b64encode(optimized.read_bytes()).decode('ascii')
                url = 'data:image/webp;base64,' + payload
            else:
                url = urlunsplit((parts.scheme, parts.netloc, parts.path, '', parts.fragment))
        elif assets_dir:
            url = urlunsplit((parts.scheme, parts.netloc, parts.path, '', parts.fragment))
        else:
            query = dict(parse_qsl(parts.query)); query['astryx_image'] = VERSION
            url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
        tag = tag.replace(match[2], html.escape(url, quote=True), 1)
        if not re.search(r'\bdecoding=', tag):
            tag = tag.replace('<img', '<img decoding="async"', 1)
        return tag
    return _IMG.sub(replace, document)
