"""Optional, source-grounded Gamma assessments; never regenerate Gamma slides."""
import asyncio
import copy
import uuid
from datetime import datetime, timedelta, timezone

_tasks = set()


def now():
    return datetime.now(timezone.utc).isoformat()


async def ask_questions(attempt, prompt):
    from services.ai_agent import PRIMARY_MODEL, FALLBACK_MODEL, _new_chat, _extract_json, UserMessage
    provider, model = (PRIMARY_MODEL, FALLBACK_MODEL)[attempt]
    chat = _new_chat('gamma_assessment_' + uuid.uuid4().hex, provider=provider, model=model)
    response = await asyncio.wait_for(chat.send_message(UserMessage(text=prompt)), timeout=150)
    return _extract_json(response)


async def prepare_slide(job, project, database, projects_dir):
    from services.agent_assessments import generate_assessment, render_assessment
    from services.guided_path import populate_assessments
    options = job['interactiveAssessment']
    spec = copy.deepcopy(job.get('assessmentSpec'))
    if not spec:
        source = job.get('assessmentSource') or ''
        if not source.strip():
            raise ValueError('Conteúdo de referência indisponível.')
        request = {'id': 'gamma_assessment_' + job['id'], 'title': 'Avaliação final — ' + job['title'],
                   'moduleName': job['title'], 'sourceExcerpt': source,
                   'purpose': 'Verificar a compreensão dos conteúdos fornecidos pelo autor.'}
        spec = await generate_assessment(request, source, ask_questions,
            {'questionCount': options['questionCount'], 'images': options['images']})
        # Cache validated questions before paid artwork. Retries reuse them.
        await database.gamma_generations.update_one({'id': job['id']}, {'$set': {'assessmentSpec': spec}})
    element = render_assessment(spec)
    element['id'] = 'gamma_assessment_' + job['id']
    slide = {'id': element['id'], 'title': spec['title'], 'elements': [element],
             'width': 1920, 'height': 820, 'background': '#f4f8fc', 'duration': 120,
             'notes': spec['instructions'], 'contentType': 'interactive_assessment',
             'gammaAssessment': {'jobId': job['id']}, 'audio': [], 'annotations': []}
    course = {'metadata': {'title': job['title']}, 'slides': [slide]}

    async def progress(done, total):
        await database.gamma_generations.update_one({'id': job['id']}, {'$set': {
            'assessment.progress': done, 'assessment.total': total}})

    result = await populate_assessments(course, project, database, projects_dir, progress)
    return slide, result


async def _run(database, projects_dir, job):
    ident, pid = job['id'], job['projectId']
    try:
        project = await database.projects.find_one({'id': pid, 'gammaJobId': ident})
        if not project:
            raise ValueError('Projeto indisponível.')
        # A worker can stop after the append but before marking the job complete.
        if ((project.get('course') or {}).get('metadata') or {}).get('gammaAssessmentJob') == ident:
            await database.gamma_generations.update_one({'id': ident}, {'$set': {
                'status': 'completed', 'assessment.status': 'ready', 'assessment.error': None,
                'totalSlides': len(project['course'].get('slides', []))}, '$unset': {'assessmentLease': ''}})
            return
        slide, result = await prepare_slide(job, project, database, projects_dir)
        # Append only: preserve author edits, questions, notes and other layers.
        latest = await database.projects.find_one({'id': pid, 'gammaJobId': ident})
        if not latest:
            raise ValueError('Projeto indisponível.')
        slide['order'] = len((latest.get('course') or {}).get('slides', []))
        attached = await database.projects.update_one(
            {'id': pid, 'gammaJobId': ident, 'course.metadata.gammaAssessmentJob': {'$ne': ident}},
            {'$push': {'course.slides': slide}, '$set': {
                'course.metadata.gammaAssessmentJob': ident, 'updatedAt': now()}})
        if not attached.modified_count:
            current = await database.projects.find_one({'id': pid, 'course.metadata.gammaAssessmentJob': ident})
            if not current:
                raise ValueError('Não foi possível anexar a avaliação. Os slides foram preservados.')
        await database.gamma_generations.update_one({'id': ident}, {'$set': {
            'status': 'completed', 'assessment.status': 'ready', 'assessment.error': None,
            'assessment.questionCount': job['interactiveAssessment']['questionCount'],
            'assessment.imagesReady': result['ready'], 'assessment.imagesFailed': result['failed'],
            'assessment.warning': 'Algumas imagens não foram geradas. As questões foram preservadas; revise e gere as imagens no Editor.' if result['failed'] else None,
            'totalSlides': slide['order'] + 1}, '$unset': {'assessmentLease': ''}})
    except Exception:
        await database.gamma_generations.update_one({'id': ident}, {'$set': {
            'status': 'completed', 'assessment.status': 'failed',
            'assessment.error': 'Os slides Gamma foram preservados, mas a avaliação não terminou. Abra o projeto para revisão ou tente somente a avaliação novamente (usa créditos de IA).'},
            '$unset': {'assessmentLease': ''}})


async def start_queued(database, projects_dir, job):
    """A database lease prevents duplicate paid workers across browser polls."""
    if job.get('status') != 'assessment':
        return
    if job.get('assessmentLease'):
        if job['assessmentLease'] < now():
            # An interrupted paid call is uncertain: require an explicit retry.
            await database.gamma_generations.update_one({'id': job['id'], 'assessmentLease': job['assessmentLease']}, {'$set': {
                'status': 'completed', 'assessment.status': 'failed',
                'assessment.error': 'Preparação interrompida. Os slides foram preservados. Revise o projeto antes de tentar somente a avaliação novamente (usa créditos de IA).'}, '$unset': {'assessmentLease': ''}})
        return
    lease = await database.gamma_generations.update_one(
        {'id': job['id'], 'status': 'assessment', 'assessmentLease': {'$exists': False}},
        {'$set': {'assessmentLease': (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(), 'assessment.status': 'processing'}})
    if not lease.modified_count:
        return
    task = asyncio.create_task(_run(database, projects_dir, copy.deepcopy(job)))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
