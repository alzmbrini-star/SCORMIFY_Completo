"""Playback status only. Upgrade saved activities without touching their data."""
import re
from pathlib import Path


def upgrade_video_quiz_playback(document):
    if not isinstance(document, str) or not re.search(r'id=[\"\']video-quiz-data[\"\']', document) or 'id="video-quiz-playback-v2"' in document:
        return document
    document = re.sub(r'<script\b[^>]*\bid=[\"\']video-quiz-playback-v1[\"\'][^>]*>[\s\S]*?</script>', '', document, flags=re.I)
    runtime = (Path(__file__).parent / 'export_assets/video-quiz-playback.js').read_text(encoding='utf-8')
    snippet = '<script id="video-quiz-playback-v2">' + runtime + '</script>'
    end = re.search(r'</body>', document, re.I)
    return document[:end.start()] + snippet + document[end.start():] if end else document + snippet
