import React,{act} from 'react';
import {createRoot} from 'react-dom/client';
import axios from 'axios';
import NativeQuizPreview,{previewQuestion} from './NativeQuizPreview';
jest.mock('axios',()=>({get:jest.fn()}));
jest.mock('../../contexts/AuthContext',()=>({authHeaders:()=>({})}));
jest.mock('../ui/button',()=>({Button:({children,variant,size,...props})=><button {...props}>{children}</button>}));
jest.mock('../ui/scroll-area',()=>({ScrollArea:({children})=><div>{children}</div>}));
global.IS_REACT_ACT_ENVIRONMENT=true;

test('legacy aliases are read without modifying the saved questions',()=>{
 const q={id:'old',questionText:'Enunciado antigo',alternatives:[{text:'Sim',is_correct:true}]};
 const before=JSON.stringify(q),normalized=previewQuestion(q);
 expect(normalized.text).toBe('Enunciado antigo');expect(normalized.alternatives[0].isCorrect).toBe(true);
 expect(normalized.alternatives[0].id).toBeTruthy();expect(JSON.stringify(q)).toBe(before);
});

test('uses original player, current question text, feedback and percentage threshold, counting each answer once',async()=>{
 const rows=[1,2].map(i=>({id:'q'+i,text:'Enunciado '+i,type:'multiple_choice',explanation:'Explicação '+i,alternatives:[{id:'ok'+i,text:'Correta '+i,isCorrect:true},{id:'no'+i,text:'Incorreta '+i,isCorrect:false}]}));
 const original=JSON.stringify(rows);axios.get.mockResolvedValue({data:rows});
 const host=document.createElement('div');document.body.append(host);const root=createRoot(host);
 await act(async()=>root.render(<NativeQuizPreview projectId="course" quizConfig={{title:'Quiz tradicional',questionIds:['q1','q2'],questionCount:2,showFeedback:true,passingScore:70,fontSize:28}}/>));
 const click=async id=>act(async()=>host.querySelector(`[data-testid="${id}"]`).click());
 expect(host.textContent).toContain('Enunciado 1');
 expect(host.querySelector('[data-testid="quiz-alt-0"] span.flex-1').style.fontSize).toBe('28px');
 await click('quiz-alt-1');await click('quiz-confirm-btn');expect(host.textContent).toContain('Explicação 1');await click('quiz-next-btn');
 expect(host.textContent).toContain('Enunciado 2');await click('quiz-alt-0');await click('quiz-confirm-btn');await click('quiz-next-btn');
 expect(host.textContent).toContain('50%');expect(host.textContent).toContain('Não foi dessa vez');
 expect(host.textContent).toContain('Nota mínima: 70%');expect(JSON.stringify(rows)).toBe(original);
 expect(axios.get).toHaveBeenCalledTimes(1);
 await act(async()=>root.unmount());host.remove();
});
