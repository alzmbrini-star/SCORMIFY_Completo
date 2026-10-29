const assert=require('node:assert/strict'),{execFileSync}=require('node:child_process'),path=require('node:path');
const {JSDOM,VirtualConsole}=require('../../frontend/node_modules/.pnpm/jsdom@16.7.0/node_modules/jsdom');
const python=process.env.RULE_TEST_PYTHON||'C:/Users/AndréLuizZambrini/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe';
const backend=path.resolve(__dirname,'..');
const pages=JSON.parse(execFileSync(python,['-c',`import sys,json
sys.path.insert(0,'tests')
from test_rule_visuals import lock_fixture
from services.rule_simulators import render_rules,validate_rules
from services.simulator_experience import normalize_experience,options
result=[]
for level in ['guided','applied','advanced']:
 raw=lock_fixture();raw['variables'][-1]['unit']='flag'
 raw['experience']=normalize_experience({'stateLabels':{'entrada':{'0':'Fechada','1':'Aberta'}}},raw,options(level))
 data=validate_rules(raw)
 result.append(dict(level=level,html=render_rules(data),checks=data['checks']))
print(json.dumps(result))`],{cwd:backend,env:{...process.env,PYTHONPATH:backend},maxBuffer:5000000}).toString());
const settle=async w=>{for(let i=0;i<4;i++)await new Promise(r=>w.requestAnimationFrame(r));};
(async()=>{for(const page of pages){
 const errors=[],vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(String(e)));
 const dom=new JSDOM(page.html,{runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:vc,beforeParse(w){w.matchMedia=()=>({matches:true});}}),w=dom.window,d=w.document;
 await settle(w);assert.ok(d.body.classList.contains('sim-exp-'+page.level));
 const visibleMetrics=()=>Array.from(d.querySelectorAll('#metrics>.metric')).filter(n=>!n.hidden);
 assert.equal(visibleMetrics().length,page.level==='guided'?2:page.level==='applied'?3:5);
 assert.ok(d.querySelector('#metrics').textContent.includes('Fechada'));
 assert.ok(!d.querySelector('#metrics').textContent.includes('0 flag'));
 assert.equal(Array.from(d.querySelectorAll('.sim-tools button')).some(b=>b.textContent==='Histórico'),page.level!=='guided');
 if(page.level!=='advanced')for(const card of d.querySelectorAll('#actions>.action'))if(!card.hidden)assert.ok(!card.querySelector('[data-action]').disabled);
 const details=Array.from(d.querySelectorAll('.sim-tools button')).find(b=>b.textContent==='Detalhes');details.click();await settle(w);
 Array.from(d.querySelectorAll('.sim-dialog-body button')).find(b=>b.textContent==='Todos os indicadores').click();await settle(w);
 assert.equal(visibleMetrics().length,5);assert.ok(d.querySelector('.sim-dialog-body #metrics'));
 d.querySelector('.sim-dialog-head button').click();await settle(w);
 assert.equal(visibleMetrics().length,page.level==='guided'?2:page.level==='applied'?3:5);
 for(const check of page.checks){d.querySelector('#reset').click();await settle(w);for(const id of check.actions){const b=d.querySelector('[data-action="'+id+'"]');assert.ok(!b.disabled);b.click();await settle(w);}const view=JSON.parse(d.querySelector('#scormify-rule-view').textContent);assert.deepEqual(view.state,check.expected);assert.equal(view.outcome,check.outcome);if(d.querySelector('dialog').open)d.querySelector('.sim-dialog-head button').click();}
 d.querySelector('#reset').click();await settle(w);assert.ok(d.querySelector('#counter').textContent.includes('Decisão 0'));
 assert.equal(d.querySelectorAll('#metrics').length,1);assert.deepEqual(errors,[]);dom.window.close();
 console.log('PASS experience '+page.level+': density, statuses, detail dialogs, original outcomes and reset');
}})().catch(e=>{console.error(e);process.exitCode=1;});
