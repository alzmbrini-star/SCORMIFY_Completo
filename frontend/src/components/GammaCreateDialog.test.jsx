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
  await act(async () => [...container.querySelectorAll('button')].find(b => b.textContent === 'Oceano').click());
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
  await act(async () => [...container.querySelectorAll('button')].find(b => b.textContent === 'Escolha').click());
  await mode('template');
  expect(container.querySelector('[data-testid="gamma-generate"]').disabled).toBe(true);
  await act(async () => [...container.querySelectorAll('button')].find(b => b.textContent === 'Escolha').click());
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
