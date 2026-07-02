"""
SCORM 1.2 Exporter Service
Generates SCORM 1.2 compliant packages
"""
import os
import json
import zipfile
import logging
import re
import base64
import httpx
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
import shutil

from models import Course, Project

logger = logging.getLogger(__name__)

# Directory containing export asset files (JS, CSS, HTML template)
EXPORT_ASSETS_DIR = Path(__file__).parent / "export_assets"
# Global storage directory (parent of services/ → backend/, then storage/)
STORAGE_DIR = Path(__file__).parent.parent / "storage"


class DateTimeEncoder(json.JSONEncoder):
    """JSON Encoder that handles datetime objects"""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


def _read_image_as_data_uri(project_id: str, filename: str, package_assets_dir: Path) -> Optional[str]:
    """Read an image file and return it as a base64 data URI.
    Tries: 1) package assets dir, 2) global storage/assets, 3) MongoDB.
    Returns None if the image cannot be found."""
    
    # Determine content type
    ext = Path(filename).suffix.lower()
    content_types = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', 
                     '.gif': 'image/gif', '.webp': 'image/webp', '.svg': 'image/svg+xml'}
    content_type = content_types.get(ext, 'image/png')
    
    # Try 1: Read from package assets directory (local file)
    local_path = package_assets_dir / filename
    if local_path.exists():
        try:
            with open(local_path, 'rb') as f:
                data = f.read()
            b64 = base64.b64encode(data).decode('ascii')
            logger.info(f"Embedded image as data URI from local file: {filename} ({len(data)} bytes)")
            return f"data:{content_type};base64,{b64}"
        except Exception as e:
            logger.warning(f"Failed to read local file {filename}: {e}")
    
    # Try 2: Read from global assets directory (AI-generated images)
    global_assets_path = STORAGE_DIR / "assets" / filename
    if global_assets_path.exists():
        try:
            with open(global_assets_path, 'rb') as f:
                data = f.read()
            # Also copy to package assets for file-based references
            try:
                package_assets_dir.mkdir(parents=True, exist_ok=True)
                with open(package_assets_dir / filename, 'wb') as out:
                    out.write(data)
            except Exception:
                pass
            b64 = base64.b64encode(data).decode('ascii')
            logger.info(f"Embedded image as data URI from global assets: {filename} ({len(data)} bytes)")
            return f"data:{content_type};base64,{b64}"
        except Exception as e:
            logger.warning(f"Failed to read global asset {filename}: {e}")
    
    # Try 3: Read from MongoDB (project-specific assets)
    try:
        from services.asset_store import retrieve_asset_sync
        mongo_url = os.environ.get('MONGO_URL')
        db_name = os.environ.get('DB_NAME')
        if mongo_url and db_name:
            # Try to restore to filesystem first
            dest = str(local_path)
            if retrieve_asset_sync(mongo_url, db_name, project_id, filename, dest):
                with open(dest, 'rb') as f:
                    data = f.read()
                b64 = base64.b64encode(data).decode('ascii')
                logger.info(f"Embedded image as data URI from MongoDB: {filename} ({len(data)} bytes)")
                return f"data:{content_type};base64,{b64}"
    except Exception as e:
        logger.warning(f"MongoDB fallback failed for {filename}: {e}")
    
    # Try 4: Read from MongoDB global assets (AI-generated images)
    try:
        from pymongo import MongoClient as SyncMongoClient
        mongo_url = os.environ.get('MONGO_URL')
        db_name = os.environ.get('DB_NAME')
        if mongo_url and db_name:
            _client = SyncMongoClient(mongo_url, serverSelectionTimeoutMS=30000, connectTimeoutMS=30000)
            _db = _client[db_name]
            doc = _db.project_assets.find_one(
                {"project_id": "global", "filename": filename},
                {"_id": 0, "data": 1}
            )
            _client.close()
            if doc and doc.get("data"):
                img_data = doc["data"]
                # Also save to disk for future use
                try:
                    global_assets_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(global_assets_path, 'wb') as f:
                        f.write(img_data)
                except Exception:
                    pass
                b64 = base64.b64encode(img_data).decode('ascii')
                logger.info(f"Embedded image as data URI from MongoDB global: {filename} ({len(img_data)} bytes)")
                return f"data:{content_type};base64,{b64}"
    except Exception as e:
        logger.warning(f"MongoDB global fallback failed for {filename}: {e}")
    
    logger.error(f"Could not find image anywhere: {filename} for project {project_id}")
    return None


def _read_asset(filename: str) -> str:
    """Read an export asset file from the export_assets directory."""
    return (EXPORT_ASSETS_DIR / filename).read_text(encoding='utf-8')


