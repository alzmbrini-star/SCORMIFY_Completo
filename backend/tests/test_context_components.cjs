const assert=require('node:assert/strict'),{execFileSync}=require('node:child_process'),path=require('node:path');
const {JSDOM,VirtualConsole}=require('../../frontend/node_modules/.pnpm/jsdom@16.7.0/node_modules/jsdom');
const Ajv=require('../../frontend/node_modules/.pnpm/ajv@8.20.0/node_modules/ajv');
const backend=path.resolve(__dirname,'..'),python=process.env.PYTHON_EXE||'C:/Users/AndréLuizZambrini/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe';
const packet=JSON.parse(execFileSync(python,['-c',`import sys,json
sys.path.insert(0,'tests')
from component_pilots import pilots
from services.component_scenes import project_schema
from services.rule_simulators import render_rules,validate_rules
items=[]
for style in ('studio','blueprint'):
 for raw in pilots(style):
  data=validate_rules(raw)
  items.append({'html':render_rules(raw),'project':data['visualProject'],'visual':data['visual'],'checks':data['checks']})
print(json.dumps({'schema':project_schema(),'items':items}))`],{cwd:backend,env:{...process.env,PYTHONPATH:backend,PYTHONIOENCODING:'utf-8'},maxBuffer:10000000}));
const schema=new Ajv({strict:false}).compile(packet.schema);
const settle=async w=>{for(let i=0;i<3;i++)await new Promise(r=>w.requestAnimationFrame(r));};
(async()=>{
 for(const p of packet.items){
  assert.ok(schema(p.project),JSON.stringify(schema.errors));
  const v1=JSON.parse(JSON.stringify(p.project));v1.catalogVersion=1;assert.equal(schema(v1),false);
  const errors=[],vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(String(e)));
  const dom=new JSDOM(p.html,{runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:vc,beforeParse(w){w.matchMedia=()=>({matches:true});}}),w=dom.window,d=w.document;
  await settle(w);const view=()=>JSON.parse(d.querySelector('#scormify-rule-view').textContent),initial=view().state;
  assert.ok(d.body.classList.contains('sim-didactic-scene'));
  for(const check of p.checks){
   d.querySelector('#reset').click();await settle(w);
   for(const id of check.actions){
    const hotspot=p.visual.nodes.find(n=>n.action===id);
    if(hotspot){
     const node=d.querySelector('[data-visual-node="'+hotspot.id+'"]');assert.equal(node.getAttribute('aria-disabled'),'false');
     node.dispatchEvent(new w.KeyboardEvent('keydown',{key:'Enter',bubbles:true}));
    }else{
     const button=d.querySelector('[data-action="'+id+'"]');assert.ok(button&&!button.disabled);
     const visible=()=>!button.hidden&&!button.closest('[hidden]');
     for(let page=0;!visible()&&page<20;page++){
      const next=Array.from(d.querySelectorAll('button')).find(n=>n.getAttribute('aria-label')==='Ações: próxima página'&&!n.disabled);assert.ok(next);next.click();await settle(w);
     }
     assert.ok(visible());button.click();
    }
    await settle(w);
   }
   assert.deepEqual(view().state,check.expected);assert.equal(view().outcome,check.outcome);
   const terminal=JSON.stringify(view().state);
   for(const node of d.querySelectorAll('#rule-visual [role="button"]')){assert.equal(node.getAttribute('aria-disabled'),'true');node.dispatchEvent(new w.KeyboardEvent('keydown',{key:'Enter',bubbles:true}));}
   await settle(w);assert.equal(JSON.stringify(view().state),terminal);
  }
  d.querySelector('#reset').click();await settle(w);assert.deepEqual(view().state,initial);
  assert.equal(d.querySelectorAll('#rule-visual').length,1);
  assert.deepEqual(errors,[]);dom.window.close();console.log('PASS contextual pilot '+p.project.title+' / '+p.project.style+': schema, keyboard, exact outcomes, terminal guards and reset');
 }
})().catch(e=>{console.error(e);process.exitCode=1;});
