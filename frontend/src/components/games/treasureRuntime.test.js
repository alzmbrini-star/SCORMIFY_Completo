import { treasureRuntime } from './treasureRuntime';
import { generateAdvancedGameHtml } from './advancedGameTemplates';
import { upgradeTreasureHtml } from '../../utils/treasureHtml';

let env,game;
const nodes=()=>[...document.querySelectorAll('.map .route .node')];
beforeEach(()=>{
  jest.useFakeTimers();
  const questions=Array.from({length:4},(_,i)=>({id:'q'+i,question:'Pergunta '+i,alternatives:[{id:'a',text:'Correta'},{id:'b',text:'Incorreta'}],correctAnswer:'a'}));
  const html=generateAdvancedGameHtml({gameType:'treasure',title:'Mapa',questions,config:{time:3,lives:3}});
  const doc=new DOMParser().parseFromString(html,'text/html');document.body.innerHTML=doc.body.innerHTML;
  env=new Function(doc.querySelector('script').textContent+';return {Game,BANK,QE};')();game=env.Game;
  new Function('return ('+treasureRuntime.toString()+');')()(game,env.BANK,env.QE,document.getElementById('stage'));
  game.start();
});
afterEach(()=>{jest.clearAllTimers();jest.useRealTimers();document.body.replaceChildren();document.getElementById('treasure-style-v1')?.remove();});

test('wrong answer marks the stage red immediately and remains wrong after advancing',()=>{
  document.querySelectorAll('.answer')[1].click();
  expect(nodes()[0].classList.contains('missed')).toBe(true);
  expect(nodes()[0].textContent).toBe('✕');expect(nodes()[0].classList.contains('open')).toBe(false);
  expect(getComputedStyle(nodes()[0]).backgroundColor).toBe('rgb(185, 28, 28)');
  expect(game.xp).toBe(0);expect(game.lives).toBe(2);
  jest.advanceTimersByTime(1100);
  expect(nodes()[0].classList.contains('missed')).toBe(true);
  expect(nodes()[1].classList.contains('current')).toBe(true);
});

test('correct answer marks green and keeps the original points',()=>{
  document.querySelectorAll('.answer')[0].click();
  expect(nodes()[0].classList.contains('correct')).toBe(true);expect(nodes()[0].textContent).toBe('✓');
  expect(getComputedStyle(nodes()[0]).backgroundColor).toBe('rgb(21, 128, 61)');
  expect(game.xp).toBe(125);expect(game.coins).toBe(15);expect(game.lives).toBe(3);
});

test('timeout is a red miss, not a green completed stage',()=>{
  jest.advanceTimersByTime(3000);
  expect(nodes()[0].classList.contains('missed')).toBe(true);
  expect(nodes()[0].getAttribute('aria-label')).toContain('tempo esgotado');
  expect(game.treasureResults).toEqual([false]);expect(game.xp).toBe(0);
});

test('mixed results, click lock and restart preserve independent stages',()=>{
  const wrong=document.querySelectorAll('.answer')[1];wrong.click();
  game.answer(env.BANK[0],0,wrong);expect(game.treasureResults).toEqual([false]);
  jest.advanceTimersByTime(1100);document.querySelectorAll('.answer')[0].click();
  jest.advanceTimersByTime(1100);
  expect(game.treasureResults).toEqual([false,true]);
  expect(nodes()[0].textContent).toBe('✕');expect(nodes()[1].textContent).toBe('✓');
  expect(nodes()[2].classList.contains('current')).toBe(true);
  expect(nodes()[3].textContent).toBe('💎');
  game.restart();expect(game.treasureResults).toEqual([]);
  expect(nodes().some(node=>node.classList.contains('correct')||node.classList.contains('missed'))).toBe(false);
});

test('legacy upgrade is idempotent and leaves other game types alone',()=>{
  const source='<html><body><script>const QE={};const SETTINGS={"type":"treasure"};function renderAdventure(){}</script></body></html>';
  const html=upgradeTreasureHtml(source);expect(html).toContain('scormify-treasure-v1');
  expect(upgradeTreasureHtml(html)).toBe(html);
  expect(upgradeTreasureHtml(source.replace('"treasure"','"race"'))).toBe(source.replace('"treasure"','"race"'));
});
