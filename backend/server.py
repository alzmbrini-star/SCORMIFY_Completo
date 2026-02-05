from fastapi import FastAPI, APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import re
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone
import shutil
import aiofiles
import httpx
import io
import asyncio
import json
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

# HeyGen Credits Cache (to avoid slow repeated API calls)
heygen_credits_cache: Dict[str, Any] = {
    "data": None,
    "timestamp": None,
    "ttl": 60  # Cache for 60 seconds
}

# SSE Event Store for HeyGen webhook notifications
# Maps video_id to list of asyncio.Event objects waiting for updates
heygen_sse_subscribers: Dict[str, List[asyncio.Queue]] = {}

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

# HTML Standalone Export
from services.html_exporter import generate_standalone_html

@api_router.post("/course/{project_id}/export-html")
async def export_html(project_id: str):
    """Export project as standalone HTML file"""
    project_doc = await get_project_by_id(project_id)
    if not project_doc:
        raise HTTPException(status_code=404, detail="Project not found")
    
    try:
        # Get assets directory
        assets_dir = str(PROJECTS_DIR / project_id / "assets")
        
        # Get base URL for external assets
        base_url = os.environ.get('REACT_APP_BACKEND_URL', '')
        
        # Generate HTML
        html_content = await generate_standalone_html(
            project_doc,
            assets_dir,
            base_url
        )
        
        # Save HTML file
        project_name = project_doc.get('name', 'course')
        safe_name = re.sub(r'[^\w\s-]', '', project_name).replace(' ', '_')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_name}_{timestamp}.html"
        
        html_path = EXPORTS_DIR / filename
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return {
            "downloadUrl": f"/api/exports/{filename}",
            "filename": filename,
            "message": "HTML standalone file generated successfully"
        }
        
    except Exception as e:
        logger.error(f"HTML export error: {e}")
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
    """Serve exported files (SCORM zip or HTML)"""
    file_path = EXPORTS_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    # Determine media type based on file extension
    if filename.endswith('.html'):
        media_type = 'text/html'
    elif filename.endswith('.zip'):
        media_type = 'application/zip'
    else:
        media_type = 'application/octet-stream'
    
    return FileResponse(
        file_path,
        media_type=media_type,
        filename=filename if media_type == 'application/zip' else None  # Only force download for zip files
    )

# ============================================
# HeyGen API Endpoints
# ============================================

@api_router.get("/heygen/avatars")
async def list_heygen_avatars(limit: int = 200, gender: Optional[str] = None):
    """List available HeyGen avatars with optional gender filter"""
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
            
            # Filter by gender if specified
            if gender and gender.lower() != 'all':
                avatars = [a for a in avatars if a.get("gender", "").lower() == gender.lower()]
            
            # Format avatars for frontend
            formatted_avatars = []
            for avatar in avatars[:limit]:
                formatted_avatars.append({
                    "avatar_id": avatar.get("avatar_id"),
                    "avatar_name": avatar.get("avatar_name"),
                    "preview_image_url": avatar.get("preview_image_url"),
                    "preview_video_url": avatar.get("preview_video_url"),
                    "gender": avatar.get("gender"),
                })
            
            # Get unique genders for filter options
            all_genders = list(set(a.get("gender", "unknown") for a in data.get("data", {}).get("avatars", []) if a.get("gender")))
            
            return {
                "avatars": formatted_avatars, 
                "total": len(avatars),
                "available_genders": sorted(all_genders)
            }
    except httpx.RequestError as e:
        logger.error(f"HeyGen request error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to connect to HeyGen: {str(e)}")

