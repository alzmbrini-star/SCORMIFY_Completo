import React,{act} from 'react';
import {createRoot} from 'react-dom/client';
import axios from 'axios';
import LayoutRecoveryNotice,{activityLayoutIncomplete} from './LayoutRecoveryNotice';
jest.mock('axios',()=>({post:jest.fn()}));
jest.mock('react-router-dom',()=>({useNavigate:()=>jest.fn()}));
jest.mock('sonner',()=>({toast:{success:jest.fn()}}));
jest.mock('../../contexts/AuthContext',()=>({authHeaders:()=>({Authorization:'Bearer test'})}));
jest.mock('../../utils/apiUrl',()=>({getApiUrl:()=> 'https://api.example'}));
jest.mock('../ui/button',()=>({Button:({children,variant,...props})=><button {...props}>{children}</button>}));
globalThis.IS_REACT_ACT_ENVIRONMENT=true;
const project={id:'p',updatedAt:'r1',course:{slides:[{elements:[{type:'html',htmlContent:'<script id="video-quiz-data">{}</script>'}]}]}};
test('only exposes recovery for incomplete isolated controlled activities',()=>{
 expect(activityLayoutIncomplete(project)).toBe(true);
 expect(activityLayoutIncomplete({course:{slides:[{elements:[{type:'html',htmlContent:'<p>Custom</p>'}]}]}})).toBe(false);
});
test('requires explicit click and sends revision before refreshing',async()=>{
 const container=document.createElement('div'),root=createRoot(container),refresh=jest.fn();
 axios.post.mockResolvedValue({data:{recoveredSlides:[1],recoveryId:'backup'}});
 await act(async()=>root.render(<LayoutRecoveryNotice project={project} onRecovered={refresh}/>));
 expect(axios.post).not.toHaveBeenCalled();
 await act(async()=>container.querySelector('button').click());
 expect(axios.post).toHaveBeenCalledWith('https://api.example/api/projects/p/recover-activity-layout',{expectedUpdatedAt:'r1'},expect.any(Object));
 expect(refresh).toHaveBeenCalledWith('p');
 await act(async()=>root.unmount());
});
