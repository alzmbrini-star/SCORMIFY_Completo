"""HeyGen V3 transport with the stable SCORMIFY response contract.

No database writes: existing course/video IDs and URLs are never migrated.
Catalogs use look IDs (not group IDs) so selections remain usable for videos.
"""
import copy
import uuid
import time
from urllib.parse import parse_qs, quote, urlsplit
import httpx

_voice_cache = {}


def _response(original, body):
    return httpx.Response(200, json=body, request=httpx.Request('GET', 'https://api.heygen.com'))


async def _catalog(client, base, path, headers, kind, **kwargs):
    rows, seen = [], set()
    variants = ('private', 'public') if kind == 'voices' else (None,)
    for variant in variants:
        params = {'limit': 100 if kind == 'voices' else 50}
        if variant:
            params['type'] = variant
        tokens = set()
        for _ in range(100):
            response = await client.get(base + path, headers=headers, params=params, **kwargs)
            if response.status_code != 200:
                return response  # Never replace a good cache with a partial/failed catalog.
            body = response.json()
            data = body.get('data')
            if not isinstance(data, list):
                raise ValueError('HeyGen V3 returned an invalid catalog')
            for item in data:
                row = copy.deepcopy(item)
                row['gender'] = row.get('gender') or ''
                identifier = row.get('voice_id') if kind == 'voices' else row.get('id')
                if not identifier or identifier in seen:
                    continue
                seen.add(identifier)
                if kind == 'voices':
                    row['language'] = row.get('language') or ''
                    row['name'] = row.get('name') or identifier
                    row['preview_audio'] = row.get('preview_audio_url') or row.get('preview_audio')
                    row['language_code'] = row.get('language') if '-' in (row.get('language') or '') else ''
                else:
                    row['avatar_id'] = identifier
                    row['avatar_name'] = row.get('name') or identifier
                rows.append(row)
            if not body.get('has_more'):
                break
            token = body.get('next_token')
            if not token or token in tokens:
                raise ValueError('HeyGen V3 returned an invalid pagination cursor')
            tokens.add(token)
            params['token'] = token
        else:
            raise ValueError('HeyGen catalog exceeded pagination safety limit')
    return _response(response, {'data': {kind: rows}})


def video_payload(payload, transparent=False):
    """Translate the existing single-scene contract, without changing its source."""
    if transparent:
        character = {'avatar_id': payload.get('avatar_pose_id')}
        voice = {'type': 'text', 'input_text': payload.get('input_text'), 'voice_id': payload.get('voice_id')}
        scene = {}
    else:
        scenes = payload.get('video_inputs') or []
        if len(scenes) != 1:
            raise ValueError('HeyGen V3 adapter requires one scene; refusing to drop scenes')
        scene = scenes[0]
        character, voice = scene.get('character') or {}, scene.get('voice') or {}
    dimensions = payload.get('dimension') or {'width': 1280, 'height': 720}
    width, height = dimensions.get('width', 1280), dimensions.get('height', 720)
    ratio = f'{width}:{height}'
    from math import gcd
    divisor = gcd(width, height)
    ratio = f'{width//divisor}:{height//divisor}'
    if ratio not in ('16:9', '9:16', '1:1', '4:5', '5:4'):
        raise ValueError('Unsupported HeyGen aspect ratio; no paid request was sent')
    result = {'type': 'avatar', 'avatar_id': character.get('avatar_id'), 'aspect_ratio': ratio,
              'resolution': '720p' if min(width, height) <= 720 else '1080p',
              'output_format': 'webm' if transparent else 'mp4',
              'engine': {'type': 'avatar_iii'}}
    if voice.get('type') == 'audio':
        if voice.get('audio_url'):
            result['audio_url'] = voice['audio_url']
        elif voice.get('audio_asset_id'):
            result['audio_asset_id'] = voice['audio_asset_id']
        else:
            raise ValueError('Missing HeyGen audio input')
    else:
        result.update(script=voice.get('input_text'), voice_id=voice.get('voice_id'))
        settings = {key: voice[key] for key in ('speed', 'pitch', 'volume', 'locale') if key in voice}
        if settings:
            result['voice_settings'] = settings
    if not transparent and scene.get('background'):
        result['background'] = {key: val for key, val in scene['background'].items() if key in ('url', 'value', 'asset_id')}
    for key in ('title', 'callback_id', 'callback_url', 'folder_id'):
        if payload.get(key):
            result[key] = payload[key]
    return result


async def request(client, method, url, catalog_cache=False, **kwargs):
    """Adapt only known HeyGen operations; no global HTTP patching or paid retries."""
    parts = urlsplit(url)
    base, path = f'{parts.scheme}://{parts.netloc}', parts.path
    headers = dict(kwargs.pop('headers', {}) or {})
    if method == 'GET' and path in ('/v2/voices', '/v2/avatars'):
        voices = path.endswith('voices')
        kwargs.pop('params', None)
        cache_key = (base, next((value for key,value in headers.items() if key.lower()=='x-api-key'), ''))
        cached = _voice_cache.get(cache_key) if voices and catalog_cache else None
        if cached and time.monotonic()-cached[0] < 300:
            return _response(None, copy.deepcopy(cached[1]))
        response = await _catalog(client, base, '/v3/models/audio/voices' if voices else '/v3/avatars/looks',
                              headers, 'voices' if voices else 'avatars', **kwargs)
        if voices and catalog_cache and response.status_code == 200:
            if len(_voice_cache)>10:
                _voice_cache.clear()
            _voice_cache[cache_key] = (time.monotonic(), response.json())
        return response
    if method == 'POST' and path in ('/v2/video/generate', '/v1/video.webm'):
        kwargs['json'] = video_payload(kwargs.get('json') or {}, path.endswith('video.webm'))
        headers.setdefault('Idempotency-Key', str(uuid.uuid4()))
        url = base + '/v3/videos'
    elif method == 'GET' and path == '/v1/video_status.get':
        params = kwargs.pop('params', {}) or {}
        video_id = params.get('video_id') or (parse_qs(parts.query).get('video_id') or [''])[0]
        if not video_id:
            raise ValueError('Missing HeyGen video ID')
        url = base + '/v3/videos/' + quote(video_id, safe='')
    elif method == 'GET' and path in ('/v1/user/remaining_quota', '/v2/user/remaining_quota'):
        response = await client.get(base + '/v3/users/me', headers=headers, **kwargs)
        if response.status_code != 200:
            return response
        account = response.json().get('data') or {}
        usage, wallet = account.get('usage_based') or {}, account.get('wallet') or {}
        remaining = usage.get('remaining_credits')
        balance = wallet.get('remaining_balance')
        return _response(response, {'data': {'remaining_quota': remaining or 0,
            'details': {'plan_credit': 0}, 'wallet_balance': balance, 'currency': wallet.get('currency'),
            'billing_type': account.get('billing_type'), 'balance_known': remaining is not None or balance is not None,
            'plan': (account.get('subscription') or {}).get('plan')}})
    response = await getattr(client, method.lower())(url, headers=headers, **kwargs)
    if response.status_code == 200 and path == '/v1/video_status.get':
        body = response.json()
        data = body.get('data') or {}
        data['video_id'] = data.get('video_id') or data.get('id')
        if data.get('failure_message'):
            data['error'] = {'message': data['failure_message'], 'code': data.get('failure_code')}
        return _response(response, body)
    return response
