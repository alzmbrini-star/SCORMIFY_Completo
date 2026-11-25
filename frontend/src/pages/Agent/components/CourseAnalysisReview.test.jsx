import React, {act} from 'react';
import {createRoot} from 'react-dom/client';
import {CourseReviewPanel} from './CoursePanels';

jest.mock('../../../contexts/AuthContext',()=>({authHeaders:()=>({})}));
jest.mock('../../../components/AnimPreviewButton',()=>({AnimPreviewButton:()=>null}));
jest.mock('../../../components/quiz/QuizPlayer',()=>()=>null);
jest.mock('./AvatarSceneControls',()=>({SlideTypeSwitcher:()=>null,AvatarSceneMockup:()=>null}));
jest.mock('./PreviewTextEditor',()=>()=>null);
jest.mock('./ImprovementHtmlPreview',()=>()=>null);
jest.mock('../../../components/ui/button',()=>({Button:({variant,size,...props})=><button {...props}/>}));
jest.mock('../../../components/ui/input',()=>({Input:props=><input {...props}/>}));
jest.mock('../../../components/ui/textarea',()=>({Textarea:props=><textarea {...props}/>}));
jest.mock('../../../components/ui/card',()=>({Card:props=><div {...props}/>,CardContent:props=><div {...props}/>,CardHeader:props=><div {...props}/>,CardTitle:props=><h3 {...props}/>}));
jest.mock('../../../components/ui/badge',()=>({Badge:({variant,...props})=><span {...props}/>}));
jest.mock('../../../components/ui/scroll-area',()=>({ScrollArea:props=><div {...props}/>}));
jest.mock('../../../components/ui/select',()=>({Select:()=>null,SelectContent:()=>null,SelectItem:()=>null,SelectTrigger:()=>null,SelectValue:()=>null}));
jest.mock('../../../components/ui/slider',()=>({Slider:()=>null}));
jest.mock('../../../components/ui/checkbox',()=>({Checkbox:({checked,...props})=><input type="checkbox" checked={checked} readOnly {...props}/>}));
jest.mock('../../../components/ui/tabs',()=>({Tabs:()=>null,TabsList:()=>null,TabsTrigger:()=>null,TabsContent:()=>null}));

let host,root;
const analysis={overallScore:7,improvements:[{slideIndex:5,type:'scenario',priority:'media',description:'Praticar decisões',
 suggestion:'Escolher caminhos com desfechos diferentes',classificationNote:'Classificação ajustada: caminhos e consequências.'}]};
beforeEach(()=>{
 global.IS_REACT_ACT_ENVIRONMENT=true;
 global.fetch=jest.fn().mockResolvedValue({ok:true,json:async()=>({configured:false,avatars:[],voices:[]})});
 host=document.createElement('div');document.body.appendChild(host);root=createRoot(host);
});
afterEach(()=>{act(()=>root.unmount());host.remove();jest.restoreAllMocks();});
function panel(overrides={}) {return <CourseReviewPanel course={{id:'p',name:'Curso'}} analysis={analysis} selectedImprovements={[]} toggleImprovement={()=>{}} onApply={()=>{}} {...overrides}/>;}

test('connection failure displays recovery button instead of a blank analysis panel',async()=>{
 const retry=jest.fn();
 await act(async()=>root.render(panel({analysis:null,analysisError:'Conexão interrompida. Curso preservado.',onRetryAnalysis:retry})));
 expect(host.querySelector('[role="alert"]').textContent).toContain('Conexão interrompida');
 act(()=>host.querySelector('[data-testid="retry-course-analysis"]').click());
 expect(retry).toHaveBeenCalledTimes(1);
});

test('decision scenario stays distinct, all three formats are offered, manual changes are explicit',async()=>{
 const change=jest.fn(),select=jest.fn();
 await act(async()=>root.render(panel({onTypeOverride:change,toggleImprovement:select})));
 const picker=host.querySelector('select[aria-label="Formato do recurso para o slide 6"]');
 expect(picker.value).toBe('scenario');expect(picker.options).toHaveLength(3);
 expect(host.textContent).toContain('Classificação ajustada');
 act(()=>{picker.value='quiz';picker.dispatchEvent(new Event('change',{bubbles:true}));});
 expect(change).toHaveBeenCalledWith(0,'quiz');
 expect(host.textContent).toContain('Nada foi convertido no curso.');
 expect(host.textContent).toContain('a prévia será adaptada');
 act(()=>host.querySelector('[data-testid="improvement-0"] .cursor-pointer').click());
 expect(select.mock.calls[0][0].type).toBe('quiz');
});

test('format overrides do not leak to another course or renewed analysis',async()=>{
 await act(async()=>root.render(panel()));
 let picker=host.querySelector('select[aria-label="Formato do recurso para o slide 6"]');
 act(()=>{picker.value='interactive_assessment';picker.dispatchEvent(new Event('change',{bubbles:true}));});
 await act(async()=>root.render(panel({course:{id:'other'},analysis:{...analysis}})));
 picker=host.querySelector('select[aria-label="Formato do recurso para o slide 6"]');
 expect(picker.value).toBe('scenario');
});
