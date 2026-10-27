"""Render a bank snapshot using the same player as the manual builder."""
import json
import os
from pathlib import Path
import uuid
import re
from services.editorial_text_colors import apply_editorial_text_colors


def refresh_assessment_documents(project):
    """Use the current controlled player with the saved question snapshot.

    Read-time only; no question-bank resampling and no database migration.
    """
    if not project:
        return project
    template = None
    for slide in (project.get('course') or {}).get('slides', []):
        for element in slide.get('elements', []):
            config = element.get('assessmentConfig')
            if element.get('type') != 'html' or not isinstance(config, dict):
                continue
            if not isinstance(config.get('questions'), list):
                match = re.search(r'<script\b[^>]*\bid=["\']assessment-data["\'][^>]*>([\s\S]*?)</script>', str(element.get('htmlContent') or ''), re.I)
                try:
                    snapshot = json.loads(match.group(1)) if match else None
                except (ValueError, TypeError):
                    snapshot = None
                if not isinstance(snapshot, dict) or not isinstance(snapshot.get('questions'), list):
                    continue
                config = dict(snapshot, **config)
                config['questions'] = snapshot['questions']
            if template is None:
                template = (Path(__file__).parent / 'export_assets' / 'assessment-player.html').read_text(encoding='utf-8')
            document = template.replace('__ASSESSMENT_DATA__', json.dumps(config, ensure_ascii=False).replace('<', '\\u003c'))
            element['htmlContent'] = apply_editorial_text_colors(document, config.get('textColors'))
    return project


def assessment_element(questions, title='Avaliação', allow_skip=True, width=960, height=540):
    config = {'title': title, 'allowSkip': allow_skip, 'questions': questions,
              'assetBase': os.environ.get('PUBLIC_BACKEND_URL') or os.environ.get('RENDER_EXTERNAL_URL') or ''}
    template = (Path(__file__).parent / 'export_assets' / 'assessment-player.html').read_text(encoding='utf-8')
    document = template.replace('__ASSESSMENT_DATA__', json.dumps(config, ensure_ascii=False).replace('<', '\\u003c'))
    return {'id': str(uuid.uuid4()), 'type': 'html', 'x': 0, 'y': 0, 'width': width, 'height': height,
            'htmlContent': document, 'htmlDisplayMode': 'fit', 'objectFit': 'cover', 'startTime': 0,
            'assessmentConfig': config}
