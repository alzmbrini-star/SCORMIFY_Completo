"""Serial, checkpointed movie production. A lost paid POST is NEVER retried."""
import asyncio
import base64
import json
import os
import time
from pathlib import Path
from datetime import datetime,timezone
from services import runway_ai,runway_narration
from services.asset_store import store_asset_async,retrieve_asset_async
from services.educational_film import voice_for

LIMIT=asyncio.Semaphore(1)


class KnownFailure(ValueError):pass
class UncertainSubmission(ValueError):pass


def now():return datetime.now(timezone.utc).isoformat()


def operation_signature(board,key):
    from services.educational_film import revision
    if key=='music':data=[board['musicPrompt'],sum(s['duration'] for s in board['scenes'])]
    elif key.startswith('character_'):data=[board['style'],board['characters'][int(key.split('_')[1])]['name'],board['characters'][int(key.split('_')[1])]['description']]
    else:
        kind,index=key.split('_');scene=board['scenes'][int(index)]
        if kind=='voice':data=[scene['narration'],voice_for(board,scene),board['allowOtherVoices']]
        else:
            data=[board['style'],[(c['name'],c['description']) for c in board['characters']],scene['visual']]
            if kind=='video':data += [board['model'],scene['duration']]
    return revision(data)


async def poll(task_id,touch):
    for _ in range(180):
        data=await runway_ai.get_task(task_id)
        if data.get('status')=='SUCCEEDED':
            result=data.get('output') or []
            if not result or not isinstance(result[0],str):raise KnownFailure('O provedor não retornou o arquivo da tarefa.')
            return result[0]
        if data.get('status') in ('FAILED','CANCELLED'):raise KnownFailure('A tarefa do provedor falhou. Reveja a cena; outra tentativa requer novo orçamento aprovado.')
        await touch()
        await asyncio.sleep(5)
    raise TimeoutError('A tarefa ainda não concluiu. Retome a consulta da mesma tarefa, sem outra geração.')


