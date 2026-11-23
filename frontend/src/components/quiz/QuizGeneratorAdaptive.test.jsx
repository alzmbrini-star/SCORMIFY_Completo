import React,{act} from 'react';
import {createRoot} from 'react-dom/client';
import axios from 'axios';
import QuizGenerator from './QuizGenerator';
jest.mock('axios',()=>({get:jest.fn(),post:jest.fn()}));
jest.mock('sonner',()=>({toast:{success:jest.fn(),error:jest.fn()}}));
jest.mock('../../contexts/AuthContext',()=>({authHeaders:()=>({})}));
jest.mock('../ui/button',()=>({Button:({children,variant,size,...p})=><button {...p}>{children}</button>}));
jest.mock('../ui/input',()=>({Input:p=><input {...p}/>}));
jest.mock('../ui/textarea',()=>({Textarea:p=><textarea {...p}/>}));
jest.mock('../ui/label',()=>({Label:({children})=><label>{children}</label>}));
jest.mock('../ui/separator',()=>({Separator:()=> <hr/>}));
jest.mock('../ui/checkbox',()=>({Checkbox:({checked,onCheckedChange,...p})=><input type="checkbox" checked={checked} onChange={e=>onCheckedChange(e.target.checked)} {...p}/>}));
jest.mock('../ui/dialog',()=>{
 const Wrap=({children})=><div>{children}</div>;
 return {Dialog:({open,children})=>open?<div>{children}</div>:null,DialogContent:Wrap,DialogDescription:Wrap,DialogHeader:Wrap,DialogTitle:Wrap,DialogFooter:Wrap};
});
jest.mock('../ui/tabs',()=>{
 const React=require('react'),C=React.createContext();
 return {Tabs:({value,onValueChange,children})=><C.Provider value={{value,onValueChange}}>{children}</C.Provider>,TabsList:({children})=><div>{children}</div>,TabsTrigger:({value,children})=>{const c=React.useContext(C);return <button onClick={()=>c.onValueChange(value)}>{children}</button>},TabsContent:({value,children})=>React.useContext(C).value===value?<div>{children}</div>:null};
});
jest.mock('../ui/select',()=>{
 const Wrap=({children})=><div>{children}</div>;
 return {Select:Wrap,SelectTrigger:Wrap,SelectValue:()=>null,SelectContent:Wrap,SelectItem:Wrap};
});
global.IS_REACT_ACT_ENVIRONMENT=true;
test('AI tab shares opt-in mode with Configure and quiz insertion without paid generation',async()=>{
 const bank=[{id:'q1',text:'Conceito',type:'multiple_choice',alternatives:[]}];
 axios.get.mockResolvedValue({data:bank});
 const created=jest.fn(),host=document.createElement('div');document.body.append(host);const root=createRoot(host);
 await act(async()=>root.render(<QuizGenerator open projectId="test" onOpenChange={()=>{}} onQuizCreated={created}/>));
 const adaptive=()=>host.querySelector('[aria-label="Avaliação adaptativa"]');
 const click=async text=>act(async()=>[...host.querySelectorAll('button')].find(b=>b.textContent.includes(text)).click());
 expect(adaptive().checked).toBe(false);
 await act(async()=>adaptive().click());
 await click('Configurar');expect(adaptive().checked).toBe(true);
 await act(async()=>adaptive().click());
 await click('Gerar com IA');expect(adaptive().checked).toBe(false);
 await act(async()=>adaptive().click());
 await click('Banco (');await act(async()=>host.querySelector('[data-testid="quiz-select-all"]').click());
 await click('Adicionar Quiz ao Slide');
 expect(created.mock.calls[0][0].quizConfig).toMatchObject({adaptiveMode:true,questionIds:['q1']});
 expect(axios.post).not.toHaveBeenCalled();expect(bank[0].id).toBe('q1');
 await act(async()=>root.unmount());host.remove();
});