@api_router.get("/heygen/voices")
async def list_heygen_voices(language: Optional[str] = None, gender: Optional[str] = None):
    """List available HeyGen voices with optional language and gender filters"""
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
            all_voices = data.get("data", {}).get("voices", [])
            voices = all_voices.copy()
            
            # Filter by language if specified
            if language and language.lower() != 'all':
                # Support specific language codes like "pt-BR", "pt-PT", "en-US"
                if '-' in language:
                    # Exact match for language code
                    voices = [v for v in voices if v.get("language", "").lower() == language.lower()]
                else:
                    # Partial match (e.g., "portuguese" matches "Portuguese (Brazil)")
                    voices = [v for v in voices if language.lower() in v.get("language", "").lower()]
            
            # Filter by gender if specified
            if gender and gender.lower() != 'all':
                voices = [v for v in voices if v.get("gender", "").lower() == gender.lower()]
            
            # Format voices for frontend
            formatted_voices = []
            for voice in voices:
                lang = voice.get("language", "")
                voice_name = voice.get("name", "")
                # Determine language code and country
                lang_code = ""
                country_flag = ""
                
                # Check if Portuguese and determine variant
                if "portuguese" in lang.lower():
                    # Check voice name for Brazil indicators
                    if "brazil" in voice_name.lower() or "brasil" in voice_name.lower():
                        lang_code = "pt-BR"
                        country_flag = "🇧🇷"
                    elif "portugal" in voice_name.lower():
                        lang_code = "pt-PT"
                        country_flag = "🇵🇹"
                    else:
                        # Default Portuguese to Brazil (most common in LatAm)
                        lang_code = "pt"
                        country_flag = "🇧🇷"
                elif "brazil" in lang.lower() or "brasileiro" in lang.lower():
                    lang_code = "pt-BR"
                    country_flag = "🇧🇷"
                elif "portugal" in lang.lower() or "português" in lang.lower():
                    lang_code = "pt-PT"
                    country_flag = "🇵🇹"
                elif "english" in lang.lower():
                    if "us" in lang.lower() or "american" in lang.lower():
                        lang_code = "en-US"
                        country_flag = "🇺🇸"
                    elif "uk" in lang.lower() or "british" in lang.lower():
                        lang_code = "en-GB"
                        country_flag = "🇬🇧"
                    else:
                        lang_code = "en"
                        country_flag = "🇺🇸"
                elif "spanish" in lang.lower() or "español" in lang.lower():
                    lang_code = "es"
                    country_flag = "🇪🇸"
                elif "french" in lang.lower():
                    lang_code = "fr"
                    country_flag = "🇫🇷"
                elif "german" in lang.lower():
                    lang_code = "de"
                    country_flag = "🇩🇪"
                elif "italian" in lang.lower():
                    lang_code = "it"
                    country_flag = "🇮🇹"
                
                formatted_voices.append({
                    "voice_id": voice.get("voice_id"),
                    "name": voice_name,
                    "language": lang,
                    "language_code": lang_code,
                    "country_flag": country_flag,
                    "gender": voice.get("gender"),
                    "preview_audio": voice.get("preview_audio"),
                    "support_pause": voice.get("support_pause", False),
                })
            
            # Get unique languages for filter options
            language_options = []
            seen_languages = set()
            for v in all_voices:
                lang = v.get("language", "")
                if lang and lang not in seen_languages:
                    seen_languages.add(lang)
                    # Create a simplified label
                    if "brazil" in lang.lower():
                        language_options.append({"value": lang, "label": "🇧🇷 Português (Brasil)", "code": "pt-BR"})
                    elif "portugal" in lang.lower():
                        language_options.append({"value": lang, "label": "🇵🇹 Português (Portugal)", "code": "pt-PT"})
                    elif "english" in lang.lower():
                        if "us" in lang.lower() or "american" in lang.lower():
                            language_options.append({"value": lang, "label": "🇺🇸 English (US)", "code": "en-US"})
                        elif "uk" in lang.lower() or "british" in lang.lower():
                            language_options.append({"value": lang, "label": "🇬🇧 English (UK)", "code": "en-GB"})
                        else:
                            language_options.append({"value": lang, "label": "🇺🇸 English", "code": "en"})
                    elif "spanish" in lang.lower():
                        language_options.append({"value": lang, "label": "🇪🇸 Español", "code": "es"})
                    elif "french" in lang.lower():
                        language_options.append({"value": lang, "label": "🇫🇷 Français", "code": "fr"})
                    elif "german" in lang.lower():
                        language_options.append({"value": lang, "label": "🇩🇪 Deutsch", "code": "de"})
                    elif "italian" in lang.lower():
                        language_options.append({"value": lang, "label": "🇮🇹 Italiano", "code": "it"})
                    else:
                        language_options.append({"value": lang, "label": lang, "code": ""})
            
            # Sort by label
            language_options.sort(key=lambda x: x["label"])
            
            # Get unique genders
            available_genders = list(set(v.get("gender", "unknown") for v in all_voices if v.get("gender")))
            
            return {
                "voices": formatted_voices,
                "total": len(voices),
                "available_languages": language_options,
                "available_genders": sorted(available_genders)
            }
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
    project_id: Optional[str] = None  # Associate video with a project

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
                        logger.warning("Avatar not compatible with WebM, falling back to standard video")
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
                "project_id": request.project_id,
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
async def list_heygen_videos(project_id: Optional[str] = None):
    """List all generated HeyGen videos, optionally filtered by project"""
    query = {}
    if project_id:
        query["project_id"] = project_id
    
    videos = await db.heygen_videos.find(query).sort("created_at", -1).to_list(100)
    
    formatted_videos = []
    for video in videos:
        formatted_videos.append({
            "video_id": video.get("video_id"),
            "title": video.get("title"),
            "status": video.get("status"),
            "video_url": video.get("video_url"),
            "thumbnail_url": video.get("thumbnail_url"),
            "duration": video.get("duration"),
            "script": video.get("script"),
            "avatar_id": video.get("avatar_id"),
            "voice_id": video.get("voice_id"),
            "project_id": video.get("project_id"),
            "transparent": video.get("transparent"),
            "created_at": video.get("created_at").isoformat() if video.get("created_at") else None
        })
    
    return {"videos": formatted_videos}


