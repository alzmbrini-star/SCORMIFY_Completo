"""Narration-first avatar lessons. No proportional or guessed pause timestamps.

Automatic timing requires BOTH a uniquely matched spoken cue in subtitles and
a measured quiet interval in the rendered audio. Otherwise keep an author draft.
"""
import asyncio
import copy
import hashlib
import ipaddress
import re
import socket
import subprocess
import tempfile
import unicodedata
from pathlib import Path
from urllib.parse import urlsplit


def _text(value, name, limit):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
        raise ValueError(f'{name}: informe texto completo de até {limit} caracteres.')
    return value.strip()


def validate_lesson(raw, count=2):
    from services.video_quiz import normalize_video_quiz
    if not isinstance(raw, dict) or not isinstance(raw.get('blocks'), list) or len(raw['blocks']) != count:
        raise ValueError(f'O roteiro precisa de {count} blocos com perguntas.')
    narration, rows = [], []
    for i, block in enumerate(raw['blocks']):
        if not isinstance(block, dict):
            raise ValueError('Bloco de roteiro inválido.')
        speech = _text(block.get('narration'), f'Fala {i+1}', 1400)
        cue = _text(block.get('transition'), f'Transição {i+1}', 240)
        if len(words(cue)) < 4 or not re.search(r'[.!?…]["”\']?$', cue):
            raise ValueError('A transição deve ser uma frase completa com ao menos quatro palavras.')
        narration.append(speech + ' ' + cue)
        row = block.get('question')
        if not isinstance(row, dict):
            raise ValueError(f'Falta a pergunta do bloco {i+1}.')
        rows.append(dict(row, at=None, relative=False, maxAttempts=3,
                         pauseCue=cue, timingStatus='pending'))
    narration.append(_text(raw.get('continuation'), 'Retomada e conclusão', 700))
    script = '\n\n'.join(narration)
    if len(script) > 2000:
        raise ValueError('O roteiro completo com as transições deve caber em 2000 caracteres; não será truncado.')
    if len({tuple(words(cp['pauseCue'])) for cp in rows}) != count:
        raise ValueError('Cada transição deve ser única no roteiro.')
    tokens = words(script)
    if any(len(matches(tokens, words(cp['pauseCue']))) != 1 for cp in rows):
        raise ValueError('Cada transição deve aparecer uma única vez na fala.')
    normalized = normalize_video_quiz(dict(src='https://example.org/avatar.mp4',
        checkpoints=rows, timingReviewRequired=True))
    return dict(version=1, narrationScript=script, checkpoints=normalized['checkpoints'])


async def plan_video_lesson(context, count=2):
    """Plan speech, spoken lead-ins and questions together, with bounded repair."""
    from services.ai_agent import _new_chat, _extract_json, UserMessage
    import uuid
    chat = _new_chat('video-lesson-' + uuid.uuid4().hex)
    prompt = ('Planeje uma aula curta com avatar em português brasileiro, usando SOMENTE o conteúdo fornecido. '
        'Planeje a fala e as perguntas JUNTAS. Retorne JSON {"blocks":[{"narration":"explicação falada",'
        '"transition":"frase natural que prepara a pergunta e termina a fala antes da pausa.",'
        '"question":{"question":"...","options":["...","...","...","..."],"correctIndex":0,'
        '"explanation":"feedback instrutivo"}}],"continuation":"retomada após a última resposta e conclusão"}. '
        f'Exatamente {count} blocos; quatro alternativas por pergunta e uma correta. '
        'A pergunta deve avaliar apenas o que já foi explicado até o respectivo bloco. '
        'Cada transição deve ser única no roteiro, com ao menos quatro palavras, encerrada com pontuação. '
        'Exemplo: "Antes de continuarmos, escolha a conduta mais adequada nesta situação." '
        'Não narre alternativas nem revele o gabarito na transição. Retome naturalmente no bloco seguinte. '
        'Toda a fala concatenada, incluindo transições e conclusão, deve caber em 2000 caracteres. '
        'Não invente tempos, percentuais, tags SSML ou instruções entre colchetes. CONTEÚDO:\n' + str(context)[:16000])
    issue = ''
    for _ in range(3):
        response = await chat.send_message(UserMessage(text=prompt if not issue else
            'Corrija o JSON completo mantendo o conteúdo e as perguntas. Problema: ' + issue))
        try:
            return validate_lesson(_extract_json(response), count)
        except (ValueError, TypeError, KeyError) as exc:
            issue = str(exc)[:500]
    raise ValueError('Não foi possível preparar roteiro e perguntas antes da geração de mídia. ' + issue)


