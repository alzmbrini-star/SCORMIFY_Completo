"""Explicit recovery of metadata on isolated, controlled full-slide activities.

Never rewrite HTML, answers, media, timing or custom multi-element layouts.
"""
import gzip
import io
import math
import re
import tempfile
import uuid
import hashlib
import json
import base64
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


def content_identity(element):
    """Only content identifies a missing-ID element; never its index alone."""
    kind = element.get('type')
    keys = {'html': ('htmlContent',), 'image': ('src',), 'video': ('src','embedUrl'),
            'flipbook': ('flipbookUrl',), 'scenario': ('scenarioData',),
            'quiz': ('quizConfig',), 'text': ('content',)}.get(kind, ())
    payload = {k: element[k] for k in keys if element.get(k)}
    # Standalone exports encode HTML, sometimes more than once in legacy files.
    # Decode losslessly only. Never strip scripts, tags or meaningful whitespace
    # to make a changed activity look identical to an earlier version.
    if kind == 'html' and isinstance(payload.get('htmlContent'),str):
        value = payload['htmlContent']
        for _ in range(4):
            if not value.startswith('__B64__:'): break
            try: value = base64.b64decode(value[8:],validate=True).decode('utf-8')
            except (ValueError,UnicodeError): return None
        payload['htmlContent'] = value
    if not payload: return None
    encoded = json.dumps([kind, payload], sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(encoded.encode('utf-8')).hexdigest()


def layout_metadata_regression(existing, incoming):
    """Do not let an old, partial Editor tab undo a successful recovery."""
    prior = (existing.get('course') or {}).get('slides') or []
    current = incoming.get('slides') or []
    for i, slide in enumerate(current):
        old = next((s for s in prior if slide.get('id') and s.get('id') == slide['id']), prior[i] if i < len(prior) else None)
        if not old: continue
        elements, originals = slide.get('elements') or [], old.get('elements') or []
        for j, e in enumerate(elements):
            o = next((v for v in originals if e.get('id') and v.get('id') == e['id']), originals[j] if j < len(originals) else None)
            if not o or not content_identity(e) or content_identity(e) != content_identity(o): continue
            if o.get('id') and not e.get('id'): return True
            if old.get('id') and not slide.get('id'): return True
            if any(positive(o.get(k)) and not positive(e.get(k)) or positive(old.get(k)) and not positive(slide.get(k)) for k in ('width','height')): return True
    return False


def reference_layout_plan(project, reference):
    """Recover metadata from an earlier export, never replace its content.

    Same slide/element structure AND exact content identity are required. Changed
    or ambiguous slides are skipped wholesale, including custom multi-element
    layouts. Healthy geometry and existing identifiers are left alone.
    """
    current = (project.get('course') or {}).get('slides') or []
    prior = reference.get('slides') if isinstance(reference, dict) else None
    if not isinstance(prior, list) or len(prior) != len(current):
        raise ValueError('A referência precisa conter a mesma quantidade de slides do curso atual.')
    changes, recovered, skipped = {}, [], []
    used_ids = {str(s.get('id')) for s in current if s.get('id')}
    used_ids.update(str(e.get('id')) for s in current for e in s.get('elements',[]) if e.get('id'))
    def recover_id(value):
        value = value if isinstance(value,str) and value.strip() and value not in used_ids else str(uuid.uuid4())
        used_ids.add(value)
        return value
    for i, (slide, old) in enumerate(zip(current, prior)):
        if not isinstance(slide,dict) or not isinstance(old,dict):
            skipped.append(i+1); continue
        elements, originals = slide.get('elements') or [], old.get('elements') or []
        if not elements or len(elements) != len(originals) or any(
                not isinstance(e,dict) or not isinstance(o,dict) or not content_identity(e) or content_identity(e) != content_identity(o)
                for e, o in zip(elements, originals)):
            skipped.append(i + 1); continue
        if not positive(old.get('width')) or not positive(old.get('height')):
            skipped.append(i + 1); continue
        prefix = f'course.slides.{i}'
        local = {}
        for k in ('id','title','order','duration'):
            if (slide.get(k) is None or k == 'id' and not slide.get(k)) and old.get(k) is not None:
                local[prefix+'.'+k] = recover_id(old[k]) if k == 'id' else old[k]
        for k in ('width','height'):
            if not positive(slide.get(k)): local[prefix+'.'+k] = old[k]
        for j, (e, o) in enumerate(zip(elements, originals)):
            ep = prefix+f'.elements.{j}.'
            if not e.get('id'): local[ep+'id'] = recover_id(o.get('id'))
            broken = not positive(e.get('width')) or not positive(e.get('height'))
            if broken:
                if not all(positive(o.get(k)) for k in ('width','height')) or not all(
                        type(o.get(k)) in (int,float) and math.isfinite(o[k]) for k in ('x','y')):
                    local = {}; break
                local.update({ep+k:o[k] for k in ('x','y','width','height')})
            for k in ('zIndex','htmlDisplayMode','objectFit','startTime','endTime'):
                if k not in e and k in o: local[ep+k] = o[k]
        if local: changes.update(local); recovered.append(i+1)
    return changes, recovered, skipped


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