@api_router.get("/heygen/videos/{video_id}/refresh")
async def refresh_heygen_video_status(video_id: str):
    """Refresh video status from HeyGen API and update database"""
    if not HEYGEN_API_KEY:
        raise HTTPException(status_code=500, detail="HeyGen API key not configured")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            response = await http_client.get(
                f"{HEYGEN_BASE_URL}/v1/video_status.get?video_id={video_id}",
                headers=HEYGEN_HEADERS
            )
            
            if response.status_code != 200:
                logger.error(f"HeyGen status error: {response.status_code} - {response.text}")
                raise HTTPException(status_code=response.status_code, detail="Failed to fetch video status")
            
            data = response.json()
            video_data = data.get("data", {})
            status = video_data.get("status", "unknown")
            video_url = video_data.get("video_url")
            thumbnail_url = video_data.get("thumbnail_url")
            duration = video_data.get("duration")
            
            # Update database with fresh status
            update_data = {"status": status}
            if video_url:
                update_data["video_url"] = video_url
            if thumbnail_url:
                update_data["thumbnail_url"] = thumbnail_url
            if duration:
                update_data["duration"] = duration
            
            await db.heygen_videos.update_one(
                {"video_id": video_id},
                {"$set": update_data}
            )
            
            # Get full video data from database
            video_doc = await db.heygen_videos.find_one({"video_id": video_id})
            
            return {
                "video_id": video_id,
                "status": status,
                "video_url": video_url,
                "thumbnail_url": thumbnail_url,
                "duration": duration,
                "title": video_doc.get("title") if video_doc else None,
                "script": video_doc.get("script") if video_doc else None,
                "project_id": video_doc.get("project_id") if video_doc else None,
                "created_at": video_doc.get("created_at").isoformat() if video_doc and video_doc.get("created_at") else None
            }
    except httpx.RequestError as e:
        logger.error(f"HeyGen request error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to connect to HeyGen: {str(e)}")

