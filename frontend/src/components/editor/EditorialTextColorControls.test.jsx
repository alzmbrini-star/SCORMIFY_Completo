import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import EditorialTextColorControls from './EditorialTextColorControls';
import { readEditorialTextColors } from '../../utils/editorialTextColors';

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
jest.mock('../ui/button', () => ({ Button: ({children, size, variant, ...props}) => <button {...props}>{children}</button> }));

test.each([
  ['cover','<h1>Nome do curso</h1><p>Introdução</p>'],
  ['content','<table><tr><td>Informação</td></tr></table>'],
  ['game','<div id="app"></div><script>startGame()</script>'],
  ['custom simulator','<canvas></canvas><button>Executar</button><script>simulate()</script>'],
  ['summary','<ul><li>Resumo</li></ul>'],
])('controls are available in %s without changing content or scripts', (name, htmlContent) => {
  const container = document.createElement('div'); document.body.appendChild(container);
  const root = createRoot(container); const update = jest.fn();
  act(() => root.render(<EditorialTextColorControls element={{type:'html',htmlContent}} onUpdate={update} />));
  expect(container.querySelector('[data-testid="editorial-text-colors"]')).not.toBeNull();
  act(() => [...container.querySelectorAll('button')].find(b => b.textContent === 'Contraste para fundo claro').click());
  const next = update.mock.calls[0][0];
  expect(next.htmlContent).toContain(htmlContent);
  expect(readEditorialTextColors(next.htmlContent).text).toBe('#172c49');
  act(() => root.render(<EditorialTextColorControls element={{type:'html',...next}} onUpdate={update} />));
  act(() => [...container.querySelectorAll('button')].find(b => b.textContent === 'Restaurar cores originais').click());
  expect(update.mock.calls[1][0].htmlContent).toBe(htmlContent);
  act(() => root.unmount()); container.remove();
});

test('assessment colors are also saved in its controlled renderer config', () => {
  const container = document.createElement('div'); const root = createRoot(container); const update = jest.fn();
  const element = {type:'html',htmlContent:'<p>Prova</p>',assessmentConfig:{questionIds:['one'],passingScore:70}};
  act(() => root.render(<EditorialTextColorControls element={element} onUpdate={update} />));
  act(() => [...container.querySelectorAll('button')].find(b => b.textContent === 'Contraste para fundo escuro').click());
  expect(update.mock.calls[0][0].assessmentConfig).toMatchObject({questionIds:['one'],passingScore:70,textColors:{text:'#e2e8f0'}});
  act(() => root.unmount());
});
