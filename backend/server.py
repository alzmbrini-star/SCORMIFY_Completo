from fastapi import FastAPI, APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from typing import List, Optional
import uuid
from datetime import datetime, timezone
import shutil
import aiofiles
import httpx
import io
from PIL import Image

from models import (
    Project, ProjectCreate, ProjectUpdate, Course, CourseMetadata,
    Slide, SlideCreate, SlideUpdate, SlideElement, ElementCreate, ElementUpdate,
    Animation, Annotation, AnnotationCreate, SlideAudio, GlobalAudio,
    JobStatus, ReorderSlidesRequest
)
from services.ppt_parser import parse_pptx
from services.ppt_image_parser import parse_pptx_high_fidelity
from services.scorm_exporter import export_scorm_package
from utils.system_deps import ensure_system_dependencies

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Check and install system dependencies (LibreOffice, poppler-utils)
# This runs at startup to ensure PPT conversion always works
logger.info("Starting Scormify API server...")
ensure_system_dependencies()

# Storage directories
STORAGE_DIR = ROOT_DIR / "storage"
UPLOADS_DIR = STORAGE_DIR / "uploads"
PROJECTS_DIR = STORAGE_DIR / "projects"
EXPORTS_DIR = STORAGE_DIR / "exports"

# Create directories
STORAGE_DIR.mkdir(exist_ok=True)
UPLOADS_DIR.mkdir(exist_ok=True)
PROJECTS_DIR.mkdir(exist_ok=True)
EXPORTS_DIR.mkdir(exist_ok=True)

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# HeyGen API Configuration
HEYGEN_API_KEY = os.environ.get('HEYGEN_API_KEY', '')
HEYGEN_BASE_URL = "https://api.heygen.com"
HEYGEN_HEADERS = {
    "X-Api-Key": HEYGEN_API_KEY,
    "Accept": "application/json",
    "Content-Type": "application/json"
}

# Create the main app
app = FastAPI(title="Scormify API", version="1.0.0")

# Create routers
api_router = APIRouter(prefix="/api")

# Job tracking (in-memory for simplicity)
jobs = {}

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Helper functions
def now_utc():
    return datetime.now(timezone.utc)

def serialize_doc(doc: dict) -> dict:
    """Serialize MongoDB document for JSON response"""
    if doc is None:
        return None
    doc.pop('_id', None)
    for key, value in doc.items():
        if isinstance(value, datetime):
            doc[key] = value.isoformat()
    return doc

async def get_project_by_id(project_id: str) -> Optional[dict]:
    """Get project from database"""
    doc = await db.projects.find_one({"id": project_id}, {"_id": 0})
    return doc

async def update_project(project_id: str, update_data: dict):
    """Update project in database"""
    update_data['updatedAt'] = now_utc().isoformat()
    await db.projects.update_one({"id": project_id}, {"$set": update_data})

# Background task for PPT processing
def process_ppt_upload(job_id: str, file_path: str, project_id: str):
    """Process uploaded PPT file in background using high-fidelity parser"""
    from pymongo import MongoClient
    
    try:
        jobs[job_id]['status'] = 'processing'
        jobs[job_id]['message'] = 'Converting PowerPoint slides to images...'
        jobs[job_id]['progress'] = 10
        
        # Use high-fidelity parser that renders slides as images
        course = parse_pptx_high_fidelity(file_path, project_id, str(PROJECTS_DIR))
        
        jobs[job_id]['progress'] = 80
        jobs[job_id]['message'] = 'Saving course data...'
        
        # Use synchronous MongoDB client for background task
        sync_client = MongoClient(mongo_url)
        sync_db = sync_client[os.environ['DB_NAME']]
        
        course_dict = course.model_dump()
        course_dict['createdAt'] = course.createdAt.isoformat()
        course_dict['updatedAt'] = course.updatedAt.isoformat()
        
        sync_db.projects.update_one(
            {"id": project_id},
            {"$set": {
                "course": course_dict,
                "status": "ready",
                "updatedAt": now_utc().isoformat()
            }}
        )
        
        sync_client.close()
        
        jobs[job_id]['status'] = 'completed'
        jobs[job_id]['progress'] = 100
        jobs[job_id]['message'] = 'Processing complete - slides rendered with high fidelity'
        jobs[job_id]['result'] = {'projectId': project_id}
        
    except Exception as e:
        logger.error(f"Error processing PPT: {e}")
        jobs[job_id]['status'] = 'failed'
        jobs[job_id]['message'] = str(e)
    finally:
        # Clean up uploaded file
        try:
            os.remove(file_path)
        except:
            pass

# API Routes

@api_router.get("/")
async def root():
    return {"message": "Scormify API v1.0"}

@api_router.get("/health")
async def health():
    return {"status": "healthy"}

# Project Routes

@api_router.get("/projects", response_model=List[dict])
async def list_projects():
    """List all projects"""
    projects = await db.projects.find({}, {"_id": 0}).sort("createdAt", -1).to_list(100)
    return projects

@api_router.post("/projects", response_model=dict)
async def create_project(data: ProjectCreate):
    """Create a new project"""
    project = Project(
        name=data.name,
        description=data.description
    )
    
    # Create default first slide
    default_slide = Slide(
        title="Slide 1",
        order=0,
        background="#FFFFFF"
    )
    project.course.slides = [default_slide]
    
    project_dict = project.model_dump()
    project_dict['createdAt'] = project.createdAt.isoformat()
    project_dict['updatedAt'] = project.updatedAt.isoformat()
    project_dict['course']['createdAt'] = project.course.createdAt.isoformat()
    project_dict['course']['updatedAt'] = project.course.updatedAt.isoformat()
    
    await db.projects.insert_one(project_dict)
    
    # Create project directory
    project_dir = PROJECTS_DIR / project.id
    (project_dir / "assets").mkdir(parents=True, exist_ok=True)
    
    return serialize_doc(project_dict)

@api_router.get("/projects/{project_id}", response_model=dict)
async def get_project(project_id: str):
    """Get project by ID"""
    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

