import ast
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
import fitz
from PIL import Image
from services import pdf_extractor as pdf


class FaithfulQualityTests(unittest.IsolatedAsyncioTestCase):
    def test_bounded_pixel_budget_across_page_shapes(self):
        for width,height in [(1280,720),(612,792),(1920,820),(10000,100),(100,10000)]:
            scale=pdf.faithful_page_scale(width,height)
            w,h=math.ceil(width*scale),math.ceil(height*scale)
            self.assertLessEqual(max(w,h),2560)
            self.assertLessEqual(w*h,3_000_000)
            self.assertAlmostEqual((width*scale)/(height*scale),width/height)
        for width,height in [(0,3),(-1,20),(float('inf'),1),(1,float('nan'))]:
            with self.assertRaises(ValueError): pdf.faithful_page_scale(width,height)

    async def test_text_page_is_high_definition_lossless_png_not_old_jpeg(self):
        with tempfile.TemporaryDirectory() as folder:
            with fitz.open() as doc:
                page=doc.new_page(width=1280,height=720)
                for line in range(30): page.insert_text((30,30+line*20),'Texto pequeno e captura de interface para testar legibilidade.',fontsize=9)
                raw=doc.tobytes()
            with patch.object(pdf.asyncio,'sleep',new=AsyncMock()):
                result=await pdf.extract_pdf_faithful(raw,Path(folder))
            row=result['pages'][0]
            self.assertEqual(row['filename'],'pdf_page_1.png')
            with Image.open(Path(folder)/row['filename']) as image:
                self.assertEqual(image.format,'PNG')
                self.assertEqual(image.mode,'RGB')
                self.assertGreater(image.width,2200)
                self.assertGreater(image.height,1200)
                self.assertLessEqual(image.width*image.height,3_000_000)
            self.assertLess((Path(folder)/row['filename']).stat().st_size,10*1024*1024)
            self.assertIn('Texto pequeno',row['text'])

    def test_quality_not_degraded_by_compressed_source_file_weight(self):
        source=Path(pdf.__file__).read_text(encoding='utf8')
        tree=ast.parse(source)
        render=next(n for n in tree.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='extract_pdf_faithful')
        body=ast.get_source_segment(source,render)
        self.assertNotIn('_pick_render_params',body)
        self.assertNotIn('jpg_quality',body)
        self.assertIn('faithful_page_scale(src_w, src_h)',body)

    def test_tutor_explains_quality_and_existing_courses(self):
        from services.creator_guide import GUIDE
        text=' '.join(next(g for g in GUIDE if g['id']=='agent-faithful')['steps'])
        for phrase in ['PNG sem perdas','2.560','3 milhões','criando outra cópia','Não usa créditos de IA']:
            self.assertIn(phrase,text)