def _build_html(
    title: str, lang: str, width: int, height: int,
    enable_vlibras: bool = True, backend_url: str = "",
    gamification_config: dict = None,
    loader_title: str = "Carregando curso…",
    loader_primary: str = "#3b82f6",
    loader_accent: str = "#60a5fa",
) -> str:
    """Build the index.html by reading the template and CSS, replacing placeholders."""
    template = _read_asset("player_template.html")
    css = _read_asset("player.css")

    # Replace dimension placeholders in CSS
    css = css.replace("__SLIDE_WIDTH__", str(width))
    css = css.replace("__SLIDE_HEIGHT__", str(height))

    # Inject CSS into template
    html = template.replace("__CSS_CONTENT__", css)

    # Replace remaining placeholders
    html = html.replace("__TITLE__", title)
    html = html.replace("__LANG__", lang)
    html = html.replace("__SLIDE_WIDTH__", str(width))
    html = html.replace("__SLIDE_HEIGHT__", str(height))
    # Branded loader placeholders. Title is HTML-escaped before reaching
    # us, so it's safe to drop straight in.
    html = html.replace("__LOADER_TITLE__", loader_title)
    html = html.replace("__LOADER_PRIMARY__", loader_primary)
    html = html.replace("__LOADER_ACCENT__", loader_accent)
    
    # Conditionally include VLibras
    if enable_vlibras:
        proxy_base = backend_url.rstrip('/') + '/api/vlibras-proxy' if backend_url else ''
        vlibras_block = f'''<!-- VLibras - Acessibilidade em LIBRAS -->
    <script>
        // CORS proxy for VLibras servers - intercept XHR to dicionario2 and traducao2
        (function() {{
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
                                var newUrl = _domainMap[domain] + u.pathname + u.search;
                                console.log("[VLibras Proxy] " + method + " " + domain + u.pathname + " -> proxy");
                                arguments[1] = newUrl;
                            }} catch(e) {{ console.warn("[VLibras Proxy] URL parse error:", e); }}
                            break;
                        }}
                    }}
                }}
                return _origOpen.apply(this, arguments);
            }};
        }})();
    </script>
    <div vw class="enabled">
        <div vw-access-button class="active"></div>
        <div vw-plugin-wrapper>
            <div class="vw-plugin-top-wrapper"></div>
        </div>
    </div>
    <script src="https://vlibras.gov.br/app/vlibras-plugin.js"></script>
    <script>
        new window.VLibras.Widget({{ position: "R", avatar: "random" }});
        // Auto-initialize VLibras plugin for programmatic LIBRAS translation
        window.addEventListener("load", function() {{
            setTimeout(function() {{
                var accessBtn = document.querySelector("[vw-access-button]");
                if (accessBtn && !window.plugin) {{
                    console.log("[VLibras] Auto-clicking access button to initialize plugin...");
                    accessBtn.click();
                }}
            }}, 2000);
        }});
    </script>'''
        html = html.replace("__VLIBRAS_BLOCK__", vlibras_block)
    else:
        html = html.replace("__VLIBRAS_BLOCK__", "")
    
    # Add gamification script and config
    if gamification_config and gamification_config.get('enabled'):
        import json
        gamification_block = f'''<!-- Gamification Engine -->
    <script src="scripts/gamification.js"></script>
    <script>
        var GAMIFICATION_CONFIG = {json.dumps(gamification_config, ensure_ascii=False)};
        document.addEventListener('DOMContentLoaded', function() {{
            Gamification.init(GAMIFICATION_CONFIG);
        }});
    </script>'''
        html = html.replace("</body>", gamification_block + "\n</body>")

    return html

IMS_MANIFEST_TEMPLATE = '''<?xml version="1.0" encoding="UTF-8"?>
<manifest identifier="{identifier}" version="1.0"
    xmlns="http://www.imsproject.org/xsd/imscp_rootv1p1p2"
    xmlns:adlcp="http://www.adlnet.org/xsd/adlcp_rootv1p2"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://www.imsproject.org/xsd/imscp_rootv1p1p2 imscp_rootv1p1p2.xsd
                        http://www.imsglobal.org/xsd/imsmd_rootv1p2p1 imsmd_rootv1p2p1.xsd
                        http://www.adlnet.org/xsd/adlcp_rootv1p2 adlcp_rootv1p2.xsd">
    <metadata>
        <schema>ADL SCORM</schema>
        <schemaversion>1.2</schemaversion>
    </metadata>
    <organizations default="org1">
        <organization identifier="org1">
            <title>{title}</title>
            <item identifier="item1" identifierref="resource1">
                <title>{title}</title>
                <adlcp:masteryscore>80</adlcp:masteryscore>
            </item>
        </organization>
    </organizations>
    <resources>
        <resource identifier="resource1" type="webcontent" adlcp:scormtype="sco" href="index.html">
            <file href="index.html"/>
            <file href="course.json"/>
            <file href="scripts/scorm-api.js"/>
            <file href="scripts/quiz-controller.js"/>
            <file href="scripts/scenario-controller.js"/>
            <file href="scripts/player.js"/>
            <file href="scripts/tutor.js"/>
            <file href="styles/tutor.css"/>
            {resource_files}
        </resource>
    </resources>
</manifest>'''


