"""Shared optional offline engine. No authored-course writes or AI calls."""
from pathlib import Path
from functools import lru_cache

@lru_cache(maxsize=1)
def engine_source():
    for folder in (Path('/app/game_templates'),Path(__file__).resolve().parents[2]/'frontend/src/utils'):
        path=folder/'adaptiveAssessment.js'
        if path.is_file():return path.read_text(encoding='utf-8').replace('export function ','function ',1)
    raise RuntimeError('Motor adaptativo indisponível')

def install_adaptive_engine(document):
    if 'id="scormify-adaptive-engine"' in document:return document
    script='<style>body:has(.quiz-player-container[data-adaptive-active="true"]) .swipe-zone{display:none!important}</style><script id="scormify-adaptive-engine">'+engine_source()+'\nwindow.ScormifyAdaptive=createAdaptiveEngine();</script>'
    return document.replace('</head>',script+'</head>',1) if '</head>' in document else script+document

def difficulty(value):
    return {'easy':1,'facil':1,'fácil':1,'medium':2,'medio':2,'médio':2,'hard':3,'dificil':3,'difícil':3,'1':1,'2':2,'3':3}.get(str(value).lower(),2)
def generation_instructions(enabled):
    return ('AVALIAÇÃO ADAPTATIVA ATIVADA: cada avaliação precisa de pelo menos três questões. '
            'Crie questões realmente fáceis (1), intermediárias (2) e avançadas (3), com pelo menos uma de cada nível. '
            'Inclua difficulty numérica, learningObjective (conceito ensinado) e reinforcement (explicação didática após erro) em cada questão. '
            'A dificuldade deve corresponder à exigência cognitiva real, não apenas ao rótulo; preserve o conteúdo da fonte.' if enabled else '')


def validate_generated_levels(questions, enabled):
    """Only validate new AI output; never relabel saved banks to fabricate variety."""
    if not enabled:
        return
    if len(questions) < 3 or any(type(q.get('difficulty')) is not int for q in questions) or {q.get('difficulty') for q in questions} != {1, 2, 3}:
        raise ValueError('Avaliação adaptativa: gere pelo menos três questões e contemple os níveis 1, 2 e 3.')
    if any(not str(q.get('learningObjective') or '').strip() or not str(q.get('reinforcement') or '').strip() for q in questions):
        raise ValueError('Avaliação adaptativa: cada questão precisa de conceito e reforço didático.')

