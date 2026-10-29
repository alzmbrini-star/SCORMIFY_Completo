const assert=require('node:assert/strict'),{execFileSync}=require('node:child_process'),path=require('node:path');
const {JSDOM,VirtualConsole}=require('../../frontend/node_modules/.pnpm/jsdom@16.7.0/node_modules/jsdom');
const backend=path.resolve(__dirname,'..'),python='C:/Users/AndréLuizZambrini/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe';
const html=execFileSync(python,['-c',`import sys
sys.path.insert(0,'tests')
from test_visual_teaching import teaching_fixture
from services.rule_simulators import render_rules
print(render_rules(teaching_fixture()))`],{cwd:backend,env:{...process.env,PYTHONPATH:backend,PYTHONIOENCODING:'utf-8'},maxBuffer:5000000}).toString();
const settle=async w=>{for(let i=0;i<4;i++)await new Promise(r=>w.requestAnimationFrame(r));};
(async()=>{
 const errors=[],vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(String(e)));
 const dom=new JSDOM(html,{runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:vc,beforeParse(w){w.matchMedia=()=>({matches:true});}}),w=dom.window,d=w.document;
 await settle(w);assert.ok(d.body.classList.contains('sim-didactic-scene'));
 assert.ok(d.querySelector('.sim-main .sim-metric-strip'));assert.ok(!d.querySelector('.sim-tools').textContent.includes('Histórico'));
 const visual=d.querySelector('#rule-visual'),focus=visual.querySelector('[role="status"]').textContent;
 assert.ok(focus.includes('equalização'));
 d.querySelector('.sim-visual-guide').click();await settle(w);
 assert.ok(d.querySelector('dialog[open]').textContent.includes('Compare as superfícies'));
 d.querySelector('.sim-dialog-head button').click();await settle(w);
 d.querySelector('[data-visual-node="gate_in"]').dispatchEvent(new w.KeyboardEvent('keydown',{key:'Enter',bubbles:true}));await settle(w);
 assert.equal(JSON.parse(d.querySelector('#scormify-rule-view').textContent).state.entrada,1);
 assert.ok(visual.querySelector('[role="status"]').textContent.includes('0 → 1'));
 assert.equal(visual.dataset.observedVariables,'entrada');
 d.querySelector('#reset').click();await settle(w);
 assert.equal(visual.querySelector('[role="status"]').textContent,focus);
 assert.equal(d.querySelectorAll('#rule-visual').length,1);assert.deepEqual(errors,[]);
 dom.window.close();console.log('PASS advanced scene-first: contextual reading, verified visible consequences, keyboard object action, optional instruments and reset');
})().catch(e=>{console.error(e);process.exitCode=1;});
