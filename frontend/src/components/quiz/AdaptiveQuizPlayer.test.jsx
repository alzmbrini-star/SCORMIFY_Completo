import React,{act} from 'react';
import {createRoot} from 'react-dom/client';
import QuizPlayer from './QuizPlayer';
jest.mock('../ui/button',()=>({Button:({children,variant,size,...props})=><button {...props}>{children}</button>}));
jest.mock('../ui/scroll-area',()=>({ScrollArea:({children})=><div>{children}</div>}));
test('traditional adaptive preview starts intermediate and supplies reinforcement after error',async()=>{
 global.IS_REACT_ACT_ENVIRONMENT=true;
 const host=document.createElement('div');document.body.appendChild(host);const root=createRoot(host);
 const questions=[1,2,3].map(n=>({id:'q'+n,text:'Nível '+n,difficulty:n,reinforcement:'Reforce o conceito',
 alternatives:[{id:'a',text:'Sim',isCorrect:true},{id:'b',text:'Não',isCorrect:false}]}));
 await act(async()=>root.render(<QuizPlayer questions={questions} quizConfig={{adaptiveMode:true,questionCount:3,shuffleQuestions:false,shuffleAlternatives:false,showFeedback:false}}/>));
 expect(host.textContent).toContain('Nível 2');
 const click=async text=>act(async()=>[...host.querySelectorAll('button')].find(b=>b.textContent.includes(text)).click());
 await click('Não');await click('Confirmar');expect(host.textContent).toContain('Reforce o conceito');
 await click('Próxima');expect(host.textContent).toContain('Nível 1');
 expect(host.querySelector('[data-testid="quiz-prev-btn"]').disabled).toBe(true);
 expect(questions.map(q=>q.difficulty)).toEqual([1,2,3]);
 await act(async()=>root.unmount());host.remove();
});
