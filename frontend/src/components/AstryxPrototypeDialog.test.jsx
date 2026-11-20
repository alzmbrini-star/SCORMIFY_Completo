import React,{act} from 'react';
import {createRoot} from 'react-dom/client';
import AstryxPrototypeDialog from './AstryxPrototypeDialog';
const mockNavigate=jest.fn();
jest.mock('react-router-dom',()=>({useNavigate:()=>mockNavigate}));
jest.mock('../contexts/AuthContext',()=>({authHeaders:()=>({Authorization:'Bearer local-test'})}));
jest.mock('../utils/apiUrl',()=>({getApiUrl:()=>''}));
jest.mock('./ui/dialog',()=>({Dialog:({open,children})=>open?<div>{children}</div>:null,DialogContent:({children})=><div>{children}</div>,DialogHeader:({children})=><div>{children}</div>,DialogTitle:({children})=><h1>{children}</h1>,DialogDescription:({children})=><p>{children}</p>}));
jest.mock('./ui/button',()=>({Button:({variant,...p})=><button {...p}/>}));
const defaults={title:'Exemplo',subtitle:'Introdução',heading:'Conteúdo',body:'Texto',image:'',imageAlt:'Descrição',question:'Pergunta?',options:['A','B','C'],correct:0,feedback:'Explicação',accent:'blue'};
let host,root,close;
beforeEach(()=>{global.IS_REACT_ACT_ENVIRONMENT=true;mockNavigate.mockClear();close=jest.fn();Object.defineProperty(global,'crypto',{configurable:true,value:{randomUUID:()=> '39bff609-8562-43d3-a198-6717865f7d9b'}});global.fetch=jest.fn(async url=>({ok:true,json:async()=>url.endsWith('defaults')?defaults:url.endsWith('create')?{projectId:'new-project'}:{course:{slides:[0,1,2].map(()=>({elements:[{htmlContent:'<p>Prévia isolada</p>'}]}))}}}));host=document.createElement('div');document.body.appendChild(host);root=createRoot(host);});
afterEach(()=>{act(()=>root.unmount());host.remove();jest.restoreAllMocks();});
async function render(){await act(async()=>root.render(<AstryxPrototypeDialog open onOpenChange={close} sourceProjectId="original"/>));}
const button=text=>Array.from(host.querySelectorAll('button')).find(n=>n.textContent===text);
async function prepare(){await act(async()=>button('Preparar prévia — sem salvar').click());}

test('opening only reads defaults; preview never saves or sends original slides',async()=>{
 await render();expect(fetch.mock.calls.length).toBe(1);expect(fetch.mock.calls[0][1].method).toBe('GET');
 expect(button('Criar novo projeto com estes 3 slides').disabled).toBe(true);await prepare();
 const [url,request]=fetch.mock.calls[1];expect(url).toMatch(/astryx\/preview$/);expect(JSON.parse(request.body)).toEqual(defaults);
 expect(host.querySelector('iframe').getAttribute('sandbox')).toBe('allow-scripts');expect(mockNavigate).not.toHaveBeenCalled();
});
test('editing invalidates preview and disables exports and creation',async()=>{
 await render();await prepare();expect(button('Baixar HTML de teste').disabled).toBe(false);
 act(()=>{const input=host.querySelector('input');Object.getOwnPropertyDescriptor(Object.getPrototypeOf(input),'value').set.call(input,'Outro tema');input.dispatchEvent(new Event('input',{bubbles:true}));});
 expect(host.querySelector('iframe')).toBeNull();expect(button('Baixar HTML de teste').disabled).toBe(true);expect(button('Criar novo projeto com estes 3 slides').disabled).toBe(true);
});
test('only explicit create opens a separate project; never PUTs original',async()=>{
 await render();await prepare();await act(async()=>button('Criar novo projeto com estes 3 slides').click());
 const [url,request]=fetch.mock.calls[2];expect(url).toMatch(/astryx\/create$/);expect(request.method).toBe('POST');
 expect(JSON.parse(request.body).sourceProjectId).toBe('original');expect(mockNavigate).toHaveBeenCalledWith('/editor/new-project');
 expect(fetch.mock.calls.some(([u,r])=>u.includes('/projects/original')||r.method==='PUT')).toBe(false);
});
