import React,{act} from 'react';
import {createRoot} from 'react-dom/client';
import CourseCoverPreview from './CourseCoverPreview';

let host,root;
beforeEach(()=>{global.IS_REACT_ACT_ENVIRONMENT=true;host=document.createElement('div');document.body.appendChild(host);root=createRoot(host);});
afterEach(()=>{act(()=>root.unmount());host.remove();jest.restoreAllMocks();});
const project=slide=>({id:'p',name:'Curso de teste',course:{slides:[slide]}});

test('Gamma image elements form the real cover with uniform scaling and no title-only substitution',()=>{
 const p=project({width:1920,height:1080,background:'#fff',gammaSource:{elementId:'gamma'},elements:[
  {id:'gamma',type:'image',src:'/api/projects/p/assets/gamma.webp',x:0,y:0,width:1920,height:1080},
  {id:'hidden',type:'image',visible:false,src:'hidden.png'}]});const before=JSON.stringify(p);
 act(()=>root.render(<CourseCoverPreview project={p}/>));
 expect(host.querySelectorAll('img')).toHaveLength(1);
 expect(host.querySelector('img').getAttribute('src')).toContain('/api/projects/p/assets/gamma.webp');
 expect(host.querySelector('[data-testid="course-cover-stage"]').style.transform).toBe('scale(0.125)');
 expect(host.querySelector('img').style.objectFit).toBe('contain');
 expect(JSON.stringify(p)).toBe(before);
});

test('Agent cover includes its full static HTML/CSS and images, isolated without scripting permissions',()=>{
 const p=project({width:1920,height:820,background:'#111',elements:[{type:'html',width:1920,height:820,
  htmlContent:'<style>h1{color:gold;font-size:80px}</style><h1>Introdução</h1><img src="/api/assets/team.webp"><script>recordGrade()</script>'}]});
 act(()=>root.render(<CourseCoverPreview project={p}/>));
 const iframe=host.querySelector('iframe');expect(iframe).not.toBeNull();
 expect(iframe.getAttribute('sandbox')).toBe('');expect(iframe.tabIndex).toBe(-1);
 expect(iframe.getAttribute('srcdoc')).toContain('font-size:80px');
 expect(iframe.getAttribute('srcdoc')).toContain('/api/assets/team.webp');
 expect(iframe.getAttribute('srcdoc')).not.toContain('recordGrade');
});

test('PPT/PDF background remains proportional and broken assets have an explicit fallback',()=>{
 const p=project({width:1200,height:1600,backgroundImage:'https://images.test/cover.png',elements:[]});
 act(()=>root.render(<CourseCoverPreview project={p}/>));
 expect(host.querySelector('img').getAttribute('src')).toBe('https://images.test/cover.png');
 expect(host.querySelector('img').style.objectFit).toBe('contain');
 act(()=>host.querySelector('img').dispatchEvent(new Event('error')));
 expect(host.textContent).toContain('Imagem da capa indisponível');
 expect(host.textContent).toContain('Curso de teste');
});

test('title fallback is only used for an empty cover and video/quiz never run',()=>{
 act(()=>root.render(<CourseCoverPreview project={project({elements:[]})}/>));
 expect(host.textContent).toContain('Curso de teste');
 act(()=>root.render(<CourseCoverPreview project={project({elements:[{id:'v',type:'video',src:'https://video.test/a.mp4'},
  {id:'q',type:'quiz',quizConfig:{title:'Meu Quiz'}}]})}/>));
 expect(host.querySelector('video,audio')).toBeNull();expect(host.textContent).toContain('Meu Quiz');
});

test('off-screen covers defer HTML mounting until intersection',()=>{
 let intersect;const disconnect=jest.fn();
 global.IntersectionObserver=jest.fn(callback=>{intersect=callback;return{observe:jest.fn(),disconnect};});
 const p=project({elements:[{type:'html',htmlContent:'<h1>Capa</h1>'}]});
 act(()=>root.render(<CourseCoverPreview project={p}/>));expect(host.querySelector('iframe')).toBeNull();
 act(()=>intersect([{isIntersecting:true}]));expect(host.querySelector('iframe')).not.toBeNull();
 act(()=>intersect([{isIntersecting:false}]));expect(host.querySelector('iframe')).toBeNull();
 delete global.IntersectionObserver;
});
