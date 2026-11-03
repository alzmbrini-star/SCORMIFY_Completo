const assert=require('node:assert/strict'),path=require('node:path'),{execFileSync}=require('node:child_process');
const {JSDOM,VirtualConsole}=require('../../frontend/node_modules/.pnpm/jsdom@16.7.0/node_modules/jsdom');
const python='C:/Users/AndréLuizZambrini/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe',backend=path.resolve(__dirname,'..');
function render(mode){return execFileSync(python,['-c',`from tests.test_process_demo import process_demo
from tests.test_visual_fidelity import scene
from services.rule_simulators import validate_rules,render_rules
from services.simulator_experience import normalize_experience,options
p=validate_rules(process_demo());p['visual']=scene(True)
if '${mode}'=='rotation':
 for n in p['visual']['nodes']:
  for b in n.get('bindings',[]):b['output']=[0,360 if b['output'][1]>0 else -360]
if '${mode}'=='declared':p['visual']['motions']=[dict(node='part_0',kind='translate',cx=0,cy=0,dx=40,dy=20,cycles=1,phase=0)]
if '${mode}'=='polygon':p['visual']['motions']=[dict(node='part_0_body',kind='translate',cx=0,cy=0,dx=40,dy=20,cycles=1,phase=0)]
if '${mode}'=='orbit':p['visual']['motions']=[dict(node='part_0',kind='orbit',cx=120,cy=225,dx=50,dy=30,cycles=1,phase=0)]
if '${mode}'=='branched':p['actions'].append(dict(p['actions'][0],id='alternative',effects={'etapa':2}))
p['experience']=normalize_experience({},p,options());print(render_rules(p))`],{cwd:backend,env:{...process.env,PYTHONIOENCODING:'utf-8',PYTHONPATH:backend+';'+path.join(backend,'tests')},maxBuffer:5000000}).toString();}
async function check(reduced,mode='rotation'){
 const frames=new Map(),errors=[],vc=new VirtualConsole();let sequence=0,clock=0;
 vc.on('jsdomError',e=>errors.push(String(e)));
 const dom=new JSDOM(render(mode),{runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:vc,beforeParse(w){w.matchMedia=()=>({matches:reduced});w.requestAnimationFrame=fn=>{frames.set(++sequence,fn);return sequence;};w.cancelAnimationFrame=id=>frames.delete(id);}});
 const d=dom.window.document;await new Promise(r=>setTimeout(r,0));
 function advance(){clock+=100;const pending=[...frames.values()];frames.clear();pending.forEach(fn=>fn(clock));}
 advance();const piece=d.querySelector('[data-visual-node="'+(mode==='polygon'?'part_0_body':'part_0')+'"]');
 if(mode==='branched'){assert.equal(d.querySelector('.sim-motion-tools'),null,'never choose a learner decision automatically');dom.window.close();return;}
 const initial=piece.getAttribute('transform'),state=d.getElementById('scormify-rule-view').textContent;
 for(let i=0;i<47;i++)advance();
 if(reduced){assert.equal(piece.getAttribute('transform'),initial);d.querySelector('.sim-motion-tools button').click();advance();for(let i=0;i<8;i++)advance();}
 assert.notEqual(piece.getAttribute('transform'),initial,'motion must continue past the old 420ms transition');
 assert.equal(d.getElementById('scormify-rule-view').textContent,state,'animation must not spend steps or mutate outcomes');
 d.querySelector('.sim-motion-tools button').click();const paused=piece.getAttribute('transform');for(let i=0;i<8;i++)advance();assert.equal(piece.getAttribute('transform'),paused);
 assert.equal(d.querySelector('.sim-motion-tools button').textContent,'Reproduzir movimento');
 d.getElementById('reset').click();advance();assert.match(piece.getAttribute('transform'),/rotate\(0\)/);
 assert.equal(d.querySelector('.sim-motion-tools select').getAttribute('aria-label'),'Velocidade do movimento');
 dom.window.dispatchEvent(new dom.window.Event('pagehide'));assert.equal(frames.size,0);
 assert.deepEqual(errors,[]);dom.window.close();
}
check(false).then(()=>check(true)).then(()=>check(false,'timeline')).then(()=>check(false,'declared')).then(()=>check(false,'polygon')).then(()=>check(false,'orbit')).then(()=>check(false,'branched')).then(()=>process.stdout.write('PASS continuous illustration: rotation, click-authored replay, orbital and whole-shape translation, no logical changes or automatic decisions, pause/reset, reduced motion and cleanup\n')).catch(e=>{console.error(e);process.exitCode=1});
