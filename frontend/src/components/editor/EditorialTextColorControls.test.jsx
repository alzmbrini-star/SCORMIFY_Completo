import React,{act} from 'react';
import {createRoot} from 'react-dom/client';
import EditorialTextColorControls from './EditorialTextColorControls';
import {readEditorialTextColors} from '../../utils/editorialTextColors';
globalThis.IS_REACT_ACT_ENVIRONMENT=true;
jest.mock('../ui/button',()=>({Button:({children,variant,size,...props})=><button {...props}>{children}</button>}));
let root,container,canvas,frame,send;
beforeEach(()=>{
 canvas=document.createElement('div');canvas.dataset.testid='slide-canvas';canvas.innerHTML='<div data-testid="element-test"><iframe></iframe></div>';document.body.appendChild(canvas);frame=canvas.querySelector('iframe');send=jest.spyOn(frame.contentWindow,'postMessage');
 container=document.createElement('div');document.body.appendChild(container);root=createRoot(container);
});
afterEach(async()=>{await act(async()=>root.unmount());container.remove();canvas.remove();jest.restoreAllMocks();});
const element={id:'test',type:'html',htmlContent:'<html><head></head><body><div class="item">Cartão</div><script>restart()</script></body></html>'};
async function report(groups){const requestId=send.mock.calls[0][0].requestId;await act(async()=>window.dispatchEvent(new MessageEvent('message',{source:frame.contentWindow,data:{type:'scormify-editorial-color-snapshot',requestId,groups}})));}
function groups(colors=['#263b55']){return Object.fromEntries(['title','text','card','cardBackground'].map(k=>[k,{count:2,colors,complex:false}]));}
test('does not pretend a default white swatch is the current card background',async()=>{
 await act(async()=>root.render(<EditorialTextColorControls element={element} onUpdate={jest.fn()}/>));
 expect(container.querySelector('input[aria-label="Fundo dos cartões e itens"]')).toBeNull();
 await report(groups());
 expect(container.querySelector('input[aria-label="Fundo dos cartões e itens"]').value).toBe('#263b55');
 expect(container.textContent).toContain('Exibida: #263b55');
});
test('mixed real colors are explicitly indicated, not misrepresented as uniform',async()=>{
 await act(async()=>root.render(<EditorialTextColorControls element={element} onUpdate={jest.fn()}/>));
 await report(groups(['#263b55','#ffffff']));
 expect(container.textContent).toContain('Cores variadas');
});
test('contrast preset stores CSS that reaches item cards while keeping scripts intact',async()=>{
 const update=jest.fn();await act(async()=>root.render(<EditorialTextColorControls element={element} onUpdate={update}/>));
 const button=[...container.querySelectorAll('button')].find(b=>b.textContent==='Contraste para fundo claro');
 await act(async()=>button.click());
 const html=update.mock.calls[0][0].htmlContent;
 expect(readEditorialTextColors(html).cardBackground).toBe('#ffffff');
 expect(html).toContain('li,.item,.card');expect(html).toContain('<script>restart()</script>');
});
