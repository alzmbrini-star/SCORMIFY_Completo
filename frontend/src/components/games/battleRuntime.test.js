import { battleRuntime } from './battleRuntime';
import { generateAdvancedGameHtml } from './advancedGameTemplates';
import { upgradeBattleHtml } from '../../utils/battleHtml';

let game, env;
const questions=Array.from({length:5},(_,i)=>({id:'q'+i,question:'Pergunta '+i,alternatives:[{id:'a',text:'Correta'},{id:'b',text:'Incorreta'}],correctAnswer:'a',explanation:'Explicação'}));
const bar=side=>document.querySelector('.battle-energy[data-side="'+side+'"]');
function answer(correct=true){document.querySelectorAll('.answer')[correct?0:1].click();}
beforeEach(()=>{
  jest.useFakeTimers();
  const html=generateAdvancedGameHtml({gameType:'battle',title:'Batalha',questions,config:{lives:3,time:3}});
  const doc=new DOMParser().parseFromString(html,'text/html');document.body.innerHTML=doc.body.innerHTML;
  env=new Function(doc.querySelector('script').textContent+';return {Game,BANK,QE,SETTINGS};')();game=env.Game;
  const save=env.QE.saveResult;env.QE.results=[];
  env.QE.saveResult=function(result){this.results.push(result);return save.call(this,result);};
  new Function('return ('+battleRuntime.toString()+');')()(game,env.BANK,env.QE,document.getElementById('stage'),env.SETTINGS);
  game.start();
});
afterEach(()=>{jest.clearAllTimers();jest.useRealTimers();document.body.replaceChildren();document.getElementById('battle-style-v1')?.remove();});

test('energy bars are named and numeric with reduced-motion support',()=>{
  expect(bar('hero').getAttribute('aria-label')).toBe('Sua energia');
  expect(bar('enemy').getAttribute('aria-label')).toBe('Energia do adversário');
  expect(bar('hero').getAttribute('aria-valuenow')).toBe('100');
  expect(document.querySelector('.battle-value').textContent).toBe('100%');
  expect(document.getElementById('battle-style-v1').textContent).toContain('prefers-reduced-motion');
});

test('correct answer immediately updates energy and animates attack and impact once',()=>{
  answer();
  expect(game.enemyHealth).toBe(80);expect(game.heroHealth).toBe(100);
  expect(bar('enemy').getAttribute('aria-valuenow')).toBe('80');
  expect(bar('enemy').querySelector('i').style.width).toBe('80%');
  expect(document.querySelector('.hero.battle-attack-right')).not.toBeNull();
  expect(document.querySelector('.enemy.battle-impact')).not.toBeNull();
  expect(document.querySelector('.battle-message').textContent).toContain('Você atacou');
  game.answer(env.BANK[0],0,document.querySelector('.answer'));
  expect(game.xp).toBe(125);expect(game.coins).toBe(15);expect(game.index).toBe(1);
  jest.advanceTimersByTime(1100);expect(game.seconds).toBe(3);
  jest.advanceTimersByTime(100);expect(game.locked).toBe(false);
  expect(bar('enemy').getAttribute('aria-valuenow')).toBe('80');
  expect(document.querySelector('.battle-projectile')).toBeNull();
});

test('wrong answer produces enemy attack, hero impact and immediate loss of a life',()=>{
  answer(false);
  expect(game.heroHealth).toBe(80);expect(game.lives).toBe(2);expect(game.enemyHealth).toBe(100);
  expect(bar('hero').getAttribute('aria-valuenow')).toBe('80');
  expect(document.querySelector('.enemy.battle-attack-left')).not.toBeNull();
  expect(document.querySelector('.hero.battle-impact')).not.toBeNull();
  expect(game.xp).toBe(0);
});

test('timeout resolves once, displays feedback and pauses the timer during animation',()=>{
  jest.advanceTimersByTime(3000);
  expect(game.seconds).toBe(0);expect(game.lives).toBe(2);expect(game.index).toBe(1);
  expect(bar('hero').getAttribute('aria-valuenow')).toBe('80');
  expect(document.querySelector('.battle-message').textContent).toContain('Tempo esgotado');
  expect(env.QE.results[0]).toMatchObject({correct:false,reason:'timeout'});
  jest.advanceTimersByTime(1199);expect(game.lives).toBe(2);
  jest.advanceTimersByTime(1);expect(game.seconds).toBe(3);expect(game.index).toBe(1);
});

test('restart cancels pending transition and starts with a single timer and full energy',()=>{
  answer();game.restart();
  expect(game.xp).toBe(0);expect(game.index).toBe(0);expect(game.lives).toBe(3);
  expect(bar('enemy').getAttribute('aria-valuenow')).toBe('100');
  expect(document.querySelector('.battle-projectile')).toBeNull();
  jest.advanceTimersByTime(1200);
  expect(game.index).toBe(0);expect(game.seconds).toBe(2);expect(game.heroHealth).toBe(100);
});

test('victory keeps the existing scoring and reports completion only once',()=>{
  for(let i=0;i<5;i++){answer();jest.advanceTimersByTime(1200);}
  expect(game.enemyHealth).toBe(0);expect(game.xp).toBe(625);expect(game.coins).toBe(75);
  expect(env.QE.results.filter(result=>result.complete)).toHaveLength(1);
  expect(env.QE.results.find(result=>result.complete).accuracy).toBe(100);
  game.end();jest.advanceTimersByTime(60000);
  expect(game.lives).toBe(3);expect(env.QE.results.filter(result=>result.complete)).toHaveLength(1);
});

test('defeat stops damage and timers after the last life',()=>{
  for(let i=0;i<3;i++){answer(false);jest.advanceTimersByTime(1200);}
  expect(game.lives).toBe(0);expect(game.heroHealth).toBe(40);
  jest.advanceTimersByTime(60000);expect(game.heroHealth).toBe(40);
  expect(env.QE.results.filter(result=>result.complete)).toHaveLength(1);
});

test('legacy HTML upgrade is idempotent and ignores other game types',()=>{
  const html='<html><body><script>const QE={};const SETTINGS={"type":"battle"};const Game={enemyHealth:100};</script></body></html>';
  expect(upgradeBattleHtml(html)).toContain('scormify-battle-v1');
  expect(upgradeBattleHtml(upgradeBattleHtml(html))).toBe(upgradeBattleHtml(html));
  expect(upgradeBattleHtml(html.replace('"battle"','"race"'))).toBe(html.replace('"battle"','"race"'));
});
