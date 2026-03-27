"""
Video Exporter Service
Exports course slides as MP4 or WebM video with:
- Slide backgrounds and images
- HeyGen avatar videos overlaid
- YouTube/Vimeo videos overlaid
- Narration audio synchronized
- Quiz elements ignored
"""
import os
import re
import uuid
import json
import shutil
import logging
import asyncio
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


def _ensure_ffmpeg():
    """Check if ffmpeg is available. Returns paths or None if not available."""
    ffmpeg = shutil.which('ffmpeg')
    ffprobe = shutil.which('ffprobe')
    
    # Also check common paths
    if not ffmpeg:
        for path in ['/usr/bin/ffmpeg', '/usr/local/bin/ffmpeg']:
            if os.path.exists(path) and os.access(path, os.X_OK):
                ffmpeg = path
                break
    
    if not ffprobe:
        for path in ['/usr/bin/ffprobe', '/usr/local/bin/ffprobe']:
            if os.path.exists(path) and os.access(path, os.X_OK):
                ffprobe = path
                break
    
    # Fallback: use static-ffmpeg Python package (works without root/apt-get)
    if not ffmpeg or not ffprobe:
        try:
            import static_ffmpeg
            paths = static_ffmpeg.run.get_or_fetch_platform_executables_else_raise()
            if not ffmpeg and paths[0]:
                ffmpeg = paths[0]
            if not ffprobe and paths[1]:
                ffprobe = paths[1]
            logger.info(f"Using static-ffmpeg: ffmpeg={ffmpeg}, ffprobe={ffprobe}")
        except ImportError:
            logger.warning("static-ffmpeg package not installed")
        except Exception as e:
            logger.warning(f"static-ffmpeg fallback failed: {e}")
    
    if ffmpeg:
        logger.info(f"FFmpeg: {ffmpeg}")
    else:
        logger.warning("FFmpeg not found - video export unavailable")
    
    return ffmpeg, ffprobe


def is_ffmpeg_available():
    """Check if ffmpeg is available for video export"""
    global FFMPEG_BIN, FFPROBE_BIN
    if not FFMPEG_BIN or not FFPROBE_BIN:
        FFMPEG_BIN, FFPROBE_BIN = _ensure_ffmpeg()
    return FFMPEG_BIN is not None and FFPROBE_BIN is not None


