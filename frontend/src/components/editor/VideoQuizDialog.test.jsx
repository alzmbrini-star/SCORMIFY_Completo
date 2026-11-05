import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import VideoQuizDialog from './VideoQuizDialog';

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
jest.mock('../../contexts/AuthContext', () => ({authHeaders: () => ({Authorization: 'Bearer test'})}));
jest.mock('../../utils/apiUrl', () => ({getApiUrl: () => 'https://api.example'}));
jest.mock('sonner', () => ({toast: {success: jest.fn()}}));
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
    const apply = jest.fn().mockResolvedValue({videoQuizConfig: config}), close = jest.fn();
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
    expect(container.querySelector('[role="alert"]').textContent).toContain('preencha a explicação'); expect(apply).not.toHaveBeenCalled();
  });
  test('Cancel does not generate AI, build or alter the element', async () => {
    const apply = jest.fn(), close = jest.fn();
    await act(async () => root.render(<VideoQuizDialog open element={{src: config.src}} onApply={apply} onOpenChange={close} />));
    await act(async () => [...container.querySelectorAll('button')].find(b => b.textContent === 'Cancelar').click());
    expect(fetch).not.toHaveBeenCalled(); expect(apply).not.toHaveBeenCalled(); expect(close).toHaveBeenCalledWith(false);
  });
  test('embedded videos offer a provider preview without suppressing its srcdoc referrer',async()=>{
    await act(async()=>root.render(<VideoQuizDialog open element={{id:'embedded',type:'video',embedUrl:'https://vimeo.com/76979871'}} onApply={jest.fn()} onOpenChange={jest.fn()}/>));
    expect(container.querySelector('[aria-label="Link ou iframe do vídeo"]').value).toBe('https://vimeo.com/76979871');
    const frame=container.querySelector('iframe[title="Prévia do vídeo externo"]');
    expect(frame).not.toBeNull();expect(frame.hasAttribute('referrerpolicy')).toBe(false);
    expect(frame.getAttribute('srcdoc')).toContain('player.vimeo.com/video/76979871');
    expect(fetch).not.toHaveBeenCalled();
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
  test('adds a second question, ignores unused options, saves and reopens both', async () => {
    const close = jest.fn(), apply = jest.fn(async payload => payload);
    const render = (open, element) => root.render(<VideoQuizDialog open={open} element={element} onApply={apply} onOpenChange={close} />);
    await act(async () => render(true, {id:'v1', videoQuizConfig:config}));
    const click = label => [...container.querySelectorAll('button')].find(b => b.textContent === label).click();
    await act(async () => click('Adicionar pausa com pergunta'));
    const set = async (label, value) => { await act(async () => { const field=container.querySelector(`[aria-label="${label}"]`); const proto=field.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype; Object.getOwnPropertyDescriptor(proto,'value').set.call(field,value);field.dispatchEvent(new Event('input',{bubbles:true})); }); };
    await set('Enunciado 2','Segunda?'); await set('Alternativa 1 da pergunta 2','Sim'); await set('Alternativa 2 da pergunta 2','Não');
    await act(async () => click('Aplicar ao vídeo'));
    expect(container.querySelector('[role="alert"]').textContent).toContain('Pergunta 2: preencha a explicação');
    expect(fetch).not.toHaveBeenCalled();
    await set('Explicação 2','Sim é a resposta.');
    // A same-element parent refresh must not erase the unsaved question.
    await act(async () => render(true,{id:'v1',videoQuizConfig:config}));
    expect(container.querySelector('[aria-label="Enunciado 2"]').value).toBe('Segunda?');
    fetch.mockImplementation(async (url, options) => ({ok:true,json:async()=>({config:JSON.parse(options.body),htmlContent:'<html>two</html>'})}));
    await act(async () => click('Aplicar ao vídeo'));
    const saved=apply.mock.calls[0][0];
    expect(saved.videoQuizConfig.checkpoints).toHaveLength(2);
    expect(saved.videoQuizConfig.checkpoints[1].options).toEqual(['Sim','Não']);
    expect(close).toHaveBeenCalledWith(false);
    await act(async () => render(false,{id:'v1',...saved}));
    await act(async () => render(true,{id:'v1',...saved}));
    expect(container.querySelector('[aria-label="Enunciado 2"]').value).toBe('Segunda?');
    expect(container.querySelector('[aria-label="Enunciado 1"]').value).toBe('Qual?');
  });
  test('does not close when persistence fails or does not acknowledge all checkpoints', async () => {
    const close=jest.fn(), apply=jest.fn().mockResolvedValue(undefined);
    await act(async()=>root.render(<VideoQuizDialog open element={{id:'v1',videoQuizConfig:config}} onApply={apply} onOpenChange={close}/>));
    fetch.mockResolvedValue({ok:true,json:async()=>({config,htmlContent:'<html/>'})});
    await act(async()=>[...container.querySelectorAll('button')].find(b=>b.textContent==='Aplicar ao vídeo').click());
    expect(close).not.toHaveBeenCalled();
    expect(container.querySelector('[role="alert"]').textContent).toContain('rascunho foi preservado');
    expect(container.querySelector('[aria-label="Enunciado 1"]').value).toBe('Qual?');
  });
  test('legacy HTML can be reopened and explicitly switched to graded',async()=>{
    const apply=jest.fn(async value=>value),close=jest.fn();
    const html='<script id="video-quiz-data" type="application/json">'+JSON.stringify(config)+'</script>';
    await act(async()=>root.render(<VideoQuizDialog open element={{id:'legacy',type:'html',htmlContent:html,width:1920,height:820}} onApply={apply} onOpenChange={close}/>));
    expect(container.querySelector('[aria-label="Enunciado 1"]').value).toBe('Qual?');
    const select=container.querySelector('[aria-label="Vale nota?"]');expect(select.value).toBe('no');
    await act(async()=>{select.value='yes';select.dispatchEvent(new Event('change',{bubbles:true}));});
    fetch.mockImplementation(async(url,options)=>({ok:true,json:async()=>({config:JSON.parse(options.body),htmlContent:'<html>graded</html>'})}));
    await act(async()=>[...container.querySelectorAll('button')].find(b=>b.textContent==='Aplicar ao vídeo').click());
    expect(apply.mock.calls[0][0].videoQuizConfig.graded).toBe(true);
    expect(apply.mock.calls[0][0].videoQuizConfig.checkpoints).toHaveLength(1);
    expect(close).toHaveBeenCalledWith(false);
  });
});
