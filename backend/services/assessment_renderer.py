"""Render a bank snapshot using the same player as the manual builder."""
import json
import os
from pathlib import Path
import uuid


def assessment_element(questions, title='Avaliação', allow_skip=True, width=960, height=540):
    config = {'title': title, 'allowSkip': allow_skip, 'questions': questions,
              'assetBase': os.environ.get('PUBLIC_BACKEND_URL') or os.environ.get('RENDER_EXTERNAL_URL') or ''}
    template = (Path(__file__).parent / 'export_assets' / 'assessment-player.html').read_text(encoding='utf-8')
    document = template.replace('__ASSESSMENT_DATA__', json.dumps(config, ensure_ascii=False).replace('<', '\\u003c'))
    return {'id': str(uuid.uuid4()), 'type': 'html', 'x': 0, 'y': 0, 'width': width, 'height': height,
            'htmlContent': document, 'htmlDisplayMode': 'fit', 'objectFit': 'cover', 'startTime': 0,
            'assessmentConfig': config}
