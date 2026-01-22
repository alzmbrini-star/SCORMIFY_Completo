"""
PPT/PPTX Parser Service
Extracts slides, elements, animations, and transitions from PowerPoint files
"""
import os
import io
import base64
import logging
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from PIL import Image
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.dml.color import RGBColor
from pptx.oxml.ns import qn
import uuid

from models import (
    Course, CourseMetadata, Slide, SlideElement, ElementStyle,
    Animation, SlideTransition, SlideAudio
)

logger = logging.getLogger(__name__)

# EMU to pixels conversion (96 DPI)
EMU_PER_INCH = 914400
DPI = 96

def emu_to_px(emu: int) -> float:
    """Convert EMU to pixels"""
    if emu is None:
        return 0
    return (emu / EMU_PER_INCH) * DPI

def rgb_to_hex(rgb) -> str:
    """Convert RGBColor to hex string"""
    if rgb is None:
        return None
    try:
        if isinstance(rgb, RGBColor):
            return f"#{rgb.red:02x}{rgb.green:02x}{rgb.blue:02x}".upper()
        return None
    except:
        return None

def get_fill_color(shape) -> Optional[str]:
    """Extract fill color from shape"""
    try:
        if hasattr(shape, 'fill'):
            fill = shape.fill
            if fill.type is not None:
                if hasattr(fill, 'fore_color') and fill.fore_color:
                    try:
                        rgb = fill.fore_color.rgb
                        if rgb:
                            return rgb_to_hex(rgb)
                    except:
                        pass
        return None
    except:
        return None

def get_line_color(shape) -> Optional[str]:
    """Extract line/stroke color from shape"""
    try:
        if hasattr(shape, 'line'):
            line = shape.line
            if line.fill and line.fill.fore_color:
                try:
                    rgb = line.fill.fore_color.rgb
                    if rgb:
                        return rgb_to_hex(rgb)
                except:
                    pass
        return None
    except:
        return None

def extract_text_properties(paragraph) -> Dict[str, Any]:
    """Extract text properties from a paragraph"""
    props = {}
    try:
        # Alignment
        if paragraph.alignment:
            align_map = {
                PP_ALIGN.LEFT: 'left',
                PP_ALIGN.CENTER: 'center',
                PP_ALIGN.RIGHT: 'right',
                PP_ALIGN.JUSTIFY: 'justify'
            }
            props['textAlign'] = align_map.get(paragraph.alignment, 'left')
        
        # Get first run properties
        if paragraph.runs:
            run = paragraph.runs[0]
            font = run.font
            
            if font.name:
                props['fontFamily'] = font.name
            if font.size:
                props['fontSize'] = font.size.pt
            if font.bold:
                props['fontWeight'] = 'bold'
            if font.color and font.color.rgb:
                props['fontColor'] = rgb_to_hex(font.color.rgb)
    except Exception as e:
        logger.debug(f"Error extracting text props: {e}")
    
    return props

