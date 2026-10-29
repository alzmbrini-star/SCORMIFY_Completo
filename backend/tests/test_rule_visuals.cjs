const assert=require('node:assert/strict');
const {execFileSync}=require('node:child_process');
const path=require('node:path');
const {JSDOM,VirtualConsole}=require('../../frontend/node_modules/.pnpm/jsdom@16.7.0/node_modules/jsdom');
const python=process.env.RULE_TEST_PYTHON || 'C:/Users/AndréLuizZambrini/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe';
const backend=path.resolve(__dirname,'..');
const cases=JSON.parse(execFileSync(python,['-c',`import sys,json
sys.path.insert(0,'tests')
from test_rule_visuals import lock_fixture,sales_visual
from test_rule_simulators import fixtures
from services.rule_simulators import render_rules,validate_rules
from services.rule_visuals import visual_state
out=[]
for raw in [lock_fixture(),sales_visual(),fixtures()[3]]:
 data=validate_rules(raw)
 out.append(dict(html=render_rules(data),spec=data,expected=[visual_state(data['visual'],c['expected']) for c in data['checks']] if 'visual' in data else []))
print(json.dumps(out))`],{cwd:backend,env:{...process.env,PYTHONPATH:backend},maxBuffer:5000000}).toString());
const settle=async w=>{for(let i=0;i<3;i++)await new Promise(resolve=>w.requestAnimationFrame(resolve));};
async function run(){
 for(let index=0;index<cases.length;index++){
  const item=cases[index],errors=[],console=new VirtualConsole();console.on('jsdomError',e=>errors.push(String(e)));
  const dom=new JSDOM(item.html,{runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:console,beforeParse(w){w.matchMedia=()=>({matches:true});}}),w=dom.window,d=w.document;
  await settle(w);
  const visual=d.querySelector('#rule-visual');assert.ok(d.querySelector('.sim-main .sim-rule-visual'));
  const zoom=Array.from(d.querySelectorAll('button')).find(b=>b.textContent==='Ampliar');assert.ok(zoom);zoom.click();
  assert.ok(d.querySelector('.sim-dialog-body #rule-visual'));assert.equal(d.querySelectorAll('#rule-visual').length,1);
  d.querySelector('.sim-dialog-head button').click();assert.ok(d.querySelector('.sim-main #rule-visual'));
  assert.equal(visual.dataset.visualMode,index<2?'illustrated':'conceptual');
  assert.equal(d.querySelectorAll('#rule-visual').length,1);
  assert.equal(visual.querySelectorAll('script,image,foreignObject').length,0);
  for(let ci=0;ci<item.spec.checks.length;ci++){
    d.querySelector('#reset').click();await settle(w);
    for(const action of item.spec.checks[ci].actions){
      const button=d.querySelector('[data-action="'+action+'"]');assert.ok(!button.disabled);
      if(index===0&&action==='abrir_entrada')d.querySelector('[data-visual-node="gate_in"]').dispatchEvent(new w.KeyboardEvent('keydown',{key:'Enter',bubbles:true}));else button.click();
      await settle(w);
    }
    const view=JSON.parse(d.querySelector('#scormify-rule-view').textContent);
    assert.deepEqual(view.state,item.spec.checks[ci].expected);
    assert.equal(view.outcome,item.spec.checks[ci].outcome);
    if(item.expected[ci])for(const projected of item.expected[ci]){
      const element=d.querySelector('[data-visual-node="'+projected.id+'"]');assert.ok(element,projected.id);
      assert.equal(element.style.display==='none',!projected.visible,projected.id);
      if(projected.attrs.text!==undefined)assert.ok(element.textContent.includes(projected.attrs.text));
      for(const [key,value] of Object.entries(projected.attrs)){
        if(typeof value!=='number'||key==='rotation'||element.tagName==='g')continue;
        const name=({strokeWidth:'stroke-width',fontSize:'font-size',fontWeight:'font-weight'})[key]||(['circle','ellipse'].includes(element.tagName)&&key==='x'?'cx':['circle','ellipse'].includes(element.tagName)&&key==='y'?'cy':key);
        assert.ok(Math.abs(Number(element.getAttribute(name))-value)<0.001,projected.id+'.'+key);
      }
    }
    const dialog=d.querySelector('dialog');if(dialog.hasAttribute('open'))d.querySelector('.sim-dialog-head button').click();
  }
  d.querySelector('#reset').click();await settle(w);
  if(index===0){
    assert.equal(d.querySelector('[data-visual-node="agua_camara"]').getAttribute('y'),'330');
    assert.equal(d.querySelector('[data-visual-node="barco_grupo"]').getAttribute('transform'),'translate(30 310) rotate(0)');
    assert.equal(d.querySelector('[data-visual-node="gate_in"]').getAttribute('aria-disabled'),'false');
    // Cancel a movement mid-animation; reset must not be overwritten later.
    w.matchMedia=()=>({matches:false});d.querySelector('[data-action="abrir_entrada"]').click();d.querySelector('#reset').click();
    await new Promise(resolve=>w.setTimeout(resolve,500));
    assert.equal(d.querySelector('[data-visual-node="gate_in"]').getAttribute('height'),'200');
    assert.equal(JSON.parse(d.querySelector('#scormify-rule-view').textContent).steps,0);
  }
  assert.deepEqual(errors,[]);dom.window.close();
  process.stdout.write('PASS reactive visual: '+item.spec.title+' — actual state, keyboard, outcomes, reset, no external assets\n');
 }
}
run().catch(e=>{console.error(e);process.exitCode=1;});
