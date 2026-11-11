import io
import unittest
from unittest.mock import AsyncMock
from fastapi import HTTPException, UploadFile
from services.gamma_documents import extract_document, DocumentError, MAX_FILE
from tests.test_gamma import routes


class GammaDocumentTests(unittest.IsolatedAsyncioTestCase):
    def test_word_paragraph_table_order(self):
        from docx import Document
        doc = Document(); doc.add_paragraph('Introdução e objetivos do curso de planejamento.')
        doc.add_table(rows=1, cols=1).cell(0,0).text = 'Conteúdo da tabela preservado'
        doc.add_paragraph('Conclusão e próximos passos.')
        stream = io.BytesIO(); doc.save(stream)
        result = extract_document('ementa.DOCX', stream.getvalue())
        self.assertLess(result['text'].index('Introdução'), result['text'].index('tabela'))
        self.assertLess(result['text'].index('tabela'), result['text'].index('Conclusão'))
        self.assertIn('não são importadas', result['warning'])

    def test_pptx_order_and_empty_slide_notice(self):
        from pptx import Presentation
        from pptx.util import Inches
        prs=Presentation()
        for value in ['Primeiro conteúdo de apresentação', '', 'Último conteúdo para encerrar o tema']:
            slide=prs.slides.add_slide(prs.slide_layouts[6])
            if value: slide.shapes.add_textbox(0,0,Inches(4),Inches(1)).text=value
        stream=io.BytesIO(); prs.save(stream)
        result=extract_document('curso.pptx',stream.getvalue())
        self.assertEqual(result['units'],3)
        self.assertIn('[Slide 2]\n[Sem texto extraível]',result['text'])
        self.assertIn('1 página(s)/slide(s)',result['warning'])

    def test_pdf_text_and_scan_rejection(self):
        import fitz
        with fitz.open() as doc:
            doc.new_page().insert_text((50,50),'Conteudo completo de um PDF para o Gamma')
            self.assertIn('Conteudo completo',extract_document('curso.pdf',doc.tobytes())['text'])
        with fitz.open() as doc:
            doc.new_page()
            with self.assertRaisesRegex(DocumentError,'OCR'): extract_document('scan.pdf',doc.tobytes())

    def test_limits_corruption_and_legacy_are_actionable(self):
        for name,raw in [('x.doc',b'legacy'),('x.ppt',b'legacy'),('x.exe',b'bad'),('x.docx',b'bad'),('x.pdf',b''),('x.pdf',b'x'*(MAX_FILE+1))]:
            with self.assertRaises(DocumentError): extract_document(name,raw)
        from docx import Document
        doc=Document(); doc.add_paragraph('a'*100001); output=io.BytesIO(); doc.save(output)
        with self.assertRaisesRegex(DocumentError,'nenhum trecho foi cortado'): extract_document('grande.docx',output.getvalue())

    async def test_route_is_authorized_and_never_calls_gamma(self):
        file=UploadFile(filename='x.docx',file=io.BytesIO(b'bad'))
        with self.assertRaises(HTTPException) as ctx: await routes().extract_document(file,{'roles':['aprovador']})
        self.assertEqual(ctx.exception.status_code,403)
        file=UploadFile(filename='x.docx',file=io.BytesIO(b'bad'))
        with self.assertRaises(HTTPException) as ctx: await routes().extract_document(file,{'roles':['editor']})
        self.assertEqual(ctx.exception.status_code,422)
        self.assertTrue(file.file.closed)

    def test_model_accepts_full_source_without_ten_thousand_truncation(self):
        import uuid
        value='Fonte completa. '*2000
        self.assertEqual(routes().Generate(requestId=uuid.uuid4(),title='Curso',prompt=value).prompt,value)

    def test_tutor_documents_upload_and_limits(self):
        from services.creator_guide import GUIDE
        text=' '.join(next(g for g in GUIDE if g['id']=='gamma-create')['steps'])
        for term in ['.docx','.pptx','20 MB','OCR','100.000','Adicionar ao conteúdo']:
            self.assertIn(term,text)