@api_router.put("/projects/{project_id}", response_model=dict)
async def update_project_endpoint(project_id: str, data: ProjectUpdate):
    """Update project"""
    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    update_data = data.model_dump(exclude_unset=True)
    await update_project(project_id, update_data)
    
    return await get_project_by_id(project_id)

@api_router.delete("/projects/{project_id}")
async def delete_project(project_id: str):
    """Delete project"""
    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    await db.projects.delete_one({"id": project_id})
    
    # Delete project files
    project_dir = PROJECTS_DIR / project_id
    if project_dir.exists():
        shutil.rmtree(project_dir)
    
    return {"message": "Project deleted"}

# PPT Upload

@api_router.post("/ppt/upload")
async def upload_ppt(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    project_name: Optional[str] = None
):
    """Upload and process a PPT/PPTX file"""
    # Validate file type
    if not file.filename.lower().endswith(('.ppt', '.pptx')):
        raise HTTPException(status_code=400, detail="Invalid file type. Only PPT/PPTX files are allowed.")
    
    # Validate file size (max 50MB)
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 50MB.")
    
    # Create project
    project_name = project_name or Path(file.filename).stem
    project = Project(name=project_name)
    
    project_dict = project.model_dump()
    project_dict['createdAt'] = project.createdAt.isoformat()
    project_dict['updatedAt'] = project.updatedAt.isoformat()
    project_dict['course']['createdAt'] = project.course.createdAt.isoformat()
    project_dict['course']['updatedAt'] = project.course.updatedAt.isoformat()
    project_dict['status'] = 'processing'
    
    await db.projects.insert_one(project_dict)
    
    # Create project directory
    project_dir = PROJECTS_DIR / project.id
    (project_dir / "assets").mkdir(parents=True, exist_ok=True)
    
    # Save uploaded file
    upload_path = UPLOADS_DIR / f"{project.id}_{file.filename}"
    async with aiofiles.open(upload_path, 'wb') as f:
        await f.write(content)
    
    # Create job
    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        'id': job_id,
        'status': 'pending',
        'progress': 0,
        'message': 'Upload received, starting processing...',
        'result': None
    }
    
    # Start background processing
    background_tasks.add_task(process_ppt_upload, job_id, str(upload_path), project.id)
    
    return {
        "jobId": job_id,
        "projectId": project.id,
        "message": "File uploaded, processing started"
    }

