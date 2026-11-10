import React, {act} from 'react';
import {createRoot} from 'react-dom/client';
import RunwayVideoForm from './RunwayVideoForm';
jest.mock('../../../contexts/AuthContext',()=>({authHeaders:()=>({})}));
jest.mock('../../../utils/apiUrl',()=>({getApiUrl:()=> 'https://backend.test'}));
jest.mock('../../../components/ui/button',()=>({Button:({children,variant,size,...props})=><button {...props}>{children}</button>}));
jest.mock('../../../components/ui/textarea',()=>({Textarea:props=><textarea {...props}/>}));
let root,container,originalFetch;
beforeEach(()=>{global.IS_REACT_ACT_ENVIRONMENT=true;originalFetch=global.fetch;container=document.createElement('div');document.body.append(container);root=createRoot(container);});
afterEach(async()=>{await act(async()=>root.unmount());container.remove();global.fetch=originalFetch;jest.restoreAllMocks();});
test('unconfigured Runway is disabled and explains API credentials',async()=>{
  global.fetch=jest.fn().mockResolvedValue({ok:true,json:async()=>({configured:false})});
  await act(async()=>root.render(<RunwayVideoForm onBusyChange={()=>{}}/>));
  expect(container.querySelector('[role="alert"]').textContent).toContain('RUNWAYML_API_SECRET');
  expect(container.querySelector('[data-testid="generate-runway-video"]').disabled).toBe(true);
});
test('shows cost, requires Turbo image and prevents double paid submission',async()=>{
  global.fetch=jest.fn().mockResolvedValue({ok:true,json:async()=>({configured:true})});
  let finish;const generate=jest.fn(()=>new Promise(resolve=>{finish=resolve;}));
  await act(async()=>root.render(<RunwayVideoForm onBusyChange={()=>{}} onGenerate={generate} context="Curso: Movimento"/>));
  await act(async()=>[...container.querySelectorAll('button')].find(b=>b.textContent==='Usar contexto do slide').click());
  expect(container.textContent).toContain('US$ 0.60');
  const button=()=>container.querySelector('[data-testid="generate-runway-video"]');
  await act(async()=>{const select=container.querySelector('[aria-label="Modelo Runway"]');select.value='gen4_turbo';select.dispatchEvent(new Event('change',{bubbles:true}));});
  expect(button().disabled).toBe(true);
  expect(container.textContent).toContain('US$ 0.25');
  await act(async()=>{const select=container.querySelector('[aria-label="Modelo Runway"]');select.value='gen4.5';select.dispatchEvent(new Event('change',{bubbles:true}));});
  await act(async()=>{button().click();button().click();});
  expect(generate).toHaveBeenCalledTimes(1);
  expect(generate.mock.calls[0][0]).toMatchObject({model:'gen4.5',duration:5,aspectRatio:'16:9'});
  await act(async()=>finish());
});

test('optional narration requires script and selected voice, and sends explicit PT-BR options',async()=>{
  global.fetch=jest.fn(async url=>({ok:true,json:async()=>url.includes('/voices') ? {voices:[{id:'br-voice',name:'Voz Brasil',brazilian:true},{id:'other',name:'Other',brazilian:false}]} : {configured:true,narrationConfigured:true,narrationAllowed:true}}));
  const generate=jest.fn().mockResolvedValue({});
  await act(async()=>root.render(<RunwayVideoForm onBusyChange={()=>{}} onGenerate={generate} context="Curso: Paisagens"/>));
  await act(async()=>[...container.querySelectorAll('button')].find(b=>b.textContent==='Usar contexto do slide').click());
  const narrationToggle=container.querySelector('fieldset input[type="checkbox"]');
  expect(narrationToggle.checked).toBe(false);
  await act(async()=>narrationToggle.click());
  const button=()=>container.querySelector('[data-testid="generate-runway-video"]');
  expect(button().disabled).toBe(true);
  expect(container.querySelector('[aria-label="Voz da narração PT-BR"]').textContent).toContain('Voz Brasil');
  expect(container.querySelector('[aria-label="Voz da narração PT-BR"]').textContent).not.toContain('Other');
  await act(async()=>{
    const text=container.querySelector('[aria-label="Texto da narração PT-BR"]');
    Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(text,'As montanhas recebem a luz do amanhecer.');
    text.dispatchEvent(new Event('input',{bubbles:true}));
    const voice=container.querySelector('[aria-label="Voz da narração PT-BR"]');
    voice.value='br-voice';voice.dispatchEvent(new Event('change',{bubbles:true}));
  });
  expect(button().disabled).toBe(false);
  await act(async()=>button().click());
  expect(generate).toHaveBeenCalledTimes(1);
  expect(generate.mock.calls[0][0].narration).toEqual({enabled:true,text:'As montanhas recebem a luz do amanhecer.',voiceId:'br-voice',language:'pt-BR',allowOtherVoices:false});
  expect(container.textContent).toContain('último quadro');
  expect(container.textContent).toContain('não sincronização labial');
});

test('no voice permission leaves silent generation available without speech requests',async()=>{
  global.fetch=jest.fn().mockResolvedValue({ok:true,json:async()=>({configured:true,narrationConfigured:true,narrationAllowed:false})});
  const generate=jest.fn().mockResolvedValue({});
  await act(async()=>root.render(<RunwayVideoForm onBusyChange={()=>{}} onGenerate={generate} context="Curso: Paisagens"/>));
  expect(container.querySelector('fieldset input[type="checkbox"]').disabled).toBe(true);
  await act(async()=>[...container.querySelectorAll('button')].find(b=>b.textContent==='Usar contexto do slide').click());
  await act(async()=>container.querySelector('[data-testid="generate-runway-video"]').click());
  expect(generate.mock.calls[0][0].narration).toBeUndefined();
  expect(global.fetch).toHaveBeenCalledTimes(1);
});

test('instrumental music is optional, costed separately, and sent with selected volume',async()=>{
  global.fetch=jest.fn().mockResolvedValue({ok:true,json:async()=>({configured:true,musicConfigured:true})});
  const generate=jest.fn().mockResolvedValue({});
  await act(async()=>root.render(<RunwayVideoForm onBusyChange={()=>{}} onGenerate={generate} context="Curso: Paisagem"/>));
  await act(async()=>[...container.querySelectorAll('button')].find(b=>b.textContent==='Usar contexto do slide').click());
  const toggle=container.querySelectorAll('fieldset')[1].querySelector('input[type="checkbox"]');
  expect(toggle.checked).toBe(false);
  await act(async()=>toggle.click());
  expect(container.textContent).toContain('20 créditos Runway');
  await act(async()=>container.querySelector('[data-testid="generate-runway-video"]').click());
  expect(generate.mock.calls[0][0].music).toMatchObject({enabled:true,volume:15});
  expect(generate.mock.calls[0][0].narration).toBeUndefined();
});
