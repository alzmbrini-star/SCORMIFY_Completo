import React, {act} from 'react';
import {createRoot} from 'react-dom/client';
import GammaCreateDialog from './GammaCreateDialog';
jest.mock('react-router-dom', () => ({useNavigate: () => jest.fn()}));
let mockUser = {roles: ['editor']};
jest.mock('../contexts/AuthContext', () => ({authHeaders: () => ({}), useAuth: () => ({user: mockUser})}));
jest.mock('../utils/apiUrl', () => ({getApiUrl: () => 'https://backend.test'}));
jest.mock('./CompanySelector', () => () => null);
jest.mock('./ui/button', () => ({Button: ({children, variant, size, ...props}) => <button {...props}>{children}</button>}));
jest.mock('./ui/input', () => ({Input: props => <input {...props}/> }));
jest.mock('./ui/dialog', () => ({Dialog: ({open,children}) => open ? <div>{children}</div> : null, DialogContent: ({children,...props}) => <div {...props}>{children}</div>, DialogHeader: ({children}) => <div>{children}</div>, DialogTitle: ({children}) => <h2>{children}</h2>, DialogDescription: ({children}) => <p>{children}</p>}));
let root, container, oldFetch;
beforeEach(() => { global.IS_REACT_ACT_ENVIRONMENT = true; mockUser = {roles: ['editor']}; oldFetch = global.fetch; container = document.createElement('div'); document.body.append(container); root = createRoot(container); Object.defineProperty(global, 'crypto', {configurable: true, value: {randomUUID: () => '11111111-1111-4111-8111-111111111111'}}); });
afterEach(async () => { await act(async () => root.unmount()); container.remove(); global.fetch = oldFetch; jest.restoreAllMocks(); });
async function open(configured = true) {
  global.fetch = jest.fn(async url => ({ok: true, json: async () => url.endsWith('/status') ? {configured} : []}));
  await act(async () => root.render(<GammaCreateDialog/>));
  await act(async () => container.querySelector('[data-testid="gamma-create-open"]').click());
}
async function fill() {
  await act(async () => {
    const title = container.querySelector('input');
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(title, 'Teste técnico Gamma');
    title.dispatchEvent(new Event('input', {bubbles: true}));
    const prompt = container.querySelector('textarea');
    Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set.call(prompt, 'Conteúdo didático para cinco slides em Português do Brasil.');
    prompt.dispatchEvent(new Event('input', {bubbles: true}));
  });
}
test('readers cannot start Gamma generation', async () => {
  mockUser = {roles: ['aprovador']};
  await act(async () => root.render(<GammaCreateDialog/>));
  expect(container.textContent).toBe('');
});

test('assessment is optional, defaults off and submits reviewed document/prompt with bounded image options',async()=>{
  await open();await fill();
  const enabled=Array.from(container.querySelectorAll('label')).find(e=>e.textContent.includes('Adicionar avaliação interativa')).querySelector('input');
  expect(enabled.checked).toBe(false);
  await act(async()=>enabled.click());
  const questionCount=container.querySelector('[aria-label="Quantidade de questões da avaliação Gamma"]');
  const images=Array.from(container.querySelectorAll('label')).find(e=>e.textContent.includes('Gerar imagem de apoio')).querySelector('input');
  expect(images.checked).toBe(true);
  for(const value of ['', '0', '11', '2.5']){
    await act(async()=>{Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(questionCount,value);questionCount.dispatchEvent(new Event('input',{bubbles:true}));});
    expect(container.querySelector('[data-testid="gamma-generate"]').disabled).toBe(true);
  }
  await act(async()=>{Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(questionCount,'3');questionCount.dispatchEvent(new Event('input',{bubbles:true}));});
  const source='Prompt original. Documento revisado: primeira e última unidade devem aparecer nas questões.';
  await act(async()=>{const p=container.querySelector('[aria-label="Conteúdo Gamma"]');Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(p,source);p.dispatchEvent(new Event('input',{bubbles:true}));});
  global.fetch.mockResolvedValue({ok:true,json:async()=>({id:'j',status:'pending'})});
  await act(async()=>container.querySelector('[data-testid="gamma-generate"]').click());
  const body=JSON.parse(global.fetch.mock.calls.find(([,o])=>o?.method==='POST')[1].body);
  expect(body.interactiveAssessment).toEqual({enabled:true,questionCount:3,images:true});expect(body.prompt).toBe(source);
  expect(body.numCards).toBe(5);expect(body).not.toHaveProperty('projectId');
});

