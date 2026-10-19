import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import KlingVideoForm from './KlingVideoForm';

jest.mock('../../../contexts/AuthContext', () => ({authHeaders:() => ({Authorization:'Bearer test'})}));
jest.mock('../../../utils/apiUrl', () => ({getApiUrl:() => 'https://backend.test'}));
jest.mock('../../../components/ui/button', () => ({Button:({children,variant,size,...props}) => <button {...props}>{children}</button>}));
jest.mock('../../../components/ui/textarea', () => ({Textarea:props => <textarea {...props} />}));
let container, root, originalFetch;
beforeEach(() => {
  global.IS_REACT_ACT_ENVIRONMENT=true;
  originalFetch=global.fetch;
  container=document.createElement('div');document.body.appendChild(container);root=createRoot(container);
});
afterEach(async() => {await act(async()=>root.unmount());container.remove();global.fetch=originalFetch;jest.restoreAllMocks();});
const button = () => container.querySelector('[data-testid="generate-kling-video"]');

test('submits selected settings only once and inserts course context on request', async () => {
  global.fetch=jest.fn().mockResolvedValue({ok:true,json:async()=>({configured:true})});
  let finish;
  const onGenerate=jest.fn(()=>new Promise(resolve=>{finish=resolve;}));
  const onBusyChange=jest.fn();
  await act(async()=>root.render(<KlingVideoForm onGenerate={onGenerate} onBusyChange={onBusyChange} context="Curso: Feedback. Slide: Escuta." />));
  expect(global.fetch).toHaveBeenCalledTimes(1);
  await act(async()=>Array.from(container.querySelectorAll('button')).find(b=>b.textContent==='Usar contexto do slide').click());
  expect(container.querySelector('textarea').value).toContain('Curso: Feedback');
  await act(async()=>{
    const duration=container.querySelector('[aria-label="Duração"]');duration.value='10';duration.dispatchEvent(new Event('change',{bubbles:true}));
    const format=container.querySelector('[aria-label="Formato"]');format.value='9:16';format.dispatchEvent(new Event('change',{bubbles:true}));
  });
  expect(button().disabled).toBe(false);
  await act(async()=>{button().click();button().click();});
  expect(onGenerate).toHaveBeenCalledTimes(1);
  expect(onGenerate.mock.calls[0][0]).toMatchObject({duration:10,resolution:'720p',aspectRatio:'9:16',audio:'off'});
  expect(onBusyChange).toHaveBeenCalledWith(true);
  await act(async()=>finish());
  expect(onBusyChange).toHaveBeenLastCalledWith(false);
});

test('unconfigured integration is explained and cannot consume credits', async () => {
  global.fetch=jest.fn().mockResolvedValue({ok:true,json:async()=>({configured:false})});
  const generate=jest.fn();
  await act(async()=>root.render(<KlingVideoForm onGenerate={generate} onBusyChange={jest.fn()} context="" />));
  expect(container.querySelector('[role="alert"]').textContent).toContain('Kling não configurado');
  expect(button().disabled).toBe(true);
  expect(generate).not.toHaveBeenCalled();
});
