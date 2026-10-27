import json
import unittest
from pathlib import Path
from services.assessment_renderer import refresh_assessment_documents
from services.editorial_text_colors import apply_editorial_text_colors, RULES


class AssessmentTextColorsTests(unittest.TestCase):
    def test_rebuild_preserves_colors_and_question_snapshot(self):
        config = {'title':'Prova','questions':[{'id':'one','prompt':'Pergunta'}],
                  'textColors':{'title':'#123456','text':'#abcdef'}}
        element = {'type':'html','assessmentConfig':config,'htmlContent':'old'}
        project = {'course':{'slides':[{'elements':[element]}]}}
        refresh_assessment_documents(project)
        html = element['htmlContent']
        self.assertIn('color:#123456!important',html)
        self.assertIn('color:#abcdef!important',html)
        self.assertIn('"id": "one"',html)
        refresh_assessment_documents(project)
        self.assertEqual(element['htmlContent'],html)
        config['textColors'] = {}
        refresh_assessment_documents(project)
        self.assertNotIn('scormify-editorial-text-colors',element['htmlContent'])

    def test_manual_legacy_snapshot_keeps_question_and_colors(self):
        element = {'type':'html','assessmentConfig':{'textColors':{'text':'#112233'}},
                   'htmlContent':'<script id="assessment-data" type="application/json">'+json.dumps({'questions':[{'id':'saved'}]})+'</script>'}
        refresh_assessment_documents({'course':{'slides':[{'elements':[element]}]}})
        self.assertIn('"id": "saved"',element['htmlContent'])
        self.assertIn('color:#112233!important',element['htmlContent'])

    def test_only_validated_colors_are_injected_and_scripts_are_untouched(self):
        html = '<html><head></head><body><script>runQuiz()</script></body></html>'
        self.assertEqual(apply_editorial_text_colors(html,{'text':'red;display:none'}),html)
        styled = apply_editorial_text_colors(html,{'text':'#ffffff'})
        self.assertIn('<script>runQuiz()</script>',styled)
        self.assertEqual(apply_editorial_text_colors(styled,{}),html)

    def test_frontend_backend_selector_parity(self):
        frontend = Path(__file__).resolve().parents[2]/'frontend/src/utils/editorialTextColors.js'
        source = frontend.read_text(encoding='utf-8')
        for selector in RULES.values():
            self.assertIn(selector,source)


if __name__ == '__main__':
    unittest.main()
