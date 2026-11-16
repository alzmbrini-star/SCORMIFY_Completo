"""Image jobs only update preview snapshots and media assets, never course slides."""
import asyncio
import copy
from datetime import datetime,timedelta,timezone
from services.assessment_formats import canonical_element,image_counts
from services.improvement_preview import coverage

_tasks=set()

async def run_images(database,projects_dir,project,preview):
    from services.assessment_images import create_support_image
    from services.assessment_renderer import refresh_assessment_documents
    result=copy.deepcopy(preview['aiResult']);lock=asyncio.Lock();slots=asyncio.Semaphore(2)
    questions=[q for s in result.get('newSlides',[]) if s.get('type')=='interactive_assessment'
               for q in (canonical_element(s) or {}).get('assessmentConfig',{}).get('questions',[]) if not (q.get('media') or {}).get('url')]
    scope={'id':preview['id'],'projectId':project['id']}
    async def prepare(q):
        async with slots:
            try:
                media=await create_support_image(q,project,database,projects_dir)
                values={'media':media,'imageGenerationStatus':'ready'}
            except Exception:
                values={'imageGenerationStatus':'failed','imageGenerationError':'A imagem não foi gerada. A pergunta foi preservada; tente somente as imagens pendentes.'}
            async with lock:
                q.update(values)
                refresh_assessment_documents({'course':{'slides':result['newSlides']}})
                info=coverage(result,preview['requestedImprovements'])
                info.update(reusedCount=preview.get('coverage',{}).get('reusedCount',0),generatedCount=preview.get('coverage',{}).get('generatedCount',0))
                await database.improvement_previews.update_one(scope,{'$set':{'aiResult':result,'coverage':info}})
    try:
        await asyncio.gather(*(prepare(q) for q in questions))
        await database.improvement_previews.update_one(scope,{'$set':{'imageStatus':'failed' if image_counts(result)['failed'] else 'ready'},'$unset':{'imageLease':''}})
    except Exception:
        await database.improvement_previews.update_one(scope,{'$set':{'imageStatus':'failed'},'$unset':{'imageLease':''}})

async def start_images(database,projects_dir,project,preview):
    counts=image_counts(preview['aiResult'])
    if not counts['total'] or counts['ready']==counts['total']:return
    lease=await database.improvement_previews.update_one(
        {'id':preview['id'],'projectId':project['id'],'imageLease':{'$exists':False},'imageStatus':{'$ne':'processing'}},
        {'$set':{'imageStatus':'processing','imageLease':(datetime.now(timezone.utc)+timedelta(minutes=30)).isoformat()}})
    if not lease.matched_count:return
    task=asyncio.create_task(run_images(database,projects_dir,copy.deepcopy(project),copy.deepcopy(preview)))
    _tasks.add(task);task.add_done_callback(_tasks.discard)
