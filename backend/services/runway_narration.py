"""PT-BR voice-over and bounded MP4 composition. No paid automatic retries."""
import asyncio
import json
import math
import os
import re
import shutil
import subprocess

import httpx


def api_key():
    return os.environ.get('ELEVENLABS_API_KEY', '').strip().strip('\"').strip("'")


def media_tools():
    return (shutil.which(os.environ.get('RUNWAY_FFMPEG_BIN', 'ffmpeg')),
            shutil.which(os.environ.get('RUNWAY_FFPROBE_BIN', 'ffprobe')))


def available():
    return bool(api_key() and all(media_tools()))


def validate(value):
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError('Configuração de narração inválida.')
    if value.get('enabled') is not True:
        return None
    text, voice = value.get('text'), value.get('voiceId')
    if not isinstance(text, str) or not 1 <= len(text.strip()) <= 600:
        raise ValueError('Informe o texto da narração em português do Brasil, com 1 a 600 caracteres.')
    if not isinstance(voice, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}', voice):
        raise ValueError('Selecione uma voz ElevenLabs para a narração.')
    if value.get('language', 'pt-BR') != 'pt-BR':
        raise ValueError('Esta opção de narração usa português do Brasil.')
    return {'enabled': True, 'text': text.strip(), 'voiceId': voice, 'language': 'pt-BR',
            'model': 'eleven_flash_v2_5', 'allowOtherVoices': value.get('allowOtherVoices') is True}


def voice_info(row):
    labels = row.get('labels') or {}
    verified = row.get('verified_languages') or []
    brazilian = any(str(v.get('locale', '')).lower() == 'pt-br'
                    or (str(v.get('language', '')).lower() in ('pt', 'portuguese')
                        and 'brazil' in str(v.get('accent', '')).lower()) for v in verified if isinstance(v, dict))
    accent = str(labels.get('accent') or '')
    brazilian = brazilian or bool(re.search(r'brazil|brasil|pt[-_]br', accent, re.I))
    return {'id': row.get('voice_id'), 'name': str(row.get('name') or 'Voz')[:100],
            'accent': accent[:80], 'brazilian': bool(brazilian),
            'previewUrl': row.get('preview_url') if str(row.get('preview_url', '')).startswith('https://') else None}


async def catalog(search=''):
    if not api_key():
        raise ValueError('Configure ELEVENLABS_API_KEY no servidor para carregar as vozes.')
    async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
        response = await client.get('https://api.elevenlabs.io/v2/voices', headers={'xi-api-key': api_key()},
                                    params={'page_size': 100, 'search': str(search)[:80], 'sort': 'name'})
    if response.status_code != 200:
        raise ValueError('Não foi possível listar as vozes ElevenLabs. Confira a chave e a permissão de leitura de vozes.')
    data = response.json()
    rows = [voice_info(row) for row in data.get('voices', []) if isinstance(row, dict)]
    return {'voices': rows, 'hasMore': bool(data.get('has_more'))}


async def speech(narration):
    if not api_key():
        raise ValueError('Configure ELEVENLABS_API_KEY para gerar a narração.')
    voice = narration['voiceId']
    async with httpx.AsyncClient(timeout=120, follow_redirects=False) as client:
        # Validate the actual voice metadata, not a client-supplied accent label.
        metadata = await client.get('https://api.elevenlabs.io/v1/voices/' + voice, headers={'xi-api-key': api_key()})
        if metadata.status_code in (401, 403):
            raise ValueError('A ElevenLabs recusou o acesso à voz. Confira a chave e as permissões de leitura e síntese.')
        if metadata.status_code != 200:
            raise ValueError('A voz selecionada não está disponível na conta ElevenLabs.')
        if not voice_info(metadata.json())['brazilian'] and not narration['allowOtherVoices']:
            raise ValueError('A voz não está identificada como brasileira. Escolha uma voz PT-BR ou confirme o uso de outra voz multilíngue.')
        response = await client.post('https://api.elevenlabs.io/v1/text-to-speech/' + voice,
            headers={'xi-api-key': api_key(), 'Accept': 'audio/mpeg'}, params={'output_format': 'mp3_44100_128'},
            json={'text': narration['text'], 'model_id': 'eleven_flash_v2_5', 'language_code': 'pt',
                  'voice_settings': {'stability': .5, 'similarity_boost': .75}})
    if response.status_code != 200:
        raise ValueError('ElevenLabs recusou a narração. Confira os créditos, a voz e as permissões da chave. Não foi solicitado vídeo à Runway.')
    if not response.content or len(response.content) > 8 * 1024 * 1024:
        raise ValueError('A narração está vazia ou excede o limite de 8 MB.')
    content_type = getattr(response, 'headers', {}).get('content-type', '').split(';')[0]
    if content_type and not content_type.startswith('audio/'):
        raise ValueError('ElevenLabs não retornou um arquivo de áudio válido. Nenhum vídeo foi solicitado.')
    return response.content


