"""Map only explicit scenario image fields; never rewrite narrative or choices."""
import copy
import re
from pathlib import Path

def resolve_scenario_image(url, assets_dir, base_url=''):
    """Reuse existing project-asset restore logic, including library images."""
    match = re.search(r'/api/projects/([A-Za-z0-9_-]+)/assets/([A-Za-z0-9_.-]+)$', url)
    if match and '..' not in match.group(2):
        from services.scorm_exporter import _read_image_as_data_uri
        source_dir = Path(assets_dir).parent.parent / match.group(1) / 'assets'
        folder = source_dir if (source_dir / match.group(2)).is_file() else Path(assets_dir)
        embedded = _read_image_as_data_uri(match.group(1), match.group(2), folder)
        if embedded:
            return embedded
    from services.single_page_exporter import _resolve_asset_url
    return _resolve_asset_url(url, '', str(assets_dir), base_url)

def map_scenario_images(data, resolve):
    result = copy.deepcopy(data or {})
    for obj in [result, result.get('config') or {}, *(result.get('nodes') or [])]:
        for field in ('imageUrl', 'scene_image', 'background_image'):
            if isinstance(obj.get(field), str) and obj[field]:
                obj[field] = resolve(obj[field])
    return result
