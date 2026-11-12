import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import HtmlSourceEditor from './HtmlSourceEditor';
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
jest.mock('../ui/button', () => ({Button: ({children, variant, ...props}) => <button {...props}>{children}</button>}));
jest.mock('../ui/dialog', () => ({Dialog: ({children, open}) => open ? <div>{children}</div> : null, DialogContent: ({children}) => <div>{children}</div>, DialogHeader: ({children}) => <div>{children}</div>, DialogTitle: ({children}) => <h1>{children}</h1>, DialogDescription: ({children}) => <p>{children}</p>, DialogFooter: ({children}) => <div>{children}</div>}));
test('opens exact source; cancel writes nothing; save patches HTML only', async () => {
  const container=document.createElement('div'); document.body.append(container);
  const root=createRoot(container), update=jest.fn().mockResolvedValue({});
  const element={id:'one',htmlContent:'<!doctype html><html><script>const items=[];</script></html>',x:0,width:1920};
  const click=text=>[...container.querySelectorAll('button')].find(b=>b.textContent===text).click();
  try {
    await act(async()=>root.render(<HtmlSourceEditor element={element} onUpdate={update}/>));
    await act(async()=>click('Editar código HTML'));
    expect(container.querySelector('textarea').value).toBe(element.htmlContent);
    await act(async()=>click('Cancelar')); expect(update).not.toHaveBeenCalled();
    await act(async()=>click('Editar código HTML'));
    await act(async()=>click('Salvar código HTML'));
    expect(update).toHaveBeenCalledWith({htmlContent:element.htmlContent});
    expect(container.querySelector('textarea')).toBeNull();
  } finally { await act(async()=>root.unmount()); container.remove(); }
});
test('keeps the draft open when saving fails', async () => {
  const container=document.createElement('div');document.body.append(container);const root=createRoot(container);
  try {
    await act(async()=>root.render(<HtmlSourceEditor element={{htmlContent:'<p>Aula</p>'}} onUpdate={async()=>{throw Error('offline');}}/>));
    await act(async()=>container.querySelector('button').click());
    await act(async()=>[...container.querySelectorAll('button')].find(b=>b.textContent==='Salvar código HTML').click());
    expect(container.querySelector('textarea').value).toBe('<p>Aula</p>');
    expect(container.querySelector('[role="alert"]').textContent).toContain('rascunho continua aberto');
  } finally {await act(async()=>root.unmount());container.remove();}
});