async def run_media(args, timeout=180):
    options = {'capture_output': True, 'timeout': timeout}
    if os.name == 'nt':
        options['creationflags'] = subprocess.CREATE_NO_WINDOW
    try:
        result = await asyncio.to_thread(subprocess.run, args, **options)
    except (subprocess.TimeoutExpired, OSError) as exc:
        raise ValueError('Não foi possível concluir a composição do vídeo no tempo previsto. O áudio e a tarefa foram preservados.') from exc
    if result.returncode:
        raise ValueError('Não foi possível processar os arquivos de áudio/vídeo. A geração original foi preservada.')
    return result.stdout


async def duration(path):
    _, probe = media_tools()
    if not probe:
        raise ValueError('FFprobe não disponível para conferir a duração da mídia.')
    data = await run_media([probe, '-v', 'error', '-show_entries', 'format=duration', '-of', 'json', str(path)], timeout=15)
    try:
        value = float(json.loads(data)['format']['duration'])
    except (ValueError, KeyError, TypeError):
        raise ValueError('Não foi possível medir a duração da mídia.') from None
    if not math.isfinite(value) or not 0 < value <= 90:
        raise ValueError('A mídia deve ter duração de até 90 segundos.')
    return value


def composition_args(binary, source, audio, destination, video_seconds, audio_seconds, music=None, volume=15):
    total = max(video_seconds, audio_seconds + .25)
    if not math.isfinite(total) or not 0 < total <= 90:
        raise ValueError('A narração deve resultar em um vídeo de até 90 segundos.')
    extra = max(0, total-video_seconds)
    args = [binary, '-y', '-v', 'error', '-i', str(source)]
    if audio:
        args += ['-i', str(audio)]
    if music:
        args += ['-stream_loop', '-1', '-i', str(music)]
    args += ['-map', '0:v:0']
    if music:
        mi = 2 if audio else 1
        gain = volume / 100
        fade = max(0, total - min(1, total / 4))
        filters = f'[{mi}:a]volume={gain:.3f},afade=t=in:d=0.4,afade=t=out:st={fade:.6f}:d={total-fade:.6f}[music]'
        if audio:
            # Split narration for sidechain ducking; never lower the voice itself.
            filters += ';[1:a]apad,asplit=2[voice][key];[music][key]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=300[bed];[voice][bed]amix=inputs=2:duration=first:normalize=0[out]'
        else:
            filters += ';[music]anull[out]'
        args += ['-filter_complex', filters, '-filter_complex_threads', '1', '-map', '[out]']
    else:
        args += ['-map', '1:a:0']
    if extra > .01:
        args += ['-vf', f'tpad=stop_mode=clone:stop_duration={extra:.6f}', '-c:v', 'libx264',
                 '-preset', 'veryfast', '-crf', '22', '-pix_fmt', 'yuv420p', '-threads', '1', '-filter_threads', '1']
    else:
        args += ['-c:v', 'copy']
    if not music:
        args += ['-af', 'apad']
    args += ['-c:a', 'aac', '-b:a', '128k', '-t', f'{total:.6f}',
             '-metadata:s:a:0', 'language=por', '-movflags', '+faststart', str(destination)]
    return args, total


async def compose(source, audio, destination, music=None, volume=15):
    binary, _ = media_tools()
    if not binary:
        raise ValueError('FFmpeg não disponível para incorporar a narração ao vídeo.')
    video_seconds, audio_seconds = await duration(source), await duration(audio) if audio else 0
    args, total = composition_args(binary, source, audio, destination, video_seconds, audio_seconds, music, volume)
    # Unique temporary output avoids serving a partially written final MP4.
    temporary = destination.with_name(destination.stem + '_composing.mp4')
    args[-1] = str(temporary)
    try:
        await run_media(args)
        if not temporary.is_file() or not 0 < temporary.stat().st_size <= 180 * 1024 * 1024:
            raise ValueError('O vídeo narrado está vazio ou excede o limite de 180 MB.')
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return total
