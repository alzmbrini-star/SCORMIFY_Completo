import React,{act} from 'react';
import {createRoot} from 'react-dom/client';
import AstryxAppearanceDialog from './AstryxAppearanceDialog';
jest.mock('../contexts/AuthContext',()=>({authHeaders:()=>({Authorization:'Bearer local-test'})}));
jest.mock('../utils/apiUrl',()=>({getApiUrl:()=>''}));
jest.mock('../utils/htmlUtils',()=>({resolveAssetUrls:v=>v}));
jest.mock('./ui/dialog',()=>({Dialog:({children})=><div>{children}</div>,DialogContent:({children})=><div>{children}</div>,DialogHeader:({children})=><div>{children}</div>,DialogTitle:({children})=><h1>{children}</h1>,DialogDescription:({children})=><p>{children}</p>}));
jest.mock('./ui/button',()=>({Button:({variant,...props})=><button {...props}/>}));
const catalog={styles:[{id:'clean',name:'Essencial'},{id:'editorial',name:'Editorial'}],palettes:[{id:'blue',name:'Azul',accent:'#315ad1'}],appearance:{},eligible:1};
let host,root,onClose,onSaved,onChange;
beforeEach(()=>{global.IS_REACT_ACT_ENVIRONMENT=true;onClose=jest.fn();onSaved=jest.fn();onChange=jest.fn();
  global.fetch=jest.fn(async(url,opts)=>({ok:true,json:async()=>opts.method==='GET'?catalog:url.endsWith('/preview')?{fingerprint:'snapshot',totalSlides:19,slides:[{slide:1,title:'Capa real',html:'<img alt="Preservada">'}]}:{changed:true}}));
  host=document.createElement('div');document.body.appendChild(host);root=createRoot(host);
});
afterEach(()=>{act(()=>root.unmount());host.remove();jest.restoreAllMocks();});
const button=t=>Array.from(host.querySelectorAll('button')).find(n=>n.textContent===t);
async function render(){await act(async()=>root.render(<AstryxAppearanceDialog projectId="target" onClose={onClose} onSaved={onSaved} onChange={onChange}/>));}
async function preview(){await act(async()=>button('Preparar prévia — sem salvar').click());}

test('opening and preview never save; captions default false; preview uses only target project',async()=>{
 await render();expect(fetch).toHaveBeenCalledTimes(1);expect(host.querySelector('input[type=checkbox]').checked).toBe(false);
 expect(button('Aplicar visual somente neste curso').disabled).toBe(true);await preview();
 expect(fetch).toHaveBeenCalledTimes(2);expect(fetch.mock.calls[1][0]).toBe('/api/projects/target/astryx-appearance/preview');
 expect(JSON.parse(fetch.mock.calls[1][1].body).appearance.captions).toBe(false);
 expect(host.querySelector('iframe').getAttribute('sandbox')).toBe('allow-scripts');
 expect(onSaved).not.toHaveBeenCalled();expect(onChange).not.toHaveBeenCalled();
});
test('every visual edit invalidates preview and prevents applying stale appearance',async()=>{
 await render();await preview();expect(button('Aplicar visual somente neste curso').disabled).toBe(false);
 act(()=>button('Editorial').click());expect(host.querySelector('iframe')).toBeNull();expect(button('Aplicar visual somente neste curso').disabled).toBe(true);
 await preview();act(()=>host.querySelector('input[type=checkbox]').click());expect(button('Aplicar visual somente neste curso').disabled).toBe(true);
});
test('explicit application sends matching fingerprint then refreshes only open course',async()=>{
 await render();await preview();await act(async()=>button('Aplicar visual somente neste curso').click());
 const [url,opts]=fetch.mock.calls[2];expect(url).toBe('/api/projects/target/astryx-appearance/apply');
 expect(JSON.parse(opts.body).fingerprint).toBe('snapshot');expect(onSaved).toHaveBeenCalledTimes(1);expect(onClose).toHaveBeenCalledTimes(1);
});
test('cancel does not write or apply; course conflict leaves dialog open with error',async()=>{
 await render();act(()=>button('Cancelar sem aplicar').click());expect(fetch).toHaveBeenCalledTimes(1);expect(onSaved).not.toHaveBeenCalled();
 await preview();fetch.mockImplementationOnce(async()=>({ok:false,json:async()=>({detail:'O curso mudou.'})}));
 await act(async()=>button('Aplicar visual somente neste curso').click());expect(host.querySelector('[role=alert]').textContent).toBe('O curso mudou.');expect(onSaved).not.toHaveBeenCalled();
});
