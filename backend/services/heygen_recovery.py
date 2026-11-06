"""Reconcile existing avatar jobs with their original slides. Never generates."""
import copy


async def reconcile_project(database, project, fetch_status, apply_video):
    project_id = project['id']
    videos = []
    for original in project.get('heygenPending', []):
        item = copy.deepcopy(original)
        slide_id, video_id = item.get('slideId'), item.get('videoId')
        query = {'project_id': project_id, 'slide_id': slide_id}
        if video_id: query['video_id'] = video_id
        records = await database.heygen_videos.find(query).limit(2).to_list(2)
        error = ''
        if len(records) > 1:
            item['status'] = 'failed'
            error = 'Há mais de um vídeo para este slide. Nenhuma substituição foi aplicada.'
        else:
            saved = records[0] if records else {}
            video_id = video_id or saved.get('video_id')
            if video_id:
                item['videoId'] = video_id
                try:
                    if item.get('attachmentStatus') == 'attached' and item.get('status') == 'completed':
                        data = dict(status='completed', video_url=item.get('videoUrl'))
                    elif saved.get('status') == 'completed' and saved.get('video_url'):
                        data = saved
                    else:
                        data = await fetch_status(video_id)
                    status, url = data.get('status', 'processing'), data.get('video_url')
                    if status == 'completed' and url:
                        if item.get('attachmentStatus') != 'attached':
                            applied = await apply_video(slide_id, url, data, item)
                            if applied is False:
                                raise ValueError('O slide original foi alterado. Nenhuma edição foi substituída.')
                        item.update(status='completed', videoUrl=url, attachmentStatus='attached')
                        await database.heygen_videos.update_one(query | {'video_id':video_id},
                            {'$set': {'status':'completed', 'video_url':url}})
                    elif status == 'failed':
                        item['status'] = 'failed'
                        error = 'O HeyGen informou falha neste vídeo. O curso e as perguntas foram preservados.'
                    else:
                        item['status'] = 'processing'
                    fields = {f'heygenPending.$.{key}':item[key] for key in ('videoId','status','videoUrl','attachmentStatus') if key in item}
                    await database.projects.update_one({'id':project_id,'heygenPending.slideId':slide_id},
                        {'$set':fields, '$unset':{'heygenPending.$.error':''}})
                except ValueError as exc:
                    item['status'] = 'failed'; error = str(exc)
                except Exception:
                    item['status'] = 'failed'
                    error = 'Não foi possível consultar ou reconectar este vídeo. Nenhuma nova geração foi solicitada; tente Atualizar.'
            elif item.get('status') == 'failed':
                item['status'] = 'failed'
                error = 'Não foi encontrado um identificador de vídeo para reconectar. Não gere novamente antes de revisar a biblioteca.'
        result = {key:item.get(key) for key in ('slideId','slideIndex','title','videoId','status','videoUrl')}
        if error: result['error'] = error
        videos.append(result)
    completed = sum(v.get('status') == 'completed' for v in videos)
    failed = sum(v.get('status') == 'failed' for v in videos)
    processing = len(videos)-completed-failed
    status = 'processing' if processing else 'partial_failed' if failed else 'all_done'
    return dict(status=status, videos=videos, completedCount=completed, failedCount=failed, processingCount=processing)