# XSD files content (minimal valid XSD for SCORM 1.2)
ADLCP_XSD = '''<?xml version="1.0" encoding="UTF-8"?>
<xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema"
    targetNamespace="http://www.adlnet.org/xsd/adlcp_rootv1p2"
    xmlns="http://www.adlnet.org/xsd/adlcp_rootv1p2"
    elementFormDefault="qualified">
    <xsd:attribute name="scormtype">
        <xsd:simpleType>
            <xsd:restriction base="xsd:string">
                <xsd:enumeration value="sco"/>
                <xsd:enumeration value="asset"/>
            </xsd:restriction>
        </xsd:simpleType>
    </xsd:attribute>
    <xsd:element name="masteryscore" type="xsd:string"/>
</xsd:schema>'''

IMS_XML_XSD = '''<?xml version="1.0" encoding="UTF-8"?>
<xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema"
    targetNamespace="http://www.w3.org/XML/1998/namespace"
    xml:lang="en">
    <xsd:attribute name="lang" type="xsd:language"/>
</xsd:schema>'''

IMSCP_XSD = '''<?xml version="1.0" encoding="UTF-8"?>
<xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema"
    targetNamespace="http://www.imsproject.org/xsd/imscp_rootv1p1p2"
    xmlns="http://www.imsproject.org/xsd/imscp_rootv1p1p2"
    elementFormDefault="qualified">
    <xsd:element name="manifest"/>
    <xsd:element name="organizations"/>
    <xsd:element name="organization"/>
    <xsd:element name="item"/>
    <xsd:element name="resources"/>
    <xsd:element name="resource"/>
    <xsd:element name="file"/>
    <xsd:element name="metadata"/>
    <xsd:element name="title" type="xsd:string"/>
    <xsd:element name="schema" type="xsd:string"/>
    <xsd:element name="schemaversion" type="xsd:string"/>
</xsd:schema>'''

IMSMD_XSD = '''<?xml version="1.0" encoding="UTF-8"?>
<xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema"
    targetNamespace="http://www.imsglobal.org/xsd/imsmd_rootv1p2p1"
    xmlns="http://www.imsglobal.org/xsd/imsmd_rootv1p2p1"
    elementFormDefault="qualified">
    <xsd:element name="lom"/>
    <xsd:element name="general"/>
    <xsd:element name="title"/>
    <xsd:element name="langstring" type="xsd:string"/>
</xsd:schema>'''

