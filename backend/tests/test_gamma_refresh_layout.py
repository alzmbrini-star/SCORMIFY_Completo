"""Production-build browser QA with synthetic course and mocked API only."""
import json
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright


def test_gamma_refresh_review_preserves_explicit_mapping_and_fits_mobile():
    root = Path(__file__).resolve().parents[2]
    class Handler(SimpleHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_GET(self):
            if self.path.startswith('/editor/'): self.path='/'
            return super().do_GET()
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=str(root/'frontend/build')))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    origin=f'http://127.0.0.1:{server.server_port}'
    image='data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="320" height="180"%3E%3Crect width="320" height="180" fill="%23233465"/%3E%3C/svg%3E'
    project={'id':'qa-gamma','name':'Curso de demonstração Gamma','source':'gamma','gammaJobId':'g1','status':'ready','updatedAt':'r1',
             'course':{'id':'c','metadata':{'title':'Curso de demonstração'},'slides':[{'id':'s1','title':'Capa','width':1920,'height':1080,'duration':10,'background':'#fff','audio':[],'annotations':[],'elements':[{'id':'e1','type':'image','src':image,'x':0,'y':0,'width':1920,'height':1080}]}]}}
    job={'id':'refresh1','status':'ready','bases':[{'slideId':'s1','elementId':'e1','index':0,'position':0,'title':'Capa','src':image,'width':1920,'height':1080}],
         'images':[{'index':i,'src':image,'width':1920,'height':1080} for i in range(3)]}
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(channel='chrome',headless=True)
            for width,height,label in [(1440,900,'desktop'),(390,844,'mobile')]:
                writes=[]; errors=[]
                page=browser.new_page(viewport={'width':width,'height':height})
                page.add_init_script("localStorage.setItem('scormify_auth_token','synthetic-local-qa-only')")
                page.on('pageerror',lambda e:errors.append(str(e)))
                def intercept(route):
                    path=urlparse(route.request.url).path
                    if '/api/' in path:
                        data=[]
                        if route.request.method=='POST':
                            writes.append((path,route.request.post_data))
                            assert path in ['/api/course/qa-gamma/save','/api/projects/qa-gamma/gamma-refresh','/api/projects/qa-gamma/gamma-refresh/refresh1/apply']
                            data=job if path.endswith('gamma-refresh') else {'appliedSlides':1}
                        elif path.endswith('/auth/me'): data={'id':'qa-user','roles':['super_admin'],'role':'super_admin','companyId':'qa-company','company':{'permissions':{}}}
                        elif path.endswith('/projects/qa-gamma'): data=project
                        elif path.endswith('/gamma-refresh/refresh1'): data=job
                        elif '/assets/' in path:
                            route.fulfill(status=200,content_type='image/svg+xml',body='<svg xmlns="http://www.w3.org/2000/svg"/>'); return
                        route.fulfill(status=200,content_type='application/json',body=json.dumps(data),headers={'Access-Control-Allow-Origin':origin,'Access-Control-Allow-Credentials':'true','Access-Control-Allow-Headers':'Authorization, Content-Type','Access-Control-Allow-Methods':'GET, POST, OPTIONS'})
                    elif route.request.url.startswith(origin): route.continue_()
                    else: route.abort()
                page.route('**/*',intercept)
                page.goto(origin+'/editor/qa-gamma')
                try: page.get_by_test_id('gamma-refresh-open').click(timeout=15000)
                except Exception:
                    print('QA initial page:',errors,page.locator('body').inner_text()[:2000]); raise
                page.get_by_role('button',name='Buscar versão atual no Gamma',exact=True).click()
                page.get_by_label('Imagem Gamma para slide 1').wait_for()
                assert page.get_by_label('Imagem Gamma para slide 1').input_value()==''
                page.get_by_label('Imagem Gamma para slide 1').select_option('2')
                page.get_by_role('checkbox',name='Conferi as correspondências',exact=False).check()
                apply=page.get_by_role('button',name='Aplicar em 1 slide(s)',exact=True)
                apply.scroll_into_view_if_needed()
                box=apply.bounding_box();assert box['y']+box['height']<=height
                assert page.locator('[role=dialog]').evaluate('(e)=>e.scrollWidth<=e.clientWidth+1')
                (root/'artifacts').mkdir(exist_ok=True)
                page.screenshot(path=str(root/f'artifacts/gamma-refresh-{label}.png'))
                apply.click()
                page.get_by_text('Imagens atualizadas do Gamma. Interações preservadas. Confira o alinhamento e reexporte o curso.',exact=True).wait_for()
                assert json.loads(writes[-1][1])=={'mappings':[{'slideId':'s1','sourceIndex':2}]}
                assert len(writes)==3
                assert not errors,errors
                page.close()
            browser.close()
    finally: server.shutdown();server.server_close()
