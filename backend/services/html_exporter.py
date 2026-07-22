"""
HTML Standalone Exporter Service
Generates a single self-contained HTML file with all assets embedded
"""
import os
import json
import base64
import logging
import re
import httpx
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
import mimetypes

from models import Course, Project

logger = logging.getLogger(__name__)


class DateTimeEncoder(json.JSONEncoder):
    """JSON Encoder that handles datetime objects"""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


def get_mime_type(file_path: str) -> str:
    """Get MIME type from file extension"""
    mime_type, _ = mimetypes.guess_type(file_path)
    return mime_type or 'application/octet-stream'


def file_to_base64(file_path: str) -> Optional[str]:
    """Convert a file to base64 data URI"""
    try:
        if not os.path.exists(file_path):
            logger.warning(f"File not found: {file_path}")
            return None
        
        mime_type = get_mime_type(file_path)
        with open(file_path, 'rb') as f:
            data = base64.b64encode(f.read()).decode('utf-8')
        return f"data:{mime_type};base64,{data}"
    except Exception as e:
        logger.error(f"Error converting file to base64: {e}")
        return None


# Storage dir of Whiteboard renderer outputs (wb_*.mp4 / wb_*.png).
# Resolved relative to this file: backend/services/ → backend/storage/whiteboard
_WHITEBOARD_STORAGE_DIR = Path(__file__).parent.parent / "storage" / "whiteboard"


def _resolve_whiteboard_asset(src: str) -> Optional[str]:
    """If `src` is a Whiteboard renderer URL (`/api/whiteboard/file/wb_*`),
    return the inlined base64 data URI by reading from the local
    whiteboard storage dir. Returns None for non-whiteboard URLs or when
    the file isn't found.

    Used by the HTML exporters so transparent APNG / MP4 outputs from the
    Hand-Writer feature don't break in offline (self-contained) HTML.
    """
    if not src or not isinstance(src, str) or "/api/whiteboard/file/" not in src:
        return None
    name = src.split("/api/whiteboard/file/")[-1].split("?")[0].split("/")[0]
    if not name:
        return None
    path = _WHITEBOARD_STORAGE_DIR / name
    if not path.exists():
        logger.warning(f"Whiteboard asset not found in storage: {path}")
        return None
    return file_to_base64(str(path))


async def url_to_base64(url: str) -> Optional[str]:
    """Download a URL and convert to base64 data URI"""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(url)
            if response.status_code == 200:
                content_type = response.headers.get('content-type', 'application/octet-stream')
                # Remove charset and other parameters from content type
                content_type = content_type.split(';')[0].strip()
                data = base64.b64encode(response.content).decode('utf-8')
                return f"data:{content_type};base64,{data}"
    except Exception as e:
        logger.error(f"Error downloading URL {url}: {e}")
    return None


async def process_html_content_images(
    html_content: str,
    assets_dir: str,
    base_url: str
) -> str:
    """
    Process images within HTML content (like Rich Text Editor content).
    Finds all <img> tags and converts their src to base64 data URIs.
    This ensures AI-generated images and other assets are embedded in the export.
    """
    if not html_content:
        return html_content
    
    # Sanitize: remove Tailwind CSS variables and editor artifacts
    html_content = re.sub(r'--tw-[^;:]+:[^;]*;?\s*', '', html_content)
    html_content = re.sub(r'outline-style:\s*dashed\s*;?\s*', '', html_content)
    html_content = re.sub(r'outline-width:\s*[^;]+;?\s*', '', html_content)
    html_content = re.sub(r'style="\s*;?\s*"', '', html_content)
    html_content = re.sub(r"style='\s*;?\s*'", '', html_content)
    
    # Find all img tags with src attribute
    img_pattern = re.compile(r'<img\s+[^>]*src=["\']([^"\']+)["\'][^>]*>', re.IGNORECASE)
    
    async def replace_img_src(match):
        full_tag = match.group(0)
        src = match.group(1)
        
        # Skip if already a data URI
        if src.startswith('data:'):
            return full_tag
        
        base64_src = None
        
        # Extract filename from URL if it contains /api/assets/ pattern
        # This handles both local (/api/assets/...) and external (https://old-domain.com/api/assets/...) URLs
        asset_filename = None
        if '/api/assets/' in src:
            asset_filename = src.split('/api/assets/')[-1].split('?')[0]  # Remove query params
        
        # If we found an asset filename, try to find it locally first
        if asset_filename:
            # AI images are stored in storage/assets/
            project_dir = os.path.dirname(assets_dir)  # /storage/projects/{id}
            projects_dir = os.path.dirname(project_dir)  # /storage/projects
            storage_dir = os.path.dirname(projects_dir)  # /storage
            storage_assets_path = os.path.join(storage_dir, 'assets', asset_filename)
            if os.path.exists(storage_assets_path):
                base64_src = file_to_base64(storage_assets_path)
                logger.info(f"Embedded AI image from local storage: {asset_filename}")
            else:
                # Try MongoDB global assets (production - disk is ephemeral)
                try:
                    from pymongo import MongoClient as SyncMongoClient
                    mongo_url = os.environ.get('MONGO_URL', '')
                    db_name = os.environ.get('DB_NAME', '')
                    if mongo_url and db_name:
                        _client = SyncMongoClient(mongo_url, serverSelectionTimeoutMS=30000, connectTimeoutMS=30000)
                        _db = _client[db_name]
                        doc = _db.project_assets.find_one(
                            {"project_id": "global", "filename": asset_filename},
                            {"_id": 0, "data": 1}
                        )
                        _client.close()
                        if doc and doc.get("data"):
                            # Restore to disk
                            os.makedirs(os.path.dirname(storage_assets_path), exist_ok=True)
                            with open(storage_assets_path, 'wb') as f:
                                f.write(doc["data"])
                            base64_src = file_to_base64(storage_assets_path)
                            logger.info(f"Restored AI image from MongoDB global: {asset_filename}")
                except Exception as e:
                    logger.warning(f"MongoDB global lookup failed for {asset_filename}: {e}")
                
                if not base64_src:
                    # Try with current base_url as last fallback
                    if src.startswith('/api/assets/'):
                        full_url = f"{base_url}{src}"
                        base64_src = await url_to_base64(full_url)
                        if base64_src:
                            logger.info(f"Downloaded AI image from current server: {asset_filename}")
        
        # Handle project assets (local paths)
        elif src.startswith('/api/projects/'):
            asset_filename = src.split('/')[-1]
            local_path = os.path.join(assets_dir, asset_filename)
            if os.path.exists(local_path):
                base64_src = file_to_base64(local_path)
                logger.info(f"Embedded project asset: {asset_filename}")
            else:
                # Try source project's assets directory (gallery images from other projects)
                import re as _re
                pid_match = _re.search(r'/api/projects/([^/]+)/assets/', src)
                if pid_match:
                    source_pid = pid_match.group(1)
                    source_dir = os.path.join(os.path.dirname(assets_dir), '..', source_pid, 'assets')
                    source_path = os.path.join(source_dir, asset_filename)
                    if os.path.exists(source_path):
                        base64_src = file_to_base64(source_path)
                        logger.info(f"Embedded gallery image from source project {source_pid}: {asset_filename}")
                if not base64_src:
                    full_url = f"{base_url}{src}"
                    base64_src = await url_to_base64(full_url)
        
        # Handle other external URLs (not /api/assets/)
        elif src.startswith('http'):
            base64_src = await url_to_base64(src)
            if base64_src:
                logger.info(f"Downloaded and embedded external image: {src[:50]}...")
        
        # Handle relative paths
        elif not src.startswith('/'):
            local_path = os.path.join(assets_dir, src)
            if os.path.exists(local_path):
                base64_src = file_to_base64(local_path)
        
        if base64_src:
            # Replace the src attribute with base64 data URI
            new_tag = full_tag.replace(f'src="{src}"', f'src="{base64_src}"')
            new_tag = new_tag.replace(f"src='{src}'", f"src='{base64_src}'")
            return new_tag
        
        logger.warning(f"Could not embed image: {src}")
        return full_tag
    
    # Process all images
    matches = list(img_pattern.finditer(html_content))
    if not matches:
        return html_content
    
    # Process matches in reverse order to maintain positions
    result = html_content
    for match in reversed(matches):
        replacement = await replace_img_src(match)
        result = result[:match.start()] + replacement + result[match.end():]
    
    logger.info(f"Processed {len(matches)} images in HTML content")
    return result


def _generate_tutor_block(tutor_config: dict = None) -> str:
    """Generate the AI Tutor chat widget HTML/CSS/JS for standalone HTML export"""
    if not tutor_config or not tutor_config.get('enabled'):
        return ''
    
    # Read tutor.css and tutor.js from export_assets
    export_assets_dir = Path(__file__).parent / "export_assets"
    
    tutor_css = ''
    tutor_js = ''
    try:
        with open(export_assets_dir / "tutor.css", 'r') as f:
            tutor_css = f.read()
    except Exception as e:
        logger.warning(f"Could not read tutor.css: {e}")
    
    try:
        with open(export_assets_dir / "tutor.js", 'r') as f:
            tutor_js = f.read()
    except Exception as e:
        logger.warning(f"Could not read tutor.js: {e}")
    
    if not tutor_js:
        return ''
    
    tutor_config_json = json.dumps({**tutor_config, 'cssInlined': True}, ensure_ascii=False)
    
    return f'''
    <style>{tutor_css}</style>
    <script>{tutor_js}</script>
    <script>
        document.addEventListener('DOMContentLoaded', function() {{
            // Skip Tutor on file:// protocol (needs API backend)
            if (window.location.protocol === 'file:') return;
            if (typeof AiTutor !== 'undefined') {{
                var tutorConfig = {tutor_config_json};
                AiTutor.init(tutorConfig);
            }}
        }});
    </script>'''



async def generate_standalone_html(
    project: Dict[str, Any],
    assets_dir: str,
    base_url: str = "",
    questions: list = None,
    backend_url: str = "",
    tutor_config: dict = None
) -> str:
    """
    Generate a standalone HTML file with all assets embedded as base64
    
    Args:
        project: The project dictionary containing course data
        assets_dir: Directory where project assets are stored
        base_url: Base URL for external assets
        questions: Optional list of quiz questions to include
        
    Returns:
        Complete HTML string
    """
    course = project.get('course', {})
    metadata = course.get('metadata', {})
    slides = course.get('slides', [])
    global_audio = course.get('globalAudio')
    
    title = metadata.get('title', project.get('name', 'Course'))
    
    # VLibras accessibility setting
    enable_vlibras = project.get('enableVlibras', True)
    backend_url = backend_url
    if enable_vlibras:
        proxy_base = backend_url.rstrip('/') + '/api/vlibras-proxy' if backend_url else ''
        vlibras_block = f'''<!-- VLibras - Acessibilidade em LIBRAS -->
    <script>
        (function() {{
            // Skip VLibras on file:// protocol (local HTML exports)
            if (window.location.protocol === 'file:') return;
            var PROXY_BASE = "{proxy_base}";
            if (!PROXY_BASE) return;
            var _domainMap = {{
                "dicionario2.vlibras.gov.br": PROXY_BASE + "/dicionario2",
                "traducao2.vlibras.gov.br": PROXY_BASE + "/traducao2"
            }};
            var _origOpen = XMLHttpRequest.prototype.open;
            XMLHttpRequest.prototype.open = function(method, url) {{
                if (typeof url === "string") {{
                    for (var domain in _domainMap) {{
                        if (url.indexOf(domain) !== -1) {{
                            try {{
                                var u = new URL(url);
                                arguments[1] = _domainMap[domain] + u.pathname + u.search;
                                console.log("[VLibras Proxy] " + method + " " + domain + u.pathname + " -> proxy");
                            }} catch(e) {{}}
                            break;
                        }}
                    }}
                }}
                return _origOpen.apply(this, arguments);
            }};
            // Dynamically load VLibras script
            var s = document.createElement('script');
            s.src = 'https://vlibras.gov.br/app/vlibras-plugin.js';
            s.onload = function() {{
                try {{
                    new window.VLibras.Widget({{ position: "R", avatar: "random" }});
                }} catch(e) {{ console.warn('[VLibras] Init failed:', e); }}
            }};
            document.body.appendChild(s);
        }})();
    </script>
    <div vw class="enabled">
        <div vw-access-button class="active"></div>
        <div vw-plugin-wrapper>
            <div class="vw-plugin-top-wrapper"></div>
        </div>
    </div>'''
    else:
        vlibras_block = ''
    
    # Get first slide dimensions as default
    default_width = 1536
    default_height = 864
    if slides:
        default_width = slides[0].get('width', 1536)
        default_height = slides[0].get('height', 864)
    
    # Process all assets and convert to base64
    processed_slides = []
    for slide in slides:
        processed_slide = slide.copy()

        # Embed whiteboard slide-level videoUrl (legacy/leftover from
        # opaque MP4 renders). Without this the raw `/api/whiteboard/file/`
        # URL leaks into the offline HTML JSON and breaks if the player
        # ever consumes `slide.videoUrl`.
        if isinstance(slide.get('videoUrl'), str) and '/api/whiteboard/file/' in slide['videoUrl']:
            wb_b64 = _resolve_whiteboard_asset(slide['videoUrl'])
            if wb_b64:
                processed_slide['videoUrl'] = wb_b64

        # Process background image
        if slide.get('backgroundImage'):
            bg_path = slide['backgroundImage']
            if bg_path.startswith('data:'):
                processed_slide['backgroundImage'] = bg_path
            elif bg_path.startswith('/api/') or bg_path.startswith('assets/'):
                # Local asset
                asset_filename = bg_path.split('/')[-1]
                local_path = os.path.join(assets_dir, asset_filename)
                if os.path.exists(local_path):
                    processed_slide['backgroundImage'] = file_to_base64(local_path)
                else:
                    # Try MongoDB fallback first
                    mongo_restored = False
                    try:
                        from services.asset_store import retrieve_asset_sync
                        mongo_url = os.environ.get('MONGO_URL')
                        db_name = os.environ.get('DB_NAME')
                        project_id = project.get('id', '')
                        if mongo_url and db_name and project_id:
                            os.makedirs(os.path.dirname(local_path), exist_ok=True)
                            if retrieve_asset_sync(mongo_url, db_name, project_id, asset_filename, local_path):
                                processed_slide['backgroundImage'] = file_to_base64(local_path)
                                mongo_restored = True
                                logger.info(f"HTML export: restored backgroundImage from MongoDB: {asset_filename}")
                    except Exception as e:
                        logger.warning(f"HTML export MongoDB fallback failed: {e}")
                    if not mongo_restored:
                        # Try with full URL
                        full_url = f"{base_url}{bg_path}" if not bg_path.startswith('http') else bg_path
                        processed_slide['backgroundImage'] = await url_to_base64(full_url)
            elif bg_path.startswith('http'):
                processed_slide['backgroundImage'] = await url_to_base64(bg_path)
        
        # Process elements
        processed_elements = []
        for element in slide.get('elements', []):
            processed_element = element.copy()
            
            # Process image elements
            if element.get('type') == 'image' and element.get('src'):
                src = element['src']
                if src.startswith('data:'):
                    processed_element['src'] = src
                elif '/api/whiteboard/file/' in src:
                    # Whiteboard renderer output (APNG transparente sai como
                    # type=image). Lê do storage dedicado e embute como data URI.
                    wb_b64 = _resolve_whiteboard_asset(src)
                    processed_element['src'] = wb_b64 if wb_b64 else src
                elif src.startswith('/api/') or src.startswith('assets/'):
                    asset_filename = src.split('/')[-1]
                    local_path = os.path.join(assets_dir, asset_filename)
                    
                    # Extract source project ID from gallery image URLs
                    source_project_id = project.get('id', '')
                    if '/api/projects/' in src:
                        import re as _re
                        pid_match = _re.search(r'/api/projects/([^/]+)/assets/', src)
                        if pid_match:
                            source_project_id = pid_match.group(1)
                    
                    if os.path.exists(local_path):
                        processed_element['src'] = file_to_base64(local_path)
                    else:
                        # Try source project's assets directory (for gallery images from other projects)
                        source_local_path = None
                        if source_project_id != project.get('id', ''):
                            source_assets_dir = os.path.join(os.path.dirname(assets_dir), '..', source_project_id, 'assets')
                            source_local_path = os.path.join(source_assets_dir, asset_filename)
                            if os.path.exists(source_local_path):
                                processed_element['src'] = file_to_base64(source_local_path)
                        
                        if not processed_element.get('src') or processed_element['src'] == src:
                            # Try MongoDB fallback
                            mongo_restored = False
                            try:
                                from services.asset_store import retrieve_asset_sync
                                mongo_url = os.environ.get('MONGO_URL')
                                db_name = os.environ.get('DB_NAME')
                                lookup_project_id = source_project_id or project.get('id', '')
                                if mongo_url and db_name and lookup_project_id:
                                    os.makedirs(os.path.dirname(local_path), exist_ok=True)
                                    if retrieve_asset_sync(mongo_url, db_name, lookup_project_id, asset_filename, local_path):
                                        processed_element['src'] = file_to_base64(local_path)
                                        mongo_restored = True
                            except Exception:
                                pass
                            if not mongo_restored:
                                full_url = f"{base_url}{src}" if not src.startswith('http') else src
                                processed_element['src'] = await url_to_base64(full_url)
                elif src.startswith('http'):
                    processed_element['src'] = await url_to_base64(src)
            
            # Process video elements (local videos)
            if element.get('type') == 'video' and element.get('src'):
                src = element['src']
                if '/api/whiteboard/file/' in src:
                    # Whiteboard renderer MP4 — embed from dedicated storage.
                    wb_b64 = _resolve_whiteboard_asset(src)
                    if wb_b64:
                        processed_element['src'] = wb_b64
                elif not src.startswith('http') and not element.get('embedUrl'):
                    if src.startswith('/api/') or src.startswith('assets/'):
                        asset_filename = src.split('/')[-1]
                        local_path = os.path.join(assets_dir, asset_filename)
                        if os.path.exists(local_path):
                            processed_element['src'] = file_to_base64(local_path)
            
            # Process HTML elements (Rich Text Editor content with embedded images)
            if element.get('type') == 'html' and element.get('htmlContent'):
                # Process any images inside the HTML content (including AI-generated images)
                processed_element['htmlContent'] = await process_html_content_images(
                    element['htmlContent'],
                    assets_dir,
                    base_url
                )
                logger.info("Processed HTML element content for embedded images")
            
            # Process flipbook/PDF elements - embed local PDF as data URI so
            # the standalone HTML works offline (runtime converts to blob URL)
            if element.get('type') == 'flipbook':
                if element.get('flipbookUrl'):
                    fb = element['flipbookUrl']
                    if isinstance(fb, str) and not fb.startswith(('http', 'data:')) and '/assets/' in fb:
                        fb_name = fb.split('/assets/')[-1].split('?')[0].split('/')[-1]
                        fb_local = os.path.join(assets_dir, fb_name)
                        fb_b64 = file_to_base64(fb_local) if os.path.exists(fb_local) else None
                        if not fb_b64 and base_url:
                            fb_b64 = await url_to_base64(f"{base_url.rstrip('/')}{fb}")
                        if fb_b64:
                            processed_element['flipbookUrl'] = fb_b64
                            logger.info(f"Embedded flipbook asset as data URI: {fb_name}")
                # Embed PDF page images / flipbook page images as data URIs
                for _list_key in ('pdfPages', 'flipbookPages'):
                    _lst = element.get(_list_key)
                    if isinstance(_lst, list) and _lst:
                        _new = []
                        for _u in _lst:
                            if isinstance(_u, str) and not _u.startswith(('http', 'data:')) and '/assets/' in _u:
                                _nm = _u.split('/assets/')[-1].split('?')[0].split('/')[-1]
                                _lp = os.path.join(assets_dir, _nm)
                                _b64 = file_to_base64(_lp) if os.path.exists(_lp) else None
                                if not _b64 and base_url:
                                    _b64 = await url_to_base64(f"{base_url.rstrip('/')}{_u}")
                                _new.append(_b64 or _u)
                            else:
                                _new.append(_u)
                        processed_element[_list_key] = _new

            processed_elements.append(processed_element)
        
        processed_slide['elements'] = processed_elements
        
        # Process slide audio
        processed_audios = []
        for audio in slide.get('audio', []):
            processed_audio = audio.copy()
            # Normalize: use 'src' or 'url' field
            src = audio.get('src') or audio.get('url') or ''
            if src:
                if '/api/audio/' in src:
                    # Narration audio from agent - read from local storage
                    audio_filename = src.split('/api/audio/')[-1].split('?')[0]
                    audio_storage = os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage", "audio", audio_filename)
                    if os.path.exists(audio_storage):
                        processed_audio['src'] = file_to_base64(audio_storage)
                    else:
                        full_url = f"{base_url}{src}" if not src.startswith('http') else src
                        b64 = await url_to_base64(full_url)
                        if b64:
                            processed_audio['src'] = b64
                elif src.startswith('/api/') or src.startswith('assets/'):
                    asset_filename = src.split('/')[-1]
                    local_path = os.path.join(assets_dir, asset_filename)
                    if os.path.exists(local_path):
                        processed_audio['src'] = file_to_base64(local_path)
                    else:
                        full_url = f"{base_url}{src}" if not src.startswith('http') else src
                        b64 = await url_to_base64(full_url)
                        if b64:
                            processed_audio['src'] = b64
                elif src.startswith('http'):
                    b64 = await url_to_base64(src)
                    if b64:
                        processed_audio['src'] = b64
            processed_audios.append(processed_audio)
        processed_slide['audio'] = processed_audios
        
        processed_slides.append(processed_slide)
    
    # Process global audio
    processed_global_audio = None
    ga_src = ''
    if global_audio:
        ga_src = global_audio.get('src') or global_audio.get('url') or ''
    if global_audio and ga_src:
        processed_global_audio = global_audio.copy()
        src = ga_src
        if src.startswith('/api/') or src.startswith('assets/'):
            asset_filename = src.split('/')[-1]
            local_path = os.path.join(assets_dir, asset_filename)
            if os.path.exists(local_path):
                processed_global_audio['src'] = file_to_base64(local_path)
            else:
                # Try downloading from full URL
                full_url = f"{base_url}{src}" if not src.startswith('http') else src
                b64 = await url_to_base64(full_url)
                if b64:
                    processed_global_audio['src'] = b64
        elif src.startswith('http'):
            b64 = await url_to_base64(src)
            if b64:
                processed_global_audio['src'] = b64
    
    # Build course JSON
    course_data = {
        "metadata": metadata,
        "slides": processed_slides,
        "globalAudio": processed_global_audio
    }
    
    # Resolve the branded loading overlay (title + accent color) from
    # the project's brand kit + course metadata. Stored under a private
    # `_loader` key on course_data so it survives the trip through
    # `generate_html_template` without changing the function signature.
    # Stripped from the JS payload right before serialisation.
    try:
        from services.loader_config import resolve_loader_config
        course_data["_loader"] = resolve_loader_config(project)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"resolve_loader_config failed (non-fatal): {exc}")
    
    # Add questions for quiz support
    if questions:
        course_data["questions"] = questions
        logger.info(f"Added {len(questions)} questions to HTML export")
    
    # Generate HTML
    html = generate_html_template(title, course_data, default_width, default_height, enable_vlibras, tutor_config=tutor_config)
    
    return html


