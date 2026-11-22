"""Opt-in Astryx design for NEW Agent lessons; never rewrites saved courses.

No subject-specific copy or AI calls. Assessment/activity players remain native.
Uses the pinned, offline Astryx Theme/Card assets shared with the laboratory.
"""
import html
import re
from functools import lru_cache
from html.parser import HTMLParser
from urllib.parse import urlsplit

from services.astryx_prototype import assets, CSS, ASSETS
from services.teaching_copy import lesson_html
from services.astryx_appearance import normalize, style_document

TEMPLATE = {
    'id': 'astryx', 'name': 'Astryx',
    'description': 'Layout responsivo para novos cursos, com cartões, imagens proporcionais e hierarquia visual',
    'preview': 'linear-gradient(135deg, #f4f7fc, #dbe7ff)', 'mode': 'light',
    'palette': {'primary': '#172744', 'accent': '#315ad1', 'accentLight': '#e9f1ff',
                'contentBg': '#f4f7fc', 'coverBg': '#f4f7fc', 'text': '#172744'},
    'fonts': {'heading': 'Arial, Helvetica, sans-serif', 'body': 'Arial, Helvetica, sans-serif'},
    'headerStyle': 'clean', 'cornerRadius': '24px', 'creationOnly': True,
}


@lru_cache(maxsize=1)
def lesson_styles():
    return (ASSETS/'lesson.css').read_text(encoding='utf-8')


def teaching_text(element):
    """Read the current document after manual edits; never narrate vendor CSS."""
    document = str(element.get('htmlContent') or '')
    document = re.sub(r'<head\b[^>]*>[\s\S]*?</head\s*>', ' ', document, flags=re.I)
    document = re.sub(r'<(?:script|style|template)\b[^>]*>[\s\S]*?</(?:script|style|template)\s*>', ' ', document, flags=re.I)
    document = re.sub(r'<!--[\s\S]*?-->', ' ', document)
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', document))).strip()


def append_source_image(slide, project_id, filename, caption=''):
    """PDF post-processing: add source images in flow, never over teaching copy."""
    target = next((e for e in slide.get('elements',[]) if e.get('astryxDesign')), None)
    if not target or not re.fullmatch(r'[A-Za-z0-9_.-]+\.(?:png|jpe?g|webp|gif)', filename, re.I):
        return False
    uri = f'/api/projects/{project_id}/assets/{filename}'
    sources = target.setdefault('astryxSourceImages', [])
    if uri in sources or f'src="{html.escape(uri,quote=True)}"' in target['htmlContent']:
        return True
    label = str(caption or 'Imagem original do documento')
    figure = (f'<figure><img src="{html.escape(uri,quote=True)}" alt="{html.escape(label,quote=True)}">'
              f'<figcaption>{html.escape(label)}</figcaption></figure>')
    card = assets()[0]['card'].replace('@@CONTENT@@', figure)
    target['htmlContent'] = target['htmlContent'].replace('</main>', '<div class="ax-copy">'+card+'</div></main>', 1)
    sources.append(uri)
    target['astryxTeachingText'] = re.sub(r'\[IMG:'+re.escape(filename)+r'\]', '', target.get('astryxTeachingText',''))
    if caption:
        target['astryxTeachingText'] += '\n' + str(caption)
    return True


def safe_url(value):
    value = str(value or '').strip()
    if not value or any(ord(c) < 32 for c in value):
        return ''
    try:
        parsed = urlsplit(value)
    except ValueError:
        return ''
    if parsed.scheme in ('http', 'https') and parsed.netloc:
        return value
    if value.startswith(('/api/', 'assets/', '#')):
        return value
    if re.match(r'^data:image/(?:png|jpeg|gif|webp|svg\+xml);base64,[A-Za-z0-9+/=]+$', value):
        return value
    return ''


