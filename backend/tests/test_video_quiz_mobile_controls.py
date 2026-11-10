import re
from pathlib import Path

import pytest
from services.video_quiz import build_video_quiz
from services.video_quiz_playback import upgrade_video_quiz_playback


def document():
    return build_video_quiz({'src':'https://example.org/video.mp4','title':'Vídeo com perguntas',
        'checkpoints':[{'at':10,'question':'Qual é a resposta?', 'options':['Uma','Duas'],
                        'correctIndex':1,'explanation':'Duas é a resposta.','maxAttempts':2}]})


def test_existing_documents_get_compact_controls_without_changing_answers_or_resume_key():
    config, html = document()
    legacy = re.sub(r'<script id="video-quiz-mobile-controls-v1">[\s\S]*?</script>', '', html)
    upgraded = upgrade_video_quiz_playback(legacy)
    assert upgraded.count('id="video-quiz-mobile-controls-v1"') == 1
    assert upgrade_video_quiz_playback(upgraded) == upgraded
    assert html.split('<script id="video-quiz-data"')[1].split('</script>')[0] == upgraded.split('<script id="video-quiz-data"')[1].split('</script>')[0]
    root=Path(__file__).resolve().parents[2]
    backend=(root/'backend/services/export_assets/video-quiz-mobile-controls.js').read_text(encoding='utf-8')
    frontend=(root/'frontend/src/utils/videoQuizMobileControls.js').read_text(encoding='utf-8')
    assert backend.split('\nvideoQuizMobileControlsRuntime();')[0] in frontend
    assert config['key'] in upgraded


def test_actual_browser_mobile_bar_is_single_line_touchable_and_keeps_play_restart_accessible():
    from playwright.sync_api import sync_playwright
    _, html = document()
    with sync_playwright() as p:
        try:
            browser=p.chromium.launch(channel='chrome',headless=True)
        except Exception as exc:
            pytest.skip('Chrome headless indisponível: '+str(exc)[:100])
        try:
            page=browser.new_page(viewport={'width':390,'height':844})
            page.add_init_script("""(()=>{
              let paused=true,position=0;
              Object.defineProperties(HTMLMediaElement.prototype,{
                duration:{get(){return 60;}},currentTime:{get(){return position;},set(v){position=v;}},
                paused:{get(){return paused;}},ended:{get(){return false;}},readyState:{get(){return 4;}}
              });
              HTMLMediaElement.prototype.play=function(){paused=false;this.dispatchEvent(new Event('play'));this.dispatchEvent(new Event('playing'));return Promise.resolve();};
              HTMLMediaElement.prototype.pause=function(){paused=true;this.dispatchEvent(new Event('pause'));};
            })();""")
            page.route('**/*',lambda route:route.fulfill(status=200,content_type='text/html',body=html) if route.request.is_navigation_request() else route.abort())
            page.goto('https://video-test.example/')
            page.locator('#video').evaluate("v=>v.dispatchEvent(new Event('loadedmetadata'))")
            page.wait_for_function("document.getElementById('restart-video-quiz').hidden===false")
            for width,height in ((320,740),(390,844),(650,920)):
                page.set_viewport_size({'width':width,'height':height})
                metrics=page.evaluate("""()=>{
                  const box=id=>{const r=document.getElementById(id).getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height,right:r.right,bottom:r.bottom};};
                  return {play:box('play'),restart:box('restart-video-quiz'),video:box('video'),
                    controls:document.querySelector('.controls').getBoundingClientRect().toJSON(),
                    overflow:document.documentElement.scrollWidth>innerWidth};
                }""")
                assert metrics['play']['height']>=44
                assert metrics['restart']['width']==44
                assert metrics['controls']['height']==52
                assert abs(metrics['play']['y']-metrics['restart']['y'])<1
                assert metrics['video']['width']>width*.85
                assert not metrics['overflow']
                assert metrics['restart']['right']<=width
            page.set_viewport_size({'width':390,'height':844})
            page.locator('#play').click()
            page.wait_for_function("document.getElementById('play').dataset.transportState==='playing'")
            assert page.locator('#play').get_attribute('aria-label')=='Pausar'
            page.locator('#play').click()
            page.wait_for_function("document.getElementById('play').getAttribute('aria-label')==='Reproduzir'")
            page.locator('#restart-video-quiz').click()
            assert page.locator('#message').inner_text().startswith('Revisão sem nota')
            assert page.locator('#restart-video-quiz').get_attribute('aria-label')=='Rever vídeo e perguntas'
            page.locator('#font').click()
            assert page.locator('#restart-video-quiz').bounding_box()['width']==44
            page.locator('#contrast').click()
            assert 'high' in page.locator('body').get_attribute('class')
            page.set_viewport_size({'width':960,'height':600})
            assert page.locator('#restart-video-quiz').evaluate("e=>getComputedStyle(e).fontSize")=='20px'
            page.set_viewport_size({'width':568,'height':320})
            assert page.locator('#play').bounding_box()['height']==44
            # Save an actual browser rendering for visual QA (synthetic poster).
            page.set_viewport_size({'width':390,'height':844})
            page.locator('body').evaluate("e=>e.classList.remove('large','high')")
            page.locator('#video').evaluate("""v=>v.poster='data:image/svg+xml,'+encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 360"><rect width="640" height="360" fill="#c7e4ee"/><path d="M0 280L130 100L300 270L450 120L640 280V360H0Z" fill="#567b91"/><path d="M0 300Q300 230 640 300V360H0Z" fill="#2489a2"/></svg>')""")
            proof=Path(__file__).resolve().parents[2]/'work/verification/video-quiz-mobile-controls.png'
            proof.parent.mkdir(parents=True,exist_ok=True)
            page.screenshot(path=str(proof),full_page=True)
        finally:
            browser.close()
