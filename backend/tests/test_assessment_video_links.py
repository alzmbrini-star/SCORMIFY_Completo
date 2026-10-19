import ast
import json
import re
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from services.assessment_video_links import assessment_video_link
from services.assessment_renderer import assessment_element
from services.assessment_assets import inline_assessment_assets


class AssessmentVideoLinks(unittest.TestCase):
    def test_supported_urls_and_private_parameters(self):
        cases = [
            ('https://youtu.be/M7lc1UVf-VE?t=45s', 'https://www.youtube-nocookie.com/embed/M7lc1UVf-VE?start=45'),
            ('https://www.youtube.com/watch?v=M7lc1UVf-VE', 'https://www.youtube-nocookie.com/embed/M7lc1UVf-VE'),
            ('https://www.youtube.com/shorts/M7lc1UVf-VE', 'https://www.youtube-nocookie.com/embed/M7lc1UVf-VE'),
            ('https://vimeo.com/76979871/abc123', 'https://player.vimeo.com/video/76979871?h=abc123'),
            ('https://player.vimeo.com/video/76979871?h=abc123&autoplay=1', 'https://player.vimeo.com/video/76979871?h=abc123'),
            ('https://iframe.mediadelivery.net/play/123/12345678-1234-1234-1234-123456789abc?token=secret&expires=123', 'https://iframe.mediadelivery.net/play/123/12345678-1234-1234-1234-123456789abc?token=secret&expires=123'),
            ('https://player.mediadelivery.net/embed/123/12345678-1234-1234-1234-123456789abc', 'https://player.mediadelivery.net/embed/123/12345678-1234-1234-1234-123456789abc'),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(assessment_video_link(raw)['url'], expected)
                self.assertEqual(assessment_video_link(expected)['url'], expected)

    def test_reject_untrusted_and_malformed_urls(self):
        for raw in ['javascript:alert(1)', 'http://youtu.be/M7lc1UVf-VE',
            'https://youtube.com.evil.test/watch?v=M7lc1UVf-VE', 'https://evil.test/video.mp4',
            'https://user:password@vimeo.com/123', 'https://vimeo.com:444/123',
            '<iframe src="https://evil.test/video"></iframe>', 'https://vimeo.com/123?x=<>',
            'https://vimeo.com/channels/123', 'https://youtube.com/watch?v=bad',
            'https://iframe.mediadelivery.net/embed/123/not-a-video', '//vimeo.com/123']:
            with self.subTest(raw=raw), self.assertRaises(ValueError): assessment_video_link(raw)

    def test_bunny_iframe_extracts_only_src_and_preserves_signed_bytes(self):
        signed='https://iframe.mediadelivery.net/play/123/12345678-1234-1234-1234-123456789abc?token=a%2Bb%3D&expires=9999999999&autoplay=true&muted=false'
        snippet='<div><iframe allow="autoplay" src="'+signed.replace('&','&amp;')+'" onload="alert(1)"></iframe></div>'
        self.assertEqual(assessment_video_link(snippet)['url'],signed)
        self.assertEqual(assessment_video_link(signed)['url'],signed)
        self.assertNotIn('onload',assessment_video_link(snippet)['url'])

    def test_bank_normalisation_and_exports_keep_link_without_upload(self):
        route = Path(__file__).resolve().parents[1] / 'routes' / 'assessments.py'
        functions = [node for node in ast.parse(route.read_text(encoding='utf-8')).body if isinstance(node,ast.FunctionDef)]
        scope = dict(re=re, uuid=uuid, datetime=datetime, timezone=timezone, Any=Any,
            QUESTION_TYPES={'single_choice','multiple_choice','ordering','categorization'})
        exec(compile(ast.Module(body=functions,type_ignores=[]),str(route),'exec'),scope)
        project={'id':'project-one','companyId':'company-one'}
        question={'prompt':'Assista e responda.', 'type':'single_choice',
            'options':[{'id':'a','text':'Sim','isCorrect':True},{'id':'b','text':'Não','isCorrect':False}],
            'media':{'kind':'video','source':'external','url':'https://vimeo.com/76979871/abc123','provider':'spoofed'}}
        saved=scope['normalise'](question,project,'user')
        self.assertEqual(saved['media']['provider'],'Vimeo')
        self.assertEqual(saved['media']['url'],'https://player.vimeo.com/video/76979871?h=abc123')
        element=assessment_element([saved])
        exported=inline_assessment_assets(element['htmlContent'],'does-not-exist')
        snapshot=re.search(r'<script id="assessment-data" type="application/json">(.*?)</script>',exported,re.S)[1]
        self.assertEqual(json.loads(snapshot)['questions'][0]['media'],saved['media'])
        self.assertIn('function assessmentVideoLink',exported)
        for patch in [dict(kind='image'),dict(url='https://evil.test/video'),dict(source='upload')]:
            invalid=dict(question,media=dict(question['media'],**patch))
            with self.assertRaises(ValueError): scope['normalise'](invalid,project,'user')
        # External URLs are only for question support, not arbitrary answer media.
        invalid=dict(question,options=[dict(question['options'][0],media=question['media']),question['options'][1]])
        with self.assertRaises(ValueError): scope['normalise'](invalid,project,'user')


if __name__ == '__main__': unittest.main()
