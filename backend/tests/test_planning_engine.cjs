const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'../..');
const {createPlanningEngine}=require(path.join(root,'backend/services/export_assets/planning-engine.js'));
const {JSDOM,VirtualConsole}=require(path.join(root,'frontend/node_modules/.pnpm/jsdom@16.7.0/node_modules/jsdom'));
const data={title:'Montando Seu Cronograma — Gestão do Tempo',subtitle:'Priorize, planeje e compare as consequências.',mission:'Organize o trabalho da equipe sem atrasos, conflitos ou compressão irrealista de duração.',briefing:'Caso fictício: planeje um projeto de melhoria do atendimento. Revele o imprevisto após alocar duas tarefas.',debrief:'Que escolha reduziu os conflitos? Compare a versão inicial com o plano ajustado.',courseConnection:'Prioridades, estimativas realistas e planejamento no curso de Gestão do Tempo.',unit:'horas',horizon:16,
 resources:[{id:'equipe',label:'Equipe principal',capacity:1},{id:'apoio',label:'Apoio técnico',capacity:1}],
 tasks:[{id:'t1',label:'Diagnóstico das prioridades',description:'Levantar as necessidades antes de preparar o trabalho.',duration:2,due:5,priority:3,resourceId:'equipe',allowedResources:['equipe'],dependencies:[]},
 {id:'t2',label:'Preparação da proposta',description:'Preparar a proposta após o diagnóstico.',duration:3,due:11,priority:2,resourceId:'equipe',allowedResources:['equipe','apoio'],dependencies:['t1']},
 {id:'t3',label:'Verificação de informações',description:'Conferir os dados com apoio técnico.',duration:2,due:10,priority:1,resourceId:'apoio',allowedResources:['apoio'],dependencies:[]},
 {id:'t4',label:'Entrega revisada',description:'Consolidar a entrega após a preparação.',duration:2,due:15,priority:3,resourceId:'equipe',allowedResources:['equipe'],dependencies:['t2']}],
 event:{title:'Reunião urgente',message:'A equipe principal precisa atender uma demanda inesperada.',resourceId:'equipe',start:3,duration:2}};
