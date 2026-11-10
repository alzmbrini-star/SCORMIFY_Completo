"""Gamma 5 transport and bounded PNG import. Never retries a paid POST."""
import io
import os
import re
import zipfile
import socket
import ipaddress
import asyncio
from urllib.parse import urlparse

import httpx
from PIL import Image

BASE = 'https://public-api.gamma.app/v1.0'
MAX_ARCHIVE = 80 * 1024 * 1024


class GammaError(ValueError):
    pass


def configured():
    return bool(os.getenv('GAMMA_API_KEY', '').strip())


async def request(method, path, payload=None):
    key = os.getenv('GAMMA_API_KEY', '').strip()
    if not key:
        raise GammaError('GAMMA_API_KEY não está configurada no servidor.')
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.request(method, BASE + path, json=payload,
                                            headers={'X-API-KEY': key})
    except httpx.HTTPError:
        raise GammaError('Sem confirmação do Gamma. Não repita a geração: confira o histórico e os créditos no Gamma.') from None
    if response.status_code >= 400:
        messages = {401: 'Chave Gamma inválida ou revogada.', 402: 'Créditos Gamma insuficientes.',
                    403: 'A conta Gamma não permite esta operação.', 429: 'Limite Gamma atingido. Aguarde antes de consultar novamente.',
                    400: 'Gamma rejeitou os parâmetros da solicitação.', 422: 'Gamma rejeitou os parâmetros da solicitação.'}
        raise GammaError(messages.get(response.status_code, 'Gamma indisponível. Confira o histórico antes de repetir a geração.'))
    try:
        return response.json()
    except ValueError:
        raise GammaError('Resposta Gamma não reconhecida. Não repita a geração automaticamente.') from None


def generation_payload(title, prompt):
    return {'prompt': prompt, 'title': title, 'format': 'presentation', 'numCards': 5,
            'quality': 'standard', 'exportAs': 'png', 'disableConnectors': True,
            'additionalInstructions': 'Produza exatamente 5 slides, integralmente em Português do Brasil (pt-BR), incluindo títulos e legendas. '
            'Use proporção horizontal 16:9, ilustrações contextualizadas, fontes grandes e bom contraste. '
            'Uma capa com o nome do curso, três slides de desenvolvimento e uma conclusão prática. Evite excesso de texto.',
            'sharingOptions': {'externalAccess': 'noAccess', 'workspaceAccess': 'noAccess'}}


def generation_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'gen_[A-Za-z0-9]{1,124}', value):
        raise GammaError('Gamma não confirmou o identificador da geração. Confira o histórico antes de repetir.')
    return value


def public_gamma_url(value):
    parsed = urlparse(value or '')
    return value if parsed.scheme == 'https' and (parsed.hostname == 'gamma.app' or (parsed.hostname or '').endswith('.gamma.app')) else None


async def download(url):
    # Only URLs returned by Gamma are accepted, never a user-supplied download URL.
    parsed = urlparse(url or '')
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        raise GammaError('Exportação Gamma sem endereço HTTPS válido.')
    try:
        addresses = await asyncio.to_thread(socket.getaddrinfo, parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
            raise GammaError('Endereço de exportação Gamma não permitido.')
    except OSError:
        raise GammaError('Não foi possível localizar o servidor da exportação Gamma.') from None
    async with httpx.AsyncClient(timeout=120, follow_redirects=False) as client:
        try:
            async with client.stream('GET', url) as response:
                if response.status_code != 200:
                    raise GammaError('Não foi possível baixar a exportação Gamma. A geração não será repetida.')
                output = bytearray()
                async for chunk in response.aiter_bytes():
                    output.extend(chunk)
                    if len(output) > MAX_ARCHIVE:
                        raise GammaError('Exportação Gamma excede o limite de 80 MB.')
                return bytes(output)
        except httpx.HTTPError:
            raise GammaError('Download Gamma interrompido. Consulte novamente; não gere outra apresentação.') from None


def png_slides(raw):
    """Do not extract paths or trust archive sizes/dimensions. Convert one card at a time."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw))
        entries = [i for i in archive.infolist() if not i.is_dir() and i.filename.lower().endswith('.png') and not i.filename.startswith('__MACOSX/')]
        if not 1 <= len(entries) <= 20 or len(archive.infolist()) > 100:
            raise GammaError('Quantidade de imagens inesperada na exportação Gamma.')
        if sum(i.file_size for i in entries) > 160 * 1024 * 1024 or any(i.file_size > 24 * 1024 * 1024 for i in entries):
            raise GammaError('Imagens Gamma excedem o limite de importação.')
        entries.sort(key=lambda item: [int(part) if part.isdigit() else part.lower() for part in re.split(r'(\d+)', item.filename)])
        for item in entries:
            with archive.open(item) as source:
                data = source.read(24 * 1024 * 1024 + 1)
            with Image.open(io.BytesIO(data)) as image:
                w, h = image.size
                if image.format != 'PNG' or w < 100 or h < 100 or w * h > 25_000_000:
                    raise GammaError('Imagem Gamma com formato ou dimensões inválidas.')
                image = image.convert('RGB')
                image.thumbnail((2560, 2560))
                result = io.BytesIO()
                image.save(result, 'WEBP', quality=92, method=4)
                if len(result.getvalue()) > 6 * 1024 * 1024:
                    raise GammaError('Slide Gamma excede o limite de armazenamento.')
                yield result.getvalue(), w, h
    except GammaError:
        raise
    except (ValueError, OSError, zipfile.BadZipFile, RuntimeError):
        raise GammaError('O ZIP Gamma não contém slides PNG válidos.') from None
