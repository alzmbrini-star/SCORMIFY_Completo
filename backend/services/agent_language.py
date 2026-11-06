"""Conservative cleanup of accidental Spanish intrusions in PT-BR structures.

Not a general translator: identifiers, assets, source documents, technical English
and explicitly quoted expressions are deliberately left alone. No provider calls.
"""
import copy
import re
import unicodedata

_ES_PT = {
    'simulación': 'simulação', 'simulaciones': 'simulações',
    'introducción': 'introdução', 'evaluación': 'avaliação',
    'evaluaciones': 'avaliações', 'gestión': 'gestão',
    'descripción': 'descrição', 'conclusión': 'conclusão',
    'conclusiones': 'conclusões', 'aplicación': 'aplicação',
    'aplicaciones': 'aplicações', 'documentación': 'documentação',
    'planificación': 'planejamento', 'preguntas': 'perguntas',
    'respuestas': 'respostas', 'aprendizaje': 'aprendizagem',
    'seguridad': 'segurança', 'herramientas': 'ferramentas',
    'desafío': 'desafio', 'desafíos': 'desafios',
    'ejercicio': 'exercício', 'ejercicios': 'exercícios',
    'conocimiento': 'conhecimento', 'conocimientos': 'conhecimentos',
    'desarrollo': 'desenvolvimento', 'habilidades': 'habilidades',
    'resumen': 'resumo', 'práctica': 'prática', 'prácticas': 'práticas',
}
_WORDS = re.compile(r'\b(' + '|'.join(map(re.escape, _ES_PT)) + r')\b', re.I)
_PROTECTED = re.compile(r'(`[^`]*`|"[^"\n]*"|“[^”\n]*”|https?://\S+)')


def is_portuguese(config=None):
    language = str((config or {}).get('language') or 'pt-BR').strip().lower()
    return language.startswith(('pt', 'portugu'))


def language_instruction(config=None):
    if not is_portuguese(config):
        return 'IDIOMA DO CONTEÚDO: ' + str(config['language'])[:80] + '. Não misture idiomas nos textos apresentados ao aluno.'
    return ('IDIOMA OBRIGATÓRIO: português brasileiro (pt-BR) em courseTitle, '
            'courseDescription, objetivos, módulos, títulos dos slides e purpose. '
            'Não misture espanhol: use Simulação, Gestão, Introdução, Avaliação e '
            'Conclusão; nunca Simulación, Gestión, Introducción, Evaluación ou '
            'Conclusión. Revise todos os textos antes de responder. Preserve nomes '
            'próprios, siglas, marcas, citações e termos técnicos consagrados, como '
            'Design Thinking. As chaves JSON, IDs e valores de type permanecem no '
            'formato técnico solicitado; apenas os textos visíveis são em pt-BR.')


def pt_br_text(text):
    if not isinstance(text, str):
        return text
    def replace(match):
        original = match.group()
        translated = _ES_PT[original.lower()]
        if original.isupper():
            return translated.upper()
        return translated[:1].upper() + translated[1:] if original[:1].isupper() else translated
    parts = _PROTECTED.split(unicodedata.normalize('NFC', text))
    return ''.join(part if index % 2 else _WORDS.sub(replace, part) for index, part in enumerate(parts))


def normalize_structure_language(structure, config=None):
    result = copy.deepcopy(structure)
    if not isinstance(result, dict) or not is_portuguese(config):
        return result
    def fields(obj, keys):
        if not isinstance(obj, dict):
            return
        for key in keys:
            value = obj.get(key)
            if isinstance(value, list):
                obj[key] = [pt_br_text(v) for v in value]
            elif isinstance(value, str):
                obj[key] = pt_br_text(value)
    fields(result, ('courseTitle', 'courseDescription', 'learningObjectives', 'prerequisites', 'competencies'))
    for module in result.get('modules') or []:
        if not isinstance(module, dict):
            continue
        fields(module, ('title', 'description'))
        for slide in module.get('slides') or []:
            fields(slide, ('title', 'purpose', 'experienceIntent'))
    return result
