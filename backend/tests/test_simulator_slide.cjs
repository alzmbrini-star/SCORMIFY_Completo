const assert=require('node:assert/strict');
const {execFileSync}=require('node:child_process');
const path=require('node:path');
const {JSDOM,VirtualConsole}=require('../../frontend/node_modules/.pnpm/jsdom@16.7.0/node_modules/jsdom');
const python=process.env.RULE_TEST_PYTHON || 'C:/Users/AndréLuizZambrini/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe';
const backend=path.resolve(__dirname,'..');
const pages=JSON.parse(execFileSync(python,['-c',`import sys,json
sys.path.insert(0,'tests')
from test_rule_simulators import fixtures
from test_planning_simulators import fixture
from services.rule_simulators import render_rules,validate_rules
from services.planning_simulators import render_planning
print(json.dumps({'rule':render_rules(fixtures()[0]),'planning':render_planning(fixture()),'checks':validate_rules(fixtures()[0])['checks']}))`],{cwd:backend,env:{...process.env,PYTHONPATH:backend},maxBuffer:3000000}).toString());
async function settle(win){for(let i=0;i<3;i++)await new Promise(resolve=>win.requestAnimationFrame(resolve));}
async function run(){
 for(const type of ['rule','planning']){
  const errors=[],vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(String(e)));
  const dom=new JSDOM(pages[type],{runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:vc}),win=dom.window,doc=win.document;
  await settle(win);
  assert.ok(doc.querySelector('#sim-slide-shell'));
  assert.equal(doc.querySelectorAll('#sim-slide-shell').length,1);
  assert.ok(doc.querySelector('#sim-slide-sources').hidden);
  const context=Array.from(doc.querySelectorAll('.sim-tools button')).find(b=>b.textContent==='Objetivo');
  context.click();assert.ok(doc.querySelector('dialog').hasAttribute('open'));assert.ok(doc.querySelector('#sim-slide-shell').hasAttribute('inert'));
  assert.ok(doc.querySelector('.sim-dialog-body').textContent.length>40);
  doc.querySelector('.sim-dialog-head button').click();assert.equal(doc.querySelector('dialog').hasAttribute('open'),false);
  if(type==='rule'){
   for(const key of pages.checks[0].actions){doc.querySelector('[data-action="'+key+'"]').click();await settle(win);}
   assert.ok(doc.querySelector('dialog').hasAttribute('open'));
   assert.ok(doc.querySelector('.sim-dialog-body').textContent.includes('As condições do objetivo'));
   doc.querySelector('.sim-dialog-head button').click();doc.querySelector('#reset').click();await settle(win);
   assert.ok(doc.querySelector('#counter').textContent.includes('Decisão 0'));
   assert.equal(doc.querySelector('#history').children.length,0);
   const versions=Array.from(doc.querySelectorAll('.sim-tools button')).find(b=>b.textContent==='Versões');versions.click();doc.querySelector('#save').click();await settle(win);
   assert.equal(doc.querySelector('#snapshots').options.length,2);doc.querySelector('.sim-dialog-head button').click();
   assert.equal(doc.querySelectorAll('#save').length,1);
  }else{
   doc.querySelector('#tasks button').click();doc.querySelector('#include').click();await settle(win);
   assert.equal(doc.querySelector('#coverage').textContent,'1/4');
   assert.ok(doc.querySelector('.metric').getAttribute('aria-label').includes('1/4'));
   assert.equal(doc.querySelector('label[for="start"]').textContent.trim(),'Início no calendário');
   const tabs=doc.querySelector('.sim-tabs');tabs.querySelectorAll('button')[1].click();await settle(win);
   assert.equal(tabs.querySelectorAll('button')[1].getAttribute('aria-selected'),'true');
   const versions=Array.from(doc.querySelectorAll('.sim-tools button')).find(b=>b.textContent==='Versões');versions.click();doc.querySelector('#save').click();await settle(win);
   assert.equal(doc.querySelector('#versions').options.length,2);doc.querySelector('.sim-dialog-head button').click();
   assert.equal(doc.querySelectorAll('#start').length,1);assert.equal(doc.querySelectorAll('#versions').length,1);
   doc.querySelector('#reset').click();await settle(win);assert.equal(doc.querySelector('#coverage').textContent,'0/4');
   assert.equal(tabs.querySelectorAll('button')[0].getAttribute('aria-selected'),'true');
  }
  assert.deepEqual(errors,[]);
  dom.window.close();console.log('PASS slide presentation: '+type+' — original controls, dialogs, focus, versions, outcome and reset preserved');
 }
}
run().catch(error=>{console.error(error);process.exitCode=1;});
