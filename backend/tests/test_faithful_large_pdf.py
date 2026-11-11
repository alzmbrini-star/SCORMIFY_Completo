import asyncio
import ast
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch
import fitz
from services.faithful_source import download_source, validate_source_size, MAX_SOURCE_BYTES, CHUNK_BYTES
from services import pdf_extractor


class SourceStream:
    def __init__(self,size,advertised=None,fail_after=None):
        self.length=size if advertised is None else advertised
        self.remaining=size; self.read_sizes=[]; self.close=AsyncMock(); self.fail_after=fail_after
    async def read(self,size):
        assert 0<size<=CHUNK_BYTES, 'Never read the whole original PDF'
        self.read_sizes.append(size)
        if self.fail_after and len(self.read_sizes)>self.fail_after: raise OSError('Interrupted')
        count=min(size,self.remaining); self.remaining-=count
        return b'x'*count


class FaithfulLargePdfTests(unittest.IsolatedAsyncioTestCase):
    async def test_motor_gridout_close_is_synchronous(self):
        stream=SourceStream(20); stream.close=Mock(return_value=None)
        path=await download_source(stream)
        try: stream.close.assert_called_once()
        finally: path.unlink()

    async def test_120mb_source_streams_to_disk_without_whole_file_allocation(self):
        stream=SourceStream(120*1024*1024)
        path=await download_source(stream)
        try:
            self.assertEqual(path.stat().st_size,120*1024*1024)
            self.assertGreater(len(stream.read_sizes),400)
            stream.close.assert_awaited_once()
        finally: path.unlink()

    async def test_size_guard_before_read_and_on_misreported_length(self):
        for stream in [SourceStream(MAX_SOURCE_BYTES+1),SourceStream(12,advertised=1)]:
            if stream.length==1:
                with patch('services.faithful_source.MAX_SOURCE_BYTES',10):
                    with self.assertRaises(ValueError): await download_source(stream)
            else:
                with self.assertRaisesRegex(ValueError,'300 MB'): await download_source(stream)
                self.assertEqual(stream.read_sizes,[])
            stream.close.assert_awaited_once()
        validate_source_size(120*1024*1024)
        validate_source_size(271*1024*1024)

    async def test_failed_download_cleans_temp_file(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch('services.faithful_source.tempfile.tempdir',folder):
                with self.assertRaises(OSError): await download_source(SourceStream(CHUNK_BYTES*3,fail_after=1))
            self.assertEqual(list(Path(folder).iterdir()),[])

    async def test_real_pdf_path_renders_every_page_and_persists_serially(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'source.pdf'; images=Path(folder)/'images'
            with fitz.open() as doc:
                for i in range(4): doc.new_page().insert_text((40,60),f'Pagina {i+1} do material original')
                doc.save(source)
            persisted=[]; progress=[]
            async def persist(page):
                self.assertEqual(page['page_num'],len(persisted)+1)
                self.assertEqual(len(list(images.glob('*.jpg'))),len(persisted)+1)
                persisted.append(page['page_num'])
            with patch.object(pdf_extractor.asyncio,'sleep',new=AsyncMock()):
                result=await pdf_extractor.extract_pdf_faithful(source,images,page_cb=persist,progress_cb=lambda pct,msg:progress.append(pct))
            self.assertEqual(persisted,[1,2,3,4]); self.assertEqual(result['total_pages'],4)
            self.assertEqual(progress[-1],1)
            self.assertTrue(all(s['backgroundImageFit']=='contain' for s in pdf_extractor.build_faithful_slides(result['pages'],'project')))

    async def test_asset_failure_is_terminal_not_a_missing_page_success(self):
        with tempfile.TemporaryDirectory() as folder:
            with fitz.open() as doc:
                doc.new_page(); raw=doc.tobytes()
            with self.assertRaisesRegex(ValueError,'página 1'):
                await pdf_extractor.extract_pdf_faithful(raw,Path(folder),page_cb=AsyncMock(side_effect=ValueError('Storage unavailable')))

    def test_route_does_not_read_original_into_memory_and_done_after_save(self):
        source=(Path(__file__).parents[1]/'routes/pdf_import.py').read_text(encoding='utf8')
        tree=ast.parse(source)
        generate=next(n for n in tree.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='agent_generate_faithful_course')
        body=ast.get_source_segment(source,generate)
        self.assertNotIn('await stream.read()',body)
        self.assertIn('validate_source_size(stream.length)',body)
        self.assertIn('with _FAITHFUL_RENDER_SLOT',body)
        worker=next(n for n in tree.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='_background_faithful_render')
        body=ast.get_source_segment(source,worker)
        self.assertIn('page_cb=_persist_page',body)
        self.assertLess(body.index('"course.slides": slides'),body.index('_faithful_set_cache(project_id, done_status)'))

    def test_tutor_explains_real_limit_and_no_silent_skip(self):
        from services.creator_guide import GUIDE
        text=' '.join(next(g for g in GUIDE if g['id']=='agent-faithful')['steps'])
        self.assertIn('300 MB',text); self.assertIn('omitida silenciosamente',text)
