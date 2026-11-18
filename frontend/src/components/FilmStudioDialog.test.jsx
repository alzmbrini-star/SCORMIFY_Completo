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
  if(path==='/films/config')return{ok:true,json:async()=>({runway:true,narration:true,mediaTools:true})};
  if(path==='/films' || path.startsWith('/films?'))return{ok:true,json:async()=>({films:[{id:'film',board:{title:'História de teste'},status:'draft'}]})};
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