test('assessment failure explains preserved slides and image warning stays visible for review',async()=>{
  await open();
  const rows=[{id:'j',title:'Com falha',status:'completed',interactiveAssessment:{enabled:true,questionCount:5},assessment:{status:'failed',error:'Falhou; slides preservados'}},
    {id:'ok',title:'Com imagens',status:'completed',totalSlides:6,interactiveAssessment:{enabled:true,questionCount:5},assessment:{status:'ready',questionCount:5,imagesReady:4,warning:'Uma imagem precisa de revisão'}}];
  global.fetch.mockResolvedValue({ok:true,json:async()=>rows});
  // Close/open refreshes the history using the normal lifecycle.
  await act(async()=>root.render(<GammaCreateDialog key="new"/>));
  await act(async()=>container.querySelector('[data-testid="gamma-create-open"]').click());
  expect(container.textContent).toContain('slides Gamma preservados');
  expect(container.textContent).toContain('Tentar somente avaliação novamente');
  expect(container.textContent).toContain('5 questões prontas para revisar no Editor');
  expect(container.textContent).toContain('4 imagens de apoio disponíveis na biblioteca');
  expect(container.textContent).toContain('Uma imagem precisa de revisão');
  expect(container.textContent).toContain('6 slides no curso completo');
  expect(container.textContent).toContain('A avaliação está no último slide');
  expect(container.textContent).toContain('Abrir curso completo no Editor');
  expect(container.textContent).toContain('ZIP Gamma — sem avaliação');
  expect(container.textContent).toContain('Exportar → HTML ou SCORM');
  expect(global.fetch.mock.calls.filter(([,options])=>options?.method==='POST')).toHaveLength(0);
});
test('missing key disables generation and explains image-base limitation', async () => {
  await open(false); await fill();
  expect(container.textContent).toContain('GAMMA_API_KEY');
  expect(container.textContent).toContain('não será editável separadamente');
  expect(container.querySelector('[data-testid="gamma-generate"]').disabled).toBe(true);
});
test('two clicks submit only once, with no existing project target', async () => {
  await open(); await fill();
  let finish;
  global.fetch.mockImplementation((url, options) => options?.method === 'POST' ? new Promise(resolve => {finish = resolve;}) : Promise.resolve({ok: true, json: async () => []}));
  const button = container.querySelector('[data-testid="gamma-generate"]');
  expect(button.disabled).toBe(false);
  await act(async () => { button.click(); button.click(); });
  const posts = global.fetch.mock.calls.filter(([, options]) => options?.method === 'POST');
  expect(posts.length).toBe(1);
  expect(JSON.parse(posts[0][1].body)).not.toHaveProperty('projectId');
  await act(async () => finish({ok: true, json: async () => ({id: 'job', title: 'Teste', status: 'pending'})}));
  expect(container.textContent).toContain('Gerando / importando');
});
test('lost POST response never automatically resubmits', async () => {
  await open(); await fill();
  global.fetch.mockRejectedValue(new Error('Conexão interrompida'));
  await act(async () => container.querySelector('[data-testid="gamma-generate"]').click());
  expect(container.querySelector('[data-testid="gamma-generate"]').disabled).toBe(true);
  expect(container.textContent).toContain('Não repetiremos automaticamente');
});

