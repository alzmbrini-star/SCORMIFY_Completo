import React, {act} from 'react';
import {createRoot} from 'react-dom/client';
import SplitPreview from './SplitPreview';
import CoursePreview from './CoursePreview';
import {getApiUrl} from '../../utils/apiUrl';
import {fluidVideoQuizSlide} from '../../utils/videoQuizPreview';
jest.mock('../assessment/AssessmentBuilder',()=>({buildAssessmentHtml:jest.fn()}));
jest.mock('@/lib/utils',()=>({cn:(...items)=>items.filter(Boolean).join(' ')}),{virtual:true});
jest.mock('../ui/slider',()=>({Slider:()=>null}));
jest.mock('../ui/scroll-area',()=>({ScrollArea:({children})=><div>{children}</div>}));
globalThis.IS_REACT_ACT_ENVIRONMENT=true;
const config={src:'/api/projects/p/assets/kling_saved.mp4',key:'same-resume-key',graded:false,checkpoints:[{at:4,question:'Escolha?',options:['A','B'],correctIndex:1}]};
const element={id:'e',type:'html',x:0,y:0,width:1920,height:820,htmlContent:'<!doctype html><html><head></head><body><script id="video-quiz-data" type="application/json">'+JSON.stringify(config)+'</script></body></html>'};
const slide={id:'s',width:1920,height:820,duration:10,elements:[element]};

describe.each([['split',SplitPreview,8],['course',CoursePreview,48]])('%s video preview', (name,Component,padding)=>{
  let container,root,resize,width;
  beforeEach(()=>{
    width=800;
    global.ResizeObserver=class {constructor(cb){resize=cb;}observe(){}disconnect(){}};
    jest.spyOn(HTMLElement.prototype,'getBoundingClientRect').mockImplementation(()=>({width,height:600,top:0,left:0,right:width,bottom:600}));
    container=document.createElement('div');document.body.appendChild(container);root=createRoot(container);
  });
  afterEach(async()=>{await act(async()=>root.unmount());container.remove();jest.restoreAllMocks();});
  async function renderSlide(selected=slide){await act(async()=>root.render(<Component course={{slides:[selected]}} projectId="p" currentSlideIndex={0} onSlideChange={jest.fn()} onClose={jest.fn()}/>));}
  test('resolves snapshot media, upgrades saved UI, and reflows on panel resize without replacing iframe',async()=>{
    const original=JSON.stringify(slide);await renderSlide();
    const frame=container.querySelector('iframe');
    const doc=new DOMParser().parseFromString(frame.getAttribute('srcdoc'),'text/html');
    expect(JSON.parse(doc.getElementById('video-quiz-data').textContent)).toEqual({...config,src:getApiUrl()+config.src});
    expect(doc.getElementById('video-quiz-feedback-v1')).not.toBeNull();
    expect(doc.getElementById('video-quiz-responsive-v1')).not.toBeNull();
    const stage=container.querySelector(`[data-testid="${name}-preview-stage"]`);
    expect(stage.style.width).toBe((800-padding)+'px');expect(stage.style.transform).toBe('scale(1)');
    width=390;await act(async()=>resize());
    expect(stage.style.width).toBe((390-padding)+'px');
    expect(container.querySelector('iframe')).toBe(frame);
    expect(JSON.stringify(slide)).toBe(original);
  });
  test('does not reflow overlays and retains their timing/geometry',async()=>{
    const custom={...slide,elements:[element,{id:'image',type:'image',src:'https://example.org/image.png',x:300,y:200,width:100,height:80,startTime:3}]};
    expect(fluidVideoQuizSlide(custom)).toBe(false);await renderSlide(custom);
    const stage=container.querySelector(`[data-testid="${name}-preview-stage"]`);
    expect(stage.style.width).toBe('1920px');expect(stage.style.transform).not.toBe('scale(1)');
    expect(container.querySelector('img')).toBeNull();
  });
});
