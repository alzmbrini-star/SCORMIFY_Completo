/* Cross-runtime parity, real controls and reset tests for five rule topologies. */
const assert=require('node:assert/strict');
const {execFileSync}=require('node:child_process');
const path=require('node:path');
const {createRuleEngine}=require('../services/export_assets/rule-engine.js');
const {JSDOM}=require('../../frontend/node_modules/.pnpm/jsdom@16.7.0/node_modules/jsdom');
const python=process.env.RULE_TEST_PYTHON || 'C:/Users/AndréLuizZambrini/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe';
const backend=path.resolve(__dirname,'..');
const fixtures=JSON.parse(execFileSync(python,['-c',`import json,sys
sys.path.insert(0,'tests')
from test_rule_simulators import fixtures
from services.rule_simulators import *
out=[]
source=fixtures()
if len(sys.argv)>1:
 with open(sys.argv[1],encoding='utf-8-sig') as file: diagnostic=json.load(file)
 record=next(r for r in diagnostic['records'] if r['status']=='accepted' and r['result']['spec'].get('mechanic')==ENGINE)
 source=[record['result']['spec']]
 assert record['result']['html']==render_rules(source[0]), 'Downloaded HTML differs from the trusted compiler'
for raw in source:
 data=validate_rules(raw)
 paths=[]
 for check in data['checks']:
  state={v['id']:v['initial'] for v in data['variables']};states=[]
  for key in check['actions']:
   state=transition(data,state,next(a for a in data['actions'] if a['id']==key));states.append(state)
  paths.append(dict(check,states=states))
 out.append(dict(data=data,paths=paths,html=render_rules(data)))
print(json.dumps(out))`,...process.argv.slice(2)],{cwd:backend,env:{...process.env,PYTHONPATH:backend},maxBuffer:3000000}).toString());
for (const fixture of fixtures) {
 const engine=createRuleEngine(fixture.data),initial=engine.getState();let notifications=0;
 const unsub=engine.subscribe(()=>notifications++);
 assert.equal(initial.outcome,'active');assert.ok(initial.actions.filter(a=>a.enabled).length>=2);
 assert.equal(engine.act('missing').ok,false);
 const blocked=initial.actions.find(a=>!a.enabled);
 if(blocked){assert.equal(engine.act(blocked.id).ok,false);assert.deepEqual(engine.getState().state,initial.state);}
 for(const check of fixture.paths){
   engine.reset();
   for(let i=0;i<check.actions.length;i++){
     assert.equal(engine.act(check.actions[i]).ok,true,fixture.data.title+': '+check.actions[i]);
     assert.deepEqual(engine.getState().state,check.states[i]);
   }
   assert.equal(engine.getState().outcome,check.outcome);
   assert.equal(engine.act(check.actions[0]).ok,false,'Terminal state must lock actions');
 }
 engine.reset();const id=engine.saveSnapshot();const key=fixture.paths[0].actions[0];engine.act(key);
 assert.ok(engine.compare(id).some(v=>v.delta!==0));
 const copy=engine.getState();copy.state[fixture.data.variables[0].id]=999;
 assert.notEqual(engine.getState().state[fixture.data.variables[0].id],999);
 engine.reset();assert.deepEqual(engine.getState().state,initial.state);assert.equal(engine.getState().history.length,0);assert.equal(engine.getState().snapshots.length,0);assert.ok(notifications>0);unsub();
 const deadlock=JSON.parse(JSON.stringify(fixture.data));deadlock.actions.forEach(a=>{a.requires=false;});
 assert.equal(createRuleEngine(deadlock).getState().outcome,'failure');
 const dom=new JSDOM(fixture.html,{runScripts:'dangerously'}),doc=dom.window.document;
 assert.equal(doc.querySelector('h1').textContent,fixture.data.title);
 for(const action of fixture.paths[0].actions){
   const button=doc.querySelector('[data-action="'+action+'"]');assert.ok(button&&!button.disabled,action);button.click();
 }
 assert.equal(doc.querySelector('#result').classList.contains('hidden'),false);
 assert.equal(doc.querySelector('#resultTitle').textContent,'Objetivo alcançado');
 assert.equal(doc.querySelectorAll('#history li').length,fixture.paths[0].actions.length);
 doc.querySelector('#reset').click();assert.equal(doc.querySelectorAll('#history li').length,0);
 assert.equal(doc.querySelector('#result').classList.contains('hidden'),true);
 doc.querySelector('#save').click();assert.equal(doc.querySelector('#snapshots').options.length,2);
 doc.querySelector('[data-action="'+fixture.paths[0].actions[0]+'"]').click();
 assert.ok(doc.querySelector('#comparison').textContent.length>0);
 dom.window.close();
 console.log('PASS: '+fixture.data.title+' — Python/JS state parity, terminal outcomes, DOM controls, comparison and reset');
}
