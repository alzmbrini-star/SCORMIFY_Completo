const assert=require('node:assert/strict'),{execFileSync}=require('node:child_process'),path=require('node:path');
const {JSDOM,VirtualConsole}=require('../../frontend/node_modules/.pnpm/jsdom@16.7.0/node_modules/jsdom');
const Ajv=require('../../frontend/node_modules/.pnpm/ajv@8.20.0/node_modules/ajv');
const backend=path.resolve(__dirname,'..'),python=process.env.PYTHON_EXE||'C:/Users/AndréLuizZambrini/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe';
const packet=JSON.parse(execFileSync(python,['-c',`import sys,json
sys.path.insert(0,'tests')
from test_component_scenes import component_fixture
from services.component_scenes import project_schema
from services.rule_simulators import render_rules,validate_rules
print(json.dumps({'schema':project_schema(),'presentations':[{'source':component_fixture(style),'html':render_rules(component_fixture(style)),'checks':validate_rules(component_fixture(style))['checks']} for style in ('blueprint','studio')]}))`],{cwd:backend,env:{...process.env,PYTHONPATH:backend,PYTHONIOENCODING:'utf-8'},maxBuffer:5000000}));
const schema=new Ajv({strict:false}).compile(packet.schema);
const settle=async w=>{for(let i=0;i<3;i++)await new Promise(r=>w.requestAnimationFrame(r));};
(async()=>{
 for(const p of packet.presentations){
  assert.ok(schema(p.source.visualProject),JSON.stringify(schema.errors));
  const errors=[],vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(String(e)));
  const dom=new JSDOM(p.html,{runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:vc,beforeParse(w){w.matchMedia=()=>({matches:true});}}),w=dom.window,d=w.document;
  await settle(w);assert.ok(d.body.classList.contains('sim-didactic-scene'));
  const view=()=>JSON.parse(d.querySelector('#scormify-rule-view').textContent);
  const initial=view().state;
  assert.equal(d.querySelector('[data-visual-node="alarm_stem"]').getAttribute('x1'),'50');
  assert.equal(d.querySelector('[data-visual-node="alarm_stem"]').getAttribute('y1'),'35');
  assert.equal(d.querySelector('[data-visual-node="boat_mast"]').getAttribute('x1'),'130');
  const gate=d.querySelector('[data-visual-node="entry"]');
  assert.equal(gate.getAttribute('role'),'button');
  gate.dispatchEvent(new w.KeyboardEvent('keydown',{key:'Enter',bubbles:true}));await settle(w);
  assert.equal(view().state.entrada,1);
  assert.equal(d.querySelector('[data-visual-node="entry_blade"]').getAttribute('height'),'24');
  assert.equal(gate.getAttribute('aria-disabled'),'true');
  const count=view().steps;gate.dispatchEvent(new w.KeyboardEvent('keydown',{key:'Enter',bubbles:true}));await settle(w);assert.equal(view().steps,count);
  for(const check of p.checks){
   d.querySelector('#reset').click();await settle(w);
   for(const id of check.actions){
    const button=d.querySelector('[data-action="'+id+'"]');assert.ok(button&&!button.disabled);
    const visible=()=>!button.hidden&&!button.closest('[hidden]');
    for(let page=0;!visible()&&page<20;page++){
     const next=Array.from(d.querySelectorAll('button')).find(n=>n.getAttribute('aria-label')==='Ações: próxima página'&&!n.disabled);assert.ok(next);next.click();await settle(w);
    }
    assert.ok(visible());button.click();await settle(w);
   }
   assert.deepEqual(view().state,check.expected);assert.equal(view().outcome,check.outcome);
   if(check.outcome==='success')assert.equal(d.querySelector('[data-visual-node="boat_water"]').getAttribute('y'),'75');
  }
  d.querySelector('#reset').click();await settle(w);assert.deepEqual(view().state,initial);
  assert.equal(d.querySelector('[data-visual-node="entry_blade"]').getAttribute('height'),'190');
  assert.equal(d.querySelectorAll('#rule-visual').length,1);
  assert.deepEqual(errors,[]);dom.window.close();
  console.log('PASS component scene '+p.source.visualProject.style+': schema, exact proof outcomes, keyboard guarded action, reactive geometry, reset and no JS errors');
 }
 const bad=JSON.parse(JSON.stringify(packet.presentations[0].source.visualProject));bad.instances[0].effects={nivel:2};assert.equal(schema(bad),false);
})().catch(e=>{console.error(e);process.exitCode=1;});
