const assert=require('node:assert/strict'),path=require('node:path'),{execFileSync}=require('node:child_process');
const {JSDOM,VirtualConsole}=require('../../frontend/node_modules/.pnpm/jsdom@16.7.0/node_modules/jsdom');
const python='C:/Users/AndréLuizZambrini/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe';
const backend=path.resolve(__dirname,'..');
const html=execFileSync(python,['-c',`from tests.test_process_demo import process_demo
from tests.test_visual_fidelity import scene
from services.rule_simulators import validate_rules,render_rules
from services.simulator_experience import normalize_experience,options
p=validate_rules(process_demo());p['visual']=scene(True);p['experience']=normalize_experience({},p,options())
print(render_rules(p))`],{cwd:backend,env:{...process.env,PYTHONIOENCODING:'utf-8',PYTHONPATH:backend+';'+path.join(backend,'tests')},maxBuffer:5000000}).toString();
async function main(){
 const errors=[],vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(String(e)));
 const dom=new JSDOM(html,{runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:vc,beforeParse(w){w.matchMedia=()=>({matches:true});}});
 const d=dom.window.document;await new Promise(r=>setTimeout(r,80));
 assert.ok(d.body.classList.contains('sim-comp-immersive'));
 assert.equal(d.querySelector('.sim-metric-strip').hidden,true);
 assert.ok(d.querySelector('.sim-compact-controls [data-action="avancar"]'));
 assert.match(d.querySelector('.sim-counter').textContent,/Etapa 0/);
 for(let i=0;i<2;i++){const b=d.querySelector('[data-action="avancar"]');assert.equal(b.disabled,false);b.click();await new Promise(r=>setTimeout(r,60));}
 assert.equal(d.querySelector('.sim-dialog-title')?.textContent||d.querySelector('#sim-dialog-title').textContent,'Demonstração concluída');
 assert.equal(d.querySelector('.sim-compact-controls').hidden,true);
 d.querySelector('.sim-dialog-head button').click();d.getElementById('reset').click();await new Promise(r=>setTimeout(r,60));
 assert.equal(d.querySelector('.sim-compact-controls').hidden,false);
 assert.equal(d.querySelector('[data-action="avancar"]').disabled,false);
 assert.deepEqual(errors,[]);dom.window.close();
 process.stdout.write('PASS immersive demonstration: no forced metrics, compact controls, neutral ending, restart and no JS errors\n');
}
main().catch(e=>{console.error(e);process.exitCode=1});
