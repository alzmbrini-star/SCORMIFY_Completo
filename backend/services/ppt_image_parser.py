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
from utils.system_deps import get_libreoffice_path, ensure_system_dependencies
from services.ppt_parser import extract_animations, extract_smartart, extract_animation_masks

logger = logging.getLogger(__name__)

# EMU to pixels conversion
EMU_PER_INCH = 914400
DPI = 96

def emu_to_px(emu: int) -> float:
    if emu is None:
        return 0
    return (emu / EMU_PER_INCH) * DPI


def check_slide_has_animations(pptx_slide) -> bool:
    """Check if a slide has any animations defined"""
    try:
        slide_xml = pptx_slide.part._element
        
        # PowerPoint animations are in the timing element
        nsmap = {
            'p': 'http://schemas.openxmlformats.org/presentationml/2006/main'
        }
        
        timing = slide_xml.find('.//p:timing', nsmap)
        if timing is None:
            return False
        
        # Check for any cTn (common time node) with presetClass (indicates animation)
        ctn_with_preset = timing.findall('.//p:cTn[@presetClass]', nsmap)
        if ctn_with_preset:
            return True
        
        # Also check for animEffect elements
        anim_effects = timing.findall('.//p:animEffect', nsmap)
        if anim_effects:
            return True
        
        return False
    except Exception as e:
        logger.debug(f"Error checking animations: {e}")
        return False


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
    
    # Find libreoffice executable
    libreoffice_path = get_libreoffice_path()
    
    # If LibreOffice not found, try to install it
    if not libreoffice_path:
        logger.warning("LibreOffice not found, attempting to install...")
        ensure_system_dependencies()
        libreoffice_path = get_libreoffice_path()
    
    if not libreoffice_path:
        raise RuntimeError(
            "LibreOffice is required for PPT conversion but could not be found or installed. "
            "Please install LibreOffice manually: sudo apt-get install libreoffice"
        )
    
    try:
        # First convert PPTX to PDF using LibreOffice
        cmd_pdf = f'"{libreoffice_path}" --headless --invisible --convert-to pdf --outdir "{temp_dir}" "{pptx_path}"'
        
        logger.info(f"Converting PPTX to PDF: {cmd_pdf}")
        result = subprocess.run(cmd_pdf, shell=True, capture_output=True, text=True, timeout=120)
        
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
    Fallback: Convert PPTX to images using multiple methods
    1. Try LibreOffice to PDF, then pdftoppm
    2. Try LibreOffice direct to PNG (only gets first slide)
    """
    output_path = Path(output_dir)
    temp_dir = output_path / "temp_fallback"
    temp_dir.mkdir(exist_ok=True)
    
    # Find libreoffice executable
    libreoffice_path = get_libreoffice_path()
    
    if not libreoffice_path:
        logger.error("LibreOffice not found in fallback method")
        raise RuntimeError("LibreOffice is required for PPT conversion")
    
    try:
        # Method 1: Convert to PDF first, then use pdftoppm directly
        cmd_pdf = f'"{libreoffice_path}" --headless --invisible --convert-to pdf --outdir "{temp_dir}" "{pptx_path}"'
        
        logger.info(f"Fallback: Converting to PDF first: {cmd_pdf}")
        result = subprocess.run(cmd_pdf, shell=True, capture_output=True, text=True, timeout=120)
        
        pdf_files = list(temp_dir.glob("*.pdf"))
        if pdf_files:
            pdf_path = pdf_files[0]
            
            # Use pdftoppm to convert PDF to images
            output_prefix = str(output_path / "slide")
            cmd_pdftoppm = f'pdftoppm -png -r 150 "{pdf_path}" "{output_prefix}"'
            
            logger.info(f"Converting PDF to images: {cmd_pdftoppm}")
            result = subprocess.run(cmd_pdftoppm, shell=True, capture_output=True, text=True, timeout=120)
            
            # pdftoppm creates files like slide-1.png, slide-2.png, etc.
            png_files = sorted(output_path.glob("slide-*.png"))
            
            if png_files:
                # Rename to our format: slide_001.png, slide_002.png, etc.
                renamed_files = []
                for i, f in enumerate(png_files):
                    new_name = output_path / f"slide_{i+1:03d}.png"
                    f.rename(new_name)
                    renamed_files.append(str(new_name))
                    logger.info(f"Created slide image: {new_name.name}")
                return renamed_files
        
        # Method 2: Direct PNG (last resort - only first slide)
        logger.warning("PDF method failed, trying direct PNG (will only get first slide)")
        cmd = f'"{libreoffice_path}" --headless --invisible --convert-to png --outdir "{output_path}" "{pptx_path}"'
        
        logger.info(f"Fallback conversion: {cmd}")
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
        
        png_files = sorted(output_path.glob("*.png"))
        return [str(f) for f in png_files]
        
    except Exception as e:
        logger.error(f"Fallback conversion failed: {e}")
        return []
    finally:
        # Cleanup temp directory
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)

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
        
        # First, check if this slide has animations
        has_animations = check_slide_has_animations(pptx_slide)
        logger.info(f"Slide {slide_idx + 1}: has_animations={has_animations}")
        
        # Get slide image path if available - ALWAYS use image background now
        background_image = None
        img_path = None
        img_filename = None
        if slide_idx < len(slide_images):
            img_path = slide_images[slide_idx]
            img_filename = Path(img_path).name
            
            # Resize image to match slide dimensions
            try:
                with Image.open(img_path) as img:
                    target_width = int(slide_width)
                    target_height = int(slide_height)
                    
                    if img.size != (target_width, target_height):
                        img_resized = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
                        img_resized.save(img_path)
                
                background_image = f"/api/projects/{project_id}/assets/{img_filename}"
            except Exception as e:
                logger.warning(f"Error processing slide image: {e}")
        
        if has_animations:
            # NEW APPROACH: Use background image + mask elements for animations
            # The background image shows everything, masks cover animated areas and reveal them with animations
            logger.info(f"Slide {slide_idx + 1}: Using MASK-BASED animations with background image")
            
            # Extract animation masks (positions and timing from XML)
            animation_masks = extract_animation_masks(pptx_slide)
            
            if animation_masks:
                # Get slide background color for masks
                slide_bg_color = "#FFFFFF"
                try:
                    if pptx_slide.background.fill.type is not None:
                        fill = pptx_slide.background.fill
                        if hasattr(fill, 'fore_color') and fill.fore_color and fill.fore_color.rgb:
                            slide_bg_color = f"#{fill.fore_color.rgb}"
                except:
                    pass
                
                # Create mask elements for each animation
                for mask in animation_masks:
                    # For ENTRANCE animations: create an opaque mask that will fade out to reveal content
                    # For EXIT animations: create a transparent mask that will fade in to hide content
                    # For EMPHASIS animations: create a highlight effect without masking
                    
                    is_entrance = mask['animation_type'] == 'entrance'
                    is_exit = mask['animation_type'] == 'exit'
                    is_emphasis = mask['animation_type'] == 'emphasis'
                    
                    if is_entrance:
                        # Entrance: mask starts OPAQUE (covering the element) and becomes TRANSPARENT
                        mask_element = SlideElement(
                            id=mask['id'],
                            type="animation_mask",
                            x=mask['x'],
                            y=mask['y'],
                            width=mask['width'],
                            height=mask['height'],
                            visible=True,
                            zIndex=1000 + len(elements),  # High z-index to be on top
                            style=ElementStyle(
                                fill=slide_bg_color,
                                opacity=1.0  # Start opaque
                            ),
                            animations=[Animation(
                                id=str(uuid.uuid4()),
                                type='entrance',  # We use entrance to fade OUT the mask (revealing content)
                                effect=mask['effect'],
                                trigger=mask['trigger'],
                                duration=mask['duration'],
                                delay=mask['start_time'],
                                easing='ease'
                            )]
                        )
                        elements.append(mask_element)
                        
                    elif is_exit:
                        # Exit: mask starts TRANSPARENT and becomes OPAQUE (hiding the element)
                        mask_element = SlideElement(
                            id=mask['id'],
                            type="animation_mask",
                            x=mask['x'],
                            y=mask['y'],
                            width=mask['width'],
                            height=mask['height'],
                            visible=True,
                            zIndex=1000 + len(elements),
                            style=ElementStyle(
                                fill=slide_bg_color,
                                opacity=0.0  # Start transparent
                            ),
                            animations=[Animation(
                                id=str(uuid.uuid4()),
                                type='exit',
                                effect=mask['effect'],
                                trigger=mask['trigger'],
                                duration=mask['duration'],
                                delay=mask['start_time'],
                                easing='ease'
                            )]
                        )
                        elements.append(mask_element)
                        
                    elif is_emphasis:
                        # Emphasis: create a highlight overlay effect
                        mask_element = SlideElement(
                            id=mask['id'],
                            type="animation_highlight",
                            x=mask['x'],
                            y=mask['y'],
                            width=mask['width'],
                            height=mask['height'],
                            visible=True,
                            zIndex=1000 + len(elements),
                            style=ElementStyle(
                                fill="transparent",
                                opacity=0.0
                            ),
                            animations=[Animation(
                                id=str(uuid.uuid4()),
                                type='emphasis',
                                effect=mask['effect'],
                                trigger=mask['trigger'],
                                duration=mask['duration'],
                                delay=mask['start_time'],
                                easing='ease'
                            )]
                        )
                        elements.append(mask_element)
                
                conversion_report["success"].append(f"Slide {slide_idx + 1}: {len(animation_masks)} animation masks with background image")
                logger.info(f"Created {len(animation_masks)} animation masks for slide {slide_idx + 1}")
            else:
                conversion_report["success"].append(f"Slide {slide_idx + 1}: Rendered as image (animations detected but no masks extracted)")
        else:
            # For slides WITHOUT animations: just use the image background
            conversion_report["success"].append(f"Slide {slide_idx + 1}: Rendered as image (no animations)")
            logger.info(f"Slide {slide_idx + 1}: No animations, using image only")
        
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
