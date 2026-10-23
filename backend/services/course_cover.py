"""Editable course cover: authoritative title and bounded visual composition."""
import html
import re


def build_cover(slide,palette,course_title,modules,image_url=None):
    from models import generate_id
    from services.ai_agent import _tokens
    tokens=_tokens(palette)
    configured=str(course_title or '').strip()
    fallback=str(slide.get('title') or '').strip()
    if fallback.casefold() in ('capa','capa do curso','introdução','introducao','title','cover'):
        fallback='Sua jornada de aprendizagem'
    title=configured or fallback or 'Sua jornada de aprendizagem'
    subtitle=''
    for element in slide.get('elements',[]):
        content=element.get('content') or element.get('htmlContent') or ''
        if not isinstance(content,str):continue
        match=re.search(r'<p\b[^>]*>([\s\S]*?)</p>',content,re.I)
        if match:
            subtitle=html.unescape(re.sub('<[^>]+>','',match[1])).strip()
            if subtitle:break
    subtitle=subtitle or str(slide.get('purpose') or 'Conheça os conceitos, explore situações práticas e aplique o aprendizado.')
    safe=lambda value:html.escape(str(value),quote=True)
    title_size=64 if len(title)<65 else 52 if len(title)<120 else 42
    badge=f'{len(modules)} módulos' if modules else 'Aprendizagem aplicada'
    copy=f'''<div data-course-cover="2" style="box-sizing:border-box;height:100%;overflow:auto;padding:12px 16px 12px 0;font-family:{tokens['body']};color:{tokens['text']};">
<p style="margin:0 0 28px;font-size:16px;letter-spacing:3px;text-transform:uppercase;color:{tokens['accent']};font-weight:700">Aprenda • pratique • transforme</p>
<h1 style="font-family:{tokens['heading']};font-size:{title_size}px;line-height:1.1;letter-spacing:-1.2px;margin:0 0 26px;color:{tokens['text']};overflow-wrap:anywhere">{safe(title)}</h1>
<p style="font-size:25px;line-height:1.5;color:{tokens['muted']};margin:0 0 32px">{safe(subtitle)}</p>
<p style="display:inline-block;background:{tokens['card_bg']};border:1px solid {tokens['card_border']};padding:12px 18px;border-radius:12px;font-size:18px;color:{tokens['text']};margin:0 0 28px">{safe(badge)}</p>
<p style="margin:0;font-size:21px;font-weight:700;color:{tokens['accent']}">Comece sua jornada →</p>
</div>'''
    elements=[{'id':generate_id(),'type':'html','x':120,'y':100,'width':880,'height':650,'htmlContent':copy,'journeyRole':'course_cover_copy','style':{},'startTime':0,'animations':[]}]
    if image_url:
        elements.append({'id':generate_id(),'type':'image','x':1060,'y':80,'width':740,'height':660,
            'src':image_url,'content':image_url,'objectFit':'cover','journeyRole':'course_cover_image',
            'style':{'borderRadius':palette.get('cornerRadius','24px')},'startTime':0,'animations':[]})
    else:
        # A truthful offline fallback, not a broken URL or unrelated stock photo.
        graphic=f'''<div style="height:100%;display:grid;place-items:center;background:linear-gradient(145deg,{tokens['accent']}22,{tokens['accent']}55);border-radius:28px;padding:36px;box-sizing:border-box"><svg viewBox="0 0 640 440" role="img" aria-label="Ilustração de uma jornada de aprendizagem" style="width:100%;height:100%"><path d="M80 340C120 160 300 400 360 190S510 50 560 90" fill="none" stroke="{tokens['accent']}" stroke-width="12" stroke-dasharray="16 12"/><circle cx="80" cy="340" r="28" fill="{tokens['accent']}"/><circle cx="360" cy="190" r="28" fill="{tokens['accent']}"/><circle cx="560" cy="90" r="34" fill="{tokens['accent']}"/><path d="M180 80L275 105V240L180 215L85 240V105Z" fill="{tokens['card_bg']}" stroke="{tokens['accent']}" stroke-width="7"/><path d="M180 80V215" fill="none" stroke="{tokens['accent']}" stroke-width="5"/></svg></div>'''
        elements.append({'id':generate_id(),'type':'html','x':1060,'y':80,'width':740,'height':660,'htmlContent':graphic,'journeyRole':'course_cover_visual_fallback','style':{},'startTime':0,'animations':[]})
    return elements


def build_journey(modules,palette):
    from models import generate_id
    from services.ai_agent import _tokens
    tk=_tokens(palette)
    entries=''.join(f'<li style="display:flex;gap:20px;align-items:baseline;padding:22px;background:{tk["card_bg"]};border:1px solid {tk["card_border"]};border-radius:16px;color:{tk["text"]};font-size:23px;line-height:1.4"><strong style="color:{tk["accent"]};font-size:24px">{i+1:02d}</strong><span>{html.escape(str(name))}</span></li>' for i,name in enumerate(modules))
    document=f'''<div data-course-journey="1" style="box-sizing:border-box;width:100%;height:100%;overflow:auto;padding:20px;font-family:{tk['body']};color:{tk['text']}"><h1 style="font-family:{tk['heading']};font-size:48px;color:{tk['text']};margin:0 0 20px">Sua jornada de aprendizagem</h1><p style="font-size:24px;color:{tk['muted']};margin:0 0 28px">Explore os temas e avance para as atividades práticas.</p><ol style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;list-style:none;margin:0;padding:0">{entries}</ol></div>'''
    return {'id':generate_id(),'title':'Sua jornada de aprendizagem','contentType':'content','background':palette.get('contentBg','#fafaf9'),
            'width':1920,'height':820,'duration':5,'notes':'Visão geral dos módulos do curso.','audio':[],
            'transition':{'type':'fade','duration':.5},'elements':[{'id':generate_id(),'type':'html','x':100,'y':70,'width':1720,'height':680,'htmlContent':document,'style':{},'startTime':0,'animations':[]}]}