def shape_to_element(shape, index: int, assets_dir: Path, project_id: str) -> Optional[SlideElement]:
    """Convert a PowerPoint shape to a SlideElement"""
    try:
        element_id = str(uuid.uuid4())
        
        # Basic positioning
        x = emu_to_px(shape.left) if shape.left else 0
        y = emu_to_px(shape.top) if shape.top else 0
        width = emu_to_px(shape.width) if shape.width else 100
        height = emu_to_px(shape.height) if shape.height else 100
        rotation = shape.rotation if hasattr(shape, 'rotation') else 0
        
        style = ElementStyle()
        element_type = "shape"
        content = None
        src = None
        shape_type = None
        svg_path = None
        fallback_image = None
        hyperlink = None
        
        # Check for hyperlink
        if hasattr(shape, 'click_action') and shape.click_action:
            if shape.click_action.hyperlink and shape.click_action.hyperlink.address:
                hyperlink = shape.click_action.hyperlink.address
        
        # Determine shape type
        if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
            element_type = "image"
            # Extract image
            try:
                image = shape.image
                image_bytes = image.blob
                image_ext = image.ext
                image_filename = f"{element_id}.{image_ext}"
                image_path = assets_dir / image_filename
                
                with open(image_path, 'wb') as f:
                    f.write(image_bytes)
                
                src = f"/api/projects/{project_id}/assets/{image_filename}"
            except Exception as e:
                logger.warning(f"Failed to extract image: {e}")
                return None
                
        elif shape.shape_type == MSO_SHAPE_TYPE.TEXT_BOX or hasattr(shape, 'text_frame'):
            element_type = "text"
            try:
                if hasattr(shape, 'text_frame'):
                    text_frame = shape.text_frame
                    paragraphs = []
                    
                    for para in text_frame.paragraphs:
                        text = para.text
                        if text:
                            paragraphs.append(text)
                            # Extract style from first paragraph
                            if not style.fontFamily:
                                text_props = extract_text_properties(para)
                                for key, val in text_props.items():
                                    setattr(style, key, val)
                    
                    content = '\n'.join(paragraphs)
                    
                    # Vertical alignment
                    if hasattr(text_frame, 'vertical_anchor'):
                        v_align_map = {
                            MSO_ANCHOR.TOP: 'top',
                            MSO_ANCHOR.MIDDLE: 'middle',
                            MSO_ANCHOR.BOTTOM: 'bottom'
                        }
                        style.verticalAlign = v_align_map.get(text_frame.vertical_anchor, 'top')
            except Exception as e:
                logger.debug(f"Error extracting text: {e}")
                
        elif shape.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE:
            element_type = "shape"
            if hasattr(shape, 'auto_shape_type'):
                shape_type = str(shape.auto_shape_type).split('.')[-1].lower()
            
            # Also check for text in shapes
            if hasattr(shape, 'text_frame') and shape.text_frame:
                try:
                    text = shape.text_frame.text
                    if text:
                        content = text
                except:
                    pass
                    
        elif shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            # For groups, we'd ideally recurse, but for now render as image fallback
            element_type = "shape"
            shape_type = "group"
            
        elif shape.shape_type == MSO_SHAPE_TYPE.TABLE:
            element_type = "table"
            # Extract table data
            try:
                if hasattr(shape, 'table'):
                    table = shape.table
                    rows = []
                    for row in table.rows:
                        cells = []
                        for cell in row.cells:
                            cells.append(cell.text)
                        rows.append(cells)
                    content = str(rows)  # JSON-like representation
            except:
                pass
                
        elif shape.shape_type == MSO_SHAPE_TYPE.CHART:
            element_type = "chart"
            # Charts are complex - render as image fallback
            
        elif shape.shape_type == MSO_SHAPE_TYPE.MEDIA:
            element_type = "video"
            
        # Extract fill color
        fill_color = get_fill_color(shape)
        if fill_color:
            style.fill = fill_color
            
        # Extract stroke/line
        stroke_color = get_line_color(shape)
        if stroke_color:
            style.stroke = stroke_color
        
        # Skip empty elements
        if element_type == "text" and not content:
            return None
            
        return SlideElement(
            id=element_id,
            type=element_type,
            x=x,
            y=y,
            width=width,
            height=height,
            rotation=rotation,
            zIndex=index,
            content=content,
            src=src,
            style=style,
            shapeType=shape_type,
            svgPath=svg_path,
            fallbackImage=fallback_image,
            hyperlink=hyperlink
        )
        
    except Exception as e:
        logger.error(f"Error converting shape: {e}")
        return None

def extract_animations(slide_xml, elements: List[SlideElement]) -> Dict[str, List[Animation]]:
    """Extract animations from slide XML"""
    animations_map = {}
    
    try:
        # PowerPoint animations are stored in the timing tree
        # This is a simplified extraction - full implementation would parse p:timing
        pass
    except Exception as e:
        logger.debug(f"Error extracting animations: {e}")
    
    return animations_map

