import React, {act} from 'react';
import {createRoot} from 'react-dom/client';
import GammaRefreshDialog from './GammaRefreshDialog';
jest.mock('../contexts/AuthContext',()=>({authHeaders:()=>({})}));
jest.mock('../utils/apiUrl',()=>({getApiUrl:()=> 'https://backend.test'}));
jest.mock('./ui/button',()=>({Button:({children,variant,...props})=><button {...props}>{children}</button>}));
jest.mock('./ui/dialog',()=>({Dialog:({open,children})=>open?<div>{children}</div>:null,DialogContent:({children,onInteractOutside,...props})=><div {...props}>{children}</div>,DialogHeader:({children})=><div>{children}</div>,DialogTitle:({children})=><h2>{children}</h2>,DialogDescription:({children})=><p>{children}</p>}));
let root,container,oldFetch,save,onApplied,calls;
const fixture={id:'job',status:'ready',bases:[{slideId:'s1',elementId:'e1',position:0,index:0,title:'Capa',src:'/old.png',width:1920,height:1080}],images:[{index:0,src:'/new.png',width:1920,height:1080},{index:1,src:'/second.png',width:1920,height:1080}]};
beforeEach(()=>{
  global.IS_REACT_ACT_ENVIRONMENT=true;sessionStorage.clear();calls=[];
  save=jest.fn(async()=>{calls.push('save');});onApplied=jest.fn(async()=>{});
  oldFetch=global.fetch;global.fetch=jest.fn(async(url,options)=>{calls.push(url);return {ok:true,json:async()=>url.endsWith('/apply')?{appliedSlides:1}:fixture};});
  Object.defineProperty(global,'crypto',{configurable:true,value:{randomUUID:()=> '11111111-1111-4111-8111-111111111111'}});
  container=document.createElement('div');document.body.append(container);root=createRoot(container);
});
afterEach(async()=>{await act(async()=>root.unmount());container.remove();global.fetch=oldFetch;});
const click=async(text)=>{const button=[...container.querySelectorAll('button')].find(b=>b.textContent===text);expect(button).toBeTruthy();await act(async()=>button.click());};
async function render(project={id:'p',source:'gamma',gammaJobId:'j'}){await act(async()=>root.render(<GammaRefreshDialog project={project} saveCourse={save} onApplied={onApplied}/>));}

test('non-Gamma courses have no update action or API calls',async()=>{await render({id:'manual',source:'manual'});expect(container.textContent).toBe('');expect(global.fetch).not.toHaveBeenCalled();});
test('saves before preview, no default replacements, requires review then only sends selected IDs',async()=>{
  await render();await click('Atualizar do Gamma');await click('Buscar versão atual no Gamma');
  expect(calls[0]).toBe('save');expect(calls[1]).toContain('/projects/p/gamma-refresh');
  expect(container.querySelector('select').value).toBe('');
  const apply=()=>[...container.querySelectorAll('button')].find(b=>b.textContent.startsWith('Aplicar em'));
  expect(apply().disabled).toBe(true);
  await act(async()=>{const select=container.querySelector('select');select.value='1';select.dispatchEvent(new Event('change',{bubbles:true}));});
  expect(apply().disabled).toBe(true);
  await act(async()=>container.querySelector('input[type=checkbox]').click());
  await click('Aplicar em 1 slide(s)');
  const sent=global.fetch.mock.calls.find(([url])=>url.endsWith('/apply'));
  expect(JSON.parse(sent[1].body)).toEqual({mappings:[{slideId:'s1',sourceIndex:1}]});
  expect(onApplied).toHaveBeenCalledWith('p');expect(container.textContent).toContain('interações preservadas');
  expect(save).toHaveBeenCalledTimes(1);
});
test('explicit position selection requires fresh confirmation and clear selection keeps course intact',async()=>{
  await render();await click('Atualizar do Gamma');await click('Buscar versão atual no Gamma');
  await click('Selecionar posições de origem — conferir antes de aplicar');
  expect(container.querySelector('select').value).toBe('0');
  await click('Limpar seleção');expect(container.querySelector('select').value).toBe('');
  expect(global.fetch.mock.calls.some(([url])=>url.endsWith('/apply'))).toBe(false);
});
test('server conflict is visible and never reloads over newer edits',async()=>{
  await render();await click('Atualizar do Gamma');await click('Buscar versão atual no Gamma');
  await click('Selecionar posições de origem — conferir antes de aplicar');await act(async()=>container.querySelector('input').click());
  global.fetch.mockResolvedValueOnce({ok:false,json:async()=>({detail:'O curso mudou durante a revisão. Nada foi substituído.'})});
  await click('Aplicar em 1 slide(s)');expect(container.querySelector('[role=alert]').textContent).toContain('Nada foi substituído');
  expect(onApplied).not.toHaveBeenCalled();
});