async def prepare_video_lessons(slides, media_config, session_id='', db=None):
    """Cache validated plans by immutable inputs; failed course retries reuse them."""
    plans = {}
    for i, slide in enumerate(slides):
        media = media_config.get(str(i), {})
        if slide.get('type', 'content') != 'content' or media.get('type') != 'heygen' or not media.get('videoQuizEnabled'):
            continue
        content = [str(slide.get('title') or ''), str(slide.get('narrationScript') or '')]
        for element in slide.get('elements', []):
            for field in ('content', 'htmlContent'):
                value = str(element.get(field) or '')
                value = re.sub(r'<(script|style)\b[^>]*>[\s\S]*?</\1>', ' ', value, flags=re.I)
                content.append(re.sub(r'<[^>]+>', ' ', value))
        context = re.sub(r'\s+', ' ', ' '.join(content)).strip()[:16000]
        digest = hashlib.sha256(('video-lesson-v1\n' + context).encode()).hexdigest()
        path = 'videoLessonPlans.' + digest
        cached = await db.agent_sessions.find_one({'id': session_id}, {path: 1}) if db is not None and session_id else None
        plan = (cached or {}).get('videoLessonPlans', {}).get(digest)
        if plan:
            # A cached snapshot must still satisfy the current format.
            try:
                if plan.get('version') != 1 or not plan.get('narrationScript') or len(plan['checkpoints']) != 2:
                    plan = None
            except (TypeError, KeyError):
                plan = None
        if not plan:
            try:
                plan = await plan_video_lesson(context)
            except ValueError as exc:
                raise ValueError(f'Vídeo com perguntas — {slide.get("title", f"Slide {i+1}")}: {exc}') from exc
            if db is not None and session_id:
                await db.agent_sessions.update_one({'id': session_id}, {'$set': {path: plan}})
        plans[i] = copy.deepcopy(plan)
    return plans


def words(text):
    return re.findall(r'\w+', ''.join(c for c in unicodedata.normalize('NFKD', str(text).lower()) if not unicodedata.combining(c)))


def matches(tokens, cue):
    return [i for i in range(len(tokens)-len(cue)+1) if tokens[i:i+len(cue)] == cue]


def subtitle_cues(text):
    """Accept SRT/WebVTT timestamps, not arbitrary markup or model timestamps."""
    cues = []
    stamp = r'(?:(\d{1,2}):)?(\d{2}):(\d{2})[,.](\d{3})'
    pattern = re.compile(stamp + r'\s*-->\s*' + stamp + r'[^\n]*\n([\s\S]*?)(?=\n\s*\n|\Z)')
    for m in pattern.finditer(text.replace('\r', '')):
        def seconds(offset):
            h, minute, second, ms = m.groups()[offset:offset+4]
            return int(h or 0)*3600 + int(minute)*60 + int(second) + int(ms)/1000
        start, end = seconds(0), seconds(4)
        if not 0 <= start < end <= 86400 or cues and start < cues[-1]['end']:
            raise ValueError('Legendas sobrepostas ou fora de ordem.')
        cues.append(dict(start=start, end=end, words=words(re.sub(r'<[^>]*>', '', m.group(9)))))
    if not cues:
        raise ValueError('Legendas indisponíveis para sincronização.')
    return cues


def align_questions(checkpoints, subtitles, silences, duration):
    """No estimate: unique full cue, caption boundary and audio silence required."""
    cues = subtitle_cues(subtitles)
    tokens, owners = [], []
    for i, cue in enumerate(cues):
        tokens.extend(cue['words']); owners.extend([i] * len(cue['words']))
    result, previous = [], -1
    for cp in checkpoints:
        cue_words = words(cp.get('pauseCue', ''))
        found = matches(tokens, cue_words) if len(cue_words) >= 4 else []
        if len(found) != 1:
            raise ValueError('A frase de transição não foi localizada de forma única nas legendas.')
        end_token = found[0] + len(cue_words) - 1
        owner = owners[end_token]
        if owner + 1 >= len(cues) or end_token+1 < len(owners) and owners[end_token+1] == owner:
            raise ValueError('A legenda não isola o fim da frase antes da próxima fala.')
        end, next_start = cues[owner]['end'], cues[owner+1]['start']
        # Require a quiet window close to the caption end, contained before the
        # next caption. The 150 ms guards avoid a pause on a syllable boundary.
        candidates = []
        for left, right in silences:
            a, b = max(left + .15, end - .1), min(right - .15, next_start - .15, duration - .2)
            if b >= a and a <= end + 1 and right-left >= .4:
                candidates.append((a+b)/2)
        if not candidates:
            raise ValueError('Não há uma pausa de áudio confirmada após a transição; revise no Editor.')
        at = round(min(candidates, key=lambda t: abs(t-end)), 3)
        if at <= previous:
            raise ValueError('As transições não seguem a ordem das perguntas.')
        previous = at
        result.append(dict(cp, at=at, relative=False, timingStatus='audio-aligned'))
    return result


