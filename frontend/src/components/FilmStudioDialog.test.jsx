import React,{act} from 'react';
import {createRoot} from 'react-dom/client';
import FilmStudioDialog from './FilmStudioDialog';
jest.mock('./ui/button',()=>({Button:({variant,size,...p})=><button {...p}/>}));
jest.mock('./ui/dialog',()=>({Dialog:({open,children})=>open?<div>{children}</div>:null,DialogContent:props=><div {...props}/>,DialogHeader:props=><header {...props}/>,DialogTitle:props=><h2 {...props}/>,DialogDescription:props=><p {...props}/>}));
jest.mock('../contexts/AuthContext',()=>({authHeaders:()=>({})}));
jest.mock('../utils/apiUrl',()=>({getApiUrl:()=>''}));
let host,root,current;
function draft(){return {id:'film',projectId:'independent',revision:'rev1',status:'draft',operations:{},board:{title:'História de teste',topic:'Conteúdo didático suficientemente detalhado para o teste.',style:'2d',model:'gen4_turbo',
 characters:[{name:'Ana',description:'Mulher adulta de roupa azul.',voiceId:''}],narratorVoice:'voice',allowOtherVoices:false,music:true,musicPrompt:'Música original suave',musicVolume:15,
 scenes:[0,1,2].map(i=>({title:'Cena '+i,visual:'Ana conversa com a equipe em uma mesa.',narration:'Vamos colaborar.',speaker:'narrator',duration:10}))}};}
