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


class DateTimeEncoder(json.JSONEncoder):
    """JSON Encoder that handles datetime objects"""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


def _read_image_as_data_uri(project_id: str, filename: str, package_assets_dir: Path) -> Optional[str]:
    """Read an image file and return it as a base64 data URI.
    Tries: 1) package assets dir, 2) MongoDB.
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
    
    # Try 2: Read from MongoDB
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
    
    logger.error(f"Could not find image anywhere: {filename} for project {project_id}")
    return None


def _read_asset(filename: str) -> str:
    """Read an export asset file from the export_assets directory."""
    return (EXPORT_ASSETS_DIR / filename).read_text(encoding='utf-8')


def _build_html(title: str, lang: str, width: int, height: int) -> str:
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
            <file href="scripts/player.js"/>
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

def export_scorm_package(project: Project, storage_dir: str, output_dir: str, questions: list = None) -> str:
    """
    Export a project as a SCORM 1.2 package
    Returns the path to the generated ZIP file
    
    Args:
        project: Project model
        storage_dir: Path to storage directory
        output_dir: Path to output directory
        questions: Optional list of quiz questions to include
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
    
    # Write scripts (read from export_assets directory)
    with open(package_dir / "scripts" / "scorm-api.js", 'w') as f:
        f.write(_read_asset("scorm-api.js"))
    
    with open(package_dir / "scripts" / "player.js", 'w') as f:
        f.write(_read_asset("player.js"))
    
    # Write quiz controller script
    with open(package_dir / "scripts" / "quiz-controller.js", 'w') as f:
        f.write(_read_asset("quiz-controller.js"))
    
    # Prepare course.json - Fix asset URLs for SCORM package
    course_data = course.model_dump()
    
    # Convert datetime to string
    course_data['createdAt'] = course.createdAt.isoformat() if course.createdAt else None
    course_data['updatedAt'] = course.updatedAt.isoformat() if course.updatedAt else None
    
    # Fix all asset URLs in slides - embed images as base64 data URIs
    package_assets = package_dir / "assets"
    for slide in (course_data.get('slides') or []):
        if not isinstance(slide, dict):
            continue

        # Fix background image URL - EMBED AS DATA URI
        bg_url = slide.get('backgroundImage') or ''
        if bg_url and isinstance(bg_url, str):
            if '/assets/' in bg_url:
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

            if elem_src and isinstance(elem_src, str) and '/assets/' in elem_src:
                raw = elem_src.split('/assets/')[-1].split('?')[0]
                filename = raw.split('/')[-1] if '/' in raw else raw
                if filename:
                    # For image elements or files with image extensions, embed as data URI
                    is_image_ext = any(filename.lower().endswith(ext) for ext in ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg'))
                    if (elem_type in ('image', '') or not elem_type) and is_image_ext:
                        data_uri = _read_image_as_data_uri(project.id, filename, package_assets)
                        element['src'] = data_uri if data_uri else f"assets/{filename}"
                    else:
                        element['src'] = f"assets/{filename}"

            # Handle external video URLs (like HeyGen videos) - SHORT TIMEOUT to avoid 520
            elif elem_type == 'video' and elem_src and isinstance(elem_src, str) and elem_src.startswith('http'):
                try:
                    import hashlib
                    url_hash = hashlib.md5(elem_src.encode()).hexdigest()[:12]
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
            audio_src = audio.get('src') or ''
            if audio_src and isinstance(audio_src, str) and '/assets/' in audio_src:
                raw = audio_src.split('/assets/')[-1].split('?')[0]
                filename = raw.split('/')[-1] if '/' in raw else raw
                if filename:
                    audio['src'] = f"assets/{filename}"
    
    # Fix global audio URL
    if course_data.get('globalAudio') and course_data['globalAudio'].get('src'):
        if '/assets/' in course_data['globalAudio']['src']:
            filename = course_data['globalAudio']['src'].split('/assets/')[-1]
            course_data['globalAudio']['src'] = f"assets/{filename}"
    
    # Add questions for quiz elements
    if questions:
        course_data['questions'] = questions
        logger.info(f"Added {len(questions)} questions to course.json for quiz support")
    
    # Verify audio assets exist (images are now embedded as data URIs)
    for slide in course_data.get('slides', []):
        for audio in slide.get('audio', []):
            src = audio.get('src', '')
            if src and src.startswith('assets/'):
                filename = src.replace('assets/', '')
                audio_path = package_dir / "assets" / filename
                if not audio_path.exists():
                    # Try MongoDB
                    try:
                        from services.asset_store import retrieve_asset_sync
                        mongo_url = os.environ.get('MONGO_URL')
                        db_name = os.environ.get('DB_NAME')
                        if mongo_url and db_name:
                            if retrieve_asset_sync(mongo_url, db_name, project.id, filename, str(audio_path)):
                                logger.info(f"Recovered audio from MongoDB: {filename}")
                    except Exception as e:
                        logger.warning(f"Audio recovery failed: {e}")
    
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
    html_content = _build_html(
        title=clean_title,
        lang=course.metadata.language or 'en',
        width=slide_width,
        height=slide_height
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
