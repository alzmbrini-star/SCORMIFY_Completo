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
                # Try with current base_url as fallback
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


async def generate_standalone_html(
    project: Dict[str, Any],
    assets_dir: str,
    base_url: str = "",
    questions: list = None
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
        
        # Process background image
        if slide.get('backgroundImage'):
            bg_path = slide['backgroundImage']
            if bg_path.startswith('/api/') or bg_path.startswith('assets/'):
                # Local asset
                asset_filename = bg_path.split('/')[-1]
                local_path = os.path.join(assets_dir, asset_filename)
                if os.path.exists(local_path):
                    processed_slide['backgroundImage'] = file_to_base64(local_path)
                else:
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
                if src.startswith('/api/') or src.startswith('assets/'):
                    asset_filename = src.split('/')[-1]
                    local_path = os.path.join(assets_dir, asset_filename)
                    if os.path.exists(local_path):
                        processed_element['src'] = file_to_base64(local_path)
                    else:
                        full_url = f"{base_url}{src}" if not src.startswith('http') else src
                        processed_element['src'] = await url_to_base64(full_url)
                elif src.startswith('http'):
                    processed_element['src'] = await url_to_base64(src)
            
            # Process video elements (local videos)
            if element.get('type') == 'video' and element.get('src'):
                src = element['src']
                if not src.startswith('http') and not element.get('embedUrl'):
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
            
            processed_elements.append(processed_element)
        
        processed_slide['elements'] = processed_elements
        
        # Process slide audio
        processed_audios = []
        for audio in slide.get('audio', []):
            processed_audio = audio.copy()
            if audio.get('src'):
                src = audio['src']
                if src.startswith('/api/') or src.startswith('assets/'):
                    asset_filename = src.split('/')[-1]
                    local_path = os.path.join(assets_dir, asset_filename)
                    if os.path.exists(local_path):
                        processed_audio['src'] = file_to_base64(local_path)
                    else:
                        # Try downloading from full URL
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
    if global_audio and global_audio.get('src'):
        processed_global_audio = global_audio.copy()
        src = global_audio['src']
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
    
    # Add questions for quiz support
    if questions:
        course_data["questions"] = questions
        logger.info(f"Added {len(questions)} questions to HTML export")
    
    # Generate HTML
    html = generate_html_template(title, course_data, default_width, default_height)
    
    return html


def generate_html_template(title: str, course_data: Dict, width: int, height: int) -> str:
    """Generate the complete HTML template with embedded player"""
    
    # Create a deep copy and sanitize htmlContent fields to prevent JSON/JS issues
    import copy
    sanitized_data = copy.deepcopy(course_data)
    
    for slide in sanitized_data.get('slides', []):
        for element in slide.get('elements', []):
            # Sanitize htmlContent - encode as base64 to prevent issues
            if element.get('htmlContent'):
                # Convert the HTML content to base64 to avoid escaping issues
                html_b64 = base64.b64encode(element['htmlContent'].encode('utf-8')).decode('utf-8')
                element['htmlContent'] = f"__B64__:{html_b64}"
    
    # Escape special characters that could break the script tag
    # First dump to JSON, then escape </script> and other problematic sequences
    course_json = json.dumps(sanitized_data, ensure_ascii=False)
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
            transform-origin: center center;
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
        
        /* Force display on mobile portrait mode */
        @media screen and (orientation: portrait) and (max-width: 900px) {{
            #orientation-overlay {{
                display: flex !important;
            }}
            #player-container {{
                display: none !important;
            }}
        }}
        
        /* Also detect by aspect ratio for devices that don't report orientation correctly */
        @media screen and (max-aspect-ratio: 4/5) and (max-width: 900px) {{
            #orientation-overlay {{
                display: flex !important;
            }}
            #player-container {{
                display: none !important;
            }}
        }}
        
        /* Extra aggressive detection for very tall screens (phones in portrait) */
        @media screen and (max-aspect-ratio: 7/10) {{
            #orientation-overlay {{
                display: flex !important;
            }}
            #player-container {{
                display: none !important;
            }}
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
                
                // Get slide duration for timeline
                var slideDuration = slide.duration || 5;
                
                // Build slide HTML
                var html = '';
                
                // Background
                if (slide.backgroundImage) {{
                    html += '<img class="slide-background" src="' + slide.backgroundImage + '" alt="">';
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
                        
                        // Check if element has animations
                        var hasAnimations = elem.animations && elem.animations.length > 0;
                        var hasEntranceAnimation = hasAnimations && elem.animations.some(function(a) {{ return a.type === 'entrance'; }});
                        
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
                        
                        // Handle opacity based on element type
                        if (isClipElement || isMaskElement) {{
                            // Clips and masks: start visible/opaque
                            var maskOpacity = (elem.style && elem.style.opacity !== undefined) ? elem.style.opacity : 1;
                            style += 'opacity:' + maskOpacity + ';';
                        }} else if (!hasAnimations && elem.style && elem.style.opacity !== undefined) {{
                            style += 'opacity:' + elem.style.opacity + ';';
                        }} else if (initiallyHidden) {{
                            style += 'visibility:hidden;opacity:0;';
                        }}
                        
                        html += '<div class="slide-element ' + elem.type + '-element" id="element-' + elemIndex + '" data-start-time="' + startTime + '" data-end-time="' + endTime + '" style="' + style + '">';
                        
                        if (elem.type === 'text') {{
                            var textStyle = '';
                            if (elem.style) {{
                                if (elem.style.fontSize) textStyle += 'font-size:' + elem.style.fontSize + 'px;';
                                if (elem.style.fontColor) textStyle += 'color:' + elem.style.fontColor + ';';
                                if (elem.style.fontWeight) textStyle += 'font-weight:' + elem.style.fontWeight + ';';
                                if (elem.style.textAlign) textStyle += 'text-align:' + elem.style.textAlign + ';';
                                // Apply background color (transparent or custom)
                                if (elem.style.transparentBackground) {{
                                    textStyle += 'background-color:transparent;';
                                }} else if (elem.style.backgroundColor) {{
                                    textStyle += 'background-color:' + elem.style.backgroundColor + ';';
                                }} else {{
                                    textStyle += 'background-color:rgba(255,255,255,0.9);';
                                }}
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
                                
                                if (isYouTube) {{
                                    // Extract YouTube video ID
                                    var ytMatch = embedUrl.match(/(?:embed\/|v=|youtu\.be\/)([^?&"'>]+)/);
                                    if (ytMatch) videoId = ytMatch[1];
                                }} else if (isVimeo) {{
                                    var vimeoMatch = embedUrl.match(/vimeo\.com\/(?:video\/)?(\d+)/);
                                    if (vimeoMatch) videoId = vimeoMatch[1];
                                }}
                                
                                // Create container for video
                                html += '<div class="video-embed-container" data-embed-url="' + embedUrl + '" data-video-id="' + videoId + '" data-is-youtube="' + isYouTube + '" data-is-vimeo="' + isVimeo + '" style="width:100%;height:100%;position:relative;overflow:hidden;background:#000;">';
                                
                                // For YouTube: Use iframe embed directly
                                if (isYouTube && videoId) {{
                                    var ytEmbedUrl = 'https://www.youtube.com/embed/' + videoId + '?rel=0&modestbranding=1&playsinline=1&enablejsapi=1';
                                    html += '<iframe class="video-iframe" src="' + ytEmbedUrl + '" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share; fullscreen" allowfullscreen frameborder="0" style="position:absolute;top:0;left:0;width:100%;height:100%;border:0;"></iframe>';
                                }} else if (isVimeo) {{
                                    // Vimeo: use iframe directly (generally more permissive)
                                    // Add parameters for better fullscreen experience
                                    var iframeUrl = embedUrl;
                                    var sep = iframeUrl.indexOf('?') !== -1 ? '&' : '?';
                                    iframeUrl += sep + 'autoplay=1&muted=1&background=0&dnt=1&title=0&byline=0&portrait=0';
                                    html += '<iframe class="video-iframe" src="' + iframeUrl + '" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share; fullscreen" allowfullscreen style="position:absolute;top:0;left:0;width:100%;height:100%;border:0;"></iframe>';
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
                            // Wrap htmlContent with proper CSS for text wrapping around images
                            var wrappedHtml = '<html><head><style>' +
                                (isFullscreen ? 
                                    // FULLSCREEN MODE - image fills entire container
                                    'html,body{{margin:0;padding:0;width:100%;height:100%;overflow:hidden;background:transparent!important;}}' +
                                    'body>div,body>*{{width:100%;height:100%;margin:0;padding:0;text-align:center;position:relative;}}' +
                                    'img,body img{{width:100%!important;height:100%!important;max-width:none!important;max-height:none!important;min-width:100%!important;min-height:100%!important;object-fit:cover!important;display:block!important;margin:0!important;padding:0!important;border:none!important;border-radius:0!important;float:none!important;position:absolute!important;top:0!important;left:0!important;}}' 
                                : 
                                    // NORMAL MODE - preserve image sizes and positions
                                    'body{{margin:0;padding:8px;background:transparent!important;font-family:Arial,sans-serif;color:#f1f5f9;line-height:1.6;overflow:auto;}}' +
                                    '*{{background:transparent!important;}}' +
                                    'img{{border:none!important;outline:none!important;box-shadow:none!important;}}' +
                                    'img.rtf-image-float-left,body img.rtf-image-float-left{{float:left!important;clear:left!important;max-width:45%!important;height:auto!important;border-radius:4px!important;margin:0 16px 12px 0!important;display:block!important;border:none!important;outline:none!important;}}' +
                                    'img.rtf-image-float-right,body img.rtf-image-float-right{{float:right!important;clear:right!important;max-width:45%!important;height:auto!important;border-radius:4px!important;margin:0 0 12px 16px!important;display:block!important;border:none!important;outline:none!important;}}' +
                                    'img.rtf-image-center{{display:inline-block!important;max-width:80%!important;border:none!important;outline:none!important;}}' +
                                    'img.rtf-image-inline{{display:block!important;max-width:100%!important;margin:8px 0!important;border:none!important;outline:none!important;}}' +
                                    'img[style*="float: left"]{{float:left!important;margin-right:16px!important;margin-bottom:12px!important;max-width:45%!important;height:auto!important;}}' +
                                    'img[style*="float: right"]{{float:right!important;margin-left:16px!important;margin-bottom:12px!important;max-width:45%!important;height:auto!important;}}' +
                                    'body::after{{content:\\'\\';display:table;clear:both;}}' +
                                    'p,div,span,ul,ol,li,h1,h2,h3,h4,h5,h6{{overflow:visible!important;}}'
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
                                'tr:nth-child(even) td{{background:#1a2433;}}' +
                                '</style></head><body>' + htmlContent + '</body></html>';
                            html += '<iframe srcdoc="' + wrappedHtml.replace(/"/g, '&quot;') + '" style="width:100%;height:100%;border:0;overflow:' + (isFullscreen ? 'hidden' : 'auto') + ';"></iframe>';
                        }}
                        else if (elem.type === 'flipbook' && elem.flipbookUrl) {{
                            html += '<iframe src="' + elem.flipbookUrl + '" style="width:100%;height:100%;border:0;" allowfullscreen></iframe>';
                        }}
                        else if (elem.type === 'quiz' && elem.quizConfig) {{
                            // Quiz element - render container for QuizController
                            var quizContainer = '<div class="quiz-player-container" data-element-id="' + elem.id + '" data-quiz-config=\\'' + JSON.stringify(elem.quizConfig).replace(/'/g, "\\\\'") + '\\' style="width:100%;height:100%;display:flex;flex-direction:column;">';
                            quizContainer += '<div style="width:100%;height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:20px;background:linear-gradient(135deg,#1e293b,#0f172a);border-radius:12px;border:2px solid rgba(34,211,238,0.3);">';
                            quizContainer += '<div style="font-size:48px;margin-bottom:16px;">📝</div>';
                            quizContainer += '<h3 style="font-size:20px;font-weight:bold;color:#fff;margin-bottom:8px;">' + (elem.quizConfig.title || 'Quiz') + '</h3>';
                            quizContainer += '<p style="color:#94a3b8;font-size:14px;margin-bottom:16px;">' + (elem.quizConfig.questionIds ? elem.quizConfig.questionIds.length : 0) + ' questões</p>';
                            quizContainer += '<button class="quiz-start-btn" style="padding:12px 32px;background:linear-gradient(135deg,#06b6d4,#8b5cf6);color:#fff;border:none;border-radius:8px;font-size:16px;font-weight:600;cursor:pointer;" ';
                            quizContainer += 'onclick="QuizController.startQuiz(\\'' + elem.id + '\\')">Iniciar Quiz</button>';
                            quizContainer += '</div></div>';
                            html += quizContainer;
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
                
                container.innerHTML = html;
                
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
                        
                        if (element) {{
                            // Check if this is an animation clip or mask element
                            var isClip = elem.type === 'animation_clip';
                            var isMask = elem.type === 'animation_mask';
                            var isHighlight = elem.type === 'animation_highlight';
                            
                            // Check if element has PPT animations
                            var hasAnimations = elem.animations && elem.animations.length > 0;
                            
                            if (hasAnimations) {{
                                // Process each animation
                                elem.animations.forEach(function(anim, animIdx) {{
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
                                        
                                        var showTimer = setTimeout(function() {{
                                            element.style.visibility = 'visible';
                                            element.style.opacity = '1';
                                            element.style.animation = animEffect + ' ' + animDuration + 's ' + (anim.easing || 'ease') + ' forwards';
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
                                        element.style.display = '';
                                        element.style.animation = 'fadeIn 0.3s ease-out';
                                    }}, startTime * 1000);
                                    timelineTimers.push(showTimer);
                                }}
                                
                                if (endTime < slideDuration) {{
                                    var hideTimer = setTimeout(function() {{
                                        element.style.animation = 'fadeOut 0.3s ease-out';
                                        setTimeout(function() {{
                                            element.style.display = 'none';
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
                
                // Detect portrait orientation
                var isPortrait = window.innerHeight > window.innerWidth;
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
                container.style.boxShadow = '';
                container.style.transformOrigin = 'center center';
                
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
                
                // Fix YouTube embeds if running locally
                fixYouTubeEmbeds();
            }}
            
            function fixYouTubeEmbeds() {{
                // Check if running from local file
                var isLocalFile = window.location.protocol === 'file:';
                
                // Find all video embed containers and setup click handlers
                var containers = document.querySelectorAll('.video-embed-container');
                containers.forEach(function(container) {{
                    var isYouTube = container.dataset.isYoutube === 'true';
                    var videoId = container.dataset.videoId;
                    var thumbContainer = container.querySelector('.youtube-thumb-container');
                    var iframe = container.querySelector('.video-iframe');
                    
                    if (isYouTube && videoId && thumbContainer) {{
                        // Add hover effect to play button
                        var playBtn = thumbContainer.querySelector('.yt-play-btn');
                        if (playBtn) {{
                            thumbContainer.onmouseover = function() {{ playBtn.style.transform = 'translate(-50%,-50%) scale(1.1)'; }};
                            thumbContainer.onmouseout = function() {{ playBtn.style.transform = 'translate(-50%,-50%) scale(1)'; }};
                        }}
                        
                        // Click handler for thumbnail
                        thumbContainer.onclick = function(e) {{
                            e.stopPropagation();
                            
                            if (isLocalFile) {{
                                // If running locally, always open in new tab
                                window.open('https://www.youtube.com/watch?v=' + videoId, '_blank');
                            }} else if (iframe) {{
                                // Try to show the iframe
                                thumbContainer.style.display = 'none';
                                iframe.style.display = 'block';
                                
                                // Add autoplay parameter when shown
                                var src = iframe.src;
                                if (src.indexOf('autoplay=1') === -1) {{
                                    var sep = src.indexOf('?') !== -1 ? '&' : '?';
                                    iframe.src = src + sep + 'autoplay=1&mute=0';
                                }}
                                
                                // If iframe fails or is blocked, show thumbnail again with click-to-youtube option
                                setTimeout(function() {{
                                    // Check if iframe has loaded properly by checking if it has content
                                    // This is a heuristic - if user sees nothing after 3 seconds, provide fallback
                                }}, 3000);
                            }} else {{
                                // No iframe available, open in new tab
                                window.open('https://www.youtube.com/watch?v=' + videoId, '_blank');
                            }}
                        }};
                    }}
                }});
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
                    
                    var html = '<style>.quiz-scroll::-webkit-scrollbar{{width:4px;height:4px;}}.quiz-scroll::-webkit-scrollbar-track{{background:transparent;}}.quiz-scroll::-webkit-scrollbar-thumb{{background:rgba(100,116,139,0.4);border-radius:4px;}}.quiz-scroll{{scrollbar-width:thin;scrollbar-color:rgba(100,116,139,0.4) transparent;}}</style>' +
                        '<div style="display:flex;flex-direction:column;height:100%;background:#1e293b;color:#fff;font-family:system-ui,-apple-system,sans-serif;border-radius:12px;overflow:hidden;">' +
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
                        '<h3 style="font-size:14px;font-weight:600;margin-bottom:12px;color:#f1f5f9;line-height:1.4;">' + question.text + '</h3>' +
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
                        '<div style="padding:10px 16px;border-top:1px solid #334155;display:flex;justify-content:space-between;align-items:center;background:#1e293b;">' +
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
                    
                    var html = '<style>.quiz-scroll::-webkit-scrollbar{{width:4px;}}.quiz-scroll::-webkit-scrollbar-thumb{{background:rgba(100,116,139,0.4);border-radius:4px;}}.quiz-scroll{{scrollbar-width:thin;}}</style>' +
                        '<div class="quiz-scroll" style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;padding:16px;background:linear-gradient(135deg,#1e293b,#0f172a);color:#fff;overflow:auto;border-radius:12px;">' +
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
                console.log('No questions found in courseData');
            }}
        }});
    </script>
</body>
</html>'''
    
    return html
