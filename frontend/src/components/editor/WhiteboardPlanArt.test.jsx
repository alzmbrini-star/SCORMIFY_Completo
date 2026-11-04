import React,{act,useState} from 'react';
import {createRoot} from 'react-dom/client';
import WhiteboardPlanArt,{WhiteboardIconPreview} from './WhiteboardPlanArt';
jest.mock('../../utils/apiUrl',()=>({getApiUrl:()=>''}));
jest.mock('../../contexts/AuthContext',()=>({authHeaders:()=>({})}));
jest.mock('../ui/button',()=>({Button:({variant,size,...props})=><button {...props}/>}));
jest.mock('../ui/input',()=>({Input:props=><input {...props}/>}));
globalThis.IS_REACT_ACT_ENVIRONMENT=true;
let host,root,plan;
beforeEach(()=>{host=document.createElement('div');document.body.appendChild(host);root=createRoot(host);global.fetch=jest.fn(async url=>({ok:true,json:async()=>url.endsWith('/icons')?{names:['house','heart'],aliases:{casa:'house'}}:{strokes:[[[0,0],[24,0],[24,24],[0,0]]]}}));});
afterEach(()=>{act(()=>root.unmount());host.remove();jest.restoreAllMocks();});
test('manual colors/fills preserve content and require no AI POST',async()=>{
 function Wrapper(){const [state,setState]=useState({ops:[{id:'box',type:'rectangle',x:200,y:200,w:300,h:200,color:'#000000'}],quality:{score:100}});plan=state;return <WhiteboardPlanArt plan={state} onChange={setState}/>;}
 await act(async()=>root.render(<Wrapper/>));
 await act(async()=>host.querySelector('input[type="checkbox"]').click());
 expect(plan.ops[0].fill).toBe('#bfdbfe');expect(plan.ops[0].w).toBe(300);expect(plan.quality).toBeUndefined();
 expect(global.fetch.mock.calls.every(([,init])=>!init.method||init.method==='GET')).toBe(true);
 await act(async()=>host.querySelector('input[type="checkbox"]').click());expect(plan.ops[0].fill).toBeNull();
});
test('real icon preview uses vector geometry, not a labeled rectangle',async()=>{
 await act(async()=>root.render(<svg><WhiteboardIconPreview op={{name:'house',x:500,y:500,size:240,fill:'#93c5fd',color:'#111111'}}/></svg>));
 expect(host.querySelectorAll('path')).toHaveLength(2);expect(host.querySelector('rect')).toBeNull();
 expect(host.querySelector('g').getAttribute('transform')).toContain('scale(10)');
});
