"""Unified, authenticated generated-video catalog. Listing never starts paid jobs."""
from fastapi import APIRouter, Depends, HTTPException, Query
from routes.auth import require_auth, has_role
from routes.deps import db

router = APIRouter(tags=['Video Library'])


def project_scope(user):
    if has_role(user, 'super_admin'):
        return {}
    return {'companyId': user['companyId']} if user.get('companyId') else {'id': {'$in': []}}


def normalize(provider, row, project=None):
    identifier = str(row.get('video_id') or row.get('taskId') or row.get('id') or row.get('slideId') or '')
    created = row.get('created_at') or row.get('createdAt') or row.get('submittedAt') or ''
    created = created.isoformat() if hasattr(created, 'isoformat') else str(created)
    url = row.get('libraryVideoUrl') or row.get('video_url') or row.get('videoUrl')
    state = row.get('status', 'processing')
    if state == 'succeeded' and url:
        state = 'completed'
    return {'library_id': provider + ':' + identifier, 'video_id': identifier, 'provider': provider,
            'title': row.get('title') or row.get('prompt', '')[:100] or 'Vídeo ' + provider,
            'status': state, 'video_url': url, 'thumbnail_url': row.get('thumbnail_url'),
            'duration': row.get('durationActual') or row.get('duration'),
            'script': row.get('script') or row.get('prompt'), 'created_at': created,
            'project_id': (project or {}).get('id') or row.get('project_id') or row.get('projectId'),
            'project_title': (project or {}).get('title') or (project or {}).get('name'),
            'narrated': bool(row.get('narration')), 'music': bool(row.get('music')),
            'error': row.get('error'), 'can_delete': provider == 'heygen',
            'can_refresh': provider in ('heygen', 'runway', 'heygem') and state not in ('completed', 'failed')}


async def accessible_projects(user):
    return await db.projects.find(project_scope(user),
        {'id': 1, 'title': 1, 'name': 1, 'runwayPending': 1, 'klingPending': 1}).to_list(None)


@router.get('/videos/library')
async def catalog(provider: str = '', search: str = '', offset: int = Query(0, ge=0),
                  limit: int = Query(100, ge=1, le=100), user=Depends(require_auth)):
    if provider and provider not in ('heygen', 'heygem', 'kling', 'runway'):
        raise HTTPException(400, 'Provedor inválido.')
    projects = await accessible_projects(user)
    by_id = {p['id']: p for p in projects}
    ids = list(by_id)
    rows = {}
    def add(p, row, project=None):
        item = normalize(p, row, project)
        rows[item['library_id']] = item
    for project in projects:
        for job in project.get('runwayPending', []):
            add('runway', job, project)
        for job in project.get('klingPending', []):
            add('kling', job, project)
    # History is independent of current slide placeholders: previous Kling
    # results remain reusable after another generation on the same slide.
    async for row in db.kling_generations.find({'projectId': {'$in': ids}}):
        add('kling', row, by_id.get(row.get('projectId')))
    heygen_query = {} if has_role(user, 'super_admin') else {'project_id': {'$in': ids}}
    async for row in db.heygen_videos.find(heygen_query):
        add('heygen', row, by_id.get(row.get('project_id')))
    owner = str(user.get('user_id') or user.get('id') or '')
    if owner:
        async for row in db.heygem_videos.find({'userId': owner}):
            add('heygem', row)
    needle = search.strip().casefold()[:120]
    matches = [r for r in rows.values() if (not provider or r['provider'] == provider)
               and (not needle or needle in ' '.join(str(r.get(k) or '') for k in ('title', 'script', 'project_title')).casefold())]
    matches.sort(key=lambda r: (r['created_at'], r['library_id']), reverse=True)
    return {'videos': matches[offset:offset+limit], 'total': len(matches),
            'hasMore': offset+limit < len(matches)}


async def authorize_item(provider, video_id, user):
    if provider == 'heygem':
        owner = str(user.get('user_id') or user.get('id') or '')
        row = await db.heygem_videos.find_one({'video_id': video_id, 'userId': owner}) if owner else None
        if row:
            return row
    elif provider == 'heygen':
        row = await db.heygen_videos.find_one({'video_id': video_id})
        if row and has_role(user, 'super_admin'):
            return row
        if row:
            from routes.projects_common import load_authorized_project
            await load_authorized_project(row.get('project_id'), user)
            return row
    elif provider == 'runway':
        project = await db.projects.find_one({**project_scope(user), 'runwayPending.id': video_id}, {'id': 1})
        if project:
            return project
    raise HTTPException(404, 'Vídeo não encontrado.')


@router.post('/videos/library/{provider}/{video_id}/refresh')
async def refresh(provider: str, video_id: str, user=Depends(require_auth)):
    row = await authorize_item(provider, video_id, user)
    if provider == 'heygen':
        from routes.heygen import refresh_heygen_video_status
        return normalize(provider, await refresh_heygen_video_status(video_id))
    if provider == 'heygem':
        from routes.heygem import reconcile
        return normalize(provider, await reconcile(row))
    from routes.runway import project_status
    result = await project_status(row['id'], user)
    return normalize(provider, next(j for j in result['videos'] if j['id'] == video_id), row)


@router.delete('/videos/library/heygen/{video_id}')
async def delete(video_id: str, user=Depends(require_auth)):
    await authorize_item('heygen', video_id, user)
    from routes.runway import can_edit
    can_edit(user)
    await db.heygen_videos.delete_one({'video_id': video_id})
    return {'deleted': True}
