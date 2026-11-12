"""Opt-in canonical assessments outside the guided-path course mode."""
import copy
import uuid


def assessment_request(source, count=3, images=True):
    return {'id': 'assessment_' + uuid.uuid4().hex[:16], 'type': 'interactive_assessment',
            'title': 'Avaliação interativa — ' + str(source.get('title') or 'Conteúdo estudado'),
            'purpose': 'Verificar a compreensão com questões contextualizadas e imagens de apoio.',
            'assessmentRequest': {'questionCount': count, 'images': images},
            'sourceExcerpt': source.get('sourceExcerpt') or source.get('purpose') or source.get('notes') or '',
            'sourceRefs': source.get('sourceRefs', []), 'estimatedDuration': 120}


def plan_assessments(structure, config):
    if not (config.get('enabledResources') or {}).get('interactive_assessment'):
        return structure
    for module in structure.get('modules', []):
        slides = module.get('slides', [])
        if any(s.get('assessmentRequest') for s in slides):
            continue
        teaching = [s for s in slides if s.get('type') not in ('title', 'cover', 'summary', 'quiz') and not s.get('sourceImageOnly')]
        if not teaching:
            continue
        source = {'title': module.get('title'), 'sourceExcerpt': '\n\n'.join(
            s.get('sourceExcerpt') or s.get('purpose') or s.get('title', '') for s in teaching),
            'sourceRefs': list(dict.fromkeys(r for s in teaching for r in s.get('sourceRefs', [])))}
        request = assessment_request(source, config.get('assessmentQuestionCount', 3), config.get('assessmentImages', True))
        request['moduleName'] = module.get('title', '')
        end = next((i for i, s in enumerate(slides) if s.get('type') == 'summary'), len(slides))
        slides.insert(end, request)
    structure['totalSlides'] = sum(len(m.get('slides', [])) for m in structure.get('modules', []))
    return structure


def media_options(slide, media):
    """Absent settings retain the author's approved storyboard; no implicit opt-in."""
    base = slide.get('assessmentRequest') or {}
    options = media.get('interactiveAssessment')
    if not isinstance(options, dict):
        options = {'enabled': bool(base), 'questionCount': base.get('questionCount', 3), 'images': base.get('images', True)}
    if type(options.get('enabled')) is not bool or type(options.get('images', True)) is not bool:
        raise ValueError('Escolha se a avaliação e as imagens estão habilitadas.')
    count = options.get('questionCount', 3)
    if type(count) is not int or not 1 <= count <= 10:
        raise ValueError('Escolha de 1 a 10 questões por avaliação interativa.')
    return {**options, 'questionCount': count, 'images': options.get('images', True)}


async def generate_assessment(source, context, ask, options=None):
    from services.guided_path import generate_activity
    options = options or media_options(source, {})
    request = {**source, 'guidedRequest': 'assessment', 'guidedUnitId': 'assessment_unit'}
    path = {'units': [{'id': 'assessment_unit', 'title': source.get('moduleName') or source['title']}],
            'questionsPerUnit': options['questionCount'], 'assessmentImages': options['images']}
    spec = await generate_activity(request, path, context, ask)
    spec['imagesEnabled'] = options['images']
    return spec


def render_assessment(spec, width=1920, height=820):
    from services.assessment_renderer import assessment_element
    element = assessment_element(copy.deepcopy(spec['questions']), spec['title'], False, width, height)
    element['agentAssessment'] = {'imagesEnabled': spec.get('imagesEnabled', True)}
    return element


async def apply_media_assessments(project_slides, storyboard_slides, media, ask):
    """Append after the source lesson; only explicitly selected quizzes are replaced."""
    if len(project_slides)!=len(storyboard_slides):
        raise ValueError('A numeração dos slides mudou antes de preparar as avaliações. Nenhum conteúdo foi descartado.')
    result = []
    for index, (slide, source) in enumerate(zip(project_slides, storyboard_slides)):
        options = media_options(source, media.get(str(index), {}))
        if source.get('guidedActivity'):
            override = media.get(str(index), {}).get('interactiveAssessment')
            if isinstance(override,dict) and source['guidedActivity'].get('questions'):
                for element in slide.get('elements',[]):
                    if element.get('assessmentConfig'):
                        element['agentAssessment']={'imagesEnabled':options['images']}
            result.append(slide)
            continue
        existing = source.get('assessmentActivity')
        if existing or options['enabled']:
            if existing and options['enabled'] and len(existing['questions']) == options['questionCount']:
                spec = copy.deepcopy(existing)
                spec['imagesEnabled'] = options['images']
            elif options['enabled']:
                context = '\n\n'.join([str(source.get(k) or '') for k in ('sourceExcerpt', 'notes', 'purpose')])
                # Include existing questions / authored text, not a topic-only placeholder.
                import json
                context += '\n' + json.dumps({'elements': source.get('elements', []), 'quizQuestions': source.get('quizQuestions', [])}, ensure_ascii=False)
                request = assessment_request(source, options['questionCount'], options['images'])
                request['moduleName'] = source.get('moduleName', '')
                spec = await generate_assessment(request, context, ask, options)
            else:
                continue  # Explicitly omit this planned assessment; source lessons are elsewhere.
            assessment_slide = {**slide, 'id': 'slide_' + uuid.uuid4().hex[:16], 'title': spec['title'],
                                'elements': [render_assessment(spec)], 'quizQuestionIds': [], 'duration': 120,
                                'background':'#f4f8fc','backgroundImage':None,'backgroundOpacity':None,
                                'contentType':'interactive_assessment','sourceImageOnly':False,'sourceImage':None,
                                'audio':[], 'notes':spec['instructions']}
            if not existing and source.get('type') != 'quiz':
                result.append(slide)
            result.append(assessment_slide)
        else:
            result.append(slide)
    for index,slide in enumerate(result):
        slide['order']=index
    return result
