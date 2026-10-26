"""Generate project-owned, persistent assessment support images."""
import asyncio
import io
import re
import uuid
from pathlib import Path


def image_prompt(question, project):
    # Omit alternatives and feedback so the visual does not expose the key.
    metadata = (project.get('course') or {}).get('metadata') or {}
    return (
        'Create one professional educational illustration for a Brazilian assessment. '
        'Landscape composition, concrete setting and objects specific to the question. '
        'Represent the situation, not the solution. Do not highlight the correct answer. '
        'No written words, labels, numbers, captions, logos or watermark. '
        'Uncluttered composition, good contrast. The question appears separately. '
        f'Course: {str(metadata.get("title") or project.get("name") or "")[:300]}. '
        f'Topic: {str(question.get("category") or "")[:140]}. '
        f'Title: {str(question.get("title") or "")[:300]}. '
        f'Situation: {str(question.get("prompt") or "")[:1800]}.'
    )


async def create_support_image(question, project, database, projects_dir):
    from PIL import Image
    from services.ai_agent import _openai_image_bytes
    from services.asset_store import store_asset_async
    project_id = str(project['id'])
    if not re.fullmatch(r'[A-Za-z0-9_-]+', project_id):
        raise ValueError('Identificador de projeto inválido')
    image_bytes = await asyncio.wait_for(_openai_image_bytes(image_prompt(question, project)), timeout=200)
    if not image_bytes:
        raise ValueError('O serviço não retornou uma imagem')
    with Image.open(io.BytesIO(image_bytes)) as source:
        source.load()
        output = io.BytesIO()
        source.convert('RGB').save(output, format='PNG')
    filename = f'assessment_{uuid.uuid4().hex}.png'
    folder = Path(projects_dir) / project_id / 'assets'
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / filename
    path.write_bytes(output.getvalue())
    if not await store_asset_async(database, project_id, filename, str(path)):
        raise ValueError('Não foi possível persistir a imagem no projeto')
    return {'url': f'/api/projects/{project_id}/assets/{filename}', 'kind': 'image',
            'name': 'Imagem de apoio · ' + str(question.get('title') or 'Questão')[:180]}
