"""Allowlisted embed normalization, without fetching or storing video files."""
import re
from urllib.parse import urlsplit, parse_qs, urlencode, urlunsplit


def assessment_video_link(raw):
    message = 'Use um link HTTPS de vídeo do YouTube, Vimeo ou Bunny Stream (não cole código HTML).'
    def invalid(): raise ValueError(message)
    if not isinstance(raw, str) or len(raw) > 4000 or re.search(r'[<>\\\x00-\x20]', raw.strip()): invalid()
    try:
        u = urlsplit(raw.strip())
        if u.scheme != 'https' or u.username or u.password or u.port not in (None,443): invalid()
    except ValueError:
        invalid()
    host, path, query = (u.hostname or '').lower(), u.path, parse_qs(u.query, keep_blank_values=True)
    def param(name): return query.get(name, [''])[0]
    if host in {'youtube.com','www.youtube.com','m.youtube.com','youtu.be','www.youtube-nocookie.com','youtube-nocookie.com'}:
        match = re.fullmatch(r'/(?:embed|shorts|live)/([\w-]+)/?', path)
        identifier = path[1:] if host == 'youtu.be' else param('v') if path == '/watch' else match[1] if match else ''
        if not re.fullmatch(r'[A-Za-z0-9_-]{11}', identifier): invalid()
        start = param('start') or param('t')
        suffix = '?' + urlencode({'start': start.rstrip('s')}) if re.fullmatch(r'\d+s?', start, re.ASCII) else ''
        return {'provider': 'YouTube', 'url': f'https://www.youtube-nocookie.com/embed/{identifier}{suffix}'}
    if host in {'vimeo.com','www.vimeo.com','player.vimeo.com'}:
        match = re.fullmatch(r'/(?:video/)?(\d+)(?:/([A-Za-z0-9]+))?/?', path, re.ASCII)
        if not match: invalid()
        private_hash = param('h') or match[2]
        if private_hash and not re.fullmatch(r'[A-Za-z0-9]+', private_hash): invalid()
        suffix = '?' + urlencode({'h': private_hash}) if private_hash else ''
        return {'provider': 'Vimeo', 'url': f'https://player.vimeo.com/video/{match[1]}{suffix}'}
    if host in {'iframe.mediadelivery.net','player.mediadelivery.net'}:
        match = re.fullmatch(r'/(?:embed|play)/(\d+)/([a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12})/?', path, re.ASCII)
        if not match: invalid()
        pairs = [(key,value) for key, values in query.items() if key != 'autoplay' for value in values]
        pairs.append(('autoplay','false'))
        return {'provider': 'Bunny Stream', 'url': urlunsplit(('https',host,f'/embed/{match[1]}/{match[2]}',urlencode(pairs),''))}
    invalid()