@api_router.get("/job/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    """Get job status"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatus(**jobs[job_id])

# Course Routes

@api_router.get("/course/{project_id}")
async def get_course(project_id: str):
    """Get course data for a project"""
    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project.get('course', {})

@api_router.post("/course/{project_id}/save")
async def save_course(project_id: str, course_data: dict):
    """Save course data"""
    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    await update_project(project_id, {"course": course_data})
    return {"message": "Course saved"}

# Slide Routes

@api_router.post("/projects/{project_id}/slides")
async def create_slide(project_id: str, data: SlideCreate):
    """Add a new slide to the project"""
    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    course = project.get('course', {})
    slides = course.get('slides', [])
    
    # Get dimensions from first slide if not provided, to maintain consistency
    first_slide = slides[0] if slides else None
    slide_width = data.width or (first_slide.get('width') if first_slide else 1280)
    slide_height = data.height or (first_slide.get('height') if first_slide else 720)
    
    new_slide = Slide(
        title=data.title,
        background=data.background,
        width=slide_width,
        height=slide_height,
        order=len(slides)
    )
    
    slides.append(new_slide.model_dump())
    course['slides'] = slides
    
    await update_project(project_id, {"course": course})
    
    return new_slide.model_dump()

@api_router.put("/projects/{project_id}/slides/{slide_id}")
async def update_slide(project_id: str, slide_id: str, data: SlideUpdate):
    """Update a slide"""
    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    course = project.get('course', {})
    slides = course.get('slides', [])
    
    slide_index = next((i for i, s in enumerate(slides) if s.get('id') == slide_id), None)
    if slide_index is None:
        raise HTTPException(status_code=404, detail="Slide not found")
    
    update_data = data.model_dump(exclude_unset=True)
    slides[slide_index].update(update_data)
    course['slides'] = slides
    
    await update_project(project_id, {"course": course})
    
    return slides[slide_index]

@api_router.delete("/projects/{project_id}/slides/{slide_id}")
async def delete_slide(project_id: str, slide_id: str):
    """Delete a slide"""
    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    course = project.get('course', {})
    slides = course.get('slides', [])
    
    slides = [s for s in slides if s.get('id') != slide_id]
    
    # Re-order slides
    for i, slide in enumerate(slides):
        slide['order'] = i
    
    course['slides'] = slides
    await update_project(project_id, {"course": course})
    
    return {"message": "Slide deleted"}

@api_router.post("/projects/{project_id}/slides/{slide_id}/duplicate")
async def duplicate_slide(project_id: str, slide_id: str):
    """Duplicate a slide"""
    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    course = project.get('course', {})
    slides = course.get('slides', [])
    
    slide_index = next((i for i, s in enumerate(slides) if s.get('id') == slide_id), None)
    if slide_index is None:
        raise HTTPException(status_code=404, detail="Slide not found")
    
    # Deep copy the slide
    import copy
    new_slide = copy.deepcopy(slides[slide_index])
    new_slide['id'] = str(uuid.uuid4())
    new_slide['title'] = f"{new_slide.get('title', 'Slide')} (copy)"
    new_slide['order'] = slide_index + 1
    
    # Insert after original
    slides.insert(slide_index + 1, new_slide)
    
    # Re-order subsequent slides
    for i in range(slide_index + 2, len(slides)):
        slides[i]['order'] = i
    
    course['slides'] = slides
    await update_project(project_id, {"course": course})
    
    return new_slide

@api_router.post("/projects/{project_id}/normalize-dimensions")
async def normalize_slide_dimensions(project_id: str, target_width: int = 1280, target_height: int = 720):
    """Normalize all slides to the same dimensions, scaling elements proportionally"""
    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    course = project.get('course', {})
    slides = course.get('slides', [])
    
    normalized_count = 0
    
    for slide in slides:
        current_width = slide.get('width', 960)
        current_height = slide.get('height', 540)
        
        # Skip if already the target dimensions
        if current_width == target_width and current_height == target_height:
            continue
        
        # Calculate scale factors
        scale_x = target_width / current_width
        scale_y = target_height / current_height
        
        # Update slide dimensions
        slide['width'] = target_width
        slide['height'] = target_height
        
        # Scale all elements proportionally
        for element in slide.get('elements', []):
            # Scale position
            if 'x' in element:
                element['x'] = element['x'] * scale_x
            if 'y' in element:
                element['y'] = element['y'] * scale_y
            
            # Scale size
            if 'width' in element:
                element['width'] = element['width'] * scale_x
            if 'height' in element:
                element['height'] = element['height'] * scale_y
        
        # Scale annotations if present
        for annotation in slide.get('annotations', []):
            if 'points' in annotation:
                for point in annotation['points']:
                    if 'x' in point:
                        point['x'] = point['x'] * scale_x
                    if 'y' in point:
                        point['y'] = point['y'] * scale_y
        
        normalized_count += 1
    
    # Save updated course
    course['slides'] = slides
    await update_project(project_id, {"course": course})
    
    return {
        "message": f"Normalized {normalized_count} slides to {target_width}x{target_height}",
        "normalized_count": normalized_count,
        "target_dimensions": {"width": target_width, "height": target_height}
    }

@api_router.post("/projects/{project_id}/slides/reorder")
async def reorder_slides(project_id: str, data: ReorderSlidesRequest):
    """Reorder slides"""
    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    course = project.get('course', {})
    slides = course.get('slides', [])
    
    # Create mapping
    slide_map = {s['id']: s for s in slides}
    
    # Reorder based on provided IDs
    new_slides = []
    for i, slide_id in enumerate(data.slideIds):
        if slide_id in slide_map:
            slide = slide_map[slide_id]
            slide['order'] = i
            new_slides.append(slide)
    
    course['slides'] = new_slides
    await update_project(project_id, {"course": course})
    
    return {"message": "Slides reordered"}

# Element Routes

@api_router.post("/projects/{project_id}/slides/{slide_id}/elements")
async def add_element(project_id: str, slide_id: str, data: ElementCreate):
    """Add element to slide"""
    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    course = project.get('course', {})
    slides = course.get('slides', [])
    
    slide_index = next((i for i, s in enumerate(slides) if s.get('id') == slide_id), None)
    if slide_index is None:
        raise HTTPException(status_code=404, detail="Slide not found")
    
    element_data = data.model_dump(exclude_unset=True)
    # Ensure style is a dict if not provided
    if 'style' not in element_data or element_data.get('style') is None:
        element_data['style'] = {}
    element = SlideElement(**element_data)
    elements = slides[slide_index].get('elements', [])
    element_dict = element.model_dump()
    element_dict['zIndex'] = len(elements)
    elements.append(element_dict)
    
    slides[slide_index]['elements'] = elements
    course['slides'] = slides
    
    await update_project(project_id, {"course": course})
    
    return element_dict

@api_router.put("/projects/{project_id}/slides/{slide_id}/elements/{element_id}")
async def update_element(project_id: str, slide_id: str, element_id: str, data: ElementUpdate):
    """Update element"""
    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    course = project.get('course', {})
    slides = course.get('slides', [])
    
    slide_index = next((i for i, s in enumerate(slides) if s.get('id') == slide_id), None)
    if slide_index is None:
        raise HTTPException(status_code=404, detail="Slide not found")
    
    elements = slides[slide_index].get('elements', [])
    elem_index = next((i for i, e in enumerate(elements) if e.get('id') == element_id), None)
    if elem_index is None:
        raise HTTPException(status_code=404, detail="Element not found")
    
    update_data = data.model_dump(exclude_unset=True)
    elements[elem_index].update(update_data)
    
    slides[slide_index]['elements'] = elements
    course['slides'] = slides
    
    await update_project(project_id, {"course": course})
    
    return elements[elem_index]

@api_router.delete("/projects/{project_id}/slides/{slide_id}/elements/{element_id}")
async def delete_element(project_id: str, slide_id: str, element_id: str):
    """Delete element"""
    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    course = project.get('course', {})
    slides = course.get('slides', [])
    
    slide_index = next((i for i, s in enumerate(slides) if s.get('id') == slide_id), None)
    if slide_index is None:
        raise HTTPException(status_code=404, detail="Slide not found")
    
    elements = slides[slide_index].get('elements', [])
    elements = [e for e in elements if e.get('id') != element_id]
    
    slides[slide_index]['elements'] = elements
    course['slides'] = slides
    
    await update_project(project_id, {"course": course})
    
    return {"message": "Element deleted"}

# Media Upload

@api_router.post("/projects/{project_id}/media")
async def upload_media(project_id: str, file: UploadFile = File(...)):
    """Upload media file (image, audio, video) with automatic image optimization"""
    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Validate file type
    allowed_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.mp3', '.wav', '.ogg', '.mp4', '.webm'}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}")
    
    # Read and validate size
    content = await file.read()
    original_size = len(content)
    max_size = 100 * 1024 * 1024  # 100MB
    if original_size > max_size:
        raise HTTPException(status_code=400, detail="File too large")
    
    # Optimize images automatically
    image_extensions = {'.png', '.jpg', '.jpeg', '.webp'}
    optimized = False
    final_content = content
    
    if ext in image_extensions:
        try:
            # Open image with Pillow
            img = Image.open(io.BytesIO(content))
            original_width, original_height = img.size
            
            # Only optimize if image is large (> 500KB or dimensions > 1920px)
            should_optimize = original_size > 500 * 1024 or img.width > 1920 or img.height > 1080
            
            if should_optimize:
                # Convert RGBA to RGB for JPEG (remove alpha channel)
                if img.mode == 'RGBA' and ext in {'.jpg', '.jpeg'}:
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[3])
                    img = background
                elif img.mode == 'RGBA':
                    pass  # Keep alpha for PNG/WebP
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Calculate max dimensions (Full HD)
                max_width = 1920
                max_height = 1080
                
                # Resize if image is larger than max dimensions
                if img.width > max_width or img.height > max_height:
                    ratio = min(max_width / img.width, max_height / img.height)
                    new_size = (int(img.width * ratio), int(img.height * ratio))
                    img = img.resize(new_size, Image.Resampling.LANCZOS)
                    logger.info(f"Resized image from {original_width}x{original_height} to {new_size[0]}x{new_size[1]}")
                
                # Save optimized image to buffer
                output = io.BytesIO()
                
                if ext == '.png':
                    # For PNG, use optimize and reduce colors if possible
                    img.save(output, format='PNG', optimize=True)
                elif ext == '.webp':
                    # WebP with quality compression
                    img.save(output, format='WEBP', quality=85, method=6)
                else:
                    # JPEG with quality compression
                    img.save(output, format='JPEG', quality=85, optimize=True)
                
                optimized_content = output.getvalue()
                
                # Only use optimized version if it's actually smaller
                if len(optimized_content) < original_size:
                    final_content = optimized_content
                    optimized = True
                    logger.info(f"Image optimized: {original_size} bytes -> {len(final_content)} bytes ({100 - (len(final_content)/original_size*100):.1f}% reduction)")
                else:
                    logger.info(f"Optimization skipped: optimized size ({len(optimized_content)}) >= original ({original_size})")
            
        except Exception as e:
            logger.warning(f"Image optimization failed, using original: {e}")
            # Use original content if optimization fails
    
    # Save file
    file_id = str(uuid.uuid4())
    filename = f"{file_id}{ext}"
    file_path = PROJECTS_DIR / project_id / "assets" / filename
    
    async with aiofiles.open(file_path, 'wb') as f:
        await f.write(final_content)
    
    return {
        "id": file_id,
        "filename": filename,
        "url": f"/api/projects/{project_id}/assets/{filename}",
        "size": len(final_content),
        "originalSize": original_size,
        "optimized": optimized,
        "type": ext[1:]
    }

