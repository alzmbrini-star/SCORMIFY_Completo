"""Explicit recovery of metadata on isolated, controlled full-slide activities.

Never rewrite HTML, answers, media, timing or custom multi-element layouts.
"""
import gzip
import io
import math
import re
import tempfile
import uuid
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from services.streaming_html import write_json

CONTROLLED = re.compile(r'<script\b[^>]*\bid=["\'](?:video-quiz-data|assessment-data)["\']', re.I)


def positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def isolated_activity(slide):
    elements = slide.get('elements') or []
    if len(elements) != 1 or not isinstance(elements[0], dict): return None
    element = elements[0]
    raw = element.get('htmlContent')
    if element.get('type') == 'html' and isinstance(raw, str) and CONTROLLED.search(raw): return element
    return None


def layout_recovery_plan(project):
    course = project.get('course') or {}
    slides = course.get('slides') or []
    reference = next((s for s in slides if positive(s.get('width')) and positive(s.get('height'))), {})
    width = reference.get('width') or (course.get('width') if positive(course.get('width')) else 1920)
    height = reference.get('height') or (course.get('height') if positive(course.get('height')) else 820)
    changes, recovered = {}, []
    for index, slide in enumerate(slides):
        element = isolated_activity(slide)
        if element is None: continue
        tiny_default = element.get('width') == element.get('height') == 100 and not element.get('videoQuizConfig') and not element.get('assessmentConfig')
        missing_box = not positive(element.get('width')) or not positive(element.get('height'))
        missing_ids = not slide.get('id') or not element.get('id')
        if not (tiny_default or missing_box or missing_ids or not positive(slide.get('width')) or not positive(slide.get('height'))): continue
        prefix = f'course.slides.{index}'
        sw = slide.get('width') if positive(slide.get('width')) else width
        sh = slide.get('height') if positive(slide.get('height')) else height
        if not slide.get('id'): changes[prefix+'.id'] = str(uuid.uuid4())
        if not element.get('id'): changes[prefix+'.elements.0.id'] = str(uuid.uuid4())
        if not positive(slide.get('width')): changes[prefix+'.width'] = sw
        if not positive(slide.get('height')): changes[prefix+'.height'] = sh
        if not slide.get('title'): changes[prefix+'.title'] = f'Slide {index+1}'
        if 'order' not in slide: changes[prefix+'.order'] = index
        if missing_box or tiny_default:
            for key, value in dict(x=0,y=0,width=sw,height=sh).items(): changes[prefix+'.elements.0.'+key] = value
        if not element.get('htmlDisplayMode'): changes[prefix+'.elements.0.htmlDisplayMode'] = 'page'
        recovered.append(index+1)
    return changes, recovered


async def backup_layout_source(db, project, user_id, paths):
    """Lossless compressed original in GridFS; no Mongo document-size limit."""
    recovery_id = str(uuid.uuid4())
    bucket = AsyncIOMotorGridFSBucket(db, bucket_name='layout_recovery_backups')
    with tempfile.TemporaryFile(mode='w+b') as source:
        with gzip.GzipFile(fileobj=source, mode='wb') as compressed:
            with io.TextIOWrapper(compressed, encoding='utf-8') as text:
                write_json(text, project)
        source.seek(0)
        await bucket.upload_from_stream(recovery_id+'.json.gz', source, metadata={
            'projectId':project['id'], 'userId':user_id, 'recoveryId':recovery_id,
            'createdAt':datetime.now(timezone.utc), 'paths':list(paths), 'version':1,
        })
    return recovery_id
