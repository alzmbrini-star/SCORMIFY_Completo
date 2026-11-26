"""Independent, single-attempt Eleven Music generation with revision-bound BRL consent."""
import hashlib
import json
import math
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_CEILING
from typing import Literal
import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator
from services.runway_narration import api_key

RATE_USD_MINUTE = Decimal('0.15')
RATES_VERSION = 'eleven-music-2026-11-26'
MAX_AUDIO_BYTES = 8 * 1024 * 1024


class MusicSpec(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    title: str = Field(min_length=3, max_length=160)
    mode: Literal['instrumental', 'educational'] = 'instrumental'
    theme: str = Field(min_length=10, max_length=800)
    style: str = Field(default='Inspiradora, leve e acolhedora', min_length=3, max_length=400)
    lyrics: str = Field(default='', max_length=2500)
    duration: int = Field(default=60, ge=15, le=300, strict=True)

    @model_validator(mode='after')
    def instrumental_has_no_lyrics(self):
        if self.mode == 'instrumental' and self.lyrics:
            raise ValueError('Trilhas instrumentais não usam letra. Selecione Música educativa para incluir vocais.')
        return self


def signature(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def payload(spec):
    spec = MusicSpec.model_validate(spec).model_dump()
    instruction = ('Trilha somente instrumental, sem voz nem letra.' if spec['mode']=='instrumental' else
                   'Música educativa cantada exclusivamente em português do Brasil, dicção clara. '
                   + ('Use a letra original abaixo; não acrescente afirmações factuais.' if spec['lyrics'] else
                      'Crie letra original, acessível, sobre o tema; não invente números, leis ou promessas.'))
    prompt = f"{instruction}\nTema e objetivos: {spec['theme']}\nEstilo e clima: {spec['style']}"
    if spec['lyrics']: prompt += '\nLetra original:\n' + spec['lyrics']
    prompt += '\nComposição original, sem imitar artistas ou músicas existentes.'
    return {'model_id':'music_v1', 'prompt':prompt, 'music_length_ms':spec['duration']*1000,
            'force_instrumental':spec['mode']=='instrumental'}


def quote(spec, fx, now=None):
    spec = MusicSpec.model_validate(spec).model_dump()
    now = now or datetime.now(timezone.utc)
    # No static currency fallback: BRL approval must refer to a dated official quote.
    if not fx.get('available') or not math.isfinite(float(fx.get('rate',0))) or not .1 <= float(fx['rate']) <= 100:
        raise ValueError('Cotação em reais indisponível. Tente calcular novamente; nenhuma mídia foi gerada.')
    day = datetime.fromisoformat(fx['asOfDate']).date()
    if not timedelta(0) <= now.date()-day <= timedelta(days=7):
        raise ValueError('Cotação vencida. Consulte novamente antes de aprovar.')
    usd = Decimal(spec['duration']) / 60 * RATE_USD_MINUTE
    brl = (usd*Decimal(str(fx['rate']))).quantize(Decimal('.01'),rounding=ROUND_CEILING)
    value = {'revision':signature(spec),'duration':spec['duration'],'estimatedUsd':float(usd),
             'estimatedBrl':float(brl),'exchange':fx,'ratesVersion':RATES_VERSION,
             'rateUsdMinute':float(RATE_USD_MINUTE),'rateSource':'https://elevenlabs.io/pricing/api',
             'expiresAt':(now+timedelta(hours=24)).isoformat(),
             'disclaimer':'Estimativa para uma única geração, sem impostos, IOF, spread ou infraestrutura. '
                          'O provedor cobra em dólares/créditos conforme seu plano. O limite autoriza esta chamada, '
                          'não garante o valor da fatura. Sem repetição paga automática. Confira a licença comercial do seu plano.'}
    value['id']=signature(value)
    return value


def validate_approval(job, quote_id, ceiling_brl, consent, now=None):
    q=job['quote']; now=now or datetime.now(timezone.utc)
    if q['id'] != quote_id or q['revision'] != signature(job['spec']):
        raise ValueError('O conteúdo ou orçamento mudou. Calcule e aprove novamente.')
    if datetime.fromisoformat(q['expiresAt']) <= now:
        raise ValueError('Orçamento vencido. Calcule um novo orçamento antes de gerar.')
    limit=Decimal(str(ceiling_brl))
    if not consent or not limit.is_finite() or limit < Decimal(str(q['estimatedBrl'])) or limit > 10000:
        raise ValueError('Confirme o orçamento em reais e informe um limite suficiente.')
    return {'quoteId':quote_id,'revision':q['revision'],'ceilingBrl':float(limit),
            'ceilingUsd':float(limit/Decimal(str(q['exchange']['rate']))),'approvedAt':now.isoformat()}


async def compose(spec):
    if not api_key(): raise ValueError('ElevenLabs não configurada no servidor.')
    # One POST only. A timeout/connection loss is ambiguous and must never be retried automatically.
    async with httpx.AsyncClient(timeout=httpx.Timeout(660, connect=20), follow_redirects=False) as client:
        async with client.stream('POST','https://api.elevenlabs.io/v1/music',
                params={'output_format':'mp3_44100_128'},headers={'xi-api-key':api_key()},json=payload(spec)) as response:
            if response.status_code != 200:
                messages={401:'Chave ElevenLabs inválida.',402:'Saldo ElevenLabs insuficiente.',
                          403:'A conta ou chave não permite Eleven Music. Confira plano e permissões.',
                          422:'O provedor recusou os parâmetros ou conteúdo da música.',429:'Limite ElevenLabs atingido.'}
                raise ValueError(messages.get(response.status_code,f'Eleven Music retornou HTTP {response.status_code}.'))
            data=bytearray()
            async for chunk in response.aiter_bytes():
                data.extend(chunk)
                if len(data)>MAX_AUDIO_BYTES:raise ValueError('Áudio excedeu o limite seguro de armazenamento.')
            if len(data)<128 or not (data[:3]==b'ID3' or data[0]==255 and data[1]&224==224):
                raise ValueError('O provedor não retornou um MP3 válido.')
            return bytes(data)