# Audio Recording

@api_router.post("/projects/{project_id}/slides/{slide_id}/audio")
async def upload_slide_audio(
    project_id: str,
    slide_id: str,
    file: UploadFile = File(...),
    audio_type: str = Form("narration")
):
    """Upload audio for a slide"""
    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Validate
    if not file.filename.lower().endswith(('.mp3', '.wav', '.ogg', '.webm')):
        raise HTTPException(status_code=400, detail="Invalid audio format")
    
    content = await file.read()
    
    # Save file
    file_id = str(uuid.uuid4())
    ext = Path(file.filename).suffix.lower()
    filename = f"audio_{file_id}{ext}"
    file_path = PROJECTS_DIR / project_id / "assets" / filename
    
    async with aiofiles.open(file_path, 'wb') as f:
        await f.write(content)
    
    # Update slide with audio
    course = project.get('course', {})
    slides = course.get('slides', [])
    
    slide_index = next((i for i, s in enumerate(slides) if s.get('id') == slide_id), None)
    if slide_index is None:
        raise HTTPException(status_code=404, detail="Slide not found")
    
    audio_data = {
        "id": file_id,
        "type": audio_type,
        "src": f"/api/projects/{project_id}/assets/{filename}",
        "filename": filename,
        "duration": 0,
        "volume": 1.0
    }
    
    audio_list = slides[slide_index].get('audio', [])
    audio_list.append(audio_data)
    slides[slide_index]['audio'] = audio_list
    
    course['slides'] = slides
    await update_project(project_id, {"course": course})
    
    return audio_data

# Global Audio (Soundtrack)

@api_router.post("/projects/{project_id}/global-audio")
async def set_global_audio(project_id: str, file: UploadFile = File(...)):
    """Set global soundtrack for the course"""
    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if not file.filename.lower().endswith(('.mp3', '.wav', '.ogg')):
        raise HTTPException(status_code=400, detail="Invalid audio format")
    
    content = await file.read()
    
    file_id = str(uuid.uuid4())
    ext = Path(file.filename).suffix.lower()
    filename = f"global_audio_{file_id}{ext}"
    file_path = PROJECTS_DIR / project_id / "assets" / filename
    
    async with aiofiles.open(file_path, 'wb') as f:
        await f.write(content)
    
    global_audio = {
        "id": file_id,
        "src": f"/api/projects/{project_id}/assets/{filename}",
        "filename": filename,
        "duration": 0,
        "volume": 0.5,
        "loop": True
    }
    
    course = project.get('course', {})
    course['globalAudio'] = global_audio
    
    await update_project(project_id, {"course": course})
    
    return global_audio


@api_router.delete("/projects/{project_id}/global-audio")
async def remove_global_audio(project_id: str):
    """Remove global audio from project"""
    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    course = project.get('course', {})
    
    # Remove global audio file if exists
    if course.get('globalAudio'):
        old_file = course['globalAudio'].get('filename')
        if old_file:
            assets_dir = Path(f"storage/projects/{project_id}/assets")
            old_path = assets_dir / old_file
            if old_path.exists():
                old_path.unlink()
    
    course['globalAudio'] = None
    await update_project(project_id, {"course": course})
    
    return {"message": "Global audio removed"}


@api_router.put("/projects/{project_id}/global-audio/volume")
async def update_global_audio_volume(project_id: str, volume: float):
    """Update global audio volume"""
    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    course = project.get('course', {})
    if not course.get('globalAudio'):
        raise HTTPException(status_code=404, detail="No global audio set")
    
    # Clamp volume between 0 and 1
    volume = max(0.0, min(1.0, volume))
    course['globalAudio']['volume'] = volume
    
    await update_project(project_id, {"course": course})
    
    return course['globalAudio']


