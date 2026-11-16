import React,{act} from 'react';
import {createRoot} from 'react-dom/client';
import QuizPlayer from '../../../components/quiz/QuizPlayer';
jest.mock('../../../components/ui/button',()=>({Button:({children,variant,size,...props})=><button {...props}>{children}</button>}));
jest.mock('../../../components/ui/scroll-area',()=>({ScrollArea:({children})=><div>{children}</div>}));
test('native quiz keeps its original player, options and explanation without canonical assessment conversion',async()=>{
 global.IS_REACT_ACT_ENVIRONMENT=true;
 const host=document.createElement('div');document.body.append(host);const root=createRoot(host);
 const questions=[{id:'q',type:'multiple_choice',text:'Qual conduta adotar?',alternatives:[{id:'a',text:'Verificar requisitos',isCorrect:true},{id:'b',text:'Ignorar requisitos',isCorrect:false}],explanation:'Verificar requisitos é a conduta correta.',points:1}];
 await act(async()=>root.render(<QuizPlayer quizConfig={{id:'quiz',title:'Quiz tradicional',questionCount:1,showFeedback:true,showExplanation:true,shuffleQuestions:false,shuffleAlternatives:false,passingScore:70}} questions={questions} onComplete={()=>{}} embedded/>));
 expect(host.textContent).toContain('Qual conduta adotar?');
 await act(async()=>Array.from(host.querySelectorAll('button')).find(b=>b.textContent.includes('Verificar requisitos')).click());
 await act(async()=>Array.from(host.querySelectorAll('button')).find(b=>b.textContent.includes('Confirmar')).click());
 expect(host.textContent).toContain('Verificar requisitos é a conduta correta.');
 await act(async()=>root.unmount());host.remove();
});