# Initialize at module level - skip FFmpeg download (video export is now client-side)
FFMPEG_BIN, FFPROBE_BIN = None, None
from PIL import Image, ImageDraw, ImageFont
import httpx


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex color to RGB tuple"""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 3:
        hex_color = ''.join(c * 2 for c in hex_color)
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def create_slide_base_image(slide: dict, project_id: str, projects_dir: str, storage_dir: str, output_path: str, canvas_width: int = 1920, canvas_height: int = 1080):
    """Create a base image for a slide by compositing background + image elements"""
    slide_w = slide.get('width', 1920)
    slide_h = slide.get('height', 1080)

    # Create canvas at target resolution
    canvas = Image.new('RGB', (canvas_width, canvas_height), (0, 0, 0))

    # Draw background
    bg = slide.get('background', '#000000')
    bg_image = slide.get('backgroundImage', '')

    if bg_image and bg_image.startswith('/api/projects/'):
        parts = bg_image.split('/assets/')
        if len(parts) == 2:
            local_path = Path(projects_dir) / project_id / "assets" / parts[1]
            if local_path.exists():
                try:
                    bg_img = Image.open(local_path).convert('RGB')
                    bg_img = bg_img.resize((canvas_width, canvas_height), Image.Resampling.LANCZOS)
                    canvas = bg_img
                except Exception as e:
                    logger.warning(f"Failed to load background image: {e}")
    elif bg and bg.startswith('#'):
        try:
            rgb = hex_to_rgb(bg)
            canvas = Image.new('RGB', (canvas_width, canvas_height), rgb)
        except Exception:
            pass

    # Calculate scale factors from slide dimensions to canvas
    scale_x = canvas_width / slide_w
    scale_y = canvas_height / slide_h

    # Sort elements by zIndex
    elements = sorted(slide.get('elements', []), key=lambda e: e.get('zIndex', 0))

    for element in elements:
        el_type = element.get('type', '')
        if el_type == 'quiz':
            continue  # Skip quiz elements

        if el_type == 'image':
            src = element.get('src', '')
            if not src:
                continue
            local_path = None
            if src.startswith('/api/projects/'):
                parts = src.split('/assets/')
                if len(parts) == 2:
                    local_path = Path(projects_dir) / project_id / "assets" / parts[1]
            elif src.startswith('/api/assets/'):
                asset_name = src.split('/api/assets/')[-1]
                local_path = Path(storage_dir) / "assets" / asset_name

            if local_path and local_path.exists():
                try:
                    img = Image.open(local_path)
                    if img.mode != 'RGBA':
                        img = img.convert('RGBA')
                    x = int(element.get('x', 0) * scale_x)
                    y = int(element.get('y', 0) * scale_y)
                    w = int(element.get('width', 100) * scale_x)
                    h = int(element.get('height', 100) * scale_y)
                    img = img.resize((max(1, w), max(1, h)), Image.Resampling.LANCZOS)
                    canvas.paste(img, (x, y), img if img.mode == 'RGBA' else None)
                except Exception as e:
                    logger.warning(f"Failed to overlay image element: {e}")

        elif el_type in ('html', 'text'):
            # Try to render inline images from htmlContent
            html_content = element.get('htmlContent') or element.get('content') or ''
            if not html_content:
                continue
            img_matches = re.findall(r'src="(/api/[^"]+)"', html_content)
            for img_src in img_matches:
                local_path = None
                if img_src.startswith('/api/projects/'):
                    parts = img_src.split('/assets/')
                    if len(parts) == 2:
                        local_path = Path(projects_dir) / project_id / "assets" / parts[1]
                elif img_src.startswith('/api/assets/'):
                    asset_name = img_src.split('/api/assets/')[-1]
                    local_path = Path(storage_dir) / "assets" / asset_name
                if local_path and local_path.exists():
                    try:
                        img = Image.open(local_path)
                        if img.mode != 'RGBA':
                            img = img.convert('RGBA')
                        # Position inline image within the element bounds
                        x = int(element.get('x', 0) * scale_x)
                        y = int(element.get('y', 0) * scale_y)
                        w = int(element.get('width', 100) * scale_x)
                        h = int(element.get('height', 100) * scale_y)
                        # Scale image to fit element while maintaining aspect ratio
                        img_ratio = img.width / img.height
                        el_ratio = w / max(h, 1)
                        if img_ratio > el_ratio:
                            new_w = w
                            new_h = int(w / img_ratio)
                        else:
                            new_h = h
                            new_w = int(h * img_ratio)
                        img = img.resize((max(1, new_w), max(1, new_h)), Image.Resampling.LANCZOS)
                        canvas.paste(img, (x, y), img if img.mode == 'RGBA' else None)
                    except Exception as e:
                        logger.warning(f"Failed to overlay inline image: {e}")

            # Render text content
            clean_text = re.sub(r'<[^>]+>', '', html_content).strip()
            if clean_text:
                try:
                    draw = ImageDraw.Draw(canvas)
                    x = int(element.get('x', 0) * scale_x)
                    y = int(element.get('y', 0) * scale_y)
                    w = int(element.get('width', 100) * scale_x)
                    h = int(element.get('height', 100) * scale_y)
                    # Try to use a reasonable font size
                    font_size = max(16, min(48, int(h * 0.08)))
                    try:
                        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
                    except Exception:
                        font = ImageFont.load_default()
                    # Word wrap
                    words = clean_text.split()
                    lines = []
                    current_line = ""
                    for word in words:
                        test_line = f"{current_line} {word}".strip()
                        bbox = draw.textbbox((0, 0), test_line, font=font)
                        if bbox[2] - bbox[0] > w - 20:
                            if current_line:
                                lines.append(current_line)
                            current_line = word
                        else:
                            current_line = test_line
                    if current_line:
                        lines.append(current_line)
                    # Draw text
                    line_height = font_size + 4
                    max_lines = max(1, h // line_height)
                    for i, line in enumerate(lines[:max_lines]):
                        draw.text((x + 10, y + 10 + i * line_height), line, fill='white', font=font)
                except Exception as e:
                    logger.warning(f"Failed to render text: {e}")

    canvas.save(output_path, 'PNG')
    return output_path


async def download_file(url: str, output_path: str, timeout: float = 120) -> bool:
    """Download a file from URL"""
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url)
            if response.status_code == 200:
                with open(output_path, 'wb') as f:
                    f.write(response.content)
                return True
    except Exception as e:
        logger.warning(f"Failed to download {url}: {e}")
    return False


async def download_youtube_video(url: str, output_path: str) -> bool:
    """Download YouTube/Vimeo video using yt-dlp"""
    try:
        # Extract video URL from embed URL
        video_url = url
        if 'youtube.com/embed/' in url:
            video_id = url.split('/embed/')[1].split('?')[0]
            video_url = f'https://www.youtube.com/watch?v={video_id}'
        elif 'player.vimeo.com/video/' in url:
            video_id = url.split('/video/')[1].split('?')[0]
            video_url = f'https://vimeo.com/{video_id}'

        proc = await asyncio.create_subprocess_exec(
            '/root/.venv/bin/yt-dlp',
            '-f', 'best[height<=720]',
            '--no-playlist',
            '--socket-timeout', '30',
            '-o', output_path,
            video_url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
        if proc.returncode == 0:
            # yt-dlp may add extension, find the actual file
            if not Path(output_path).exists():
                for f in Path(output_path).parent.glob(f"{Path(output_path).stem}.*"):
                    return True
            return True
        else:
            logger.warning(f"yt-dlp failed: {stderr.decode()[:200]}")
    except asyncio.TimeoutError:
        logger.warning(f"yt-dlp timeout for {url}")
    except Exception as e:
        logger.warning(f"Failed to download video from {url}: {e}")
    return False


def get_media_duration(file_path: str) -> float:
    """Get duration of audio/video file using ffprobe"""
    global FFPROBE_BIN
    if not FFPROBE_BIN:
        _, FFPROBE_BIN = _ensure_ffmpeg()
    if not FFPROBE_BIN:
        return 0
    try:
        result = subprocess.run(
            [FFPROBE_BIN, '-v', 'quiet', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', file_path],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except Exception as e:
        logger.warning(f"ffprobe failed for {file_path}: {e}")
    return 0


def run_ffmpeg(args: list, timeout: int = 300) -> bool:
    """Run FFmpeg command"""
    global FFMPEG_BIN
    if not FFMPEG_BIN:
        FFMPEG_BIN, _ = _ensure_ffmpeg()
    if not FFMPEG_BIN:
        logger.error("FFmpeg not available")
        return False
    cmd = [FFMPEG_BIN, '-y'] + args
    logger.info(f"FFmpeg: {' '.join(cmd[:10])}...")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            logger.error(f"FFmpeg error: {result.stderr[:500]}")
            return False
        return True
    except subprocess.TimeoutExpired:
        logger.error("FFmpeg timeout")
        return False
    except Exception as e:
        logger.error(f"FFmpeg exception: {e}")
        return False


async def run_ffmpeg_async(args: list, timeout: int = 300) -> bool:
    """Run FFmpeg command asynchronously (non-blocking).
    Uses -threads 1 to prevent CPU starvation of the web server in production."""
    global FFMPEG_BIN
    if not FFMPEG_BIN:
        FFMPEG_BIN, _ = _ensure_ffmpeg()
    if not FFMPEG_BIN:
        logger.error("FFmpeg not available")
        return False
    # -threads 1 limits FFmpeg to 1 encoding thread to leave CPU for the web server
    cmd = [FFMPEG_BIN, '-y', '-threads', '1'] + args
    logger.info(f"FFmpeg async: {' '.join(cmd[:12])}...")
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        if proc.returncode != 0:
            logger.error(f"FFmpeg error: {stderr.decode()[:500]}")
            return False
        return True
    except asyncio.TimeoutError:
        logger.error("FFmpeg async timeout")
        try:
            proc.kill()
        except Exception:
            pass
        return False
    except Exception as e:
        logger.error(f"FFmpeg async exception: {e}")
        return False


async def export_video(
    project_doc: dict,
    projects_dir: str,
    storage_dir: str,
    exports_dir: str,
    video_format: str = 'mp4',
    default_duration: float = 5.0,
    on_progress=None
) -> str:
    """
    Export project as video (MP4 or WebM).
    Returns path to the output video file.
    """
    # Check ffmpeg availability
    if not is_ffmpeg_available():
        raise ValueError(
            "A exportação de vídeo não está disponível neste ambiente. "
            "FFmpeg não está instalado no servidor de produção. "
            "Por favor, use a exportação SCORM ou HTML como alternativa."
        )

    project_id = project_doc.get('id', '')
    course = project_doc.get('course', {})
    slides = course.get('slides', [])

    if not slides:
        raise ValueError("No slides to export")

    # Create temp working directory
    work_dir = Path(tempfile.mkdtemp(prefix='video_export_'))
    slides_dir = work_dir / "slides"
    videos_dir = work_dir / "videos"
    audio_dir = work_dir / "audio"
    segments_dir = work_dir / "segments"
    slides_dir.mkdir()
    videos_dir.mkdir()
    audio_dir.mkdir()
    segments_dir.mkdir()

    try:
        total_slides = len(slides)
        canvas_w, canvas_h = 1280, 720

        # ============================================================
        # PHASE 1: Create all slide images (fast, in thread pool)
        # ============================================================
        for idx, slide in enumerate(slides):
            logger.info(f"[VIDEO] Slide {idx+1}/{total_slides} creating image")
            if on_progress:
                on_progress(int((idx / total_slides) * 40), f"Criando imagens: slide {idx+1}/{total_slides}...")

            slide_img_path = str(slides_dir / f"slide_{idx:03d}.png")
            slide_w = slide.get('width', 1920)
            slide_h = slide.get('height', 1080)
            ratio = min(canvas_w / slide_w, canvas_h / slide_h)
            target_w = int(slide_w * ratio)
            target_h = int(slide_h * ratio)
            target_w = target_w if target_w % 2 == 0 else target_w + 1
            target_h = target_h if target_h % 2 == 0 else target_h + 1

            await asyncio.to_thread(
                create_slide_base_image,
                slide, project_id, projects_dir, storage_dir,
                slide_img_path, target_w, target_h
            )

            if target_w < canvas_w or target_h < canvas_h:
                _p, _CW, _CH, _TW, _TH = slide_img_path, canvas_w, canvas_h, target_w, target_h
                def _pad(p=_p, cw=_CW, ch=_CH, tw=_TW, th=_TH):
                    c = Image.new('RGB', (cw, ch), (0, 0, 0))
                    s = Image.open(p)
                    c.paste(s, ((cw - tw) // 2, (ch - th) // 2))
                    c.save(p)
                    s.close()
                    c.close()
                await asyncio.to_thread(_pad)

            await asyncio.sleep(0)

        logger.info(f"[VIDEO] All {total_slides} images created")

        # ============================================================
        # PHASE 2: Single FFmpeg call with concat demuxer
        # ============================================================
        if on_progress:
            on_progress(50, f"Encodando video ({total_slides} slides)...")

        concat_list = str(work_dir / "slides_concat.txt")
        with open(concat_list, 'w') as f:
            for idx in range(total_slides):
                img = str(slides_dir / f"slide_{idx:03d}.png")
                dur = slides[idx].get('duration', default_duration) or default_duration
                dur = max(2.0, float(dur))
                f.write(f"file '{img}'\n")
                f.write(f"duration {dur}\n")
            if total_slides > 0:
                last_img = str(slides_dir / f"slide_{total_slides-1:03d}.png")
                f.write(f"file '{last_img}'\n")

        concat_output = str(work_dir / "concat_output.mp4")
        logger.info(f"[VIDEO] Single-pass FFmpeg encode ({total_slides} slides)")
        ok = await run_ffmpeg_async([
            '-f', 'concat', '-safe', '0',
            '-i', concat_list,
            '-c:v', 'libx264', '-preset', 'ultrafast',
            '-tune', 'stillimage',
            '-crf', '28',
            '-pix_fmt', 'yuv420p',
            '-r', '6',
            '-vf', f'scale={canvas_w}:{canvas_h}',
            '-movflags', '+faststart',
            concat_output
        ], timeout=600)

        if not ok or not Path(concat_output).exists():
            raise ValueError("FFmpeg encoding failed")

        logger.info(f"[VIDEO] Encode complete")

        # ============================================================
        # PHASE 3: Add silent audio track
        # ============================================================
        if on_progress:
            on_progress(75, "Adicionando audio...")

        with_audio = str(work_dir / "with_audio.mp4")
        audio_ok = await run_ffmpeg_async([
            '-i', concat_output,
            '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo',
            '-c:v', 'copy', '-c:a', 'aac', '-b:a', '64k',
            '-shortest',
            with_audio
        ], timeout=300)

        final_source = with_audio if (audio_ok and Path(with_audio).exists()) else concat_output

        if on_progress:
            on_progress(90, "Finalizando...")

        # ============================================================
        # PHASE 4: Output
        # ============================================================
        project_name = project_doc.get('name', 'course')
        safe_name = re.sub(r'[^\w\s-]', '', project_name).replace(' ', '_')
        timestamp = __import__('datetime').datetime.now().strftime("%Y%m%d_%H%M%S")

        if video_format == 'webm':
            output_filename = f"{safe_name}_{timestamp}.webm"
            output_path = str(Path(exports_dir) / output_filename)
            await run_ffmpeg_async([
                '-i', final_source,
                '-c:v', 'libvpx-vp9', '-b:v', '1M',
                '-cpu-used', '5', '-deadline', 'realtime',
                '-c:a', 'libopus', '-b:a', '96k',
                '-r', '6',
                output_path
            ], timeout=600)
        else:
            output_filename = f"{safe_name}_{timestamp}.mp4"
            output_path = str(Path(exports_dir) / output_filename)
            shutil.copy2(final_source, output_path)

        if not Path(output_path).exists():
            raise ValueError(f"Failed to create {video_format} file")

        if on_progress:
            on_progress(100, "Exportacao concluida!")

        logger.info(f"Video export complete: {output_path}")
        return output_path

    finally:
        # Clean up temp directory
        try:
            shutil.rmtree(work_dir)
        except Exception as e:
            logger.warning(f"Failed to cleanup temp dir: {e}")