test('theme discovery costs no generation; chosen ID is sent only on explicit generate', async () => {
  await open(); await fill();
  global.fetch.mockImplementation(async (url, options) => ({ok: true, json: async () => options?.method === 'POST'
    ? {id: 'job', title: 'Teste', status: 'pending'} : {items: [{id: 'ocean', name: 'Oceano', source: 'custom', colors: ['azul', 'branco'], tones: ['profissional']}], nextCursor: 'page2'}}));
  await act(async () => {const select = container.querySelector('[aria-label="Modo visual Gamma"]'); select.value = 'theme'; select.dispatchEvent(new Event('change', {bubbles:true}));});
  expect(container.querySelector('[data-testid="gamma-generate"]').disabled).toBe(true);
  expect(global.fetch.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(0);
  expect(container.textContent).toContain('azul · branco');
  await act(async () => container.querySelector('[aria-label="Oceano"]').click());
  expect(container.querySelector('[data-testid="gamma-generate"]').disabled).toBe(false);
  await act(async () => container.querySelector('[data-testid="gamma-generate"]').click());
  const body = JSON.parse(global.fetch.mock.calls.find(([, options]) => options?.method === 'POST')[1].body);
  expect(body.themeId).toBe('ocean'); expect(body).not.toHaveProperty('templateId');
});

test('changing theme to template clears selection and sends template only', async () => {
  await open(); await fill();
  global.fetch.mockImplementation(async (url, options) => ({ok: true, json: async () => options?.method === 'POST'
    ? {id: 'job', status: 'pending'} : {items: [{id: url.includes('kind=themes') ? 'theme' : 'model', name: 'Escolha', source: 'official'}], nextCursor: null}}));
  async function mode(value) { await act(async () => { const select = container.querySelector('[aria-label="Modo visual Gamma"]'); select.value = value; select.dispatchEvent(new Event('change', {bubbles:true})); }); }
  await mode('theme');
  await act(async () => container.querySelector('[aria-label="Escolha"]').click());
  await mode('template');
  expect(container.querySelector('[data-testid="gamma-generate"]').disabled).toBe(true);
  await act(async () => container.querySelector('[aria-label="Escolha"]').click());
  await act(async () => container.querySelector('[data-testid="gamma-generate"]').click());
  const body = JSON.parse(global.fetch.mock.calls.find(([, options]) => options?.method === 'POST')[1].body);
  expect(body.templateId).toBe('model'); expect(body).not.toHaveProperty('themeId');
});

test('catalog failure can be bypassed by returning to automatic without paid requests', async () => {
  await open(); await fill();
  global.fetch.mockRejectedValue(new Error('Catálogo temporariamente indisponível'));
  const select = container.querySelector('[aria-label="Modo visual Gamma"]');
  await act(async () => { select.value = 'theme'; select.dispatchEvent(new Event('change', {bubbles:true})); });
  expect(container.textContent).toContain('Catálogo temporariamente indisponível');
  expect(container.querySelector('[data-testid="gamma-generate"]').disabled).toBe(true);
  await act(async () => { select.value = 'auto'; select.dispatchEvent(new Event('change', {bubbles:true})); });
  expect(container.querySelector('[data-testid="gamma-generate"]').disabled).toBe(false);
  expect(global.fetch.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(0);
});

test('tabs keep content while changing steps and footer actions remain outside the scroll body', async () => {
  await open(); await fill();
  expect(container.querySelector('#gamma-panel-content').hidden).toBe(false);
  await act(async () => container.querySelector('[data-step="design"]').click());
  expect(container.querySelector('#gamma-panel-content').hidden).toBe(true);
  expect(container.querySelector('#gamma-panel-design').hidden).toBe(false);
  expect(container.querySelector('[aria-label="Título Gamma"]').value).toBe('Teste técnico Gamma');
  expect(container.querySelector('.gamma-footer [data-testid="gamma-generate"]')).not.toBeNull();
  expect(container.querySelector('.gamma-body [data-testid="gamma-generate"]')).toBeNull();
  await act(async () => container.querySelector('[data-step="history"]').click());
  expect(container.querySelector('#gamma-panel-history').hidden).toBe(false);
});

test('slide quantity is editable and sent to backend, never fixed at five', async()=>{
  await open(); await fill();
  const input=container.querySelector('[aria-label="Quantidade de slides Gamma"]');
  await act(async()=>{Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,'25');input.dispatchEvent(new Event('input',{bubbles:true}));});
  expect(container.querySelector('[data-testid="gamma-generate"]').textContent).toBe('Gerar 25 slides');
  global.fetch.mockResolvedValue({ok:true,json:async()=>({id:'job',title:'Teste',status:'pending',numCards:25})});
  await act(async()=>container.querySelector('[data-testid="gamma-generate"]').click());
  const call=global.fetch.mock.calls.find(([,options])=>options?.method==='POST');
  expect(JSON.parse(call[1].body).numCards).toBe(25);
  expect(container.textContent).toContain('Quantidade solicitada: 25');
});

test('empty, zero, fractional and oversized slide quantities disable paid generation', async()=>{
  await open(); await fill();
  const input=container.querySelector('[aria-label="Quantidade de slides Gamma"]');
  for(const value of ['', '0','1.5','101']){
    await act(async()=>{Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,value);input.dispatchEvent(new Event('input',{bubbles:true}));});
    expect(container.querySelector('[data-testid="gamma-generate"]').disabled).toBe(true);
  }
  await act(async()=>{Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,'100');input.dispatchEvent(new Event('input',{bubbles:true}));});
  expect(container.querySelector('[data-testid="gamma-generate"]').disabled).toBe(false);
  expect(container.querySelector('[data-testid="gamma-generate"]').textContent).toBe('Gerar 100 slides');
  expect(global.fetch.mock.calls.filter(([,options])=>options?.method==='POST')).toHaveLength(0);
});

test('catalog paginates six colorful cards without an inner scrolling region', async () => {
  await open();
  global.fetch.mockResolvedValue({ok:true,json:async()=>({items:Array.from({length:13},(_,i)=>({id:`theme${i}`,name:`Tema ${i}`,colors:i%2?['blue','white']:['gold','black'],source:'standard'}))})});
  await act(async()=>{const select=container.querySelector('[aria-label="Modo visual Gamma"]');select.value='theme';select.dispatchEvent(new Event('change',{bubbles:true}));});
  expect(container.querySelectorAll('.gamma-design-card')).toHaveLength(6);
  expect(container.querySelectorAll('.gamma-palette i').length).toBeGreaterThan(6);
  expect(container.querySelector('.gamma-design-grid').className).not.toContain('overflow');
  await act(async()=>container.querySelector('[aria-label="Próximos visuais"]').click());
  expect(container.querySelector('[aria-label="Tema 6"]')).not.toBeNull();
  expect(container.querySelector('[aria-label="Tema 0"]')).toBeNull();
  await act(async()=>container.querySelector('[aria-label="Tema 6"]').click());
  expect(container.querySelector('.gamma-design-card.selected').textContent).toContain('Selecionado');
});
