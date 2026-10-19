import copy
import unittest
from pathlib import Path

from services.assessment_renderer import refresh_assessment_documents

ROOT = Path(__file__).resolve().parents[2]


class InlineVideoTests(unittest.TestCase):
    def test_existing_assessment_gets_current_player_without_bank_resampling(self):
        config = {'title': 'Teste', 'questions': [{'id':'same-question', 'title':'</script><script>alert(1)</script>',
                  'media':{'kind':'video','source':'external','url':'https://iframe.mediadelivery.net/embed/123/12345678-1234-1234-1234-123456789abc?token=a%2Bb&expires=9999999999'}}]}
        project = {'course':{'slides':[{'elements':[{'type':'html','assessmentConfig':config,
                   'htmlContent':'<script>untrustedSavedCode()</script>', 'x':15,'width':900}]}]}}
        before = copy.deepcopy(config)
        refresh_assessment_documents(project)
        element = project['course']['slides'][0]['elements'][0]
        html = element['htmlContent']
        self.assertEqual(config,before)
        self.assertEqual(element['x'],15)
        self.assertNotIn('untrustedSavedCode()',html)
        self.assertNotIn('Abrir vídeo em nova aba',html)
        self.assertNotIn('</script><script>alert(1)',html)
        self.assertIn('\\u003c/script>',html)
        self.assertIn('no-referrer',html)
        self.assertIn('picture-in-picture; fullscreen',html)
        self.assertIn('token=a%2Bb&expires=9999999999',html)
        snapshot = copy.deepcopy(project)
        self.assertEqual(refresh_assessment_documents(project),snapshot)

    def test_arbitrary_html_without_question_snapshot_unchanged(self):
        project={'course':{'slides':[{'elements':[{'type':'html','htmlContent':'<b>Manual</b>'}]}]}}
        snapshot=copy.deepcopy(project)
        self.assertEqual(refresh_assessment_documents(project),snapshot)

    def test_all_editor_surfaces_rebuild_before_granting_provider_permissions(self):
        helper=(ROOT/'frontend/src/components/assessment/assessmentFrame.js').read_text(encoding='utf-8')
        self.assertIn('buildAssessmentHtml(config)',helper)
        self.assertIn('JSON.parse(',helper)
        self.assertNotIn('return element.htmlContent',helper)
        self.assertIn('allow-same-origin',helper)
        for name in ('CoursePreview','SlideCanvas','SplitPreview'):
            source=(ROOT/f'frontend/src/components/editor/{name}.jsx').read_text(encoding='utf-8')
            self.assertIn('if (element.assessmentConfig) return wrapInteractiveFullbleed(assessmentFrameDocument(element)',source)
            self.assertIn('allow={element.assessmentConfig ? assessmentFrameAllow : undefined}',source)
            self.assertIn("sandbox={element.assessmentConfig ? assessmentFrameSandbox : 'allow-scripts",source)

    def test_older_manual_question_id_config_keeps_embedded_snapshot(self):
        import json
        snapshot={'title':'Antiga','questions':[{'id':'q1','title':'Pergunta original'}]}
        config={'title':'Atual','questionIds':['q1'],'questionCount':1}
        element={'type':'html','assessmentConfig':config,'htmlContent':'<script id="assessment-data" type="application/json">'+json.dumps(snapshot)+'</script><script>oldCode()</script>'}
        project={'course':{'slides':[{'elements':[element]}]}}
        refresh_assessment_documents(project)
        self.assertIn('Pergunta original',element['htmlContent'])
        self.assertNotIn('oldCode()',element['htmlContent'])
        self.assertEqual(element['assessmentConfig'],config)


if __name__ == '__main__':
    unittest.main()
