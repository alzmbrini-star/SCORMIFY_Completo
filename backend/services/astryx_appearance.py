"""Local, deterministic Astryx appearance. Never regenerates authored content."""
import copy
import json
import re
from html import escape
from pydantic import BaseModel, ConfigDict, field_validator
from typing import Literal

STYLES = [
    {'id':'clean','name':'Essencial','description':'Equilíbrio entre texto e imagem, com cartões suaves.'},
    {'id':'editorial','name':'Editorial','description':'Títulos com serifa e composição de revista.'},
    {'id':'corporate','name':'Corporativo','description':'Linhas retas, bordas e hierarquia objetiva.'},
    {'id':'soft','name':'Acolhedor','description':'Cantos arredondados e fundos delicados.'},
]
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
    style: Literal['clean','editorial','corporate','soft'] = 'clean'
    palette: Literal['blue','teal','violet','amber','rose','graphite'] = 'blue'
    customAccent: str = ''
    captions: bool = False

    @field_validator('customAccent')
    @classmethod
    def color(cls, value):
        if value and not re.fullmatch(r'#[0-9a-fA-F]{6}', value):
            raise ValueError('Use uma cor hexadecimal com seis dígitos, como #315AD1.')
        return value.lower()

def normalize(value=None):
    return Appearance.model_validate(value or {}).model_dump()

def catalog():
    return {'styles':copy.deepcopy(STYLES),'palettes':copy.deepcopy(PALETTES),'defaults':normalize()}

def luminance(color):
    channels=[int(color[i:i+2],16)/255 for i in (1,3,5)]
    return sum((c/12.92 if c<=.04045 else ((c+.055)/1.055)**2.4)*w for c,w in zip(channels,(.2126,.7152,.0722)))

def appearance_css(value=None):
    opt=normalize(value)
    preset=next(p for p in PALETTES if p['id']==opt['palette'])
    requested=opt['customAccent'] or preset['accent']
    # Accent is also used for small text. Darken very bright custom colors until
    # contrast against white and the chosen background is at least 4.5:1.
    accent=requested
    while (luminance(preset['background'])+.05)/(luminance(accent)+.05)<4.5:
        accent='#'+''.join(f'{int(int(accent[i:i+2],16)*.9):02x}' for i in (1,3,5))
    radius={'clean':'24px','editorial':'8px','corporate':'4px','soft':'32px'}[opt['style']]
    css=f''':root{{--ax-accent:{accent};--ax-ink:#172744;--ax-appearance-bg:{preset['background']}}}
html body{{background:var(--ax-appearance-bg)!important}}
[data-astryx-theme]{{--color-primary:var(--ax-accent);--color-background-body:var(--ax-appearance-bg)}}
.ax-page .astryx-card{{border-radius:{radius}!important;background:#fff;border:1px solid #c4cfdf;overflow:hidden}}
.ax-page h1,.ax-page h2{{color:#172744}}
.ax-kicker,.ax-rule{{color:var(--ax-accent)}}.ax-rule{{background:var(--ax-accent)}}
.ax-page figcaption{{display:{'block' if opt['captions'] else 'none'}!important}}
.ax-page img{{object-fit:contain}}'''
    if opt['style']=='editorial':
        css+='.ax-page h1,.ax-page h2{font-family:Georgia,serif!important;font-weight:600!important;letter-spacing:-.02em}.ax-rule{width:110px;height:3px}.ax-page .astryx-card{box-shadow:none!important}.ax-grid{gap:clamp(22px,5vw,72px)}'
    elif opt['style']=='corporate':
        css+='.ax-page .astryx-card{border-top:5px solid var(--ax-accent)!important;box-shadow:none!important}.ax-rule{width:100%;height:2px}.ax-kicker{border-left:4px solid var(--ax-accent);padding-left:12px}'
    elif opt['style']=='soft':
        css+='.ax-page .astryx-card{box-shadow:0 12px 30px #17274414!important}.ax-page img{border-radius:24px}.ax-rule{width:84px;height:8px}.ax-kicker{display:inline-block;border-radius:99px;background:#fff;padding:8px 14px}'
    return css

def style_document(document, value=None):
    """Only own CSS/metadata changes. All scripts, image alt and teaching copy stay."""
    opt=normalize(value)
    document=re.sub(r'<style id="astryx-appearance-v1">[\s\S]*?</style>', '', document, flags=re.I)
    document=re.sub(r'<script id="astryx-appearance-data" type="application/json">[\s\S]*?</script>', '', document, flags=re.I)
    snippet='<style id="astryx-appearance-v1">'+appearance_css(opt)+'</style>'
    snippet+='<script id="astryx-appearance-data" type="application/json">'+json.dumps(opt).replace('<','\\u003c')+'</script>'
    return re.sub(r'</head\s*>',lambda m:snippet+m[0],document,count=1,flags=re.I) if re.search(r'</head\s*>',document,re.I) else snippet+document

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
