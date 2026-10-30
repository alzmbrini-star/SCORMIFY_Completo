const assert=require('node:assert/strict'),path=require('node:path'),{execFileSync}=require('node:child_process');
const {JSDOM,VirtualConsole}=require('../../frontend/node_modules/.pnpm/jsdom@16.7.0/node_modules/jsdom');
const root=path.resolve(__dirname,'../..'),python='C:/Users/AndréLuizZambrini/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe';
const packet=JSON.parse(execFileSync(python,['-c',`import json
from visual_finish_fixtures import pilots
from services.didactic_visualizations import render
print(json.dumps([{'html':render(p),'plan':p} for p in pilots()]))`],{cwd:root,env:{...process.env,PYTHONPATH:path.join(root,'backend')+';'+path.join(root,'backend/tests'),PYTHONIOENCODING:'utf-8'},encoding:'utf8'}));
for(const {html,plan} of packet){
  const errors=[],vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(e.message));let pending=new Map(),seq=0;
  const dom=new JSDOM(html,{runScripts:'dangerously',virtualConsole:vc,beforeParse(w){w.requestAnimationFrame=fn=>{pending.set(++seq,fn);return seq};w.cancelAnimationFrame=id=>pending.delete(id);}}),d=dom.window.document;
  assert.equal(d.body.dataset.visualFinish,'1');assert.equal(d.body.dataset.visualTheme,plan.presentation.theme);
  assert.equal(d.querySelectorAll('#vf-definitions').length,1);assert.ok(d.querySelectorAll('defs stop').length>=3);
  assert.equal(d.querySelectorAll('#items button').length,plan.nodes.length);
  assert.equal(d.querySelector('#play').textContent,'Iniciar');assert.equal(pending.size,0);
  const first=plan.motions[0],g=Array.from(d.querySelectorAll('#scene > g')).find(g=>g.getAttribute('aria-label')===plan.nodes.find(n=>n.id===first.node).label);
  const before=g.getAttribute('transform')||g.getAttribute('opacity');d.getElementById('time').value=170;d.getElementById('time').dispatchEvent(new dom.window.Event('input'));
  assert.notEqual(g.getAttribute('transform')||g.getAttribute('opacity'),before);
  const finished=g.firstElementChild.getAttribute('fill');assert.ok(finished==='none'||finished.startsWith('url(#vf-'));
  d.getElementById('reset').click();assert.equal(pending.size,0);
  d.querySelector('#items button').click();assert.equal(d.querySelectorAll('[data-vf-selected=true]').length,1);
  const marker=d.querySelector('#scormify-visualization-finish-v1');dom.window.eval(marker.textContent);
  assert.equal(d.querySelectorAll('#vf-definitions').length,1);assert.equal(d.querySelectorAll('#scormify-visualization-finish-style-v1').length,1);
  assert.deepEqual(errors,[]);dom.window.close();console.log('PASS finish: '+plan.presentation.theme+' / '+plan.title+' — paints, controls, exact motion, reset and idempotency');
}
