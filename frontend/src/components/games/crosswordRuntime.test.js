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
afterEach(()=>{jest.clearAllTimers();jest.useRealTimers();document.body.replaceChildren();document.getElementById('crossword-style-v4')?.remove();});

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
  expect(upgradeCrosswordHtml(legacy)).toContain('scormify-crossword-v4');
  expect(upgradeCrosswordHtml(upgradeCrosswordHtml(legacy))).toBe(upgradeCrosswordHtml(legacy));
  expect(upgradeCrosswordHtml(legacy.replace('"crossword"','"climb"'))).toBe(legacy.replace('"crossword"','"climb"'));
});

test('timeout ends once and reveals a read-only answer key without rewards or new completion',()=>{
  const save=jest.spyOn(game,'end');
  expect(document.getElementById('crossword-reveal')).toBeNull();
  jest.advanceTimersByTime(30000);
  expect(game.seconds).toBe(0);expect(save).toHaveBeenCalledTimes(1);
  const reveal=document.getElementById('crossword-reveal');expect(reveal).not.toBeNull();
  const state=[game.correct,game.xp,game.coins,game.index,game.lives];
  reveal.click();reveal.click();
  expect(document.querySelectorAll('#crossword-review')).toHaveLength(1);
  document.querySelectorAll('#crossword-review input').forEach(input=>{expect(input.value).toBe(input.dataset.solution);expect(input.readOnly).toBe(true);});
  expect(document.querySelectorAll('#crossword-review li')).toHaveLength(game.cross.placements.length);
  expect([game.correct,game.xp,game.coins,game.index,game.lives]).toEqual(state);
  jest.advanceTimersByTime(10000);expect(save).toHaveBeenCalledTimes(1);
  game.restart();expect(document.getElementById('crossword-review')).toBeNull();expect(game.locked).toBe(false);expect(game.seconds).toBe(30);
});

test('losing all lives permits review, while a perfect solution never does',()=>{
  game.validateCross();game.validateCross();game.validateCross();
  expect(document.getElementById('crossword-reveal')).not.toBeNull();
  game.restart();
  document.querySelectorAll('input.cell').forEach(input=>{input.value=input.dataset.solution;});
  game.validateCross();jest.advanceTimersByTime(700);
  expect(game.xp).toBe(500);expect(game.coins).toBe(60);
  expect(document.getElementById('crossword-reveal')).toBeNull();
});

test('restart cancels pending success completion and v2 documents are replaced by v4',()=>{
  document.querySelectorAll('input.cell').forEach(input=>{input.value=input.dataset.solution;});
  game.validateCross();game.restart();jest.advanceTimersByTime(700);
  expect(document.getElementById('finishScreen').classList.contains('hidden')).toBe(true);
  const old='<html><body><script>const QE={};const SETTINGS={"type":"crossword"};function renderCrossword(){}</script><script id="scormify-crossword-v2">oldRuntime()</script></body></html>';
  const upgraded=upgradeCrosswordHtml(old);
  expect(upgraded).not.toContain('oldRuntime()');expect(upgraded).toContain('scormify-crossword-v4');
});

test('whole terms and compound terms never lose letters and all crossings remain consistent',()=>{
  const bank=['Criatividade','Design Thinking','Interdisciplinaridade','Empatia'].map((text,i)=>({id:'term'+i,question:'Termo '+i,alternatives:[{id:'a',text}],correctAnswer:'a'}));
  const QE={correct:()=>0};
  const fresh={start(){},restart(){},end(){},resetTimer(){}};
  new Function('return ('+crosswordRuntime.toString()+');')()(fresh,bank,QE,document.getElementById('stage'));
  const cross=fresh.makeCross();
  expect(cross.placements.map(p=>p.word)).toEqual(['CRIATIVIDADE','DESIGNTHINKING','INTERDISCIPLINARIDADE','EMPATIA']);
  expect(cross.size).toBeGreaterThanOrEqual('INTERDISCIPLINARIDADE'.length);
  cross.placements.forEach(p=>expect(p.cells.map(pos=>cross.grid[pos]).join('')).toBe(p.word));
});

test('long answer sentences use a complete word and an explicit cloze, not a truncated sentence',()=>{
  const text='Permite entender profundamente as necessidades dos usuários.';
  const bank=[{question:'Qual a importância da empatia?',alternatives:[{id:'a',text}],correctAnswer:'a'}];
  const fresh={start(){},restart(){},end(){},resetTimer(){}};
  new Function('return ('+crosswordRuntime.toString()+');')()(fresh,bank,{correct:()=>0},document.getElementById('stage'));
  const p=fresh.makeCross().placements[0];
  expect(text.split(/\s+/)).toContain(p.target);
  expect(p.word).toBe('PROFUNDAMENTE');
  expect(p.clue).toBe('Qual a importância da empatia? Complete a resposta: Permite entender _____ as necessidades dos usuários.');
  expect(p.word).not.toBe('PERMITEENTE');
});

test('previous v3 saved games migrate to v4 without keeping an old installer',()=>{
  const old='<body><script>const QE={};const SETTINGS={"type":"crossword"};function renderCrossword(){}</script><script id="scormify-crossword-v3">outdated()</script></body>';
  const upgraded=upgradeCrosswordHtml(old);
  expect(upgraded).not.toContain('outdated()');expect(upgraded).toContain('scormify-crossword-v4');
  expect(upgradeCrosswordHtml(upgraded)).toBe(upgraded);
});