async def run(film_id,run_id,database,projects_dir):
    async with LIMIT:
        film=await database.educational_films.find_one({'id':film_id,'runId':run_id,'status':'generating'})
        if not film:return
        board=film['board'];pid=film['projectId'];folder=Path(projects_dir)/pid/'assets';folder.mkdir(parents=True,exist_ok=True)
        operations=film.get('operations',{})
        async def write(values):
            result=await database.educational_films.update_one({'id':film_id,'runId':run_id,'status':'generating'},
                {'$set':{**values,'heartbeat':now(),'updatedAt':now()}})
            if not result.matched_count:raise RuntimeError('A execução não está mais ativa.')
        async def persist(path):
            if not path.is_file() or not 0<path.stat().st_size<=180*1024*1024:raise KnownFailure('Arquivo de mídia inválido ou maior que 180 MB.')
            if not await store_asset_async(database,pid,path.name,str(path)):raise RuntimeError('Não foi possível preservar a mídia; não haverá repetição paga automática.')
            return f'/api/projects/{pid}/assets/{path.name}'
        async def local(op):
            path=folder/op['filename']
            if not path.is_file():
                raw,_=await retrieve_asset_async(database,pid,path.name)
                if not raw:raise KnownFailure('A mídia preservada não foi encontrada. Nenhuma nova geração foi feita.')
                path.write_bytes(raw)
            return path
        async def operation(key,submit,kind):
            op=operations.get(key,{})
            if op.get('status')=='ready':return await local(op)
            if op.get('status') in ('sending','unknown'):raise UncertainSubmission('Envio pago não confirmado. Confira o provedor; o sistema não o repetirá.')
            signature=operation_signature(board,key)
            if op.get('status')!='submitted':
                op={'status':'sending','signature':signature,'approval':film['budgetApproval']['token'],'kind':kind}
                operations[key]=op;await write({f'operations.{key}':op,'progress':key})
                try:result=await submit()
                except Exception as exc:
                    op.update(status='unknown');await write({f'operations.{key}':op})
                    raise UncertainSubmission('Não foi possível confirmar uma chamada paga. Confira o provedor antes de tentar outra geração.') from exc
                if kind=='voice':
                    path=folder/f'film_{film_id}_{key}_{signature[:10]}.mp3';path.write_bytes(result)
                    # Store immediately: a restart must not cause a second synthesis.
                    url=await persist(path);op.update(status='ready',filename=path.name,url=url)
                    operations[key]=op;await write({f'operations.{key}':op});return path
                task_id=str(result.get('id') or '');import uuid;uuid.UUID(task_id)
                op.update(status='submitted',taskId=task_id);operations[key]=op
                await write({f'operations.{key}':op})
            try:remote=await poll(op['taskId'],lambda:write({}))
            except KnownFailure:
                op.update(status='failed');await write({f'operations.{key}':op});raise
            suffix={'image':'.png','video':'.mp4','music':'.mp3'}[kind]
            path=folder/f'film_{film_id}_{key}_{signature[:10]}{suffix}'
            await runway_ai.download(remote,path,{'image':'image','video':'video','music':'audio'}[kind])
            url=await persist(path);op.update(status='ready',filename=path.name,url=url)
            operations[key]=op;await write({f'operations.{key}':op})
            if kind=='image':
                await database.image_gallery.update_one({'id':f'{film_id}:{key}:{signature}'},{'$setOnInsert':{
                    'id':f'{film_id}:{key}:{signature}','imageUrl':url,'projectId':pid,'projectName':board['title'],
                    'companyId':film.get('companyId'),'userId':film['ownerId'],'createdAt':now(),'prompt':'Filme educativo · '+key}},upsert=True)
            return path
        def image_input(path):
            from PIL import Image
            import io
            out=io.BytesIO()
            with Image.open(path) as im:im.convert('RGB').save(out,'JPEG',quality=88)
            return 'data:image/jpeg;base64,'+base64.b64encode(out.getvalue()).decode()
        try:
            characters=[]
            for i,char in enumerate(board['characters']):
                prompt=f"Original educational {board['style']} cartoon character, full body, clean neutral background. {char['name']}: {char['description']}. Consistent clothes and face. No text or logos."
                path=await operation(f'character_{i}',lambda p=prompt:runway_ai.request('POST','text_to_image',{'model':'gen4_image','ratio':'1280:720','promptText':p}),'image')
                characters.append({'uri':image_input(path),'tag':f'character{i+1}'})
            clips=[];subtitle_lines=[];cursor=0
            for i,scene in enumerate(board['scenes']):
                await write({'progress':f'Cena {i+1} de {len(board["scenes"])}'})
                audio=await operation(f'voice_{i}',lambda s=scene:runway_narration.speech({'text':s['narration'],
                    'voiceId':voice_for(board,s),'allowOtherVoices':board['allowOtherVoices']}),'voice')
                spoken=await runway_narration.duration(audio)
                if spoken+.15>scene['duration']:
                    raise KnownFailure(f'Cena {i+1}: a fala dura {spoken:.1f}s, excedendo {scene["duration"]}s. Reduza a fala e aprove novamente; áudio preservado, vídeo desta cena não foi gerado.')
                prompt=(f"Educational {board['style']} cartoon scene. Keep the exact appearance and clothes of "+' and '.join('@'+c['tag'] for c in characters)+'. '+scene['visual']+'. No written text, subtitles or logos.')[:1000]
                frame=await operation(f'frame_{i}',lambda p=prompt:runway_ai.request('POST','text_to_image',{
                    'model':'gen4_image','ratio':'1280:720','promptText':p,'referenceImages':characters}),'image')
                _,payload=runway_ai.build_payload({'model':board['model'],'duration':scene['duration'],'aspectRatio':'16:9',
                    'image':image_input(frame),'prompt':(f"{board['style']} cartoon animation. "+scene['visual']+'. Natural character movements, consistent faces and clothes, stable camera. No text.')[:1000]})
                video=await operation(f'video_{i}',lambda p=payload:runway_ai.request('POST','image_to_video',p),'video')
                clip=folder/f'film_{film_id}_scene_{i}.mp4'
                ffmpeg,_=runway_narration.media_tools()
                await runway_narration.run_media([ffmpeg,'-y','-v','error','-i',str(video),'-i',str(audio),
                    '-map','0:v:0','-map','1:a:0','-vf','scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=24',
                    '-af','apad','-t',str(scene['duration']),'-c:v','libx264','-preset','veryfast','-crf','22','-pix_fmt','yuv420p',
                    '-threads','1','-filter_threads','1','-c:a','aac','-ar','44100','-ac','2','-movflags','+faststart',str(clip)])
                clips.append(clip)
                def stamp(sec):
                    ms=round(sec*1000);return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'
                subtitle_lines.append(f'{i+1}\n{stamp(cursor)} --> {stamp(cursor+spoken)}\n{scene["narration"]}\n');cursor+=scene['duration']
            listing=folder/f'film_{film_id}_concat.txt'
            # Filenames are application-generated UUIDs, not user-supplied paths.
            listing.write_text(''.join("file '"+p.name+"'\n" for p in clips),encoding='utf-8')
            merged=folder/f'film_{film_id}_merged.mp4'
            await runway_narration.run_media([ffmpeg,'-y','-v','error','-f','concat','-safe','1','-i',str(listing),'-c','copy','-movflags','+faststart',str(merged)])
            music=None
            if board['music']:
                music=await operation('music',lambda:runway_ai.request('POST','text_to_music',{'model':'eleven_music_v2_5',
                    'promptText':board['musicPrompt'],'instrumental':True,'duration':cursor}),'music')
            final=folder/f'educational_film_{film_id}.mp4'
            if music:
                gain=board['musicVolume']/100
                filters=f'[1:a]volume={gain},afade=t=in:d=1,afade=t=out:st={max(0,cursor-1)}:d=1[m];[0:a]asplit=2[v][key];[m][key]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=300[bed];[v][bed]amix=inputs=2:duration=first:normalize=0[out]'
                await runway_narration.run_media([ffmpeg,'-y','-v','error','-i',str(merged),'-stream_loop','-1','-i',str(music),
                    '-filter_complex',filters,'-filter_complex_threads','1','-map','0:v:0','-map','[out]','-c:v','copy','-c:a','aac','-t',str(cursor),'-movflags','+faststart',str(final)])
            else:await asyncio.to_thread(__import__('shutil').copyfile,merged,final)
            final_url=await persist(final)
            subtitles=folder/f'film_{film_id}.srt';subtitles.write_text('\n'.join(subtitle_lines),encoding='utf-8');srt_url=await persist(subtitles)
            # Only the independently created film workspace is changed, NEVER sourceProjectId.
            await database.projects.update_one({'id':pid,'source':'educational_film','course.slides.0.id':film['slideId'],
                'course.slides.0.elements':[]},{'$set':{
                'course.slides.0.elements':[{'id':film_id,'type':'video','x':0,'y':0,'width':1280,'height':720,'src':final_url,
                    'provider':'educational_film','controls':True,'autoplay':False,'objectFit':'contain','duration':cursor}],
                'course.slides.0.duration':cursor,'name':board['title']+' — Filme educativo','updatedAt':now()}})
            await write({'status':'completed','videoUrl':final_url,'subtitlesUrl':srt_url,'duration':cursor,'progress':'Filme concluído','error':None})
        except Exception as exc:
            uncertain=isinstance(exc,UncertainSubmission) or any(o.get('status') in ('sending','unknown') for o in operations.values())
            message=str(exc) if isinstance(exc,(KnownFailure,UncertainSubmission,TimeoutError)) else 'A produção foi interrompida. Mídias prontas foram preservadas; consulte o status antes de autorizar uma retomada.'
            await write({'status':'unknown' if uncertain else 'failed','error':message[:800]})