# HeyGen Credits/Quota Check
@api_router.get("/heygen/credits")
async def get_heygen_credits(force_refresh: bool = False):
    """Check remaining HeyGen API credits/quota (with caching)"""
    if not HEYGEN_API_KEY:
        raise HTTPException(status_code=500, detail="HeyGen API key not configured")
    
    # Check cache first (unless force refresh requested)
    if not force_refresh and heygen_credits_cache["data"] is not None:
        cache_age = (datetime.now(timezone.utc) - heygen_credits_cache["timestamp"]).total_seconds()
        if cache_age < heygen_credits_cache["ttl"]:
            logger.info(f"Returning cached HeyGen credits (age: {cache_age:.1f}s)")
            return heygen_credits_cache["data"]
    
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
            
            result = {
                "remaining_quota": quota_data.get("remaining_quota", 0),
                "used_quota": quota_data.get("used_quota"),
                "plan": quota_data.get("plan"),
                "has_credits": quota_data.get("remaining_quota", 0) > 0
            }
            
            # Update cache
            heygen_credits_cache["data"] = result
            heygen_credits_cache["timestamp"] = datetime.now(timezone.utc)
            
            return result
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
            
            # Notify SSE subscribers waiting for this video
            if video_id in heygen_sse_subscribers:
                event_data = {
                    "event": "video_update",
                    "video_id": video_id,
                    "status": status,
                    "video_url": video_url,
                    "thumbnail_url": thumbnail_url,
                    "duration": duration
                }
                for queue in heygen_sse_subscribers[video_id]:
                    try:
                        queue.put_nowait(event_data)
                    except asyncio.QueueFull:
                        pass
                logger.info(f"Notified {len(heygen_sse_subscribers[video_id])} SSE subscribers for video {video_id}")
            
            # Invalidate credits cache after video generation
            heygen_credits_cache["data"] = None
            heygen_credits_cache["timestamp"] = None
            
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

# SSE endpoint for real-time video status updates
@api_router.get("/heygen/video-events/{video_id}")
async def heygen_video_events(video_id: str, request: Request):
    """Server-Sent Events stream for real-time video status updates.
    The frontend connects to this endpoint to receive webhook notifications without polling."""
    
    async def event_generator():
        queue = asyncio.Queue(maxsize=10)
        
        # Register subscriber
        if video_id not in heygen_sse_subscribers:
            heygen_sse_subscribers[video_id] = []
        heygen_sse_subscribers[video_id].append(queue)
        logger.info(f"SSE subscriber connected for video {video_id}")
        
        try:
            # Send initial connection confirmation
            yield f"data: {json.dumps({'event': 'connected', 'video_id': video_id})}\n\n"
            
            # Check current status from database immediately
            video_doc = await db.heygen_videos.find_one({"video_id": video_id})
            if video_doc:
                current_status = video_doc.get("status", "processing")
                current_url = video_doc.get("video_url")
                yield f"data: {json.dumps({'event': 'current_status', 'video_id': video_id, 'status': current_status, 'video_url': current_url})}\n\n"
                
                # If already completed, close stream
                if current_status in ["completed", "failed", "error"]:
                    yield f"data: {json.dumps({'event': 'final', 'video_id': video_id, 'status': current_status, 'video_url': current_url})}\n\n"
                    return
            
            # Wait for updates from webhook
            timeout_seconds = 900  # 15 minutes max
            start_time = datetime.now(timezone.utc)
            last_api_check = start_time
            api_check_interval = 10  # Check API every 10 seconds if no webhook
            
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.info(f"SSE client disconnected for video {video_id}")
                    break
                
                # Check timeout
                elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
                if elapsed > timeout_seconds:
                    yield f"data: {json.dumps({'event': 'timeout', 'video_id': video_id})}\n\n"
                    break
                
                try:
                    # Wait for event with timeout
                    event_data = await asyncio.wait_for(queue.get(), timeout=5.0)
                    yield f"data: {json.dumps(event_data)}\n\n"
                    
                    # If video is done, close the stream
                    if event_data.get("status") in ["completed", "failed", "error"]:
                        break
                        
                except asyncio.TimeoutError:
                    # No webhook received, check API directly as fallback
                    time_since_last_check = (datetime.now(timezone.utc) - last_api_check).total_seconds()
                    
                    if time_since_last_check >= api_check_interval:
                        last_api_check = datetime.now(timezone.utc)
                        
                        # Check status from HeyGen API directly
                        try:
                            async with httpx.AsyncClient() as client:
                                headers = {"X-Api-Key": os.getenv("HEYGEN_API_KEY", "")}
                                resp = await client.get(
                                    f"https://api.heygen.com/v1/video_status.get?video_id={video_id}",
                                    headers=headers,
                                    timeout=10.0
                                )
                                if resp.status_code == 200:
                                    api_data = resp.json().get("data", {})
                                    api_status = api_data.get("status", "processing")
                                    api_video_url = api_data.get("video_url")
                                    
                                    # Update database
                                    if api_status in ["completed", "failed", "error"]:
                                        await db.heygen_videos.update_one(
                                            {"video_id": video_id},
                                            {"$set": {
                                                "status": api_status,
                                                "video_url": api_video_url,
                                                "api_checked_at": now_utc()
                                            }}
                                        )
                                        
                                        yield f"data: {json.dumps({'event': 'status_update', 'video_id': video_id, 'status': api_status, 'video_url': api_video_url})}\n\n"
                                        break
                                    else:
                                        # Send progress update
                                        yield f"data: {json.dumps({'event': 'ping', 'elapsed': int(elapsed), 'status': api_status})}\n\n"
                        except Exception as e:
                            logger.error(f"Error checking HeyGen API: {e}")
                            # Send keepalive ping
                            yield f"data: {json.dumps({'event': 'ping', 'elapsed': int(elapsed)})}\n\n"
                    else:
                        # Just send keepalive
                        yield f"data: {json.dumps({'event': 'ping', 'elapsed': int(elapsed)})}\n\n"
                    
        finally:
            # Unregister subscriber
            if video_id in heygen_sse_subscribers:
                try:
                    heygen_sse_subscribers[video_id].remove(queue)
                    if not heygen_sse_subscribers[video_id]:
                        del heygen_sse_subscribers[video_id]
                except ValueError:
                    pass
            logger.info(f"SSE subscriber disconnected for video {video_id}")
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

