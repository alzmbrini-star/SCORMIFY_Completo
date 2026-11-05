import React,{act} from 'react';
import {createRoot} from 'react-dom/client';
import DensitySuggestionsDialog from './DensitySuggestionsDialog';
globalThis.IS_REACT_ACT_ENVIRONMENT=true;
jest.mock('../utils/apiUrl',()=>({getApiUrl:()=>''}));
jest.mock('./ui/button',()=>({Button:({children,variant,size,...props})=><button {...props}>{children}</button>}));
jest.mock('./ui/dialog',()=>({Dialog:({children,open})=>open?<div>{children}</div>:null,DialogContent:({children,...props})=><div {...props}>{children}</div>,DialogHeader:({children})=><div>{children}</div>,DialogTitle:({children})=><h1>{children}</h1>,DialogDescription:({children})=><p>{children}</p>}));
let container,root;
beforeEach(()=>{container=document.createElement('div');document.body.appendChild(container);root=createRoot(container);global.fetch=jest.fn(url=>Promise.resolve({ok:true,json:async()=>url.includes('/suggestions')?{density:{score:50,label:'medium',reasons:[]},suggestions:[{id:'one',type:'bullets',title:'Resumo',transformedText:'Novo texto'}]}:{}}));});
afterEach(async()=>{await act(async()=>root.unmount());container.remove();});
test('failed save stays open, exposes error and never reports success by closing',async()=>{
 const close=jest.fn(),apply=jest.fn().mockRejectedValue(new Error('Falha ao salvar HTTP 500'));
 await act(async()=>root.render(<DensitySuggestionsDialog open title="Tema" text="Texto" onClose={close} onApply={apply}/>));
 await act(async()=>container.querySelector('[data-testid="density-apply-0"]').click());
 expect(container.textContent).toContain('Falha ao salvar HTTP 500');expect(close).not.toHaveBeenCalled();
});
test('protected activity never requests paid suggestions or applies a rewrite',async()=>{
 const apply=jest.fn();await act(async()=>root.render(<DensitySuggestionsDialog open protectedActivity onApply={apply}/>));
 expect(fetch).not.toHaveBeenCalled();expect(container.textContent).toContain('Atividade interativa protegida');
 expect(container.textContent).not.toContain('configuracao da OpenAI');
 expect(container.textContent).not.toContain('Conteudo equilibrado');
 expect(container.querySelector('[data-testid="density-apply-0"]')).toBeNull();
});