class Copy(HTMLParser):
    """Retain semantic copy, lists, tables, code examples and source images.

    Model-authored absolute positions/inline font sizes cannot defeat the layout.
    User scripts/forms are not accepted here: interactive lessons bypass adapter.
    """
    allowed = {'h1','h2','h3','h4','h5','h6','p','ul','ol','li','strong','b','em','i','u',
               'br','div','span','table','thead','tbody','tfoot','tr','th','td','caption',
               'pre','code','blockquote','dl','dt','dd','figure','figcaption','img','a','hr','sub','sup'}
    void = {'img', 'br', 'hr'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.suppressed = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script','style','template','noscript'):
            self.suppressed += 1
        if self.suppressed or tag not in self.allowed:
            return
        attrs = dict(attrs)
        extra = ''
        if tag == 'img':
            src = safe_url(attrs.get('src'))
            if not src:
                return
            extra = f' src="{html.escape(src, quote=True)}" alt="{html.escape(attrs.get("alt") or "Imagem do material original", quote=True)}"'
        elif tag == 'a':
            href = safe_url(attrs.get('href'))
            if href:
                extra = f' href="{html.escape(href, quote=True)}" target="_blank" rel="noopener noreferrer"'
        elif tag in ('td','th'):
            for name in ('colspan','rowspan'):
                if re.fullmatch(r'[1-9][0-9]?', str(attrs.get(name) or '')):
                    extra += f' {name}="{attrs[name]}"'
        # A lesson has one authoritative page heading.
        self.parts.append(f'<{"h2" if tag == "h1" else tag}{extra}>')

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.void:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag in ('script','style','template','noscript'):
            self.suppressed = max(0, self.suppressed - 1)
        elif not self.suppressed and tag in self.allowed and tag not in self.void:
            self.parts.append(f'</{"h2" if tag == "h1" else tag}>')

    def handle_data(self, data):
        if not self.suppressed:
            self.parts.append(html.escape(data))


def compatible(slide):
    if slide.get('sourceImageOnly') or slide.get('guidedActivity') or slide.get('assessmentActivity'):
        return False
    raw = '\n'.join(str(e.get('htmlContent') or e.get('content') or '') for e in slide.get('elements',[]) if isinstance(e,dict))
    # Preserve an authored app/diagram rather than flattening it into text.
    return not re.search(r'<(?:script|iframe|button|input|form|canvas|svg|video|audio)\b|\b(?:onclick|data-sim-engine)\s*=', raw, re.I)


def readable_color(value, fallback):
    if not re.fullmatch(r'#[0-9a-fA-F]{6}', str(value or '')):
        return fallback
    rgb = [int(value[i:i+2],16)/255 for i in (1,3,5)]
    linear = [v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in rgb]
    luminance = sum(v*w for v,w in zip(linear,(.2126,.7152,.0722)))
    return value if luminance < .16 else fallback


EXTRA_CSS = '''
.ax-agent .ax-copy{color:var(--ax-ink);font-size:inherit;line-height:1.65;white-space:pre-line}
.ax-agent .ax-copy p,.ax-agent .ax-copy li{font-size:inherit;line-height:inherit;color:inherit}
.ax-agent .ax-copy h2{font-size:clamp(23px,2.6vw,32px);margin:24px 0 16px;color:var(--ax-ink)}
.ax-agent .ax-copy h3,.ax-agent .ax-copy h4{font-size:clamp(20px,2vw,26px);line-height:1.4;margin:20px 0 12px;color:var(--ax-ink)}
.ax-agent .ax-copy ul,.ax-agent .ax-copy ol{padding-left:26px;margin:16px 0;list-style-position:outside}
.ax-agent .ax-copy ul{list-style-type:disc}.ax-agent .ax-copy ol{list-style-type:decimal}.ax-agent .ax-copy li{margin:12px 0}
.ax-agent .ax-copy table{display:block;overflow:auto;max-width:100%;border-collapse:collapse;background:white;font-size:17px;white-space:normal}
.ax-agent .ax-copy th,.ax-agent .ax-copy td{padding:12px;border:1px solid #bccbe0;text-align:left;min-width:120px;color:#172744}
.ax-agent .ax-copy pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#e7edf7;color:#172744;padding:16px;border-radius:12px}
.ax-agent .ax-copy code{font-size:.9em}.ax-agent .ax-copy a{color:var(--ax-accent);text-decoration:underline}
.ax-agent .ax-copy blockquote{border-left:4px solid var(--ax-accent);padding:12px 20px;background:#e9f1ff;color:#172744;margin:20px 0}
.ax-agent .ax-copy img{height:auto;max-height:none;object-fit:contain;margin:20px 0}
.ax-agent .ax-grid{align-items:start}.ax-agent .ax-page{color:var(--ax-ink)}
.ax-agent h1,.ax-agent h2,.ax-agent .ax-copy strong,.ax-agent .ax-copy b{color:var(--ax-ink)}
.ax-agent .ax-copy ul.ax-modules{font-size:18px;line-height:1.55}.ax-agent .ax-kicker{max-width:100%;white-space:normal}
@media(max-width:640px){.ax-agent .ax-page{font-size:17px}.ax-agent .ax-copy{font-size:17px}.ax-agent .ax-copy table{font-size:16px}}
'''


def build_elements(slide, palette, module='', image_url=None, course_title=None, modules=None):
    """Return a responsive lesson element, or None for protected authored apps."""
    if not compatible(slide):
        return None
    bits, _, license_text = assets()
    vendor_css = lesson_styles()
    raw = lesson_html(slide)
    parser = Copy()
    parser.feed(raw)
    parser.close()
    copy = ''.join(parser.parts)
    title = str(course_title or slide.get('title') or 'Aprendizagem')
    kind = 'cover' if course_title is not None else str(slide.get('type') or 'content')
    # Only validated literal colors enter CSS. Incompatible global choices cannot
    # inject styles or create invisible teaching copy on this light theme.
    accent = readable_color(palette.get('accent'), '#315ad1')
    ink = readable_color(palette.get('text'), '#172744')
    scale = max(.8, min(1.5, float(palette.get('astryxFontScale') or 1)))
    scale_css = f'.ax-agent .ax-page{{font-size:clamp(17px,{1.65*scale:.2f}vw,{max(17,22*scale):.2f}px)}}'
    safe = html.escape
    h = 'h1' if kind == 'cover' else 'h2'
    copy = f'<{h}>{safe(title)}</{h}><div class="ax-rule"></div><div class="ax-copy">{copy}</div>'
    if modules:
        # Never silently truncate long module names or lists.
        copy += '<div class="ax-copy"><ul class="ax-modules">' + ''.join(f'<li>{safe(str(m))}</li>' for m in modules) + '</ul></div>'
    image = safe_url(image_url)
    if image:
        alt = safe(str(slide.get('imageAlt') or slide.get('title') or title), quote=True)
        figure = bits['card'].replace('@@CONTENT@@', f'<figure><img src="{safe(image,quote=True)}" alt="{alt}"><figcaption>{alt}</figcaption></figure>')
        copy = f'<div class="ax-grid"><section>{copy}</section>{figure}</div>'
    body = (f'<main class="ax-page" data-astryx-lesson="1" data-astryx-kind="{safe(kind,quote=True)}">'
            f'<p class="ax-kicker">{safe(str(module or "Aprendizagem aplicada"))}</p>{copy}</main>')
    root = bits['root'].replace('@@CONTENT@@', f'<div class="ax-agent">{body}</div>')
    document = (f'<!doctype html><html lang="pt-BR" data-theme="light"><head><meta charset="utf-8">'
                f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{safe(title)}</title>'
                f'<style>{vendor_css}\n:root{{--ax-accent:{accent};--ax-ink:{ink}}}\n{CSS}\n{EXTRA_CSS}\n{scale_css}</style></head><body>'
                f'<!-- Astryx 0.7.16 / MIT\n{license_text} -->{root}</body></html>')
    appearance = normalize(palette.get('astryxAppearance'))
    document = style_document(document, appearance)
    from services.astryx_viewport import upgrade_astryx_viewport
    document = upgrade_astryx_viewport(document)
    from models import generate_id
    from services.teaching_copy import visible_teaching_text
    return [{'id':generate_id(),'type':'html','x':0,'y':0,'width':1920,'height':820,
             'htmlContent':document,'htmlDisplayMode':'scroll','astryxDesign':True,
             'astryxAppearance':appearance,
             'astryxTeachingText':title + '\n' + re.sub(r'\[IMG:[^\]]+\]', '', visible_teaching_text(raw)) + ('\n' + '\n'.join(str(m) for m in modules) if modules else ''),
             'style':{},'startTime':0,'animations':[]}]
