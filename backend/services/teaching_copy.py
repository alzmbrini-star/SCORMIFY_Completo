"""Keep instructional copy separate from image-generation metadata."""
import html
import re

_MARKER = re.compile(r'\[IMG:([^\]]*)\]', re.I | re.S)
_ASSET = re.compile(r'[A-Za-z0-9_.-]+\.(?:png|jpe?g|gif|webp|svg)', re.I)


def visible_teaching_text(value):
    """Read visible prose for fallback/media use, never implementation comments.

    This does not rewrite authored HTML or code examples in the original slide.
    Code blocks are not suitable source copy for replacement concept cards.
    """
    value=clean_image_instructions(value)
    value=re.sub(r'<!--.*?-->', ' ', value, flags=re.S)
    value=re.sub(r'<(script|style|template|noscript|pre|code)\b[^>]*>[\s\S]*?</\1\s*>', ' ', value, flags=re.I)
    value=html.unescape(re.sub(r'<[^>]+>', ' ', value))
    value=re.sub(r'/\*[\s\S]*?\*/', ' ', value)
    value=re.sub(r'<!--.*?-->', ' ', value, flags=re.S)
    return re.sub(r'\s+', ' ', value).strip()


def clean_image_instructions(value):
    if not isinstance(value,str): return ''
    # File markers from source documents remain intact for the asset migrator.
    return _MARKER.sub(lambda m:m.group(0) if _ASSET.fullmatch(m.group(1).strip()) else '', value)


def lesson_html(slide):
    """Compose all teaching blocks in order; an image must never overwrite them."""
    prompts={html.unescape(str(slide.get(k) or '')).strip() for k in ('imageKeywords','requiredImagePrompt')}
    blocks=[]
    for element in slide.get('elements') or []:
        if not isinstance(element,dict) or element.get('type','text') not in ('text','html'):
            continue
        value=element.get('content') or element.get('htmlContent') or ''
        clean=clean_image_instructions(value)
        plain=html.unescape(re.sub(r'<[^>]+>',' ',clean)).strip()
        if not plain or plain in prompts: continue
        blocks.append(clean)
    return '\n'.join(blocks)


def validate_lesson(slide):
    if slide.get('type')!='content' or slide.get('sourceImageOnly'):return
    raw=lesson_html(slide)
    clean=re.sub(r'<(?:script|style)\b[^>]*>[\s\S]*?</(?:script|style)>',' ',raw,flags=re.I)
    clean=_MARKER.sub('',clean)
    plain=html.unescape(re.sub(r'<[^>]+>',' ',clean))
    words=re.findall(r'\b[\wÀ-ÿ]+\b',plain)
    if len(words)<12:
        raise ValueError('CONTEUDO_DIDATICO_AUSENTE: escreva a explicação do assunto em elements de texto; descrições de imagem pertencem somente a imageKeywords. Não use [IMG:prompt] nem apenas título ou marcador de arquivo como conteúdo.')
