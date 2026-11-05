import json
from pathlib import Path
import pytest
from services.video_quiz import build_video_quiz, normalize_video_quiz
from services.video_quiz_sources import video_quiz_source
from services.assessment_assets import inline_assessment_assets


@pytest.mark.parametrize('source,provider,expected',[
    ('https://youtu.be/M7lc1UVf-VE','youtube','https://www.youtube.com/embed/M7lc1UVf-VE'),
    ('https://vimeo.com/76979871/ab12cd','vimeo','https://player.vimeo.com/video/76979871?h=ab12cd'),
    ('<iframe src="https://player.vimeo.com/video/76979871?h=abc" onload="alert(1)"></iframe>','vimeo','https://player.vimeo.com/video/76979871?h=abc'),
    ('https://iframe.mediadelivery.net/play/123/11111111-2222-3333-4444-555555555555?token=a%2Bb&expires=99','bunny','https://iframe.mediadelivery.net/play/123/11111111-2222-3333-4444-555555555555?token=a%2Bb&expires=99')
])
def test_sources(source,provider,expected,tmp_path):
    assert video_quiz_source(source)==(expected,provider)
    config,doc=build_video_quiz(dict(src=source,graded=True,checkpoints=[dict(at=4,question='Qual?',options=['A','B'],correctIndex=1,explanation='B.',maxAttempts=2)]))
    assert config['provider']==provider and config['src']==expected and config['graded'] is True
    assert doc.index('id="video-quiz-providers-v1"')<doc.index('id="video-quiz-runtime-v2"')
    assert 'onload="alert(1)"' not in doc
    exported=inline_assessment_assets(doc,str(tmp_path))
    snap=exported.split('<script id="video-quiz-data" type="application/json">')[1].split('</script>')[0]
    assert json.loads(snap)==config


def test_frontend_and_export_use_identical_provider_adapter():
    root=Path(__file__).resolve().parents[2]
    backend=(root/'backend/services/export_assets/video-quiz-providers.js').read_text(encoding='utf-8')
    frontend=(root/'frontend/src/utils/videoQuizProviders.js').read_text(encoding='utf-8')
    assert backend.split('\nvideoQuizProviderRuntime();')[0] in frontend
    template=(root/'frontend/src/utils/videoQuizHostedDocument.js').read_text(encoding='utf-8')
    import re
    authored=json.loads(re.search(r'export const HOSTED_VIDEO_TEMPLATE = (.*);',template)[1])
    _,doc=build_video_quiz(dict(src='https://vimeo.com/76979871',checkpoints=[dict(at=4,question='Q',options=['A','B'],correctIndex=0,explanation='E')]))
    canonical=re.sub(r'(<script id="video-quiz-data" type="application/json">).*?(</script>)',lambda m:m[1]+'__VIDEO_CONFIG__'+m[2],doc)
    assert authored==canonical


@pytest.mark.parametrize('value',['<iframe src="https://evil.test/x"></iframe>','https://vimeo.com/123/bad%3Cscript','https://user:pass@vimeo.com/123','https://youtube.com/playlist?list=abc'])
def test_reject_untrusted_embed(value):
    with pytest.raises(ValueError):video_quiz_source(value)


def test_single_page_provider_export_preserves_origin_without_author_scripts(tmp_path):
    from services.single_page_exporter import _render_html_element_inner
    _,doc=build_video_quiz(dict(src='https://youtu.be/M7lc1UVf-VE',checkpoints=[dict(at=4,question='Q',options=['A','B'],correctIndex=0,explanation='E')]))
    dirty=doc.replace('</body>','<script>stealParentSecrets()</script></body>')
    exported=_render_html_element_inner(dict(type='html',height=650,htmlContent=dirty,style={'textShadow':'</style><script>evil()</script>'}),'p1',str(tmp_path),'',0,0)
    assert 'srcdoc="' in exported
    assert 'data:text/html' not in exported
    assert 'stealParentSecrets' not in exported
    assert 'evil()' not in exported
    assert 'video-quiz-providers-v1' in exported