def generate_html_template(title: str, course_data: Dict, width: int, height: int, enable_vlibras: bool = True, backend_url: str = "", tutor_config: dict = None) -> str:
    """Generate the complete HTML template with embedded player"""
    
    # VLibras block for accessibility (LIBRAS - Brazilian Sign Language)
    if enable_vlibras:
        proxy_base = backend_url.rstrip('/') + '/api/vlibras-proxy' if backend_url else ''
        vlibras_block = f'''<!-- VLibras - Acessibilidade em LIBRAS -->
    <script>
        (function() {{
            // Skip VLibras on file:// protocol (local HTML exports)
            if (window.location.protocol === 'file:') return;
            var PROXY_BASE = "{proxy_base}";
            if (!PROXY_BASE) return;
            var _domainMap = {{
                "dicionario2.vlibras.gov.br": PROXY_BASE + "/dicionario2",
                "traducao2.vlibras.gov.br": PROXY_BASE + "/traducao2"
            }};
            var _origOpen = XMLHttpRequest.prototype.open;
            XMLHttpRequest.prototype.open = function(method, url) {{
                if (typeof url === "string") {{
                    for (var domain in _domainMap) {{
                        if (url.indexOf(domain) !== -1) {{
                            try {{
                                var u = new URL(url);
                                arguments[1] = _domainMap[domain] + u.pathname + u.search;
                                console.log("[VLibras Proxy] " + method + " " + domain + u.pathname + " -> proxy");
                            }} catch(e) {{}}
                            break;
                        }}
                    }}
                }}
                return _origOpen.apply(this, arguments);
            }};
            // Dynamically load VLibras script
            var s = document.createElement('script');
            s.src = 'https://vlibras.gov.br/app/vlibras-plugin.js';
            s.onload = function() {{
                try {{
                    new window.VLibras.Widget({{ position: "R", avatar: "random" }});
                }} catch(e) {{ console.warn('[VLibras] Init failed:', e); }}
            }};
            document.body.appendChild(s);
        }})();
    </script>
    <div vw class="enabled">
        <div vw-access-button class="active"></div>
        <div vw-plugin-wrapper>
            <div class="vw-plugin-top-wrapper"></div>
        </div>
    </div>'''
    else:
        vlibras_block = ''
    
    # Create a deep copy and sanitize htmlContent fields to prevent JSON/JS issues
    import copy
    sanitized_data = copy.deepcopy(course_data)
    
    # Pull the pre-resolved branded loader config from the course_data
    # envelope (set by `generate_standalone_html`). Fall back to neutral
    # defaults if the caller didn't populate it (e.g. legacy paths).
    from services.loader_config import (
        resolve_loader_config, DEFAULT_TITLE, DEFAULT_PRIMARY, DEFAULT_ACCENT,
    )
    _loader_cfg = course_data.get("_loader") or resolve_loader_config(
        {"course": {"metadata": course_data.get("metadata") or {}}}
    )
    loader_title = _loader_cfg.get("title_html") or DEFAULT_TITLE
    loader_primary = _loader_cfg.get("primary") or DEFAULT_PRIMARY
    loader_accent = _loader_cfg.get("accent") or DEFAULT_ACCENT
    # `_loader` is internal-only — strip it before serialising into the
    # JS bundle so the runtime payload stays clean.
    sanitized_data.pop("_loader", None)
    
    for slide in sanitized_data.get('slides', []):
        for element in slide.get('elements', []):
            # Sanitize htmlContent - encode as base64 to prevent issues
            if element.get('htmlContent'):
                # Convert the HTML content to base64 to avoid escaping issues
                html_b64 = base64.b64encode(element['htmlContent'].encode('utf-8')).decode('utf-8')
                element['htmlContent'] = f"__B64__:{html_b64}"
    
    # Escape special characters that could break the script tag
    # First dump to JSON, then escape </script> and other problematic sequences
    course_json = json.dumps(sanitized_data, ensure_ascii=False, cls=DateTimeEncoder)
    # Escape </script> to prevent breaking the script block
    course_json = course_json.replace('</script>', '<\\/script>')
    course_json = course_json.replace('</Script>', '<\\/Script>')
    course_json = course_json.replace('</SCRIPT>', '<\\/SCRIPT>')
    
    html = f'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Lato:wght@300;400;700&family=Merriweather:wght@300;400;700&family=Montserrat:wght@300;400;500;600;700&family=Nunito:wght@300;400;600;700&family=Open+Sans:wght@300;400;600;700&family=Oswald:wght@300;400;500;600;700&family=Playfair+Display:wght@400;500;600;700&family=Poppins:wght@300;400;500;600;700&family=PT+Sans:wght@400;700&family=Raleway:wght@300;400;500;600;700&family=Roboto:wght@300;400;500;700&family=Source+Sans+3:wght@300;400;600;700&family=Ubuntu:wght@300;400;500;700&family=Manrope:wght@400;600;700;800&family=Sora:wght@400;600;700&family=Fraunces:wght@400;600;700&family=Source+Serif+4:wght@400;600&family=Space+Grotesk:wght@400;600;700&family=IBM+Plex+Sans:wght@400;600&family=Archivo:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            min-height: 100vh;
            overflow: hidden;
        }}
        
        #player-container {{
            display: flex;
            flex-direction: column;
            height: 100vh;
            width: 100vw;
        }}
        
        #header {{
            height: 50px;
            background: rgba(0, 0, 0, 0.3);
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 20px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }}
        
        #header h1 {{
            color: #fff;
            font-size: 18px;
            font-weight: 500;
        }}
        
        #progress-info {{
            color: rgba(255, 255, 255, 0.7);
            font-size: 14px;
        }}
        
        #main-content {{
            display: flex;
            flex: 1;
            overflow: hidden;
        }}
        
        #sidebar {{
            width: 0;
            background: rgba(0, 0, 0, 0.3);
            border-right: 1px solid rgba(255, 255, 255, 0.1);
            overflow-y: auto;
            transition: width 0.3s ease;
        }}
        
        #sidebar.open {{
            width: 250px;
        }}
        
        .sidebar-item {{
            padding: 10px 15px;
            cursor: pointer;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            transition: background 0.2s;
        }}
        
        .sidebar-item:hover {{
            background: rgba(255, 255, 255, 0.1);
        }}
        
        .sidebar-item.active {{
            background: rgba(99, 102, 241, 0.3);
            border-left: 3px solid #6366f1;
        }}
        
        .sidebar-item-title {{
            color: #fff;
            font-size: 14px;
            margin-bottom: 4px;
        }}
        
        .sidebar-item-number {{
            color: rgba(255, 255, 255, 0.5);
            font-size: 12px;
        }}
        
        #slide-wrapper {{
            flex: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
            background: #0f0f1a;
            overflow: hidden;
        }}
        
        @media screen and (orientation: landscape) and (max-height: 500px) {{
            #slide-wrapper {{
                padding: 5px;
            }}
        }}
        
        /* AUTO FULLSCREEN on mobile landscape - only for actual mobile devices 
           Using max-height to ensure we're on a true mobile screen in landscape,
           not just a resized desktop window. Mobile landscape typically has height < 500px */
        @media screen and (orientation: landscape) and (max-height: 450px) and (max-width: 950px) {{
            #header {{
                display: none !important;
            }}
            #controls {{
                display: none !important;
            }}
            #sidebar {{
                display: none !important;
            }}
            #slide-wrapper {{
                padding: 5px !important;
                background: #000 !important;
            }}
            #mobile-float-controls {{
                display: flex !important;
            }}
        }}
        
        /* Also apply for touch devices with coarse pointer in landscape mode */
        @media screen and (orientation: landscape) and (max-width: 950px) and (pointer: coarse) {{
            #header {{
                display: none !important;
            }}
            #controls {{
                display: none !important;
            }}
            #sidebar {{
                display: none !important;
            }}
            #slide-wrapper {{
                padding: 5px !important;
                background: #000 !important;
            }}
            #mobile-float-controls {{
                display: flex !important;
            }}
        }}
        
        /* MOBILE PORTRAIT MODE - Full width slide */
        @media screen and (max-width: 1024px) and (orientation: portrait) {{
            html, body {{
                width: 100vw !important;
                max-width: 100vw !important;
                min-width: 100vw !important;
                overflow-x: hidden !important;
                margin: 0 !important;
                padding: 0 !important;
                box-sizing: border-box !important;
            }}
            
            #player-container {{
                width: 100vw !important;
                max-width: 100vw !important;
                min-width: 100vw !important;
                padding: 0 !important;
                margin: 0 !important;
                box-sizing: border-box !important;
            }}
            
            #slide-wrapper {{
                padding: 0 !important;
                margin: 0 !important;
                width: 100vw !important;
                max-width: 100vw !important;
                min-width: 100vw !important;
                align-items: flex-start !important;
                justify-content: flex-start !important;
                overflow-y: auto;
                overflow-x: hidden;
                -webkit-overflow-scrolling: touch;
                box-sizing: border-box !important;
            }}
            
            #slide-container {{
                box-shadow: none !important;
                margin: 0 !important;
                transform-origin: left top !important;
            }}
            
            #header {{
                display: none !important;
            }}
            
            #sidebar {{
                display: none !important;
            }}
            
            #controls {{
                display: none !important;
            }}
        }}
        
        /* Mobile floating controls - always available on mobile landscape */
        #mobile-float-controls {{
            display: none;
            position: fixed;
            bottom: 10px;
            left: 50%;
            transform: translateX(-50%);
            align-items: center;
            gap: 12px;
            background: rgba(0, 0, 0, 0.85);
            padding: 10px 20px;
            border-radius: 25px;
            z-index: 10001;
        }}
        
        #mobile-float-controls button {{
            background: rgba(255, 255, 255, 0.2);
            border: none;
            color: #fff;
            width: 48px;
            height: 48px;
            border-radius: 50%;
            font-size: 20px;
            cursor: pointer;
            touch-action: manipulation;
        }}
        
        #mobile-float-controls button:active {{
            background: rgba(255, 255, 255, 0.4);
        }}
        
        #mobile-float-controls .progress-text {{
            color: #fff;
            font-size: 14px;
            font-weight: 600;
            min-width: 50px;
            text-align: center;
        }}
        
        #slide-container {{
            width: {width}px;
            height: {height}px;
            background: #fff;
            position: relative;
            overflow: hidden;
            box-shadow: 0 10px 50px rgba(0, 0, 0, 0.5);
            transform-origin: 0 0;
        }}
        
        .slide-background {{
            position: absolute;
            inset: 0;
            width: 100%;
            height: 100%;
            object-fit: fill; /* Fill to match PPT slide proportions - same as SCORM */
        }}
        
        .slide-element {{
            position: absolute;
            transition: opacity 0.3s ease;
            overflow: hidden;
        }}
        
        .slide-element.text-element {{
            padding: 10px;
            overflow: hidden;
            background: transparent;
            border-radius: 0;
        }}
        
        .slide-element.shape-element {{
            display: flex;
            align-items: center;
            justify-content: center;
            background: transparent;
        }}
        
        .slide-element.animation_mask-element {{
            position: absolute;
            pointer-events: none;
            transition: opacity 0.5s ease;
        }}
        
        .slide-element.animation_clip-element {{
            position: absolute;
            pointer-events: none;
            overflow: hidden;
        }}
        
        .slide-element.animation_clip-element .animation-clip {{
            transition: opacity 0.5s ease, backdrop-filter 0.5s ease;
        }}
        
        .slide-element.animation_highlight-element {{
            position: absolute;
            pointer-events: none;
            box-sizing: border-box;
        }}
        
        .slide-element.image-element img {{
            width: 100%;
            height: 100%;
            /* object-fit is set inline per element */
        }}
        
        .slide-element.video-element {{
            background: transparent;
            border-radius: 0;
            overflow: hidden;
            position: relative;
        }}
        
        .slide-element.video-element .video-embed-container {{
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
        }}
        
        .slide-element.video-element video,
        .slide-element.video-element iframe {{
            width: 100%;
            height: 100%;
            border: 0;
            background: transparent;
        }}
        
        /* WebM videos with alpha channel transparency */
        .slide-element.video-element video {{
            /* object-fit is set inline per element */
            background-color: transparent !important;
        }}
        
        .slide-element.button-element {{
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        
        .slide-element.button-element a {{
            text-decoration: none;
            display: flex;
            align-items: center;
            justify-content: center;
            width: 100%;
            height: 100%;
        }}
        
        .slide-element.button-element button {{
            padding: 12px 24px;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
            border: none;
        }}
        
        .slide-element.button-element button:hover {{
            transform: scale(1.05);
        }}
        
        .button-primary {{
            background: linear-gradient(135deg, #7c3aed, #06b6d4);
            color: white;
        }}
        
        .button-secondary {{
            background: #4b5563;
            color: white;
        }}
        
        .button-outline {{
            background: transparent;
            border: 2px solid #7c3aed !important;
            color: #7c3aed;
        }}
        
        #controls {{
            height: 60px;
            background: #16213e;
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 20px;
            border-top: 1px solid #0f3460;
        }}
        
        @media screen and (max-width: 900px) {{
            #controls {{
                height: 50px;
                padding: 0 10px;
            }}
        }}
        
        .nav-buttons {{
            display: flex;
            gap: 10px;
            align-items: center;
        }}
        
        .control-btn {{
            background: #0f3460;
            border: none;
            color: #fff;
            padding: 10px 20px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            transition: background 0.2s, transform 0.1s;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        
        .control-btn:hover {{
            background: #1a4980;
        }}
        
        .control-btn:active {{
            transform: scale(0.98);
        }}
        
        .control-btn:disabled {{
            opacity: 0.5;
            cursor: not-allowed;
        }}
        
        .control-btn.icon-btn {{
            padding: 10px;
        }}
        
        @media screen and (max-width: 900px) {{
            .control-btn {{
                padding: 8px 12px;
                font-size: 12px;
            }}
        }}
        
        .progress-container {{
            flex: 1;
            display: flex;
            align-items: center;
            gap: 15px;
            margin: 0 20px;
        }}
        
        .progress-bar {{
            flex: 1;
            height: 6px;
            background: #0f3460;
            border-radius: 3px;
            cursor: pointer;
            position: relative;
        }}
        
        .progress-fill {{
            height: 100%;
            background: linear-gradient(90deg, #7c3aed, #06b6d4);
            border-radius: 3px;
            transition: width 0.3s ease;
        }}
        
        .progress-dots {{
            display: flex;
            gap: 6px;
            align-items: center;
        }}
        
        .progress-dot {{
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: rgba(255, 255, 255, 0.3);
            cursor: pointer;
            transition: background 0.2s, transform 0.2s;
        }}
        
        .progress-dot:hover {{
            background: rgba(255, 255, 255, 0.5);
        }}
        
        .progress-dot.active {{
            background: #06b6d4;
            transform: scale(1.2);
        }}
        
        .progress-dot.completed {{
            background: #10b981;
        }}
        
        .volume-control {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        
        .volume-slider {{
            width: 80px;
            height: 4px;
            -webkit-appearance: none;
            background: #0f3460;
            border-radius: 2px;
            outline: none;
        }}
        
        .volume-slider::-webkit-slider-thumb {{
            -webkit-appearance: none;
            width: 14px;
            height: 14px;
            background: #06b6d4;
            border-radius: 50%;
            cursor: pointer;
        }}
        
        /* SVG Annotations */
        .annotations-layer {{
            position: absolute;
            inset: 0;
            pointer-events: none;
            z-index: 100;
        }}
        
        /* Mobile orientation overlay */
        #orientation-overlay {{
            display: none;
            position: fixed;
            inset: 0;
            width: 100vw;
            height: 100vh;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            z-index: 99999;
            justify-content: center;
            align-items: center;
            flex-direction: column;
        }}
        
        /* Force display on mobile portrait mode - JS controlled, dismissable */
        @media screen and (orientation: portrait) and (max-width: 900px) {{
            /* JS controls overlay display */
        }}
        
        /* Also detect by aspect ratio for devices that don't report orientation correctly */
        @media screen and (max-aspect-ratio: 4/5) and (max-width: 900px) {{
            /* JS controls overlay display */
        }}
        
        /* Extra aggressive detection for very tall screens (phones in portrait) */
        @media screen and (max-aspect-ratio: 7/10) {{
            /* JS controls overlay display */
        }}
        
        /* Override for landscape - always hide overlay */
        @media screen and (orientation: landscape) {{
            #orientation-overlay {{
                display: none !important;
            }}
            #player-container {{
                display: flex !important;
            }}
        }}
        
        /* Override for wide screens - always hide overlay */
        @media screen and (min-aspect-ratio: 10/9) {{
            #orientation-overlay {{
                display: none !important;
            }}
            #player-container {{
                display: flex !important;
            }}
        }}
        
        .orientation-content {{
            text-align: center;
            padding: 30px;
            color: white;
            max-width: 90%;
        }}
        
        .orientation-icon {{
            font-size: 70px;
            margin-bottom: 10px;
            animation: shake 1.5s ease-in-out infinite;
        }}
        
        .orientation-arrow {{
            font-size: 50px;
            color: #7c3aed;
            margin-bottom: 15px;
            animation: rotate-hint 2s ease-in-out infinite;
        }}
        
        @keyframes rotate-hint {{
            0%, 100% {{ transform: rotate(0deg); }}
            50% {{ transform: rotate(90deg); }}
        }}
        
        @keyframes shake {{
            0%, 100% {{ transform: rotate(-10deg); }}
            50% {{ transform: rotate(10deg); }}
        }}
        
        .orientation-content h2 {{
            font-size: 24px;
            margin-bottom: 12px;
            color: #fff;
        }}
        
        .orientation-content p {{
            font-size: 14px;
            color: #a0aec0;
            margin-bottom: 25px;
            line-height: 1.5;
            max-width: 300px;
            margin: 0 auto 25px auto;
        }}
        
        .orientation-hint {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 15px;
            margin-top: 15px;
        }}
        
        .phone-icon {{
            font-size: 40px;
            transition: all 0.3s ease;
        }}
        
        .phone-icon.vertical {{
            opacity: 0.5;
        }}
        
        .phone-icon.horizontal {{
            transform: rotate(90deg);
            color: #7c3aed;
        }}
        
        .orientation-hint .arrow {{
            font-size: 24px;
            color: #7c3aed;
            animation: pulse-arrow 1s ease-in-out infinite;
        }}
        
        @keyframes pulse-arrow {{
            0%, 100% {{ transform: translateX(0); opacity: 1; }}
            50% {{ transform: translateX(10px); opacity: 0.5; }}
        }}
        
        /* Continue in portrait button */
        .continue-portrait-btn {{
            margin-top: 25px;
            background: transparent;
            border: 1px solid rgba(255,255,255,0.3);
            color: #94a3b8;
            padding: 12px 28px;
            border-radius: 20px;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.2s;
        }}
        
        .continue-portrait-btn:hover,
        .continue-portrait-btn:active {{
            background: rgba(255,255,255,0.1);
            color: #fff;
            border-color: rgba(255,255,255,0.5);
        }}
        
        @keyframes pulse {{
            0%, 100% {{ transform: scale(1); }}
            50% {{ transform: scale(1.1); }}
        }}
        
        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(10px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        
        @keyframes fadeOut {{
            from {{ opacity: 1; transform: translateY(0); }}
            to {{ opacity: 0; transform: translateY(-10px); }}
        }}
        
        /* PowerPoint Animation Effects */
        @keyframes ppt-appear {{
            from {{ opacity: 0; }}
            to {{ opacity: 1; }}
        }}
        
        @keyframes ppt-fade {{
            from {{ opacity: 0; }}
            to {{ opacity: 1; }}
        }}
        
        @keyframes ppt-fly-left {{
            from {{ opacity: 0; transform: translateX(-100%); }}
            to {{ opacity: 1; transform: translateX(0); }}
        }}
        
        @keyframes ppt-fly-right {{
            from {{ opacity: 0; transform: translateX(100%); }}
            to {{ opacity: 1; transform: translateX(0); }}
        }}
        
        @keyframes ppt-fly-top {{
            from {{ opacity: 0; transform: translateY(-100%); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        
        @keyframes ppt-fly-bottom {{
            from {{ opacity: 0; transform: translateY(100%); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        
        @keyframes ppt-zoom {{
            from {{ opacity: 0; transform: scale(0.3); }}
            to {{ opacity: 1; transform: scale(1); }}
        }}
        
        @keyframes ppt-grow {{
            from {{ transform: scale(0); }}
            to {{ transform: scale(1); }}
        }}
        
        @keyframes ppt-shrink {{
            from {{ transform: scale(1.5); }}
            to {{ transform: scale(1); }}
        }}
        
        @keyframes ppt-spin {{
            from {{ opacity: 0; transform: rotate(-360deg) scale(0.5); }}
            to {{ opacity: 1; transform: rotate(0deg) scale(1); }}
        }}
        
        @keyframes ppt-swivel {{
            from {{ opacity: 0; transform: rotateY(-90deg); }}
            to {{ opacity: 1; transform: rotateY(0deg); }}
        }}
        
        @keyframes ppt-bounce {{
            0% {{ opacity: 0; transform: translateY(-100%); }}
            50% {{ transform: translateY(10%); }}
            70% {{ transform: translateY(-5%); }}
            100% {{ opacity: 1; transform: translateY(0); }}
        }}
        
        @keyframes ppt-float {{
            from {{ opacity: 0; transform: translateY(50px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        
        @keyframes ppt-wipe-left {{
            from {{ clip-path: inset(0 100% 0 0); }}
            to {{ clip-path: inset(0 0 0 0); }}
        }}
        
        @keyframes ppt-wipe-right {{
            from {{ clip-path: inset(0 0 0 100%); }}
            to {{ clip-path: inset(0 0 0 0); }}
        }}
        
        @keyframes ppt-wipe-top {{
            from {{ clip-path: inset(100% 0 0 0); }}
            to {{ clip-path: inset(0 0 0 0); }}
        }}
        
        @keyframes ppt-wipe-bottom {{
            from {{ clip-path: inset(0 0 100% 0); }}
            to {{ clip-path: inset(0 0 0 0); }}
        }}
        
        @keyframes ppt-blinds {{
            from {{ opacity: 0; clip-path: polygon(0% 0%, 10% 0%, 10% 100%, 0% 100%, 0% 0%, 20% 0%, 20% 100%, 30% 0%, 30% 100%, 40% 0%, 40% 100%, 50% 0%, 50% 100%); }}
            to {{ opacity: 1; clip-path: polygon(0% 0%, 100% 0%, 100% 100%, 0% 100%); }}
        }}
        
        @keyframes ppt-emphasis-pulse {{
            0%, 100% {{ transform: scale(1); }}
            50% {{ transform: scale(1.1); }}
        }}
        
        @keyframes ppt-emphasis-teeter {{
            0%, 100% {{ transform: rotate(0deg); }}
            25% {{ transform: rotate(3deg); }}
            75% {{ transform: rotate(-3deg); }}
        }}
        
        @keyframes ppt-exit-fade {{
            from {{ opacity: 1; }}
            to {{ opacity: 0; }}
        }}
        
        @keyframes ppt-exit-fly {{
            from {{ opacity: 1; transform: translateY(0); }}
            to {{ opacity: 0; transform: translateY(-100%); }}
        }}
        
        @keyframes ppt-exit-zoom {{
            from {{ opacity: 1; transform: scale(1); }}
            to {{ opacity: 0; transform: scale(0.3); }}
        }}
        
        /* Presentation Mode - Fullscreen optimized */
        .presentation-mode #slide-wrapper {{
            padding: 5px !important;
            background: #000 !important;
        }}
        
        .presentation-mode #sidebar {{
            display: none !important;
        }}
        
        /* Floating controls for presentation mode */
        #floating-controls {{
            position: fixed;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            display: flex;
            align-items: center;
            gap: 15px;
            background: rgba(0, 0, 0, 0.8);
            padding: 12px 25px;
            border-radius: 30px;
            z-index: 10001;
            backdrop-filter: blur(10px);
        }}
        
        #floating-controls button {{
            background: rgba(255, 255, 255, 0.2);
            border: none;
            color: #fff;
            width: 44px;
            height: 44px;
            border-radius: 50%;
            font-size: 18px;
            cursor: pointer;
            transition: background 0.2s, transform 0.1s;
        }}
        
        #floating-controls button:hover {{
            background: rgba(255, 255, 255, 0.3);
        }}
        
        #floating-controls button:active {{
            transform: scale(0.95);
        }}
        
        #float-progress {{
            color: #fff;
            font-size: 16px;
            font-weight: 500;
            min-width: 60px;
            text-align: center;
        }}
        
        /* Touch-friendly on mobile */
        @media screen and (max-width: 900px) {{
            #floating-controls {{
                bottom: 15px;
                padding: 10px 20px;
            }}
            
            #floating-controls button {{
                width: 50px;
                height: 50px;
                font-size: 20px;
            }}
        }}
    </style>
