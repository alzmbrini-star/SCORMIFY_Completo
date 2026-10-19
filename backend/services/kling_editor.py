"""Build a durable Editor slot without replacing existing slide content."""
import uuid


def editor_video_placeholder(slide, options):
    if options.get('duration',5) not in (5,10,15) or options.get('resolution','720p') not in ('720p','1080p') or options.get('aspectRatio','16:9') not in ('16:9','9:16','1:1') or options.get('audio','off') not in ('off','native'):
        raise ValueError('Configuração de vídeo Kling inválida.')
    marker = str(uuid.uuid4())
    canvas_w, canvas_h = float(slide.get('width') or 960), float(slide.get('height') or 540)
    ratio = {'16:9':16/9,'9:16':9/16,'1:1':1}[options.get('aspectRatio','16:9')]
    width = min(canvas_w*.9, canvas_h*.85*ratio)
    height = width/ratio
    return {
        'id':str(uuid.uuid4()), 'type':'html', 'x':(canvas_w-width)/2, 'y':(canvas_h-height)/2,
        'width':width, 'height':height, 'duration':options.get('duration',5), 'startTime':0,
        'htmlContent':f'<div data-kling-slide="{marker}" data-kling-editor-job="1" style="box-sizing:border-box;width:100%;height:100%;display:grid;place-items:center;padding:24px;background:#10223b;color:#eaf1ff;border:2px dashed #60a5fa;border-radius:14px;font-family:Arial;text-align:center">Vídeo Kling em processamento. Acompanhe o status no Editor; o vídeo substituirá este marcador quando estiver pronto.</div>',
    }, marker
