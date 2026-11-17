"""Deterministic course-wide pacing. Does not generate content or modify a course."""
import copy
import math
import re
import unicodedata

POLICY = 'balanced-resources-v2'


def plain(value):
    return ''.join(c for c in unicodedata.normalize('NFKD',str(value or '').lower()) if not unicodedata.combining(c))


def resource_slide(slide):
    # Imported teaching bases remain teaching slides even with authored overlays.
    if slide.get('gammaSource') or slide.get('backgroundImage') and not slide.get('learningResource'):
        return False
    if slide.get('learningResource'):
        return True
    if slide.get('type') in ('quiz','scenario','simulator','reinforcement','visual_summary','avatar_scene','narration'):
        return True
    return any(e.get('assessmentConfig') or e.get('quizConfig') or e.get('type') in ('quiz','scenario','simulator') for e in slide.get('elements',[]))


def budget(project):
    slides=project.get('course',{}).get('slides',[])
    gamma=any(s.get('gammaSource') for s in slides)
    resources=sum(bool(resource_slide(s) or gamma and not s.get('gammaSource')) for s in slides)
    teaching=len(slides)-resources
    target=math.ceil(teaching/3)
    return {'policy':POLICY,'explanatorySlides':teaching,'existingResourceSlides':resources,
            'recommendedTotal':target,'recommendedAdditions':max(0,target-resources),
            'hardMaximumTotal':teaching,'remainingHardLimit':max(0,teaching-resources),
            'suggestionLimit':target,'applicationLimit':min(target,max(0,teaching-resources))}


def orientation(item,row,slide):
    if row.get('pedagogicalRole') in ('orientation','assessment'):
        return True
    title=plain(slide.get('title'))
    if re.fullmatch(r'(capa|agenda|sumario|boas.vindas|carga horaria|objetivos do curso|apresentacao do curso)',title.strip()):
        return True
    text=plain(item.get('description'))+' '+plain(item.get('suggestion'))
    return bool(re.search(r'quantas horas|carga horaria|distribuicao (de|das) horas|alocacao de horas|tempo (de|do) curso|duracao do curso',text))


def balanced_result(result,project):
    """Select a diverse, spaced subset without re-reading/rebilling slide images."""
    from services.assessment_formats import migrate_analysis
    out=migrate_analysis(result)
    info=budget(project)
    slides=project.get('course',{}).get('slides',[])
    rows={r.get('slideIndex'):r for r in out.get('visualAnalysis',{}).get('slides',[])}
    # Prefer original per-slide candidates so rebalancing is idempotent on cached results.
    candidates=[];seen=set()
    raw=[*out.get('improvements',[]),*(i for r in rows.values() for i in r.get('improvements',[]))]
    for i in raw:
        if not isinstance(i,dict):
            continue
        index=i.get('slideIndex')
        if type(index) is not int or not 0<=index<len(slides) or resource_slide(slides[index]):
            continue
        key=(index,i.get('type'),i.get('description'))
        if key in seen or orientation(i,rows.get(index,{}),slides[index]):
            continue
        seen.add(key);candidates.append(i)
    chosen=[];counts={};used=set()
    # Advice remains visible even when the soft target or hard ceiling is met.
    # Generation/application, not analysis, enforce the remaining allowance.
    limit=info['suggestionLimit']
    while candidates and len(chosen)<limit:
        eligible=[i for i in candidates if i['slideIndex'] not in used]
        if not eligible:break
        # Equalize activity types, then cover distant parts of the course, then priority.
        def rank(i):
            distance=min((abs(i['slideIndex']-x) for x in used),default=len(slides))
            return (-counts.get(i.get('type'),0),distance,{'alta':3,'media':2,'baixa':1}.get(i.get('priority'),0),-i['slideIndex'])
        pick=max(eligible,key=rank)
        chosen.append(pick);used.add(pick['slideIndex']);counts[pick.get('type')]=counts.get(pick.get('type'),0)+1
    out['improvements']=sorted(chosen,key=lambda i:i['slideIndex'])
    # Imported-course complements have one unified allowance, not a second unbounded list.
    out['suggestedNewSlides']=[]
    candidate_count=max(len(seen),out.get('resourceBalance',{}).get('candidateCount',0))
    info.update(selectedSuggestions=len(chosen),candidateCount=candidate_count,omittedCandidates=max(0,candidate_count-len(chosen)))
    out['resourceBalance']=info
    # Preserve the complete paid per-slide evidence/candidates for cache reuse.
    # Only the top-level shortlist is filtered; no authored course data is touched.
    return out


def validate_selection(project,improvements,new_slides=None):
    count=len(improvements or [])+len(new_slides or [])
    info=budget(project)
    if count>info['applicationLimit']:
        raise ValueError(f"Equilíbrio didático: selecione no máximo {info['applicationLimit']} novos complementos neste lote. Há {info['existingResourceSlides']} recursos e o teto total é {info['hardMaximumTotal']}. O curso foi preservado.")
    if any(not isinstance(i,dict) for i in improvements or []):
        raise ValueError('Seleção de recursos inválida.')
    indices=[i.get('slideIndex') for i in improvements or []]
    slides=project.get('course',{}).get('slides',[])
    if any(type(i) is not int or not 0<=i<len(slides) for i in indices):
        raise ValueError('Cada recurso deve apontar para um slide de origem válido.')
    if len(indices)!=len(set(indices)):
        raise ValueError('Escolha no máximo um complemento por slide de origem. O curso foi preservado.')


def validate_additions(project,additions):
    info=budget(project)
    if len(additions)>info['applicationLimit']:
        raise ValueError('A geração excedeu o limite de complementos do curso. Nenhum novo slide foi aplicado; selecione menos recursos.')
    indices=[a['afterIndex'] for a in additions]
    if len(indices)!=len(set(indices)):
        raise ValueError('A geração duplicou complementos no mesmo slide. Nenhum novo slide foi aplicado.')
