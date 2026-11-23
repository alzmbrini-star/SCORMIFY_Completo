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