@api_router.delete("/projects/{project_id}/slides/{slide_id}/audio/{audio_id}")
async def remove_slide_audio(project_id: str, slide_id: str, audio_id: str):
    """Remove audio from slide"""
    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    course = project.get('course', {})
    slides = course.get('slides', [])
    
    slide_index = next((i for i, s in enumerate(slides) if s.get('id') == slide_id), None)
    if slide_index is None:
        raise HTTPException(status_code=404, detail="Slide not found")
    
    audio_list = slides[slide_index].get('audio', [])
    
    # Find and remove audio
    audio_to_remove = next((a for a in audio_list if a.get('id') == audio_id), None)
    if not audio_to_remove:
        raise HTTPException(status_code=404, detail="Audio not found")
    
    # Remove audio file
    if audio_to_remove.get('filename'):
        assets_dir = Path(f"storage/projects/{project_id}/assets")
        audio_path = assets_dir / audio_to_remove['filename']
        if audio_path.exists():
            audio_path.unlink()
    
    # Update slide
    slides[slide_index]['audio'] = [a for a in audio_list if a.get('id') != audio_id]
    course['slides'] = slides
    
    await update_project(project_id, {"course": course})
    
    return {"message": "Audio removed from slide"}


@api_router.put("/projects/{project_id}/slides/{slide_id}/audio/{audio_id}/volume")
async def update_slide_audio_volume(project_id: str, slide_id: str, audio_id: str, volume: float):
    """Update slide audio volume"""
    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    course = project.get('course', {})
    slides = course.get('slides', [])
    
    slide_index = next((i for i, s in enumerate(slides) if s.get('id') == slide_id), None)
    if slide_index is None:
        raise HTTPException(status_code=404, detail="Slide not found")
    
    audio_list = slides[slide_index].get('audio', [])
    audio_index = next((i for i, a in enumerate(audio_list) if a.get('id') == audio_id), None)
    if audio_index is None:
        raise HTTPException(status_code=404, detail="Audio not found")
    
    # Clamp volume between 0 and 1
    volume = max(0.0, min(1.0, volume))
    audio_list[audio_index]['volume'] = volume
    slides[slide_index]['audio'] = audio_list
    course['slides'] = slides
    
    await update_project(project_id, {"course": course})
    
    return audio_list[audio_index]


@api_router.put("/projects/{project_id}/slides/{slide_id}/audio/{audio_id}/timing")
async def update_slide_audio_timing(project_id: str, slide_id: str, audio_id: str, data: dict):
    """Update slide audio timing (startTime and duration for trimming)"""
    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    course = project.get('course', {})
    slides = course.get('slides', [])
    
    slide_index = next((i for i, s in enumerate(slides) if s.get('id') == slide_id), None)
    if slide_index is None:
        raise HTTPException(status_code=404, detail="Slide not found")
    
    audio_list = slides[slide_index].get('audio', [])
    audio_index = next((i for i, a in enumerate(audio_list) if a.get('id') == audio_id), None)
    if audio_index is None:
        raise HTTPException(status_code=404, detail="Audio not found")
    
    # Store original duration if not already stored
    if 'originalDuration' not in audio_list[audio_index]:
        audio_list[audio_index]['originalDuration'] = audio_list[audio_index].get('duration', 10)
    
    # Update timing
    if data.get('startTime') is not None:
        audio_list[audio_index]['startTime'] = max(0, data['startTime'])
    if data.get('duration') is not None:
        audio_list[audio_index]['duration'] = max(0.5, data['duration'])
    
    slides[slide_index]['audio'] = audio_list
    course['slides'] = slides
    
    await update_project(project_id, {"course": course})
    
    return audio_list[audio_index]


# Annotations

@api_router.post("/projects/{project_id}/slides/{slide_id}/annotations")
async def add_annotation(project_id: str, slide_id: str, data: AnnotationCreate):
    """Add annotation to slide"""
    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    course = project.get('course', {})
    slides = course.get('slides', [])
    
    slide_index = next((i for i, s in enumerate(slides) if s.get('id') == slide_id), None)
    if slide_index is None:
        raise HTTPException(status_code=404, detail="Slide not found")
    
    annotation = Annotation(**data.model_dump())
    annotations = slides[slide_index].get('annotations', [])
    annotations.append(annotation.model_dump())
    
    slides[slide_index]['annotations'] = annotations
    course['slides'] = slides
    
    await update_project(project_id, {"course": course})
    
    return annotation.model_dump()

@api_router.put("/projects/{project_id}/slides/{slide_id}/annotations/{annotation_id}")
async def update_annotation(project_id: str, slide_id: str, annotation_id: str, update_data: dict):
    """Update annotation (for timeline settings)"""
    from models import AnnotationUpdate
    
    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    course = project.get('course', {})
    slides = course.get('slides', [])
    
    slide_index = next((i for i, s in enumerate(slides) if s.get('id') == slide_id), None)
    if slide_index is None:
        raise HTTPException(status_code=404, detail="Slide not found")
    
    annotations = slides[slide_index].get('annotations', [])
    annotation_index = next((i for i, a in enumerate(annotations) if a.get('id') == annotation_id), None)
    if annotation_index is None:
        raise HTTPException(status_code=404, detail="Annotation not found")
    
    # Update annotation with new data
    for key, value in update_data.items():
        if value is not None:
            annotations[annotation_index][key] = value
    
    slides[slide_index]['annotations'] = annotations
    course['slides'] = slides
    
    await update_project(project_id, {"course": course})
    
    return annotations[annotation_index]

@api_router.delete("/projects/{project_id}/slides/{slide_id}/annotations/{annotation_id}")
async def delete_annotation(project_id: str, slide_id: str, annotation_id: str):
    """Delete annotation"""
    project = await get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    course = project.get('course', {})
    slides = course.get('slides', [])
    
    slide_index = next((i for i, s in enumerate(slides) if s.get('id') == slide_id), None)
    if slide_index is None:
        raise HTTPException(status_code=404, detail="Slide not found")
    
    annotations = slides[slide_index].get('annotations', [])
    annotations = [a for a in annotations if a.get('id') != annotation_id]
    
    slides[slide_index]['annotations'] = annotations
    course['slides'] = slides
    
    await update_project(project_id, {"course": course})
    
    return {"message": "Annotation deleted"}

