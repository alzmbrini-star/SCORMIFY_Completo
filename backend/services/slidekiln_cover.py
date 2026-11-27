"""Passive first-slide derivatives. No provider calls or course writes."""
import base64
import html
import io
import re
from html.parser import HTMLParser

VERSION = 'v2'
MAX_COVER = 12 * 1024 * 1024
_VOID = {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}
_BLOCKED = {'script','iframe','object','embed','form','input','textarea','select','audio','video','link','meta','base'}


def _css(value):
    # Only embedded resources; never fetch external fonts/images for a thumbnail.
    value = re.sub(r'@import\s+[^;]+;', '', value, flags=re.I)
    return re.sub(r'url\(\s*([\'\"]?)(.*?)\1\s*\)',
                  lambda m: m[0] if m[2].strip().startswith(('data:', '#')) else 'url("")', value, flags=re.I|re.S)


def _image(value):
    if not value.startswith('data:image/') or ';base64,' not in value or len(value)<50000:
        return value
    try:
        from PIL import Image
        raw=base64.b64decode(value.split(',',1)[1],validate=True)
        with Image.open(io.BytesIO(raw)) as source:
            if source.width*source.height>16_000_000 or getattr(source,'is_animated',False):
                return value
            image=source.convert('RGBA' if 'A' in source.getbands() else 'RGB')
            image.thumbnail((640,640),Image.Resampling.LANCZOS)
            output=io.BytesIO();image.save(output,'WEBP',quality=90,method=3)
        if len(output.getvalue())<len(raw):
            return 'data:image/webp;base64,'+base64.b64encode(output.getvalue()).decode('ascii')
    except Exception:
        pass
    return value


class FirstSlide(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.head=False;self.style=False;self.styles=[];self.body=[]
        self.depth=0;self.blocked=0;self.done=False;self.width=1280;self.height=720

    def handle_starttag(self,tag,attrs):
        values=dict(attrs)
        if tag=='head':self.head=True
        if self.head and tag=='style':self.style=True
        if not self.depth:
            if values.get('id')=='stage':
                for key in ('width','height'):
                    try:
                        value=float(values.get('data-w' if key=='width' else 'data-h',0))
                        if 1<=value<=16000:setattr(self,key,value)
                    except (TypeError,ValueError):pass
            if self.done or tag!='section' or 'slide' not in values.get('class','').split():return
            self.depth=1
        elif tag not in _VOID:
            self.depth+=1
        if tag in _BLOCKED:
            if tag not in _VOID:self.blocked+=1
            return
        if self.blocked:return
        safe=[]
        for name,value in attrs:
            if value is None or name.startswith('on') or name in ('srcdoc','autofocus','autoplay','contenteditable'):continue
            if name in ('src','href','xlink:href'):
                if not value.startswith(('data:image/','#')):continue
                if name=='src':value=_image(value)
            if name=='style':value=_css(value)
            safe.append(name+'="'+html.escape(value,quote=True)+'"')
        self.body.append('<'+tag+(' '+' '.join(safe) if safe else '')+'>')

    def handle_startendtag(self,tag,attrs):
        self.handle_starttag(tag,attrs)
        if tag not in _VOID:self.handle_endtag(tag)

    def handle_endtag(self,tag):
        if tag=='head':self.head=False
        if tag=='style':self.style=False
        if not self.depth:return
        if not self.blocked and tag not in _BLOCKED:self.body.append('</'+tag+'>')
        if tag in _BLOCKED and tag not in _VOID:self.blocked=max(0,self.blocked-1)
        if tag not in _VOID:self.depth-=1
        if self.depth==0:self.done=True

    def handle_data(self,data):
        if self.head and self.style:self.styles.append(data)
        elif self.depth and not self.blocked:self.body.append(data)

    def handle_entityref(self,name):
        if self.depth and not self.blocked:self.body.append('&'+name+';')

    def handle_charref(self,name):
        if self.depth and not self.blocked:self.body.append('&#'+name+';')


def build_cover(path):
    parser=FirstSlide()
    with open(path,encoding='utf-8') as source:
        while block:=source.read(64*1024):
            parser.feed(block)
            if parser.done:break
    if not parser.done:parser.close()  # Flush deferred parsing of a large image tag.
    if not parser.done:raise ValueError('Primeiro slide indisponível no pacote convertido.')
    body=''.join(parser.body)
    css=''.join(parser.styles)
    family_pattern=r'''font-family\s*:\s*('[^']*'|"[^"]*"|[^;}"<>]+)'''
    families={m[1].strip().strip('\'"').casefold() for m in re.finditer(family_pattern,html.unescape(body),re.I)}
    def face(match):
        name=re.search(family_pattern,match[0],re.I)
        return match[0] if name and name[1].strip().strip('\'"').casefold() in families else ''
    css=_css(re.sub(r'@font-face\s*\{[^}]*\}',face,css,flags=re.I))
    from services.slidekiln_text import TEXT_FLIP_CSS
    css+=TEXT_FLIP_CSS.removeprefix('<style id="sk-readable-text-flips-v1">').removesuffix('</style>')
    csp="default-src 'none'; script-src 'none'; connect-src 'none'; frame-src 'none'; media-src 'none'; img-src data:; font-src data:; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"
    result='<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="'+csp+'"><style>'+css+'</style><style>html,body{margin:0!important;padding:0!important;overflow:hidden!important;width:100%!important;height:100%!important}.slide{display:block!important;visibility:visible!important;position:absolute!important;inset:0!important;width:100%!important;height:100%!important;opacity:1!important;transform:none!important}*,*::before,*::after{animation:none!important;transition:none!important}</style></head><body>'+body+'</body></html>'
    if len(result.encode('utf-8'))>MAX_COVER:raise ValueError('Capa excede o limite de prévia segura.')
    return {'html':result,'width':parser.width,'height':parser.height}
