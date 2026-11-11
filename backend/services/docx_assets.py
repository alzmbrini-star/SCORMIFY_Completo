"""Native DOCX screenshots: exact bytes, durable assets and no AI redraw."""
import base64
import hashlib
import html
import io
import uuid

from PIL import Image
from services.source_coverage import docx_text


def extract_docx_source(raw):
    images = []
    total = 0
    def picture(part):
        nonlocal total
        blob = part.blob
        total += len(blob)
        if len(images) >= 150 or len(blob) > 10_000_000 or total > 60_000_000:
            raise ValueError('As imagens do DOCX excedem o limite de importação. Divida o documento; nenhuma captura foi descartada silenciosamente.')
        with Image.open(io.BytesIO(blob)) as image:
            width, height = image.size
            fmt = image.format
            if width * height > 40_000_000: raise ValueError('Uma captura do DOCX é grande demais. Reduza a resolução e reenvie.')
        extension = {'PNG':'png','JPEG':'jpg','WEBP':'webp','GIF':'gif'}.get(fmt)
        if not extension:
            raise ValueError('O DOCX contém uma imagem não suportada. Converta-a para PNG ou JPEG e reenvie.')
        name = f'docx_{len(images)+1:03}_{hashlib.sha256(blob).hexdigest()[:16]}.{extension}'
        images.append({'filename':name,'width':width,'height':height,'data':base64.b64encode(blob).decode('ascii'),
                       'content_type':Image.MIME.get(fmt,'image/png')})
        return '[IMG:'+name+']'
    return docx_text(raw, picture), images


async def save_source_images(db, images, owner_id, company_id):
    source_id = 'docximport_' + uuid.uuid4().hex
    for image in images:
        await db.project_assets.update_one({'project_id':source_id,'filename':image['filename']},
            {'$set':{**image,'project_id':source_id,'userId':owner_id,'companyId':company_id}}, upsert=True)
    return {'version':1,'assetProjectId':source_id,
            'images':[{k:v for k,v in image.items() if k not in ('data','content_type')} for image in images]}


async def copy_source_images(db, metadata, project_id):
    for image in metadata.get('images', []):
        asset = await db.project_assets.find_one({'project_id':metadata['assetProjectId'],'filename':image['filename']},{'_id':0})
        if not asset or not asset.get('data'):
            raise ValueError('Não foi possível recuperar uma captura original do DOCX. Reenvie o documento antes de gerar novamente.')
        await db.project_assets.update_one({'project_id':project_id,'filename':image['filename']},
            {'$set':{**asset,'project_id':project_id}}, upsert=True)


def reference_elements(slide, project_id):
    filename = slide['sourceImage']
    # Names are generated internally at extraction, never accepted as a path.
    import re
    if not re.fullmatch(r'docx_\d{3}_[a-f0-9]{16}\.(?:png|jpg|webp|gif)', filename):
        raise ValueError('Referência de captura DOCX inválida.')
    url = f'/api/projects/{project_id}/assets/{filename}'
    def ident(): return str(uuid.uuid4())
    elements = [
        {'id':ident(),'type':'html','x':60,'y':28,'width':1800,'height':65,
         'content':'<h2 style="margin:0;font:600 30px system-ui;color:#18354b">'+html.escape(slide['title'])+'</h2>', 'startTime':0},
        {'id':ident(),'type':'image','x':60,'y':105,'width':1800,'height':620,'src':url,'content':url,
         'objectFit':'contain','style':{'objectFit':'contain'},'startTime':0,'sourceDocumentImage':True},
        {'id':ident(),'type':'html','x':60,'y':747,'width':1800,'height':45,
         'content':'<p style="margin:0;font:22px system-ui;color:#31556e">Captura original do material de referência. Rótulos e permissões podem variar conforme o ambiente.</p>', 'startTime':0}
    ]
    for element in elements:
        if element['type'] == 'html':
            element['htmlContent'] = element['content']
    return elements


def repair_reference_html(course):
    """Recover only missing HTML fields on native DOCX reference slides."""
    changed = False
    for slide in course.get('slides', []):
        if not slide.get('sourceImageOnly'):
            continue
        for element in slide.get('elements', []):
            if (element.get('type') == 'html' and not element.get('htmlContent')
                    and isinstance(element.get('content'), str) and element['content']):
                element['htmlContent'] = element['content']
                changed = True
    return changed
