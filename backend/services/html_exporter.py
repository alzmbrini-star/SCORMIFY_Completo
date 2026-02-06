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


async def generate_standalone_html(
    project: Dict[str, Any],
    assets_dir: str,
    base_url: str = ""
) -> str:
    """
    Generate a standalone HTML file with all assets embedded as base64
    
    Args:
        project: The project dictionary containing course data
        assets_dir: Directory where project assets are stored
        base_url: Base URL for external assets
        
    Returns:
        Complete HTML string
    """
    course = project.get('course', {})
    metadata = course.get('metadata', {})
    slides = course.get('slides', [])
    global_audio = course.get('globalAudio')
    
    title = metadata.get('title', project.get('name', 'Course'))
    
    # Get first slide dimensions as default
    default_width = 1280
    default_height = 720
    if slides:
        default_width = slides[0].get('width', 1280)
        default_height = slides[0].get('height', 720)
    
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
            object-fit: contain;
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
            object-fit: contain;
        }}
        
        .slide-element.video-element {{
            background: transparent;
            border-radius: 0;
            overflow: visible;
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
            object-fit: contain;
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
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            z-index: 99999;
            justify-content: center;
            align-items: center;
            flex-direction: column;
        }}
        
        @media screen and (orientation: portrait) and (max-width: 900px) {{
            #orientation-overlay {{
                display: flex !important;
            }}
            #player-container {{
                display: none !important;
            }}
        }}
        
        .orientation-content {{
            text-align: center;
            padding: 30px;
            color: white;
        }}
        
        .orientation-icon {{
            font-size: 80px;
            margin-bottom: 20px;
            animation: pulse 2s ease-in-out infinite;
        }}
        
        .orientation-content h2 {{
            font-size: 24px;
            margin-bottom: 15px;
        }}
        
        .orientation-content p {{
            font-size: 16px;
            opacity: 0.8;
            max-width: 300px;
            margin: 0 auto;
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
            <h2>Rotacione seu dispositivo</h2>
            <p>Para uma melhor experiência, visualize no modo paisagem (horizontal)</p>
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
                            }}
                            html += '<div style="' + textStyle + '">' + (elem.content || '') + '</div>';
                        }}
                        else if (elem.type === 'image' && elem.src) {{
                            html += '<img src="' + elem.src + '" alt="" style="object-fit:' + (elem.objectFit || 'contain') + ';">';
                        }}
                        else if (elem.type === 'smartart' && elem.src) {{
                            // SmartArt rendered as image with fallback content for accessibility
                            html += '<img src="' + elem.src + '" alt="SmartArt: ' + (elem.content || 'Diagram') + '" style="object-fit:contain;">';
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
                                html += '<iframe src="' + elem.embedUrl + '" allow="autoplay; fullscreen" allowfullscreen style="background:transparent;"></iframe>';
                            }} else if (elem.src) {{
                                // Check if video is WebM (likely has alpha channel for transparency)
                                var isWebM = elem.src && elem.src.toLowerCase().includes('.webm');
                                var videoStyle = isWebM ? 'style="background:transparent !important;"' : '';
                                html += '<video src="' + elem.src + '" controls ' + videoStyle + '></video>';
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
                            html += '<iframe srcdoc="' + htmlContent.replace(/"/g, '&quot;') + '" style="width:100%;height:100%;border:0;"></iframe>';
                        }}
                        else if (elem.type === 'flipbook' && elem.flipbookUrl) {{
                            html += '<iframe src="' + elem.flipbookUrl + '" style="width:100%;height:100%;border:0;" allowfullscreen></iframe>';
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
                                        // CLIP ANIMATION: Fade out the blur/cover to reveal content underneath
                                        var clipInner = element.querySelector('.animation-clip');
                                        if (clipInner) {{
                                            if (anim.type === 'entrance') {{
                                                // Entrance: start with blur cover, then fade it out
                                                var revealTimer = setTimeout(function() {{
                                                    clipInner.style.opacity = '0';
                                                    clipInner.style.backdropFilter = 'blur(0px)';
                                                    clipInner.style.webkitBackdropFilter = 'blur(0px)';
                                                }}, actualDelay * 1000);
                                                timelineTimers.push(revealTimer);
                                                
                                            }} else if (anim.type === 'exit') {{
                                                // Exit: start visible, then add blur cover
                                                clipInner.style.opacity = '0';
                                                clipInner.style.backdropFilter = 'blur(0px)';
                                                var hideTimer = setTimeout(function() {{
                                                    clipInner.style.opacity = '1';
                                                    clipInner.style.backdropFilter = 'blur(20px)';
                                                    clipInner.style.webkitBackdropFilter = 'blur(20px)';
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
                
                var wrapperRect = wrapper.getBoundingClientRect();
                
                // Use minimal padding on mobile landscape for maximum slide size
                var isMobileLand = isMobileLandscape();
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
                
                // Allow higher scale on mobile/presentation for better readability
                // No upper limit on mobile landscape - fill the screen!
                var maxScale;
                if (isPresentationMode || isMobileLand) {{
                    maxScale = 5.0; // Virtually no limit
                }} else {{
                    maxScale = 1.0;
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
    </script>
</body>
</html>'''
    
    return html
