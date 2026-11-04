import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import VideoQuizDialog from './VideoQuizDialog';

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
jest.mock('../../contexts/AuthContext', () => ({authHeaders: () => ({Authorization: 'Bearer test'})}));
jest.mock('../../utils/apiUrl', () => ({getApiUrl: () => 'https://api.example'}));
jest.mock('../ui/button', () => ({Button: ({children, variant, ...props}) => <button {...props}>{children}</button>}));
jest.mock('../ui/input', () => ({Input: props => <input {...props} />}));
jest.mock('../ui/textarea', () => ({Textarea: props => <textarea {...props} />}));
jest.mock('../ui/dialog', () => ({Dialog: ({children, open}) => open ? <div>{children}</div> : null, DialogContent: ({children}) => <div>{children}</div>, DialogHeader: ({children}) => <div>{children}</div>, DialogTitle: ({children}) => <h1>{children}</h1>, DialogDescription: ({children}) => <p>{children}</p>}));
describe('interactive avatar video authoring', () => {
  let container, root;
  const config = {src: 'https://example.org/video.mp4', title: 'Avatar', checkpoints: [{at: 10, question: 'Qual?', options: ['A', 'B'], correctIndex: 1, explanation: 'Porque B.', maxAttempts: 3}]};
  beforeEach(() => { container = document.createElement('div'); document.body.append(container); root = createRoot(container); global.fetch = jest.fn(); });
  afterEach(async () => { await act(async () => root.unmount()); container.remove(); jest.restoreAllMocks(); });
  test('reopens saved checkpoints and updates the same element only on Apply', async () => {
    const apply = jest.fn(), close = jest.fn();
    await act(async () => root.render(<VideoQuizDialog open element={{type: 'html', videoQuizConfig: config}} onApply={apply} onOpenChange={close} />));
    expect(container.querySelector('[aria-label="Enunciado 1"]').value).toBe('Qual?');
    expect(apply).not.toHaveBeenCalled(); expect(fetch).not.toHaveBeenCalled();
    fetch.mockResolvedValue({ok: true, json: async () => ({config, htmlContent: '<html>controlled</html>'})});
    await act(async () => [...container.querySelectorAll('button')].find(b => b.textContent === 'Aplicar ao vídeo').click());
    expect(JSON.parse(fetch.mock.calls[0][1].body).checkpoints[0].maxAttempts).toBe(3);
    expect(apply).toHaveBeenCalledWith(expect.objectContaining({type: 'html', videoQuizConfig: config, htmlDisplayMode: 'page'}));
    expect(close).toHaveBeenCalledWith(false);
  });
  test('failed validation preserves the course and displays the error', async () => {
    const apply = jest.fn();
    await act(async () => root.render(<VideoQuizDialog open element={{src: config.src}} onApply={apply} onOpenChange={() => {}} />));
    fetch.mockResolvedValue({ok: false, json: async () => ({detail: 'Informe a explicação.'})});
    await act(async () => [...container.querySelectorAll('button')].find(b => b.textContent === 'Aplicar ao vídeo').click());
    expect(container.querySelector('[role="alert"]').textContent).toBe('Informe a explicação.'); expect(apply).not.toHaveBeenCalled();
  });
  test('Cancel does not generate AI, build or alter the element', async () => {
    const apply = jest.fn(), close = jest.fn();
    await act(async () => root.render(<VideoQuizDialog open element={{src: config.src}} onApply={apply} onOpenChange={close} />));
    await act(async () => [...container.querySelectorAll('button')].find(b => b.textContent === 'Cancelar').click());
    expect(fetch).not.toHaveBeenCalled(); expect(apply).not.toHaveBeenCalled(); expect(close).toHaveBeenCalledWith(false);
  });
  test('project video URLs point at the backend rather than the separate static frontend', async () => {
    await act(async () => root.render(<VideoQuizDialog open element={{id: 'v1', src: '/api/projects/p1/assets/avatar.mp4'}} onApply={() => {}} onOpenChange={() => {}} />));
    expect(container.querySelector('video').getAttribute('src')).toBe('https://api.example/api/projects/p1/assets/avatar.mp4');
  });
  test('preserving video transparency is enabled by default', async () => {
    await act(async () => root.render(<VideoQuizDialog open element={{src: 'https://example.org/alpha.webm'}} onApply={() => {}} onOpenChange={() => {}} />));
    const label = [...container.querySelectorAll('label')].find(n => n.textContent.includes('Preservar fundo transparente'));
    expect(label.querySelector('input').checked).toBe(true);
  });
});
