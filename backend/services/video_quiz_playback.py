"""Playback status only. Upgrade saved activities without touching their data."""
import re
from pathlib import Path


def _feedback_layout(document):
    if 'id="video-quiz-feedback-v1"' in document:
        return document
    runtime = (Path(__file__).parent / 'export_assets/video-quiz-feedback.js').read_text(encoding='utf-8')
    snippet = '<script id="video-quiz-feedback-v1">' + runtime + '</script>'
    end = re.search(r'</body>', document, re.I)
    return document[:end.start()] + snippet + document[end.start():] if end else document + snippet


def upgrade_video_quiz_playback(document):
    if not isinstance(document, str) or not re.search(r'id=[\"\']video-quiz-data[\"\']', document):
        return document
    if 'id="video-quiz-runtime-v2"' not in document:
        runtime = (Path(__file__).parent / 'export_assets/video-quiz.js').read_text(encoding='utf-8')
        def upgrade(match):
            # Replace only the known controlled player, never arbitrary author JS.
            if "const storeKey = 'scormify-video-quiz:'" in match[2] and 'const progress = config.checkpoints.map' in match[2]:
                return '<script id="video-quiz-runtime-v2">' + runtime + '</script>'
            return match[0]
        document = re.sub(r'(<script\b[^>]*>)([\s\S]*?)(</script>)', upgrade, document, flags=re.I)
    if 'id="video-quiz-playback-v2"' in document:
        return _feedback_layout(document)
    document = re.sub(r'<script\b[^>]*\bid=[\"\']video-quiz-playback-v1[\"\'][^>]*>[\s\S]*?</script>', '', document, flags=re.I)
    runtime = (Path(__file__).parent / 'export_assets/video-quiz-playback.js').read_text(encoding='utf-8')
    snippet = '<script id="video-quiz-playback-v2">' + runtime + '</script>'
    end = re.search(r'</body>', document, re.I)
    upgraded = document[:end.start()] + snippet + document[end.start():] if end else document + snippet
    return _feedback_layout(upgraded)


def refresh_video_quiz_documents(project):
    for slide in ((project or {}).get('course') or {}).get('slides',[]) or []:
        for element in slide.get('elements',[]):
            if element.get('type')=='html' and isinstance(element.get('htmlContent'),str) and 'video-quiz-data' in element['htmlContent']:
                element['htmlContent']=upgrade_video_quiz_playback(element.get('htmlContent'))
    return project
