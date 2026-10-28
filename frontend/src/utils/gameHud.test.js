import { upgradeGameHud } from './gameHud';
import { generateEducationalGameHtml } from '../components/games/gameTemplates';
import { wrapInteractiveFullbleed } from './htmlUtils';

const questions = Array.from({length:5}, (_,i) => ({id:`q${i}`,question:'Qual ação é correta?',alternatives:[{id:'a',text:'Correta'},{id:'b',text:'Incorreta'}],correctAnswer:'a'}));
const generate = type => generateEducationalGameHtml({gameType:type,title:'Teste',questions,config:{lives:3,time:30,shuffle:false}});

test.each(['penalty','quiz_show','memory','hangman','climb','crossword','sudoku','race','battle','treasure'])('%s has labeled, enlarged metrics with unchanged game script and IDs', type => {
  const original = generate(type); const upgraded = upgradeGameHud(original);
  const doc = new DOMParser().parseFromString(upgraded,'text/html');
  expect(doc.querySelectorAll('.hud-metric').length).toBe(4);
  expect(doc.querySelector('.hud-timer .hud-label').textContent).toBe('⏱ Tempo');
  expect(doc.querySelector('.hud-xp .hud-label').textContent).toBe('⭐ Pontuação');
  for (const id of ['lives','timer','xp','coins']) expect(doc.querySelectorAll(`#${id}`).length).toBe(1);
  expect(doc.querySelector('script').textContent).toBe(new DOMParser().parseFromString(original,'text/html').querySelector('script').textContent);
  expect(upgradeGameHud(upgraded)).toBe(upgraded);
  expect(wrapInteractiveFullbleed(original,'fit')).toContain('scormify-game-hud-v1');
});

test('leaves unrelated pages untouched', () => {
  const html='<html><body><span class="chip">Normal</span></body></html>';
  expect(upgradeGameHud(html)).toBe(html);
});

test('quiz timer, correct score and restart still update the same metrics', () => {
  jest.useFakeTimers();
  const doc = new DOMParser().parseFromString(upgradeGameHud(generate('quiz_show')),'text/html');
  document.body.innerHTML=doc.body.innerHTML;
  const script=doc.querySelector('script').textContent;
  const game = new Function(script+';return Game;')();
  game.start();
  jest.advanceTimersByTime(1000);
  expect(document.getElementById('timer').textContent).toBe('29');
  document.querySelector('.answer').click();
  expect(document.getElementById('xp').textContent).toBe('100');
  expect(document.getElementById('coins').textContent).toBe('10');
  game.restart();
  expect(document.getElementById('xp').textContent).toBe('0');
  expect(document.getElementById('timer').textContent).toBe('30');
  jest.clearAllTimers(); jest.useRealTimers(); document.body.replaceChildren();
});
