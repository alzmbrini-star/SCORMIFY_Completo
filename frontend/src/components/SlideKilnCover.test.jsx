import React,{act} from 'react';
import {createRoot} from 'react-dom/client';
import axios from 'axios';
import SlideKilnCover from './SlideKilnCover';
import CourseCoverPreview from './CourseCoverPreview';
jest.mock('axios',()=>({get:jest.fn(),post:jest.fn()}));
let div,root;
global.IS_REACT_ACT_ENVIRONMENT=true;
const props={projectId:'p',revision:'module',visible:true,size:{width:240,height:135},title:'Ancora'};
beforeEach(()=>{jest.clearAllMocks();div=document.createElement('div');document.body.appendChild(div);root=createRoot(div);});
afterEach(()=>{act(()=>root.unmount());div.remove();});
test('old and future modules use authenticated passive first-slide snapshot',async()=>{
 axios.get.mockResolvedValue({data:{width:1280,height:720,html:'<h1>Capa real</h1><script>bad()</script><iframe src="x"></iframe>'}});
 await act(async()=>root.render(<SlideKilnCover {...props}/>));
 expect(axios.get.mock.calls[0][0]).toMatch(/\/api\/projects\/p\/slidekiln-cover$/);
 const frame=div.querySelector('iframe');expect(frame.getAttribute('sandbox')).toBe('');
 expect(frame.srcdoc).toContain('Capa real');expect(frame.srcdoc).not.toMatch(/<script|<iframe/);
 expect(frame.srcdoc).toContain('img-src data:;');expect(frame.srcdoc).not.toContain('img-src https:');
 expect(frame.style.transform).toBe('scale(0.1875)');
 expect(axios.post).not.toHaveBeenCalled();
});
test('offscreen cards do not load; missing package gives visible fallback',async()=>{
 axios.get.mockRejectedValue(new Error('Unavailable'));
 await act(async()=>root.render(<SlideKilnCover {...props} visible={false}/>));
 expect(axios.get).not.toHaveBeenCalled();
 await act(async()=>root.render(<SlideKilnCover {...props}/>));
 expect(div.querySelector('[role=status]').textContent).toBe('Ancora — Capa indisponível');
 expect(axios.post).not.toHaveBeenCalled();
});
test('late response from another project cannot replace the current cover',async()=>{
 let finish;
 axios.get.mockImplementationOnce(()=>new Promise(resolve=>{finish=resolve;}));
 axios.get.mockResolvedValue({data:{width:1280,height:720,html:'<h1>Segundo curso</h1>'}});
 await act(async()=>root.render(<SlideKilnCover {...props}/>));
 await act(async()=>root.render(<SlideKilnCover {...props} projectId="next"/>));
 await act(async()=>finish({data:{width:1280,height:720,html:'<h1>Curso antigo</h1>'}}));
 expect(div.querySelector('iframe').srcdoc).toContain('Segundo curso');
 expect(div.querySelector('iframe').srcdoc).not.toContain('Curso antigo');
});
test('dashboard routes legacy SlideKiln HTML through cover snapshot without changing course',async()=>{
 const project={id:'legacy',name:'Ancora',course:{slides:[{elements:[{type:'html',source:'slidekiln',htmlContent:'<iframe src="original.sk.html"></iframe>'}]}]}};
 const before=JSON.stringify(project);
 axios.get.mockResolvedValue({data:{width:1280,height:720,html:'<h1>Capa recuperada</h1>'}});
 await act(async()=>root.render(<CourseCoverPreview project={project}/>));
 expect(axios.get.mock.calls[0][0]).toMatch(/\/legacy\/slidekiln-cover$/);
 expect(div.querySelector('iframe').srcdoc).toContain('Capa recuperada');
 expect(JSON.stringify(project)).toBe(before);expect(axios.post).not.toHaveBeenCalled();
});
