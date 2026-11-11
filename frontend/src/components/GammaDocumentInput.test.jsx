import React,{act} from 'react';
import {createRoot} from 'react-dom/client';
import GammaDocumentInput from './GammaDocumentInput';
jest.mock('../contexts/AuthContext',()=>({authHeaders:()=>({Authorization:'test'})}));
jest.mock('../utils/apiUrl',()=>({getApiUrl:()=> 'https://backend.test'}));
jest.mock('./ui/button',()=>({Button:({children,variant,...props})=><button {...props}>{children}</button>}));
let root,container,onChange,onBusy,originalFetch;
beforeEach(async()=>{global.IS_REACT_ACT_ENVIRONMENT=true;originalFetch=global.fetch;container=document.createElement('div');document.body.append(container);root=createRoot(container);onChange=jest.fn();onBusy=jest.fn();await act(async()=>root.render(<GammaDocumentInput value="Texto já digitado" onChange={onChange} onBusy={onBusy}/>));});
afterEach(async()=>{await act(async()=>root.unmount());container.remove();global.fetch=originalFetch;});
async function upload(file){await act(async()=>{const input=container.querySelector('input');Object.defineProperty(input,'files',{configurable:true,value:[file]});input.dispatchEvent(new Event('change',{bubbles:true}));});}
test('upload previews without generating, appends only on confirmation, uses multipart auth',async()=>{
  global.fetch=jest.fn(async()=>({ok:true,json:async()=>({text:'Conteúdo extraído integralmente.',warning:'Imagens não são importadas.'})}));
  await upload(new File(['fake'],'ementa.docx'));
  expect(onChange).not.toHaveBeenCalled();
  expect(onBusy).toHaveBeenLastCalledWith(true);
  const [url,options]=global.fetch.mock.calls[0];expect(url).toContain('/extract-document');expect(options.body).toBeInstanceOf(FormData);expect(options.headers).not.toHaveProperty('Content-Type');
  await act(async()=>container.querySelector('button').click());
  expect(onChange).toHaveBeenCalledWith('Texto já digitado\n\nConteúdo extraído integralmente.');expect(onBusy).toHaveBeenLastCalledWith(false);
  expect(global.fetch).toHaveBeenCalledTimes(1);
});
test('legacy rejected before network and extraction error preserves existing text',async()=>{
  global.fetch=jest.fn();await upload(new File(['bad'],'old.ppt'));expect(global.fetch).not.toHaveBeenCalled();expect(container.textContent).toContain('formato atual');
  global.fetch.mockResolvedValue({ok:false,json:async()=>({detail:'PDF precisa de OCR'})});await upload(new File(['bad'],'scan.pdf'));expect(container.textContent).toContain('PDF precisa de OCR');expect(onChange).not.toHaveBeenCalled();expect(onBusy).toHaveBeenLastCalledWith(false);
});
test('oversized combined text blocked, not silently truncated',async()=>{
  global.fetch=jest.fn(async()=>({ok:true,json:async()=>({text:'a'.repeat(100000),warning:'Revise'})}));await upload(new File(['fake'],'long.pdf'));
  expect(container.querySelector('button').disabled).toBe(true);expect(container.textContent).toContain('nada será cortado');expect(onChange).not.toHaveBeenCalled();
});
