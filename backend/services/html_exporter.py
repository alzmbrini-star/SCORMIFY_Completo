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
    
    course_json = json.dumps(course_data, ensure_ascii=False)
    
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
            background: rgba(255, 255, 255, 0.95);
            border-radius: 4px;
        }}
        
        .slide-element.shape-element {{
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        
        .slide-element.image-element img {{
            width: 100%;
            height: 100%;
            object-fit: contain;
        }}
        
        .slide-element.video-element {{
            background: #000;
            border-radius: 8px;
            overflow: hidden;
        }}
        
        .slide-element.video-element video,
        .slide-element.video-element iframe {{
            width: 100%;
            height: 100%;
            border: 0;
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
                        
                        var style = 'left:' + (elem.x || 0) + 'px;';
                        style += 'top:' + (elem.y || 0) + 'px;';
                        style += 'width:' + (elem.width || 100) + 'px;';
                        style += 'height:' + (elem.height || 100) + 'px;';
                        style += 'z-index:' + ((elem.zIndex || 0) + 1) + ';';
                        if (elem.rotation) style += 'transform:rotate(' + elem.rotation + 'deg);';
                        if (elem.style && elem.style.opacity !== undefined) style += 'opacity:' + elem.style.opacity + ';';
                        
                        html += '<div class="slide-element ' + elem.type + '-element" style="' + style + '">';
                        
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
                        else if (elem.type === 'video') {{
                            if (elem.embedUrl) {{
                                html += '<iframe src="' + elem.embedUrl + '" allow="autoplay; fullscreen" allowfullscreen></iframe>';
                            }} else if (elem.src) {{
                                html += '<video src="' + elem.src + '" controls></video>';
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
                            html += '<iframe srcdoc="' + elem.htmlContent.replace(/"/g, '&quot;') + '" style="width:100%;height:100%;border:0;"></iframe>';
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
                    slide.annotations.forEach(function(ann) {{
                        var color = ann.color || '#EF4444';
                        var strokeWidth = ann.strokeWidth || 3;
                        
                        if (ann.type === 'freehand' && ann.points && ann.points.length > 0) {{
                            var d = 'M ' + ann.points[0].x + ' ' + ann.points[0].y;
                            for (var i = 1; i < ann.points.length; i++) {{
                                d += ' L ' + ann.points[i].x + ' ' + ann.points[i].y;
                            }}
                            html += '<path d="' + d + '" stroke="' + color + '" stroke-width="' + strokeWidth + '" fill="none" stroke-linecap="round" stroke-linejoin="round"/>';
                        }}
                        else if (ann.type === 'arrow' && ann.points && ann.points.length >= 2) {{
                            html += '<defs><marker id="arrow-' + ann.id + '" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">';
                            html += '<polygon points="0 0, 10 3.5, 0 7" fill="' + color + '"/></marker></defs>';
                            html += '<line x1="' + ann.points[0].x + '" y1="' + ann.points[0].y + '" x2="' + ann.points[1].x + '" y2="' + ann.points[1].y + '" ';
                            html += 'stroke="' + color + '" stroke-width="' + strokeWidth + '" marker-end="url(#arrow-' + ann.id + ')"/>';
                        }}
                        else if (ann.type === 'circle' && ann.points && ann.points.length >= 2) {{
                            var cx = (ann.points[0].x + ann.points[1].x) / 2;
                            var cy = (ann.points[0].y + ann.points[1].y) / 2;
                            var rx = Math.abs(ann.points[1].x - ann.points[0].x) / 2;
                            var ry = Math.abs(ann.points[1].y - ann.points[0].y) / 2;
                            html += '<ellipse cx="' + cx + '" cy="' + cy + '" rx="' + rx + '" ry="' + ry + '" stroke="' + color + '" stroke-width="' + strokeWidth + '" fill="none"/>';
                        }}
                        else if (ann.type === 'rectangle' && ann.points && ann.points.length >= 2) {{
                            var x = Math.min(ann.points[0].x, ann.points[1].x);
                            var y = Math.min(ann.points[0].y, ann.points[1].y);
                            var w = Math.abs(ann.points[1].x - ann.points[0].x);
                            var h = Math.abs(ann.points[1].y - ann.points[0].y);
                            html += '<rect x="' + x + '" y="' + y + '" width="' + w + '" height="' + h + '" stroke="' + color + '" stroke-width="' + strokeWidth + '" fill="none"/>';
                        }}
                    }});
                    html += '</svg>';
                }}
                
                container.innerHTML = html;
                
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
            }}
            
            function updateSlideScale() {{
                var container = document.getElementById('slide-container');
                var wrapper = document.getElementById('slide-wrapper');
                if (!container || !wrapper || !course.slides) return;
                
                var slide = course.slides[currentSlide];
                var slideWidth = slide.width || {width};
                var slideHeight = slide.height || {height};
                
                var wrapperRect = wrapper.getBoundingClientRect();
                var availableWidth = wrapperRect.width - 40;
                var availableHeight = wrapperRect.height - 40;
                
                if (availableWidth < 100 || availableHeight < 100) return;
                
                var scaleX = availableWidth / slideWidth;
                var scaleY = availableHeight / slideHeight;
                var scale = Math.min(scaleX, scaleY);
                
                var isMobile = window.innerWidth < 900 || window.innerHeight < 600;
                var maxScale = isMobile ? 1.5 : 1.0;
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
            
            function fullscreen() {{
                var elem = document.getElementById('player-container');
                if (!document.fullscreenElement) {{
                    elem.requestFullscreen().catch(function() {{}});
                }} else {{
                    document.exitFullscreen();
                }}
            }}
            
            // Initialize on load
            document.addEventListener('DOMContentLoaded', init);
            
            return {{
                next: next,
                prev: prev,
                goTo: goTo,
                toggleSidebar: toggleSidebar,
                toggleMute: toggleMute,
                setVolume: setVolume,
                fullscreen: fullscreen
            }};
        }})();
    </script>
</body>
</html>'''
    
    return html
