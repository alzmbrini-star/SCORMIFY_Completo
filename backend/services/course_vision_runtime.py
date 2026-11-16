"""Bounded, paced visual reads; no course writes, no blind quota retries."""
import asyncio
import logging
import os
import threading
import time

logger = logging.getLogger(__name__)
_lock = threading.Lock()
_next_request = 0.0

MESSAGES = {
    'quota_exhausted': 'A API informou saldo/cota indisponível. Confira o faturamento da organização da chave.',
    'rate_limit': 'A API limitou temporariamente as chamadas. A leitura válida foi preservada para retomada.',
    'authentication': 'A API recusou a chave ou a permissão do modelo.',
    'provider_error': 'A API de leitura está temporariamente indisponível.',
    'timeout': 'A API não respondeu dentro do prazo desta leitura.',
    'invalid_response': 'A resposta da IA não trouxe uma leitura válida completa.',
    'image_unreadable': 'A IA informou que o conteúdo da imagem não está legível.',
    'asset_error': 'Não foi possível preparar a imagem-base para leitura.',
    'not_attempted': 'Leitura pendente para retomada: impedimento da API ou limite de execução desta análise.',
}


class VisionFailure(Exception):
    def __init__(self, code, request_id=None):
        self.code, self.request_id = code, request_id
        super().__init__(MESSAGES[code])


def error_code(exc, phase='provider'):
    if isinstance(exc, VisionFailure):
        return exc.code
    body = getattr(exc, 'body', None) or {}
    error = body.get('error', body) if isinstance(body, dict) else {}
    code = getattr(exc, 'code', None) or error.get('code') or error.get('type')
    status = getattr(exc, 'status_code', None)
    if code in ('insufficient_quota', 'credit_balance_exhausted', 'billing_hard_limit_reached', 'usage_limit_reached'):
        return 'quota_exhausted'
    if status == 429:
        return 'rate_limit'
    if status in (401,403,404):
        return 'authentication'
    if phase == 'asset':
        return 'asset_error'
    if 'timeout' in type(exc).__name__.lower():
        return 'timeout'
    if isinstance(exc, (ValueError, TypeError, KeyError)) or status == 400:
        return 'invalid_response'
    return 'provider_error'


async def pace(sleep=asyncio.sleep):
    global _next_request
    interval = max(0.0, min(60.0, float(os.environ.get('OPENAI_COURSE_VISION_MIN_INTERVAL', '20'))))
    with _lock:
        now = time.monotonic()
        delay = max(0.0, _next_request-now)
        _next_request = max(now, _next_request)+interval
    if delay:
        await sleep(delay)


async def recover(operation, sleep=asyncio.sleep, gate=pace):
    """At most four attempts; only explicit temporary 429 gets a retry."""
    waited = 0.0
    for attempt in range(4):
        await gate()
        try:
            return await operation()
        except Exception as exc:
            code = error_code(exc)
            if code != 'rate_limit' or attempt == 3:
                raise
            response = getattr(exc, 'response', None)
            headers = getattr(response, 'headers', {}) or {}
            try:
                delay = float(headers.get('retry-after') or float(headers.get('retry-after-ms', 0))/1000 or 20*(attempt+1))
            except (ValueError,TypeError):
                delay = 20*(attempt+1)
            delay = max(1, delay)
            if waited+delay > 180:
                raise  # Never retry before an upstream wait larger than our budget.
            logger.warning('course_vision_retry code=%s attempt=%d wait=%.1f request_id=%s', code, attempt+1, delay, getattr(exc,'request_id',None))
            waited += delay
            await sleep(delay)
