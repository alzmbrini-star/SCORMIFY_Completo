"""Recorded avatar questions, formative by default and optionally graded."""
import hashlib
import json
import math
from pathlib import Path
from urllib.parse import urlsplit


def normalize_video_quiz(raw):
    if not isinstance(raw, dict):
        raise ValueError('Configuração de vídeo inválida.')
    from services.video_quiz_sources import video_quiz_source
    source, provider = video_quiz_source(raw.get('src'))
    checkpoints = raw.get('checkpoints')
    if not isinstance(checkpoints, list) or not 1 <= len(checkpoints) <= 12:
        raise ValueError('Adicione de 1 a 12 perguntas ao vídeo.')
    clean = []
    review_required = raw.get('timingReviewRequired') is True
    for i, cp in enumerate(checkpoints):
        if not isinstance(cp, dict):
            raise ValueError('Pergunta inválida.')
        question = str(cp.get('question') or '').strip()
        explanation = str(cp.get('explanation') or '').strip()
        options = cp.get('options')
        correct = cp.get('correctIndex')
        at = cp.get('at', 0)
        attempts = cp.get('maxAttempts', 3)
        if not question or len(question) > 1500 or not explanation or len(explanation) > 3000:
            raise ValueError(f'Pergunta {i+1}: informe enunciado e explicação final.')
        if not isinstance(options, list) or not 2 <= len(options) <= 6 or any(not isinstance(s, str) or not s.strip() or len(s) > 600 for s in options):
            raise ValueError(f'Pergunta {i+1}: informe de 2 a 6 alternativas completas.')
        if type(correct) is not int or not 0 <= correct < len(options):
            raise ValueError(f'Pergunta {i+1}: selecione uma resposta correta.')
        unresolved = review_required and at is None and bool(cp.get('pauseCue'))
        if not unresolved and (type(at) not in (int, float) or not math.isfinite(at) or at < 0 or at > 86400):
            raise ValueError(f'Pergunta {i+1}: tempo inválido.')
        relative = cp.get('relative') is True
        if unresolved and relative:
            raise ValueError('Uma pausa ainda não confirmada não pode ser proporcional.')
        if relative and not 0 < at < 1:
            raise ValueError('A posição proporcional deve estar entre 0 e 1.')
        if type(attempts) is not int or not 1 <= attempts <= 10:
            raise ValueError('O limite deve ser de 1 a 10 tentativas.')
        row = dict(id=f'q{i+1}', at=at, relative=relative, question=question,
                          explanation=explanation, options=[s.strip() for s in options],
                          correctIndex=correct, maxAttempts=attempts)
        if cp.get('pauseCue'):
            row['pauseCue'] = str(cp['pauseCue'])[:240]
            row['timingStatus'] = str(cp.get('timingStatus') or 'pending')[:40]
        clean.append(row)
    if len({cp['relative'] for cp in clean}) > 1:
        raise ValueError('Use segundos ou posições proporcionais, sem misturar os dois.')
    if not review_required:
        clean.sort(key=lambda c: c['at'])
    known_times = [cp['at'] for cp in clean if cp['at'] is not None]
    if len(set(known_times)) != len(known_times):
        raise ValueError('Cada pergunta precisa de um momento diferente.')
    result = dict(version=1, src=source, title=str(raw.get('title') or 'Vídeo com perguntas')[:200], checkpoints=clean,
                  instanceId=str(raw.get('instanceId') or '')[:100])
    if provider != 'direct':
        result['provider'] = provider
    if review_required:
        result['timingReviewRequired'] = True
        result['timingReviewMessage'] = str(raw.get('timingReviewMessage') or 'Confira os tempos de pausa no Editor antes de liberar esta atividade.')[:600]
    if raw.get('narrationScript'):
        result['narrationScript'] = str(raw['narrationScript'])[:2000]
    if raw.get('graded') is True:
        result['graded'] = True  # Different grading modes never share learner state.
    result['key'] = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()[:20]
    result['graded'] = raw.get('graded') is True
    # Visual preferences must not invalidate the learner's saved answers.
    result['preserveTransparency'] = raw.get('preserveTransparency') is not False
    return result


