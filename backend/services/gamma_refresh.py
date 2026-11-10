"""Explicit Gamma base-image updates. Never replace slides or user interactions."""
import re
import uuid
from urllib.parse import urlparse


def linked_bases(project):
    job_id = project.get('gammaJobId')
    if project.get('source') != 'gamma' or not job_id:
        raise ValueError('Este curso não possui uma importação Gamma vinculada.')
    result = []
    for position, slide in enumerate((project.get('course') or {}).get('slides') or []):
        source = slide.get('gammaSource') or {}
        # Legacy imports had deterministic element IDs; do not guess by position
        # or accept any image simply because its name mentions Gamma.
        for element_position, element in enumerate(slide.get('elements') or []):
            if element.get('type') != 'image': continue
            index = source.get('index')
            valid = source.get('jobId') == job_id and source.get('elementId') == element.get('id') and type(index) is int and 0 <= index < 102
            if not valid:
                match = re.search(r'/assets/(gamma_' + re.escape(job_id) + r'_(\d+)\.webp)$', element.get('src') or '')
                if not match or element.get('id') != str(uuid.uuid5(uuid.NAMESPACE_DNS, match.group(1))): continue
                index = int(match.group(2)) - 1
            if not 0 <= index < 102: continue
            result.append({'slideId': slide['id'], 'elementId': element['id'], 'index': index,
                           'position': position, 'elementPosition': element_position,
                           'title': slide.get('title') or f'Slide {position+1}', 'src': element.get('src'),
                           'width': element.get('width'), 'height': element.get('height')})
            break
    if not result: raise ValueError('Nenhuma imagem-base Gamma identificada com segurança. As outras imagens foram preservadas.')
    return result


def document_id(job):
    ident = job.get('gammaId')
    if not ident:
        url = urlparse(job.get('gammaUrl') or '')
        if url.scheme != 'https' or url.hostname not in ('gamma.app', 'www.gamma.app'):
            raise ValueError('A apresentação Gamma original não está vinculada a este curso.')
        parts = url.path.strip('/').split('/')
        ident = parts[1] if len(parts) == 2 and parts[0] == 'docs' else None
    if not isinstance(ident, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', ident):
        raise ValueError('Identificador Gamma não reconhecido. Nenhuma atualização foi solicitada.')
    return ident


def image_patches(project, job, mappings):
    bases = {row['slideId']: row for row in linked_bases(project)}
    images = {row['index']: row for row in job.get('images', [])}
    if not mappings or len(mappings) > 102: raise ValueError('Selecione de 1 a 102 slides para atualizar.')
    patches, backup, seen = {}, [], set()
    for mapping in mappings:
        sid, index = mapping['slideId'], mapping['sourceIndex']
        if sid in seen or sid not in bases or index not in images:
            raise ValueError('Correspondência de slides inválida. Revise a seleção.')
        seen.add(sid)
        base, image = bases[sid], images[index]
        prefix = f'course.slides.{base["position"]}'
        patches[f'{prefix}.elements.{base["elementPosition"]}.src'] = image['src']
        patches[f'{prefix}.gammaSource'] = {'jobId': project['gammaJobId'], 'index': index, 'elementId': base['elementId']}
        backup.append({'slideId': sid, 'elementId': base['elementId'], 'src': base['src'],
                       'replacement': image['src'], 'gammaSource': (project['course']['slides'][base['position']]).get('gammaSource')})
    return patches, backup