# SCORM Export

@api_router.post("/course/{project_id}/export-scorm")
async def export_scorm(project_id: str, background_tasks: BackgroundTasks):
    """Export project as SCORM 1.2 package"""
    project_doc = await get_project_by_id(project_id)
    if not project_doc:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Create job
    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        'id': job_id,
        'status': 'processing',
        'progress': 0,
        'message': 'Generating SCORM package...',
        'result': None
    }
    
    try:
        # Convert dict to Project model
        project = Project(**project_doc)
        
        # Generate package
        zip_path = export_scorm_package(
            project,
            str(PROJECTS_DIR),
            str(EXPORTS_DIR)
        )
        
        jobs[job_id]['status'] = 'completed'
        jobs[job_id]['progress'] = 100
        jobs[job_id]['message'] = 'SCORM package ready'
        jobs[job_id]['result'] = {
            'downloadUrl': f"/api/exports/{Path(zip_path).name}"
        }
        
        return {
            "jobId": job_id,
            "downloadUrl": f"/api/exports/{Path(zip_path).name}"
        }
        
    except Exception as e:
        logger.error(f"SCORM export error: {e}")
        jobs[job_id]['status'] = 'failed'
        jobs[job_id]['message'] = str(e)
        raise HTTPException(status_code=500, detail=str(e))

# Static file serving

@api_router.get("/projects/{project_id}/assets/{filename}")
async def serve_asset(project_id: str, filename: str):
    """Serve project asset"""
    file_path = PROJECTS_DIR / project_id / "assets" / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)

@api_router.get("/exports/{filename}")
async def serve_export(filename: str):
    """Serve exported SCORM package"""
    file_path = EXPORTS_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        file_path,
        media_type='application/zip',
        filename=filename
    )

# ============================================
# HeyGen API Endpoints
# ============================================

@api_router.get("/heygen/avatars")
async def list_heygen_avatars(limit: int = 100):
    """List available HeyGen avatars"""
    if not HEYGEN_API_KEY:
        raise HTTPException(status_code=500, detail="HeyGen API key not configured")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            response = await http_client.get(
                f"{HEYGEN_BASE_URL}/v2/avatars",
                headers=HEYGEN_HEADERS
            )
            
            if response.status_code != 200:
                logger.error(f"HeyGen avatars error: {response.status_code} - {response.text}")
                raise HTTPException(status_code=response.status_code, detail="Failed to fetch avatars from HeyGen")
            
            data = response.json()
            avatars = data.get("data", {}).get("avatars", [])
            
            # Filter and format avatars for frontend (limit to improve performance)
            formatted_avatars = []
            for avatar in avatars[:limit]:
                formatted_avatars.append({
                    "avatar_id": avatar.get("avatar_id"),
                    "avatar_name": avatar.get("avatar_name"),
                    "preview_image_url": avatar.get("preview_image_url"),
                    "preview_video_url": avatar.get("preview_video_url"),
                    "gender": avatar.get("gender"),
                })
            
            return {"avatars": formatted_avatars, "total": len(avatars)}
    except httpx.RequestError as e:
        logger.error(f"HeyGen request error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to connect to HeyGen: {str(e)}")

@api_router.get("/heygen/voices")
async def list_heygen_voices(language: Optional[str] = None):
    """List available HeyGen voices"""
    if not HEYGEN_API_KEY:
        raise HTTPException(status_code=500, detail="HeyGen API key not configured")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            response = await http_client.get(
                f"{HEYGEN_BASE_URL}/v2/voices",
                headers=HEYGEN_HEADERS
            )
            
            if response.status_code != 200:
                logger.error(f"HeyGen voices error: {response.status_code} - {response.text}")
                raise HTTPException(status_code=response.status_code, detail="Failed to fetch voices from HeyGen")
            
            data = response.json()
            voices = data.get("data", {}).get("voices", [])
            
            # Filter by language if specified
            if language:
                voices = [v for v in voices if language.lower() in v.get("language", "").lower()]
            
            # Format voices for frontend
            formatted_voices = []
            for voice in voices:
                formatted_voices.append({
                    "voice_id": voice.get("voice_id"),
                    "name": voice.get("name"),
                    "language": voice.get("language"),
                    "gender": voice.get("gender"),
                    "preview_audio": voice.get("preview_audio"),
                    "support_pause": voice.get("support_pause", False),
                })
            
            return {"voices": formatted_voices}
    except httpx.RequestError as e:
        logger.error(f"HeyGen request error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to connect to HeyGen: {str(e)}")

from pydantic import BaseModel, ConfigDict

class HeyGenVideoRequest(BaseModel):
    avatar_id: str
    voice_id: str
    script: str
    title: Optional[str] = "Generated Video"
    aspect_ratio: Optional[str] = "16:9"
    transparent_background: Optional[bool] = True  # Default to transparent