def export_scorm_package(project: Project, storage_dir: str, output_dir: str, questions: list = None, tutor_config: dict = None, backend_url: str = "", gamification_config: dict = None) -> str:
    """
    Export a project as a SCORM 1.2 package
    Returns the path to the generated ZIP file
    
    Args:
        project: Project model
        storage_dir: Path to storage directory
        output_dir: Path to output directory
        questions: Optional list of quiz questions to include
        tutor_config: Optional AI tutor configuration dict
        gamification_config: Optional gamification configuration dict
    """
    logger.info(f"Exporting SCORM package for project: {project.id}")
    
    course = project.course
    
    # Create temp directory for package
    package_dir = Path(output_dir) / f"scorm_{project.id}"
    package_dir.mkdir(parents=True, exist_ok=True)
    
    # Create directory structure
    (package_dir / "assets").mkdir(exist_ok=True)
    (package_dir / "resources").mkdir(exist_ok=True)
    (package_dir / "scripts").mkdir(exist_ok=True)
    
    # Copy assets from storage
    project_assets = Path(storage_dir) / project.id / "assets"
    logger.info(f"Looking for project assets in: {project_assets}")
    if project_assets.exists():
        asset_count = 0
        for asset in project_assets.iterdir():
            if asset.is_dir():
                continue
            shutil.copy2(asset, package_dir / "assets" / asset.name)
            asset_count += 1
            logger.info(f"Copied asset: {asset.name}")
        logger.info(f"Total project assets copied: {asset_count}")
    else:
        logger.warning(f"Project assets directory does not exist: {project_assets}")
    
    # Restore missing assets from MongoDB (production environments with ephemeral storage)
    try:
        from services.asset_store import restore_project_assets_sync
        mongo_url = os.environ.get('MONGO_URL')
        db_name = os.environ.get('DB_NAME')
        if mongo_url and db_name:
            restored = restore_project_assets_sync(
                mongo_url, db_name, project.id, str(package_dir / "assets")
            )
            if restored > 0:
                logger.info(f"Restored {restored} missing assets from MongoDB for SCORM package")
    except Exception as e:
        logger.warning(f"Failed to restore assets from MongoDB (non-fatal): {e}")
    
    # Collect gallery images from other referenced projects
    import re as _re
    referenced_project_ids = set()
    course_data_pre = course.model_dump()
    for slide in (course_data_pre.get('slides') or []):
        if not isinstance(slide, dict):
            continue
        for element in (slide.get('elements') or []):
            if not isinstance(element, dict):
                continue
            elem_src = element.get('src') or ''
            if elem_src and '/api/projects/' in elem_src:
                pid_match = _re.search(r'/api/projects/([^/]+)/assets/', elem_src)
                if pid_match and pid_match.group(1) != project.id:
                    referenced_project_ids.add(pid_match.group(1))
        bg = slide.get('backgroundImage') or ''
        if bg and '/api/projects/' in bg:
            pid_match = _re.search(r'/api/projects/([^/]+)/assets/', bg)
            if pid_match and pid_match.group(1) != project.id:
                referenced_project_ids.add(pid_match.group(1))
    
    if referenced_project_ids:
        logger.info(f"Found gallery images from {len(referenced_project_ids)} other project(s), collecting assets...")
        for ref_pid in referenced_project_ids:
            ref_assets = Path(storage_dir) / ref_pid / "assets"
            if ref_assets.exists():
                for asset in ref_assets.iterdir():
                    if asset.is_dir():
                        continue
                    dest = package_dir / "assets" / asset.name
                    if not dest.exists():
                        shutil.copy2(asset, dest)
                        logger.info(f"Copied gallery asset from project {ref_pid}: {asset.name}")
            # Also restore from MongoDB
            try:
                if mongo_url and db_name:
                    restored = restore_project_assets_sync(
                        mongo_url, db_name, ref_pid, str(package_dir / "assets")
                    )
                    if restored > 0:
                        logger.info(f"Restored {restored} gallery assets from MongoDB for project {ref_pid}")
            except Exception as e:
                logger.warning(f"Failed to restore gallery assets for {ref_pid}: {e}")
    
    # Also copy global assets (AI-generated images are stored here)
    # storage_dir points to /storage/projects, so parent is /storage
    storage_base = Path(storage_dir).parent
    global_assets = storage_base / "assets"
    logger.info(f"Looking for global assets in: {global_assets}")
    if global_assets.exists():
        global_count = 0
        for asset in global_assets.iterdir():
            dest_path = package_dir / "assets" / asset.name
            if not dest_path.exists():  # Avoid overwriting project assets
                shutil.copy2(asset, dest_path)
                global_count += 1
                logger.info(f"Copied global asset (AI image): {asset.name}")
        logger.info(f"Total global assets copied: {global_count}")
    else:
        logger.warning(f"Global assets directory does not exist: {global_assets}")

    # Copy pre-extracted COMPANY brand assets (logos, watermarks, BrandKit
    # backgrounds). These were materialized by `prepare_company_assets_for_export`
    # into `<project_assets>/_companies/<asset_id>.<ext>` before this exporter
    # was invoked. We copy them into the SCORM package and rewrite every
    # `/api/companies/<cid>/assets/<aid>/file` URL in the generated HTML to
    # point to the local file. Without this, offline LMS playback shows
    # broken image icons.
    _company_url_to_local: dict = {}
    src_companies = Path(storage_dir) / project.id / "assets" / "_companies"
    if src_companies.exists() and src_companies.is_dir():
        dest_companies = package_dir / "assets" / "_companies"
        dest_companies.mkdir(exist_ok=True)
        company_count = 0
        for asset_file in src_companies.iterdir():
            if not asset_file.is_file():
                continue
            shutil.copy2(asset_file, dest_companies / asset_file.name)
            company_count += 1
            # Map asset_id (filename stem) → local relative URL
            asset_id = asset_file.stem
            _company_url_to_local[asset_id] = f"assets/_companies/{asset_file.name}"
        logger.info(f"Copied {company_count} company brand assets")
    else:
        logger.info(
            "No pre-extracted company assets found — brand images will be "
            "kept as live URLs (may break offline)"
        )
    
    # Write scripts (read from export_assets directory)
    with open(package_dir / "scripts" / "scorm-api.js", 'w') as f:
        f.write(_read_asset("scorm-api.js"))
    
    with open(package_dir / "scripts" / "player.js", 'w') as f:
        f.write(_read_asset("player.js"))
    
    # Write quiz controller script
    with open(package_dir / "scripts" / "quiz-controller.js", 'w') as f:
        f.write(_read_asset("quiz-controller.js"))
    
    # Write scenario controller script
    with open(package_dir / "scripts" / "scenario-controller.js", 'w') as f:
        f.write(_read_asset("scenario-controller.js"))
    
    # Write AI tutor files if tutor is enabled
    if tutor_config and tutor_config.get('enabled'):
        (package_dir / "styles").mkdir(exist_ok=True)
        with open(package_dir / "scripts" / "tutor.js", 'w') as f:
            f.write(_read_asset("tutor.js"))
        with open(package_dir / "styles" / "tutor.css", 'w') as f:
            f.write(_read_asset("tutor.css"))
    
    # Write gamification files if enabled
    if gamification_config and gamification_config.get('enabled'):
        with open(package_dir / "scripts" / "gamification.js", 'w') as f:
            f.write(_read_asset("gamification.js"))
    
    # Prepare course.json - Fix asset URLs for SCORM package
    course_data = course.model_dump()
    
    # Convert datetime to string
    course_data['createdAt'] = course.createdAt.isoformat() if course.createdAt else None
    course_data['updatedAt'] = course.updatedAt.isoformat() if course.updatedAt else None
    
    # Fix all asset URLs in slides - embed images as base64 data URIs
    package_assets = package_dir / "assets"

    # Helper for rewriting company-asset URLs.
    _company_url_re = re.compile(r"/api/companies/[^/]+/assets/([^/]+)/file/?", re.IGNORECASE)

    def _rewrite_company_url(url: str) -> str:
        """If `url` matches /api/companies/.../assets/<id>/file, return the
        local `assets/_companies/<id>.<ext>` rewrite. Otherwise unchanged."""
        if not url or not isinstance(url, str):
            return url
        m = _company_url_re.search(url)
        if not m:
            return url
        asset_id = m.group(1)
        local = _company_url_to_local.get(asset_id)
        if local:
            return local
        # Not yet copied: try a fallback lookup in `_companies/` directory.
        cdir = package_assets / "_companies"
        if cdir.exists():
            for f in cdir.iterdir():
                if f.stem == asset_id:
                    return f"assets/_companies/{f.name}"
        return url  # leave unchanged so the LMS still tries the live URL

    for slide in (course_data.get('slides') or []):
        if not isinstance(slide, dict):
            continue

        # Fix background image URL - EMBED AS DATA URI
        bg_url = slide.get('backgroundImage') or ''
        if bg_url and isinstance(bg_url, str):
            # Company brand image — rewrite to local _companies/ path
            if "/api/companies/" in bg_url:
                slide['backgroundImage'] = _rewrite_company_url(bg_url)
            elif '/assets/' in bg_url:
                # Handle both /assets/filename and /assets/project_id/filename patterns
                parts = bg_url.split('/assets/')
                raw = parts[-1].split('?')[0]
                # Strip leading project_id segment if present (e.g. "proj_id/file.png")
                filename = raw.split('/')[-1] if '/' in raw else raw
                if filename:
                    data_uri = _read_image_as_data_uri(project.id, filename, package_assets)
                    if data_uri:
                        slide['backgroundImage'] = data_uri
                    else:
                        slide['backgroundImage'] = f"assets/{filename}"
                        logger.warning(f"Could not embed backgroundImage, using relative path: assets/{filename}")
            elif bg_url.startswith('data:'):
                pass  # Already a data URI, keep as-is

        # Fix element URLs - embed images as data URIs
        for element in (slide.get('elements') or []):
            if not isinstance(element, dict):
                continue
            elem_src = element.get('src') or ''
            elem_type = element.get('type') or ''

            # Company brand image (logo, watermark) — rewrite to local path
            if elem_src and isinstance(elem_src, str) and "/api/companies/" in elem_src:
                element['src'] = _rewrite_company_url(elem_src)
            # Whiteboard renderer output (MP4 video or APNG image). The URL
            # is relative (`/api/whiteboard/file/wb_*.mp4|.png`) so it never
            # resolves once the SCORM package is opened offline. Copy the
            # actual file from the global whiteboard storage into the
            # package assets and rewrite the src to a local path.
            elif elem_src and isinstance(elem_src, str) and '/api/whiteboard/file/' in elem_src:
                wb_name = elem_src.split('/api/whiteboard/file/')[-1].split('?')[0].split('/')[0]
                if wb_name:
                    wb_source = STORAGE_DIR / "whiteboard" / wb_name
                    if wb_source.exists():
                        try:
                            (package_dir / "assets").mkdir(parents=True, exist_ok=True)
                            shutil.copy2(str(wb_source), str(package_dir / "assets" / wb_name))
                            element['src'] = f"assets/{wb_name}"
                            logger.info(f"Copied whiteboard asset to package: {wb_name}")
                        except Exception as e:
                            logger.warning(f"Failed to copy whiteboard asset {wb_name}: {e}")
                            element['src'] = f"assets/{wb_name}"
                    else:
                        logger.warning(f"Whiteboard source file not found: {wb_source}")
                        element['src'] = f"assets/{wb_name}"
            elif elem_src and isinstance(elem_src, str) and '/assets/' in elem_src:
                raw = elem_src.split('/assets/')[-1].split('?')[0]
                filename = raw.split('/')[-1] if '/' in raw else raw
                if filename:
                    # Extract source project ID from URL (gallery images may reference other projects)
                    source_project_id = project.id
                    if '/api/projects/' in elem_src:
                        import re as _re
                        pid_match = _re.search(r'/api/projects/([^/]+)/assets/', elem_src)
                        if pid_match:
                            source_project_id = pid_match.group(1)
                    
                    # For image elements or files with image extensions, embed as data URI
                    is_image_ext = any(filename.lower().endswith(ext) for ext in ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg'))
                    if (elem_type in ('image', '') or not elem_type) and is_image_ext:
                        # First try with current project assets, then source project
                        data_uri = _read_image_as_data_uri(project.id, filename, package_assets)
                        if not data_uri and source_project_id != project.id:
                            # Try from source project's assets directory
                            source_assets = Path(storage_dir) / source_project_id / "assets"
                            if source_assets.exists():
                                source_file = source_assets / filename
                                if source_file.exists():
                                    shutil.copy2(source_file, package_assets / filename)
                            # Also try restoring from MongoDB with source project ID
                            data_uri = _read_image_as_data_uri(source_project_id, filename, package_assets)
                        element['src'] = data_uri if data_uri else f"assets/{filename}"
                    else:
                        element['src'] = f"assets/{filename}"

            # Handle external video URLs (like HeyGen videos) - SHORT TIMEOUT to avoid 520
            elif elem_type == 'video' and elem_src and isinstance(elem_src, str) and elem_src.startswith('http'):
                try:
                    import hashlib
                    url_hash = hashlib.md5(elem_src.encode(), usedforsecurity=False).hexdigest()[:12]
                    if '.webm' in elem_src.lower():
                        vid_ext = '.webm'
                    elif '.mp4' in elem_src.lower():
                        vid_ext = '.mp4'
                    else:
                        vid_ext = '.mp4'
                    video_filename = f"video_{url_hash}{vid_ext}"
                    video_path = package_dir / "assets" / video_filename

                    logger.info(f"Downloading external video: {elem_src[:100]}...")
                    # Use 25s timeout - Cloudflare upstream limit is ~30s
                    with httpx.Client(timeout=25.0, follow_redirects=True) as client:
                        response = client.get(elem_src)
                        if response.status_code == 200:
                            with open(video_path, 'wb') as vf:
                                vf.write(response.content)
                            element['src'] = f"assets/{video_filename}"
                            logger.info(f"Downloaded video as: {video_filename}")
                        else:
                            logger.warning(f"Failed to download video ({response.status_code}), keeping original URL")
                except Exception as e:
                    logger.warning(f"Video download skipped (non-fatal): {e}")
                    # Keep original URL as fallback so the element still works online

            # Process HTML elements - fix image URLs inside htmlContent
            if elem_type == 'html':
                html_content = element.get('htmlContent') or ''
                if html_content and isinstance(html_content, str):
                    # Sanitize: remove Tailwind CSS variables and editor artifacts
                    html_content = re.sub(r'--tw-[^;:]+:[^;]*;?\s*', '', html_content)
                    html_content = re.sub(r'outline-style:\s*dashed\s*;?\s*', '', html_content)
                    html_content = re.sub(r'outline-width:\s*[^;]+;?\s*', '', html_content)
                    html_content = re.sub(r'style="\s*;?\s*"', '', html_content)
                    html_content = re.sub(r"style='\s*;?\s*'", '', html_content)

                    img_pattern = re.compile(r'src=["\']([^"\']+)["\']', re.IGNORECASE)

                    def fix_img_src(match):
                        src = match.group(1)
                        if not src or src.startswith('data:'):
                            return match.group(0)
                        # Company brand image URL — rewrite to local
                        # _companies/ path (the directory copy happens above).
                        if "/api/companies/" in src:
                            rewritten = _rewrite_company_url(src)
                            if rewritten != src:
                                return f'src="{rewritten}"'
                            return match.group(0)
                        if '/api/assets/' in src:
                            fn_raw = src.split('/api/assets/')[-1].split('?')[0]
                            fn = fn_raw.split('/')[-1] if '/' in fn_raw else fn_raw
                        elif '/assets/' in src:
                            fn_raw = src.split('/assets/')[-1].split('?')[0]
                            fn = fn_raw.split('/')[-1] if '/' in fn_raw else fn_raw
                        else:
                            return match.group(0)
                        if fn:
                            data_uri = _read_image_as_data_uri(project.id, fn, package_assets)
                            if data_uri:
                                return f'src="{data_uri}"'
                            return f'src="assets/{fn}"'
                        return match.group(0)

                    element['htmlContent'] = img_pattern.sub(fix_img_src, html_content)

        # Fix audio URLs (keep as files, not data URIs)
        for audio in (slide.get('audio') or []):
            if not isinstance(audio, dict):
                continue
            # Normalize: use 'src' or 'url' field
            audio_src = audio.get('src') or audio.get('url') or ''
            if audio_src and isinstance(audio_src, str):
                if '/assets/' in audio_src:
                    raw = audio_src.split('/assets/')[-1].split('?')[0]
                    filename = raw.split('/')[-1] if '/' in raw else raw
                    if filename:
                        audio['src'] = f"assets/{filename}"
                elif '/api/audio/' in audio_src:
                    filename = audio_src.split('/api/audio/')[-1].split('?')[0]
                    if filename:
                        # Copy narration file from audio storage to package assets
                        audio_storage = Path(os.path.dirname(os.path.dirname(__file__))) / "storage" / "audio" / filename
                        if audio_storage.exists():
                            shutil.copy2(str(audio_storage), str(package_dir / "assets" / filename))
                            logger.info(f"Copied narration audio to package: {filename}")
                        audio['src'] = f"assets/{filename}"
    
    # Fix global audio URL
    global_audio = course_data.get('globalAudio')
    if global_audio and isinstance(global_audio, dict):
        ga_src = global_audio.get('src') or ''
        if ga_src and isinstance(ga_src, str) and '/assets/' in ga_src:
            raw = ga_src.split('/assets/')[-1].split('?')[0]
            filename = raw.split('/')[-1] if '/' in raw else raw
            if filename:
                global_audio['src'] = f"assets/{filename}"
    
    # Add questions for quiz elements
    if questions:
        course_data['questions'] = questions
        logger.info(f"Added {len(questions)} questions to course.json for quiz support")
    
    # Add tutor configuration
    if tutor_config and tutor_config.get('enabled'):
        # Build course context from slide content for the tutor.
        #
        # 2026-05-26: include `slide.title` and `slide.notes` so courses
        # imported from PDF Modo Fiel or PPT (whose `elements` is empty
        # but whose OCR'd / extracted text lives in `notes`) get a
        # meaningful tutor context. Previously the tutor was useless on
        # imported courses because it only read `elements[*].content`.
        import re as _re

        def _slide_text_parts(slide: dict) -> list:
            """Collect ALL textual signals from a slide for tutor context.

            Order: title -> notes (PDF Modo Fiel OCR) -> extractedText (PPT
            import shapes) -> elements text. Notes/extractedText are
            critical for Modo Fiel and PPT imports where `elements` is empty.
            """
            parts = []
            title = (slide.get('title') or '').strip()
            if title and title.lower() not in ('novo slide', 'slide', 'untitled'):
                parts.append(title[:200])
            for field in ('notes', 'extractedText'):
                txt = (slide.get(field) or '').strip()
                if txt:
                    clean = _re.sub(r'<[^>]+>', ' ', txt)
                    clean = _re.sub(r'\s+', ' ', clean).strip()
                    if clean:
                        parts.append(clean[:2000])
            for elem in (slide.get('elements') or []):
                if not isinstance(elem, dict):
                    continue
                raw = elem.get('content') or elem.get('htmlContent') or elem.get('text') or ''
                if raw:
                    plain = _re.sub(r'<[^>]+>', ' ', raw).strip()
                    plain = _re.sub(r'\s+', ' ', plain)
                    if plain:
                        parts.append(plain[:500])
                btn_text = elem.get('buttonText')
                if btn_text:
                    parts.append(btn_text)
                quiz_cfg = elem.get('quizConfig')
                if quiz_cfg and isinstance(quiz_cfg, dict):
                    q_title = quiz_cfg.get('title')
                    if q_title:
                        parts.append(f"Quiz: {q_title}")
                scenario_data = elem.get('scenarioData')
                if scenario_data and isinstance(scenario_data, dict):
                    s_title = scenario_data.get('title')
                    if s_title:
                        parts.append(f"Cenário: {s_title}")
            return parts

        slide_summaries = []
        per_slide_contexts = []
        for i, slide in enumerate(course_data.get('slides') or []):
            if not isinstance(slide, dict):
                per_slide_contexts.append('')
                continue
            parts = _slide_text_parts(slide)
            joined = " | ".join(parts) if parts else ''
            per_slide_contexts.append(joined)
            if parts:
                slide_summaries.append(f"Slide {i+1}: " + joined)

        course_context = "\n".join(slide_summaries[:80])  # cap at 80 slides

        course_data['tutorConfig'] = {
            'enabled': True,
            'apiUrl': tutor_config.get('apiUrl', ''),
            'courseTopic': tutor_config.get('courseTopic', course.metadata.title or project.name),
            'courseContext': course_context,
            'slideContexts': per_slide_contexts,
            'tutorName': tutor_config.get('tutorName', 'Tutor IA'),
            'avatarUrl': tutor_config.get('avatarUrl', '') or '',
            'messageLimit': tutor_config.get('messageLimit', 50),
            'suggestedQuestions': tutor_config.get('suggestedQuestions', []),
            # Forward attribution so the in-widget feedback POSTs include
            # projectId + companyId — required for the admin dashboard
            # enrichment to join the rows back to the right course.
            'projectId': tutor_config.get('projectId', '') or project.id or '',
            'companyId': tutor_config.get('companyId', '') or (getattr(project, 'companyId', '') or ''),
        }
        logger.info(
            f"AI Tutor enabled for SCORM package with {len(slide_summaries)} slide summaries "
            f"(context len={len(course_context)} chars)"
        )
    
    # Verify audio assets exist and restore from MongoDB if missing
    for slide in (course_data.get('slides') or []):
        if not isinstance(slide, dict):
            continue
        for audio in (slide.get('audio') or []):
            if not isinstance(audio, dict):
                continue
            src = audio.get('src') or ''
            if src and isinstance(src, str) and src.startswith('assets/'):
                filename = src[len('assets/'):]
                audio_path = package_dir / "assets" / filename
                if not audio_path.exists():
                    # Try local audio storage first
                    audio_storage = Path(os.path.dirname(os.path.dirname(__file__))) / "storage" / "audio" / filename
                    if audio_storage.exists():
                        shutil.copy2(str(audio_storage), str(audio_path))
                        logger.info(f"Recovered narration audio from local storage: {filename}")
                    else:
                        try:
                            from services.asset_store import retrieve_asset_sync
                            mongo_url = os.environ.get('MONGO_URL')
                            db_name = os.environ.get('DB_NAME')
                            if mongo_url and db_name:
                                if retrieve_asset_sync(mongo_url, db_name, project.id, filename, str(audio_path)):
                                    logger.info(f"Recovered audio from MongoDB: {filename}")
                        except Exception as e:
                            logger.warning(f"Audio recovery failed (non-fatal): {e}")
    
    # Log summary of embedded images
    embedded_count = sum(1 for s in course_data.get('slides', []) 
                        if (s.get('backgroundImage') or '').startswith('data:'))
    logger.info(f"SCORM package: {embedded_count} background images embedded as data URIs")
    
    with open(package_dir / "course.json", 'w', encoding='utf-8') as f:
        json.dump(course_data, f, ensure_ascii=False, indent=2, cls=DateTimeEncoder)
    
    # Get slide dimensions with safe None fallback
    slide_width = 960
    slide_height = 540
    if course.slides:
        slide_width = int(course.slides[0].width or 960)
        slide_height = int(course.slides[0].height or 540)
    
    # Clean the course title - remove UUID prefix if present
    clean_title = course.metadata.title or project.name
    # Remove UUID pattern at the beginning (e.g., "a87fd1a0-1338-4043-9c2f-b0cc8572a12e_")
    clean_title = re.sub(r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}_?', '', clean_title)
    clean_title = clean_title.strip('_').strip()
    if not clean_title:
        clean_title = 'Curso SCORM'
    
    # Generate index.html from template + CSS assets
    enable_vlibras = getattr(project, 'enableVlibras', True)
    # Resolve branded loader config (title + colors) from the project's
    # brand kit + per-course override. Falls back to neutral defaults.
    try:
        from services.loader_config import resolve_loader_config
        _proj_dict = project.model_dump() if hasattr(project, "model_dump") else dict(project)
        _loader_cfg = resolve_loader_config(_proj_dict)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"loader_config resolve failed in classic SCORM (non-fatal): {exc}")
        _loader_cfg = {"title_html": "Carregando curso…", "primary": "#3b82f6", "accent": "#60a5fa"}

    html_content = _build_html(
        title=clean_title,
        lang=course.metadata.language or 'en',
        width=slide_width,
        height=slide_height,
        enable_vlibras=enable_vlibras,
        backend_url=backend_url,
        gamification_config=gamification_config,
        loader_title=_loader_cfg["title_html"],
        loader_primary=_loader_cfg["primary"],
        loader_accent=_loader_cfg["accent"],
    )
    
    with open(package_dir / "index.html", 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    # Generate resource files list for manifest
    resource_files = []
    
    # Add assets
    assets_dir = package_dir / "assets"
    if assets_dir.exists():
        for asset in assets_dir.iterdir():
            resource_files.append(f'<file href="assets/{asset.name}"/>')
    
    # Generate imsmanifest.xml
    manifest_content = IMS_MANIFEST_TEMPLATE.format(
        identifier=f"SCORM_{project.id}",
        title=clean_title,
        resource_files='\n            '.join(resource_files)
    )
    
    with open(package_dir / "imsmanifest.xml", 'w', encoding='utf-8') as f:
        f.write(manifest_content)
    
    # Write XSD files
    with open(package_dir / "adlcp_rootv1p2.xsd", 'w', encoding='utf-8') as f:
        f.write(ADLCP_XSD)
    
    with open(package_dir / "ims_xml.xsd", 'w', encoding='utf-8') as f:
        f.write(IMS_XML_XSD)
    
    with open(package_dir / "imscp_rootv1p1p2.xsd", 'w', encoding='utf-8') as f:
        f.write(IMSCP_XSD)
    
    with open(package_dir / "imsmd_rootv1p2p1.xsd", 'w', encoding='utf-8') as f:
        f.write(IMSMD_XSD)
    
    # Create ZIP file
    # Clean the project name - remove UUID prefix if present and special characters
    clean_name = project.name
    # Remove UUID pattern at the beginning (e.g., "a87fd1a0-1338-4043-9c2f-b0cc8572a12e_")
    clean_name = re.sub(r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}_?', '', clean_name)
    # Replace spaces with underscores and remove other special characters
    clean_name = re.sub(r'[^\w\s-]', '', clean_name)
    clean_name = clean_name.replace(' ', '_').strip('_')
    # Fallback to 'course' if name is empty
    if not clean_name:
        clean_name = 'course'
    
    zip_filename = f"{clean_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    zip_path = Path(output_dir) / zip_filename
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(package_dir):
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(package_dir)
                zipf.write(file_path, arcname)
    
    # Cleanup temp directory
    shutil.rmtree(package_dir)
    
    logger.info(f"SCORM package created: {zip_path}")
    return str(zip_path)
