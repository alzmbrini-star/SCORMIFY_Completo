import ast
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace
import fitz
from PIL import Image
from services import pdf_extractor as pdf


class FaithfulQualityTests(unittest.IsolatedAsyncioTestCase):
    def test_isolated_worker_memory_fallback_preserves_png(self):
        with patch.object(pdf.subprocess,'run',side_effect=[SimpleNamespace(returncode=2),SimpleNamespace(returncode=0,stdout='{"text":"ok","width":1600,"height":900}')]) as run:
            self.assertEqual(pdf._faithful_isolated_page(Path('source.pdf'),2,Path('page.png')),'ok')
            self.assertEqual([call.args[0][-1] for call in run.call_args_list],['3000000','1500000'])
            self.assertTrue(all(call.kwargs['timeout']==90 for call in run.call_args_list))
            self.assertTrue(all(call.args[0][-2]=='page.png' for call in run.call_args_list))

    async def test_isolated_real_page_returns_text_and_png(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'source.pdf'; target=Path(folder)/'page.png'
            with fitz.open() as doc:
                doc.new_page().insert_text((30,50),'Texto preservado em processo isolado')
                doc.save(source)
            self.assertIn('Texto preservado',pdf._faithful_isolated_page(source,0,target))
            with Image.open(target) as image:
                self.assertEqual(image.format,'PNG'); self.assertGreater(image.height,1800)

    async def test_stale_processing_after_restart_is_not_cached_forever(self):
        from datetime import datetime,timezone,timedelta
        from fastapi import HTTPException
        import asyncio
        source=(Path(pdf.__file__).parents[1]/'routes/pdf_import.py').read_text(encoding='utf8')
        fn=next(n for n in ast.parse(source).body if isinstance(n,ast.AsyncFunctionDef) and n.name=='get_faithful_status')
        fn.decorator_list=[]
        saved={'faithfulStatus':{'status':'processing','progress':10},'updatedAt':(datetime.now(timezone.utc)-timedelta(minutes=10)).isoformat()}
        cache={}; set_cache=AsyncMock()
        scope={'Depends':lambda _:None,'require_auth':None,'asyncio':asyncio,'datetime':datetime,'timezone':timezone,
               'HTTPException':HTTPException,'db':SimpleNamespace(projects=SimpleNamespace(find_one=AsyncMock(return_value=saved))),
               '_FAITHFUL_STATUS_CACHE':cache,'_faithful_set_cache':set_cache}
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'status','exec'),scope)
        result=await scope['get_faithful_status']('project',{})
        self.assertEqual(result['status'],'error'); self.assertIn('interrompida',result['message'])
        set_cache.assert_not_called()
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
