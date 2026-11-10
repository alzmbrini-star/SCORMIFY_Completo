"""Real Chrome layout QA against the local production build; mocked API, no AI spend."""
import json
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from playwright.sync_api import sync_playwright


def test_gamma_dialog_responsive_fixed_actions():
    root = Path(__file__).resolve().parents[2]
    output = root / 'artifacts'
    output.mkdir(exist_ok=True)
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(SimpleHTTPRequestHandler, directory=str(root / 'frontend/build')))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f'http://127.0.0.1:{server.server_port}'
    names = [('Aurum',['gold','metallic','black']),('Basic Dark',['dark','black','blue','purple']),('Basic Light',['light','blue','white']),('Bee Happy',['yellow','bright','dark']),('Ocean',['blue','cyan','navy']),('Forest',['green','white','teal']),('Rose',['pink','white'])]
    cards = [{'id':str(i),'name':name,'colors':colors,'tones':['professional','modern'],'source':'standard'} for i,(name,colors) in enumerate(names)]
    def intercept(route):
        url = route.request.url
        path = urlparse(url).path
        if '/api/' in path:
            data = []
            if path.endswith('/auth/me'): data={'id':'mock-user','roles':['super_admin'],'role':'super_admin','companyId':'mock-company','company':{'permissions':{}}}
            elif path.endswith('/gamma/status'): data={'configured':True}
            elif path.endswith('/gamma/designs'): data={'items':cards,'nextCursor':None}
            elif path.endswith('/companies'): data=[{'id':'mock-company','name':'Empresa de demonstração'},{'id':'other-company','name':'Outra empresa'}]
            elif path.endswith('/dashboard/metrics'): data={}
            assert route.request.method in ['GET','OPTIONS'], 'Layout QA must never submit a paid generation'
            route.fulfill(status=200, content_type='application/json', body=json.dumps(data), headers={'Access-Control-Allow-Origin':origin,'Access-Control-Allow-Credentials':'true','Access-Control-Allow-Headers':'Authorization, Content-Type','Access-Control-Allow-Methods':'GET, OPTIONS'})
        elif url.startswith(origin): route.continue_()
        else: route.abort()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel='chrome', headless=True)
            for width,height,name in [(1440,900,'desktop'),(390,844,'mobile')]:
                page = browser.new_page(viewport={'width':width,'height':height}, device_scale_factor=1)
                errors=[]
                page.on('pageerror',lambda error: errors.append(str(error)))
                page.route('**/*', intercept)
                page.goto(origin)
                try:
                    page.get_by_test_id('gamma-create-open').wait_for(timeout=5000)
                except Exception:
                    print('LOCAL QA ERROR', errors, page.locator('body').inner_text()[:1600])
                    raise
                page.get_by_test_id('gamma-create-open').click()
                page.wait_for_function("getComputedStyle(document.querySelector('.gamma-dialog')).opacity === '1'")
                company=page.get_by_test_id('gamma-company-trigger')
                assert company.evaluate('(e)=>e.tagName')=='SELECT'
                company.select_option('other-company')
                assert company.input_value()=='other-company'
                assert company.evaluate('(e)=>{const r=e.getBoundingClientRect();return e.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2));}'), 'Company control is covered'
                page.screenshot(path=str(output/f'gamma-company-{name}.png'))
                page.get_by_label('Título Gamma', exact=True).fill('Gestão do Tempo')
                page.get_by_label('Conteúdo Gamma', exact=True).fill('Introdução didática à gestão do tempo, com prioridades, foco e pausas.')
                page.get_by_label('Quantidade de slides Gamma', exact=True).fill('12')
                assert page.get_by_test_id('gamma-generate').inner_text()=='Gerar 12 slides'
                page.locator('[data-step="design"]').click()
                page.get_by_label('Modo visual Gamma').select_option('theme')
                page.get_by_role('button',name='Basic Dark',exact=True).click()
                assert page.locator('.gamma-design-card.selected').count()==1
                assert page.locator('.gamma-design-card').count()==6
                footer = page.locator('.gamma-footer').bounding_box()
                body = page.locator('.gamma-body').bounding_box()
                assert footer['y']+footer['height'] <= height+1
                assert body['x']+body['width'] <= width+1
                if width>1000:
                    grid=page.locator('.gamma-design-grid').bounding_box()
                    assert grid['y']+grid['height'] <= body['y']+body['height']+1
                assert page.locator('.gamma-design-grid').evaluate('(e)=>getComputedStyle(e).overflowY')=='visible'
                page.locator('.gamma-body').evaluate('(e)=>e.scrollTop=e.scrollHeight')
                assert page.get_by_test_id('gamma-generate').is_visible()
                page.locator('.gamma-body').evaluate('(e)=>e.scrollTop=0')
                page.screenshot(path=str(output/f'gamma-ui-{name}.png'))
                page.close()
            browser.close()
    finally:
        server.shutdown(); server.server_close()
