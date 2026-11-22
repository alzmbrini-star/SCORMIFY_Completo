"""Local, deterministic Astryx appearance. Never regenerates authored content."""
import copy
import json
import re
from pydantic import BaseModel, ConfigDict, field_validator
from typing import Literal

STYLES = [
    {'id':'clean','name':'Essencial','description':'Equilíbrio entre texto e imagem, com cartões suaves.'},
    {'id':'editorial','name':'Editorial','description':'Títulos com serifa e composição de revista.'},
    {'id':'corporate','name':'Corporativo','description':'Linhas retas, bordas e hierarquia objetiva.'},
    {'id':'soft','name':'Acolhedor','description':'Cantos arredondados e fundos delicados.'},
    {'id':'focus','name':'Leitura focada','description':'Coluna única, leitura contínua e imagem ao final.'},
    {'id':'visual','name':'Destaque visual','description':'Mais espaço para a imagem, com texto ao lado.'},
    {'id':'journal','name':'Caderno','description':'Margem de destaque, texto amplo e imagem de apoio.'},
    {'id':'studio','name':'Estúdio','description':'Blocos equilibrados, molduras e títulos marcantes.'},
]
THEMES = [{'id':'light','name':'Claro'},{'id':'dark','name':'Escuro'},{'id':'midnight','name':'Azul-noturno'}]
TYPOGRAPHIES = [
    {'id':'auto','name':'Recomendada pelo estilo'},
    {'id':'sans','name':'Moderna · Arial / Helvetica'},
    {'id':'humanist','name':'Humanista · Trebuchet / Segoe UI'},
    {'id':'serif','name':'Editorial · Georgia'},
    {'id':'book','name':'Clássica · Palatino'},
    {'id':'technical','name':'Técnica · Consolas / Courier'},
]
FONTS = {'sans':'Arial,Helvetica,sans-serif','humanist':'"Trebuchet MS","Segoe UI",sans-serif',
         'serif':'Georgia,"Times New Roman",serif','book':'"Palatino Linotype",Palatino,Georgia,serif',
         'technical':'Consolas,"Courier New",monospace'}
PALETTES = [
    {'id':'blue','name':'Azul','accent':'#315ad1','background':'#f4f7fc'},
    {'id':'teal','name':'Verde-petróleo','accent':'#087e70','background':'#f0f8f6'},
    {'id':'violet','name':'Violeta','accent':'#6741c1','background':'#f7f3fc'},
    {'id':'amber','name':'Âmbar','accent':'#945000','background':'#fffbf2'},
    {'id':'rose','name':'Rosa','accent':'#aa2853','background':'#fff4f7'},
    {'id':'graphite','name':'Grafite','accent':'#364152','background':'#f5f6f8'},
]

class Appearance(BaseModel):
    model_config = ConfigDict(extra='forbid')
    style: Literal['clean','editorial','corporate','soft','focus','visual','journal','studio'] = 'clean'
    palette: Literal['blue','teal','violet','amber','rose','graphite'] = 'blue'
    customAccent: str = ''
    captions: bool = False
    theme: Literal['light','dark','midnight'] = 'light'
    typography: Literal['auto','sans','humanist','serif','book','technical'] = 'auto'

    @field_validator('customAccent')
    @classmethod
    def color(cls, value):
        if value and not re.fullmatch(r'#[0-9a-fA-F]{6}', value):
            raise ValueError('Use uma cor hexadecimal com seis dígitos, como #315AD1.')
        return value.lower()

def normalize(value=None):
    return Appearance.model_validate(value or {}).model_dump()

def catalog():
    return {'styles':copy.deepcopy(STYLES),'palettes':copy.deepcopy(PALETTES),
            'themes':copy.deepcopy(THEMES),'typographies':copy.deepcopy(TYPOGRAPHIES),'defaults':normalize()}

def luminance(color):
    channels=[int(color[i:i+2],16)/255 for i in (1,3,5)]
    return sum((c/12.92 if c<=.04045 else ((c+.055)/1.055)**2.4)*w for c,w in zip(channels,(.2126,.7152,.0722)))

