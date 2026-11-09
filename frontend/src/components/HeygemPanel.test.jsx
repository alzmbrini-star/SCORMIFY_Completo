import React,{act} from 'react';
import {createRoot} from 'react-dom/client';
import {HeygemPanel} from './HeygemPanel';
jest.mock('../utils/apiUrl',()=>({getApiUrl:()=> 'https://api.test'}));
jest.mock('../contexts/AuthContext',()=>({authHeaders:()=>({Authorization:'Bearer test'})}));
jest.mock('./ui/button',()=>({Button:({children,variant,...props})=><button {...props}>{children}</button>}));
jest.mock('./ui/input',()=>({Input:props=><input {...props}/>}));
jest.mock('./ui/textarea',()=>({Textarea:props=><textarea {...props}/>}));
global.IS_REACT_ACT_ENVIRONMENT=true;
let host,root;
beforeEach(()=>{host=document.createElement('div');document.body.appendChild(host);root=createRoot(host);});
afterEach(()=>{act(()=>root.unmount());host.remove();jest.restoreAllMocks();});
test('unconfigured provider cannot generate or consume credits',async()=>{
  global.fetch=jest.fn(async url=>({ok:true,json:async()=>url.endsWith('/config')?{configured:false,ttsReady:false,message:'Configure a ponte GPU'}:{videos:[]}}));
  await act(async()=>{root.render(<HeygemPanel onUseVideo={jest.fn()}/>);});
  expect(host.querySelector('[data-testid="heygem-generate"]').disabled).toBe(true);
  expect(host.textContent).toContain('Configure a ponte GPU');
  expect(fetch.mock.calls.every(call=>call[1].method==='GET')).toBe(true);
});
test('completed library asset is used only after explicit selection',async()=>{
  const use=jest.fn();
  global.fetch=jest.fn(async url=>({ok:true,json:async()=>url.endsWith('/config')?{configured:false,ttsReady:false,message:'Não configurado'}:{videos:[{video_id:'one',title:'Professor',status:'completed',video_url:'/api/heygem/assets/one.mp4'}]}}));
  await act(async()=>{root.render(<HeygemPanel onUseVideo={use}/>);});
  expect(use).not.toHaveBeenCalled();
  await act(async()=>{Array.from(host.querySelectorAll('button')).find(b=>b.textContent==='Usar este vídeo HeyGem').click();});
  expect(use.mock.calls[0][0]).toBe('https://api.test/api/heygem/assets/one.mp4');
  expect(host.querySelector('video').getAttribute('preload')).toBe('metadata');
});
