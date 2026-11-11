import asyncio
import subprocess
import zipfile
from pathlib import Path

from services.export_navigation import install_navigation_window


def test_window_indices_are_bounded_and_keep_current_first_last():
    result=subprocess.run(['node',str(Path(__file__).with_name('navigation_window.cjs'))],capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr


def test_shared_styles_bound_flex_content_without_hiding_primary_actions():
    html=install_navigation_window('<html><head></head><body></body></html>')
    assert 'flex:1 1 0;min-width:0' in html
    assert 'flex:0 0 auto;flex-wrap:nowrap' in html
    assert 'white-space:nowrap;flex-shrink:0' in html
    assert '.volume-control{display:none}' in html
    assert '#next-btn{display:none}' not in html
    assert html==install_navigation_window(html)


def sample():
    return {'id':'nav-long','name':'Navegação de 97 slides','enableVlibras':False,
            'course':{'slides':[{'id':f's{i}','title':f'Slide {i+1}','elements':[], 'duration':5} for i in range(97)]}}


def test_html_embeds_navigation_before_player_and_keeps_all_slides(tmp_path):
    from services.html_exporter import generate_standalone_html
    html=asyncio.run(generate_standalone_html(sample(),str(tmp_path)))
    assert html.index('root.ScormifyNavigation')<html.index('function updateProgress()')
    assert 'window.ScormifyNavigation.indices(totalSlides, currentSlide)' in html
    assert 'navigation-slide-count' in html and 'id="next-btn"' in html
    assert 'Slide 97' in html


def test_scorm_zip_embeds_shared_layout_and_bounded_dots(tmp_path):
    from models import Project
    from services.scorm_exporter import export_scorm_package
    result=export_scorm_package(Project(**sample()),str(tmp_path/'storage'),str(tmp_path/'exports'))
    with zipfile.ZipFile(result) as package:
        html=package.read('index.html').decode('utf-8')
        script=package.read('scripts/player.js').decode('utf-8')
    assert 'scormify-navigation-window' in html
    assert 'window.ScormifyNavigation.indices(totalSlides, currentSlide)' in script
    assert 'navigation-slide-count' in script and 'slideCompletionState(i)' in script


def test_tutor_explains_navigation_and_reexport():
    from services.creator_guide import topics_for
    text=' '.join(next(t for t in topics_for({'role':'super_admin'}) if t['id']=='export')['steps'])
    assert 'janela limitada de pontos' in text and 'Reexporte arquivos antigos' in text
