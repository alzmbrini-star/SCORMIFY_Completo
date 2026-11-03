const assert=require('node:assert/strict'),path=require('node:path'),{execFileSync}=require('node:child_process');
const {JSDOM,VirtualConsole}=require('../../frontend/node_modules/.pnpm/jsdom@16.7.0/node_modules/jsdom');
const python='C:/Users/AndréLuizZambrini/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe',backend=path.resolve(__dirname,'..');
const html=execFileSync(python,['-c',`from tests.test_process_demo import process_demo
from tests.test_visual_fidelity import scene
from services.rule_simulators import validate_rules,render_rules
from services.simulator_experience import normalize_experience,options
p=validate_rules(process_demo());p['visual']=scene(True);p['visual']['nodes'][0]['label']='Peça principal';p['visual']['nodes'][0]['explanation']='Recebe o movimento ilustrativo.'
p['experience']=normalize_experience({},p,options());print(render_rules(p))`],{cwd:backend,env:{...process.env,PYTHONIOENCODING:'utf-8',PYTHONPATH:backend+';'+path.join(backend,'tests')},maxBuffer:5000000}).toString();
async function main(){const errors=[],vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(String(e)));
 const dom=new JSDOM(html,{runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:vc,beforeParse(w){w.matchMedia=()=>({matches:true});}}),d=dom.window.document;
 await new Promise(r=>setTimeout(r,40));const state=d.getElementById('scormify-rule-view').textContent;
 const trigger=[...d.querySelectorAll('button')].find(b=>b.textContent==='Objetos e legendas');assert.ok(trigger);trigger.click();
 const panel=d.querySelector('.sim-object-legend');assert.equal(panel.hidden,false);
 assert.equal(panel.closest('#sim-slide-sources'),null,'legend survives slide-shell source relocation');
 const first=panel.querySelector('[data-legend-object="part_0"]');first.focus();
 assert.match(panel.textContent,/Recebe o movimento ilustrativo/);assert.equal(first.getAttribute('aria-pressed'),'true');
 assert.equal(d.querySelector('[data-visual-node="part_0"]').dataset.legendSelected,'true');assert.equal(d.querySelector('.sim-object-name').textContent,'Peça principal');
 panel.querySelector('[data-legend-object="part_1"]').click();assert.equal(first.getAttribute('aria-pressed'),'false');
 assert.equal(d.getElementById('scormify-rule-view').textContent,state,'legend must not invoke simulation actions');
 panel.dispatchEvent(new dom.window.KeyboardEvent('keydown',{key:'Escape',bubbles:true}));assert.equal(panel.hidden,true);assert.equal(d.activeElement,trigger);
 d.getElementById('reset').click();assert.equal(d.querySelector('.sim-object-name').hidden,true);assert.equal(d.querySelector('[data-legend-object="part_1"]').getAttribute('aria-pressed'),'false');
 assert.deepEqual(errors,[]);dom.window.close();process.stdout.write('PASS object legend: all named objects, keyboard, explanation, highlight, no logical changes, close focus and reset\n');}
main().catch(e=>{console.error(e);process.exitCode=1});
