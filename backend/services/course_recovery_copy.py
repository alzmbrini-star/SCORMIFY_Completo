"""Restore an exported course into a new project; never patch the source."""
import base64
import copy
import hashlib
import json
import math
import uuid


def recovered_project(original, reference, user_id, now, request_id):
    if not isinstance(reference,dict) or not isinstance(reference.get('slides'),list):
        raise ValueError('O HTML anterior não contém um curso válido.')
    if not 1 <= len(reference['slides']) <= 500:
        raise ValueError('A referência precisa conter entre 1 e 500 slides.')
    encoded=json.dumps(reference,ensure_ascii=False,allow_nan=False)
    if len(encoded.encode('utf-8'))>14*1024*1024:
        raise ValueError('A cópia excede 14 MB de dados. Não foi criado um projeto parcial.')
    try: uuid.UUID(request_id)
    except (ValueError,TypeError,AttributeError):raise ValueError('Identificação da recuperação inválida.')
    fingerprint=hashlib.sha256(encoded.encode('utf-8')).hexdigest()
    new_id=str(uuid.uuid5(uuid.NAMESPACE_URL,f'{user_id}:{original["id"]}:{request_id}'))
    course=copy.deepcopy(reference)
    slide_ids=set()
    for number,slide in enumerate(course['slides'],1):
        if not isinstance(slide,dict):raise ValueError(f'Slide {number} inválido.')
        for key in ('width','height'):
            value=slide.get(key)
            if type(value) not in (int,float) or not math.isfinite(value) or not 0<value<=20000:
                raise ValueError(f'Slide {number}: referência sem dimensões válidas.')
        if not slide.get('id'):slide['id']=str(uuid.uuid4())
        if slide['id'] in slide_ids:raise ValueError('A referência repete identificadores de slides.')
        slide_ids.add(slide['id'])
        elements=slide.get('elements')
        if not isinstance(elements,list) or len(elements)>300:raise ValueError(f'Slide {number}: elementos inválidos.')
        element_ids=set()
        for element in elements:
            if not isinstance(element,dict):raise ValueError(f'Slide {number}: elemento inválido.')
            for key in ('x','y','width','height'):
                value=element.get(key)
                if type(value) not in (int,float) or not math.isfinite(value) or abs(value)>20000 or key in ('width','height') and value<=0:
                    raise ValueError(f'Slide {number}: referência com enquadramento incompleto.')
            if not element.get('id'):element['id']=str(uuid.uuid4())
            if element['id'] in element_ids:raise ValueError(f'Slide {number}: identificador de elemento repetido.')
            element_ids.add(element['id'])
            html=element.get('htmlContent')
            if isinstance(html,str):
                for _ in range(4):
                    if not html.startswith('__B64__:'):break
                    try:html=base64.b64decode(html[8:],validate=True).decode('utf-8')
                    except (ValueError,UnicodeError):raise ValueError(f'Slide {number}: HTML codificado inválido.')
                element['htmlContent']=html
    # Preserve internal slide/element IDs: HTML/configuration can refer to them.
    # Isolation is the NEW project ID, not rewriting arbitrary authored scripts.
    course['id']=new_id
    course['createdAt']=course['updatedAt']=now
    for key in ('_loader','_playerTheme'):course.pop(key,None)
    return {
        'id':new_id,'name':str(original.get('name') or 'Curso')[:180]+' (Recuperado)',
        'description':'Cópia recuperada de uma exportação HTML anterior. O projeto original não foi alterado.',
        'course':course,'status':'draft','source':'html_recovery',
        'userId':user_id,'companyId':original.get('companyId'),
        'createdAt':now,'updatedAt':now,
        'enableVlibras':original.get('enableVlibras',True),'singlePageMode':original.get('singlePageMode',False),
        'recoverySource':{'projectId':original['id'],'sha256':fingerprint,'requestId':request_id},
    }
