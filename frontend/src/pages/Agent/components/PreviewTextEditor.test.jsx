import React,{act} from 'react';
import {createRoot} from 'react-dom/client';
import PreviewTextEditor from './PreviewTextEditor';
jest.mock('../../../components/ui/button',()=>({Button:({variant,...props})=><button {...props}/>}));

const slide={afterIndex:4,type:'quiz',editor:{revision:'same-revision',title:'Processo',scenario:{},questions:[
 {id:'q',prompt:'O que é PDI?',explanation:'Programa',options:[{id:'a',text:'Programa'},{id:'b',text:'Outro'}]}]}};
let host,root;
beforeEach(()=>{global.IS_REACT_ACT_ENVIRONMENT=true;host=document.createElement('div');document.body.appendChild(host);root=createRoot(host);});
afterEach(()=>{act(()=>root.unmount());host.remove();});
test('select question and save only editable text with unchanged IDs and revision',async()=>{
 const save=jest.fn().mockResolvedValue(undefined);
 await act(async()=>root.render(<PreviewTextEditor slide={slide} onSave={save} onCancel={()=>{}}/>));
 expect(host.textContent).toContain('Não usa IA');
 const select=host.querySelector('select');
 act(()=>{select.value='q';select.dispatchEvent(new Event('change',{bubbles:true}));});
 expect(host.querySelector('[aria-label="Enunciado"]').value).toBe('O que é PDI?');
 await act(async()=>host.querySelector('form').dispatchEvent(new Event('submit',{bubbles:true,cancelable:true})));
 expect(save).toHaveBeenCalledWith({afterIndex:4,type:'quiz',revision:'same-revision',questionId:'q',changes:{prompt:'O que é PDI?',explanation:'Programa',options:[{id:'a',text:'Programa'},{id:'b',text:'Outro'}]}});
 expect(host.textContent).not.toContain('isCorrect');
});
test('saving error remains visible and cancel does not save',async()=>{
 const cancel=jest.fn(),save=jest.fn().mockRejectedValue(new Error('A prévia mudou'));
 await act(async()=>root.render(<PreviewTextEditor slide={slide} onSave={save} onCancel={cancel}/>));
 await act(async()=>host.querySelector('form').dispatchEvent(new Event('submit',{bubbles:true,cancelable:true})));
 expect(host.querySelector('[role="alert"]').textContent).toContain('A prévia mudou');
 act(()=>Array.from(host.querySelectorAll('button')).find(b=>b.textContent==='Cancelar edição').click());
 expect(cancel).toHaveBeenCalledTimes(1);expect(save).toHaveBeenCalledTimes(1);
});
