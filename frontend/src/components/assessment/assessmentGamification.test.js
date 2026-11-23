import fs from 'fs';
import path from 'path';
import { assessmentRuntime } from './assessmentRuntime';

const engine = fs.readFileSync(path.resolve(process.cwd(), '../backend/services/export_assets/gamification.js'), 'utf8');
const q = (id, points) => ({id, points, type:'single_choice', title:id, prompt:'Escolha',
  media:{kind:'image',url:'https://example.com/support.png',name:'Apoio'},
  options:[{id:'a',text:'Certa',isCorrect:true},{id:'b',text:'Errada'}]});
const click = text => [...document.querySelectorAll('button')].find(b => b.textContent.includes(text)).click();
afterEach(() => { jest.restoreAllMocks(); document.body.replaceChildren(); document.head.replaceChildren(); });

test.each([false,true])('weighted score, review deduplication and retry; guided=%s', guidedPath => {
  document.body.innerHTML='<script id="assessment-data" type="application/json"></script><main id="app"></main>';
  const config={title:'Avaliação',questions:[q('q1',3),q('q2',1)],guidedPath};
  document.getElementById('assessment-data').textContent=JSON.stringify(config);
  const post=jest.spyOn(window.parent,'postMessage').mockImplementation(() => {});
  assessmentRuntime();
  click('A. Certa'); click('Confirmar'); click('B. Errada'); click('Confirmar');
  const messages=() => post.mock.calls.map(args => args[0]).filter(m=>m.type==='scormify-assessment-gamification');
  expect(messages()).toHaveLength(1);
  expect(messages()[0]).toMatchObject({score:75,totalQuestions:2,correctAnswers:1});
  click('Revisar respostas'); click('Finalizar');
  expect(messages()).toHaveLength(1);
  click('Tentar novamente'); click('A. Certa'); click('Confirmar'); click('A. Certa'); click('Confirmar');
  expect(messages()).toHaveLength(2);
  expect(messages()[1].score).toBe(100);
  expect(messages()[1].attemptId).not.toBe(messages()[0].attemptId);
  expect(config.questions[0].media.name).toBe('Apoio');
});

function setup(extra={}) {
  const listeners=[];
  const host={addEventListener:jest.fn((type,handler)=>listeners.push(handler))};
  const gamification=new Function('window','document',engine+';return Gamification;')(host,document);
  gamification.init({enabled:true,showBadgesAfterQuiz:true,showFinalSummary:true,
    badges:[{id:'master',name:'Mestre',description:'80%',criteria:{type:'quiz_score',operator:'gte',threshold:80}}],
    quizFeedbackRanges:[{minScore:80,maxScore:100,title:'Excelente!',message:'Parabéns'}],...extra});
  const frame=document.createElement('iframe');frame.dataset.assessment='true';document.body.appendChild(frame);
  const send=(overrides={},source=frame.contentWindow)=>listeners[0]({source,data:{type:'scormify-assessment-gamification',attemptId:'a1',score:100,totalQuestions:3,correctAnswers:3,...overrides}});
  return {gamification,send,frame,host};
}
test('registered frames earn configured badges once and reuse traditional quiz settings',()=>{
  const {gamification,send,host}=setup();
  send();send();
  expect(gamification.getStats().quizScores).toEqual([100]);
  expect(gamification.getEarnedBadges().map(b=>b.id)).toEqual(['master']);
  expect(document.querySelector('.gamification-title').textContent).toBe('Excelente!');
  document.querySelector('.gamification-modal').remove();
  send({attemptId:'a2',score:50,correctAnswers:1});
  expect(gamification.getStats().quizScores).toEqual([100,50]);
  expect(document.querySelectorAll('.gamification-badge')).toHaveLength(0);
  gamification.init({enabled:true}); expect(host.addEventListener).toHaveBeenCalledTimes(1);
});
test('ignores foreign, unmarked, invalid and disabled messages',()=>{
  const {gamification,send,frame}=setup();
  send({},window);send({score:NaN});send({score:101});send({correctAnswers:4});send({totalQuestions:0});send({attemptId:''});
  delete frame.dataset.assessment;send();
  expect(gamification.getStats().quizScores).toEqual([]);
  frame.dataset.assessment='true';gamification.init({enabled:false});send();
  expect(gamification.getStats().quizScores).toEqual([]);
  expect(document.querySelector('.gamification-modal')).toBeNull();
});
test('hidden feedback still counts results without showing a modal',()=>{
  const {gamification,send}=setup({showBadgesAfterQuiz:false});send();
  expect(gamification.getStats().quizScores).toEqual([100]);
  expect(gamification.getEarnedBadges()).toHaveLength(1);
  expect(document.querySelector('.gamification-modal')).toBeNull();
});
