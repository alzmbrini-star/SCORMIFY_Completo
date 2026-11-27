import React, {act} from 'react';
import {createRoot} from 'react-dom/client';
import axios from 'axios';
import SlideKilnImport from './SlideKilnImport';
jest.mock('axios',()=>({get:jest.fn(),post:jest.fn()}));
jest.mock('./ui/button',()=>({Button:props=><button {...props}/>}));
let div,root;
global.IS_REACT_ACT_ENVIRONMENT=true;
beforeEach(()=>{div=document.createElement('div');document.body.appendChild(div);root=createRoot(div);jest.clearAllMocks();});
afterEach(()=>{act(()=>root.unmount());div.remove();});
test('unconfigured provider never uploads or converts',async()=>{
 axios.get.mockResolvedValue({data:{configured:false}});
 await act(async()=>root.render(<SlideKilnImport onComplete={jest.fn()}/>));
 expect(div.textContent).toContain('SLIDEKILN_API_KEY');expect(div.querySelector('input[type=file]')).toBeNull();expect(axios.post).not.toHaveBeenCalled();
});
test('file selection only prepares quote; conversion requires both checks',async()=>{
 axios.get.mockResolvedValue({data:{configured:true,canApprove:true}});
 axios.post.mockResolvedValue({data:{id:'q',status:'awaiting_approval',filename:'a.pptx',slides:8,budget:{maxBrl:5.75,maxUsd:1,exchange:{rate:5.7446,asOfDate:'2026-11-26'},notice:'Limite aprovado por arquivo'}}});
 await act(async()=>root.render(<SlideKilnImport onComplete={jest.fn()}/>));
 const input=div.querySelector('input[type=file]');Object.defineProperty(input,'files',{value:[new File(['test'],'a.pptx')],configurable:true});
 await act(async()=>input.dispatchEvent(new Event('change',{bubbles:true})));
 expect(axios.post).toHaveBeenCalledTimes(1);expect(axios.post.mock.calls[0][0]).toMatch(/\/quote$/);
 const button=div.querySelector('button');expect(button.disabled).toBe(true);
 const checks=div.querySelectorAll('input[type=checkbox]');await act(async()=>checks[0].click());expect(button.disabled).toBe(true);
 await act(async()=>checks[1].click());expect(button.disabled).toBe(false);
 expect(axios.post).toHaveBeenCalledTimes(1);
});
