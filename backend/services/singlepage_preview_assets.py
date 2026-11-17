"""Lossless, snapshot-only preview media. Full exports still embed their media."""
import base64
import hashlib
import re
from pathlib import Path

IMAGE=re.compile(r'data:(image/(?:png|jpeg|jpg|gif|webp|avif|bmp|svg\+xml));base64,([A-Za-z0-9+/=]+)',re.I)
EXT={'png':'png','jpeg':'jpg','jpg':'jpg','gif':'gif','webp':'webp','avif':'avif','bmp':'bmp','svg+xml':'svg'}

def prepare_preview_assets(snapshot,assets_dir,base_url):
    """Replace image payloads with local URLs in an already detached snapshot.

    Do not recompress, persist the course, or fetch external media. Files are
    ordinary temporary project assets, served by the existing media endpoint.
    """
    directory=Path(assets_dir);directory.mkdir(parents=True,exist_ok=True)
    prefix=base_url.rstrip('/')+'/api/projects/'+snapshot['id']+'/assets/'
    def replace(match):
        try:raw=base64.b64decode(match[2],validate=True)
        except (ValueError,base64.binascii.Error):return match[0]
        if not raw:return match[0]
        name='preview-image-'+hashlib.sha256(raw).hexdigest()+'.'+EXT[match[1].lower().split('/')[1]]
        target=directory/name
        if not target.is_file():target.write_bytes(raw)
        return prefix+name
    def visit(value):
        if isinstance(value,dict):
            for key,item in value.items():value[key]=visit(item)
        elif isinstance(value,list):
            for index,item in enumerate(value):value[index]=visit(item)
        elif isinstance(value,str):
            if value.startswith('__B64__:'):
                try:
                    raw=base64.b64decode(value[8:],validate=True).decode('utf-8');updated=IMAGE.sub(replace,raw)
                    return '__B64__:'+base64.b64encode(updated.encode()).decode() if updated!=raw else value
                except (ValueError,UnicodeError):return value
            return IMAGE.sub(replace,value) if 'data:image/' in value else value
        return value
    return visit(snapshot)
