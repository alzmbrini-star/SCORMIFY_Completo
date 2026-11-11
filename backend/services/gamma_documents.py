"""Bounded, local text extraction. No OCR, macros, network or paid generation."""
import io
import zipfile
from pathlib import PurePath

MAX_FILE = 20 * 1024 * 1024
MAX_TEXT = 100000
EXTENSIONS = {'.docx', '.pdf', '.pptx'}


class DocumentError(ValueError):
    pass


def extract_document(filename, raw):
    ext = PurePath(filename.replace('\\', '/')).suffix.lower()
    if ext not in EXTENSIONS:
        raise DocumentError('Use Word (.docx), PDF ou PowerPoint (.pptx). Para .doc ou .ppt antigos, salve uma cópia como .docx ou .pptx.')
    if not raw or len(raw) > MAX_FILE:
        raise DocumentError('Envie um arquivo não vazio de até 20 MB.')
    blocks, units, empty = [], 0, 0
    try:
        if ext in {'.docx', '.pptx'}:
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                entries = archive.infolist()
                if len(entries) > 10000 or sum(i.file_size for i in entries) > 80 * 1024 * 1024 or any(i.flag_bits & 1 for i in entries):
                    raise DocumentError('Documento protegido ou grande demais para extração segura.')
            if ext == '.docx':
                from docx import Document
                # Iterate the XML body to keep paragraphs and table cells in order.
                doc = Document(io.BytesIO(raw))
                for paragraph in doc.element.body.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'):
                    value = ''.join(
                        t.text or '' for t in paragraph.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t'))
                    if value.strip():
                        blocks.append(value.strip())
                units = 1
            else:
                from pptx import Presentation
                presentation = Presentation(io.BytesIO(raw))
                if len(presentation.slides) > 300:
                    raise DocumentError('Limite de 300 slides por arquivo.')
                def shape_text(shapes):
                    output = []
                    for shape in shapes:
                        if shape.has_text_frame:
                            output.append(shape.text)
                        if shape.has_table:
                            output.extend(' | '.join(cell.text for cell in row.cells) for row in shape.table.rows)
                        if hasattr(shape, 'shapes'):
                            output.extend(shape_text(shape.shapes))
                    return output
                for index, slide in enumerate(presentation.slides, 1):
                    value = '\n'.join(shape_text(slide.shapes)).strip()
                    empty += not bool(value)
                    blocks.append(f'[Slide {index}]\n{value or "[Sem texto extraível]"}')
                units = len(presentation.slides)
        else:
            import fitz
            with fitz.open(stream=raw, filetype='pdf') as document:
                if document.needs_pass:
                    raise DocumentError('O PDF está protegido por senha. Envie uma cópia desbloqueada.')
                if len(document) > 300:
                    raise DocumentError('Limite de 300 páginas por arquivo.')
                for index, page in enumerate(document, 1):
                    value = page.get_text(sort=True).strip()
                    empty += not bool(value)
                    blocks.append(f'[Página {index}]\n{value or "[Sem texto extraível]"}')
                units = len(document)
    except DocumentError:
        raise
    except Exception:
        raise DocumentError('Não foi possível ler o documento. Verifique o formato e se o arquivo abre normalmente, sem senha.') from None
    text = '\n\n'.join(blocks).strip()
    if not text or (units and empty == units) or len(text) < 20:
        raise DocumentError('Não foi encontrado texto suficiente. PDFs digitalizados e slides apenas com imagens precisam de OCR antes do envio. Nenhum conteúdo foi substituído.')
    if len(text) > MAX_TEXT:
        raise DocumentError('O texto excede 100.000 caracteres. Divida o documento em partes; nenhum trecho foi cortado ou enviado ao Gamma.')
    warning = 'Importação de texto: imagens, capturas, diagramação e animações originais não são importadas nesta opção. Revise antes de gerar.'
    if empty:
        warning += f' {empty} página(s)/slide(s) sem texto extraível; confira os trechos marcados. Não há OCR automático.'
    return {'text': text, 'characters': len(text), 'units': units, 'warning': warning}