def extract_transition(pptx_slide) -> SlideTransition:
    """Extract slide transition"""
    transition = SlideTransition()
    
    try:
        # Transitions are in the slide XML under p:transition
        slide_part = pptx_slide.part
        slide_xml = slide_part._element
        
        # Find transition element
        trans_el = slide_xml.find('.//{http://schemas.openxmlformats.org/presentationml/2006/main}transition')
        if trans_el is not None:
            # Get transition type from child elements
            for child in trans_el:
                tag = child.tag.split('}')[-1]
                if tag not in ['sndAc']:  # Skip sound action
                    transition.type = tag.lower()
                    # Get direction if available
                    if 'dir' in child.attrib:
                        transition.direction = child.attrib['dir']
                    break
            
            # Get duration
            if 'spd' in trans_el.attrib:
                speed_map = {'slow': 1.0, 'med': 0.5, 'fast': 0.25}
                transition.duration = speed_map.get(trans_el.attrib['spd'], 0.5)
                
    except Exception as e:
        logger.debug(f"Error extracting transition: {e}")
    
    return transition

def get_slide_background(pptx_slide, assets_dir: Path, project_id: str) -> Tuple[str, Optional[str]]:
    """Extract slide background color or image"""
    bg_color = "#FFFFFF"
    bg_image = None
    
    try:
        background = pptx_slide.background
        if background and background.fill:
            fill = background.fill
            
            # Solid fill
            if fill.type is not None and hasattr(fill, 'fore_color'):
                try:
                    rgb = fill.fore_color.rgb
                    if rgb:
                        bg_color = rgb_to_hex(rgb)
                except:
                    pass
                    
            # Image fill
            if hasattr(fill, 'background_image') and fill.background_image:
                try:
                    image = fill.background_image
                    image_bytes = image.blob
                    image_ext = image.ext
                    image_filename = f"bg_{uuid.uuid4()}.{image_ext}"
                    image_path = assets_dir / image_filename
                    
                    with open(image_path, 'wb') as f:
                        f.write(image_bytes)
                    
                    bg_image = f"/api/projects/{project_id}/assets/{image_filename}"
                except Exception as e:
                    logger.debug(f"Error extracting background image: {e}")
                    
    except Exception as e:
        logger.debug(f"Error extracting background: {e}")
    
    return bg_color, bg_image

def parse_pptx(file_path: str, project_id: str, storage_dir: str) -> Course:
    """
    Parse a PPTX file and return a Course object
    """
    logger.info(f"Parsing PPTX: {file_path}")
    
    # Create storage directories
    project_dir = Path(storage_dir) / project_id
    assets_dir = project_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    
    conversion_report = {
        "success": [],
        "warnings": [],
        "errors": [],
        "fallbacks": []
    }
    
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
    
    slides = []
    
    for slide_idx, pptx_slide in enumerate(prs.slides):
        slide_id = str(uuid.uuid4())
        
        # Get background
        bg_color, bg_image = get_slide_background(pptx_slide, assets_dir, project_id)
        
        # Get transition
        transition = extract_transition(pptx_slide)
        
        # Extract elements
        elements = []
        for shape_idx, shape in enumerate(pptx_slide.shapes):
            element = shape_to_element(shape, shape_idx, assets_dir, project_id)
            if element:
                elements.append(element)
                conversion_report["success"].append(f"Slide {slide_idx + 1}: {element.type}")
        
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
            title=title[:50],  # Limit title length
            order=slide_idx,
            width=slide_width,
            height=slide_height,
            background=bg_color,
            backgroundImage=bg_image,
            elements=elements,
            transition=transition,
            notes=notes
        )
        
        slides.append(slide)
        logger.info(f"Parsed slide {slide_idx + 1} with {len(elements)} elements")
    
    course = Course(
        metadata=metadata,
        slides=slides,
        originalFilename=Path(file_path).name,
        conversionReport=conversion_report
    )
    
    logger.info(f"Successfully parsed {len(slides)} slides")
    return course

def render_slide_thumbnail(slide: Slide, assets_dir: Path, size: Tuple[int, int] = (320, 180)) -> str:
    """Generate a thumbnail for a slide"""
    try:
        # Create a simple thumbnail using PIL
        img = Image.new('RGB', (int(slide.width), int(slide.height)), slide.background or '#FFFFFF')
        
        # Resize to thumbnail
        img.thumbnail(size, Image.Resampling.LANCZOS)
        
        # Save
        thumb_filename = f"thumb_{slide.id}.png"
        thumb_path = assets_dir / thumb_filename
        img.save(thumb_path, 'PNG')
        
        return f"/assets/{thumb_filename}"
    except Exception as e:
        logger.error(f"Error generating thumbnail: {e}")
        return None