async def _provider_file(url, destination=None, limit=2_000_000):
    """Only public HTTPS assets returned by HeyGen; no redirects/private hosts."""
    import httpx
    parsed = urlsplit(url or '')
    host = (parsed.hostname or '').lower()
    if (parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port not in (None, 443)
        or not any(host == domain or host.endswith('.'+domain) for domain in ('heygen.ai', 'heygen.com', 'amazonaws.com', 'cloudfront.net'))):
        raise ValueError('Arquivo de sincronização fora dos servidores permitidos.')
    addresses = await asyncio.to_thread(socket.getaddrinfo, host, 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        raise ValueError('Endereço de mídia não público.')
    total, chunks = 0, []
    async with httpx.AsyncClient(timeout=45, follow_redirects=False) as client:
        async with client.stream('GET', url) as response:
            response.raise_for_status()
            with destination.open('wb') if destination else _NullWriter() as output:
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > limit:
                        raise ValueError('Mídia excede o limite para sincronização automática.')
                    if destination: output.write(chunk)
                    else: chunks.append(chunk)
    return b''.join(chunks).decode('utf-8-sig') if not destination else None


class _NullWriter:
    def __enter__(self): return self
    def __exit__(self, *args): pass


def measure_silences(path, duration):
    import imageio_ffmpeg
    completed = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-nostdin', '-hide_banner',
        '-protocol_whitelist', 'file,pipe', '-i', str(path), '-vn', '-af', 'silencedetect=noise=-38dB:d=0.4', '-f', 'null', '-'],
        capture_output=True, text=True, timeout=90, encoding='utf-8', errors='replace')
    if completed.returncode:
        raise ValueError('Não foi possível medir as pausas do áudio.')
    result, left = [], None
    for kind, value in re.findall(r'silence_(start|end):\s*([\d.]+)', completed.stderr):
        if kind == 'start': left = float(value)
        elif left is not None: result.append((left, float(value))); left = None
    if left is not None: result.append((left, duration))
    return result


async def fetch_timing_metadata(video_id, metadata, base_url, headers):
    """Read-only v3 details supplement legacy status responses when available.

    No new video/voice/subtitle generation, and no change of transparent source.
    Older video IDs/accounts may not expose sidecars: retain review fallback.
    """
    import httpx
    result = dict(metadata)
    if result.get('subtitle_url') and result.get('duration'):
        return result
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,150}', str(video_id)):
        return result
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
            response = await client.get(f'{base_url}/v3/videos/{video_id}', headers=headers)
            if response.status_code == 200:
                detail = response.json().get('data')
                if isinstance(detail, dict):
                    for key in ('subtitle_url', 'duration'):
                        if detail.get(key): result[key] = detail[key]
    except Exception:
        pass  # Missing metadata is not a failed video; the author can review it.
    return result


async def resolve_lesson_timing(pending, video_url, metadata):
    """Return an editable, non-assessable draft when evidence is unavailable."""
    config = copy.deepcopy(pending)
    if not pending.get('timingReviewRequired'):
        return config  # Legacy/manual snapshots remain unchanged.
    try:
        duration = float(metadata.get('duration') or 0)
        if not 0 < duration <= 600:
            raise ValueError('Duração indisponível ou acima de dez minutos para sincronização automática.')
        subtitles = await _provider_file(metadata.get('subtitle_url'))
        with tempfile.TemporaryDirectory(prefix='scormify-timing-') as directory:
            local = Path(directory) / 'avatar.video'
            await _provider_file(video_url, local, limit=200_000_000)
            silences = await asyncio.to_thread(measure_silences, local, duration)
        config['checkpoints'] = align_questions(config['checkpoints'], subtitles, silences, duration)
        config.pop('timingReviewRequired', None)
        config.pop('timingReviewMessage', None)
    except Exception:
        # Never discard narration/questions or fabricate pause times. Do not log
        # signed asset URLs/provider exceptions into an author-visible message.
        config['timingReviewRequired'] = True
        config['timingReviewMessage'] = ('Não foi possível comprovar as pausas automaticamente. No Editor, abra '
            'Perguntas durante o vídeo, escute cada frase de transição e confirme os tempos antes de aplicar.')
    return config
