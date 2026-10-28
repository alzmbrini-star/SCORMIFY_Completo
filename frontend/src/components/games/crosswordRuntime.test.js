import { crosswordRuntime } from './crosswordRuntime';
import { generateAdvancedGameHtml } from './advancedGameTemplates';
import { upgradeCrosswordHtml } from '../../utils/crosswordHtml';

const words=['CRIATIVIDADE','EMPATIA','IDEACAO','PROTOTIPO','INOVACAO','TESTE'];
const questions=words.map((word,i)=>({id:'q'+i,question:'Pergunta '+(i+1),alternatives:[{id:'a',text:word},{id:'b',text:'Outra'}],correctAnswer:'a'}));
let game;
function inputAt(pos) { return document.querySelector('input[data-position="'+pos+'"]'); }
function type(input,letter) {input.value=letter;input.dispatchEvent(new Event('input',{bubbles:true}));}
function select(word) { [...document.querySelectorAll('.cross-clue')].find(b=>b.textContent.includes(word.q.question)).click(); }
beforeEach(()=>{
  jest.useFakeTimers();
  const html=generateAdvancedGameHtml({gameType:'crossword',title:'Teste',questions,config:{lives:3,time:30}});
  const doc=new DOMParser().parseFromString(html,'text/html');
  document.body.innerHTML=doc.body.innerHTML;
  const env=new Function(doc.querySelector('script').textContent+';return {Game,BANK,QE};')();
  game=env.Game;
  // Execute the serialized function, not an in-module closure.
  new Function('return ('+crosswordRuntime.toString()+');')()(game,env.BANK,env.QE,document.getElementById('stage'));
  game.start();
});
afterEach(()=>{jest.clearAllTimers();jest.useRealTimers();document.body.replaceChildren();document.getElementById('crossword-style-v2')?.remove();});

test('every clue maps to its numbered start, orientation and collision-free word',()=>{
  expect(game.cross.placements).toHaveLength(6);
  expect(document.querySelectorAll('.cross-clue')).toHaveLength(6);
  for(const p of game.cross.placements){
    expect(p.cells.map(pos=>game.cross.grid[pos]).join('')).toBe(p.word);
    expect(inputAt(p.cells[0]).parentElement.querySelector('.cross-number').textContent).toBe(String(p.number));
    select(p);
    expect(document.querySelectorAll('.word-active')).toHaveLength(p.word.length);
    expect(document.querySelector('.cross-clue[aria-pressed="true"]').textContent).toContain(p.vertical?'Vertical':'Horizontal');
    expect(document.activeElement).toBe(inputAt(p.cells[0]));
  }
});

test.each([false,true])('typing follows the active word (vertical=%s), including intersections and last cell',vertical=>{
  const p=game.cross.placements.find(word=>word.vertical===vertical);
  expect(p).toBeDefined(); select(p);
  p.cells.forEach((pos,i)=>{
    type(inputAt(pos),p.word[i]);
    expect(document.activeElement).toBe(inputAt(p.cells[Math.min(i+1,p.cells.length-1)]));
  });
});

test('accented input, rejected digits, backspace and paste support natural typing',()=>{
  const p=game.cross.placements[0];select(p);
  const first=inputAt(p.cells[0]);type(first,'é');expect(first.value).toBe('E');
  const second=inputAt(p.cells[1]);type(second,'7');expect(second.value).toBe('');expect(document.activeElement).toBe(second);
  second.dispatchEvent(new KeyboardEvent('keydown',{key:'Backspace',bubbles:true}));
  expect(document.activeElement).toBe(first);expect(first.value).toBe('');
  const paste=new Event('paste',{bubbles:true,cancelable:true});
  Object.defineProperty(paste,'clipboardData',{value:{getData:()=>p.word}});
  first.dispatchEvent(paste);
  expect(p.cells.map(pos=>inputAt(pos).value).join('')).toBe(p.word);
  expect(document.activeElement).toBe(inputAt(p.cells[p.cells.length-1]));
});

test('intersection Enter switches direction and score is credited only once',()=>{
  const pair=game.cross.placements.flatMap(p=>p.cells.map(pos=>({p,pos}))).find(({p,pos})=>game.cross.placements.some(other=>other!==p && other.cells.includes(pos)));
  expect(pair).toBeDefined();select(pair.p);inputAt(pair.pos).focus();
  const before=document.querySelector('.cross-clue[aria-pressed="true"]').textContent;
  inputAt(pair.pos).dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}));
  expect(document.querySelector('.cross-clue[aria-pressed="true"]').textContent).not.toBe(before);
  document.querySelectorAll('input.cell').forEach(input=>{input.value=input.dataset.solution;});
  game.validateCross();game.validateCross();expect(game.xp).toBe(500);
  game.restart();expect(game.xp).toBe(0);expect(document.querySelectorAll('input.cell').length).toBeGreaterThan(0);
});

test('legacy upgrade is idempotent; other games are unchanged',()=>{
  const legacy='<html><body><script>const QE={};const SETTINGS={"type":"crossword"};function renderCrossword(){}</script></body></html>';
  expect(upgradeCrosswordHtml(legacy)).toContain('scormify-crossword-v2');
  expect(upgradeCrosswordHtml(upgradeCrosswordHtml(legacy))).toBe(upgradeCrosswordHtml(legacy));
  expect(upgradeCrosswordHtml(legacy.replace('"crossword"','"climb"'))).toBe(legacy.replace('"crossword"','"climb"'));
});
