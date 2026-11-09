"""HeyGem/Duix adapter. Calls our authenticated GPU bridge, NOT the Duix conversational API."""
import base64
import os
import re
from urllib.parse import urlsplit
import httpx


class HeygemError(ValueError):
    pass


def asset_path(url):
    """Only completed SCORMIFY HeyGem capability URLs, never arbitrary embeds."""
    path=urlsplit(str(url or '')).path
    if not re.fullmatch(r'/api/heygem/assets/[a-f0-9-]{36}\.mp4',path):
        raise HeygemError('Selecione um vídeo HeyGem concluído na biblioteca.')
    return path


def video_element(url):
    import uuid
    return {'id':str(uuid.uuid4()),'type':'video','provider':'heygem','src':asset_path(url),
            'x':1120,'y':110,'width':740,'height':440,'objectFit':'contain','autoplay':False,
            'loop':False,'startTime':0,'animations':[]}


def configuration():
    url=os.environ.get('HEYGEM_BRIDGE_URL','').strip().rstrip('/')
    key=os.environ.get('HEYGEM_BRIDGE_KEY','').strip()
    parsed=urlsplit(url)
    valid=bool(parsed.hostname and parsed.scheme=='https' and not parsed.username and not parsed.password
               and not parsed.query and not parsed.fragment)
    return url,key,bool(valid and len(key)>=24)


def tts_key():
    return os.environ.get('ELEVENLABS_API_KEY','').strip().strip('"').strip("'")


async def bridge(method,path,**kwargs):
    url,key,ready=configuration()
    if not ready:raise HeygemError('HeyGem não configurado: o administrador precisa instalar a ponte GPU e definir HEYGEM_BRIDGE_URL e HEYGEM_BRIDGE_KEY no servidor.')
    try:
        async with httpx.AsyncClient(timeout=60,follow_redirects=False,trust_env=False) as client:
            response=await client.request(method,url+path,headers={'Authorization':'Bearer '+key},**kwargs)
        if response.status_code>=300:raise HeygemError('O serviço HeyGem recusou a operação. Confira disponibilidade e configuração da ponte GPU.')
        return response.json()
    except (httpx.HTTPError,ValueError) as exc:
        if isinstance(exc,HeygemError):raise
        raise HeygemError('Não foi possível confirmar a operação no HeyGem. Consulte a tarefa existente antes de iniciar outra geração.') from exc


async def catalog():
    result=await bridge('GET','/avatars')
    if not isinstance(result,dict):raise HeygemError('Catálogo HeyGem inválido.')
    rows=result.get('avatars',[])
    if not isinstance(rows,list):raise HeygemError('Catálogo HeyGem inválido.')
    return [{'id':r['id'],'name':str(r.get('name') or r['id'])[:100]} for r in rows[:100]
            if isinstance(r,dict) and re.fullmatch(r'[a-zA-Z0-9_-]{1,80}',str(r.get('id','')))]


async def speech(script,voice):
    if not tts_key():raise HeygemError('Configure ElevenLabs para gerar a fala em português brasileiro.')
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}',voice):raise HeygemError('ID de voz ElevenLabs inválido.')
    try:
        async with httpx.AsyncClient(timeout=120,follow_redirects=False,trust_env=False) as client:
            response=await client.post('https://api.elevenlabs.io/v1/text-to-speech/'+voice,
                headers={'xi-api-key':tts_key(),'Accept':'audio/mpeg'},
                json={'text':script,'model_id':'eleven_multilingual_v2','language_code':'pt',
                      'voice_settings':{'stability':.5,'similarity_boost':.75}})
        if response.status_code!=200:raise HeygemError('ElevenLabs não gerou o áudio. Confira a voz, a chave e os créditos.')
        if not response.content or len(response.content)>8_000_000:raise HeygemError('Áudio vazio ou maior que o limite desta prova de conceito.')
        return response.content
    except httpx.HTTPError as exc:raise HeygemError('Falha ao gerar áudio PT-BR; não foi solicitado vídeo ao HeyGem.') from exc


async def submit(code,avatar,audio):
    return await bridge('POST','/jobs',json={'code':code,'avatar_id':avatar,
                                          'audio_base64':base64.b64encode(audio).decode('ascii')})


async def status(code):
    return await bridge('GET','/jobs/'+code)


async def download(code):
    """Stream bounded bytes from the configured bridge only; never trust output URLs."""
    url,key,ready=configuration()
    if not ready:raise HeygemError('Ponte HeyGem não configurada.')
    async with httpx.AsyncClient(timeout=120,follow_redirects=False,trust_env=False) as client:
        async with client.stream('GET',url+'/jobs/'+code+'/video',headers={'Authorization':'Bearer '+key}) as response:
            if response.status_code!=200:raise HeygemError('O vídeo HeyGem ainda não está disponível para persistência.')
            count=0
            async for chunk in response.aiter_bytes(1024*1024):
                count+=len(chunk)
                if count>256*1024*1024:raise HeygemError('O vídeo ultrapassou 256 MB. Use um roteiro mais curto.')
                yield chunk


async def prepare_for_export(project,db,assets_dir):
    """Materialize persistent MP4s and rewrite only the export's in-memory copy.

    Never fetch an arbitrary URL, retain provider credentials or modify a course.
    All exporters already support local project asset URLs, including nested HTML.
    """
    from pathlib import Path
    from motor.motor_asyncio import AsyncIOMotorGridFSBucket
    pattern=re.compile(r'(?:https?://[^/\s\"\'<>]+)?/api/heygem/assets/([a-f0-9-]{36})\.mp4')
    def strings(value):
        if isinstance(value,str):yield value
        elif isinstance(value,dict):
            for item in value.values():yield from strings(item)
        elif isinstance(value,list):
            for item in value:yield from strings(item)
    codes={m.group(1) for value in strings(project) for m in pattern.finditer(value)}
    if not codes:return 0
    directory=Path(assets_dir);directory.mkdir(parents=True,exist_ok=True)
    for code in codes:
        record=await db.heygem_videos.find_one({'video_id':code,'status':'completed',
                                               'companyId':project.get('companyId')})
        if not record or not record.get('fileId'):raise HeygemError('Vídeo HeyGem indisponível para exportação. Confira a biblioteca antes de exportar.')
        target=directory/('heygem_'+code+'.mp4')
        if not target.is_file():
            temporary=directory/('heygem_'+code+'.'+__import__('uuid').uuid4().hex+'.part')
            stream=await AsyncIOMotorGridFSBucket(db,bucket_name='heygem_media').open_download_stream(record['fileId'])
            try:
                with temporary.open('wb') as out:
                    while True:
                        chunk=await stream.read(1024*1024)
                        if not chunk:break
                        out.write(chunk)
                temporary.replace(target)
            finally:
                stream.close()
                temporary.unlink(missing_ok=True)
    def rewrite(value):
        if isinstance(value,str):return pattern.sub(lambda m:'/api/projects/'+project['id']+'/assets/heygem_'+m.group(1)+'.mp4',value)
        if isinstance(value,list):return [rewrite(item) for item in value]
        if isinstance(value,dict):return {k:rewrite(v) for k,v in value.items()}
        return value
    updated=rewrite(project);project.clear();project.update(updated)
    return len(codes)
