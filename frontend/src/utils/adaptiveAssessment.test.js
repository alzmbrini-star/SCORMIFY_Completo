import {createAdaptiveEngine} from './adaptiveAssessment';
import {assessmentRuntime} from '../components/assessment/assessmentRuntime';
const engine=createAdaptiveEngine();
const q=(id,difficulty,category='Tema')=>({id,difficulty,category,type:'single_choice',title:id,prompt:id,points:1,
 reinforcement:'Reforce '+id,options:[{id:'a',text:'Sim',isCorrect:true},{id:'b',text:'Não'}]});
afterEach(()=>{document.body.replaceChildren();delete window.ScormifyAdaptive;jest.restoreAllMocks();});
test('adaptive path rises falls and preserves every selected item without bank mutation',()=>{
 const bank=[q('easy',1),q('hard',3),q('medium',2),q('easy-other',1,'Outro')];
 const before=JSON.stringify(bank);let order=engine.start(bank);
 expect(order[0].id).toBe('medium');order=engine.next(order,0,true);expect(order[1].id).toBe('hard');
 order=engine.next(order,1,false);expect(order[2].id).toBe('easy');
 expect(new Set(order.map(x=>x.id)).size).toBe(4);expect(JSON.stringify(bank)).toBe(before);
});
test('missing levels default to intermediate and exhausted levels finish with remaining items',()=>{
 const bank=[{id:'a'},{id:'b'}];expect(engine.level(bank[0])).toBe(2);
 expect(engine.next(bank,0,false).map(q=>q.id)).toEqual(['a','b']);
 expect(engine.next(bank,1,true)).toEqual(bank);
 expect(engine.reinforce({explanation:'Explicação salva'})).toBe('Explicação salva');
});
test('image assessment enforces confirmation reinforcement progression grading and restart',()=>{
 window.ScormifyAdaptive=engine;
 document.body.innerHTML='<script id="assessment-data" type="application/json"></script><main id="app"></main>';
 const questions=[q('easy',1),q('medium',2),q('hard',3)];
 document.getElementById('assessment-data').textContent=JSON.stringify({title:'Adaptativa',adaptiveMode:true,allowSkip:true,questions});
 const post=jest.spyOn(window.parent,'postMessage').mockImplementation(()=>{});
 const click=text=>[...document.querySelectorAll('button')].find(b=>b.textContent===text).click();
 assessmentRuntime();
 expect(document.querySelector('h1').textContent).toBe('medium');
 expect([...document.querySelectorAll('button')].find(b=>b.textContent==='Finalizar').disabled).toBe(true);
 expect([...document.querySelectorAll('button')].some(b=>b.textContent==='Pular')).toBe(false);
 click('B. Não');click('✓ Confirmar resposta');
 expect(document.querySelector('[role="status"]').textContent).toContain('Reforce medium');
 expect(document.querySelector('h1').textContent).toBe('medium');click('Próxima questão →');
 expect(document.querySelector('h1').textContent).toBe('easy');
 click('A. Sim');click('✓ Confirmar resposta');click('Próxima questão →');
 expect(document.querySelector('h1').textContent).toBe('hard');
 click('A. Sim');click('✓ Confirmar resposta');click('Próxima questão →');
 expect(document.querySelector('.score').textContent).toBe('67%');
 expect(post.mock.calls.filter(([m])=>m.type==='scormify-assessment-gamification')).toHaveLength(1);
 click('Tentar novamente');expect(document.querySelector('h1').textContent).toBe('medium');
 expect(questions.map(q=>q.id)).toEqual(['easy','medium','hard']);
});