@api_router.post("/heygen/generate-video")
async def generate_heygen_video(request: HeyGenVideoRequest):
    """Generate a video using HeyGen API"""
    if not HEYGEN_API_KEY:
        raise HTTPException(status_code=500, detail="HeyGen API key not configured")
    
    if len(request.script) > 5000:
        raise HTTPException(status_code=400, detail="Script exceeds 5000 character limit")
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as http_client:
            
            # For transparent background, try the WebM endpoint first (v1/video.webm)
            if request.transparent_background:
                payload = {
                    "avatar_pose_id": request.avatar_id,
                    "avatar_style": "normal",
                    "input_text": request.script,
                    "voice_id": request.voice_id,
                    "dimension": {
                        "width": 1280 if request.aspect_ratio == "16:9" else 720,
                        "height": 720 if request.aspect_ratio == "16:9" else 1280
                    }
                }
                
                response = await http_client.post(
                    f"{HEYGEN_BASE_URL}/v1/video.webm",
                    headers=HEYGEN_HEADERS,
                    json=payload
                )
                
                # If WebM endpoint fails (avatar not supported), fall back to standard endpoint
                if response.status_code != 200:
                    error_data = response.json()
                    error_code = error_data.get("data", {}).get("error", {}).get("code", "")
                    
                    # Check if it's an avatar compatibility issue
                    if "AVATAR_NOT_FOUND" in str(error_code) or "avatar" in str(error_data).lower():
                        logger.warning(f"Avatar not compatible with WebM, falling back to standard video")
                        # Fall back to standard endpoint without transparent background
                        request.transparent_background = False
                    else:
                        logger.error(f"HeyGen WebM error: {response.status_code} - {response.text}")
                        error_msg = error_data.get("error", {}).get("message", "")
                        if not error_msg:
                            error_msg = error_data.get("data", {}).get("error", {}).get("message", response.text)
                        raise HTTPException(status_code=response.status_code, detail=f"HeyGen error: {error_msg}")
            
            # Standard video (either requested or fallback from WebM)
            if not request.transparent_background:
                payload = {
                    "video_inputs": [
                        {
                            "character": {
                                "type": "avatar",
                                "avatar_id": request.avatar_id,
                                "avatar_style": "normal"
                            },
                            "voice": {
                                "type": "text",
                                "input_text": request.script,
                                "voice_id": request.voice_id
                            }
                        }
                    ],
                    "dimension": {
                        "width": 1280 if request.aspect_ratio == "16:9" else 720,
                        "height": 720 if request.aspect_ratio == "16:9" else 1280
                    },
                    "title": request.title
                }
                
                response = await http_client.post(
                    f"{HEYGEN_BASE_URL}/v2/video/generate",
                    headers=HEYGEN_HEADERS,
                    json=payload
                )
            
            if response.status_code != 200:
                logger.error(f"HeyGen generate error: {response.status_code} - {response.text}")
                error_data = response.json()
                error_msg = error_data.get("error", {}).get("message", "")
                if not error_msg:
                    error_msg = error_data.get("data", {}).get("error", {}).get("message", response.text)
                raise HTTPException(status_code=response.status_code, detail=f"HeyGen error: {error_msg}")
            
            data = response.json()
            video_id = data.get("data", {}).get("video_id")
            
            if not video_id:
                raise HTTPException(status_code=500, detail="No video ID returned from HeyGen")
            
            # Store video generation request in database
            await db.heygen_videos.insert_one({
                "video_id": video_id,
                "avatar_id": request.avatar_id,
                "voice_id": request.voice_id,
                "script": request.script,
                "title": request.title,
                "status": "processing",
                "transparent": request.transparent_background,
                "created_at": now_utc()
            })
            
            return {
                "video_id": video_id,
                "status": "processing",
                "message": "Video generation started. Poll status endpoint for updates."
            }
    except httpx.RequestError as e:
        logger.error(f"HeyGen request error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to connect to HeyGen: {str(e)}")

# AI Script Generation
from emergentintegrations.llm.chat import LlmChat, UserMessage

class GenerateScriptRequest(BaseModel):
    topic: str
    style: Optional[str] = "educational"  # educational, conversational, formal, friendly
    duration: Optional[str] = "medium"  # short (30s), medium (1-2min), long (3-5min)
    language: Optional[str] = "português brasileiro"

@api_router.post("/ai/generate-script")
async def generate_ai_script(request: GenerateScriptRequest):
    """Generate a video script using AI"""
    emergent_key = os.environ.get('EMERGENT_LLM_KEY', '')
    
    if not emergent_key:
        raise HTTPException(status_code=500, detail="AI key not configured")
    
    # Define duration guidelines
    duration_guide = {
        "short": "30 segundos a 1 minuto (aproximadamente 75-150 palavras)",
        "medium": "1 a 2 minutos (aproximadamente 150-300 palavras)",
        "long": "3 a 5 minutos (aproximadamente 450-750 palavras)"
    }
    
    style_guide = {
        "educational": "tom educativo e didático, explicando conceitos de forma clara",
        "conversational": "tom conversacional e descontraído, como se estivesse falando com um amigo",
        "formal": "tom formal e profissional, adequado para ambientes corporativos",
        "friendly": "tom amigável e acolhedor, criando conexão com o espectador"
    }
    
    try:
        chat = LlmChat(
            api_key=emergent_key,
            session_id=f"script-gen-{uuid.uuid4()}",
            system_message=f"""Você é um roteirista profissional especializado em criar scripts para vídeos com avatares de IA.

Suas diretrizes:
1. Escreva em {request.language}
2. Use {style_guide.get(request.style, style_guide['educational'])}
3. O script deve ter {duration_guide.get(request.duration, duration_guide['medium'])}
4. Escreva de forma natural e fluida, como se fosse uma pessoa real falando
5. Use pausas naturais (vírgulas, pontos) para dar ritmo ao texto
6. Evite jargões técnicos complexos, a menos que sejam explicados
7. Comece com uma saudação ou gancho que prenda a atenção
8. Termine com uma conclusão clara ou call-to-action

IMPORTANTE: Retorne APENAS o script, sem títulos, numeração de cenas ou instruções de direção."""
        ).with_model("openai", "gpt-4o")
        
        user_message = UserMessage(
            text=f"Crie um script de vídeo sobre o seguinte tema:\n\n{request.topic}"
        )
        
        response = await chat.send_message(user_message)
        
        return {
            "script": response,
            "topic": request.topic,
            "style": request.style,
            "duration": request.duration,
            "language": request.language
        }
    except Exception as e:
        logger.error(f"AI script generation error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate script: {str(e)}")