def appearance_css(value=None):
    opt=normalize(value)
    preset=next(p for p in PALETTES if p['id']==opt['palette'])
    requested=opt['customAccent'] or preset['accent']
    dark = opt['theme'] != 'light'
    bg = preset['background'] if not dark else ('#121820' if opt['theme']=='dark' else '#0b1228')
    surface = '#ffffff' if not dark else ('#1c2633' if opt['theme']=='dark' else '#16213d')
    ink = '#172744' if not dark else '#edf3ff'
    muted = '#425575' if not dark else '#c1cee2'
    border = '#c4cfdf' if not dark else '#71839d'
    # Accent labels need >= 4.5:1 against BOTH the page and card backgrounds.
    accent=requested
    def contrast(a,b):return (max(luminance(a),luminance(b))+.05)/(min(luminance(a),luminance(b))+.05)
    for _ in range(80):
        if min(contrast(accent,bg),contrast(accent,surface))>=4.5:break
        accent='#'+''.join(f'{min(255,int(int(accent[i:i+2],16)*.9+26)) if dark else int(int(accent[i:i+2],16)*.9):02x}' for i in (1,3,5))
    radius={'clean':'24px','editorial':'8px','corporate':'4px','soft':'32px','focus':'14px','visual':'20px','journal':'4px','studio':'12px'}[opt['style']]
    font = opt['typography']
    if font=='auto':font={'editorial':'serif','journal':'book','soft':'humanist','studio':'humanist'}.get(opt['style'],'sans')
    css=f''':root{{--ax-accent:{accent};--ax-ink:{ink};--ax-appearance-bg:{bg};--ax-surface:{surface};--ax-muted:{muted};--ax-border:{border}}}
html{{color-scheme:{'dark' if dark else 'light'}!important}}html body{{background:var(--ax-appearance-bg)!important;color:var(--ax-ink)!important}}
[data-astryx-theme]{{--color-primary:var(--ax-accent);--color-background-body:var(--ax-appearance-bg);--color-background-card:var(--ax-surface);--color-text-primary:var(--ax-ink);--color-text-secondary:var(--ax-muted);--font-family:{FONTS[font]};--font-family-body:{FONTS[font]};--font-family-heading:{FONTS[font]}}}
.ax-page,.ax-page button,.ax-page input{{font-family:{FONTS[font]}!important}}
.ax-page h1,.ax-page h2,.ax-page h3,.ax-page h4{{font-family:{FONTS[font]}!important;color:var(--ax-ink)!important}}
.ax-page,.ax-agent .ax-page,.ax-agent .ax-copy,.ax-text p,.ax-agent .ax-copy strong,.ax-agent .ax-copy b{{color:var(--ax-ink)!important}}
.ax-page .astryx-card{{border-radius:{radius}!important;background:var(--ax-surface)!important;border:1px solid var(--ax-border);overflow:hidden}}
.ax-lead,.ax-page figcaption,.ax-page .ax-foot{{color:var(--ax-muted)!important}}
.ax-pill,.ax-objectives span,.ax-kicker,.ax-choice,.ax-agent .ax-copy pre,.ax-agent .ax-copy blockquote{{background:var(--ax-surface)!important;color:var(--ax-ink);border-color:var(--ax-border)}}
.ax-kicker,.ax-agent .ax-copy a{{color:var(--ax-accent)!important}}
.ax-choice{{color:var(--ax-ink)!important}}.ax-choice:has(input:checked){{outline:2px solid var(--ax-accent);background:var(--ax-surface)!important}}
.ax-page .astryx-button[data-variant=primary]{{background:var(--ax-accent)!important;color:{'#101828' if dark else '#ffffff'}!important}}
.ax-page .astryx-button[data-variant=secondary]{{background:var(--ax-surface)!important;color:var(--ax-ink)!important;border-color:var(--ax-border)}}
.ax-agent .ax-copy table,.ax-agent .ax-copy td,.ax-agent .ax-copy th{{background:var(--ax-surface)!important;color:var(--ax-ink)!important;border-color:var(--ax-border)}}
.ax-feedback{{background:var(--ax-surface)!important;color:var(--ax-ink)!important;border-left:4px solid var(--ax-accent)}}
.ax-kicker,.ax-rule{{color:var(--ax-accent)}}.ax-rule{{background:var(--ax-accent)}}
.ax-page figcaption{{display:{'block' if opt['captions'] else 'none'}!important}}
.ax-page img{{object-fit:contain}}'''
    if opt['style']=='editorial':
        css+='.ax-page h1,.ax-page h2{font-weight:600!important;letter-spacing:-.02em}.ax-rule{width:110px;height:3px}.ax-page .astryx-card{box-shadow:none!important}.ax-grid{gap:clamp(22px,5vw,72px)}'
    elif opt['style']=='corporate':
        css+='.ax-page .astryx-card{border-top:5px solid var(--ax-accent)!important;box-shadow:none!important}.ax-rule{width:100%;height:2px}.ax-kicker{border-left:4px solid var(--ax-accent);padding-left:12px}'
    elif opt['style']=='soft':
        css+='.ax-page .astryx-card{box-shadow:0 12px 30px #17274414!important}.ax-page img{border-radius:24px}.ax-rule{width:84px;height:8px}.ax-kicker{display:inline-block;border-radius:99px;background:#fff;padding:8px 14px}'
    elif opt['style']=='focus':
        css+='.ax-page{max-width:960px!important}.ax-grid{grid-template-columns:minmax(0,1fr)!important;gap:28px}.ax-page .astryx-card{max-width:760px;width:100%;margin-inline:auto}.ax-page h1,.ax-page h2{max-width:24ch}.ax-cover{min-height:0}'
    elif opt['style']=='visual':
        css+='.ax-grid{grid-template-columns:minmax(0,.85fr) minmax(0,1.4fr);gap:clamp(24px,4vw,48px)}.ax-page .astryx-card{padding:12px}.ax-page img{max-height:560px}.ax-page h1{font-size:clamp(30px,3.6vw,48px)}'
    elif opt['style']=='journal':
        css+='.ax-page{border-left:6px solid var(--ax-accent)}.ax-grid{grid-template-columns:minmax(0,1.25fr) minmax(0,.75fr)}.ax-rule{height:2px;width:100%}.ax-page .astryx-card{box-shadow:none!important}.ax-text p+p,.ax-copy p+p{border-top:1px solid var(--ax-border);padding-top:16px}'
    elif opt['style']=='studio':
        css+='.ax-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:24px}.ax-page .astryx-card{border:3px solid var(--ax-accent)!important;padding:12px}.ax-page h1,.ax-page h2{font-weight:800!important;letter-spacing:-.035em}.ax-rule{height:8px;width:120px}.ax-topline{border-bottom:2px solid var(--ax-accent);padding-bottom:18px}'
    css+='@media(max-width:700px){.ax-grid{grid-template-columns:minmax(0,1fr)!important;gap:24px}.ax-page{padding:24px 20px!important}.ax-page h1{font-size:clamp(28px,7vw,38px)!important}.ax-page h2{font-size:clamp(25px,6vw,32px)!important}.ax-topline{flex-wrap:wrap}.ax-page img{max-height:none}.ax-page .astryx-card{max-width:100%}}'
    return css

