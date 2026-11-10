"""SCORM-only visual startup and lossless media externalization."""
import base64
import hashlib
import re
from pathlib import Path


def install_initial_loader(html):
    script = (Path(__file__).parent / 'export_assets/initial-loader.js').read_text(encoding='utf-8')
    pattern = re.compile(r'<script\b[^>]*>(.*?)</script\s*>', re.I | re.S)
    for match in pattern.finditer(html):
        if "document.getElementById('scormify-loader')" in match.group(1):
            return html[:match.start()] + '<script id="scormify-initial-loader-v2">\n' + script + '\n</script>' + html[match.end():]
    raise ValueError('Initial SCORM loader block not found; refusing to silently export the old loader.')


def externalize_scorm_images(course, assets_dir):
    """Keep exact raster bytes, deduplicate and rewrite the export snapshot only.

    HTML/SVG snippets stay untouched. srcdoc relative image URLs resolve against
    the parent package URL. No recompression, learning-rule changes or database writes.
    """
    assets_dir = Path(assets_dir)
    assets_dir.mkdir(parents=True, exist_ok=True)
    extensions = {'image/png': '.png', 'image/jpeg': '.jpg', 'image/jpg': '.jpg',
                  'image/gif': '.gif', 'image/webp': '.webp', 'image/avif': '.avif', 'image/bmp': '.bmp'}
    known = {}
    for path in assets_dir.iterdir():
        if path.is_file() and path.suffix.lower() in extensions.values():
            digest = hashlib.sha256()
            with path.open('rb') as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b''): digest.update(chunk)
            known[digest.hexdigest()] = path.name
    stats = {'references': 0, 'newFiles': 0, 'removedDataChars': 0}
    def image(value):
        match = re.match(r'^data:(image/(?:png|jpeg|jpg|gif|webp|avif|bmp));base64,', value, re.I)
        if not match or len(value) > 44 * 1024 * 1024:
            return value
        try:
            raw = base64.b64decode(value[match.end():], validate=True)
        except (ValueError, base64.binascii.Error):
            return value
        if not raw: return value
        digest = hashlib.sha256(raw).hexdigest()
        name = known.get(digest)
        if name is None:
            name = 'scorm-image-' + digest + extensions[match.group(1).lower()]
            (assets_dir / name).write_bytes(raw)
            known[digest] = name
            stats['newFiles'] += 1
        stats['references'] += 1
        stats['removedDataChars'] += len(value)
        return 'assets/' + name
    def visit(value):
        if isinstance(value, dict):
            for key, item in value.items(): value[key] = visit(item)
        elif isinstance(value, list):
            for index, item in enumerate(value): value[index] = visit(item)
        elif isinstance(value, str) and value.startswith('data:image/'):
            return image(value)
        return value
    visit(course)
    return stats
