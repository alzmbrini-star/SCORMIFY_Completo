"""Runway video API. Credentials stay server-side; never retry paid POSTs."""
import base64
import os
import uuid
from urllib.parse import urlparse

import httpx

BASE_URL = 'https://api.dev.runwayml.com/v1'
MODELS = {'gen4_turbo': 5, 'gen4.5': 12}  # credits/second; indicative, not a quote
RATIOS = {'16:9': '1280:720', '9:16': '720:1280'}


def configured():
    return bool(os.getenv('RUNWAYML_API_SECRET', '').strip())


def build_payload(options):
    model = options.get('model', 'gen4.5')
    duration = options.get('duration', 5)
    ratio = options.get('aspectRatio', '16:9')
    prompt = options.get('prompt', '')
    if model not in MODELS or type(duration) is not int or duration not in (5, 10) or ratio not in RATIOS:
        raise ValueError('Modelo, duração ou formato Runway inválido.')
    if not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 1000:
        raise ValueError('Descreva a cena com 1 a 1000 caracteres.')
    image = options.get('image', '')
    if not isinstance(image, str):
        raise ValueError('Imagem inicial inválida.')
    if model == 'gen4_turbo' and not image:
        raise ValueError('Gen-4 Turbo requer uma imagem inicial.')
    if image:
        if image.startswith('data:'):
            try:
                header, encoded = image.split(',', 1)
                if header not in ('data:image/png;base64', 'data:image/jpeg;base64', 'data:image/webp;base64'):
                    raise ValueError()
                if len(image) > 5 * 1024 * 1024 or not base64.b64decode(encoded, validate=True):
                    raise ValueError()
            except (ValueError, TypeError):
                raise ValueError('Use uma imagem PNG, JPEG ou WebP de até 3 MB.') from None
        else:
            parsed = urlparse(image)
            if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or len(image) > 2048:
                raise ValueError('Use uma URL HTTPS pública para a imagem inicial.')
    payload = {'model': model, 'promptText': prompt.strip(), 'duration': duration, 'ratio': RATIOS[ratio]}
    if image:
        payload['promptImage'] = image
    return ('image_to_video' if image else 'text_to_video'), payload


async def request(method, path, payload=None):
    if not configured():
        raise ValueError('Runway não configurado: cadastre RUNWAYML_API_SECRET no servidor.')
    headers = {'Authorization': 'Bearer ' + os.environ['RUNWAYML_API_SECRET'].strip(),
               'X-Runway-Version': '2024-11-06', 'Content-Type': 'application/json'}
    async with httpx.AsyncClient(timeout=httpx.Timeout(70, connect=15)) as client:
        response = await client.request(method, f'{BASE_URL}/{path}', headers=headers, json=payload)
    if response.status_code >= 400:
        messages = {401: 'Chave Runway inválida.', 402: 'Verifique os créditos da API Runway.',
                    403: 'A conta Runway não permite esta operação.', 429: 'Limite Runway atingido. Aguarde antes de consultar novamente.'}
        raise ValueError(messages.get(response.status_code, f'Runway retornou HTTP {response.status_code}. Confira os parâmetros e os créditos da conta.'))
    return response.json()


async def submit(options):
    path, payload = build_payload(options)
    data = await request('POST', path, payload)
    task_id = str(data.get('id') or '')
    uuid.UUID(task_id)
    return task_id


async def get_task(task_id):
    uuid.UUID(task_id)
    return await request('GET', f'tasks/{task_id}')


async def download(url, destination):
    """Bounded streaming; provider output is copied before its URL expires."""
    if urlparse(url).scheme != 'https':
        raise ValueError('O resultado Runway não contém uma URL HTTPS válida.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(300, connect=20), follow_redirects=True) as client:
            async with client.stream('GET', url) as response:
                response.raise_for_status()
                content_type = response.headers.get('content-type', '').split(';')[0].lower()
                if content_type and not content_type.startswith('video/') and content_type != 'application/octet-stream':
                    raise ValueError('O resultado Runway não é um arquivo de vídeo válido.')
                with destination.open('wb') as handle:
                    async for chunk in response.aiter_bytes(1024 * 1024):
                        total += len(chunk)
                        if total > 180 * 1024 * 1024:
                            raise ValueError('O vídeo Runway excede o limite de 180 MB.')
                        handle.write(chunk)
        if not total:
            raise ValueError('O vídeo Runway está vazio.')
    except Exception:
        destination.unlink(missing_ok=True)
        raise
