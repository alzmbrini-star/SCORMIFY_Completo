"""Source-first planning, without topic templates or silent prefix truncation."""
import copy
import io
import re
import unicodedata

MAX_SOURCE_CHARS = 120000


def complete_source(text):
    text = str(text or '').strip()
    if len(text) > MAX_SOURCE_CHARS:
        raise ValueError('O material excede 120 mil caracteres. Divida-o em partes antes de gerar; nenhum trecho será descartado silenciosamente.')
    return text


def docx_text(raw, image_handler=None):
    from docx import Document
    from docx.text.paragraph import Paragraph
    from docx.table import Table
    doc = Document(io.BytesIO(raw))
    blocks = []
    for child in doc.element.body:
        if child.tag.endswith('}p'):
            p = Paragraph(child, doc)
            text = p.text.strip()
            if text:
                match = re.search(r'(?:Heading|Título)\s+(\d+)', p.style.name or '', re.I)
                blocks.append(('#' * min(6, int(match.group(1))) + ' ' if match else '') + text)
        elif child.tag.endswith('}tbl'):
            for row in Table(child, doc).rows:
                cells = [c.text.strip() for c in row.cells if c.text.strip()]
                if cells: blocks.append(' | '.join(cells))
        if image_handler:
            for blip in child.iter('{http://schemas.openxmlformats.org/drawingml/2006/main}blip'):
                rid = blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
                if rid and rid in doc.part.related_parts:
                    marker = image_handler(doc.part.related_parts[rid])
                    if marker: blocks.append(marker)
    return '\n\n'.join(blocks)


def normalized(text):
    return re.sub(r'\W+', ' ', ''.join(c for c in unicodedata.normalize('NFKD', text.lower()) if not unicodedata.combining(c))).strip()


def source_items(ident, paragraphs):
    chunks = []
    for paragraph in paragraphs:
        words, current = paragraph.split(), []
        for word in words:
            if current and len(' '.join(current)) + len(word) + 1 > 480:
                chunks.append(' '.join(current)); current = []
            current.append(word)
        if current: chunks.append(' '.join(current))
    return [{'id': f'{ident}.I{i+1:03}', 'text': value} for i,value in enumerate(chunks)]


