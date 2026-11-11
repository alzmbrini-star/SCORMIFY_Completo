"""Plan pedagogy once; final contextual questions and mechanics are built later."""
import asyncio
import html
import json
from services.source_coverage import complete_source


async def plan_game(source, content, config, ask):
    prompt = ('Planeje um jogo educativo em português brasileiro usando SOMENTE a referência. '
              'Esta é a fase Storyboard, não gere HTML, CSS, JavaScript nem perguntas finais. '
              'Retorne JSON {"mission":"missão específica", "learningPoints":["3 a 5 pontos '
              'fundamentados na referência"], "narrationScript":"explicação de pelo menos cinco frases"}. '
              'Não invente fatos. O jogo final será montado pelo motor existente com questões '
              'contextualizadas na etapa Gerar Curso.\n' + json.dumps({
                  'course': config.get('title'), 'slide': source,
                  'reference': complete_source(content)}, ensure_ascii=False))
    plan = None
    for attempt in range(2):
        try:
            candidate = await asyncio.wait_for(ask(attempt, prompt), timeout=90)
            if isinstance(candidate, dict) and isinstance(candidate.get('mission'), str) and candidate['mission'].strip() and isinstance(candidate.get('learningPoints'), list) and any(isinstance(x, str) and x.strip() for x in candidate['learningPoints']):
                plan = {'version': 1, 'mission': candidate['mission'][:1200],
                        'learningPoints': [x[:1200] for x in candidate['learningPoints'] if isinstance(x, str) and x.strip()][:5]}
                narration = str(candidate.get('narrationScript') or source.get('purpose') or '')[:5000]
                break
        except Exception:
            continue
    if plan is None:
        # Keep a truthful planning card for author review, not fabricated quiz facts.
        plan = {'version': 1, 'mission': source.get('purpose') or source.get('title') or 'Revisar o conteúdo do módulo.',
                'learningPoints': [], 'needsReview': True}
        narration = plan['mission']
    return {**source, 'type': 'game', 'gamePlan': plan, 'narrationScript': narration,
            'notes': '\n'.join([plan['mission'], *plan['learningPoints']]), 'quizQuestions': []}


def game_plan_preview(slide):
    plan = slide['gamePlan']
    esc = lambda value: html.escape(str(value or ''))
    points = ''.join('<li>' + esc(x) + '</li>' for x in plan.get('learningPoints', []))
    notice = ('<p>Revise e complete o planejamento pedagógico antes de gerar o curso.</p>'
              if plan.get('needsReview') else '')
    return ('<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<style>body{margin:0;padding:24px;background:#102239;color:#eef5ff;font:18px/1.5 system-ui}main{max-width:860px;margin:auto}h1{font-size:28px}li{margin:10px 0}aside{padding:16px;background:#1d4056;border-radius:12px}</style>'
            '<main data-game-plan="1"><small>PLANEJAMENTO DO JOGO · STORYBOARD</small><h1>' + esc(slide.get('title')) + '</h1><p>' + esc(plan.get('mission')) + '</p><ul>' + points + '</ul>' + notice +
            '<aside>Esta é uma prévia do planejamento, não o jogo final. Na etapa Gerar Curso, '
            'o jogo será montado com questões vinculadas ao conteúdo do curso e a mecânica selecionada.</aside></main></html>')
