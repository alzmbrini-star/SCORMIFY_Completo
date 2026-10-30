"""Private, bounded diagnostics and exact-input reuse of reviewed simulations.

No generated document is logged or executed here. The route owns persistence
and authorization; ContextVars isolate concurrent requests and background loops.
"""
from contextlib import contextmanager
from contextvars import ContextVar
import copy
import hashlib
import json
import re

_scope = ContextVar('simulator_diagnostic_scope', default=None)
_record = ContextVar('simulator_diagnostic_record', default=None)
VERSION = 17
MAX_DOCUMENT = 1000000


@contextmanager
def editor_attempts(record):
    """Collect bounded attempts in the owning Editor job, never in public logs."""
    record.update(attempts=[],error='')
    token=_record.set(record)
    try:
        yield
    except Exception as exc:
        record['error']=str(exc)[:12000]
        raise
    finally:
        _record.reset(token)


def simulator_request(source, content, config):
    from services.simulator_experience import options
    return (json.dumps(source, ensure_ascii=False), json.dumps({
        'course': {key: config[key] for key in ('title', 'targetAudience', 'audience', 'depth', 'learningObjectives', 'objectives') if key in config},
        'module': source.get('moduleName'), 'objective': source.get('purpose'), 'reference': content[:6000],
        'simulatorOptions':{**options(config.get('simulatorComplexity'),config.get('simulatorVisualStyle')),
                            **({'activityType':'visualization'} if config.get('simulatorActivityType')=='visualization' else {})}}, ensure_ascii=False))


def simulator_sources(session):
    slides = []
    for module in (session.get('structure') or {}).get('modules', []):
        for slide in module.get('slides', []):
            slides.append(dict(slide, moduleName=module.get('title', '')))
    return [(index, slide) for index, slide in enumerate(slides) if slide.get('type') == 'simulator']


def generation_key(prompt, context, config, version=VERSION):
    payload = json.dumps([version, prompt, context, config], ensure_ascii=True)
    return hashlib.sha256(payload.encode()).hexdigest()


@contextmanager
def diagnostic_scope(sink, cached=()):
    cached=list(cached)
    token = _scope.set((sink, {item['generationKey']: item for item in cached
        if item.get('status') == 'accepted' and item.get('version') == VERSION
        and item.get('result') and not item.get('truncated')}, cached))
    try:
        yield
    finally:
        _scope.reset(token)


async def capture_generation(generate, prompt, context, session_id, config, enrich=None):
    scope = _scope.get()
    if scope is None:
        return await generate(prompt, context, session_id)
    key = generation_key(prompt, context, config)
    cached = scope[1].get(key)
    if cached and not (enrich is not None and (cached.get('result',{}).get('spec') or {}).get('mechanic')=='finite-rules-v1'
                       and not (cached.get('result',{}).get('spec') or {}).get('visual')):
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
        result = _revalidate_rule_data(scope[2],prompt,context,config)
        if result is None:
            result = await generate(prompt, context, session_id)
        else:
            if enrich is not None:result=await enrich(result,prompt,context,session_id)
            record_attempt(result['html'],result['spec'],[],review='Regras anteriores revalidadas sem gerar outra lógica; solução e teste contra atalhos comprovados novamente. A ilustração ausente é tratada separadamente quando solicitado pelo gerador. HTML anterior não foi executado.')
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


def _revalidate_rule_data(records, prompt, context, config):
    """Recompile only exact-input, owned/TTL-filtered records from known DSL versions.

Routes supply owner-scoped records. This function never runs saved HTML or trusts
an earlier approval: all JSON passes the current proof and quality policy again.
"""
    from services.rule_simulators import ENGINE, validate_rules, render_rules, single_action_shortcuts
    records=sorted((r for r in records if type(r.get('version')) is int),key=lambda r:r['version'],reverse=True)
    for previous in records[:60]:
        version=previous.get('version')
        if type(version) is not int or not 8 <= version <= VERSION:
            continue
        if previous.get('status') not in {'accepted','failed'} or previous.get('truncated'):
            continue
        if previous.get('generationKey') != generation_key(prompt,context,config,version):
            continue
        if (previous.get('plan') or {}).get('mechanic') != ENGINE:
            continue
        candidates=[]
        saved=(previous.get('result') or {}).get('spec')
        if isinstance(saved,dict): candidates.append(saved)
        for attempt in reversed(previous.get('attempts',[])[-3:]):
            document=attempt.get('document')
            if attempt.get('truncated') or not isinstance(document,str) or len(document)>MAX_DOCUMENT:
                continue
            try:
                candidates.append(json.loads(re.sub(r'^```(?:json)?\s*|\s*```$','',document.strip(),flags=re.I)))
            except (ValueError,TypeError,RecursionError):
                continue
        for raw in candidates:
            try:
                try:
                    data=validate_rules(raw)
                except ValueError:
                    if not isinstance(raw,dict) or 'visual' not in raw:raise
                    # A stricter visual compiler must never discard proven rules.
                    # Revalidate those rules from scratch, then request only art.
                    logic=dict(raw);logic.pop('visual');logic.pop('visualNotice',None)
                    data=validate_rules(logic)
                    data['verification']['visualRevalidationRequired']=True
                if single_action_shortcuts(data): continue
                from services.simulator_experience import from_context,normalize_experience,has_options
                selected=from_context(context)
                if has_options(context) and data.get('experience') and any(data['experience'].get(k)!=selected[k] for k in selected):continue
                if has_options(context) and not data.get('experience'):
                    data['experience']=normalize_experience(None,data,selected)
                from services.rule_visuals import illustration_detail_issues
                teaching_required=has_options(context) and selected['complexity']=='advanced'
                if teaching_required and data.get('visual') and not data['visual'].get('teaching'):
                    data.pop('visual');data.pop('visualNotice',None)
                    data['verification']['visualTeachingRevalidationRequired']=True
                if has_options(context) and data.get('visual') and illustration_detail_issues(data['visual'],data):
                    data.pop('visual');data.pop('visualNotice',None)
                    data['verification']['visualDetailRevalidationRequired']=True
                if not data.get('visual'):
                    from services.rule_visuals import validate_visual
                    for attempt in reversed(previous.get('attempts',[])[-3:]):
                        document=attempt.get('document')
                        if attempt.get('truncated') or not isinstance(document,str):continue
                        try:
                            scene=json.loads(re.sub(r'^```(?:json)?\s*|\s*```$','',document.strip(),flags=re.I))
                            visual=validate_visual(scene,data)
                            if teaching_required and not visual.get('teaching'):continue
                            if has_options(context) and illustration_detail_issues(visual,data):continue
                            data['visual']=visual
                            data['verification'].update(visualMode='illustrated',visualRecompiled=True)
                            data.pop('visualNotice',None)
                            break
                        except (ValueError,TypeError,KeyError,RecursionError):continue
                data['verification'].update(noSingleActionShortcut=True,revalidatedFromVersion=version)
                return {'html':render_rules(data),'spec':dict(data,template='custom',mechanic=ENGINE)}
            except (ValueError,TypeError,KeyError,RecursionError):
                continue
    return None


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