function priced(){return{id:'quote1',duration:30,ratesVersion:'2026-11-18-v1',estimatedUsd:2,suggestedCeilingUsd:2.4,items:[{label:'Vídeos',quantity:30,unit:'segundos',usd:1.5}],disclaimer:'Estimativa sem impostos.'};}
beforeEach(()=>{
 global.IS_REACT_ACT_ENVIRONMENT=true;host=document.createElement('div');document.body.appendChild(host);root=createRoot(host);current=draft();
 if(!global.crypto)global.crypto={};
 Object.defineProperty(global.crypto,'randomUUID',{configurable:true,value:()=> '00000000-0000-4000-8000-000000000001'});
 global.fetch=jest.fn(async(path,options={})=>{
  const body=options.body?JSON.parse(options.body):{};
  if(!path.startsWith('/api/'))throw new Error('API prefix missing');
  if(path==='/api/films/config')return{ok:true,json:async()=>({runway:true,narration:true,mediaTools:true})};
  if(path==='/api/films' || path.startsWith('/api/films?'))return{ok:true,json:async()=>({films:[{id:'film',board:{title:'História de teste'},status:'draft'}]})};
  if(path.includes('/approve-storyboard'))current={...current,status:'storyboard_approved',storyboardApproval:current.revision,quote:priced()};
  if(path.includes('/approve-budget'))current={...current,status:'budget_approved',budgetApproval:{quoteId:body.quoteId}};
  if(path.includes('/generate'))current={...current,status:'generating'};
  return{ok:true,json:async()=>JSON.parse(JSON.stringify(current))};
 });
});
afterEach(()=>{act(()=>root.unmount());host.remove();jest.restoreAllMocks();});
async function openFilm(){await act(async()=>root.render(<FilmStudioDialog open onOpenChange={()=>{}}/>));await act(async()=>Array.from(host.querySelectorAll('button')).find(b=>b.textContent.includes('História de teste')).click());}
test('opening the studio only reads history/configuration and does not generate anything',async()=>{
 await act(async()=>root.render(<FilmStudioDialog open onOpenChange={()=>{}} sourceProjectId="original"/>));
 expect(host.textContent).toContain('projeto separado');
 expect(fetch.mock.calls.every(([,options])=>options.method==='GET')).toBe(true);
 expect(fetch.mock.calls.map(([url])=>url)).toEqual(['/api/films/config','/api/films?sourceProjectId=original']);
 expect(host.querySelector('[data-testid="film-create-draft"]').disabled).toBe(true);
});
test('two explicit approvals are required before the media button is enabled',async()=>{
 await openFilm();const generate=()=>host.querySelector('[data-testid="film-generate"]');expect(generate().disabled).toBe(true);
 expect(host.querySelector('[data-testid="film-approve-storyboard"]').disabled).toBe(true);
 act(()=>host.querySelector('[aria-label="Confirmar revisão do storyboard"]').click());
 await act(async()=>host.querySelector('[data-testid="film-approve-storyboard"]').click());
 expect(generate().disabled).toBe(true);expect(host.textContent).toContain('Estimativa restante');
 expect(host.querySelector('[data-testid="film-approve-budget"]').disabled).toBe(true);
 act(()=>host.querySelector('[aria-label="Confirmar orçamento do filme"]').click());
 await act(async()=>host.querySelector('[data-testid="film-approve-budget"]').click());
 expect(generate().disabled).toBe(false);
 expect(fetch.mock.calls.some(([url])=>url.endsWith('/generate'))).toBe(false);
 await act(async()=>generate().click());expect(fetch.mock.calls.filter(([url])=>url.endsWith('/generate'))).toHaveLength(1);
 expect(host.textContent).toContain('Produzindo mídias');
});
test('a local storyboard edit disables approvals and production immediately',async()=>{
 await openFilm();const select=host.querySelector('[aria-label="Estilo do filme"]');
 act(()=>{select.value='3d';select.dispatchEvent(new Event('change',{bubbles:true}));});
 expect(host.querySelector('[data-testid="film-generate"]').disabled).toBe(true);
 expect(host.querySelector('[aria-label="Confirmar revisão do storyboard"]').disabled).toBe(true);
 expect(host.textContent).toContain('Alterações locais ainda não salvas');
 expect(fetch.mock.calls.some(([url])=>/approve|generate/.test(url))).toBe(false);
});
test('alternative voice catalog notice does not change or save the storyboard',async()=>{
 await openFilm();const original=fetch.getMockImplementation();
 fetch.mockImplementation(async(url,options)=>url==='/api/runway/voices'?{ok:true,json:async()=>({voices:[{id:'br1',name:'Voz brasileira',brazilian:true}],fallback:true,notice:'Vozes carregadas pela consulta alternativa da ElevenLabs.'})}:original(url,options));
 const prior=JSON.stringify(current);
 await act(async()=>Array.from(host.querySelectorAll('button')).find(b=>b.textContent.includes('Carregar vozes ElevenLabs')).click());
 expect(host.textContent).toContain('consulta alternativa');
 expect(host.textContent).toContain('1 vozes carregadas');
 expect(JSON.stringify(current)).toBe(prior);
 expect(host.querySelector('[aria-label="ID da voz do narrador"]').value).toBe('voice');
 expect(fetch.mock.calls.some(([,o])=>o.method!=='GET')).toBe(false);
 expect(host.querySelector('[data-testid="film-generate"]').disabled).toBe(true);
});
function field(label,value){act(()=>{const el=host.querySelector('[aria-label="'+label+'"]');Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el),'value').set.call(el,value);el.dispatchEvent(new Event('input',{bubbles:true}));});}
async function upload(file){await act(async()=>{const el=host.querySelector('[aria-label="Documento do filme"]');Object.defineProperty(el,'files',{configurable:true,value:[file]});el.dispatchEvent(new Event('change',{bubbles:true}));});}
function guidedMock(){
 const original=fetch.getMockImplementation();
 fetch.mockImplementation(async(url,options={})=>{
  if(url==='/api/films/extract-document')return{ok:true,json:async()=>({text:'[Página 1] Conteúdo completo sobre trabalho em equipe.',units:1,warning:'Extração de texto, sem imagens originais.'})};
  if(url==='/api/films'&&options.method==='POST'){
   const data=JSON.parse(options.body);current={...draft(),sourceName:data.sourceName,sourceText:data.sourceText,sourceWarning:data.sourceWarning,board:{...draft().board,title:data.title,topic:data.topic,style:data.style,scenes:Array.from({length:data.scenes},(_,i)=>({title:'Cena '+i,visual:'',narration:'',speaker:'narrator',duration:10}))}};
   return{ok:true,json:async()=>current};
  }
  if(url.endsWith('/suggest-storyboard')){current={...current,board:{...current.board,scenes:current.board.scenes.map(s=>({...s,visual:'Ana e Bruno dividem tarefas na mesa.',narration:'Vamos combinar as tarefas.'}))},planningReview:{summary:'Uma história sobre colaboração.',coveredTopics:['Divisão de tarefas'],notCoveredTopics:['Avaliação de desempenho'],warnings:[],revision:current.revision}};return{ok:true,json:async()=>current};}
  return original(url,options);
 });
}
test('guided theme prepares text only and keeps advanced mode and both approval gates',async()=>{
 guidedMock();await act(async()=>root.render(<FilmStudioDialog open onOpenChange={()=>{}} sourceProjectId="original"/>));
 expect(host.querySelector('[data-testid="film-guided-prepare"]').disabled).toBe(true);
 field('Tema do filme guiado','Trabalho em Equipe');field('Objetivo do filme','Dividir tarefas e pedir ajuda');
 await act(async()=>host.querySelector('[data-testid="film-guided-prepare"]').click());
 expect(host.textContent).toContain('Ficou fora deste filme:');expect(host.textContent).toContain('Avaliação de desempenho');
 expect(fetch.mock.calls.filter(([u,o])=>u==='/api/films'&&o.method==='POST')).toHaveLength(1);
 const body=JSON.parse(fetch.mock.calls.find(([u,o])=>u==='/api/films'&&o.method==='POST')[1].body);
 expect(body).toMatchObject({scenes:6,style:'3d',sourceProjectId:'original'});
 expect(fetch.mock.calls.some(([u])=>u.endsWith('/generate')||u.includes('/approve-'))).toBe(false);
 const before=JSON.stringify(current);act(()=>Array.from(host.querySelectorAll('button')).find(b=>b.textContent==='Modo avançado').click());
 expect(host.querySelector('fieldset[hidden]')).toBeNull();expect(JSON.stringify(current)).toBe(before);
 expect(host.querySelector('[data-testid="film-generate"]').disabled).toBe(true);
});
test('document extraction must be reviewed before the full source is sent for storyboard planning',async()=>{
 guidedMock();await act(async()=>root.render(<FilmStudioDialog open onOpenChange={()=>{}}/>));
 act(()=>Array.from(host.querySelectorAll('button')).find(b=>b.textContent==='Por documento').click());
 await upload(new File(['pdf'],'Equipe.pdf',{type:'application/pdf'}));
 field('Objetivo do filme','Colaborar em equipe');
 expect(host.querySelector('[data-testid="film-guided-prepare"]').disabled).toBe(true);
 expect(fetch.mock.calls.some(([u])=>u.endsWith('/suggest-storyboard'))).toBe(false);
 act(()=>host.querySelector('[aria-label="Confirmar revisão do documento"]').click());
 await act(async()=>host.querySelector('[data-testid="film-guided-prepare"]').click());
 const body=JSON.parse(fetch.mock.calls.find(([u,o])=>u==='/api/films'&&o.method==='POST')[1].body);
 expect(body.sourceText).toBe('[Página 1] Conteúdo completo sobre trabalho em equipe.');
 expect(body.sourceName).toBe('Equipe.pdf');expect(fetch.mock.calls.some(([u])=>u.endsWith('/generate'))).toBe(false);
});
test('legacy and oversize uploads are refused without a network or paid call',async()=>{
 await act(async()=>root.render(<FilmStudioDialog open onOpenChange={()=>{}}/>));
 act(()=>Array.from(host.querySelectorAll('button')).find(b=>b.textContent==='Por documento').click());
 const count=fetch.mock.calls.length;
 await upload({name:'antigo.ppt',size:20});
 expect(host.textContent).toContain('PPT/DOC antigos');
 await upload({name:'grande.pdf',size:21*1024*1024});
 expect(host.textContent).toContain('limite é 20 MB');expect(fetch.mock.calls.length).toBe(count);
});