# ============================================
# AI Text Generation Endpoint
# ============================================
class AITextGenerateRequest(BaseModel):
    prompt: str
    context: Optional[str] = None
    format: str = "html"  # html, plain, markdown

@api_router.post("/ai/generate-text")
async def generate_text_with_ai(request: AITextGenerateRequest):
    """Generate formatted text content using AI (GPT-4o)"""
    
    emergent_key = os.environ.get('EMERGENT_LLM_KEY')
    if not emergent_key:
        raise HTTPException(status_code=500, detail="AI API key not configured")
    
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        
        # System message for text generation
        system_message = """Você é um assistente especializado em criar conteúdo educacional formatado em HTML.

Regras:
1. SEMPRE responda em português brasileiro
2. Use tags HTML para formatação: <h1>, <h2>, <h3>, <p>, <strong>, <em>, <ul>, <ol>, <li>, <table>, <tr>, <td>, <th>
3. Crie conteúdo bem estruturado com títulos, parágrafos e listas quando apropriado
4. Use tabelas para dados comparativos ou estruturados
5. Seja conciso mas informativo
6. NÃO inclua tags <html>, <head> ou <body> - apenas o conteúdo interno
7. NÃO use markdown, apenas HTML puro

Exemplo de resposta formatada:
<h2>Título do Tópico</h2>
<p>Parágrafo introdutório explicando o conceito.</p>
<h3>Subtópico</h3>
<ul>
  <li><strong>Item 1:</strong> Descrição do item</li>
  <li><strong>Item 2:</strong> Descrição do item</li>
</ul>"""

        # Initialize chat with GPT-4o
        chat = LlmChat(
            api_key=emergent_key,
            session_id=f"text-gen-{uuid.uuid4()}",
            system_message=system_message
        ).with_model("openai", "gpt-4o")
        
        # Build the prompt
        full_prompt = f"Gere conteúdo formatado sobre: {request.prompt}"
        if request.context:
            full_prompt += f"\n\nContexto adicional: {request.context}"
        
        # Send message and get response
        user_message = UserMessage(text=full_prompt)
        response = await chat.send_message(user_message)
        
        logger.info(f"AI text generated successfully for prompt: {request.prompt[:50]}...")
        
        return {
            "success": True,
            "content": response,
            "format": request.format
        }
        
    except ImportError:
        logger.error("emergentintegrations library not installed")
        raise HTTPException(status_code=500, detail="AI integration library not available")
    except Exception as e:
        logger.error(f"AI text generation error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate text: {str(e)}")

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
