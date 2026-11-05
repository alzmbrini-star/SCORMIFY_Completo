"""Allowlisted video URLs; iframe markup is data, never executable author HTML."""
import re
from html.parser import HTMLParser
from urllib.parse import urlsplit, parse_qs, urlencode, urlunsplit


def video_quiz_source(value):
    source = str(value or '').strip()
    if len(source) > 12000:
        raise ValueError('Link de vídeo muito longo.')
    if source.startswith('<'):
        class Frames(HTMLParser):
            def __init__(self):
                super().__init__(); self.sources = []
            def handle_starttag(self, tag, attrs):
                if tag == 'iframe':
                    self.sources.append(dict(attrs).get('src', ''))
        parser = Frames(); parser.feed(source)
        if len(parser.sources) != 1:
            raise ValueError('Cole a URL ou um único iframe de Bunny, Vimeo ou YouTube.')
        source = parser.sources[0].strip()
    source = re.sub('&amp;', '&', source, flags=re.I)
    u = urlsplit(source)
    if not source or not (u.scheme in ('https', 'http') and u.netloc or source.startswith('/api/')) or u.username or u.password:
        raise ValueError('Informe uma URL de vídeo válida.')
    host = (u.hostname or '').lower(); query = parse_qs(u.query); parts = u.path.strip('/').split('/')
    if host in ('youtube.com','www.youtube.com','m.youtube.com','youtube-nocookie.com','www.youtube-nocookie.com','youtu.be','www.youtu.be'):
        ident = parts[0] if host.endswith('youtu.be') else query.get('v', [''])[0] if u.path == '/watch' else parts[1] if len(parts) == 2 and parts[0] in ('embed','shorts','live') else ''
        if not re.fullmatch(r'[A-Za-z0-9_-]{11}', ident):
            raise ValueError('Link do YouTube inválido. Use o endereço de um vídeo, não de uma lista.')
        return 'https://www.youtube.com/embed/' + ident, 'youtube'
    if host in ('vimeo.com','www.vimeo.com','player.vimeo.com'):
        ident = parts[1] if len(parts) >= 2 and parts[0] == 'video' else parts[0]
        if not ident.isdigit():
            raise ValueError('Use o link do vídeo Vimeo ou o iframe do player.')
        secret = query.get('h', [''])[0] or (parts[1] if len(parts) == 2 and parts[0].isdigit() else '')
        if secret and not re.fullmatch(r'[A-Za-z0-9]+', secret):
            raise ValueError('Hash do vídeo Vimeo inválido.')
        return 'https://player.vimeo.com/video/' + ident + ('?' + urlencode({'h':secret}) if secret else ''), 'vimeo'
    if host == 'iframe.mediadelivery.net':
        if u.scheme != 'https':
            raise ValueError('Use um link HTTPS do Bunny Stream.')
        if len(parts) != 3 or parts[0] not in ('embed','play') or not parts[1].isdigit() or not re.fullmatch(r'[a-fA-F0-9-]{36}', parts[2]):
            raise ValueError('Use o link Embed ou iframe completo do Bunny Stream.')
        # Keep signed query parameters byte-for-byte, including token/expires.
        return source, 'bunny'
    if str(value or '').strip().startswith('<'):
        raise ValueError('Iframe permitido somente para Bunny, Vimeo ou YouTube.')
    return source, 'direct'
