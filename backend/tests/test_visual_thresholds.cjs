const assert=require('node:assert/strict'),path=require('node:path'),{execFileSync}=require('node:child_process');
const {JSDOM,VirtualConsole}=require('../../frontend/node_modules/.pnpm/jsdom@16.7.0/node_modules/jsdom');
const backend=path.resolve(__dirname,'..'),python='C:/Users/AndréLuizZambrini/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe';
const html=execFileSync(python,['-c',`from test_visual_thresholds import threshold_scene
from test_process_demo import process_demo
from services.rule_simulators import validate_rules,render_rules
from services.simulator_experience import normalize_experience,options
p=process_demo();p['visual']=threshold_scene();p=validate_rules(p)
p['experience']=normalize_experience({},p,options());print(render_rules(p))`],{cwd:backend,env:{...process.env,PYTHONPATH:backend+';'+path.join(backend,'tests'),PYTHONIOENCODING:'utf-8'},maxBuffer:3000000}).toString();
(async()=>{const errors=[],vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(String(e)));
 const dom=new JSDOM(html,{runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:vc,beforeParse(w){w.matchMedia=()=>({matches:true});}}),d=dom.window.document;
 await new Promise(r=>setTimeout(r,30));const piece=d.querySelector('[data-visual-node="piece"]');
 assert.equal(Number(piece.getAttribute('opacity')),0);
 d.querySelector('[data-action="avancar"]').click();assert.equal(Number(piece.getAttribute('opacity')),0);
 d.querySelector('[data-action="avancar"]').click();assert.equal(Number(piece.getAttribute('opacity')),1);
 assert.equal(JSON.parse(d.getElementById('scormify-rule-view').textContent).outcome,'success');
 assert.ok(![...piece.attributes].some(a=>/NaN|Infinity/.test(a.value)));
 d.getElementById('reset').click();assert.equal(Number(piece.getAttribute('opacity')),0);
 assert.deepEqual(errors,[]);dom.window.close();console.log('PASS guided step threshold: boundary, finite rendering, original outcome and reset');
})().catch(e=>{console.error(e);process.exitCode=1});