def source_sections(text):
    """Numbered teaching units and a final project are mandatory scope, not headings like 'Contents'."""
    text = complete_source(text)
    sections, current, preamble = [], None, []
    for line in text.splitlines():
        clean = line.strip().lstrip('#').strip()
        title = bool(re.match(r'^(?:unidade|m[oó]dulo|cap[ií]tulo|aula|se[cç][aã]o|unit|module|chapter|lesson)\s+(?:\d+|[IVXLCDM]+)\b.{2,}', clean, re.I))
        final = bool(re.match(r'^(?:projeto integrador|projeto final|trabalho final|avalia[cç][aã]o final|final project|capstone)\b', clean, re.I)) and len(clean) < 150
        if title or final:
            current = {'id': f'SRC{len(sections)+1:03}', 'title': clean, 'items': []}
            sections.append(current)
        elif current and clean:
            picture = re.fullmatch(r'\[IMG:([a-zA-Z0-9_.-]+)\]', clean)
            if picture:
                current.setdefault('images', []).append(picture.group(1)); continue
            if re.match(r'^(?:conte[uú]dos e funcionalidades|carga sugerida|figura\s+\d)', clean, re.I): continue
            current['items'].append({'id': f'{current["id"]}.I{len(current["items"])+1:03}', 'text': clean.lstrip('•- ').strip()})
        elif clean:
            preamble.append(clean)
    if sections and preamble:
        sections.insert(0, {'id': 'SRC000', 'title': 'Contexto e fundamentos do material',
            'items': source_items('SRC000', preamble)})
    if not sections and (len(text) >= 250 or '[IMG:' in text):
        # Articles, reports and unnumbered material have scope too. Preserve
        # every paragraph/table row instead of relying on a numbered syllabus.
        paragraphs = [re.sub(r'\s+', ' ', p).strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
        sections = [{'id': 'SRC001', 'title': 'Conteúdo do material fornecido',
            'items': source_items('SRC001', paragraphs)}]
    for section in sections:
        for item in section['items'][:]:
            picture = re.fullmatch(r'\[IMG:([a-zA-Z0-9_.-]+)\]', item['text'])
            if picture:
                section.setdefault('images', []).append(picture.group(1))
                section['items'].remove(item)
        section['items'] = source_items(section['id'], [i['text'] for i in section['items']])
    return [s for s in sections if s['items'] or s.get('images')]


def source_contract(text):
    sections = source_sections(text)
    if not sections: return ''
    lines = ['ESCOPO OBRIGATÓRIO — cubra todos os itens, inclusive os finais. O número de módulos e a duração não autorizam omissões. '
             'Associe cada item a um slide de ensino, usando sourceRefs. Quiz/jogo não substitui a explicação. '
             'Ementa é roteiro de assuntos: desenvolva explicações, exemplos, procedimentos e cuidados sem inventar regras do produto.']
    for section in sections:
        lines.append(section['id'] + ' ' + section['title'])
        lines.extend(item['id'] + ' ' + item['text'] for item in section['items'])
    return '\n'.join(lines)


def ensure_coverage(structure, text):
    result = copy.deepcopy(structure)
    sections = source_sections(text)
    if not sections: return result
    modules = result.get('modules')
    if not isinstance(modules, list): modules = result['modules'] = []
    all_items = {i['id']: i['text'] for s in sections for i in s['items']}
    assigned = set()
    for module in modules:
        for slide in module.get('slides', []):
            refs = list(dict.fromkeys(r for r in (slide.get('sourceRefs') or []) if isinstance(r, str) and r in all_items))[:2]
            if sum(len(all_items[r]) for r in refs) > 650: refs = refs[:1]
            if slide.get('type') in ('content', 'infographic', 'avatar_scene') and refs:
                slide.update(sourceRefs=refs, sourceRequired=True, sourceExcerpt='\n'.join(all_items[r] for r in refs))
                assigned.update(refs)
    # Missing scope is appended as real teaching work, never as a 'covered' label.
    for section in sections:
        missing = [i for i in section['items'] if i['id'] not in assigned]
        if not missing: continue
        name = normalized(re.sub(r'^(?:unidade|m[oó]dulo|cap[ií]tulo|unit|module|chapter)\s+(?:\d+|[IVXLCDM]+)\s*[:.\-]?\s*', '', section['title'], flags=re.I))
        target = next((m for m in modules if name and name in normalized(m.get('title', ''))), None)
        if target is None:
            target = {'id': 'source_' + section['id'], 'title': section['title'], 'description': 'Desenvolver todos os itens da ementa.', 'slides': []}
            if section['id'] == 'SRC000':
                modules.insert(1 if modules and any(s.get('type') == 'title' for s in modules[0].get('slides', [])) else 0, target)
            else:
                modules.append(target)
        groups, group = [], []
        for item in missing:
            if group and (len(group) >= 2 or sum(len(i['text']) for i in group) + len(item['text']) > 650):
                groups.append(group); group = []
            group.append(item)
        if group: groups.append(group)
        for start, items in enumerate(groups):
            topic = next((i['text'] for i in items if len(i['text']) >= 35), items[0]['text'])
            topic = re.sub(r'^[•\-\s]+', '', topic)
            topic = topic if len(topic) <= 85 else topic[:85].rsplit(' ', 1)[0] + '…'
            target['slides'].append({'id': 'source_' + items[0]['id'].replace('.', '_'), 'title': topic,
                'type': 'content', 'purpose': 'Explicar e exemplificar, sem apenas anunciar o assunto: ' + ' '.join(i['text'] for i in items),
                'sourceRefs': [i['id'] for i in items], 'sourceExcerpt': '\n'.join(i['text'] for i in items),
                'sourceRequired': True, 'estimatedDuration': 120})
    # Original figures are deterministic reference slides, not AI reconstructions.
    for section in sections:
        for filename in section.get('images', []):
            if any(filename == s.get('sourceImage') for m in modules for s in m.get('slides', [])): continue
            target = next((m for m in modules if any(r.startswith(section['id']+'.') for s in m.get('slides', []) for r in s.get('sourceRefs', []))), None)
            if target is None:
                target = {'id':'source_'+section['id'], 'title':section['title'], 'description':'Referências visuais do material.', 'slides':[]}
                modules.append(target)
            anchor = next((i+1 for i,s in enumerate(target['slides']) if any(r.startswith(section['id']+'.') for r in s.get('sourceRefs', []))), 0)
            while anchor < len(target['slides']) and target['slides'][anchor].get('sourceImageOnly'): anchor += 1
            target['slides'].insert(anchor, {'id': 'source_image_' + filename.replace('.', '_'),
                'type': 'content', 'title': 'Referência visual — ' + section['title'],
                'purpose': 'Observar a captura original desta unidade. A imagem não será recriada por IA.',
                'sourceImageOnly': True, 'sourceRequired': True, 'sourceImage': filename, 'estimatedDuration': 60})
    result['sourceCoverage'] = {'version': 1, 'sections': len(sections), 'items': len(all_items),
        'plannedItems': len(all_items), 'status': 'planned', 'note': 'Itens distribuídos para desenvolvimento; planejamento não certifica profundidade ou correção do conteúdo.'}
    # A conclusion originally at the end must not precede appended teaching units.
    conclusions = [s for m in modules for s in m.get('slides', []) if s.get('type') == 'summary']
    if not conclusions and modules:
        conclusions = [{'id': 'source_course_summary', 'type': 'summary', 'title': 'Síntese e próximos passos',
            'purpose': 'Retomar as aprendizagens de todas as unidades e orientar a aplicação prática.', 'estimatedDuration': 120}]
    if conclusions and modules:
        final = conclusions[-1]
        for m in modules:
            m['slides'] = [s for s in m.get('slides', []) if s is not final]
        modules[-1]['slides'].append(final)
    result['totalSlides'] = sum(len(m.get('slides', [])) for m in modules)
    return result


def batch_source(text, slides):
    excerpts = [s.get('sourceExcerpt') for s in slides if s.get('sourceExcerpt')]
    if excerpts: return '\n\n'.join(excerpts)
    sections = source_sections(text)
    labels = ' '.join(str(s.get('moduleName', '')) + ' ' + str(s.get('title', '')) for s in slides)
    matches = [s for s in sections if normalized(re.sub(r'^(?:Unidade|Módulo)\s+\d+\s*', '', s['title'], flags=re.I)) in normalized(labels)]
    if matches: return '\n\n'.join(s['title']+'\n'+'\n'.join(i['text'] for i in s['items']) for s in matches)
    return complete_source(text)
