import React,{act} from 'react';
import {createRoot} from 'react-dom/client';
import MusicStudioDialog from './MusicStudioDialog';
jest.mock('./ui/button',()=>({Button:({variant,size,...p})=><button {...p}/>}));
jest.mock('./ui/dialog',()=>({Dialog:({open,children})=>open?<div>{children}</div>:null,DialogContent:props=><div {...props}/>,DialogHeader:props=><header {...props}/>,DialogTitle:props=><h2 {...props}/>,DialogDescription:props=><p {...props}/>}));
jest.mock('../contexts/AuthContext',()=>({authHeaders:()=>({'Authorization':'Bearer local-test'})}));
jest.mock('../utils/apiUrl',()=>({getApiUrl:()=>''}));
let host,root,current;
const spec={title:'Música de teste',theme:'Colaboração e comunicação em equipe',style:'Pop acolhedor',mode:'educational',lyrics:'Vamos colaborar',duration:60};
const quoted=()=>({id:'music1',status:'quoted',spec:{...spec},quote:{id:'q1',estimatedBrl:.83,estimatedUsd:.15,rateUsdMinute:.15,duration:60,exchange:{rate:5.5,asOfDate:'2026-11-26'},expiresAt:'2026-11-27T12:00:00Z',disclaimer:'Estimativa, sem nova tentativa paga automática.'}});
beforeEach(()=>{
 global.IS_REACT_ACT_ENVIRONMENT=true;host=document.createElement('div');document.body.appendChild(host);root=createRoot(host);current=quoted();
 if(!global.crypto)global.crypto={};
 Object.defineProperty(global.crypto,'randomUUID',{configurable:true,value:()=> '00000000-0000-4000-8000-000000000001'});
 global.fetch=jest.fn(async(url,options={})=>{
  if(url==='/api/music/config')return {ok:true,json:async()=>({configured:true})};
  if(url==='/api/music')return {ok:true,json:async()=>({music:[current]})};
  if(url.endsWith('/approve'))current={...current,status:'approved',approval:{ceilingBrl:1}};
  if(url.endsWith('/generate'))current={...current,status:'generating'};
  return {ok:true,json:async()=>JSON.parse(JSON.stringify(current))};
 });
 URL.createObjectURL=jest.fn(()=> 'blob:preview');URL.revokeObjectURL=jest.fn();
});
afterEach(()=>{act(()=>root.unmount());host.remove();jest.restoreAllMocks();});
const button=text=>Array.from(host.querySelectorAll('button')).find(b=>b.textContent.includes(text));
async function open(){await act(async()=>root.render(<MusicStudioDialog open onOpenChange={()=>{}}/>));}
async function history(){await open();await act(async()=>button('Música de teste').click());}
function field(label,value){const input=host.querySelector(`[aria-label="${label}"]`);const proto=input.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;act(()=>{Object.getOwnPropertyDescriptor(proto,'value').set.call(input,value);input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new Event('change',{bubbles:true}));});}

test('opening only reads config and history; no paid POST or course mutation',async()=>{
 await open();expect(fetch.mock.calls.every(([,o])=>o.method==='GET')).toBe(true);
 expect(host.textContent).toContain('nenhum curso é alterado automaticamente');
 expect(button('Calcular orçamento').disabled).toBe(true);
 expect(host.querySelector('[data-testid="music-generate"]')).toBeNull();
});

test('BRL quote shows dated USD reference and requires separate approval before generation',async()=>{
 await history();expect(host.textContent).toContain('26/11/2026');expect(host.textContent).toContain('0,83');
 const generate=()=>host.querySelector('[data-testid="music-generate"]');
 expect(generate().disabled).toBe(true);field('Limite do orçamento da música','1');
 await act(async()=>host.querySelector('[aria-label="Confirmar orçamento da música"]').click());
 await act(async()=>host.querySelector('[data-testid="music-approve"]').click());
 expect(fetch.mock.calls.filter(([u])=>u.endsWith('/generate'))).toHaveLength(0);
 expect(generate().disabled).toBe(false);
 await act(async()=>{generate().click();generate().click();});
 expect(fetch.mock.calls.filter(([u])=>u.endsWith('/generate'))).toHaveLength(1);
 expect(generate().disabled).toBe(true);
 expect(host.textContent).toContain('Fechar esta janela não cancela');
});

test('editing any content discards old quote and approval without generating',async()=>{
 await history();field('Tema da música','Outro tema educativo para revisão');
 expect(host.querySelector('[data-testid="music-budget"]')).toBeNull();
 expect(fetch.mock.calls.every(([,o])=>o.method==='GET')).toBe(true);
});

test('changed ceiling blocks generation of previously approved budget',async()=>{
 current={...quoted(),status:'approved',approval:{ceilingBrl:1}};await history();
 field('Limite do orçamento da música','2');
 expect(host.querySelector('[data-testid="music-generate"]').disabled).toBe(true);
});

test('reopening an approved quote preserves the author custom BRL limit',async()=>{
 current={...quoted(),status:'approved',approval:{ceilingBrl:2.5}};await history();
 expect(host.querySelector('[aria-label="Limite do orçamento da música"]').value).toBe('2.50');
 expect(host.querySelector('[data-testid="music-generate"]').disabled).toBe(false);
});

test('recalculating a saved quote requests a fresh budget, not a paid generation',async()=>{
 await history();await act(async()=>button('Calcular orçamento').click());
 expect(fetch.mock.calls.filter(([u])=>u==='/api/music/quotes')).toHaveLength(1);
 expect(fetch.mock.calls.some(([u])=>u.endsWith('/generate'))).toBe(false);
});

test('ready audio is fetched with authentication and inserted only after explicit click',async()=>{
 current={...quoted(),status:'ready',audioUrl:'/api/music/music1/audio'};
 const use=jest.fn(),close=jest.fn();await act(async()=>root.render(<MusicStudioDialog open onOpenChange={close} onUseAudio={use}/>));
 await act(async()=>button('Música de teste').click());
 expect(use).not.toHaveBeenCalled();
 const previous=fetch.getMockImplementation();fetch.mockImplementation(async(url,opts)=>url.endsWith('/audio')?{ok:true,blob:async()=>new Blob(['audio'],{type:'audio/mpeg'})}:previous(url,opts));
 await act(async()=>button('Carregar áudio para ouvir').click());
 expect(host.querySelector('audio').autoplay).toBe(false);expect(host.querySelector('audio').controls).toBe(true);
 expect(fetch.mock.calls.find(([u])=>u.endsWith('/audio'))[1].headers.Authorization).toBe('Bearer local-test');
 await act(async()=>button('Escolher onde inserir').click());
 expect(use).toHaveBeenCalledTimes(1);expect(use.mock.calls[0][0].type).toBe('audio/mpeg');expect(close).toHaveBeenCalledWith(false);
 expect(fetch.mock.calls.some(([u])=>u.includes('/projects/'))).toBe(false);
});

test('unknown generation cannot be approved or submitted again',async()=>{
 current={...quoted(),status:'unknown',notice:'Confira o provedor antes de outro orçamento.'};await history();
 expect(host.querySelector('[data-testid="music-generate"]').disabled).toBe(true);
 expect(host.querySelector('[data-testid="music-approve"]').disabled).toBe(true);
 expect(host.textContent).toContain('Confira o provedor');
});