</head>
<body>
    <!-- ── Initial loading overlay (covers viewport until slide 1 ─────
         is ready). Especially important for SCORM packages on slow
         LMS bandwidth: prevents the broken-image flash before the
         player's JS finishes rendering and the assets cache.  ───── -->
    <div id="scormify-loader" role="status" aria-label="Carregando curso" data-testid="scorm-initial-loader">
        <style>
            #scormify-loader {{
                position: fixed; inset: 0; z-index: 99999;
                background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
                color: #f1f5f9;
                display: flex; align-items: center; justify-content: center;
                flex-direction: column;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                transition: opacity 0.5s ease;
            }}
            #scormify-loader.hidden {{ opacity: 0; pointer-events: none; }}
            #scormify-loader .ldr-spin {{
                width: 64px; height: 64px;
                border: 4px solid rgba(255,255,255,0.12);
                border-top-color: {loader_primary};
                border-radius: 50%;
                animation: scormify-spin 0.9s linear infinite;
                margin-bottom: 24px;
            }}
            #scormify-loader .ldr-title {{
                font-size: 18px; font-weight: 600; margin-bottom: 14px;
                letter-spacing: 0.3px;
                text-align: center; padding: 0 16px; max-width: min(640px, 90vw);
            }}
            #scormify-loader .ldr-bar-track {{
                width: min(320px, 60vw); height: 6px;
                background: rgba(255,255,255,0.12);
                border-radius: 999px; overflow: hidden;
            }}
            #scormify-loader .ldr-bar-fill {{
                height: 100%; width: 0%;
                background: linear-gradient(90deg, {loader_primary}, {loader_accent});
                border-radius: 999px;
                transition: width 0.25s ease;
            }}
            #scormify-loader .ldr-percent {{
                font-size: 13px; opacity: 0.7;
                margin-top: 10px; font-variant-numeric: tabular-nums;
            }}
            @keyframes scormify-spin {{
                from {{ transform: rotate(0deg); }}
                to   {{ transform: rotate(360deg); }}
            }}
        </style>
        <div class="ldr-spin" aria-hidden="true"></div>
        <div class="ldr-title">{loader_title}</div>
        <div class="ldr-bar-track" aria-hidden="true">
            <div class="ldr-bar-fill" id="scormify-loader-bar"></div>
        </div>
        <div class="ldr-percent" id="scormify-loader-percent">0%</div>
    </div>
    <script>
        // Initial-load progress tracker. Hides the overlay once the
        // first slide's <img>/<video> elements finish loading, OR
        // after a 15 s safety timeout (some LMSes proxy assets through
        // slow CDNs and individual files may never settle). Watched
        // resources are sampled progressively as the Player renders
        // slide 1 — we poll the slide-elements wrapper every 200 ms
        // for up to 2 s after DOMContentLoaded to pick up assets that
        // get injected after the script tag.
        (function() {{
            var overlay = document.getElementById('scormify-loader');
            var bar = document.getElementById('scormify-loader-bar');
            var pctLabel = document.getElementById('scormify-loader-percent');
            var hidden = false;
            function setProgress(p) {{
                p = Math.max(0, Math.min(100, p));
                if (bar) bar.style.width = p.toFixed(0) + '%';
                if (pctLabel) pctLabel.textContent = p.toFixed(0) + '%';
            }}
            function hide() {{
                if (hidden) return;
                hidden = true;
                setProgress(100);
                setTimeout(function() {{
                    if (overlay) {{
                        overlay.classList.add('hidden');
                        setTimeout(function() {{
                            if (overlay && overlay.parentNode) {{
                                overlay.parentNode.removeChild(overlay);
                            }}
                        }}, 600);
                    }}
                }}, 180);
            }}

            function trackAssets() {{
                // Look at the slide that's currently rendered (slide 1
                // after Player.init). Includes images, videos and
                // backgrounds. Track each individually for accurate %.
                var root = document.getElementById('slide-elements')
                        || document.getElementById('slide-canvas')
                        || document.body;
                var imgs = Array.from(root.querySelectorAll('img'));
                var vids = Array.from(root.querySelectorAll('video'));
                var total = imgs.length + vids.length;
                if (total === 0) {{
                    // No assets to wait for — give the player a brief
                    // moment to settle then bail.
                    setTimeout(hide, 250);
                    return;
                }}
                var loaded = 0;
                function bump() {{
                    loaded++;
                    setProgress((loaded / total) * 95);
                    if (loaded >= total) hide();
                }}
                imgs.forEach(function(im) {{
                    if (im.complete && im.naturalWidth > 0) {{
                        bump();
                    }} else {{
                        im.addEventListener('load', bump, {{once: true}});
                        im.addEventListener('error', bump, {{once: true}});
                    }}
                }});
                vids.forEach(function(v) {{
                    if (v.readyState >= 2) {{
                        bump();
                    }} else {{
                        v.addEventListener('loadeddata', bump, {{once: true}});
                        v.addEventListener('error', bump, {{once: true}});
                    }}
                }});
            }}

            // Poll for the first slide's DOM up to 2 s after page load.
            // The Player builds it inside `init` which runs on
            // DOMContentLoaded — usually it's ready almost immediately,
            // but on slow LMSes the JS bundle alone can take a beat.
            var started = false;
            function tryStart() {{
                if (started) return;
                var root = document.getElementById('slide-elements');
                if (root && root.children.length > 0) {{
                    started = true;
                    trackAssets();
                }}
            }}
            var pollHandle = setInterval(function() {{
                tryStart();
                if (started) clearInterval(pollHandle);
            }}, 200);
            setTimeout(function() {{
                clearInterval(pollHandle);
                if (!started) {{
                    // Player never rendered — hide anyway so the user
                    // can at least see whatever IS on screen.
                    hide();
                }}
            }}, 2000);

            // Hard safety net: never block the user for more than 15 s,
            // even if some asset is irrevocably stuck.
            setTimeout(hide, 15000);

            // Coarse progress while we wait for the first slide to
            // appear — gives the user a sign of life on very slow
            // bandwidth.
            var coarse = 5;
            var coarseHandle = setInterval(function() {{
                if (started || hidden) {{ clearInterval(coarseHandle); return; }}
                coarse = Math.min(coarse + 3, 35);
                setProgress(coarse);
            }}, 250);
        }})();
    </script>
    <!-- Mobile Orientation Overlay -->
    <div id="orientation-overlay">
        <div class="orientation-content">
            <div class="orientation-icon">📱</div>
            <div class="orientation-arrow">↻</div>
            <h2>Rotacione seu dispositivo</h2>
            <p>Para uma melhor experiência, por favor visualize este conteúdo no modo horizontal (paisagem)</p>
            <div class="orientation-hint">
                <span class="phone-icon vertical">📱</span>
                <span class="arrow">→</span>
                <span class="phone-icon horizontal">📱</span>
            </div>
            <button class="continue-portrait-btn" onclick="(function(){{ try{{sessionStorage.setItem('orientation_overlay_dismissed','true')}}catch(e){{}} document.getElementById('orientation-overlay').style.display='none'; document.getElementById('player-container').style.display='flex'; if(typeof Player!=='undefined'&&Player.updateScale)setTimeout(function(){{Player.updateScale()}},100); }})()">
                Continuar no modo retrato
            </button>
        </div>
    </div>
    
    <!-- Main Player Container -->
    <div id="player-container">
        <div id="header">
            <div style="display: flex; align-items: center; gap: 15px;">
                <button class="control-btn icon-btn" onclick="Player.toggleSidebar()" title="Menu">
                    ☰
                </button>
                <h1 id="course-title">{title}</h1>
            </div>
            <div id="progress-info">
                <span id="current-slide">1</span> / <span id="total-slides">1</span>
            </div>
        </div>
        
        <div id="main-content">
            <div id="sidebar">
                <div id="sidebar-content"></div>
            </div>
            
            <div id="slide-wrapper">
                <div id="slide-container"></div>
            </div>
        </div>
        
        <div id="controls">
            <div class="nav-buttons">
                <button class="control-btn icon-btn" onclick="Player.toggleSidebar()" title="Menu">☰</button>
                <button class="control-btn" onclick="Player.prev()" id="prev-btn">← Anterior</button>
            </div>
            
            <div class="progress-container">
                <div class="progress-dots" id="progress-dots"></div>
            </div>
            
            <div class="nav-buttons">
                <button class="control-btn" onclick="Player.next()" id="next-btn">Próximo →</button>
                <div class="volume-control">
                    <button class="control-btn icon-btn" onclick="Player.toggleMute()" id="mute-btn" title="Volume">🔊</button>
                    <input type="range" class="volume-slider" min="0" max="100" value="70" 
                           onchange="Player.setVolume(this.value / 100)" id="volume-slider">
                </div>
                <button class="control-btn icon-btn" onclick="Player.fullscreen()" title="Tela Cheia">⛶</button>
            </div>
        </div>
    </div>
    
    <!-- Mobile Floating Controls (shown automatically on mobile landscape) -->
    <div id="mobile-float-controls">
        <button onclick="Player.prev()">←</button>
        <span class="progress-text" id="mobile-progress">1/1</span>
        <button onclick="Player.next()">→</button>
    </div>
    
    <script>
        // Course data embedded
        var courseData = {course_json};
        
        // VLibras automatic translation helper
        // Uses Plugin.translate(text) which requires Unity player to be fully loaded
        var _vlibrasQueue = [];
        var _vlibrasPlayerLoaded = false;
        var _vlibrasSetupDone = false;
        
        function _processVLibrasQueue() {{
            if (_vlibrasQueue.length > 0 && window.plugin && typeof window.plugin.translate === 'function') {{
                var item = _vlibrasQueue[_vlibrasQueue.length - 1];
                _vlibrasQueue = [];
                setTimeout(function() {{
                    try {{ window.plugin.translate(item.text); }}
                    catch(e) {{ console.log('[VLibras] error:', e); }}
                }}, 1500);
            }}
        }}
        
        function _setupVLibrasWatcher() {{
            if (_vlibrasSetupDone) return;
            _vlibrasSetupDone = true;
            var pollId = setInterval(function() {{
                if (!window.plugin || !window.plugin.player) return;
                clearInterval(pollId);
                var player = window.plugin.player;
                if (typeof player.isLoaded === 'function' && player.isLoaded()) {{
                    _vlibrasPlayerLoaded = true;
                    _processVLibrasQueue();
                    return;
                }}
                if (typeof player.on === 'function') {{
                    player.on('load', function() {{
                        _vlibrasPlayerLoaded = true;
                        _processVLibrasQueue();
                    }});
                }}
                var canvasPoll = setInterval(function() {{
                    if (_vlibrasPlayerLoaded) {{ clearInterval(canvasPoll); return; }}
                    var wrapper = document.querySelector('[vw-plugin-wrapper]');
                    if (wrapper && wrapper.querySelector('canvas')) {{
                        clearInterval(canvasPoll);
                        if (!_vlibrasPlayerLoaded) {{
                            _vlibrasPlayerLoaded = true;
                            _processVLibrasQueue();
                        }}
                    }}
                }}, 2000);
                setTimeout(function() {{ clearInterval(canvasPoll); }}, 120000);
            }}, 500);
            setTimeout(function() {{ clearInterval(pollId); }}, 120000);
        }}
        
        function translateWithVLibras(text, slideIndex) {{
            if (!text) return;
            if (_vlibrasPlayerLoaded && window.plugin && typeof window.plugin.translate === 'function') {{
                try {{ window.plugin.translate(text); }}
                catch(e) {{ console.log('[VLibras] error:', e); }}
            }} else {{
                _vlibrasQueue = [{{ text: text, slideIndex: slideIndex }}];
                _setupVLibrasWatcher();
            }}
        }}
        
        // Player module
        var Player = (function() {{
            var course = null;
            var currentSlide = 0;
            var totalSlides = 0;
            var globalAudio = null;
            var slideAudios = [];
            var isMuted = false;
            var volume = 0.7;
            var sidebarOpen = false;
            var timelineTimers = []; // Timeline timers for showing/hiding elements
            var isPresentationMode = false;
            
            function init() {{
                course = courseData;
                totalSlides = course.slides ? course.slides.length : 0;
                
                document.getElementById('total-slides').textContent = totalSlides;
                
                // Setup global audio
                if (course.globalAudio && course.globalAudio.src) {{
                    globalAudio = new Audio(course.globalAudio.src);
                    globalAudio.loop = true;
                    globalAudio.volume = (course.globalAudio.volume || 0.5) * volume;
                }}
                
                renderSidebar();
                renderSlide(0);
                updateProgress();
                
                // Show start overlay if there's any audio
                var hasAudio = (course.globalAudio && course.globalAudio.src);
                if (!hasAudio) {{
                    // Check if any slide has audio
                    for (var i = 0; i < course.slides.length; i++) {{
                        if (course.slides[i].audio && course.slides[i].audio.length > 0) {{
                            hasAudio = true;
                            break;
                        }}
                    }}
                }}
                
                if (hasAudio) {{
                    showStartOverlay();
                }}
                
                // Keyboard navigation
                document.addEventListener('keydown', function(e) {{
                    if (e.key === 'ArrowLeft') prev();
                    else if (e.key === 'ArrowRight') next();
                    else if (e.key === 'Escape' && document.fullscreenElement) {{
                        document.exitFullscreen();
                    }}
                }});
                
                // Handle resize
                window.addEventListener('resize', updateSlideScale);
                updateSlideScale();
            }}
            
            function showStartOverlay() {{
                var overlay = document.createElement('div');
                overlay.id = 'start-overlay';
                overlay.innerHTML = '<div class="start-content">' +
                    '<div class="start-icon">🎵</div>' +
                    '<h2>Este curso contém áudio</h2>' +
                    '<p>Clique para iniciar com som</p>' +
                    '<button class="start-btn" onclick="Player.startCourse()">▶ Iniciar Curso</button>' +
                    '</div>';
                overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.9);z-index:10000;display:flex;align-items:center;justify-content:center;';
                document.body.appendChild(overlay);
                
                // Add styles for overlay
                var style = document.createElement('style');
                style.textContent = '.start-content{{text-align:center;color:#fff;}}.start-icon{{font-size:60px;margin-bottom:20px;}}.start-content h2{{font-size:24px;margin-bottom:10px;}}.start-content p{{opacity:0.7;margin-bottom:20px;}}.start-btn{{background:linear-gradient(135deg,#7c3aed,#06b6d4);border:none;color:#fff;padding:15px 40px;border-radius:8px;font-size:18px;cursor:pointer;transition:transform 0.2s;}}.start-btn:hover{{transform:scale(1.05);}}';
                document.head.appendChild(style);
            }}
            
            function hideStartOverlay() {{
                var overlay = document.getElementById('start-overlay');
                if (overlay) {{
                    overlay.remove();
                    
                    // Start global audio
                    if (globalAudio) {{
                        globalAudio.play().catch(function() {{
                            globalAudio.muted = true;
                            globalAudio.play().catch(function() {{}});
                        }});
                    }}
                    
                    // Also try to play current slide audio
                    var slide = course.slides[currentSlide];
                    if (slide && slide.audio && slide.audio.length > 0) {{
                        slide.audio.forEach(function(audioData) {{
                            if (audioData.src) {{
                                var audio = new Audio(audioData.src);
                                audio.volume = isMuted ? 0 : volume;
                                slideAudios.push(audio);
                                audio.play().catch(function() {{}});
                            }}
                        }});
                    }}
                }}
            }}
            
            function renderSidebar() {{
                var sidebar = document.getElementById('sidebar-content');
                var html = '';
                
                course.slides.forEach(function(slide, index) {{
                    var isActive = index === currentSlide;
                    html += '<div class="sidebar-item ' + (isActive ? 'active' : '') + '" onclick="Player.goTo(' + index + ')">';
                    html += '<div class="sidebar-item-number">Slide ' + (index + 1) + '</div>';
                    html += '<div class="sidebar-item-title">' + (slide.title || 'Slide ' + (index + 1)) + '</div>';
                    html += '</div>';
                }});
                
                sidebar.innerHTML = html;
            }}
            
            function renderSlide(index) {{
                currentSlide = index;
                var slide = course.slides[index];
                var container = document.getElementById('slide-container');
                
                // Notify AI Tutor of slide change
                if (typeof AiTutor !== 'undefined') {{ AiTutor.onSlideChange(index); }}
                
                // Clear any existing timeline timers
                timelineTimers.forEach(function(timer) {{
                    clearTimeout(timer);
                }});
                timelineTimers = [];
                
                // Stop previous audio
                slideAudios.forEach(function(audio) {{
                    if (audio) {{
                        audio.pause();
                        audio.currentTime = 0;
                    }}
                }});
                slideAudios = [];
                
                // Stop previous videos
                var prevVideos = container.querySelectorAll('video.local-video');
                prevVideos.forEach(function(video) {{
                    if (video) {{
                        video.pause();
                        video.currentTime = 0;
                    }}
                }});
                
                // Set dimensions
                var slideWidth = slide.width || {width};
                var slideHeight = slide.height || {height};
                container.style.width = slideWidth + 'px';
                container.style.height = slideHeight + 'px';
                
                // Get slide duration for timeline - consider audio and video durations
                var slideDuration = slide.duration || 5;
                var maxMediaDuration = 0;
                if (slide.audio && slide.audio.length > 0) {{
                    slide.audio.forEach(function(a) {{
                        var audioEnd = (a.startTime || 0) + (a.duration || 0);
                        if (audioEnd > maxMediaDuration) maxMediaDuration = audioEnd;
                    }});
                }}
                if (slide.elements) {{
                    slide.elements.forEach(function(el) {{
                        if (el.type === 'video' || el.type === 'heygen') {{
                            var videoEnd = (el.startTime || 0) + (el.duration || 0);
                            if (videoEnd > maxMediaDuration) maxMediaDuration = videoEnd;
                        }}
                    }});
                }}
                if (maxMediaDuration > 0 && maxMediaDuration > slideDuration) {{
                    slideDuration = maxMediaDuration + 1;
                }}
                
                // Build slide HTML
                var html = '';

                // Zoom-on-hotspot effect (Tutorial Agent imports). When the
                // slide carries a `zoomEffect`, wrap everything inside a stage
                // div so the magnify animation moves bg AND overlays together
                // (so the hotspot keeps pointing at the right element).
                var __zoomEffect = (slide.zoomEffect && typeof slide.zoomEffect === 'object' && parseFloat(slide.zoomEffect.scale || 1) > 1) ? slide.zoomEffect : null;
                if (__zoomEffect) {{
                    container.style.overflow = 'hidden';
                    html += '<div class="slide-zoom-stage" style="position:absolute;inset:0;transform-origin:' +
                        (__zoomEffect.focusX != null ? __zoomEffect.focusX : 50) + '% ' +
                        (__zoomEffect.focusY != null ? __zoomEffect.focusY : 50) + '%;will-change:transform;z-index:0">';
                }}
                
                // Background
                if (slide.backgroundImage) {{
                    var bgOpacity = 1;
                    if (slide.backgroundImageOpacity !== undefined && slide.backgroundImageOpacity !== null) {{
                        bgOpacity = slide.backgroundImageOpacity;
                    }} else if (slide.backgroundOpacity !== undefined && slide.backgroundOpacity !== null) {{
                        bgOpacity = slide.backgroundOpacity / 100;
                    }}
                    html += '<img class="slide-background" src="' + slide.backgroundImage + '" alt="" style="opacity:' + bgOpacity + '">';
                    // Aesthetic Analyzer scrim/overlay for text legibility.
                    // Suppressed when bg came from the Brand Library — author
                    // already made a deliberate choice. Force via backgroundImageOverlayForce.
                    var bgFromLibrary = slide.backgroundImageSource === 'brand_library';
                    if (slide.backgroundImageOverlay && (!bgFromLibrary || slide.backgroundImageOverlayForce)) {{
                        var ov = slide.backgroundImageOverlay;
                        var ovBg;
                        if (ov === 'dark') ovBg = 'linear-gradient(180deg,rgba(0,0,0,0.45),rgba(0,0,0,0.65))';
                        else if (ov === 'light') ovBg = 'linear-gradient(180deg,rgba(255,255,255,0.55),rgba(255,255,255,0.75))';
                        else ovBg = ov;
                        html += '<div class="slide-bg-overlay" aria-hidden="true" style="position:absolute;inset:0;pointer-events:none;z-index:1;background:' + ovBg + '"></div>';
                    }}
                    if (slide.background && slide.background !== '#fff') {{
                        container.style.background = slide.background;
                    }}
                }} else {{
                    container.style.background = slide.background || '#fff';
                }}
                
                // Elements
                if (slide.elements) {{
                    slide.elements.forEach(function(elem, elemIndex) {{
                        if (elem.visible === false) return;
                        
                        // Check if element has timeline settings
                        var startTime = elem.startTime || 0;
                        var endTime = (elem.endTime !== undefined && elem.endTime !== null) ? elem.endTime : slideDuration;
                        
                        // Check element type
                        var isClipElement = elem.type === 'animation_clip';
                        var isMaskElement = elem.type === 'animation_mask';
                        var isHighlightElement = elem.type === 'animation_highlight';
                        var isAnimationElement = isClipElement || isMaskElement || isHighlightElement;
                        
                        // Check if element has animations (support both arrays and single object)
                        var anims = (elem.animations && elem.animations.length > 0) ? elem.animations : [];
                        if (!anims.length && elem.animation && elem.animation.effect) {{
                            anims = [{{
                                type: elem.animation.type || 'entrance',
                                effect: elem.animation.effect,
                                duration: elem.animation.duration || 0.5,
                                startTime: elem.animation.delay || 0,
                            }}];
                        }}
                        var hasAnimations = anims.length > 0;
                        var hasEntranceAnimation = hasAnimations && anims.some(function(a) {{ return a.type === 'entrance'; }});
                        
                        // Determine initial visibility
                        // For clips/masks: they should START VISIBLE (to cover content)
                        // For other elements with entrance animations: start hidden
                        var initiallyHidden = false;
                        if (isClipElement || isMaskElement) {{
                            // Clips and masks should start VISIBLE
                            initiallyHidden = false;
                        }} else if (startTime > 0 || hasEntranceAnimation) {{
                            initiallyHidden = true;
                        }}
                        
                        var style = 'left:' + (elem.x || 0) + 'px;';
                        style += 'top:' + (elem.y || 0) + 'px;';
                        style += 'width:' + (elem.width || 100) + 'px;';
                        style += 'height:' + (elem.height || 100) + 'px;';
                        style += 'z-index:' + ((elem.zIndex || 0) + 1) + ';';
                        if (elem.rotation) style += 'transform:rotate(' + elem.rotation + 'deg);';
                        
                        // Handle opacity based on element type. Order matters:
                        // initially-hidden (startTime > 0 or has entrance
                        // animation) must take precedence over a custom
                        // `elem.style.opacity` — otherwise a user-set
                        // opacity caused the element to be rendered VISIBLE
                        // from t=0 even when the timeline said it should
                        // only appear later (2026-02 bugfix).
                        if (isClipElement || isMaskElement) {{
                            // Clips and masks: start visible/opaque
                            var maskOpacity = (elem.style && elem.style.opacity !== undefined) ? elem.style.opacity : 1;
                            style += 'opacity:' + maskOpacity + ';';
                        }} else if (initiallyHidden) {{
                            style += 'visibility:hidden;opacity:0;';
                        }} else if (!hasAnimations && elem.style && elem.style.opacity !== undefined) {{
                            style += 'opacity:' + elem.style.opacity + ';';
                        }}
                        
                        html += '<div class="slide-element ' + elem.type + '-element" id="element-' + elemIndex + '" data-start-time="' + startTime + '" data-end-time="' + endTime + '" style="' + style + '">';
                        
                        if (elem.type === 'text') {{
                            var textStyle = '';
                            if (elem.style) {{
                                if (elem.style.fontSize) textStyle += 'font-size:' + elem.style.fontSize + 'px;';
                                if (elem.style.fontFamily) textStyle += 'font-family:' + elem.style.fontFamily + ',sans-serif;';
                                if (elem.style.fontColor) textStyle += 'color:' + elem.style.fontColor + ';';
                                if (elem.style.fontWeight) textStyle += 'font-weight:' + elem.style.fontWeight + ';';
                                if (elem.style.textAlign) textStyle += 'text-align:' + elem.style.textAlign + ';';
                                // Apply background color (transparent or custom; textBackgroundColor is the
                                // Aesthetic Analyzer plate alias and takes priority).
                                if (elem.style.transparentBackground) {{
                                    textStyle += 'background-color:transparent;';
                                }} else if (elem.style.textBackgroundColor) {{
                                    textStyle += 'background-color:' + elem.style.textBackgroundColor + ';';
                                }} else if (elem.style.backgroundColor) {{
                                    textStyle += 'background-color:' + elem.style.backgroundColor + ';';
                                }} else {{
                                    textStyle += 'background-color:rgba(255,255,255,0.9);';
                                }}
                                if (elem.style.padding) textStyle += 'padding:' + elem.style.padding + ';';
                                if (elem.style.borderRadius) textStyle += 'border-radius:' + (typeof elem.style.borderRadius === 'number' ? elem.style.borderRadius + 'px' : elem.style.borderRadius) + ';';
                                if (elem.style.textShadow) textStyle += 'text-shadow:' + elem.style.textShadow + ';';
                            }} else {{
                                textStyle += 'background-color:rgba(255,255,255,0.9);';
                            }}
                            html += '<div style="' + textStyle + '">' + (elem.content || '') + '</div>';
                        }}
                        else if (elem.type === 'image' && elem.src) {{
                            html += '<img src="' + elem.src + '" alt="" style="width:100%;height:100%;object-fit:' + (elem.objectFit || 'contain') + ';">';
                        }}
                        else if (elem.type === 'smartart' && elem.src) {{
                            // SmartArt rendered as image with fallback content for accessibility
                            html += '<img src="' + elem.src + '" alt="SmartArt: ' + (elem.content || 'Diagram') + '" style="width:100%;height:100%;object-fit:contain;">';
                        }}
                        else if (elem.type === 'shape') {{
                            var shapeBg = (elem.style && elem.style.fill) || '#7c3aed';
                            var shapeRadius = elem.shapeType === 'ellipse' ? '50%' : (elem.shapeType === 'rounded_rectangle' ? '8px' : '0');
                            html += '<div style="width:100%;height:100%;background:' + shapeBg + ';border-radius:' + shapeRadius + ';display:flex;align-items:center;justify-content:center;">';
                            if (elem.content) {{
                                var contentColor = (elem.style && elem.style.fontColor) || '#fff';
                                html += '<span style="color:' + contentColor + ';">' + elem.content + '</span>';
                            }}
                            html += '</div>';
                        }}
                        else if (elem.type === 'animation_clip') {{
                            // Animation clip - invisible overlay that controls when content is revealed
                            // Uses a semi-transparent dark overlay that fades out
                            html += '<div class="animation-clip" style="width:100%;height:100%;background:rgba(0,0,0,0.85);transition:opacity 0.5s ease;"></div>';
                        }}
                        else if (elem.type === 'animation_mask') {{
                            // Legacy animation mask (kept for compatibility)
                            var maskBg = (elem.style && elem.style.fill) || '#FFFFFF';
                            var maskOpacity = (elem.style && elem.style.opacity !== undefined) ? elem.style.opacity : 1;
                            html += '<div class="animation-mask" style="width:100%;height:100%;background:' + maskBg + ';opacity:' + maskOpacity + ';pointer-events:none;"></div>';
                        }}
                        else if (elem.type === 'animation_highlight') {{
                            // Animation highlight for emphasis effects
                            html += '<div class="animation-highlight" style="width:100%;height:100%;background:transparent;pointer-events:none;border:3px solid transparent;box-sizing:border-box;"></div>';
                        }}
                        else if (elem.type === 'video') {{
                            if (elem.embedUrl) {{
                                // Extract video ID for YouTube/Vimeo
                                var embedUrl = elem.embedUrl;
                                var videoId = '';
                                var isYouTube = embedUrl.indexOf('youtube') !== -1 || embedUrl.indexOf('youtu.be') !== -1;
                                var isVimeo = embedUrl.indexOf('vimeo') !== -1;
                                var isBunny = embedUrl.indexOf('iframe.mediadelivery.net') !== -1;
                                
                                if (isYouTube) {{
                                    // Extract YouTube video ID
                                    var ytMatch = embedUrl.match(/(?:embed\/|v=|youtu\.be\/)([^?&"'>]+)/);
                                    if (ytMatch) videoId = ytMatch[1];
                                }} else if (isVimeo) {{
                                    var vimeoMatch = embedUrl.match(/vimeo\.com\/(?:video\/)?(\d+)/);
                                    if (vimeoMatch) videoId = vimeoMatch[1];
                                }}
                                
                                // Create container for video
                                html += '<div class="video-embed-container" data-embed-url="' + embedUrl + '" data-video-id="' + videoId + '" data-is-youtube="' + isYouTube + '" data-is-vimeo="' + isVimeo + '" data-is-bunny="' + isBunny + '" style="width:100%;height:100%;position:relative;overflow:hidden;background:#000;">';
                                
                                // For YouTube: Use iframe embed directly
                                if (isYouTube && videoId) {{
                                    var ytEmbedUrl = 'https://www.youtube.com/embed/' + videoId + '?autoplay=1&rel=0&modestbranding=1&playsinline=1&enablejsapi=1';
                                    html += '<iframe class="video-iframe" src="' + ytEmbedUrl + '" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share; fullscreen" allowfullscreen frameborder="0" style="position:absolute;top:0;left:0;width:100%;height:100%;border:0;"></iframe>';
                                }} else if (isVimeo) {{
                                    // Vimeo: use iframe directly (generally more permissive)
                                    // Add parameters for better fullscreen experience
                                    var iframeUrl = embedUrl;
                                    var sep = iframeUrl.indexOf('?') !== -1 ? '&' : '?';
                                    iframeUrl += sep + 'autoplay=1&muted=0&background=0&dnt=1&title=0&byline=0&portrait=0';
                                    html += '<iframe class="video-iframe" src="' + iframeUrl + '" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share; fullscreen" allowfullscreen style="position:absolute;top:0;left:0;width:100%;height:100%;border:0;"></iframe>';
                                }} else if (isBunny) {{
                                    // Bunny Stream player
                                    var bunnyUrl = embedUrl;
                                    if (bunnyUrl.indexOf('autoplay=') === -1) {{
                                        bunnyUrl += (bunnyUrl.indexOf('?') !== -1 ? '&' : '?') + 'autoplay=true';
                                    }}
                                    if (bunnyUrl.indexOf('preload=') === -1) bunnyUrl += '&preload=true';
                                    if (bunnyUrl.indexOf('responsive=') === -1) bunnyUrl += '&responsive=true';
                                    bunnyUrl = bunnyUrl.replace('muted=true', 'muted=false');
                                    html += '<iframe class="video-iframe" src="' + bunnyUrl + '" allow="accelerometer; gyroscope; autoplay; encrypted-media; picture-in-picture;" allowfullscreen loading="lazy" style="position:absolute;top:0;left:0;width:100%;height:100%;border:0;"></iframe>';
                                }} else {{
                                    // Other embeds
                                    html += '<iframe class="video-iframe" src="' + embedUrl + '" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" allowfullscreen style="width:100%;height:100%;border:0;"></iframe>';
                                }}
                                
                                html += '</div>';
                            }} else if (elem.src) {{
                                // Local video (uploaded or HeyGen)
                                var isWebM = elem.src && elem.src.toLowerCase().includes('.webm');
                                var bgStyle = isWebM ? 'background:transparent !important;' : '';
                                var videoObjectFit = elem.objectFit || 'contain';
                                html += '<video data-element-id="' + elem.id + '" class="local-video" src="' + elem.src + '" playsinline style="width:100%;height:100%;object-fit:' + videoObjectFit + ';pointer-events:none;' + bgStyle + '"></video>';
                            }}
                        }}
                        else if (elem.type === 'button') {{
                            var btnClass = 'button-' + (elem.buttonStyle || 'primary');
                            var btnUrl = elem.buttonUrl || '#';
                            var btnTarget = elem.openInNewTab ? '_blank' : '_self';
                            html += '<a href="' + btnUrl + '" target="' + btnTarget + '">';
                            html += '<button class="' + btnClass + '">' + (elem.buttonText || 'Click') + '</button>';
                            html += '</a>';
                        }}
                        else if (elem.type === 'html' && elem.htmlContent) {{
                            var htmlContent = elem.htmlContent;
                            // Check if content is base64 encoded (to avoid JS escaping issues)
                            if (htmlContent.startsWith('__B64__:')) {{
                                try {{
                                    // Decode base64 and properly handle UTF-8
                                    var binaryString = atob(htmlContent.substring(8));
                                    var bytes = new Uint8Array(binaryString.length);
                                    for (var i = 0; i < binaryString.length; i++) {{
                                        bytes[i] = binaryString.charCodeAt(i);
                                    }}
                                    htmlContent = new TextDecoder('utf-8').decode(bytes);
                                }} catch(e) {{
                                    console.error('Failed to decode htmlContent:', e);
                                }}
                            }}
                            // Check if this element is truly fullscreen (covers most of the slide area)
                            var slideWidth = slide.width || 1280;
                            var slideHeight = slide.height || 720;
                            var isFullscreen = elem.objectFit === 'cover' && 
                                elem.width >= slideWidth * 0.95 && 
                                elem.height >= slideHeight * 0.95 &&
                                elem.x <= slideWidth * 0.05 &&
                                elem.y <= slideHeight * 0.05;
                            // Detect if content is a full HTML document (AI-generated)
                            var isFullDoc = /<!doctype\\s+html|<html[\\s>]/i.test(htmlContent);
                            var wrappedHtml;
                            if (isFullDoc) {{
                                wrappedHtml = htmlContent;
                                // Auto-fit legacy interactive docs missing the __stage
                                // wrapper: center + scale a 960x540 design to the element.
                                if (wrappedHtml.indexOf('__stage') === -1) {{
                                    var fitSnippet = '<style>html,body{{margin:0!important;padding:0!important;width:100%;height:100%;overflow:hidden!important;}}body{{display:flex!important;align-items:center!important;justify-content:center!important;}}</style>' +
                                        '<scr' + 'ipt>(function(){{function b(){{var bd=document.body;if(!bd||document.getElementById("__stage"))return;var st=document.createElement("div");st.id="__stage";st.style.cssText="width:960px;flex:0 0 auto;position:relative;transform-origin:center center;";while(bd.firstChild){{st.appendChild(bd.firstChild);}}bd.appendChild(st);function fit(){{var ch=Math.max(st.scrollHeight,540);var cw=Math.max(st.scrollWidth,960);var s=Math.min(window.innerWidth/cw,window.innerHeight/ch);st.style.transform="scale("+s+")";}}window.addEventListener("resize",fit);fit();setTimeout(fit,300);setTimeout(fit,1000);}}if(document.readyState==="loading"){{document.addEventListener("DOMContentLoaded",b);}}else{{b();}}}})();</scr' + 'ipt>';
                                    var fitBodyIdx = wrappedHtml.toLowerCase().lastIndexOf('</bo' + 'dy>');
                                    wrappedHtml = fitBodyIdx !== -1 ? wrappedHtml.slice(0, fitBodyIdx) + fitSnippet + wrappedHtml.slice(fitBodyIdx) : wrappedHtml + fitSnippet;
                                }}
                            }} else {{
                            wrappedHtml = '<html><head><style>' +
                                (isFullscreen ? 
                                    // FULLSCREEN MODE - image fills entire container
                                    'html,body{{margin:0;padding:0;width:100%;height:100%;overflow:hidden;background:transparent!important;}}' +
                                    'body>div,body>*{{width:100%;height:100%;margin:0;padding:0;text-align:center;position:relative;}}' +
                                    'img,body img{{width:100%!important;height:100%!important;max-width:none!important;max-height:none!important;min-width:100%!important;min-height:100%!important;object-fit:cover!important;display:block!important;margin:0!important;padding:0!important;border:none!important;border-radius:0!important;float:none!important;position:absolute!important;top:0!important;left:0!important;}}' 
                                : 
                                    // NORMAL MODE - preserve image sizes and positions, content must stay within bounds
                                    'html{{margin:0;padding:0;width:100%;height:100%;overflow:hidden!important;}}' +
                                    'body{{margin:0;padding:8px;background:transparent!important;font-family:Arial,sans-serif;color:#f1f5f9;line-height:1.6;overflow:auto!important;word-wrap:break-word;overflow-wrap:break-word;width:100%!important;height:100%!important;box-sizing:border-box!important;}}' +
                                    '*{{box-sizing:border-box!important;max-width:100%!important;}}' +
                                    'img{{border:none!important;outline:none!important;box-shadow:none!important;max-width:100%!important;width:auto!important;height:auto!important;}}' +
                                    'img[style*="width"]{{max-width:100%!important;width:auto!important;height:auto!important;}}' +
                                    'img.rtf-image-float-left,body img.rtf-image-float-left{{float:left!important;clear:left!important;max-width:45%!important;width:auto!important;height:auto!important;border-radius:4px!important;margin:0 16px 12px 0!important;display:block!important;border:none!important;outline:none!important;}}' +
                                    'img.rtf-image-float-right,body img.rtf-image-float-right{{float:right!important;clear:right!important;max-width:45%!important;width:auto!important;height:auto!important;border-radius:4px!important;margin:0 0 12px 16px!important;display:block!important;border:none!important;outline:none!important;}}' +
                                    'img.rtf-image-center{{display:inline-block!important;max-width:80%!important;width:auto!important;height:auto!important;border:none!important;outline:none!important;}}' +
                                    'img.rtf-image-inline{{display:block!important;max-width:100%!important;width:auto!important;height:auto!important;margin:8px 0!important;border:none!important;outline:none!important;}}' +
                                    'img.rtf-image-float-left,img[style*="float: left"],img[style*="float:left"]{{float:left!important;max-width:45%!important;margin-right:16px!important;margin-bottom:12px!important;height:auto!important;object-fit:contain!important;}}' +
                                    'img.rtf-image-float-right,img[style*="float: right"],img[style*="float:right"]{{float:right!important;max-width:45%!important;margin-left:16px!important;margin-bottom:12px!important;height:auto!important;object-fit:contain!important;}}' +
                                    'body::after{{content:\\'\\';display:table;clear:both;}}' +
                                    'p,div,span,ul,ol,li,h1,h2,h3,h4,h5,h6{{overflow:visible!important;word-wrap:break-word;overflow-wrap:break-word;max-width:100%!important;word-break:normal;hyphens:auto;-webkit-hyphens:auto;}}'
                                ) +
                                /* Thin scrollbar styles - apply to both modes */
                                'html,body{{scrollbar-width:thin;scrollbar-color:rgba(100,116,139,0.3) transparent;}}' +
                                '::-webkit-scrollbar{{width:4px;height:4px;}}' +
                                '::-webkit-scrollbar-track{{background:transparent;}}' +
                                '::-webkit-scrollbar-thumb{{background:rgba(100,116,139,0.3);border-radius:4px;}}' +
                                '::-webkit-scrollbar-thumb:hover{{background:rgba(100,116,139,0.5);}}' +
                                /* Typography - apply to both modes */
                                'h1{{font-size:1.5rem;font-weight:bold;margin-bottom:1rem;}}' +
                                'h2{{font-size:1.25rem;font-weight:bold;margin-bottom:0.75rem;}}' +
                                'h3{{font-size:1.1rem;font-weight:bold;margin-bottom:0.5rem;}}' +
                                'p{{margin-bottom:0.75rem;}}' +
                                'ul{{list-style:disc;padding-left:1.5rem;margin-bottom:0.75rem;}}' +
                                'ol{{list-style:decimal;padding-left:1.5rem;margin-bottom:0.75rem;}}' +
                                'li{{margin-bottom:0.25rem;}}' +
                                'table{{border-collapse:separate;border-spacing:0;width:100%;margin:1rem 0;border-radius:8px;overflow:hidden;box-shadow:0 4px 6px -1px rgba(0,0,0,0.3);}}' +
                                'th{{background:linear-gradient(to bottom,#475569,#334155);border-bottom:2px solid #22d3ee;padding:0.75rem 1rem;font-weight:600;text-align:left;color:#f1f5f9;}}' +
                                'td{{border-bottom:1px solid #334155;padding:0.75rem 1rem;background:#1e293b;color:#e2e8f0;}}' +
                                // Google Fonts — REQUIRED for design-template
                                // fonts to be visible (Nunito, Playfair,
                                // JetBrains Mono, etc). Without this every
                                // theme falls back to sans-serif.
                                '@import url("https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Lato:wght@300;400;700&family=Merriweather:wght@300;400;700&family=Montserrat:wght@300;400;500;600;700&family=Nunito:wght@300;400;600;700&family=Oswald:wght@300;400;500;600;700&family=Playfair+Display:wght@400;500;600;700&family=Poppins:wght@300;400;500;600;700&family=Raleway:wght@300;400;500;600;700&family=Outfit:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&family=Manrope:wght@400;600;700;800&family=Sora:wght@400;600;700&family=Fraunces:wght@400;600;700&family=Source+Serif+4:wght@400;600&family=Space+Grotesk:wght@400;600;700&family=IBM+Plex+Sans:wght@400;600&family=Archivo:wght@400;600;700&display=swap");' +
                                'tr:nth-child(even) td{{background:#1a2433;}}' +
                                // Text-shadow — set from element.style.textShadow.
                                // Wins over anything above via !important + broad
                                // selector so RichText / RTF content also picks it up.
                                (elem.style && elem.style.textShadow ?
                                    'body,body *{{text-shadow:' + elem.style.textShadow + '!important;}}' : '') +
                                '</style></head><body>' + htmlContent + '</body></html>';
                            }}
                            html += '<iframe srcdoc="' + wrappedHtml.replace(/"/g, '&quot;') + '" style="width:100%;height:100%;border:0;overflow:' + (isFullscreen ? 'hidden' : 'auto') + ';"></iframe>';
                        }}
                        else if (elem.type === 'flipbook' && elem.flipbookUrl) {{
                            var fbUrl = elem.flipbookUrl;
                            // Embedded PDFs arrive as data URIs — convert to a blob
                            // URL so every browser renders them in the iframe viewer.
                            if (fbUrl.indexOf('data:application/pdf') === 0) {{
                                try {{
                                    var fbB64 = fbUrl.split(',')[1];
                                    var fbBin = atob(fbB64);
                                    var fbBytes = new Uint8Array(fbBin.length);
                                    for (var fbI = 0; fbI < fbBin.length; fbI++) {{ fbBytes[fbI] = fbBin.charCodeAt(fbI); }}
                                    fbUrl = URL.createObjectURL(new Blob([fbBytes], {{type: 'application/pdf'}}));
                                }} catch(fbErr) {{ console.error('PDF blob conversion failed:', fbErr); }}
                            }}
                            html += '<iframe src="' + fbUrl + '" style="width:100%;height:100%;border:0;" allowfullscreen></iframe>';
                        }}
                        else if (elem.type === 'quiz' && elem.quizConfig) {{
                            // Quiz element - render container for QuizController
                            var quizTransparent = elem.quizConfig.transparentBackground === true;
                            var quizStartBgStyle = quizTransparent
                                ? 'background:transparent;'
                                : 'background:linear-gradient(135deg,#1e293b,#0f172a);border-radius:12px;border:2px solid rgba(34,211,238,0.3);';
                            var quizStartTitleColor = quizTransparent ? '#e0f2fe' : '#fff';
                            var quizStartMetaColor = quizTransparent ? '#cbd5e1' : '#94a3b8';
                            var quizStartTextShadow = quizTransparent ? 'text-shadow:0 1px 2px rgba(0,0,0,0.6);' : '';
                            var quizContainer = '<div class="quiz-player-container" data-element-id="' + elem.id + '" data-quiz-config=\\'' + JSON.stringify(elem.quizConfig).replace(/'/g, "\\\\'") + '\\' style="width:100%;height:100%;display:flex;flex-direction:column;">';
                            quizContainer += '<div style="width:100%;height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:20px;' + quizStartBgStyle + '">';
                            quizContainer += '<div style="font-size:48px;margin-bottom:16px;">📝</div>';
                            quizContainer += '<h3 style="font-size:20px;font-weight:bold;color:' + quizStartTitleColor + ';margin-bottom:8px;' + quizStartTextShadow + '">' + (elem.quizConfig.title || 'Quiz') + '</h3>';
                            quizContainer += '<p style="color:' + quizStartMetaColor + ';font-size:14px;margin-bottom:16px;' + quizStartTextShadow + '">' + (elem.quizConfig.questionIds ? elem.quizConfig.questionIds.length : 0) + ' questões</p>';
                            quizContainer += '<button class="quiz-start-btn" style="padding:12px 32px;background:linear-gradient(135deg,#06b6d4,#8b5cf6);color:#fff;border:none;border-radius:8px;font-size:16px;font-weight:600;cursor:pointer;" ';
                            quizContainer += 'onclick="QuizController.startQuiz(\\'' + elem.id + '\\')">Iniciar Quiz</button>';
                            quizContainer += '</div></div>';
                            html += quizContainer;
                        }}
                        else if (elem.type === 'scenario' && elem.scenarioData) {{
                            // Scenario element - store data in JS map (avoids HTML attribute escaping issues)
                            if (!window.__scenarioDataMap) window.__scenarioDataMap = {{}};
                            window.__scenarioDataMap[elem.id] = elem.scenarioData;
                            var sc = '<div class="scenario-player-container" data-element-id="' + elem.id + '" style="width:100%;height:100%;display:flex;flex-direction:column;">';
                            sc += '<div style="width:100%;height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:20px;background:linear-gradient(135deg,#0f172a,#164e63);border-radius:12px;border:2px solid rgba(34,211,238,0.3);">';
                            sc += '<svg style="width:48px;height:48px;color:#22d3ee;margin-bottom:16px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M6 3v12"/><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M18 9a9 9 0 0 1-9 9"/></svg>';
                            sc += '<h3 style="font-size:20px;font-weight:bold;color:#fff;margin-bottom:8px;">' + (elem.scenarioData.title || 'Cenário Interativo') + '</h3>';
                            sc += '<p style="color:#94a3b8;font-size:14px;margin-bottom:16px;">' + (elem.scenarioData.nodes ? elem.scenarioData.nodes.length : 0) + ' cenas</p>';
                            sc += '<button class="scenario-start-btn" style="padding:12px 32px;background:linear-gradient(135deg,#06b6d4,#0891b2);color:#fff;border:none;border-radius:8px;font-size:16px;font-weight:600;cursor:pointer;" ';
                            sc += 'onclick="ScenarioController.startScenario(\\'' + elem.id + '\\')">Iniciar Cenário</button>';
                            sc += '</div></div>';
                            html += sc;
                        }}
                        
                        html += '</div>';
                    }});
                }}
                
                // Annotations SVG
                if (slide.annotations && slide.annotations.length > 0) {{
                    html += '<svg class="annotations-layer" viewBox="0 0 ' + slideWidth + ' ' + slideHeight + '" preserveAspectRatio="none">';
                    slide.annotations.forEach(function(ann, annIndex) {{
                        var color = ann.color || '#EF4444';
                        var strokeWidth = ann.strokeWidth || 3;
                        
                        // Check if annotation has timeline settings
                        var startTime = ann.startTime || 0;
                        var endTime = (ann.endTime !== undefined && ann.endTime !== null) ? ann.endTime : slideDuration;
                        var initiallyHidden = startTime > 0;
                        var hideStyle = initiallyHidden ? ' style="display:none;"' : '';
                        var annId = 'annotation-' + annIndex;
                        
                        if (ann.type === 'freehand' && ann.points && ann.points.length > 0) {{
                            var d = 'M ' + ann.points[0].x + ' ' + ann.points[0].y;
                            for (var i = 1; i < ann.points.length; i++) {{
                                d += ' L ' + ann.points[i].x + ' ' + ann.points[i].y;
                            }}
                            html += '<path id="' + annId + '" data-start-time="' + startTime + '" data-end-time="' + endTime + '" d="' + d + '" stroke="' + color + '" stroke-width="' + strokeWidth + '" fill="none" stroke-linecap="round" stroke-linejoin="round"' + hideStyle + '/>';
                        }}
                        else if (ann.type === 'arrow' && ann.points && ann.points.length >= 2) {{
                            html += '<defs><marker id="arrow-' + ann.id + '" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">';
                            html += '<polygon points="0 0, 10 3.5, 0 7" fill="' + color + '"/></marker></defs>';
                            html += '<line id="' + annId + '" data-start-time="' + startTime + '" data-end-time="' + endTime + '" x1="' + ann.points[0].x + '" y1="' + ann.points[0].y + '" x2="' + ann.points[1].x + '" y2="' + ann.points[1].y + '" ';
                            html += 'stroke="' + color + '" stroke-width="' + strokeWidth + '" marker-end="url(#arrow-' + ann.id + ')"' + hideStyle + '/>';
                        }}
                        else if (ann.type === 'circle' && ann.points && ann.points.length >= 2) {{
                            var cx = (ann.points[0].x + ann.points[1].x) / 2;
                            var cy = (ann.points[0].y + ann.points[1].y) / 2;
                            var rx = Math.abs(ann.points[1].x - ann.points[0].x) / 2;
                            var ry = Math.abs(ann.points[1].y - ann.points[0].y) / 2;
                            html += '<ellipse id="' + annId + '" data-start-time="' + startTime + '" data-end-time="' + endTime + '" cx="' + cx + '" cy="' + cy + '" rx="' + rx + '" ry="' + ry + '" stroke="' + color + '" stroke-width="' + strokeWidth + '" fill="none"' + hideStyle + '/>';
                        }}
                        else if (ann.type === 'rectangle' && ann.points && ann.points.length >= 2) {{
                            var x = Math.min(ann.points[0].x, ann.points[1].x);
                            var y = Math.min(ann.points[0].y, ann.points[1].y);
                            var w = Math.abs(ann.points[1].x - ann.points[0].x);
                            var h = Math.abs(ann.points[1].y - ann.points[0].y);
                            html += '<rect id="' + annId + '" data-start-time="' + startTime + '" data-end-time="' + endTime + '" x="' + x + '" y="' + y + '" width="' + w + '" height="' + h + '" stroke="' + color + '" stroke-width="' + strokeWidth + '" fill="none"' + hideStyle + '/>';
                        }}
                    }});
                    html += '</svg>';
                }}

                // Close the zoom stage wrapper opened at the top of this
                // function so the bg + overlays are all inside it.
                if (__zoomEffect) {{
                    html += '</div>';
                }}

                container.innerHTML = html;

                // Kick off the zoom animation (Tutorial Agent imports). We
                // schedule the start AFTER a brief settle so the slide is
                // visible at scale 1 first, then magnifies into the hotspot.
                if (__zoomEffect) {{
                    var __zStage = container.querySelector('.slide-zoom-stage');
                    if (__zStage) {{
                        var __zScale = parseFloat(__zoomEffect.scale || 1);
                        var __zIntro = parseInt(__zoomEffect.intro || 800, 10);
                        var __zHold = parseInt(__zoomEffect.hold || 2400, 10);
                        var __zOutro = parseInt(__zoomEffect.outro || 600, 10);
                        __zStage.style.transition = 'none';
                        __zStage.style.transform = 'scale(1)';
                        void __zStage.offsetWidth;
                        var __zTimer = setTimeout(function() {{
                            __zStage.style.transition = 'transform ' + __zIntro + 'ms cubic-bezier(.2,.8,.2,1)';
                            __zStage.style.transform = 'scale(' + __zScale + ')';
                            var __zOutTimer = setTimeout(function() {{
                                __zStage.style.transition = 'transform ' + __zOutro + 'ms cubic-bezier(.4,0,.2,1)';
                                __zStage.style.transform = 'scale(1)';
                            }}, __zIntro + __zHold);
                            timelineTimers.push(__zOutTimer);
                        }}, 300);
                        timelineTimers.push(__zTimer);
                    }}
                }}
                
                // Animation effect map for PPT animations
                var animationEffectMap = {{
                    'appear': 'ppt-appear',
                    'fade': 'ppt-fade',
                    'fly': 'ppt-fly-bottom',
                    'fly_in': 'ppt-fly-bottom',
                    'float': 'ppt-float',
                    'float_up': 'ppt-float',
                    'zoom': 'ppt-zoom',
                    'grow': 'ppt-grow',
                    'shrink': 'ppt-shrink',
                    'spin': 'ppt-spin',
                    'swivel': 'ppt-swivel',
                    'bounce': 'ppt-bounce',
                    'wipe': 'ppt-wipe-left',
                    'blinds': 'ppt-blinds',
                    'pulse': 'ppt-emphasis-pulse',
                    'teeter': 'ppt-emphasis-teeter',
                    'box': 'ppt-zoom',
                    'circle': 'ppt-zoom',
                    'diamond': 'ppt-zoom',
                    'dissolve': 'ppt-fade',
                    'peek': 'ppt-wipe-bottom',
                    'random_bars': 'ppt-blinds',
                    'split': 'ppt-wipe-left',
                    'strips': 'ppt-blinds',
                    'wedge': 'ppt-wipe-left',
                    'wheel': 'ppt-spin',
                    'checkerboard': 'ppt-blinds',
                    'crawl': 'ppt-fly-left',
                    'glide': 'ppt-float',
                    'rise_up': 'ppt-fly-bottom'
                }};
                
                // Setup timeline for elements with startTime/endTime and animations
                if (slide.elements) {{
                    var animationDelay = 0; // Cumulative delay for sequential animations
                    
                    slide.elements.forEach(function(elem, elemIndex) {{
                        if (elem.visible === false) return;
                        
                        var startTime = elem.startTime || 0;
                        var endTime = (elem.endTime !== undefined && elem.endTime !== null) ? elem.endTime : slideDuration;
                        var element = document.getElementById('element-' + elemIndex);
                        var elementOpacity = (elem.style && elem.style.opacity !== undefined && elem.style.opacity !== null) ? elem.style.opacity : 1;
                        
                        if (element) {{
                            // Check if this is an animation clip or mask element
                            var isClip = elem.type === 'animation_clip';
                            var isMask = elem.type === 'animation_mask';
                            var isHighlight = elem.type === 'animation_highlight';
                            
                            // Check if element has animations (support both arrays and single object)
                            var elemAnims = (elem.animations && elem.animations.length > 0) ? elem.animations : [];
                            if (!elemAnims.length && elem.animation && elem.animation.effect) {{
                                elemAnims = [{{
                                    type: elem.animation.type || 'entrance',
                                    effect: elem.animation.effect,
                                    duration: elem.animation.duration || 0.5,
                                    delay: elem.animation.delay || 0,
                                    startTime: elem.animation.delay || 0,
                                }}];
                            }}
                            var hasAnimations = elemAnims.length > 0;
                            
                            if (hasAnimations) {{
                                // Process each animation
                                elemAnims.forEach(function(anim, animIdx) {{
                                    var animEffect = animationEffectMap[anim.effect] || 'ppt-fade';
                                    var animDuration = anim.duration || 0.5;
                                    var animDelay = anim.delay || 0;
                                    
                                    // For clips/masks, the delay is already the start time
                                    var actualDelay = (isClip || isMask) ? animDelay : animDelay;
                                    
                                    if (!isClip && !isMask) {{
                                        // Calculate actual delay based on trigger for non-mask elements
                                        if (anim.trigger === 'afterPrevious') {{
                                            actualDelay = animationDelay + animDelay;
                                        }} else if (anim.trigger === 'withPrevious') {{
                                            // Use same timing as previous
                                        }} else if (anim.trigger === 'onClick') {{
                                            // Skip auto-play for onClick animations
                                            return;
                                        }}
                                    }}
                                    
                                    if (isClip) {{
                                        // CLIP ANIMATION: Fade out the dark overlay to reveal content
                                        var clipInner = element.querySelector('.animation-clip');
                                        if (clipInner) {{
                                            if (anim.type === 'entrance') {{
                                                // Entrance: start with dark cover, then fade it out
                                                var revealTimer = setTimeout(function() {{
                                                    clipInner.style.opacity = '0';
                                                }}, actualDelay * 1000);
                                                timelineTimers.push(revealTimer);
                                                
                                            }} else if (anim.type === 'exit') {{
                                                // Exit: start transparent, then fade in the cover
                                                clipInner.style.opacity = '0';
                                                var hideTimer = setTimeout(function() {{
                                                    clipInner.style.opacity = '1';
                                                }}, actualDelay * 1000);
                                                timelineTimers.push(hideTimer);
                                            }}
                                        }}
                                        
                                    }} else if (isMask) {{
                                        // MASK ANIMATION: For entrance, fade mask OUT to reveal content
                                        // For exit, fade mask IN to hide content
                                        if (anim.type === 'entrance') {{
                                            // Mask starts visible (covering content)
                                            element.style.opacity = '1';
                                            
                                            // Fade out mask to reveal content underneath
                                            var revealTimer = setTimeout(function() {{
                                                element.style.transition = 'opacity ' + animDuration + 's ' + (anim.easing || 'ease');
                                                element.style.opacity = '0';
                                            }}, actualDelay * 1000);
                                            timelineTimers.push(revealTimer);
                                            
                                        }} else if (anim.type === 'exit') {{
                                            // Mask starts transparent
                                            element.style.opacity = '0';
                                            
                                            // Fade in mask to hide content
                                            var hideTimer = setTimeout(function() {{
                                                element.style.transition = 'opacity ' + animDuration + 's ' + (anim.easing || 'ease');
                                                element.style.opacity = '1';
                                            }}, actualDelay * 1000);
                                            timelineTimers.push(hideTimer);
                                        }}
                                        
                                    }} else if (isHighlight) {{
                                        // HIGHLIGHT ANIMATION: Pulse or glow effect
                                        var highlightTimer = setTimeout(function() {{
                                            element.style.borderColor = '#FFD700';
                                            element.style.boxShadow = '0 0 15px rgba(255, 215, 0, 0.7)';
                                            element.style.animation = 'ppt-emphasis-pulse ' + animDuration + 's ' + (anim.easing || 'ease');
                                            
                                            // Remove highlight after animation
                                            setTimeout(function() {{
                                                element.style.borderColor = 'transparent';
                                                element.style.boxShadow = 'none';
                                            }}, animDuration * 1000);
                                        }}, actualDelay * 1000);
                                        timelineTimers.push(highlightTimer);
                                        
                                    }} else if (anim.type === 'entrance') {{
                                        // Regular entrance animation
                                        element.style.opacity = '0';
                                        element.style.visibility = 'hidden';
                                        var eff = anim.effect || 'fadeIn';
                                        // Set initial transform based on effect
                                        if (eff === 'slideInLeft') element.style.transform = 'translateX(-60px)';
                                        else if (eff === 'slideInRight') element.style.transform = 'translateX(60px)';
                                        else if (eff === 'slideInUp') element.style.transform = 'translateY(40px)';
                                        else if (eff === 'slideInDown') element.style.transform = 'translateY(-40px)';
                                        else if (eff === 'zoomIn') element.style.transform = 'scale(0.5)';
                                        else if (eff === 'bounce') element.style.transform = 'translateY(-30px)';
                                        else if (eff === 'typewriter') {{ element.style.opacity = '1'; element.style.clipPath = 'inset(0 100% 0 0)'; }}
                                        
                                        var showTimer = setTimeout(function() {{
                                            element.style.visibility = 'visible';
                                            if (eff === 'typewriter') {{
                                                element.style.transition = 'clip-path ' + animDuration + 's steps(20, end)';
                                                element.style.clipPath = 'inset(0 0% 0 0)';
                                            }} else if (eff === 'bounce') {{
                                                element.style.transition = 'opacity ' + animDuration + 's ease, transform ' + animDuration + 's cubic-bezier(0.34, 1.56, 0.64, 1)';
                                                element.style.opacity = String(elementOpacity);
                                                element.style.transform = 'translateY(0) translateX(0) scale(1)';
                                            }} else {{
                                                var easeFunc = anim.easing || 'cubic-bezier(0.25, 0.46, 0.45, 0.94)';
                                                element.style.transition = 'opacity ' + animDuration + 's ' + easeFunc + ', transform ' + animDuration + 's ' + easeFunc;
                                                element.style.opacity = String(elementOpacity);
                                                element.style.transform = 'translateY(0) translateX(0) scale(1)';
                                            }}
                                        }}, (startTime + actualDelay) * 1000);
                                        timelineTimers.push(showTimer);
                                        
                                        // Update cumulative delay
                                        animationDelay = actualDelay + animDuration;
                                        
                                    }} else if (anim.type === 'exit') {{
                                        var exitEffect = 'ppt-exit-' + (anim.effect || 'fade');
                                        var hideTimer = setTimeout(function() {{
                                            element.style.animation = exitEffect + ' ' + animDuration + 's ' + (anim.easing || 'ease') + ' forwards';
                                            setTimeout(function() {{
                                                element.style.visibility = 'hidden';
                                            }}, animDuration * 1000);
                                        }}, (startTime + actualDelay) * 1000);
                                        timelineTimers.push(hideTimer);
                                        
                                    }} else if (anim.type === 'emphasis') {{
                                        var emphasisTimer = setTimeout(function() {{
                                            element.style.animation = animEffect + ' ' + animDuration + 's ' + (anim.easing || 'ease');
                                        }}, (startTime + actualDelay) * 1000);
                                        timelineTimers.push(emphasisTimer);
                                    }}
                                }});
                                
                            }} else {{
                                // No PPT animations - use timeline startTime/endTime
                                if (startTime > 0) {{
                                    var showTimer = setTimeout(function() {{
                                        // BUGFIX (2026-02): the element was rendered with
                                        // inline `visibility:hidden;opacity:0` to keep it
                                        // invisible until startTime. The fadeIn keyframe
                                        // only animates opacity and has no fill-mode, so
                                        // after 0.3s the element snapped right back to
                                        // invisible. We must explicitly reset visibility
                                        // and opacity to the element's intended values
                                        // BEFORE applying the fadeIn keyframe (the
                                        // keyframe's "from opacity:0" still produces
                                        // a clean fade-in for the user).
                                        element.style.display = '';
                                        element.style.visibility = 'visible';
                                        element.style.opacity = String(elementOpacity);
                                        element.style.animation = 'fadeIn 0.3s ease-out';
                                    }}, startTime * 1000);
                                    timelineTimers.push(showTimer);
                                }}
                                
                                if (endTime < slideDuration) {{
                                    var hideTimer = setTimeout(function() {{
                                        element.style.animation = 'fadeOut 0.3s ease-out forwards';
                                        setTimeout(function() {{
                                            element.style.display = 'none';
                                            element.style.visibility = 'hidden';
                                            element.style.opacity = '0';
                                        }}, 300);
                                    }}, endTime * 1000);
                                    timelineTimers.push(hideTimer);
                                }}
                            }}
                        }}
                    }});
                }}
                
                // Setup timeline for annotations with startTime/endTime
                if (slide.annotations) {{
                    slide.annotations.forEach(function(ann, annIndex) {{
                        var startTime = ann.startTime || 0;
                        var endTime = (ann.endTime !== undefined && ann.endTime !== null) ? ann.endTime : slideDuration;
                        var annotation = document.getElementById('annotation-' + annIndex);
                        
                        if (annotation) {{
                            // Schedule annotation to appear at startTime
                            if (startTime > 0) {{
                                var showTimer = setTimeout(function() {{
                                    annotation.style.display = '';
                                    annotation.style.opacity = '1';
                                }}, startTime * 1000);
                                timelineTimers.push(showTimer);
                            }}
                            
                            // Schedule annotation to hide at endTime (if before slide ends)
                            if (endTime < slideDuration) {{
                                var hideTimer = setTimeout(function() {{
                                    annotation.style.opacity = '0';
                                    setTimeout(function() {{
                                        annotation.style.display = 'none';
                                    }}, 300);
                                }}, endTime * 1000);
                                timelineTimers.push(hideTimer);
                            }}
                        }}
                    }});
                }}
                
                // Start slide audio if exists
                if (slide.audio && slide.audio.length > 0) {{
                    slide.audio.forEach(function(audioData) {{
                        if (audioData.src) {{
                            var audio = new Audio(audioData.src);
                            audio.volume = isMuted ? 0 : volume;
                            slideAudios.push(audio);
                            audio.play().catch(function() {{}});
                        }}
                    }});
                }}
                
                // Auto-play local videos (HeyGen and uploaded videos)
                var localVideos = container.querySelectorAll('video.local-video');
                localVideos.forEach(function(video) {{
                    // Reset video to beginning
                    video.currentTime = 0;
                    video.muted = false;
                    video.volume = isMuted ? 0 : volume;
                    
                    // Play video with proper error handling
                    var playPromise = video.play();
                    if (playPromise !== undefined) {{
                        playPromise.catch(function(error) {{
                            console.log('Autoplay blocked, trying muted:', error);
                            // If autoplay is blocked, try muted
                            video.muted = true;
                            video.play().catch(function(e) {{
                                console.log('Even muted autoplay failed:', e);
                            }});
                        }});
                    }}
                    
                    // Also handle loadedmetadata event for videos that are not yet loaded
                    video.addEventListener('loadedmetadata', function() {{
                        if (video.paused) {{
                            video.play().catch(function() {{
                                video.muted = true;
                                video.play().catch(function() {{}});
                            }});
                        }}
                    }}, {{ once: true }});
                }});
                
                // Update UI
                document.getElementById('current-slide').textContent = currentSlide + 1;
                updateProgress();
                renderSidebar();
                updateSlideScale();
                updateFloatingProgress();
                updateMobileProgress();
            }}
            
            function updateMobileProgress() {{
                var mobileProgress = document.getElementById('mobile-progress');
                if (mobileProgress) {{
                    mobileProgress.textContent = (currentSlide + 1) + '/' + totalSlides;
                }}
            }}
            
            function isMobileLandscape() {{
                // More restrictive check: must be landscape AND have mobile-like dimensions
                // Typical mobile landscape: width < 950px AND height < 450px
                var isLandscape = window.innerWidth > window.innerHeight;
                var hasMobileDimensions = window.innerWidth <= 950 && window.innerHeight <= 450;
                var isTouchDevice = 'ontouchstart' in window || navigator.maxTouchPoints > 0;
                // Return true only if definitely on mobile landscape
                return isLandscape && (hasMobileDimensions || (isTouchDevice && window.innerWidth <= 950));
            }}
            
            function updateSlideScale() {{
                var container = document.getElementById('slide-container');
                var wrapper = document.getElementById('slide-wrapper');
                if (!container || !wrapper || !course.slides) return;
                
                var slide = course.slides[currentSlide];
                var slideWidth = slide.width || {width};
                var slideHeight = slide.height || {height};
                
                // Detect mobile device
                var isMobileDevice = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
                var isTouchDevice = 'ontouchstart' in window || navigator.maxTouchPoints > 0;
                var isSmallScreen = window.innerWidth < 1024;
                var isMobile = isMobileDevice || (isSmallScreen && isTouchDevice);
                
                // Detect portrait orientow.innerWidth;
                var isMobilePortrait = isMobile && isPortrait;
                var isMobileLand = isMobileLandscape();
                
                if (isMobilePortrait) {{
                    // MOBILE PORTRAIT MODE - Fill the screen width completely
                    var screenWidth = Math.max(window.innerWidth, document.documentElement.clientWidth);
                    var screenHeight = Math.max(window.innerHeight, document.documentElement.clientHeight);
                    
                    var viewportWidth = screenWidth;
                    var viewportHeight = screenHeight - 40; // Space for counter
                    
                    // Calculate scale to fill width completely
                    var scaleForWidth = viewportWidth / slideWidth;
                    
                    // Calculate the scaled height
                    var scaledHeight = slideHeight * scaleForWidth;
                    
                    // Center vertically if there's extra space
                    var topOffset = 0;
                    if (scaledHeight < viewportHeight) {{
                        topOffset = (viewportHeight - scaledHeight) / 2;
                    }}
                    
                    // Force wrapper to have no padding and full width
                    wrapper.style.padding = '0';
                    wrapper.style.margin = '0';
                    wrapper.style.width = '100vw';
                    wrapper.style.maxWidth = '100vw';
                    wrapper.style.alignItems = 'flex-start';
                    wrapper.style.justifyContent = 'flex-start';
                    wrapper.style.paddingTop = topOffset + 'px';
                    
                    // Apply scale with left-aligned transform origin for true full-width
                    container.style.width = slideWidth + 'px';
                    container.style.height = slideHeight + 'px';
                    container.style.transform = 'scale(' + scaleForWidth + ')';
                    container.style.transformOrigin = 'left top';
                    container.style.marginLeft = '0';
                    container.style.boxShadow = 'none';
                    
                    console.log('[Scale] Mobile portrait - scale:', scaleForWidth.toFixed(3));
                    return;
                }}
                
                // DESKTOP / LANDSCAPE MODE
                // Reset wrapper styles that might have been modified
                wrapper.style.padding = '';
                wrapper.style.margin = '';
                wrapper.style.width = '';
                wrapper.style.maxWidth = '';
                wrapper.style.alignItems = '';
                wrapper.style.justifyContent = '';
                wrapper.style.paddingTop = '';
                container.style.marginLeft = '';
                container.style.marginRight = '';
                container.style.marginBottom = '';
                container.style.boxShadow = '';
                container.style.transformOrigin = '0 0';
                
                var wrapperRect = wrapper.getBoundingClientRect();
                
                // Use minimal padding on mobile landscape for maximum slide size
                var padding = (isPresentationMode || isMobileLand) ? 10 : 40;
                var availableWidth = wrapperRect.width - padding;
                var availableHeight = wrapperRect.height - padding;
                
                // On mobile landscape, account for the floating controls at bottom
                if (isMobileLand) {{
                    availableHeight -= 70; // Space for mobile float controls
                }}
                
                if (availableWidth < 50 || availableHeight < 50) return;
                
                var scaleX = availableWidth / slideWidth;
                var scaleY = availableHeight / slideHeight;
                var scale = Math.min(scaleX, scaleY);
                
                // Allow higher scale for better visibility
                // No upper limit on mobile landscape - fill the screen!
                var maxScale;
                if (isPresentationMode || isMobileLand) {{
                    maxScale = 5.0; // Virtually no limit
                }} else {{
                    // Allow scale up to 1.5 to accommodate smaller slides
                    maxScale = 1.5;
                }}
                scale = Math.min(scale, maxScale);
                
                container.style.transform = 'scale(' + scale + ')';
                
                // Shrink layout box to match visual size so flexbox centering works
                container.style.marginRight = -(slideWidth * (1 - scale)) + 'px';
                container.style.marginBottom = -(slideHeight * (1 - scale)) + 'px';
            }}
            
            function updateProgress() {{
                var dots = document.getElementById('progress-dots');
                var html = '';
                for (var i = 0; i < totalSlides; i++) {{
                    var cls = 'progress-dot';
                    if (i === currentSlide) cls += ' active';
                    else if (i < currentSlide) cls += ' completed';
                    html += '<div class="' + cls + '" onclick="Player.goTo(' + i + ')"></div>';
                }}
                dots.innerHTML = html;
                
                // Update nav buttons
                document.getElementById('prev-btn').disabled = currentSlide === 0;
                document.getElementById('next-btn').disabled = currentSlide === totalSlides - 1;
                
                // Send LIBRAS script to VLibras for automatic translation
                var currentSlideData = course.slides[currentSlide];
                if (currentSlideData && currentSlideData.librasScript && currentSlideData.librasScript.trim()) {{
                    translateWithVLibras(currentSlideData.librasScript.trim(), currentSlide);
                }}
                
                // Fix YouTube embeds if running locally
                fixYouTubeEmbeds();
            }}
            
            function fixYouTubeEmbeds() {{
                // Check if running from local file
                // YouTube iframes are now rendered directly - no thumbnail click handler needed
            }}
            
            function next() {{
                if (currentSlide < totalSlides - 1) {{
                    renderSlide(currentSlide + 1);
                }}
            }}
            
            function prev() {{
                if (currentSlide > 0) {{
                    renderSlide(currentSlide - 1);
                }}
            }}
            
            function goTo(index) {{
                if (index >= 0 && index < totalSlides) {{
                    renderSlide(index);
                }}
            }}
            
            function toggleSidebar() {{
                sidebarOpen = !sidebarOpen;
                document.getElementById('sidebar').classList.toggle('open', sidebarOpen);
                updateSlideScale();
            }}
            
            function toggleMute() {{
                isMuted = !isMuted;
                var btn = document.getElementById('mute-btn');
                btn.textContent = isMuted ? '🔇' : '🔊';
                
                if (globalAudio) {{
                    globalAudio.volume = isMuted ? 0 : (course.globalAudio.volume || 0.5) * volume;
                }}
                slideAudios.forEach(function(audio) {{
                    if (audio) audio.volume = isMuted ? 0 : volume;
                }});
            }}
            
            function setVolume(val) {{
                volume = val;
                if (globalAudio) {{
                    globalAudio.volume = isMuted ? 0 : (course.globalAudio.volume || 0.5) * volume;
                }}
                slideAudios.forEach(function(audio) {{
                    if (audio) audio.volume = isMuted ? 0 : volume;
                }});
            }}
            
            var isPresentationMode = false;
            
            function fullscreen() {{
                var elem = document.getElementById('player-container');
                if (!document.fullscreenElement) {{
                    // Enter fullscreen and presentation mode
                    elem.requestFullscreen().then(function() {{
                        enterPresentationMode();
                    }}).catch(function() {{
                        // If fullscreen fails, still enter presentation mode
                        enterPresentationMode();
                    }});
                }} else {{
                    document.exitFullscreen().then(function() {{
                        exitPresentationMode();
                    }});
                }}
            }}
            
            function enterPresentationMode() {{
                isPresentationMode = true;
                document.getElementById('header').style.display = 'none';
                document.getElementById('controls').style.display = 'none';
                document.getElementById('slide-wrapper').style.padding = '0';
                document.body.classList.add('presentation-mode');
                
                // Add floating controls
                if (!document.getElementById('floating-controls')) {{
                    var floatDiv = document.createElement('div');
                    floatDiv.id = 'floating-controls';
                    floatDiv.innerHTML = '<button onclick="Player.prev()">←</button>' +
                        '<span id="float-progress"></span>' +
                        '<button onclick="Player.next()">→</button>' +
                        '<button onclick="Player.fullscreen()" style="margin-left:10px;">✕</button>';
                    document.body.appendChild(floatDiv);
                }}
                updateFloatingProgress();
                
                // Update scale for presentation mode
                setTimeout(updateSlideScale, 100);
            }}
            
            function exitPresentationMode() {{
                isPresentationMode = false;
                document.getElementById('header').style.display = 'flex';
                document.getElementById('controls').style.display = 'flex';
                document.getElementById('slide-wrapper').style.padding = '20px';
                document.body.classList.remove('presentation-mode');
                
                var floatDiv = document.getElementById('floating-controls');
                if (floatDiv) floatDiv.remove();
                
                setTimeout(updateSlideScale, 100);
            }}
            
            function updateFloatingProgress() {{
                var floatProgress = document.getElementById('float-progress');
                if (floatProgress) {{
                    floatProgress.textContent = (currentSlide + 1) + ' / ' + totalSlides;
                }}
            }}
            
            // Listen for fullscreen change
            document.addEventListener('fullscreenchange', function() {{
                if (!document.fullscreenElement && isPresentationMode) {{
                    exitPresentationMode();
                }}
            }});
            
            // Initialize on load
            document.addEventListener('DOMContentLoaded', init);
            
            // Portrait orientation check (JS-controlled overlay)
            function checkPortraitOverlay() {{
                var overlay = document.getElementById('orientation-overlay');
                var playerContainer = document.getElementById('player-container');
                if (!overlay || !playerContainer) return;
                
                var isPortrait = window.innerHeight > window.innerWidth;
                var isSmallScreen = Math.min(window.innerWidth, window.innerHeight) < 900;
                var isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) || (isSmallScreen && ('ontouchstart' in window));
                var dismissed = false;
                try {{ dismissed = sessionStorage.getItem('orientation_overlay_dismissed') === 'true'; }} catch(e) {{}}
                
                if (isMobile && isPortrait && !dismissed) {{
                    overlay.style.display = 'flex';
                    playerContainer.style.display = 'none';
                }} else {{
                    overlay.style.display = 'none';
                    playerContainer.style.display = 'flex';
                }}
            }}
            
            document.addEventListener('DOMContentLoaded', function() {{ setTimeout(checkPortraitOverlay, 50); }});
            window.addEventListener('resize', function() {{ setTimeout(checkPortraitOverlay, 200); }});
            window.addEventListener('orientationchange', function() {{ setTimeout(checkPortraitOverlay, 200); }});
            
            return {{
                next: next,
                prev: prev,
                goTo: goTo,
                toggleSidebar: toggleSidebar,
                toggleMute: toggleMute,
                setVolume: setVolume,
                fullscreen: fullscreen,
                startCourse: hideStartOverlay
            }};
        }})();
        
        // QuizController for HTML export
        var QuizController = (function() {{
            var quizzes = {{}};
            var questions = {{}};
            
            function shuffleArray(array) {{
                var shuffled = array.slice();
                for (var i = shuffled.length - 1; i > 0; i--) {{
                    var j = Math.floor(Math.random() * (i + 1));
                    var temp = shuffled[i];
                    shuffled[i] = shuffled[j];
                    shuffled[j] = temp;
                }}
                return shuffled;
            }}
            
            return {{
                init: function(courseData) {{
                    questions = {{}};
                    if (courseData && courseData.questions) {{
                        courseData.questions.forEach(function(q) {{
                            questions[q.id] = q;
                        }});
                    }}
                }},
                
                startQuiz: function(elementId) {{
                    var container = document.querySelector('.quiz-player-container[data-element-id="' + elementId + '"]');
                    if (!container) return;
                    
                    var config = JSON.parse(container.dataset.quizConfig || '{{}}');
                    var questionIds = config.questionIds || [];
                    var quizQuestions = questionIds.map(function(id) {{ return questions[id]; }}).filter(Boolean);
                    
                    if (quizQuestions.length === 0) {{
                        container.innerHTML = '<div style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;background:#1e293b;color:#fbbf24;border-radius:12px;"><span style="font-size:48px;">⚠️</span><p style="margin-left:16px;">Nenhuma questão encontrada</p></div>';
                        return;
                    }}
                    
                    if (config.shuffleQuestions !== false) {{
                        quizQuestions = shuffleArray(quizQuestions);
                    }}
                    
                    var count = Math.min(config.questionCount || quizQuestions.length, quizQuestions.length);
                    quizQuestions = quizQuestions.slice(0, count);
                    
                    if (config.shuffleAlternatives !== false) {{
                        quizQuestions = quizQuestions.map(function(q) {{
                            return Object.assign({{}}, q, {{ alternatives: shuffleArray(q.alternatives || []) }});
                        }});
                    }}
                    
                    quizzes[elementId] = {{
                        config: config,
                        questions: quizQuestions,
                        currentIndex: 0,
                        answers: [],
                        selectedAnswer: null,
                        showingFeedback: false
                    }};
                    
                    this.renderQuestion(elementId);
                }},
                
                renderQuestion: function(elementId) {{
                    var quiz = quizzes[elementId];
                    if (!quiz) return;
                    
                    var container = document.querySelector('.quiz-player-container[data-element-id="' + elementId + '"]');
                    if (!container) return;
                    
                    var question = quiz.questions[quiz.currentIndex];
                    var total = quiz.questions.length;
                    var current = quiz.currentIndex + 1;
                    var progress = (current / total) * 100;
                    
                    var quizTransparent = quiz.config && quiz.config.transparentBackground === true;
                    var quizPlayBg = quizTransparent ? 'transparent' : '#1e293b';
                    var quizFooterBg = quizTransparent ? 'transparent' : '#1e293b';
                    var quizPlayRadius = quizTransparent ? '0' : '12px';
                    var quizQuestionColor = quizTransparent ? '#f8fafc' : '#f1f5f9';
                    var quizQuestionShadow = quizTransparent ? 'text-shadow:0 1px 2px rgba(0,0,0,0.6);' : '';
                    var html = '<style>.quiz-scroll::-webkit-scrollbar{{width:4px;height:4px;}}.quiz-scroll::-webkit-scrollbar-track{{background:transparent;}}.quiz-scroll::-webkit-scrollbar-thumb{{background:rgba(100,116,139,0.4);border-radius:4px;}}.quiz-scroll{{scrollbar-width:thin;scrollbar-color:rgba(100,116,139,0.4) transparent;}}</style>' +
                        '<div style="display:flex;flex-direction:column;height:100%;background:' + quizPlayBg + ';color:#fff;font-family:system-ui,-apple-system,sans-serif;border-radius:' + quizPlayRadius + ';overflow:hidden;">' +
                        '<div style="padding:10px 16px 8px;border-bottom:1px solid #334155;">' +
                        '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">' +
                        '<div style="display:flex;align-items:center;gap:8px;">' +
                        '<span style="font-weight:500;font-size:13px;">' + (quiz.config.title || 'Quiz') + '</span>' +
                        '<span style="padding:2px 6px;font-size:9px;border-radius:3px;font-weight:500;' + 
                        (question.type === 'true_false' ? 'background:rgba(168,85,247,0.15);color:#a78bfa;' : 'background:rgba(6,182,212,0.15);color:#22d3ee;') + '">' +
                        (question.type === 'true_false' ? 'V/F' : 'Múltipla') + '</span></div>' +
                        '<span style="color:#94a3b8;font-size:12px;">' + current + '/' + total + '</span></div>' +
                        '<div style="height:3px;background:#334155;border-radius:2px;overflow:hidden;">' +
                        '<div style="height:100%;width:' + progress + '%;background:#06b6d4;transition:width 0.3s;"></div></div></div>' +
                        '<div class="quiz-scroll" style="flex:1;padding:12px 16px;overflow:auto;">' +
                        '<h3 style="font-size:14px;font-weight:600;margin-bottom:12px;color:' + quizQuestionColor + ';line-height:1.4;' + quizQuestionShadow + '">' + question.text + '</h3>' +
                        '<div style="display:grid;grid-template-columns:repeat(2,1fr);gap:6px;">';
                    
                    question.alternatives.forEach(function(alt) {{
                        var isSelected = quiz.selectedAnswer === alt.id;
                        var isCorrect = alt.isCorrect;
                        var showingFeedback = quiz.showingFeedback;
                        
                        var altStyle = 'padding:8px 10px;border-radius:6px;cursor:pointer;display:flex;align-items:center;gap:8px;transition:all 0.2s;text-align:left;width:100%;';
                        var circleStyle = 'width:20px;height:20px;min-width:20px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:10px;';
                        var textStyle = 'font-size:12px;line-height:1.3;';
                        
                        if (showingFeedback) {{
                            if (isCorrect) {{
                                altStyle += 'background:transparent;border:2px solid #22c55e;';
                                circleStyle += 'background:#22c55e;color:#fff;';
                                textStyle += 'color:#f1f5f9;';
                            }} else if (isSelected && !isCorrect) {{
                                altStyle += 'background:transparent;border:2px solid #ef4444;';
                                circleStyle += 'background:#ef4444;color:#fff;';
                                textStyle += 'color:#94a3b8;';
                            }} else {{
                                altStyle += 'background:transparent;border:2px solid #475569;opacity:0.5;';
                                circleStyle += 'background:#475569;color:#94a3b8;';
                                textStyle += 'color:#94a3b8;';
                            }}
                        }} else if (isSelected) {{
                            altStyle += 'background:transparent;border:2px solid #06b6d4;';
                            circleStyle += 'background:#06b6d4;color:#fff;';
                            textStyle += 'color:#f1f5f9;';
                        }} else {{
                            altStyle += 'background:transparent;border:2px solid #475569;';
                            circleStyle += 'background:#475569;color:#94a3b8;';
                            textStyle += 'color:#cbd5e1;';
                        }}
                        
                        html += '<button style="' + altStyle + '" onclick="QuizController.selectAnswer(\\'' + elementId + '\\', \\'' + alt.id + '\\')" ' + (showingFeedback ? 'disabled' : '') + '>' +
                            '<div style="' + circleStyle + '">' + (showingFeedback && isCorrect ? '✓' : (showingFeedback && isSelected && !isCorrect ? '✕' : '')) + '</div>' +
                            '<span style="flex:1;' + textStyle + '">' + alt.text + '</span></button>';
                    }});
                    
                    html += '</div>';
                    
                    if (quiz.showingFeedback) {{
                        var selectedAlt = question.alternatives.find(function(a) {{ return a.id === quiz.selectedAnswer; }});
                        var correctAlt = question.alternatives.find(function(a) {{ return a.isCorrect; }});
                        var wasCorrect = selectedAlt && selectedAlt.isCorrect;
                        
                        html += '<div style="margin-top:10px;padding:10px 12px;border-radius:6px;' + 
                            (wasCorrect ? 'background:rgba(34,197,94,0.08);border:1px solid rgba(34,197,94,0.25);' : 'background:rgba(239,68,68,0.08);border:1px solid rgba(239,68,68,0.25);') + '">' +
                            '<div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;">' +
                            '<span style="width:18px;height:18px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:10px;' + 
                            (wasCorrect ? 'background:#22c55e;color:#fff;' : 'background:#ef4444;color:#fff;') + '">' + (wasCorrect ? '✓' : '✕') + '</span>' +
                            '<span style="font-weight:600;font-size:12px;' + (wasCorrect ? 'color:#22c55e;' : 'color:#ef4444;') + '">' + (wasCorrect ? 'Correto!' : 'Incorreto') + '</span></div>';
                        
                        if (question.explanation) {{
                            html += '<p style="color:#cbd5e1;font-size:11px;margin:0;line-height:1.4;">' + question.explanation + '</p>';
                        }}
                        if (!wasCorrect && correctAlt) {{
                            html += '<p style="color:#94a3b8;margin-top:4px;font-size:10px;">Correta: <span style="color:#22c55e;font-weight:500;">' + correctAlt.text + '</span></p>';
                        }}
                        html += '</div>';
                    }}
                    
                    html += '</div>' +
                        '<div style="padding:10px 16px;border-top:1px solid #334155;display:flex;justify-content:space-between;align-items:center;background:' + quizFooterBg + ';">' +
                        '<button style="padding:6px 12px;background:transparent;border:none;color:#94a3b8;cursor:pointer;font-size:12px;' + 
                        (quiz.currentIndex === 0 || quiz.showingFeedback ? 'opacity:0.4;cursor:not-allowed;' : '') + '" ' + 
                        (quiz.currentIndex === 0 || quiz.showingFeedback ? 'disabled' : '') + 
                        ' onclick="QuizController.prevQuestion(\\'' + elementId + '\\')">‹ Anterior</button>';
                    
                    if (quiz.showingFeedback) {{
                        if (quiz.currentIndex < total - 1) {{
                            html += '<button style="padding:8px 16px;background:#475569;color:#fff;border:none;border-radius:6px;font-weight:500;font-size:12px;cursor:pointer;" onclick="QuizController.nextQuestion(\\'' + elementId + '\\')">Próxima ›</button>';
                        }} else {{
                            html += '<button style="padding:8px 16px;background:#22c55e;color:#fff;border:none;border-radius:6px;font-weight:500;font-size:12px;cursor:pointer;" onclick="QuizController.showResults(\\'' + elementId + '\\')">Ver Resultado</button>';
                        }}
                    }} else {{
                        html += '<button style="padding:8px 16px;background:#475569;color:#fff;border:none;border-radius:6px;font-weight:500;font-size:12px;cursor:pointer;' + 
                            (!quiz.selectedAnswer ? 'opacity:0.4;cursor:not-allowed;' : '') + '" ' +
                            (!quiz.selectedAnswer ? 'disabled' : '') + 
                            ' onclick="QuizController.confirmAnswer(\\'' + elementId + '\\')">Confirmar ✓</button>';
                    }}
                    
                    html += '</div></div>';
                    container.innerHTML = html;
                }},
                
                selectAnswer: function(elementId, altId) {{
                    var quiz = quizzes[elementId];
                    if (!quiz || quiz.showingFeedback) return;
                    quiz.selectedAnswer = altId;
                    this.renderQuestion(elementId);
                }},
                
                confirmAnswer: function(elementId) {{
                    var quiz = quizzes[elementId];
                    if (!quiz || !quiz.selectedAnswer) return;
                    
                    var question = quiz.questions[quiz.currentIndex];
                    var selectedAlt = question.alternatives.find(function(a) {{ return a.id === quiz.selectedAnswer; }});
                    
                    quiz.answers.push({{
                        questionId: question.id,
                        selectedAlternativeId: quiz.selectedAnswer,
                        isCorrect: selectedAlt && selectedAlt.isCorrect
                    }});
                    
                    if (quiz.config.showFeedback !== false) {{
                        quiz.showingFeedback = true;
                        this.renderQuestion(elementId);
                    }} else {{
                        this.nextQuestion(elementId);
                    }}
                }},
                
                nextQuestion: function(elementId) {{
                    var quiz = quizzes[elementId];
                    if (!quiz) return;
                    
                    quiz.showingFeedback = false;
                    quiz.selectedAnswer = null;
                    
                    if (quiz.currentIndex < quiz.questions.length - 1) {{
                        quiz.currentIndex++;
                        this.renderQuestion(elementId);
                    }} else {{
                        this.showResults(elementId);
                    }}
                }},
                
                prevQuestion: function(elementId) {{
                    var quiz = quizzes[elementId];
                    if (!quiz || quiz.currentIndex === 0 || quiz.showingFeedback) return;
                    
                    quiz.currentIndex--;
                    quiz.selectedAnswer = quiz.answers[quiz.currentIndex] ? quiz.answers[quiz.currentIndex].selectedAlternativeId : null;
                    quiz.answers.pop();
                    this.renderQuestion(elementId);
                }},
                
                showResults: function(elementId) {{
                    var quiz = quizzes[elementId];
                    if (!quiz) return;
                    
                    var container = document.querySelector('.quiz-player-container[data-element-id="' + elementId + '"]');
                    if (!container) return;
                    
                    var correctCount = quiz.answers.filter(function(a) {{ return a.isCorrect; }}).length;
                    var totalCount = quiz.answers.length;
                    var percentage = totalCount > 0 ? (correctCount / totalCount) * 100 : 0;
                    var score = Math.round(percentage) / 10;
                    var passed = percentage >= (quiz.config.passingScore || 60);
                    
                    var quizTransparent = quiz.config && quiz.config.transparentBackground === true;
                    var quizResultsOuterBg = quizTransparent ? 'transparent' : 'linear-gradient(135deg,#1e293b,#0f172a)';
                    var quizResultsRadius = quizTransparent ? '0' : '12px';
                    var html = '<style>.quiz-scroll::-webkit-scrollbar{{width:4px;}}.quiz-scroll::-webkit-scrollbar-thumb{{background:rgba(100,116,139,0.4);border-radius:4px;}}.quiz-scroll{{scrollbar-width:thin;}}</style>' +
                        '<div class="quiz-scroll" style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;padding:16px;background:' + quizResultsOuterBg + ';color:#fff;overflow:auto;border-radius:' + quizResultsRadius + ';">' +
                        '<div style="max-width:360px;width:100%;background:#0f172a;border-radius:12px;padding:20px;text-align:center;">' +
                        '<div style="width:60px;height:60px;margin:0 auto 12px;border-radius:50%;display:flex;align-items:center;justify-content:center;' +
                        (passed ? 'background:rgba(34,197,94,0.2);' : 'background:rgba(239,68,68,0.2);') + '">' +
                        '<span style="font-size:32px;">' + (passed ? '🏆' : '⚠️') + '</span></div>' +
                        '<h2 style="font-size:20px;font-weight:bold;margin-bottom:4px;">' + (passed ? 'Parabéns!' : 'Não foi dessa vez') + '</h2>' +
                        '<p style="color:#94a3b8;font-size:13px;margin-bottom:16px;">' + (passed ? 'Você atingiu a nota mínima' : 'Tente novamente para melhorar') + '</p>' +
                        '<div style="margin-bottom:16px;">' +
                        '<div style="font-size:48px;font-weight:bold;line-height:1;' + (passed ? 'color:#22c55e;' : 'color:#ef4444;') + '">' + score.toFixed(1) + '</div>' +
                        '<p style="color:#94a3b8;font-size:12px;margin-top:4px;">de 10</p></div>' +
                        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px;padding:12px;background:#1e293b;border-radius:8px;">' +
                        '<div><p style="font-size:20px;font-weight:bold;color:#22c55e;margin:0;">' + correctCount + '</p><p style="font-size:11px;color:#94a3b8;margin:2px 0 0;">Corretas</p></div>' +
                        '<div><p style="font-size:20px;font-weight:bold;color:#ef4444;margin:0;">' + (totalCount - correctCount) + '</p><p style="font-size:11px;color:#94a3b8;margin:2px 0 0;">Incorretas</p></div></div>' +
                        '<div style="margin-bottom:16px;">' +
                        '<div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:4px;"><span>Aproveitamento</span><span>' + Math.round(percentage) + '%</span></div>' +
                        '<div style="height:8px;background:#334155;border-radius:4px;overflow:hidden;">' +
                        '<div style="height:100%;width:' + percentage + '%;' + (passed ? 'background:#22c55e;' : 'background:#ef4444;') + '"></div></div>' +
                        '<p style="font-size:11px;color:#94a3b8;margin-top:4px;">Nota mínima: ' + (quiz.config.passingScore || 60) + '%</p></div>' +
                        '<button style="width:100%;padding:10px 20px;background:linear-gradient(135deg,#06b6d4,#8b5cf6);color:#fff;border:none;border-radius:8px;font-size:14px;font-weight:600;cursor:pointer;" onclick="QuizController.restartQuiz(\\'' + elementId + '\\')">🔄 Tentar Novamente</button>' +
                        '</div></div>';
                    
                    container.innerHTML = html;
                }},
                
                restartQuiz: function(elementId) {{
                    var quiz = quizzes[elementId];
                    if (!quiz) return;
                    
                    quiz.currentIndex = 0;
                    quiz.answers = [];
                    quiz.selectedAnswer = null;
                    quiz.showingFeedback = false;
                    
                    if (quiz.config.shuffleQuestions !== false) {{
                        quiz.questions = shuffleArray(quiz.questions);
                    }}
                    if (quiz.config.shuffleAlternatives !== false) {{
                        quiz.questions = quiz.questions.map(function(q) {{
                            return Object.assign({{}}, q, {{ alternatives: shuffleArray(q.alternatives || []) }});
                        }});
                    }}
                    
                    this.renderQuestion(elementId);
                }}
            }};
        }})();
        
        // Initialize QuizController with course data
        document.addEventListener('DOMContentLoaded', function() {{
            if (typeof courseData !== 'undefined' && courseData.questions) {{
                QuizController.init(courseData);
                console.log('QuizController initialized with ' + courseData.questions.length + ' questions');
            }} else {{
                console.log('QuizController: no quiz questions in this course');
            }}
        }});

        // ScenarioController for interactive scenario playback in exports
        var ScenarioController = (function() {{
            var scenarios = {{}};

            return {{
                startScenario: function(elementId) {{
                    var container = document.querySelector('.scenario-player-container[data-element-id="' + elementId + '"]');
                    if (!container) return;
                    var data = (window.__scenarioDataMap && window.__scenarioDataMap[elementId]) || null;
                    if (!data) {{ console.error('[ScenarioController] No scenario data for:', elementId); return; }}
                    var nodesMap = {{}};
                    var maxPoints = 0;
                    (data.nodes || []).forEach(function(n) {{
                        nodesMap[n.id] = n;
                        if (!n.is_ending && n.choices && n.choices.length > 0) {{
                            var best = 0;
                            n.choices.forEach(function(c) {{ if ((c.points || 0) > best) best = c.points || 0; }});
                            maxPoints += best;
                        }}
                    }});
                    scenarios[elementId] = {{
                        data: data,
                        nodesMap: nodesMap,
                        currentNodeId: data.start_node_id || (data.nodes && data.nodes[0] ? data.nodes[0].id : null),
                        history: [],
                        totalPoints: 0,
                        optimalCount: 0,
                        totalDecisions: 0,
                        maxPoints: maxPoints || 1,
                        container: container
                    }};
                    this.renderNode(elementId);
                }},

                renderNode: function(elementId) {{
                    var sc = scenarios[elementId];
                    if (!sc) return;
                    var node = sc.nodesMap[sc.currentNodeId];
                    if (!node) return;

                    if (node.is_ending) {{
                        this.renderEnding(elementId, node);
                        return;
                    }}

                    var iconColor = '#22d3ee';
                    var html = '<div style="display:flex;flex-direction:column;height:100%;background:linear-gradient(180deg,#0f172a,#1e293b);border-radius:12px;overflow:hidden;">';
                    // Header
                    html += '<div style="display:flex;align-items:center;justify-content:space-between;padding:8px 16px;background:rgba(30,41,59,0.8);border-bottom:1px solid rgba(51,65,85,0.5);">';
                    html += '<div style="display:flex;align-items:center;gap:8px;"><svg style="width:16px;height:16px;color:' + iconColor + ';" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M6 3v12"/><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M18 9a9 9 0 0 1-9 9"/></svg>';
                    html += '<span style="font-size:12px;color:#cbd5e1;font-weight:500;">' + (sc.data.title || 'Cenário') + '</span></div>';
                    html += '<div style="display:flex;align-items:center;gap:12px;">';
                    html += '<span style="font-size:11px;color:#64748b;">Cena ' + (sc.history.length + 1) + '</span>';
                    html += '<span style="font-size:11px;color:#fbbf24;">★ ' + sc.optimalCount + '/' + sc.totalDecisions + '</span>';
                    html += '</div></div>';
                    // Content
                    html += '<div style="flex:1;overflow-y:auto;padding:16px;">';
                    if (node.character_speaking) {{
                        html += '<div style="display:flex;align-items:center;gap:8px;margin-bottom:12px;">';
                        html += '<div style="width:28px;height:28px;border-radius:50%;background:linear-gradient(135deg,#06b6d4,#2563eb);display:flex;align-items:center;justify-content:center;flex-shrink:0;">';
                        html += '<svg style="width:14px;height:14px;color:#fff;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg></div>';
                        html += '<span style="font-size:12px;font-weight:500;color:#67e8f9;">' + node.character_speaking + '</span></div>';
                    }}
                    html += '<h3 style="font-size:16px;font-weight:600;color:#fff;margin-bottom:8px;">' + (node.title || '') + '</h3>';
                    html += '<p style="font-size:14px;color:#cbd5e1;line-height:1.6;margin-bottom:16px;white-space:pre-line;">' + (node.narrative || '') + '</p>';
                    // Choices
                    if (node.choices && node.choices.length > 0) {{
                        html += '<p style="font-size:12px;color:#64748b;margin-bottom:8px;font-weight:500;">O que você faria?</p>';
                        node.choices.forEach(function(choice, idx) {{
                            var letter = String.fromCharCode(65 + idx);
                            html += '<button onclick="ScenarioController.selectChoice(\\'' + elementId + '\\',\\'' + choice.id + '\\')" style="display:flex;align-items:center;gap:8px;width:100%;text-align:left;padding:10px 12px;margin-bottom:8px;border-radius:8px;border:1px solid rgba(51,65,85,0.5);background:rgba(30,41,59,0.5);color:#e2e8f0;font-size:13px;cursor:pointer;transition:all 0.2s;" onmouseover="this.style.background=\\'rgba(51,65,85,0.7)\\';this.style.borderColor=\\'rgba(34,211,238,0.4)\\';" onmouseout="this.style.background=\\'rgba(30,41,59,0.5)\\';this.style.borderColor=\\'rgba(51,65,85,0.5)\\';">';
                            html += '<span style="width:24px;height:24px;border-radius:50%;background:#334155;display:flex;align-items:center;justify-content:center;flex-shrink:0;font-size:11px;font-weight:bold;color:#94a3b8;">' + letter + '</span>';
                            html += '<span style="flex:1;">' + (choice.text || '') + '</span>';
                            html += '<span style="color:#475569;font-size:16px;">›</span></button>';
                        }});
                    }}
                    html += '</div></div>';
                    sc.container.innerHTML = html;
                }},

                selectChoice: function(elementId, choiceId) {{
                    var sc = scenarios[elementId];
                    if (!sc) return;
                    var node = sc.nodesMap[sc.currentNodeId];
                    if (!node) return;
                    var choice = node.choices.find(function(c) {{ return c.id === choiceId; }});
                    if (!choice) return;
                    sc.totalPoints += (choice.points || 0);
                    sc.totalDecisions += 1;
                    if (choice.is_optimal) sc.optimalCount += 1;
                    this.renderFeedback(elementId, choice);
                }},

                renderFeedback: function(elementId, choice) {{
                    var sc = scenarios[elementId];
                    if (!sc) return;
                    var fbColor = choice.is_optimal ? '#10b981' : '#f59e0b';
                    var fbBg = choice.is_optimal ? 'rgba(16,185,129,0.1)' : 'rgba(245,158,11,0.1)';
                    var fbBorder = choice.is_optimal ? 'rgba(16,185,129,0.3)' : 'rgba(245,158,11,0.3)';
                    var fbLabel = choice.is_optimal ? 'Excelente escolha!' : 'Considere outras perspectivas';
                    var fbIcon = choice.is_optimal ? '✓' : '⚠';

                    var html = '<div style="display:flex;flex-direction:column;height:100%;background:linear-gradient(180deg,#0f172a,#1e293b);border-radius:12px;overflow:hidden;padding:16px;">';
                    html += '<div style="padding:10px 12px;border-radius:8px;background:rgba(51,65,85,0.4);border:1px solid rgba(51,65,85,0.4);margin-bottom:12px;">';
                    html += '<p style="font-size:11px;color:#64748b;margin-bottom:4px;">Sua escolha:</p>';
                    html += '<p style="font-size:13px;color:#fff;">' + (choice.text || '') + '</p></div>';
                    html += '<div style="padding:10px 12px;border-radius:8px;background:' + fbBg + ';border:1px solid ' + fbBorder + ';margin-bottom:12px;">';
                    html += '<div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;">';
                    html += '<span style="color:' + fbColor + ';font-size:14px;">' + fbIcon + '</span>';
                    html += '<span style="font-size:12px;font-weight:500;color:' + fbColor + ';">' + fbLabel + '</span>';
                    if (choice.points > 0) html += '<span style="margin-left:auto;font-size:11px;color:#fbbf24;">+' + choice.points + ' pts</span>';
                    html += '</div>';
                    html += '<p style="font-size:13px;color:#cbd5e1;line-height:1.5;">' + (choice.feedback || '') + '</p></div>';
                    html += '<button onclick="ScenarioController.proceed(\\'' + elementId + '\\',\\'' + (choice.next_node_id || '') + '\\')" style="width:100%;padding:10px 20px;background:linear-gradient(135deg,#0891b2,#2563eb);color:#fff;border:none;border-radius:8px;font-size:14px;font-weight:600;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:8px;">Continuar →</button>';
                    html += '</div>';
                    sc.container.innerHTML = html;
                }},

                proceed: function(elementId, nextNodeId) {{
                    var sc = scenarios[elementId];
                    if (!sc) return;
                    sc.history.push(sc.currentNodeId);
                    if (nextNodeId && sc.nodesMap[nextNodeId]) {{
                        sc.currentNodeId = nextNodeId;
                        this.renderNode(elementId);
                    }} else {{
                        // Ended without explicit ending node
                        this.renderEnding(elementId, sc.nodesMap[sc.currentNodeId] || {{}});
                    }}
                }},

                renderEnding: function(elementId, node) {{
                    var sc = scenarios[elementId];
                    if (!sc) return;
                    var calcScore = sc.totalDecisions > 0 
                        ? Math.round((sc.optimalCount / sc.totalDecisions) * 100) 
                        : 0;
                    var endColor = calcScore >= 80 ? '#10b981' : calcScore >= 50 ? '#f59e0b' : '#ef4444';
                    var endIcon = calcScore >= 80 ? '🏆' : calcScore >= 50 ? '⚠' : '✗';

                    var html = '<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;background:linear-gradient(180deg,#0f172a,#1e293b);border-radius:12px;padding:24px;text-align:center;">';
                    html += '<div style="font-size:48px;margin-bottom:12px;">' + endIcon + '</div>';
                    html += '<h2 style="font-size:20px;font-weight:bold;color:' + endColor + ';margin-bottom:8px;">' + (node.title || 'Fim') + '</h2>';
                    html += '<p style="font-size:14px;color:#cbd5e1;max-width:400px;line-height:1.6;margin-bottom:16px;">' + (node.narrative || '') + '</p>';
                    html += '<div style="display:flex;align-items:center;gap:8px;background:rgba(51,65,85,0.5);padding:8px 16px;border-radius:999px;margin-bottom:8px;">';
                    html += '<span style="color:#fbbf24;">★</span><span style="color:#fff;font-weight:600;">Pontuação: ' + calcScore + '%</span></div>';
                    html += '<div style="display:flex;flex-direction:column;align-items:center;gap:4px;margin-bottom:16px;">';
                    html += '<span style="font-size:12px;color:#94a3b8;">Decisões ideais: ' + sc.optimalCount + ' de ' + sc.totalDecisions + '</span>';
                    html += '</div>';
                    html += '<button onclick="ScenarioController.startScenario(\\'' + elementId + '\\')" style="padding:10px 20px;background:transparent;border:1px solid rgba(34,211,238,0.5);color:#22d3ee;border-radius:8px;font-size:14px;cursor:pointer;">↻ Tentar Novamente</button>';
                    html += '</div>';
                    sc.container.innerHTML = html;
                }}
            }};
        }})();
    </script>
    {vlibras_block}
    {_generate_tutor_block(tutor_config)}
</body>
</html>'''
    
    return html
