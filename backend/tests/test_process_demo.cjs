const assert=require('node:assert/strict'),path=require('node:path'),{execFileSync}=require('node:child_process');
const {JSDOM,VirtualConsole}=require('../../frontend/node_modules/.pnpm/jsdom@16.7.0/node_modules/jsdom');
const python='C:/Users/AndréLuizZambrini/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe';
const backend=path.resolve(__dirname,'..');
const html=execFileSync(python,['-c',`from tests.test_rule_visuals import lock_fixture
from services.rule_simulators import render_rules,PROCESS_DEMO
p=lock_fixture();p['didacticMode']=PROCESS_DEMO;p['experience']={'complexity':'guided','visualStyle':'illustrated'}
print(render_rules(p))`],{cwd:backend,env:{...process.env,PYTHONIOENCODING:'utf-8',PYTHONPATH:backend+';'+path.join(backend,'tests')},maxBuffer:5000000}).toString();
const errors=[],console=new VirtualConsole();console.on('jsdomError',e=>errors.push(String(e)));
const dom=new JSDOM(html,{runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:console,beforeParse(w){w.matchMedia=()=>({matches:true});}});
const d=dom.window.document;
assert.ok(d.querySelector('#process-art-finish'));
assert.equal(d.querySelector('#rule-visual').dataset.artFinish,'soft-volume');
assert.match(d.querySelector('[data-visual-node="casco"]').getAttribute('fill'),/^url\(#process-paint-/);
assert.equal(d.querySelector('[data-action="abrir_saida"]').disabled,true);
for(const action of ['abrir_entrada','entrar','fechar','elevar','abrir_saida','sair']){
 const b=d.querySelector('[data-action="'+action+'"]');assert.ok(!b.disabled,action);b.click();
}
assert.match(d.querySelector('#rule-visual figcaption').textContent,/Demonstração didática simplificada/);
assert.equal(d.querySelector('[data-visual-node="gate_in"]').getAttribute('height'),'200');
const count=d.querySelectorAll('#process-art-finish stop').length;
d.getElementById('reset').click();
assert.equal(d.querySelectorAll('#process-art-finish stop').length,count);
assert.equal(d.querySelector('[data-action="abrir_saida"]').disabled,true);
assert.deepEqual(errors,[]);dom.window.close();
process.stdout.write('PASS process demo: soft-volume finish, guarded actions, full path, reset, stable defs and no JS errors\n');
