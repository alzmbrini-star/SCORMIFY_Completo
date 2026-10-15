"""Rewrite media inside assessment snapshots, not generated HTML markup."""
import base64
import json
import mimetypes
import os
import re
from pathlib import Path
from urllib.parse import urlsplit


def inline_assessment_assets(document: str, assets_dir: str) -> str:
    pattern = re.compile(r'(<script\b[^>]*\bid="assessment-data"[^>]*>)([\s\S]*?)(</script>)', re.I)

    def replace(match):
        data = json.loads(match.group(2))
        cache = {}

        def visit(value):
            if isinstance(value, list):
                return [visit(item) for item in value]
            if not isinstance(value, dict):
                return value
            result = {key: visit(item) for key, item in value.items()}
            url = result.get('url')
            if not isinstance(url, str):
                return result
            path = urlsplit(url).path
            asset = re.fullmatch(r'/api/projects/([A-Za-z0-9_-]+)/assets/([A-Za-z0-9_.-]+)', path)
            if not asset or '..' in asset.group(2):
                return result
            if path not in cache:
                project_id, filename = asset.groups()
                local = Path(assets_dir) / filename
                if not local.is_file():
                    from services.asset_store import retrieve_asset_sync
                    mongo = os.environ.get('MONGO_URL')
                    database = os.environ.get('DB_NAME')
                    if mongo and database:
                        retrieve_asset_sync(mongo, database, project_id, filename, str(local))
                if not local.is_file():
                    raise ValueError(f'O anexo da avaliação não está disponível: {filename}. Reenvie o arquivo antes de exportar.')
                mime = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
                cache[path] = f'data:{mime};base64,' + base64.b64encode(local.read_bytes()).decode('ascii')
            result['url'] = cache[path]
            return result

        encoded = json.dumps(visit(data), ensure_ascii=False).replace('<', '\\u003c')
        return match.group(1) + encoded + match.group(3)

    return pattern.sub(replace, document)
