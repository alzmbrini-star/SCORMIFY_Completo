import copy
import ast
import unittest
from pathlib import Path
from typing import Optional
from html.parser import HTMLParser

from services.editorial_layout import content_boxes, repair_legacy_agent_project
from services.ai_agent import _build_content_slide, _style_content_html, _style_summary_html


DARK = dict(accent='#34d399', text='#f4f4f5', mode='dark')
LIGHT = dict(accent='#1d4ed8', text='#1c1917', mode='light')
RAW = '<h2 style="color:white">Descrição e impacto</h2><div style="display:flex;width:1000px"><p style="background:white;color:white">Descreva fatos observáveis.</p><ul><li style="background:#fff">Combine o acompanhamento.</li></ul></div>'


def overlaps(a, b):
    return (a['x'] < b['x']+b['width'] and b['x'] < a['x']+a['width']
            and a['y'] < b['y']+b['height'] and b['y'] < a['y']+a['height'])


class Styles(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.items = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.items.append((tag, attrs))


class EditorialLayoutTests(unittest.TestCase):
    def test_every_image_composition_is_bounded_and_disjoint(self):
        for layout in ('cinematic_scene','guided_observation','decision_split','workbench','reflection','unknown'):
            with self.subTest(layout=layout):
                elements = _build_content_slide(dict(title='Feedback', journeyLayout=layout,
                    elements=[{'content':RAW}]), DARK, 'Curso', '/image.png')
                text = next(e for e in elements if e.get('journeyRole') == 'learning_copy')
                image = next(e for e in elements if e.get('journeyRole') == 'evidence_scene')
                self.assertFalse(overlaps(text,image))
                for e in (text,image):
                    self.assertGreaterEqual(e['x'], 0)
                    self.assertGreaterEqual(e['y'], 100)
                    self.assertLessEqual(e['x']+e['width'], 1920)
                    self.assertLessEqual(e['y']+e['height'], 820)
                self.assertGreaterEqual(text['width'], 600)

    def test_editorial_styles_do_not_duplicate_or_preserve_conflicting_styles(self):
        for palette in (DARK,LIGHT):
            for summary in (False,True):
                html = (_style_summary_html(RAW,palette['accent'],palette) if summary
                        else _style_content_html(RAW,palette['text'],palette))
                self.assertIn('data-agent-copy-version="2"',html)
                self.assertIn('overflow:auto',html)
                self.assertIn('Descreva fatos observáveis.',html)
                self.assertIn('Combine o acompanhamento.',html)
                self.assertNotIn('width:1000px',html)
                self.assertNotIn('display:flex',html)
                self.assertNotIn('background:white',html)
                for tag,attrs in Styles(html).items:
                    self.assertLessEqual(sum(k=='style' for k,v in attrs),1)
                    if tag in ('p','li'):
                        self.assertIn('color:',dict(attrs)['style'])
                if summary and palette == DARK:
                    self.assertIn('background:rgba(255,255,255,0.045)',html)

    def fixture(self):
        legacy = '<div style="padding:6px 0;font-family:Arial;">'+RAW+'</div>'
        return dict(createdByAgent=True,course={'slides':[dict(contentType='content',
            journeyLayout='cinematic_scene',background='#121417',elements=[
                dict(type='html',journeyRole='learning_copy',x=120,y=500,width=980,height=250,htmlContent=legacy),
                dict(type='image',journeyRole='evidence_scene',x=120,y=105,width=1680,height=610,src='image.png')])]})

    def test_existing_generated_course_repaired_idempotently(self):
        project=self.fixture()
        repaired=repair_legacy_agent_project(project)
        elements=repaired['course']['slides'][0]['elements']
        self.assertFalse(overlaps(*elements))
        self.assertEqual(elements[1]['src'],'image.png')
        self.assertIn('data-agent-copy-version="2"',elements[0]['htmlContent'])
        snapshot=copy.deepcopy(repaired)
        self.assertEqual(repair_legacy_agent_project(repaired),snapshot)

    def test_manual_layout_and_interactive_content_not_rewritten(self):
        project=self.fixture()
        slide=project['course']['slides'][0]
        slide['elements'][0].update(x=300,htmlContent='<div>Conteúdo manual</div>')
        snapshot=copy.deepcopy(project)
        self.assertEqual(repair_legacy_agent_project(project),snapshot)
        for kind in ('simulator','case_study','game','quiz'):
            project=self.fixture()
            project['course']['slides'][0]['contentType']=kind
            snapshot=copy.deepcopy(project)
            self.assertEqual(repair_legacy_agent_project(project),snapshot)
        project=self.fixture()
        project.pop('createdByAgent')
        snapshot=copy.deepcopy(project)
        self.assertEqual(repair_legacy_agent_project(project),snapshot)

    def test_legacy_summary_uses_actual_slide_background(self):
        for bg,palette in (('#121417',DARK),('#fff',LIGHT)):
            project=self.fixture()
            slide=project['course']['slides'][0]
            slide.update(contentType='summary',background=bg)
            repair_legacy_agent_project(project)
            html=slide['elements'][0]['htmlContent']
            self.assertIn('color:'+palette['text'],html)

    def test_user_summary_color_override_survives_legacy_project_read(self):
        project=self.fixture()
        slide=project['course']['slides'][0]
        slide['contentType']='summary'
        html=slide['elements'][0]['htmlContent']+'<style id="scormify-editorial-text-colors">body li{color:#172c49!important}</style>'
        slide['elements'][0]['htmlContent']=html
        repair_legacy_agent_project(project)
        self.assertEqual(slide['elements'][0]['htmlContent'],html)


class ProjectReadTests(unittest.IsolatedAsyncioTestCase):
    async def test_shared_project_read_repairs_without_database_write(self):
        source = Path(__file__).resolve().parents[1] / 'routes' / 'deps.py'
        tree = ast.parse(source.read_text(encoding='utf-8'))
        node = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == 'get_project_by_id')
        project = EditorialLayoutTests().fixture()

        class Collection:
            async def find_one(self, query, projection):
                self.query = query
                return copy.deepcopy(project)

        class DB:
            projects = Collection()

        namespace = {'db': DB(), 'Optional': Optional}
        exec(compile(ast.Module(body=[node], type_ignores=[]),str(source),'exec'),namespace)
        repaired = await namespace['get_project_by_id']('same-project')
        self.assertEqual(namespace['db'].projects.query, {'id':'same-project'})
        self.assertIn('data-agent-copy-version="2"',repaired['course']['slides'][0]['elements'][0]['htmlContent'])
        self.assertNotIn('data-agent-copy-version="2"',project['course']['slides'][0]['elements'][0]['htmlContent'])


if __name__ == '__main__':
    unittest.main()