def style_document(document, value=None):
    """Only own CSS/metadata changes. All scripts, image alt and teaching copy stay."""
    opt=normalize(value)
    document=re.sub(r'<style id="astryx-appearance-v1">[\s\S]*?</style>', '', document, flags=re.I)
    document=re.sub(r'<script id="astryx-appearance-data" type="application/json">[\s\S]*?</script>', '', document, flags=re.I)
    snippet='<style id="astryx-appearance-v1">'+appearance_css(opt)+'</style>'
    snippet+='<script id="astryx-appearance-data" type="application/json">'+json.dumps(opt).replace('<','\\u003c')+'</script>'
    styled = re.sub(r'</head\s*>',lambda m:snippet+m[0],document,count=1,flags=re.I) if re.search(r'</head\s*>',document,re.I) else snippet+document
    from services.astryx_viewport import upgrade_astryx_viewport
    return upgrade_astryx_viewport(styled)

def eligible(element):
    raw=element.get('htmlContent')
    return element.get('type')=='html' and isinstance(raw,str) and bool(re.search(r'data-astryx-(?:lesson|slide)=',raw))

def appearance_plan(project, value):
    opt=normalize(value);patches={};previews=[]
    for i,slide in enumerate(project.get('course',{}).get('slides',[])):
        for j,element in enumerate(slide.get('elements',[])):
            if not eligible(element):continue
            raw=element['htmlContent'];fixed=style_document(raw,opt)
            if fixed!=raw:patches[f'course.slides.{i}.elements.{j}.htmlContent']=fixed
            previews.append({'slide':i+1,'title':slide.get('title',''),'html':fixed})
    if previews:patches['course.metadata.astryxAppearance']=opt
    return patches,previews