@api_router.get("/heygen/video-status/{video_id}")
async def get_heygen_video_status(video_id: str):
    """Check the status of a HeyGen video generation"""
    if not HEYGEN_API_KEY:
        raise HTTPException(status_code=500, detail="HeyGen API key not configured")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            response = await http_client.get(
                f"{HEYGEN_BASE_URL}/v1/video_status.get",
                headers=HEYGEN_HEADERS,
                params={"video_id": video_id}
            )
            
            if response.status_code != 200:
                logger.error(f"HeyGen status error: {response.status_code} - {response.text}")
                raise HTTPException(status_code=response.status_code, detail="Failed to get video status")
            
            data = response.json()
            video_data = data.get("data", {})
            
            status = video_data.get("status", "unknown")
            video_url = video_data.get("video_url")
            thumbnail_url = video_data.get("thumbnail_url")
            duration = video_data.get("duration")
            
            # Update database
            await db.heygen_videos.update_one(
                {"video_id": video_id},
                {"$set": {
                    "status": status,
                    "video_url": video_url,
                    "thumbnail_url": thumbnail_url,
                    "duration": duration,
                    "updated_at": now_utc()
                }}
            )
            
            return {
                "video_id": video_id,
                "status": status,
                "video_url": video_url,
                "thumbnail_url": thumbnail_url,
                "duration": duration
            }
    except httpx.RequestError as e:
        logger.error(f"HeyGen request error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to connect to HeyGen: {str(e)}")

@api_router.get("/heygen/videos")
async def list_heygen_videos():
    """List all generated HeyGen videos"""
    videos = await db.heygen_videos.find().sort("created_at", -1).to_list(100)
    
    formatted_videos = []
    for video in videos:
        formatted_videos.append({
            "video_id": video.get("video_id"),
            "title": video.get("title"),
            "status": video.get("status"),
            "video_url": video.get("video_url"),
            "thumbnail_url": video.get("thumbnail_url"),
            "duration": video.get("duration"),
            "created_at": video.get("created_at").isoformat() if video.get("created_at") else None
        })
    
    return {"videos": formatted_videos}

# HeyGen Credits/Quota Check
@api_router.get("/heygen/credits")
async def get_heygen_credits():
    """Check remaining HeyGen API credits/quota"""
    if not HEYGEN_API_KEY:
        raise HTTPException(status_code=500, detail="HeyGen API key not configured")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            response = await http_client.get(
                f"{HEYGEN_BASE_URL}/v2/user/remaining_quota",
                headers=HEYGEN_HEADERS
            )
            
            if response.status_code != 200:
                logger.error(f"HeyGen credits error: {response.status_code} - {response.text}")
                raise HTTPException(status_code=response.status_code, detail="Failed to fetch credits from HeyGen")
            
            data = response.json()
            quota_data = data.get("data", {})
            
            return {
                "remaining_quota": quota_data.get("remaining_quota", 0),
                "used_quota": quota_data.get("used_quota"),
                "plan": quota_data.get("plan"),
                "has_credits": quota_data.get("remaining_quota", 0) > 0
            }
    except httpx.RequestError as e:
        logger.error(f"HeyGen credits request error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to connect to HeyGen: {str(e)}")

# HeyGen Webhook Endpoint
class HeyGenWebhookPayload(BaseModel):
    model_config = ConfigDict(extra="allow")
    event_type: Optional[str] = None
    video_id: Optional[str] = None
    status: Optional[str] = None
    video_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    duration: Optional[float] = None

@api_router.post("/heygen/webhook")
async def heygen_webhook(request: Request):
    """Receive webhook notifications from HeyGen when video processing completes"""
    try:
        # Get raw body for signature verification if needed
        body = await request.json()
        logger.info(f"HeyGen webhook received: {body}")
        
        # Extract relevant data
        event_type = body.get("event_type") or body.get("event") or "video.status"
        video_id = body.get("video_id") or body.get("data", {}).get("video_id")
        status = body.get("status") or body.get("data", {}).get("status")
        video_url = body.get("video_url") or body.get("data", {}).get("video_url")
        thumbnail_url = body.get("thumbnail_url") or body.get("data", {}).get("thumbnail_url")
        duration = body.get("duration") or body.get("data", {}).get("duration")
        
        if video_id:
            # Update video status in database
            update_data = {
                "webhook_received": True,
                "webhook_received_at": now_utc(),
                "updated_at": now_utc()
            }
            
            if status:
                update_data["status"] = status
            if video_url:
                update_data["video_url"] = video_url
            if thumbnail_url:
                update_data["thumbnail_url"] = thumbnail_url
            if duration:
                update_data["duration"] = duration
            
            result = await db.heygen_videos.update_one(
                {"video_id": video_id},
                {"$set": update_data}
            )
            
            logger.info(f"HeyGen webhook processed: video_id={video_id}, status={status}, matched={result.matched_count}")
            
            return {
                "success": True,
                "video_id": video_id,
                "status": status,
                "message": "Webhook processed successfully"
            }
        else:
            logger.warning(f"HeyGen webhook received without video_id: {body}")
            return {"success": True, "message": "Webhook received but no video_id found"}
            
    except Exception as e:
        logger.error(f"HeyGen webhook error: {e}")
        # Always return 200 to acknowledge receipt (avoid retries)
        return {"success": False, "error": str(e)}

# HeyGen Webhook Configuration Helper
@api_router.get("/heygen/webhook-url")
async def get_heygen_webhook_url(request: Request):
    """Get the webhook URL to configure in HeyGen dashboard"""
    # Get the base URL from the request or environment
    base_url = os.environ.get('REACT_APP_BACKEND_URL', str(request.base_url).rstrip('/'))
    webhook_url = f"{base_url}/api/heygen/webhook"
    
    return {
        "webhook_url": webhook_url,
        "instructions": [
            "1. Acesse o dashboard da HeyGen",
            "2. Vá em Settings > Webhooks",
            "3. Clique em 'Add Webhook Endpoint'",
            "4. Cole a URL acima no campo 'Endpoint URL'",
            "5. Selecione os eventos: 'video.completed', 'video.failed'",
            "6. Salve as configurações"
        ]
    }

# Include router
app.include_router(api_router)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
