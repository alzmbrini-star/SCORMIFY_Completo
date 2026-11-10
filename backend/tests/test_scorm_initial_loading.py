import asyncio
import base64
import copy
import json
import tempfile
import unittest
from pathlib import Path

from playwright.async_api import async_playwright
from services.scorm_initial_loading import install_initial_loader, externalize_scorm_images

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Z7V8AAAAASUVORK5CYII=')


class Assets(unittest.TestCase):
    def test_zip_repair_preserves_source_rules_scripts_and_manifest_ids(self):
        import zipfile
        from scripts.repair_scorm_loading import repair
        uri = 'data:image/png;base64,' + base64.b64encode(PNG).decode()
        original = {'id': 'course1', 'passingScore': 80, 'slides': [{'id': 's1', 'elements': [{'id': 'i1', 'type': 'image', 'src': uri}]}]}
        manifest = '<manifest xmlns="urn:test" identifier="same-id"><resources><resource href="index.html?v=old"><file href="index.html"/></resource></resources></manifest>'
        from services.scorm_exporter import _build_html
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory)/'input.zip', Path(directory)/'fixed.zip'
            with zipfile.ZipFile(source, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr('index.html', _build_html('Teste', 'pt-BR', 960, 540, enable_vlibras=False))
                archive.writestr('course.json', json.dumps(original))
                archive.writestr('imsmanifest.xml', manifest)
                archive.writestr('scripts/player.js', '/* unchanged player */')
            before = source.read_bytes()
            repair(source, output)
            self.assertEqual(before, source.read_bytes())
            with zipfile.ZipFile(output) as archive:
                data = json.loads(archive.read('course.json'))
                self.assertEqual(archive.read(data['slides'][0]['elements'][0]['src']), PNG)
                self.assertEqual(data['passingScore'], 80)
                self.assertEqual(archive.read('scripts/player.js'), b'/* unchanged player */')
                self.assertIn(b'identifier="same-id"', archive.read('imsmanifest.xml'))
            with self.assertRaises(ValueError): repair(source, output)

    def test_exact_bytes_dedup_and_learning_rules_unchanged(self):
        uri = 'data:image/png;base64,' + base64.b64encode(PNG).decode()
        course = {'id': 'original-id', 'slides': [{'elements': [{'type': 'image', 'src': uri}, {'type': 'scenario', 'scene': {'image': uri}, 'score': 7}, {'type': 'html', 'htmlContent': '<img src="' + uri + '">'}]}], 'passingScore': 80}
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / 'already.png').write_bytes(PNG)
            result = externalize_scorm_images(course, directory)
            self.assertEqual(result['references'], 2)
            self.assertEqual(result['newFiles'], 0)
            self.assertEqual(course['slides'][0]['elements'][0]['src'], 'assets/already.png')
            self.assertIn(uri, course['slides'][0]['elements'][2]['htmlContent'])
            self.assertEqual(course['passingScore'], 80)
            self.assertEqual(course['slides'][0]['elements'][1]['score'], 7)

    def test_export_builder_contains_new_inline_runtime(self):
        from services.scorm_exporter import _build_html
        html = _build_html('Teste', 'pt-BR', 960, 540, enable_vlibras=False)
        self.assertIn('scormify-initial-loader-v2', html)
        self.assertIn("getElementById('slide-container')", html)
        self.assertNotIn('if (!started) hide()', html)
        self.assertIn('Continuar mesmo assim', html)

    def test_singlepage_scorm_uses_same_visual_gate(self):
        import zipfile
        from services.scorm_single_page_exporter import export_single_page_scorm_package
        project = {'id': 'test-loading', 'name': 'Teste', 'enableVlibras': False,
                   'course': {'slides': [{'id': 's1', 'title': 'Conteúdo', 'elements': []}]}}
        with tempfile.TemporaryDirectory() as directory:
            output = export_single_page_scorm_package(project, directory, directory)
            with zipfile.ZipFile(output) as archive:
                html = archive.read('index.html').decode('utf-8')
            self.assertIn('scormify-initial-loader-v2', html)
            self.assertNotIn('setTimeout(hide, 15000)', html)


class LoaderBrowser(unittest.IsolatedAsyncioTestCase):
    async def test_slow_json_direct_nested_broken_and_text_slides(self):
        script = (Path(__file__).resolve().parents[1] / 'services/export_assets/initial-loader.js').read_text(encoding='utf-8')
        async with async_playwright() as p:
            browser = await p.chromium.launch(channel='chrome', headless=True)
            for kind in ['direct', 'nested', 'broken', 'text']:
                page = await browser.new_page()
                async def route(request):
                    if request.request.url.endswith('/slow.png'):
                        await asyncio.sleep(1.2)
                        await request.fulfill(body=PNG, content_type='image/png')
                    else: await request.fulfill(status=404, body=b'')
                await page.route('https://example.test/**', route)
                await page.set_content('<div id="scormify-loader"><div id="scormify-loader-bar"></div><div id="scormify-loader-percent"></div></div><div id="slide-container"></div><script>'+script+'</script>')
                # No slide DOM: the old player removed the loader at 2 seconds.
                if kind == 'direct':
                    await page.wait_for_timeout(2300)
                    self.assertFalse(await page.evaluate('window.ScormifyInitialLoader.ready'))
                markup = '<p>Conteúdo textual</p>' if kind == 'text' else '<img src="https://example.test/'+('bad.png' if kind=='broken' else 'slow.png')+'">'
                if kind == 'nested':
                    import html
                    markup = '<iframe srcdoc="'+html.escape(markup, quote=True)+'"></iframe>'
                await page.locator('#slide-container').evaluate('(e,markup)=>e.innerHTML=markup', markup)
                if kind in ['direct','nested']:
                    await page.wait_for_timeout(500)
                    self.assertFalse(await page.evaluate('window.ScormifyInitialLoader.ready'))
                if kind == 'broken':
                    await page.get_by_text('Algumas imagens não puderam ser carregadas.', exact=False).wait_for()
                    self.assertFalse(await page.evaluate('window.ScormifyInitialLoader.ready'))
                    await page.get_by_role('button', name='Continuar mesmo assim').click()
                await page.wait_for_function('window.ScormifyInitialLoader.ready', timeout=8000)
                await page.close()
            await browser.close()
