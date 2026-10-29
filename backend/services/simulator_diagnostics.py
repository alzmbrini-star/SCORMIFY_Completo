"""Private, bounded diagnostics and exact-input reuse of reviewed simulations.

No generated document is logged or executed here. The route owns persistence
and authorization; ContextVars isolate concurrent requests and background loops.
"""
from contextlib import contextmanager
from contextvars import ContextVar
import copy
import hashlib
import json

_scope = ContextVar('simulator_diagnostic_scope', default=None)
_record = ContextVar('simulator_diagnostic_record', default=None)
VERSION = 9
MAX_DOCUMENT = 1000000


def simulator_request(source, content, config):
    return (json.dumps(source, ensure_ascii=False), json.dumps({
        'course': {key: config[key] for key in ('title', 'targetAudience', 'audience', 'depth', 'learningObjectives', 'objectives') if key in config},
        'module': source.get('moduleName'), 'objective': source.get('purpose'), 'reference': content[:6000]}, ensure_ascii=False))


def simulator_sources(session):
    slides = []
    for module in (session.get('structure') or {}).get('modules', []):
        for slide in module.get('slides', []):
            slides.append(dict(slide, moduleName=module.get('title', '')))
    return [(index, slide) for index, slide in enumerate(slides) if slide.get('type') == 'simulator']


def generation_key(prompt, context, config):
    payload = json.dumps([VERSION, prompt, context, config], ensure_ascii=True)
    return hashlib.sha256(payload.encode()).hexdigest()


@contextmanager
def diagnostic_scope(sink, cached=()):
    token = _scope.set((sink, {item['generationKey']: item for item in cached
        if item.get('status') == 'accepted' and item.get('version') == VERSION
        and item.get('result') and not item.get('truncated')}))
    try:
        yield
    finally:
        _scope.reset(token)


async def capture_generation(generate, prompt, context, session_id, config):
    scope = _scope.get()
    if scope is None:
        return await generate(prompt, context, session_id)
    key = generation_key(prompt, context, config)
    cached = scope[1].get(key)
    if cached:
        return copy.deepcopy(cached['result'])
    record = {'version': VERSION, 'generationKey': key, 'generatorSessionId': session_id,
              'status': 'running', 'attempts': [], 'error': ''}
    try:
        parsed = json.loads(prompt)
        record['activityTitle'] = str(parsed.get('title', 'Simulador'))[:150] if isinstance(parsed, dict) else 'Simulador'
    except (ValueError, TypeError):
        record['activityTitle'] = 'Simulador'
    token = _record.set(record)
    try:
        _publish()
        result = await generate(prompt, context, session_id)
        record.update(status='accepted', plan=result.get('spec'), result=result)
        if len(json.dumps(result, ensure_ascii=True)) > MAX_DOCUMENT:
            record.pop('result', None)
            record['truncated'] = True
        _publish()
        return result
    except Exception as exc:
        record.update(status='failed', error=str(exc)[:12000])
        _publish()
        raise
    finally:
        _record.reset(token)


def record_attempt(document, spec, issues, error='', review=''):
    record = _record.get()
    if record is None:
        return
    text = str(document)
    record['plan'] = spec
    record['attempts'].append({'document': text[:MAX_DOCUMENT], 'truncated': len(text) > MAX_DOCUMENT,
        'issues': issues, 'error': str(error)[:12000], 'review': str(review)[:24000]})
    record['attempts'] = record['attempts'][-3:]
    _publish()


def _publish():
    scope, record = _scope.get(), _record.get()
    if scope and record:
        # Persistence failures must not masquerade as a successful diagnostic run.
        scope[0](copy.deepcopy(record))
