"""
High-Fidelity PPT Parser using LibreOffice
Converts each slide to PNG image for exact visual fidelity
"""
import os
import subprocess
import shutil
import logging
from pathlib import Path
from typing import List, Tuple, Optional
import uuid
from PIL import Image

from pptx import Presentation
from pptx.util import Emu

from models import (
    Course, CourseMetadata, Slide, SlideElement, ElementStyle,
    Animation, SlideTransition
)

logger = logging.getLogger(__name__)

# EMU to pixels conversion
EMU_PER_INCH = 914400
DPI = 96

def emu_to_px(emu: int) -> float:
    if emu is None:
        return 0
    return (emu / EMU_PER_INCH) * DPI

def convert_pptx_to_images(pptx_path: str, output_dir: str, dpi: int = 150) -> List[str]:
    """
    Convert PPTX to PNG images using LibreOffice
    Returns list of image paths
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Create temp directory for conversion
    temp_dir = Path(output_dir) / "temp_convert"
    temp_dir.mkdir(exist_ok=True)
    
    try:
        # First convert PPTX to PDF using LibreOffice
        cmd_pdf = [
            'libreoffice',
            '--headless',
            '--invisible',
            '--convert-to', 'pdf',
            '--outdir', str(temp_dir),
            pptx_path
        ]
        
        logger.info(f"Converting PPTX to PDF: {' '.join(cmd_pdf)}")
        result = subprocess.run(cmd_pdf, capture_output=True, text=True, timeout=120)
        
        if result.returncode != 0:
            logger.error(f"LibreOffice PDF conversion failed: {result.stderr}")
            # Fallback: try direct PNG conversion
            return convert_pptx_to_images_fallback(pptx_path, output_dir)
        
        # Find the PDF file
        pdf_files = list(temp_dir.glob("*.pdf"))
        if not pdf_files:
            logger.error("No PDF file generated")
            return convert_pptx_to_images_fallback(pptx_path, output_dir)
        
        pdf_path = pdf_files[0]
        
        # Convert PDF to images using pdftoppm (if available) or PIL
        try:
            # Try pdftoppm for better quality
            from pdf2image import convert_from_path
            images = convert_from_path(str(pdf_path), dpi=dpi)
            
            image_paths = []
            for i, img in enumerate(images):
                img_filename = f"slide_{i+1:03d}.png"
                img_path = output_path / img_filename
                img.save(str(img_path), 'PNG')
                image_paths.append(str(img_path))
                logger.info(f"Saved slide image: {img_filename}")
            
            return image_paths
            
        except ImportError:
            logger.warning("pdf2image not available, using fallback")
            return convert_pptx_to_images_fallback(pptx_path, output_dir)
            
    except subprocess.TimeoutExpired:
        logger.error("LibreOffice conversion timed out")
        return convert_pptx_to_images_fallback(pptx_path, output_dir)
    except Exception as e:
        logger.error(f"Error converting PPTX: {e}")
        return convert_pptx_to_images_fallback(pptx_path, output_dir)
    finally:
        # Cleanup temp directory
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)

def convert_pptx_to_images_fallback(pptx_path: str, output_dir: str) -> List[str]:
    """
    Fallback: Convert directly to PNG using LibreOffice
    """
    output_path = Path(output_dir)
    
    try:
        # Direct PNG conversion
        cmd = [
            'libreoffice',
            '--headless',
            '--invisible',
            '--convert-to', 'png',
            '--outdir', str(output_path),
            pptx_path
        ]
        
        logger.info(f"Fallback conversion: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        # LibreOffice creates PNG files for each slide
        png_files = sorted(output_path.glob("*.png"))
        return [str(f) for f in png_files]
        
    except Exception as e:
        logger.error(f"Fallback conversion failed: {e}")
        return []

def parse_pptx_high_fidelity(file_path: str, project_id: str, storage_dir: str) -> Course:
    """
    Parse PPTX with high visual fidelity by rendering slides as images
    """
    logger.info(f"High-fidelity parsing PPTX: {file_path}")
    
    # Create storage directories
    project_dir = Path(storage_dir) / project_id
    assets_dir = project_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    
    conversion_report = {
        "success": [],
        "warnings": [],
        "errors": [],
        "method": "high_fidelity_image"
    }
    
    # Open PPTX for metadata and text extraction
    try:
        prs = Presentation(file_path)
    except Exception as e:
        logger.error(f"Failed to open PPTX: {e}")
        raise ValueError(f"Could not open PowerPoint file: {e}")
    
    # Get presentation dimensions
    slide_width = emu_to_px(prs.slide_width)
    slide_height = emu_to_px(prs.slide_height)
    
    # Extract metadata
    core_props = prs.core_properties
    metadata = CourseMetadata(
        title=core_props.title or Path(file_path).stem,
        author=core_props.author or "",
        description=core_props.subject or "",
        keywords=core_props.keywords.split(',') if core_props.keywords else []
    )
    
    # Convert slides to images
    logger.info("Converting slides to images...")
    slide_images = convert_pptx_to_images(file_path, str(assets_dir))
    
    slides = []
    num_slides = len(prs.slides)
    
    for slide_idx, pptx_slide in enumerate(prs.slides):
        slide_id = str(uuid.uuid4())
        elements = []
        
        # Get slide image if available
        background_image = None
        if slide_idx < len(slide_images):
            img_path = slide_images[slide_idx]
            img_filename = Path(img_path).name
            
            # Resize image to match slide dimensions
            try:
                with Image.open(img_path) as img:
                    # Calculate proper dimensions maintaining aspect ratio
                    target_width = int(slide_width)
                    target_height = int(slide_height)
                    
                    # Resize if needed
                    if img.size != (target_width, target_height):
                        img_resized = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
                        img_resized.save(img_path)
                
                background_image = f"/api/projects/{project_id}/assets/{img_filename}"
                conversion_report["success"].append(f"Slide {slide_idx + 1}: Rendered as image")
            except Exception as e:
                logger.warning(f"Error processing slide image: {e}")
        
        # Extract text elements for accessibility/search (overlay on image)
        for shape_idx, shape in enumerate(pptx_slide.shapes):
            if hasattr(shape, 'text_frame') and shape.text_frame:
                try:
                    text = shape.text_frame.text
                    if text and text.strip():
                        # Create invisible text element for accessibility
                        element = SlideElement(
                            id=str(uuid.uuid4()),
                            type="text",
                            x=emu_to_px(shape.left) if shape.left else 0,
                            y=emu_to_px(shape.top) if shape.top else 0,
                            width=emu_to_px(shape.width) if shape.width else 100,
                            height=emu_to_px(shape.height) if shape.height else 50,
                            content=text,
                            visible=False,  # Hidden - image provides visual
                            zIndex=shape_idx,
                            style=ElementStyle(opacity=0)  # Invisible for accessibility
                        )
                        elements.append(element)
                except:
                    pass
        
        # Get slide title
        title = f"Slide {slide_idx + 1}"
        if pptx_slide.shapes.title:
            try:
                title = pptx_slide.shapes.title.text or title
            except:
                pass
        
        # Get notes
        notes = None
        if pptx_slide.has_notes_slide:
            try:
                notes_slide = pptx_slide.notes_slide
                notes = notes_slide.notes_text_frame.text
            except:
                pass
        
        slide = Slide(
            id=slide_id,
            title=title[:50],
            order=slide_idx,
            width=slide_width,
            height=slide_height,
            background="#FFFFFF",
            backgroundImage=background_image,
            elements=elements,
            notes=notes
        )
        
        slides.append(slide)
        logger.info(f"Processed slide {slide_idx + 1}")
    
    course = Course(
        metadata=metadata,
        slides=slides,
        originalFilename=Path(file_path).name,
        conversionReport=conversion_report
    )
    
    logger.info(f"Successfully processed {len(slides)} slides with high fidelity")
    return course