function solve(engine){[['t1',0,'equipe'],['t2',2,'apoio'],['t3',5,'apoio'],['t4',5,'equipe']].forEach(([id,start,resourceId])=>assert.equal(engine.updateTask(id,{start,resourceId}).ok,true));}
const engine=createPlanningEngine(data);
assert.equal(engine.getState().metrics.coverage,0);
assert.equal(engine.finalize().ok,false);
assert.equal(engine.revealEvent().ok,false);
engine.updateTask('t1',{start:0});engine.updateTask('t2',{start:0});
assert.ok(engine.getState().metrics.overload>0);
assert.ok(engine.getState().metrics.violations.some(text=>text.includes('precisa começar')));
assert.equal(engine.revealEvent().ok,true);assert.equal(engine.revealEvent().ok,false);
solve(engine);assert.equal(engine.getState().metrics.score,100);assert.equal(engine.finalize().ok,true);assert.equal(engine.getState().report.success,true);
engine.saveSnapshot();const version=engine.getState().snapshots[0].id;
engine.updateTask('t4',{start:14});assert.equal(engine.getState().report,null);assert.equal(engine.getState().metrics.late,1);assert.ok(engine.compare(version).score<0);
engine.restoreSnapshot(version);assert.equal(engine.getState().metrics.success,true);
engine.updateTask('t1',{duration:1});assert.equal(engine.getState().metrics.quality,1);assert.equal(engine.getState().metrics.success,false);
engine.restoreSnapshot(version);engine.removeTask('t1');assert.equal(engine.getState().metrics.coverage,75);engine.finalize();assert.equal(engine.getState().report.success,false);
const before=engine.getState();assert.equal(engine.updateTask('t2',{start:7,duration:-1}).ok,false);assert.deepEqual(engine.getState(),before);
assert.equal(engine.updateTask('t2',{due:99}).ok,false);assert.equal(engine.updateTask('t1',{resourceId:'apoio'}).ok,false);
engine.reset();assert.equal(engine.getState().eventActive,false);assert.equal(engine.getState().snapshots.length,0);assert.equal(engine.getState().history.length,0);
engine.updateTask('t1',{start:0});engine.updateTask('t2',{start:5});engine.saveSnapshot();const preEvent=engine.getState().snapshots[0].id;engine.revealEvent();engine.restoreSnapshot(preEvent);assert.equal(engine.getState().eventActive,true);
const state=engine.getState();state.tasks[0].duration=99;assert.notEqual(engine.getState().tasks[0].duration,99);
const multiData=JSON.parse(JSON.stringify(data));multiData.resources[0].capacity=3;
const multi=createPlanningEngine(multiData);multi.updateTask('t1',{start:2});multi.updateTask('t2',{start:5,resourceId:'apoio'});assert.equal(multi.getState().metrics.overload,0);multi.revealEvent();assert.ok(multi.getState().metrics.overload>0,'The event must reserve the resource even when its capacity exceeds one');
for(const theme of ['Manutenção Industrial','Organização de Eventos','Produção de Conteúdo']){const alternate=createPlanningEngine({...data,title:theme});solve(alternate);alternate.revealEvent();assert.equal(alternate.getState().metrics.success,true);}
const assets=path.join(root,'backend/services/export_assets');
const html=fs.readFileSync(path.join(assets,'planning-simulator.html'),'utf8').replace('__PLANNING_DATA__',JSON.stringify(data).replace(/</g,'\\u003c')).replace('__PLANNING_ENGINE__',fs.readFileSync(path.join(assets,'planning-engine.js'),'utf8'));
const errors=[];const virtualConsole=new VirtualConsole();virtualConsole.on('jsdomError',error=>errors.push(String(error)));
const dom=new JSDOM(html,{runScripts:'dangerously',pretendToBeVisual:true,virtualConsole});
const doc=dom.window.document;
function click(id){doc.getElementById(id).click();}
function selectTask(index){doc.querySelectorAll('#tasks button')[index].click();}
function set(id,value){const field=doc.getElementById(id);field.value=String(value);field.dispatchEvent(new dom.window.Event('change',{bubbles:true}));}
assert.equal(doc.getElementById('coverage').textContent,'0/4');assert.equal(doc.getElementById('include').disabled,true);
selectTask(0);click('include');assert.equal(doc.getElementById('coverage').textContent,'1/4');assert.equal(doc.getElementById('remove').disabled,false);
selectTask(1);set('start',2);set('resource','apoio');click('include');click('reveal');assert.ok(doc.getElementById('event').textContent.includes('Reunião urgente'));
selectTask(2);set('start',5);click('include');selectTask(3);set('start',5);click('include');
assert.equal(doc.getElementById('score').textContent,'100%');click('save');assert.ok(doc.getElementById('versions').value);click('finalize');assert.ok(doc.getElementById('report').textContent.includes('Plano viável'));
set('duration',1);assert.ok(doc.getElementById('report').hidden);assert.ok(Number.parseInt(doc.getElementById('score').textContent)<100);click('restore');assert.equal(doc.getElementById('score').textContent,'100%');
doc.getElementById('extraName').value='<img src=x onerror=alert(1)>';click('addExtra');assert.equal(doc.querySelectorAll('img').length,0);assert.ok(doc.getElementById('tasks').textContent.includes('<img src=x'));
click('reset');assert.equal(doc.getElementById('coverage').textContent,'0/4');assert.equal(doc.getElementById('versions').options.length,1);assert.equal(doc.getElementById('include').disabled,true);
assert.deepEqual(errors,[]);dom.window.close();
if(process.argv[2])fs.writeFileSync(path.resolve(process.argv[2]),html);
console.log('Planning engine: causal calculations, constraints, partial outcomes, recovery, snapshots, reset, theme-independent data and actual DOM controls passed.');
