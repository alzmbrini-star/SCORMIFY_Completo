import { climbRuntime } from './climbRuntime';
import { generateAdvancedGameHtml } from './advancedGameTemplates';
import { upgradeClimbHtml } from '../../utils/climbHtml';

let game,env;
const avatar=()=>document.querySelector('.climb-avatar');
function answer(correct=true){document.querySelectorAll('.answer')[correct?0:1].click();}
beforeEach(()=>{
  jest.useFakeTimers();
  const questions=Array.from({length:10},(_,i)=>({id:'q'+i,question:'Pergunta '+i,alternatives:[{id:'a',text:'Correta'},{id:'b',text:'Incorreta'}],correctAnswer:'a'}));
  const html=generateAdvancedGameHtml({gameType:'climb',title:'Escalada',questions,config:{time:3,lives:3}});
  const doc=new DOMParser().parseFromString(html,'text/html');document.body.innerHTML=doc.body.innerHTML;
  env=new Function(doc.querySelector('script').textContent+';return {Game,BANK,QE,SETTINGS};')();game=env.Game;
  const save=env.QE.saveResult;env.QE.results=[];env.QE.saveResult=function(result){this.results.push(result);return save.call(this,result);};
  new Function('return ('+climbRuntime.toString()+');')()(game,env.BANK,env.QE,document.getElementById('stage'),env.SETTINGS);
  game.start();
});
afterEach(()=>{jest.clearAllTimers();jest.useRealTimers();document.body.replaceChildren();document.getElementById('climb-style-v1')?.remove();});

test('correct answers move diagonally along the mountain and update climb progress immediately',()=>{
  expect(avatar().style.left).toBe('13%');expect(avatar().style.top).toBe('80%');
  answer();
  expect(avatar().style.left).toBe('20.2%');expect(avatar().style.top).toBe('73.6%');
  expect(document.querySelector('.climb-step')).not.toBeNull();
  expect(document.querySelector('.climb-meter').getAttribute('aria-valuenow')).toBe('10');
  expect(document.getElementById('bar').style.width).toBe('10%');
  expect(game.xp).toBe(125);expect(game.coins).toBe(15);expect(game.enemyHealth).toBe(100);
  jest.advanceTimersByTime(1200);
  expect(document.querySelector('.climb-question-progress').textContent).toBe('Pergunta 2 de 10');
  expect(avatar().style.top).toBe('73.6%');
});

test('errors consume lives without climbing; mixed progress counts only correct answers',()=>{
  answer(false);expect(game.lives).toBe(2);expect(avatar().style.top).toBe('80%');
  expect(document.querySelector('.climb-slip')).not.toBeNull();
  jest.advanceTimersByTime(1200);answer();jest.advanceTimersByTime(1200);answer(false);
  expect(game.index).toBe(3);expect(game.correct).toBe(1);expect(game.lives).toBe(1);
  expect(document.getElementById('bar').style.width).toBe('10%');
  expect(document.querySelector('.climb-status').textContent).toContain('não avançou');
});

test('timeout does not climb, records one miss and pauses during feedback',()=>{
  jest.advanceTimersByTime(3000);
  expect(game.lives).toBe(2);expect(game.index).toBe(1);expect(game.seconds).toBe(0);
  expect(avatar().style.top).toBe('80%');expect(env.QE.results[0].reason).toBe('timeout');
  jest.advanceTimersByTime(1199);expect(game.lives).toBe(2);
  jest.advanceTimersByTime(1);expect(game.seconds).toBe(3);
});

test('more than five correct answers do not trigger the battle enemy-health ending',()=>{
  for(let i=0;i<6;i++){answer();jest.advanceTimersByTime(1200);}
  expect(game.index).toBe(6);expect(game.enemyHealth).toBe(100);
  expect(env.QE.results.some(result=>result.complete)).toBe(false);
  for(let i=6;i<10;i++){answer();jest.advanceTimersByTime(1200);}
  expect(game.xp).toBe(1250);expect(game.coins).toBe(150);
  expect(env.QE.results.filter(result=>result.complete)).toHaveLength(1);
  expect(env.QE.results.find(result=>result.complete).accuracy).toBe(100);
  expect(document.getElementById('finishText').textContent).toContain('Topo alcançado');
  jest.advanceTimersByTime(60000);expect(game.lives).toBe(3);
});

test('restart cancels pending movement and resets points, position and a single timer',()=>{
  answer();game.restart();
  expect(game.xp).toBe(0);expect(game.correct).toBe(0);expect(avatar().style.top).toBe('80%');
  jest.advanceTimersByTime(1200);expect(game.index).toBe(0);expect(game.seconds).toBe(2);
  expect(document.querySelector('.climb-step')).toBeNull();
});

test('last life ends the game without negative lives or more timeout damage',()=>{
  for(let i=0;i<3;i++){answer(false);jest.advanceTimersByTime(1200);}
  expect(game.lives).toBe(0);expect(env.QE.results.filter(result=>result.complete)).toHaveLength(1);
  jest.advanceTimersByTime(60000);expect(game.lives).toBe(0);
});

test('legacy upgrade is idempotent and leaves other games unchanged',()=>{
  const source='<html><body><script>const QE={};const SETTINGS={"type":"climb"};function renderAdventure(){}</script></body></html>';
  expect(upgradeClimbHtml(source)).toContain('scormify-climb-v1');
  expect(upgradeClimbHtml(upgradeClimbHtml(source))).toBe(upgradeClimbHtml(source));
  expect(upgradeClimbHtml(source.replace('"climb"','"race"'))).toBe(source.replace('"climb"','"race"'));
});
