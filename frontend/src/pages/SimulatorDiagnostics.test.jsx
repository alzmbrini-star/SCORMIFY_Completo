import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import SimulatorDiagnostics from './SimulatorDiagnostics';

jest.mock('../contexts/AuthContext',()=>({authHeaders:()=>({Authorization:'Bearer test'})}));
jest.mock('../utils/apiUrl',()=>({getApiUrl:()=>''}));
const sessions=[{id:'owned-session',title:'Gestão do Tempo',error:'Simulador reprovado',
  simulators:[{index:8,title:'Montando Seu Cronograma'},{index:14,title:'Gestão de Projetos'}]}];
let container,root;
async function render(){await act(async()=>{root.render(<SimulatorDiagnostics />);});}
async function choose(label,value){await act(async()=>{const select=container.querySelector('[aria-label="'+label+'"]');select.value=value;select.dispatchEvent(new Event('change',{bubbles:true}));});}
beforeEach(()=>{
  global.IS_REACT_ACT_ENVIRONMENT=true;
  container=document.createElement('div');document.body.appendChild(container);root=createRoot(container);
  global.fetch=jest.fn(async url=>({ok:true,json:async()=>url.endsWith('/sessions')?sessions:{records:[],run:null}}));
});
afterEach(()=>{act(()=>root.unmount());container.remove();jest.restoreAllMocks();});

test('read-only initial load and retry targets only the selected existing simulator',async()=>{
  await render();
  expect(container.textContent).toContain('Gestão do Tempo');
  expect(fetch).toHaveBeenCalledTimes(1);
  await choose('Curso / sessão','owned-session');
  expect(container.textContent).toContain('Último erro do Storyboard');
  await choose('Simulador','8');
  await act(async()=>{Array.from(container.querySelectorAll('button')).find(b=>b.textContent==='Gerar somente este simulador com diagnóstico').click();});
  expect(fetch.mock.calls.some(([url,opts])=>url.endsWith('/retry') && opts.body==='{"slideIndex":8}')).toBe(true);
  expect(fetch.mock.calls.some(([url])=>url.includes('generate-storyboard'))).toBe(false);
});

test('generated markup in a diagnostic is text, never executed or placed in an iframe',async()=>{
  fetch.mockImplementation(async url=>({ok:true,json:async()=>url.endsWith('/sessions')?sessions:{run:{status:'failed',title:'Montando Seu Cronograma',error:'Falha'},records:[{
    generationKey:'key',activityTitle:'Cronograma',status:'failed',attempts:[{error:'Falha no botão',issues:[{issue:'<img src=x onerror=alert(1)>',context:'Adicionar tarefa',action:'Atualizar render'}]}]
  }]}}));
  await render();
  await choose('Curso / sessão','owned-session');
  expect(container.textContent).toContain('<img src=x onerror=alert(1)>');
  expect(container.querySelector('img,iframe,script')).toBeNull();
});
