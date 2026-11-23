import React from 'react';
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {renderToStaticMarkup} from 'react-dom/server';
import ConfigPanel from './ConfigPanel';
jest.mock('@/lib/utils',()=>({cn:(...values)=>values.filter(Boolean).join(' ')}),{virtual:true});
jest.mock('../../../components/ui/select',()=>{const Box=({children})=><div>{children}</div>;return {Select:Box,SelectTrigger:Box,SelectValue:()=>null,SelectContent:Box,SelectItem:Box};});
jest.mock('../../../components/ui/slider',()=>({Slider:()=>null}));
jest.mock('../../../components/ui/scroll-area',()=>({ScrollArea:({children})=><div>{children}</div>}));
jest.mock('../../../components/ui/checkbox',()=>({Checkbox:()=>null}));
jest.mock('../../../components/ui/tabs',()=>{const Box=({children})=><div>{children}</div>;return {Tabs:Box,TabsList:Box,TabsTrigger:Box,TabsContent:Box};});
jest.mock('../../../components/AnimPreviewButton',()=>({AnimPreviewButton:()=>null}));
jest.mock('../../../components/SimulatorExperienceOptions',()=>()=>null);
jest.mock('../../../components/AstryxAppearanceDialog',()=>({AstryxAppearanceButton:()=>null}));
jest.mock('../../../contexts/AuthContext',()=>({authHeaders:()=>({}),useAuth:()=>({canCreateSimulators:false})}));

test.each(['standard','illustrated_journey','guided_practice_project'])('initial adaptive choice in %s is off by default, updates only new configuration',async mode=>{
 global.IS_REACT_ACT_ENVIRONMENT=true;
 const host=document.createElement('div');document.body.append(host);const root=createRoot(host);
 const config={title:'Tema qualquer',visualCourseMode:mode,enabledResources:{quiz:true,interactive_assessment:true},assessmentQuestionCount:1,guidedQuestionsPerUnit:1};
 const before=JSON.stringify(config),setConfig=jest.fn();
 await act(async()=>root.render(<ConfigPanel config={config} setConfig={setConfig} loading={false} templates={[]} designTemplates={[]}/>));
 const option=host.querySelector('[aria-label="Avaliações adaptativas nos novos recursos"]');
 expect(option.checked).toBe(false);
 await act(async()=>option.click());
 expect(setConfig.mock.calls[0][0](config)).toEqual({...config,adaptiveAssessments:true,assessmentQuestionCount:3,guidedQuestionsPerUnit:3});
 expect(JSON.stringify(config)).toBe(before);
 await act(async()=>root.unmount());host.remove();
});

test('guided mode uses interactive assessments and exposes image-credit notice without replacing existing options',()=>{
 const html=renderToStaticMarkup(<ConfigPanel config={{title:'Planejamento',visualCourseMode:'guided_practice_project',enabledResources:{}}} setConfig={()=>{}} loading={false} templates={[]} designTemplates={[]}/>);
 expect(html).toContain('Avaliações interativas');expect(html).toContain('sem o Quiz tradicional');
 expect(html).toContain('Gerar imagem IA para cada questão e salvar na biblioteca');
 expect(html).toContain('Imagens das avaliações consomem créditos');
 expect(html).toMatch(/data-testid="guidedQuestionsPerUnit"[^>]*value="3"/);
 expect(html).toMatch(/data-testid="guidedPassingScore"[^>]*value="80"/);
});

test('standard mode exposes independent interactive assessment options alongside Quiz',()=>{
 const html=renderToStaticMarkup(<ConfigPanel config={{title:'Curso',visualCourseMode:'standard',enabledResources:{quiz:true,interactive_assessment:true}}} setConfig={()=>{}} loading={false} templates={[]} designTemplates={[]}/>);
 expect(html).toContain('data-testid="assessment-resource-options"');
 expect(html).toContain('Uma Avaliação interativa por módulo');
 expect(html).toContain('Os Quizzes continuam independentes');
 expect(html).toContain('Questões e imagens usam créditos');
});

test.each(['standard','illustrated_journey','guided_practice_project'])('Astryx is an additive visual design in %s without replacing learning modes',mode=>{
 const astryx={id:'astryx',name:'Astryx',creationOnly:true,description:'Novo design responsivo',palette:{primary:'#172744',accent:'#315ad1',contentBg:'#f4f7fc',text:'#172744'},fonts:{heading:'Arial'}};
 const old={id:'clean-light',name:'Minimal Claro',palette:{},fonts:{}};
 const html=renderToStaticMarkup(<ConfigPanel config={{title:'Outro assunto',visualCourseMode:mode,enabledResources:{quiz:true,interactive_assessment:true}}} setConfig={()=>{}} loading={false} templates={[]} designTemplates={[old,astryx]} selectedDesignTemplate={astryx}/>);
 expect(html).toContain('data-testid="design-template-astryx"');
 expect(html).toContain('data-testid="design-template-clean-light"');
 expect(html).toContain('qualquer tema');expect(html).toContain('Sem créditos adicionais pelo design');
 expect(html).toContain('Slides premium variados');expect(html).toContain('Jornada Visual Ilustrada');
 expect(html).toContain('Percurso guiado com prática e projeto');
});
