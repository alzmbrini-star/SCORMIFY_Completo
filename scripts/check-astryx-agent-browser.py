"""Isolated headless QA against local generated fixtures only, never user Chrome.

Run build-astryx-agent-qa.py first. No authentication, DB or remote API requests.
"""
import asyncio
import functools
import http.server
import json
import threading
from pathlib import Path
from playwright.async_api import async_playwright

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT.parents[1]/'outputs'/'astryx-agent'


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*args):pass


async def metrics(frame):
    return await frame.locator('main.ax-page').evaluate('''n=>({width:innerWidth,scroll:document.documentElement.scrollWidth,
      font:getComputedStyle(n.querySelector('.ax-copy')||n).fontSize,
      color:getComputedStyle(n.querySelector('.ax-copy')||n).color,
      heading:getComputedStyle(n.querySelector('h1,h2')).fontSize,
      images:Array.from(n.querySelectorAll('img')).map(i=>({complete:i.complete,natural:i.naturalWidth,width:i.clientWidth,height:i.clientHeight,fit:getComputedStyle(i).objectFit}))})''')


async def run():
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(QuietHandler,directory=str(OUT)))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    base=f'http://127.0.0.1:{server.server_port}'
    results=[]
    try:
        async with async_playwright() as p:
            browser=await p.chromium.launch(channel='chrome',headless=True)
            context=await browser.new_context()
            async def local_only(route):
                if route.request.url.startswith(base) or route.request.url.startswith('data:'):
                    await route.continue_()
                else:
                    await route.abort()
            await context.route('**/*',local_only)
            page=await context.new_page()
            for topic in range(3):
                for width in (390,1280):
                    await page.set_viewport_size({'width':width,'height':900})
                    for slide in (0,1,2,6):
                        await page.goto(f'{base}/{topic}/slide-{slide}.html')
                        m=await metrics(page)
                        assert m['scroll'] <= width+1, m
                        assert float(m['font'].replace('px','')) >= 17, m
                        assert m['color'] != 'rgb(255, 255, 255)', m
                        assert all(i['complete'] and i['natural']>0 and i['fit']=='contain' for i in m['images']),m
                        results.append({'topic':topic,'slide':slide,'viewport':width,'metrics':m})
                        if topic==0 and slide==2:
                            await page.screenshot(path=str(OUT/f'content-{width}.png'),full_page=True)
            # Real classic players must apply and remove responsive sizing when
            # navigating between new lessons and the untouched traditional Quiz.
            for kind,path in [('html','HTML.html'),('scorm','scorm/index.html')]:
                await page.set_viewport_size({'width':390,'height':844})
                await page.goto(f'{base}/0/{path}')
                portrait=page.get_by_role('button',name='Continuar no modo retrato',exact=True)
                if await portrait.is_visible():await portrait.click()
                await page.wait_for_function("document.getElementById('slide-container')?.classList.contains('astryx-mobile-stage')")
                await page.locator('#scormify-loader').wait_for(state='hidden')
                frame=page.frame_locator('#slide-container iframe').first
                m=await metrics(frame)
                assert m['width'] <= 390 and float(m['font'].replace('px',''))>=17,m
                nxt=page.locator('#mobile-nav-next') if kind=='scorm' else page.locator('#next-btn')
                previous=page.locator('#mobile-nav-prev') if kind=='scorm' else page.locator('#prev-btn')
                for _ in range(3):await nxt.click()
                await page.wait_for_function("!document.getElementById('slide-container').classList.contains('astryx-mobile-stage')")
                await previous.click()
                await page.wait_for_function("document.getElementById('slide-container').classList.contains('astryx-mobile-stage')")
                frame=page.frame_locator('#slide-container iframe').first
                m=await metrics(frame)
                assert m['width'] <= 390 and float(m['font'].replace('px',''))>=17,m
                results.append({'player':kind,'quizStageUnchanged':True,'lessonResponsiveRestored':True,'metrics':m})
                await page.screenshot(path=str(OUT/f'{kind}-mobile.png'))
            await browser.close()
    finally:
        server.shutdown()
    (OUT/'browser-report.json').write_text(json.dumps({'checks':len(results),'passed':True,'results':results},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'checks':len(results),'passed':True,'report':str(OUT/'browser-report.json')}))


if __name__=='__main__':asyncio.run(run())