def build_video_quiz(raw):
    config = normalize_video_quiz(raw)
    snapshot = json.dumps(config, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    runtime = (Path(__file__).parent / 'export_assets' / 'video-quiz.js').read_text(encoding='utf-8')
    document = '''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>
*{box-sizing:border-box}html,body{margin:0;width:100%;height:100%;background:#0d1728;color:#f3f7ff;font:16px/1.45 system-ui,Arial}body{display:flex;flex-direction:column;padding:12px;gap:10px}header{display:flex;align-items:center;gap:10px}h1{font-size:clamp(18px,2.3vw,28px);margin:0;flex:1}main{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(270px,1fr);gap:14px;flex:1;min-height:0}.avatar{display:flex;flex-direction:column;min-height:0;min-width:0;background:#142a43;border:1px solid #466986;border-radius:14px;padding:10px}video{width:100%;min-height:0;flex:1;object-fit:contain;background:#080f1c;border-radius:9px}.controls{display:flex;align-items:center;gap:10px;padding-top:8px;flex-wrap:wrap}button{font:inherit;color:#fff;background:#22587c;border:1px solid #79aec5;border-radius:8px;padding:9px 14px;cursor:pointer}button:disabled{opacity:.5;cursor:not-allowed}button:focus-visible,input:focus-visible{outline:3px solid #ffd56a;outline-offset:3px}#feedback{white-space:pre-wrap;margin:8px 0 0;padding:10px;border-left:3px solid #62dfcf;background:#17394b;max-height:30%;overflow:auto}#panel{overflow:auto;padding:16px;border:1px solid #597795;background:#172d45;border-radius:14px}h2{font-size:20px;margin:0 0 12px}.option{display:flex;gap:10px;align-items:start;padding:12px;border:1px solid #6984a3;border-radius:9px;margin:9px 0;cursor:pointer}.option input{margin-top:5px;flex-shrink:0}#message{color:#ffe39b;white-space:pre-wrap}#continue{background:#096b5d}small{color:#c8dcee}#seek{flex:1;min-width:80px}footer{font-size:12px;color:#c8dcee}body.high{background:#000;color:#fff}body.high #panel,body.high .avatar{background:#000;border-color:#fff}body.high #feedback{background:#141414}body.large{font-size:20px}@media(max-width:650px){main{grid-template-columns:1fr;grid-template-rows:minmax(120px,1fr) minmax(130px,1fr)}body{padding:8px}h1{font-size:18px}#panel{padding:10px}}[hidden]{display:none!important}
</style></head><body><header><h1 id="title"></h1><button id="font" aria-label="Aumentar fonte" aria-pressed="false">A+</button><button id="contrast" aria-pressed="false">Contraste</button></header><main><section class="avatar" aria-label="Vídeo do personagem"><video id="video" playsinline preload="metadata" disablepictureinpicture></video><div class="controls"><button id="play">Reproduzir</button><input id="seek" aria-label="Posição do vídeo" type="range" min="0" max="0" step="0.1" value="0"><span id="clock">0:00</span></div><p id="feedback" role="status" aria-live="polite" hidden></p></section><section id="panel" aria-label="Pergunta de aprendizagem"><h2 id="question" tabindex="-1">Assista ao vídeo</h2><p id="progress"></p><fieldset id="options" style="border:0;padding:0;margin:0" hidden><legend>Selecione uma alternativa</legend></fieldset><p id="message" role="status" aria-live="polite"></p><button id="answer" hidden>Confirmar resposta</button><button id="continue" hidden>Continuar vídeo</button></section></main><footer>Atividade formativa: acertar ou continuar com explicação não altera automaticamente a aprovação do curso.</footer><script id="video-quiz-data" type="application/json">__DATA__</script><script>__RUNTIME__</script></body></html>'''
    from services.video_quiz_playback import upgrade_video_quiz_playback
    return config, upgrade_video_quiz_playback(document.replace('__DATA__', snapshot).replace('__RUNTIME__', runtime))


async def plan_video_questions(context, count=2, max_attempts=3):
    """Generate data only; timestamps proportional until video duration is known."""
    from services.ai_agent import _new_chat, _extract_json, UserMessage
    import uuid
    chat = _new_chat('video-quiz-' + uuid.uuid4().hex)
    prompt = ('Crie perguntas formativas SOMENTE sobre fatos explicados no roteiro abaixo. '
              'Não use banco genérico. Retorne JSON {"checkpoints":[{"question":"...",'
              '"options":["...","...","...","..."],"correctIndex":0,"explanation":"..."}]}. '
              f'Exatamente {count} perguntas, quatro alternativas, uma correta, feedback instrutivo. '
              'Distribua na ordem dos assuntos do roteiro. Português brasileiro. ROTEIRO:\n' + str(context)[:16000])
    parsed = _extract_json(await chat.send_message(UserMessage(text=prompt))) or {}
    rows = parsed.get('checkpoints', []) if isinstance(parsed, dict) else []
    if len(rows) != count:
        raise ValueError('Não foi possível gerar as perguntas. Tente novamente ou crie manualmente.')
    rows = [dict(row, at=(i+1)/(count+1), relative=True, maxAttempts=max_attempts) for i, row in enumerate(rows)]
    return normalize_video_quiz(dict(src='https://example.org/video.mp4', checkpoints=rows))['checkpoints']
