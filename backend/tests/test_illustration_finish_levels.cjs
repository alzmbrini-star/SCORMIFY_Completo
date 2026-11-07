const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
const {JSDOM,VirtualConsole}=require('../../frontend/node_modules/.pnpm/jsdom@16.7.0/node_modules/jsdom');
const runtime=fs.readFileSync(path.resolve(__dirname,'../../frontend/src/components/games/ruleVisualRuntime.js'),'utf8').replace('export function','function');
for(const complexity of ['guided','applied','advanced'])for(const visualStyle of ['illustrated','technical']){
 const data={variables:[{id:'step',min:0,max:1,initial:0}],actions:[],experience:{complexity,visualStyle},visual:{version:1,title:'Assunto original',description:'Componente em destaque',background:'#edf7fb',nodes:[
  {id:'background',type:'rect',label:'Ambiente',attrs:{x:0,y:0,width:800,height:450,fill:'#eaf4fa'}},
  {id:'piece',type:'group',label:'Componente',attrs:{x:300,y:200}},
  {id:'body',type:'rect',parent:'piece',label:'Corpo',attrs:{x:0,y:0,width:120,height:80,fill:'#94aabb'}},
  {id:'detail',type:'circle',parent:'piece',label:'Conexão',attrs:{x:40,y:40,r:16,fill:'#e2ebf1'}}]}};
 const original=JSON.stringify(data),errors=[],vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(e.message));
 const dom=new JSDOM('<html><body><p id="sceneDescription"></p><script id="scormify-simulator-plan" type="application/json">'+original+'</script></body></html>',{runScripts:'outside-only',virtualConsole:vc});
 const w=dom.window,d=w.document;w.eval(runtime+';ruleVisualRuntime();');
 const finished=visualStyle==='illustrated';
 assert.equal(d.querySelector('#rule-visual').dataset.artFinish,finished?'soft-volume':undefined);
 assert.equal(d.querySelector('[data-visual-node=background]').getAttribute('fill'),'#eaf4fa');
 assert.equal(!!d.querySelector('[data-visual-node=piece]').getAttribute('filter'),finished);
 assert.equal(d.querySelector('[data-visual-node=body]').getAttribute('filter'),null);
 assert.equal(d.querySelector('[data-visual-node=body]').getAttribute('fill').startsWith('url('),finished);
 assert.equal(d.querySelector('#scormify-simulator-plan').textContent,original);
 assert.equal(d.querySelectorAll('image,foreignObject,iframe').length,0);
 assert.deepEqual(errors,[]);w.close();
 console.log(complexity+' / '+visualStyle+': finish, flat environment and unchanged rules OK');
}
